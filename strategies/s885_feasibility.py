#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S885 — امکان‌سنجی «بازآزمایی میانهٔ تکانه» (Impulse Midpoint Retest) — فقط نیمهٔ اول، فقط شمارش.

تکانهٔ صعودی: close[t0] > max(high[t0-W..t0-1]) (قلهٔ تازهٔ W-کندلی).
پای حرکت: از کفِ W کندلِ قبل (leg_lo=min(low[t0-W..t0-1])) تا high[t0].
میانه: mid = (high[t0]+leg_lo)/2.
بازآزمایی long: در اولین کندل t∈(t0, t0+k] که low[t] ≤ mid و close[t] ≥ mid
(نفوذ به میانه + دفاع در بسته). short قرینه. بدون نگاه به جلو؛ هر تکانه حداکثر یک بازآزمایی.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from strategies.s884_feasibility import rolling_max_prev, rolling_min_prev

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_s885_feasibility.json')


def midpoint_retest_signals(high, low, close, W, k):
    """سیگنال long/short بازآزمایی میانهٔ تکانه — بدون نگاه به جلو."""
    n = len(close)
    hmax = rolling_max_prev(high, W)
    lmin = rolling_min_prev(low, W)
    with np.errstate(invalid='ignore'):
        fresh_hi = close > hmax
        fresh_lo = close < lmin
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    # وضعیت انتظار برای بازآزمایی (فقط آخرین تکانهٔ هر سمت فعال است)
    up_mid, up_dead = np.nan, -1     # up_dead = آخرین کندل مجاز
    dn_mid, dn_dead = np.nan, -1
    for t in range(n):
        # ۱) بررسی بازآزماییِ تکانه‌های قبلی (قبل از ثبت تکانهٔ جدید در همین کندل)
        if not np.isnan(up_mid) and t <= up_dead:
            if low[t] <= up_mid and close[t] >= up_mid:
                long_sig[t] = True
                up_mid = np.nan   # هر تکانه فقط یک بازآزمایی
        if not np.isnan(dn_mid) and t <= dn_dead:
            if high[t] >= dn_mid and close[t] <= dn_mid:
                short_sig[t] = True
                dn_mid = np.nan
        # ۲) ثبت تکانهٔ جدید (میانه از اطلاعات تا کندل t، بازآزمایی از t+1)
        if fresh_hi[t]:
            leg_lo = lmin[t]
            up_mid = 0.5 * (high[t] + leg_lo)
            up_dead = t + k
        if fresh_lo[t]:
            leg_hi = hmax[t]
            dn_mid = 0.5 * (low[t] + leg_hi)
            dn_dead = t + k
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
        for W in [34, 55]:
            for k in [21, 34]:
                ls, ss = midpoint_retest_signals(high, low, close, W, k)
                ev = int(ls.sum() + ss.sum())
                r[f'W{W}k{k}'] = {'events': ev, 'long': int(ls.sum()),
                                  'short': int(ss.sum()),
                                  'per_year': round(ev / years, 1)}
        res[tf] = r
        print(tf, json.dumps(r), flush=True)
    with open(OUT, 'w') as f:
        json.dump(res, f, indent=1)


if __name__ == '__main__':
    main()
