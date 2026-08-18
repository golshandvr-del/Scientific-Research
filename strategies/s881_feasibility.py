#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S881 — امکان‌سنجیِ «چرخشِ چولگی» (Skew Flip) — فقط نیمهٔ اولِ داده (Path C).

رویدادِ خام: عبورِ skew(p) از زیرِ −θ (چولگیِ منفیِ عمیق) به بالای +۰ در ≤k کندل.
سؤال: چند بار در سال شلیک می‌کند؟ (بدونِ بک‌تست، بدونِ WR — فقط شمارش)
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_s881_feasibility.json')

def skew_vec(close, p, chunk=50_000):
    """چولگیِ غلتانِ بازده — گشتاورِ سومِ استانداردشده، برداری و کم‌حافظه."""
    n = len(close)
    ret = np.zeros(n)
    ret[1:] = np.where(close[:-1] != 0, (close[1:] - close[:-1]) / close[:-1], 0.0)
    out = np.full(n, np.nan)
    from numpy.lib.stride_tricks import sliding_window_view
    for c0 in range(p, n, chunk):
        c1 = min(c0 + chunk, n)
        w = sliding_window_view(ret, p)[c0 - p + 1: c1 - p + 1]
        m = w.mean(axis=1, keepdims=True)
        d = w - m
        s2 = (d ** 2).mean(axis=1)
        s3 = (d ** 3).mean(axis=1)
        sd = np.sqrt(s2)
        with np.errstate(divide='ignore', invalid='ignore'):
            sk = np.where(sd > 0, s3 / sd ** 3, 0.0)
        out[c0:c1] = sk
    return out

def count_flips(S, theta, k):
    """لبهٔ عبور به بالای ۰ درحالی‌که در k کندلِ اخیر زیرِ −θ بوده (long)؛ و قرینه (short)."""
    n = len(S)
    below = S < -theta
    above_deep = S > theta
    run_lo = np.zeros(n, dtype=bool)
    run_hi = np.zeros(n, dtype=bool)
    for j in range(1, k + 1):
        run_lo[j:] |= below[:-j]
        run_hi[j:] |= above_deep[:-j]
    cross_up = (S > 0) & np.concatenate(([False], S[:-1] <= 0)) & run_lo
    cross_dn = (S < 0) & np.concatenate(([False], S[:-1] >= 0)) & run_hi
    return int(cross_up.sum()), int(cross_dn.sum())

def main():
    from tools import s434_fast_data as fd
    res = {}
    for tf in ['M5', 'M15', 'M30', 'H1', 'H4', 'D1']:
        d = fd.load_fast('XAUUSD', tf)
        close = np.asarray(d['close'], float)
        t = np.asarray(d['time'], np.int64)
        half = len(close) // 2
        c1, t1 = close[:half], t[:half]
        del d
        years = (t1[-1] - t1[0]) / (365.25 * 86400)
        r = {'n_half': half, 'years': round(float(years), 2), 'events': {}}
        for p in (34, 55, 89):
            S = skew_vec(c1, p)
            for theta in (0.618, 1.0):
                for k in (13, 21):
                    nu, nd = count_flips(S, theta, k)
                    r['events'][f'p{p}_t{theta}_k{k}'] = {
                        'long': nu, 'short': nd,
                        'per_year': round((nu + nd) / years, 1)}
        res[tf] = r
        print(tf, json.dumps(r['events'], ensure_ascii=False)[:300], flush=True)
    with open(OUT, 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('saved ->', OUT)

if __name__ == '__main__':
    main()
