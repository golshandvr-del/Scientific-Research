# -*- coding: utf-8 -*-
"""
S211c — بهینه‌سازیِ مقادیرِ سه SMA + فیلترهای اندیکاتوری (مرحله ۲ و ۳ User Note)
================================================================================
یافتهٔ S211b: ست ۸/۷۰/۲۴۰ روی LONG در M15/M30/H1/H4 net مثبتِ بزرگ می‌سازد
(WR≥۴۶٪) اما گیتِ سخت را رد می‌کند چون *نیمهٔ اول (پیش از ~۲۰۲۳) منفی* است.
فرضیه: سیستمِ trend-following در رژیمِ رنج ضرر می‌دهد؛ نیاز به فیلترِ رژیم.

این فایل دو کار می‌کند:
  (مرحله ۲) grid search روی (fast, mid, slow) اطراف پیشنهادِ تریدر.
  (مرحله ۳) افزودنِ فیلترهای اندیکاتوری (قانونِ بهبود: هر تعداد فیلتر مجاز):
     F1: ADX ≥ thr  (فقط روندِ قوی)
     F2: شیبِ SMA-slow صعودی (روندِ بلندمدتِ واقعاً رو-به-بالا)
     F3: فاصلهٔ قیمت تا SMA-slow نه‌خیلی‌دور (نه over-extended)
     F4: RSI در بازهٔ سالم (نه اشباعِ خرید در لحظهٔ ورود)
     F5: ATR-regime (نوسانِ کافی — حذفِ رنجِ مرده)
هدف: پاس‌کردنِ گیتِ سخت (net>0 + هر دو نیمه + ۴/۴ WF + WR≥۴۰) با بیشترین net.
تمرکزِ اولیه روی XAUUSD M15 (بهترین net خام)، سپس تعمیم به بقیه TFها.
"""
import sys, os, json, itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import sma, atr, rsi, adx, rolling_slope
from engine.scalp_engine import simulate_trades, run_capital, ASSETS


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def _net(t, asset):
    if t is None or len(t) == 0:
        return 0.0
    stats, _ = run_capital(t, asset)
    return stats['net_profit']


def hard_gate(trades, df, asset):
    if trades is None or len(trades) == 0:
        return dict(n=0, net=0, wr=0, pass_gate=False)
    net = _net(trades, asset)
    wr = 100.0 * (trades['outcome'] == 'win').mean()
    n = len(trades)
    half = len(df) // 2
    net_h1 = _net(trades[trades['signal_bar'] < half], asset)
    net_h2 = _net(trades[trades['signal_bar'] >= half], asset)
    wf = []
    bounds = np.linspace(0, len(df), 5).astype(int)
    for k in range(4):
        tw = trades[(trades['signal_bar'] >= bounds[k]) & (trades['signal_bar'] < bounds[k + 1])]
        wf.append(_net(tw, asset))
    pg = (net > 0 and net_h1 > 0 and net_h2 > 0 and all(w > 0 for w in wf) and wr >= 40.0)
    return dict(n=n, net=round(net), wr=round(wr, 1), net_h1=round(net_h1),
                net_h2=round(net_h2), wf=[round(w) for w in wf], pass_gate=bool(pg))


def precompute(df, p_fast, p_mid, p_slow):
    ind = {}
    ind['sf'] = sma(df['close'], p_fast).values
    ind['sm'] = sma(df['close'], p_mid).values
    ind['ss'] = sma(df['close'], p_slow).values
    ind['adx'] = adx(df, 14)[0].values if isinstance(adx(df, 14), tuple) else adx(df, 14).values
    ind['rsi'] = rsi(df['close'], 14).values
    ind['atr'] = atr(df, 14).values
    ind['ss_slope'] = rolling_slope(pd.Series(ind['ss']), 20).values
    return ind


def build_long_signals(df, ind, p_slow, adx_thr=0, slope_pos=False,
                       dist_max_atr=None, rsi_max=None, atr_min_pct=None):
    c = df['close'].values.astype(float)
    l = df['low'].values.astype(float)
    sf, sm, ss = ind['sf'], ind['sm'], ind['ss']
    adxv, rsiv, atrv, slopev = ind['adx'], ind['rsi'], ind['atr'], ind['ss_slope']
    n = len(df)
    atr_median = np.nanmedian(atrv)
    long_sig = np.zeros(n, dtype=bool)
    for i in range(p_slow + 1, n):
        if np.isnan(ss[i]) or np.isnan(sm[i]) or np.isnan(sf[i]):
            continue
        if not (sf[i] > sm[i] > ss[i]):
            continue
        if not (l[i - 1] <= sf[i - 1] and c[i] > sf[i]):
            continue
        # فیلترها
        if adx_thr and not (adxv[i] >= adx_thr):
            continue
        if slope_pos and not (slopev[i] > 0):
            continue
        if dist_max_atr is not None and atrv[i] > 0:
            if (c[i] - ss[i]) / atrv[i] > dist_max_atr:
                continue
        if rsi_max is not None and not (rsiv[i] <= rsi_max):
            continue
        if atr_min_pct is not None and not (atrv[i] >= atr_min_pct * atr_median):
            continue
        long_sig[i] = True
    return long_sig


