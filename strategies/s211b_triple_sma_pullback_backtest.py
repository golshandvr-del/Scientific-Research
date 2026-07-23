# -*- coding: utf-8 -*-
"""
S211b — بک‌تستِ معاملاتیِ ترکیبِ سه SMA (8/70/240) — پاسخ به User Note (مرحله ۱ و ۲)
================================================================================
یافتهٔ S211: ادعای «bounce/واکنشِ صرف» به SMAها آماری رد شد (base-rate طلا خودش
~۸۵–۹۰٪ است؛ لمسِ SMA اطلاعاتِ افزوده ندارد). اما «واکنش» می‌تواند *جهت‌دار* و
*رژیم-محور* باشد. تفسیرِ حرفه‌ایِ triple-MA:
  • SMA8   = روندِ کوتاه‌مدت (ماشه)
  • SMA70  = روندِ میان‌مدت (بدنه)
  • SMA240 = روندِ بلندمدت (فیلترِ رژیم)

قاعدهٔ کلاسیکِ این ست (Guppy-وار): در چیدمانِ صعودی
`SMA8 > SMA70 > SMA240` (up-stack) وقتی قیمت به SMA8 pullback می‌کند و دوباره
بالای آن close می‌کند ⇒ ورودِ LONG در جهتِ روند. متقارن برای SHORT.

این فایل این قاعده را به‌صورتِ *بک‌تستِ کامل با موتورِ pip-native و هزینهٔ واقعی*
روی XAUUSD همهٔ تایم‌فریم‌ها (شروع از M5 طبقِ قانونِ مولتی‌تایم‌فریم) می‌آزماید،
با گیتِ سختِ ضدِ overfit (net>0 + هر دو نیمه + ۴/۴ walk-forward).
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import sma, atr
from engine.scalp_engine import simulate_trades, run_capital, ASSETS


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def build_signals(df, p_fast, p_mid, p_slow, pullback_atr=0.5):
    """
    سیگنالِ pullback در جهتِ چیدمانِ سه SMA.
    LONG: up-stack (fast>mid>slow) و کندلِ قبل low زیرِ fast رفته (pullback)
          و کندلِ فعلی دوباره بالای fast close کرده (بازگشت به روند).
    SHORT: متقارن.
    """
    c = df['close'].values.astype(float)
    l = df['low'].values.astype(float)
    h = df['high'].values.astype(float)
    sf = sma(df['close'], p_fast).values
    sm = sma(df['close'], p_mid).values
    ss = sma(df['close'], p_slow).values
    n = len(df)

    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)

    for i in range(p_slow + 1, n):
        if np.isnan(ss[i]) or np.isnan(sm[i]) or np.isnan(sf[i]):
            continue
        up_stack = sf[i] > sm[i] > ss[i]
        dn_stack = sf[i] < sm[i] < ss[i]
        if up_stack:
            # pullback: کندلِ قبل low آن را زیرِ fast برده، حالا close بالای fast
            if l[i - 1] <= sf[i - 1] and c[i] > sf[i]:
                long_sig[i] = True
        elif dn_stack:
            if h[i - 1] >= sf[i - 1] and c[i] < sf[i]:
                short_sig[i] = True
    return long_sig, short_sig


def hard_gate(trades, df, asset):
    """گیتِ سختِ ضدِ overfit: net، دو نیمه، ۴ پنجرهٔ walk-forward."""
    if trades is None or len(trades) == 0:
        return dict(n=0, net=0, wr=0, pass_gate=False, reason='no-trades')

    def _net(t):
        if t is None or len(t) == 0:
            return 0.0
        stats, _ = run_capital(t, asset)
        return stats['net_profit']

    net = _net(trades)
    wr = 100.0 * (trades['outcome'] == 'win').mean()
    n = len(trades)

    # دو نیمه بر اساسِ signal_bar
    t1 = trades[trades['signal_bar'] < len(df) // 2]
    t2 = trades[trades['signal_bar'] >= len(df) // 2]
    net_h1 = _net(t1)
    net_h2 = _net(t2)

    # ۴ پنجرهٔ walk-forward
    wf = []
    bounds = np.linspace(0, len(df), 5).astype(int)
    for k in range(4):
        tw = trades[(trades['signal_bar'] >= bounds[k]) & (trades['signal_bar'] < bounds[k + 1])]
        wf.append(_net(tw))

    pass_gate = (net > 0 and net_h1 > 0 and net_h2 > 0 and all(w > 0 for w in wf) and wr >= 40.0)
    return dict(n=n, net=round(net), wr=round(wr, 1),
                net_h1=round(net_h1), net_h2=round(net_h2),
                wf=[round(w) for w in wf], pass_gate=bool(pass_gate))


def main():
    asset = 'XAUUSD'
    tfs = ['M5', 'M15', 'M30', 'H1', 'H4']
    # TP/SL متناسب با TF (ATR طلا در TFهای بزرگ‌تر بزرگ‌تر است)
    tpsl_map = {
        'M5':  dict(sl=100, tp=200, mh=48),
        'M15': dict(sl=150, tp=300, mh=32),
        'M30': dict(sl=200, tp=400, mh=24),
        'H1':  dict(sl=250, tp=500, mh=16),
        'H4':  dict(sl=400, tp=800, mh=12),
    }
    p_fast, p_mid, p_slow = 8, 70, 240

    print("=" * 100)
    print(f"S211b — بک‌تستِ pullback در چیدمانِ سه SMA ({p_fast}/{p_mid}/{p_slow}) — XAUUSD")
    print("=" * 100)
    print(f"{'TF':>4} {'dir':>6} {'n':>6} {'net':>10} {'wr':>6} {'h1':>8} {'h2':>8} {'walk-forward':>28}  gate")
    print("-" * 100)

    results = []
    for tf in tfs:
        path = f'data/XAUUSD_{tf}.csv'
        if not os.path.exists(path):
            continue
        df = load(path)
        cfg = tpsl_map[tf]
        # override asset file for this TF
        ASSETS[asset]['file'] = path
        ls, ss = build_signals(df, p_fast, p_mid, p_slow)

        for label, lsig, shsig in [('LONG', ls, np.zeros(len(df), bool)),
                                   ('SHORT', np.zeros(len(df), bool), ss)]:
            trades = simulate_trades(df, lsig, shsig, cfg['sl'], cfg['tp'], asset,
                                     max_hold=cfg['mh'])
            g = hard_gate(trades, df, asset)
            g['tf'] = tf; g['dir'] = label
            results.append(g)
            wf_str = str(g.get('wf', []))
            mark = "✅PASS" if g['pass_gate'] else "✗"
            print(f"{tf:>4} {label:>6} {g['n']:>6} {g['net']:>10} {g['wr']:>6} "
                  f"{g.get('net_h1',0):>8} {g.get('net_h2',0):>8} {wf_str:>28}  {mark}")
        print("-" * 100)

    os.makedirs('results', exist_ok=True)
    with open('results/_s211b_triple_sma_pullback.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("saved: results/_s211b_triple_sma_pullback.json")


if __name__ == '__main__':
    main()
