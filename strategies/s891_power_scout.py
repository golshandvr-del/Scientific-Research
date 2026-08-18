#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S891 «رژیمِ بازتابی» — اسکاوتِ توان (پیش از پیش‌ثبت و هر آزمون).

فرضیه: رویدادِ عبورِ نمای هرست از آستانهٔ چارکی (ورود به رژیمِ پایا/روندی)
+ جهت از علامتِ شیبِ قیمت در پنجرهٔ گذشته ⇒ ورود در جهتِ روند.
(Hurst 1951 · Peters, Fractal Market Hypothesis 1994 · Soros, reflexive regimes)

این فایل: نرخِ شلیک + برابریِ (parity) هرستِ برداری با مرجعِ بانک.
"""
import sys, os, json, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine.rqs2 import n_required_for_h3

SPREAD_PIP = 3.3
PIP = 0.1

def hurst_fast(close, p=64, chunk=100_000):
    """R/S هم‌ارزِ دقیقِ indicator_bank.hurst — برداری و تکه‌تکه (سازگار با ۱GB)."""
    x = np.asarray(close, np.float64)
    n = len(x)
    ret = np.zeros(n)
    with np.errstate(divide='ignore', invalid='ignore'):
        ret[1:] = np.where(x[:-1] != 0, np.log(x[1:] / x[:-1]), 0.0)
    ret = np.nan_to_num(ret)
    out = np.full(n, np.nan)
    logp = np.log(p)
    from numpy.lib.stride_tricks import sliding_window_view
    # پنجرهٔ i شاملِ ret[i-p+1..i] است ⇒ اولین خروجی در i=p (مطابقِ مرجع)
    for s in range(p, n, chunk):
        e = min(s + chunk, n)
        W = sliding_window_view(ret[s - p + 1:e], p)   # (e-s, p)
        m = W.mean(axis=1, keepdims=True)
        dev = W - m
        cum = np.cumsum(dev, axis=1)
        R = cum.max(axis=1) - cum.min(axis=1)
        sd = np.sqrt((dev * dev).mean(axis=1))
        ok = (sd > 0) & (R > 0)
        vals = np.full(e - s, 0.5)
        vals[ok] = np.log(R[ok] / sd[ok]) / logp
        out[s:e] = vals
        del W, dev, cum
    return out


def parity_check():
    from engine import indicator_bank as ib
    d = fd.load_fast('XAUUSD', 'D1')
    df = fd.as_dataframe(d).iloc[:3000]
    ref = ib.compute('hurst', df).values
    mine = hurst_fast(df['close'].values, 64)
    m = np.isfinite(ref) & np.isfinite(mine)
    err = float(np.max(np.abs(ref[m] - mine[m])))
    print(f"PARITY hurst_fast vs bank: max|Δ| = {err:.2e}  ({'PASS' if err < 1e-9 else 'FAIL'})")
    return err < 1e-9


def scout_tf(tf, P=64, LSLOPE=21):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    N = len(df)
    split = int(N * 0.70)
    c = df['close'].values
    del df; gc.collect()
    hu = hurst_fast(c[:split], P)
    huv = hu[np.isfinite(hu)]
    rows = []
    slope_up = c[:split] > np.roll(c[:split], LSLOPE)   # جهتِ سادهٔ Lکندلی
    for q in (0.72, 0.86):
        thr = float(np.quantile(huv, q))
        above = hu > thr
        prev = np.roll(above, 1); prev[0] = False
        cross = above & ~prev
        cross[:P + LSLOPE + 2] = False
        n_ev = int(cross.sum())
        n_long = int((cross & slope_up).sum())
        rows.append(dict(q=q, thr=round(thr, 5), events=n_ev,
                         long=n_long, short=n_ev - n_long))
    return dict(tf=tf, bars=N, split=split, rows=rows)


def main():
    if not parity_check():
        print("ABORT: parity failed"); sys.exit(1)
    out = []
    for tf in ['M5', 'M15', 'M30', 'H1', 'H2', 'H6', 'D1']:
        r = scout_tf(tf)
        ev = '  '.join(f"q{x['q']}: n={x['events']} (L{x['long']}/S{x['short']}) thr={x['thr']}"
                       for x in r['rows'])
        print(f"{r['tf']:>4} bars={r['bars']:>9} | {ev}", flush=True)
        out.append(r); gc.collect()
    print("\n--- n_required_for_h3 (p0=0.42) ---")
    for lift in [4, 6, 8, 10, 14]:
        print(f"  lift={lift}pp ⇒ n≥{n_required_for_h3(lift, 0.42):.0f}")
    os.makedirs('results/_s891', exist_ok=True)
    with open('results/_s891/power_scout.json', 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("saved → results/_s891/power_scout.json")


if __name__ == '__main__':
    main()