def main():
    asset = 'XAUUSD'
    tf = 'M15'
    path = f'data/XAUUSD_{tf}.csv'
    ASSETS[asset]['file'] = path
    df = load(path)
    sl, tp, mh = 150, 300, 32
    n = len(df)
    zeros = np.zeros(n, dtype=bool)

    print("=" * 104)
    print(f"S211c — XAUUSD {tf} — grid SMA + فیلترهای اندیکاتوری (هدف: پاس‌کردنِ گیتِ سخت)")
    print("=" * 104)

    # ---------- مرحله ۲: grid روی مقادیرِ SMA (بدونِ فیلتر) ----------
    print("\n[مرحله ۲] grid روی (fast,mid,slow) — بدونِ فیلتر:")
    print(f"{'fast':>4} {'mid':>4} {'slow':>4} {'n':>5} {'net':>9} {'wr':>5} {'h1':>7} {'h2':>7} {'wf':>26} gate")
    grid = list(itertools.product([5, 8, 13], [50, 70, 100], [200, 240, 300]))
    best_raw = None
    for pf, pm, ps in grid:
        ind = precompute(df, pf, pm, ps)
        ls = build_long_signals(df, ind, ps)
        tr = simulate_trades(df, ls, zeros, sl, tp, asset, max_hold=mh)
        g = hard_gate(tr, df, asset)
        flag = "✅" if g['pass_gate'] else ""
        print(f"{pf:>4} {pm:>4} {ps:>4} {g['n']:>5} {g['net']:>9} {g['wr']:>5} "
              f"{g.get('net_h1',0):>7} {g.get('net_h2',0):>7} {str(g.get('wf',[])):>26} {flag}")
        if g['net'] > (best_raw['net'] if best_raw else -1e9):
            best_raw = dict(g, pf=pf, pm=pm, ps=ps)

    print(f"\nبهترین (خام، بیشترین net): {best_raw['pf']}/{best_raw['pm']}/{best_raw['ps']} net={best_raw['net']} pass={best_raw['pass_gate']}")

    # ---------- مرحله ۳: افزودنِ فیلتر روی ست پیشنهادِ تریدر 8/70/240 ----------
    print("\n[مرحله ۳] ست تریدر 8/70/240 + جاروبِ فیلترها (قانونِ بهبود):")
    pf, pm, ps = 8, 70, 240
    ind = precompute(df, pf, pm, ps)
    filt_grid = [
        dict(),
        dict(adx_thr=20),
        dict(adx_thr=25),
        dict(slope_pos=True),
        dict(adx_thr=20, slope_pos=True),
        dict(adx_thr=25, slope_pos=True),
        dict(adx_thr=20, slope_pos=True, dist_max_atr=3.0),
        dict(adx_thr=20, slope_pos=True, rsi_max=70),
        dict(adx_thr=20, slope_pos=True, atr_min_pct=0.8),
        dict(adx_thr=20, slope_pos=True, dist_max_atr=3.0, rsi_max=72, atr_min_pct=0.7),
        dict(adx_thr=25, slope_pos=True, dist_max_atr=2.5, rsi_max=70, atr_min_pct=0.8),
    ]
    print(f"{'filters':>62} {'n':>5} {'net':>9} {'wr':>5} {'h1':>7} {'h2':>7} gate")
    best_filt = None
    for fk in filt_grid:
        ls = build_long_signals(df, ind, ps, **fk)
        tr = simulate_trades(df, ls, zeros, sl, tp, asset, max_hold=mh)
        g = hard_gate(tr, df, asset)
        flag = "✅PASS" if g['pass_gate'] else ""
        label = str(fk) if fk else "(none)"
        print(f"{label:>62} {g['n']:>5} {g['net']:>9} {g['wr']:>5} "
              f"{g.get('net_h1',0):>7} {g.get('net_h2',0):>7} {flag}")
        # بهترین: اولویت با pass_gate، سپس net
        score = (1 if g['pass_gate'] else 0, g['net'])
        if best_filt is None or score > best_filt['score']:
            best_filt = dict(g, filters=fk, score=score)

    print(f"\nبهترین فیلتر: {best_filt['filters']}")
    print(f"  net={best_filt['net']} wr={best_filt['wr']} pass_gate={best_filt['pass_gate']} wf={best_filt.get('wf')}")

    out = dict(stage2_best_raw=best_raw, stage3_best_filter=best_filt)
    os.makedirs('results', exist_ok=True)
    with open('results/_s211c_optimize_filter.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print("\nsaved: results/_s211c_optimize_filter.json")


if __name__ == '__main__':
    main()
