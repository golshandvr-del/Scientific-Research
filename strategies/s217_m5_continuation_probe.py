"""
s217_m5_continuation_probe.py — کاوشِ لایهٔ «تداومِ روند» روی XAUUSD M5 (پاسخِ User Note)
================================================================================
> قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD). WR≥40٪ کف. رکورد قبلی = +$262,519.

مسئلهٔ User Note:
  کاربر یک روندِ صعودیِ قویِ خالص روی M5/M15 دید (>۱۰ کندلِ صعودیِ پیاپی، +۳۰$ در ۴ ساعت)
  اما اسکالپِ M5ِ زنده هیچ سیگنالی نداد. علت (تشخیصِ ما): منطقِ فعالِ اسکالپِ M5 (S79)
  فقط «خریدِ پولبک» است — شرطِ ورود = RSI(21) < 35. در یک روندِ صعودیِ قویِ خالص، RSI
  هرگز به زیرِ ۳۵ نمی‌رسد (بلکه ۵۰–۸۰ می‌ماند) ⇒ استراتژی در بهترین روندها فلج است.

فرضیهٔ علمی:
  یک لایهٔ «تداومِ روند» (continuation / breakout-pullback-shallow) که در روندِ صعودیِ
  قوی *بدونِ* نیازِ به پولبکِ عمیق وارد شود، یک لبهٔ مکملِ ناهمپوشان با لایهٔ پولبک است.

منطقِ تستی (چند واریانت):
  روند:   EMA20 > EMA100  (هم‌راستا با S79)
  تداوم:  رشتهٔ ≥ RUN کندلِ صعودی در پنجرهٔ اخیر  +  RSI در بازهٔ [RSI_LO, RSI_HI]
          (RSI بالای پولبک اما زیرِ اشباعِ خرید ⇒ «قدرتِ سالم، نه climax»)
  فیلترِ ضدِclimax: کندلِ فعلی نباید بیش از CLX×ATR باشد (پرهیز از خریدِ قله).

هر واریانت روی همهٔ TF×دارایی مستقل گیت می‌شود؛ کاندیدها با قانونِ همپوشانی بررسی
می‌شوند (بعداً در گامِ finalize). این گام فقط «raw gate probe» است.
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

# داده‌ها: از XAUUSD M5 شروع (قانونِ مولتی‌تایم‌فریم) سپس M15/M30/H1 و EURUSD.
PAIRS_TF = [
    ('XAUUSD', 'M5'), ('XAUUSD', 'M15'), ('XAUUSD', 'M30'), ('XAUUSD', 'H1'),
    ('EURUSD', 'M5'), ('EURUSD', 'M15'), ('EURUSD', 'M30'),
]


def load(pair, tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', f'{pair}_{tf}.csv'))
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def ema(x, n):
    a = 2.0 / (n + 1.0)
    out = np.empty(len(x)); out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi(close, n=21):
    d = np.diff(close, prepend=close[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    ru = np.empty(len(close)); rd = np.empty(len(close))
    ru[0] = up[0]; rd[0] = dn[0]
    a = 1.0 / n
    for i in range(1, len(close)):
        ru[i] = a * up[i] + (1 - a) * ru[i - 1]
        rd[i] = a * dn[i] + (1 - a) * rd[i - 1]
    rs = ru / np.where(rd == 0, 1e-9, rd)
    return 100 - 100 / (1 + rs)


def atr(df, n=14):
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.empty(len(tr)); out[0] = tr[0]
    a = 1.0 / n
    for i in range(1, len(tr)):
        out[i] = a * tr[i] + (1 - a) * out[i - 1]
    return out


def continuation_sig(df, run_len, rsi_lo, rsi_hi, clx):
    c = df['close'].values; o = df['open'].values
    ef = ema(c, 20); es = ema(c, 100)
    r = rsi(c, 21); at = atr(df, 14)
    up_bar = (c > o).astype(int)
    # رشتهٔ کندلِ صعودیِ پیاپی تا i (شاملِ i)
    runc = np.zeros(len(c), int)
    for i in range(1, len(c)):
        runc[i] = runc[i - 1] + 1 if up_bar[i] else 0
    cur_range = (df['high'].values - df['low'].values)
    trend = ef > es
    momentum = runc >= run_len
    healthy = (r >= rsi_lo) & (r <= rsi_hi)
    not_climax = cur_range <= clx * at
    return trend & momentum & healthy & not_climax


def run_layer(df, long_sig, sl, tp, mh, asset):
    short = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_sig, short, sl, tp, asset, max_hold=mh)
    if tr is None or len(tr) == 0:
        return None, None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    return st, tr


def gate(df, sig_arr, sl, tp, mh, asset):
    st, tr = run_layer(df, sig_arr, sl, tp, mh, asset)
    if st is None or st['n_trades'] < 30:
        return None
    n = len(df); half = n // 2
    s1, _ = run_layer(df.iloc[:half].reset_index(drop=True), sig_arr[:half], sl, tp, mh, asset)
    s2, _ = run_layer(df.iloc[half:].reset_index(drop=True), sig_arr[half:], sl, tp, mh, asset)
    wf = []
    for k in range(4):
        a = k * (n // 4); b = n if k == 3 else (k + 1) * (n // 4)
        sk, _ = run_layer(df.iloc[a:b].reset_index(drop=True), sig_arr[a:b], sl, tp, mh, asset)
        wf.append(sk['net_profit'] if sk else 0.0)
    both = (s1 and s1['net_profit'] > 0) and (s2 and s2['net_profit'] > 0)
    ok = st['net_profit'] > 0 and both and min(wf) > 0 and st['win_rate'] >= 40
    return dict(net=st['net_profit'], wr=st['win_rate'], n=st['n_trades'],
                pf=st['profit_factor'], h1=(s1['net_profit'] if s1 else 0),
                h2=(s2['net_profit'] if s2 else 0), wf=wf, wf_min=min(wf),
                both=both, ok=ok)


# TP/SL مخصوصِ هر TF (اشتباهِ رایج: یکسان برای همه) — بر پایهٔ ATR نسبیِ TF
TPSL = {
    'M5':  [(80, 40, 12), (120, 80, 12), (150, 100, 18)],
    'M15': [(150, 100, 12), (250, 150, 16), (300, 150, 20)],
    'M30': [(250, 150, 12), (400, 200, 16)],
    'H1':  [(400, 200, 12), (600, 300, 16)],
}
# واریانت‌های تداوم: (run_len, rsi_lo, rsi_hi, clx)
VARIANTS = [
    (4, 50, 75, 2.0),
    (3, 50, 80, 2.5),
    (5, 55, 80, 2.0),
    (4, 45, 70, 1.8),
]


def main():
    print("=" * 90)
    print("s217 — M5/MTF Continuation probe (پاسخِ User Note: خرید در تداومِ روندِ قوی)")
    print("=" * 90, flush=True)
    winners = []
    for pair, tf in PAIRS_TF:
        try:
            df = load(pair, tf)
        except FileNotFoundError:
            continue
        tpsl_list = TPSL.get(tf, [(150, 100, 12)])
        for (rl, rlo, rhi, clx) in VARIANTS:
            sig = continuation_sig(df, rl, rlo, rhi, clx)
            if sig.sum() < 30:
                continue
            for (tp, sl, mh) in tpsl_list:
                g = gate(df, sig, sl, tp, mh, pair)
                if g is None:
                    continue
                tag = f"{pair}-{tf} run{rl} rsi[{rlo},{rhi}] clx{clx} TP{tp}/SL{sl}/mh{mh}"
                mark = "✅" if g['ok'] else "  "
                if g['ok'] or g['net'] > 500:
                    print(f"{mark} {tag}: net=${g['net']:+,.0f} WR={g['wr']:.1f}% "
                          f"n={g['n']} PF={g['pf']:.2f} h1=${g['h1']:+,.0f} h2=${g['h2']:+,.0f} "
                          f"WFmin=${g['wf_min']:+,.0f}", flush=True)
                if g['ok']:
                    winners.append(dict(pair=pair, tf=tf, run=rl, rsi_lo=rlo, rsi_hi=rhi,
                                        clx=clx, tp=tp, sl=sl, mh=mh, **g))
    print("\n" + "=" * 90)
    print(f"تعدادِ کاندیدِ گیت-پاس: {len(winners)}")
    winners.sort(key=lambda w: -w['net'])
    for w in winners[:15]:
        print(f"  {w['pair']}-{w['tf']} run{w['run']} rsi[{w['rsi_lo']},{w['rsi_hi']}] "
              f"TP{w['tp']}/SL{w['sl']}: net=${w['net']:+,.0f} WR={w['wr']:.1f}% n={w['n']}")
    with open(os.path.join(RESULTS, '_s217_continuation_probe.json'), 'w') as f:
        json.dump(winners, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s217_continuation_probe.json")


if __name__ == '__main__':
    main()
