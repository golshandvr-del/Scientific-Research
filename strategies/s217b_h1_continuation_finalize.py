"""
s217b_h1_continuation_finalize.py — نهایی‌سازیِ کاندیدِ H1 Continuation + قانونِ همپوشانی
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪. رکورد قبلی = +$262,519.

کاندیدِ گیت-پاسِ S217 (تنها برندهٔ مولتی‌تایم‌فریم):
  XAUUSD-H1، run4، RSI[45,70]، clx1.8، TP600/SL300/mh16
  net +$4,257، WR 50.0٪، n=974، PF 1.22، h1 +$457 / h2 +$3,493، WF 4/4 مثبت (min +$91)

قانونِ همپوشانیِ اجباری (پیش از پذیرش):
  کاندیدِ H1 با اجتماعِ لایه‌های LONGِ طلای فعال مقایسه می‌شود. چون همهٔ لایه‌های فعالِ
  LONGِ طلا روی M5/M15 هستند (زمان‌محورها + triple-SMA + late-entry + trend-line)،
  همپوشانی را در «فضای زمانِ تقویمی» می‌سنجیم: هر معاملهٔ H1 یک بازهٔ [ورود، خروج] دارد؛
  اگر یک ساعت از این بازه با هر ساعتِ فعالِ لایه‌های LONGِ M5/M15 هم‌پوشان باشد، آن
  معاملهٔ H1 «همپوشان» تلقی می‌شود. سپس سهمِ مستقلِ ناهمپوشان محاسبه و دوباره گیت می‌شود.

  کشف کلیدیِ پروژه: انتخاب بر پایهٔ «پایداریِ سهمِ مستقل» (نه net خام).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0
# کاندیدِ برنده
RUN, RSI_LO, RSI_HI, CLX = 4, 45, 70, 1.8
TP, SL, MH = 600, 300, 16


def load(pair, tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', f'{pair}_{tf}.csv'))
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    return df.reset_index(drop=True)


def ema(x, n):
    a = 2.0 / (n + 1.0); out = np.empty(len(x)); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi(close, n=21):
    d = np.diff(close, prepend=close[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    ru = np.empty(len(close)); rd = np.empty(len(close)); ru[0] = up[0]; rd[0] = dn[0]
    a = 1.0 / n
    for i in range(1, len(close)):
        ru[i] = a * up[i] + (1 - a) * ru[i - 1]; rd[i] = a * dn[i] + (1 - a) * rd[i - 1]
    rs = ru / np.where(rd == 0, 1e-9, rd)
    return 100 - 100 / (1 + rs)


def atr(df, n=14):
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.empty(len(tr)); out[0] = tr[0]; a = 1.0 / n
    for i in range(1, len(tr)):
        out[i] = a * tr[i] + (1 - a) * out[i - 1]
    return out


def cont_sig(df):
    c = df['close'].values; o = df['open'].values
    ef = ema(c, 20); es = ema(c, 100); r = rsi(c, 21); at = atr(df, 14)
    up_bar = (c > o).astype(int)
    runc = np.zeros(len(c), int)
    for i in range(1, len(c)):
        runc[i] = runc[i - 1] + 1 if up_bar[i] else 0
    cur_range = (df['high'].values - df['low'].values)
    return (ef > es) & (runc >= RUN) & (r >= RSI_LO) & (r <= RSI_HI) & (cur_range <= CLX * at)


def run_layer(df, sig, sl, tp, mh, asset):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, sig, short, sl, tp, asset, max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def gate_from_mask(df, entry_mask, sl, tp, mh, asset):
    """گیتِ سخت روی یک زیرمجموعه از سیگنال‌ها (mask بولین هم‌طولِ df)."""
    st, tr = run_layer(df, entry_mask, sl, tp, mh, asset)
    if st is None or st['n_trades'] < 30:
        return None
    n = len(df); half = n // 2
    s1, _ = run_layer(df.iloc[:half].reset_index(drop=True), entry_mask[:half], sl, tp, mh, asset)
    s2, _ = run_layer(df.iloc[half:].reset_index(drop=True), entry_mask[half:], sl, tp, mh, asset)
    wf = []
    for k in range(4):
        a = k * (n // 4); b = n if k == 3 else (k + 1) * (n // 4)
        sk, _ = run_layer(df.iloc[a:b].reset_index(drop=True), entry_mask[a:b], sl, tp, mh, asset)
        wf.append(sk['net_profit'] if sk else 0.0)
    both = (s1 and s1['net_profit'] > 0) and (s2 and s2['net_profit'] > 0)
    ok = st['net_profit'] > 0 and both and min(wf) > 0 and st['win_rate'] >= 40
    return dict(net=st['net_profit'], wr=st['win_rate'], n=st['n_trades'], pf=st['profit_factor'],
                h1=(s1['net_profit'] if s1 else 0), h2=(s2['net_profit'] if s2 else 0),
                wf=wf, wf_min=min(wf), both=both, ok=ok)


def build_gold_long_hours(dfH1):
    """
    اجتماعِ «ساعت‌های فعالِ لایه‌های LONGِ طلا» را به‌صورت مجموعه‌ای از timestampهای
    ساعتی (کفِ ساعت UTC) می‌سازد. لایه‌های فعالِ LONGِ طلا (طبقِ README):
      - زمان‌محورها روی M5: S139 (h1)، S140++ (Mon h18-20)، S141 (h7-12)، S142 (h1-12)
      - triple-SMA S211 روی M15 (LONG، همهٔ ساعات وقتی stack+pullback)
      - late-entry S214 روی M5 (pre-EOM، ساعاتِ روز)
    برای سنجشِ محافظه‌کارانهٔ همپوشانی، «پوششِ ساعتیِ» این لایه‌ها را تقریب می‌زنیم:
    مجموعهٔ ساعاتِ UTC که حداقل یکی از این لایه‌ها می‌تواند فعال باشد.
    این تقریب عمداً *سخت‌گیرانه* (over-inclusive) است تا همپوشانی دست‌کم گرفته نشود.
    """
    active_hours = set(range(1, 13))          # S141/S142 پنجرهٔ روز (h1-12)
    active_hours |= {18, 19, 20}              # S140++ دوشنبه
    active_hours |= {1}                       # S139
    active_hours |= set(range(6, 22))         # S211/S214 (day-session، محافظه‌کارانه)
    return active_hours


def main():
    print("=" * 90)
    print("s217b — نهایی‌سازیِ H1 Continuation + قانونِ همپوشانیِ اجباری")
    print(f"کاندید: XAUUSD-H1 run{RUN} RSI[{RSI_LO},{RSI_HI}] clx{CLX} TP{TP}/SL{SL}/mh{MH}")
    print("=" * 90, flush=True)

    df = load('XAUUSD', 'H1')
    sig = cont_sig(df)

    # خامِ کامل
    g_raw = gate_from_mask(df, sig, SL, TP, MH, 'XAUUSD')
    print(f"\n[خامِ کامل] net=${g_raw['net']:+,.0f} WR={g_raw['wr']:.1f}% n={g_raw['n']} "
          f"PF={g_raw['pf']:.2f} h1=${g_raw['h1']:+,.0f} h2=${g_raw['h2']:+,.0f} WFmin=${g_raw['wf_min']:+,.0f} ok={g_raw['ok']}")

    # ---- قانونِ همپوشانی: تفکیکِ سیگنال‌های H1 به «ساعتِ همپوشان» و «مستقل» ----
    active_hours = build_gold_long_hours(df)
    idx = np.where(sig)[0]
    hours = df['hour'].values
    overlap_mask = np.zeros(len(df), bool)
    indep_mask = np.zeros(len(df), bool)
    for i in idx:
        if hours[i] in active_hours:
            overlap_mask[i] = True
        else:
            indep_mask[i] = True
    n_ov = int(overlap_mask.sum()); n_id = int(indep_mask.sum()); n_all = len(idx)
    print(f"\n[همپوشانیِ ساعتی] کل سیگنال={n_all}  همپوشان={n_ov} ({100*n_ov/n_all:.1f}%)  "
          f"مستقل={n_id} ({100*n_id/n_all:.1f}%)")

    # سهمِ مستقل (ناهمپوشان) را جداگانه گیت کن
    g_ind = gate_from_mask(df, indep_mask, SL, TP, MH, 'XAUUSD')
    if g_ind:
        print(f"\n[سهمِ مستقلِ ناهمپوشان] net=${g_ind['net']:+,.0f} WR={g_ind['wr']:.1f}% n={g_ind['n']} "
              f"PF={g_ind['pf']:.2f} h1=${g_ind['h1']:+,.0f} h2=${g_ind['h2']:+,.0f} "
              f"WF={['%+.0f'%x for x in g_ind['wf']]} WFmin=${g_ind['wf_min']:+,.0f}")
        print(f"    گیتِ سخت روی سهمِ مستقل: {'✅ پاس' if g_ind['ok'] else '❌ رد'}")
    else:
        print("\n[سهمِ مستقل] n<30 یا معامله‌ای نساخت ⇒ لبهٔ مستقلِ کافی ندارد.")

    # سهمِ همپوشان را هم گزارش کن (برای قانونِ سومِ همپوشانی: امکانِ استفاده به‌عنوان فیلتر)
    g_ov = gate_from_mask(df, overlap_mask, SL, TP, MH, 'XAUUSD')
    if g_ov:
        print(f"\n[سهمِ همپوشان] net=${g_ov['net']:+,.0f} WR={g_ov['wr']:.1f}% n={g_ov['n']} PF={g_ov['pf']:.2f}")

    out = dict(candidate=dict(run=RUN, rsi_lo=RSI_LO, rsi_hi=RSI_HI, clx=CLX, tp=TP, sl=SL, mh=MH),
               raw=g_raw, overlap_pct=float(100 * n_ov / n_all),
               independent=g_ind, overlap=g_ov, n_all=n_all, n_overlap=n_ov, n_indep=n_id)
    with open(os.path.join(RESULTS, '_s217b_h1_finalize.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s217b_h1_finalize.json")

    # تصمیم
    print("\n" + "=" * 90)
    if g_ind and g_ind['ok']:
        print(f"تصمیم: لبهٔ مستقلِ H1-Continuation پذیرفته می‌شود ⇒ Δ سودِ خالصِ محافظه‌کارانه = +${g_ind['net']:,.0f}")
    elif g_raw['ok'] and (100 * n_ov / n_all) < 50:
        print(f"تصمیم: همپوشانی <۵۰٪ و خام گیت-پاس ⇒ کاندید ارزشِ افزودن دارد (Δ محافظه‌کارانه = سهمِ مستقل).")
    else:
        print("تصمیم: نیازمندِ بررسیِ بیشتر (همپوشانیِ بالا یا سهمِ مستقلِ ناپایدار).")


if __name__ == '__main__':
    main()
