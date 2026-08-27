#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S884 — امکان‌سنجی «شکست خشکسالی» (Dormancy Break) — فقط نیمهٔ اول، فقط شمارش.

رویداد long: close[t] > max(high[t-W..t-1]) (قلهٔ تازهٔ W-کندلی) درحالی‌که
از آخرین قلهٔ تازهٔ قبلی حداقل Dمین کندل گذشته باشد (خشکسالی).
short قرینه با کف. بدون نگاه به جلو.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_s884_feasibility.json')


def rolling_max_prev(x, W):
    """max(x[t-W..t-1]) — بدون شامل شدن t. NaN برای t<W."""
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(x)
    out = np.full(n, np.nan)
    if n <= W:
        return out
    out[W:] = sliding_window_view(x, W)[:-1].max(axis=1)
    return out


def rolling_min_prev(x, W):
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(x)
    out = np.full(n, np.nan)
    if n <= W:
        return out
    out[W:] = sliding_window_view(x, W)[:-1].min(axis=1)
    return out


def dormancy_signals(high, low, close, W, Dmin):
    """قلهٔ/کفِ تازهٔ W-کندلی پس از خشکسالی ≥ Dmin کندل."""
    n = len(close)
    hmax = rolling_max_prev(high, W)
    lmin = rolling_min_prev(low, W)
    with np.errstate(invalid='ignore'):
        fresh_hi = close > hmax
        fresh_lo = close < lmin
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    last_hi = -10**9
    last_lo = -10**9
    for t in range(n):
        if fresh_hi[t]:
            if t - last_hi >= Dmin:
                long_sig[t] = True
            last_hi = t
        if fresh_lo[t]:
            if t - last_lo >= Dmin:
                short_sig[t] = True
            last_lo = t
    return long_sig, short_sig


def main():
    res = {}
    tf_min = {'M15': 15, 'M30': 30, 'H1': 60, 'H2': 120, 'H4': 240,
              'H8': 480, 'D1': 1440}
    for tf, mins in tf_min.items():
        d = fd.load_fast('XAUUSD', tf)
        assert 'mt5_full' in d['src'], f'E-16: {d["src"]}'
        half = len(d['close']) // 2
        high = np.asarray(d['high'][:half], dtype=np.float64)
        low = np.asarray(d['low'][:half], dtype=np.float64)
        close = np.asarray(d['close'][:half], dtype=np.float64)
        years = half * mins / (365.25 * 24 * 60)
        r = {}
        for W in [55, 89]:
            for Dmin in [34, 89]:
                ls, ss = dormancy_signals(high, low, close, W, Dmin)
                ev = int(ls.sum() + ss.sum())
                r[f'W{W}D{Dmin}'] = {'events': ev, 'per_year': round(ev / years, 1)}
        res[tf] = r
        print(tf, json.dumps(r), flush=True)
    with open(OUT, 'w') as f:
        json.dump(res, f, indent=1)


if __name__ == '__main__':
    main()
