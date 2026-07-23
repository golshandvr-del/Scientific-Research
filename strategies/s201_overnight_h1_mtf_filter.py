"""
s201_overnight_h1_mtf_filter.py — قانونِ سومِ همپوشانی: فیلترِ MTF (H1-confirm) روی Overnight-M15
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪ کف. رکورد = +$252,471.
> قانونِ سومِ همپوشانی: از بخشِ همپوشانِ لایهٔ جدید می‌توان به‌عنوان *فیلتر* استفاده کرد
>   تا WR/net بالا رود.

پس‌زمینه:
  S199 نشان داد H1-Overnight با M15-Overnight همبستهٔ بالا (corr +0.748، همپوشانیِ
  روز-معاملاتی ۸۳–۸۶٪) است ⇒ لایهٔ مستقلِ جدید نیست. طبقِ قانونِ سوم، به‌جای افزودن،
  «تأییدِ H1» را به‌عنوان فیلتر روی entryهای M15 آزمایش می‌کنیم.

فرضیه:
  entryهای Overnightِ M15 (ساعتِ ۲۲/۲۳) وقتی «بافتِ H1 صعودی» است کیفیتِ بهتری دارند.
  چند تعریفِ فیلترِ H1 (forward-safe؛ فقط از کندل‌های H1ِ *بسته‌شده تا زمانِ سیگنال*):
    F1) close آخرین کندلِ H1 بسته‌شده > EMA20(H1)  (روند صعودیِ H1)
    F2) کندلِ H1 قبلی صعودی بود (close>open)
    F3) close(H1) > close(H1) چند کندل قبل (مومنتومِ H1 مثبت)
    F4) نزدیک نبودن به سقفِ اخیرِ H1 (اجتناب از خریدِ اوج) — close < high20(H1)*0.995 ... (اختیاری)

  فیلتر باید: (الف) net را نسبت به baseline کم نکند یا WR را ببرد بالا، (ب) گیتِ سخت
  را حفظ کند، (ج) از قانونِ همپوشانی «حتی ۱٪ ناهمپوشان ارزش دارد» پیروی کند.

روش:
  baseline = Overnight M15 h22-23 SL150/TP500/mh96 (سهمِ مستقل net=+$52,872).
  برای هر فیلتر، سیگنالِ M15 را با mask فیلتر می‌کنیم و مجدداً گیت می‌گیریم.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)

RESULTS = os.path.join(ROOT, 'results')
DATA_M15 = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
DATA_H1 = os.path.join(ROOT, 'data', 'XAUUSD_H1.csv')
CAP, RISK = 10000.0, 1.0
SL, TP, MH = 150, 500, 96


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    return df.reset_index(drop=True)


def build_h1_features(dfh):
    """ویژگی‌های H1 (forward-safe: هر ویژگی از کندلِ H1ِ بسته‌شده استفاده می‌کند)."""
    c = dfh['close']
    ema20 = ind.ema(c, 20)
    dfh = dfh.copy()
    dfh['h1_above_ema'] = (c > ema20).astype(float)
    dfh['h1_bull'] = (dfh['close'] > dfh['open']).astype(float)
    dfh['h1_mom5'] = (c > c.shift(5)).astype(float)
    return dfh


def map_h1_to_m15(dfm, dfh):
    """
    برای هر کندلِ M15، مقدارِ ویژگیِ آخرین کندلِ H1ِ *بسته‌شده پیش از شروعِ این کندلِ M15*
    را نگاشت می‌کند (forward-safe؛ از merge_asof با کلیدِ زمانِ بسته‌شدنِ H1).
    زمانِ بسته‌شدنِ کندلِ H1 = time + 3600 ثانیه. فقط کندل‌های H1 که closeشان <= time(M15)
    است مجازند ⇒ backward asof روی close-time.
    """
    h = dfh.copy()
    h['h1_close_time'] = h['time'] + 3600  # زمانِ بسته‌شدن (unix)
    h = h.sort_values('h1_close_time')
    m = dfm.copy().sort_values('time')
    cols = ['h1_above_ema', 'h1_bull', 'h1_mom5']
    merged = pd.merge_asof(m, h[['h1_close_time'] + cols],
                           left_on='time', right_on='h1_close_time',
                           direction='backward')
    merged = merged.sort_index()
    for col in cols:
        dfm[col] = merged[col].values
    return dfm


def run(df, long_sig, sl=SL, tp=TP, mh=MH):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, sl, tp, 'XAUUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def gate_sig(df, base_mask, filt_mask=None):
    """گیتِ سخت روی سیگنالِ (base AND filter)."""
    sig = base_mask if filt_mask is None else (base_mask & filt_mask)
    n = len(df)
    def seg_net(a, b):
        sub = df.iloc[a:b].reset_index(drop=True)
        subsig = sig[a:b]
        s, _ = run(sub, subsig)
        return s['net_profit'] if s else 0.0
    st, _ = run(df, sig)
    if st is None:
        return None
    net = st['net_profit']; wr = st['win_rate']; ntr = st['n_trades']
    half = n // 2
    h1 = seg_net(0, half); h2 = seg_net(half, n)
    wf = [seg_net(k * (n // 4), n if k == 3 else (k + 1) * (n // 4)) for k in range(4)]
    wf_min = min(wf)
    both = h1 > 0 and h2 > 0
    ok = net > 0 and both and wf_min > 0 and wr >= 40.0
    return dict(net=float(net), wr=float(wr), n=int(ntr), h1=float(h1), h2=float(h2),
                wf=[float(x) for x in wf], wf_min=float(wf_min), both=bool(both), ok=bool(ok))


def main():
    print("=" * 92)
    print("s201 — فیلترِ MTF (H1-confirm) روی Overnight-M15 (قانونِ سومِ همپوشانی)")
    print("=" * 92, flush=True)

    dfm = load(DATA_M15)
    dfh = build_h1_features(load(DATA_H1))
    dfm = map_h1_to_m15(dfm, dfh)
    print(f"داده M15: {len(dfm):,} | نگاشتِ H1 انجام شد (forward-safe merge_asof)\n")

    base = np.isin(dfm['hour'].values, [22, 23])
    gb = gate_sig(dfm, base)
    print(f"── baseline (بدونِ فیلتر): net=${gb['net']:+,.0f}  WR={gb['wr']:.1f}%  n={gb['n']}  "
          f"{'✅' if gb['ok'] else '—'}")

    filters = {
        'F1: close(H1)>EMA20(H1)': dfm['h1_above_ema'].values == 1,
        'F2: کندلِ H1 قبلی صعودی': dfm['h1_bull'].values == 1,
        'F3: مومنتومِ H1 مثبت (5)': dfm['h1_mom5'].values == 1,
        'F1&F2': (dfm['h1_above_ema'].values == 1) & (dfm['h1_bull'].values == 1),
        'F1&F3': (dfm['h1_above_ema'].values == 1) & (dfm['h1_mom5'].values == 1),
        'F1&F2&F3': (dfm['h1_above_ema'].values == 1) & (dfm['h1_bull'].values == 1) & (dfm['h1_mom5'].values == 1),
    }

    print(f"\n{'فیلتر':>28}{'net':>12}{'Δ':>10}{'WR':>7}{'n':>7}{'WFmin':>10} حکم")
    print("-" * 84)
    rows = {}
    for name, fmask in filters.items():
        g = gate_sig(dfm, base, fmask)
        if g is None:
            continue
        delta = g['net'] - gb['net']
        improved = g['ok'] and (g['wr'] > gb['wr'] or g['net'] > gb['net'])
        flag = "✅بهبود" if improved else ("✅گیت" if g['ok'] else "—")
        print(f"{name:>28}${g['net']:>+11,.0f}${delta:>+9,.0f}{g['wr']:>6.1f}%{g['n']:>7}"
              f"${g['wf_min']:>+9,.0f} {flag}", flush=True)
        rows[name] = dict(**g, delta=float(delta), improved=bool(improved))

    # بهترین از نظرِ net در میانِ گیت-پاس‌ها
    passed = {k: v for k, v in rows.items() if v['ok']}
    print(f"\n{'='*92}")
    if passed:
        best = max(passed.items(), key=lambda kv: kv[1]['net'])
        bn, bv = best
        print(f"🏆 بهترین فیلترِ گیت-پاس: {bn}")
        print(f"   net=${bv['net']:+,.0f} (Δ${bv['delta']:+,.0f})  WR={bv['wr']:.1f}%  "
              f"WF={['%+.0f'%x for x in bv['wf']]}")
        # آیا نسبت به baseline بهبودِ WR یا net می‌دهد؟
        if bv['net'] > gb['net']:
            print(f"   ⇒ ✅ فیلتر net را افزایش می‌دهد (Δ+${bv['net']-gb['net']:,.0f}) — بهبودِ واقعی!")
        elif bv['wr'] > gb['wr']:
            print(f"   ⇒ WR بالاتر ({bv['wr']:.1f}% vs {gb['wr']:.1f}%) اما net کمتر؛ "
                  f"فیلتر معاملاتِ سودده را هم حذف کرده.")
        else:
            print(f"   ⇒ فیلتر بهبودِ خالص نمی‌دهد.")
    else:
        print("⚠️ هیچ فیلتری گیتِ سخت را حفظ نکرد.")

    out = dict(baseline=gb, filters=rows)
    with open(os.path.join(RESULTS, '_s201_overnight_h1_filter.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s201_overnight_h1_filter.json")


if __name__ == '__main__':
    main()
