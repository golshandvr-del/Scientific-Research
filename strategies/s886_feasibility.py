#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S886 — امکان‌سنجی «شکاف فرار» (Runaway Overlap Gap) — فقط نیمهٔ اول، فقط شمارش.

رویداد: هم‌پوشانیِ دامنهٔ کندل t با دامنهٔ کندل t−1 ≤ θ (θ=0 یعنی شکاف واقعی:
low[t] > high[t−1] یا high[t] < low[t−1]). شکاف‌های آخر هفته/تعطیلات حذف می‌شوند
(فاصلهٔ زمانی > 1.5×TF) — چون S810/S405 آن خانواده را رد کرده‌اند.
جهت: follow — کندل بالاتر → long، پایین‌تر → short.
لنگر بیرونی: دامنهٔ کندل قبلی (نه چندک توزیعی). هیچ شبیه‌سازی معامله‌ای در این فایل نیست.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def overlap_ratio(high, low):
    """نسبت هم‌پوشانی دامنهٔ کندل t با کندل t−1، نسبت به دامنهٔ کندل t−1. NaN برای t=0."""
    n = len(high)
    r = np.full(n, np.nan)
    ph, pl = high[:-1], low[:-1]
    ch, cl = high[1:], low[1:]
    ov = np.minimum(ph, ch) - np.maximum(pl, cl)      # می‌تواند منفی باشد = شکاف
    prng = ph - pl
    with np.errstate(divide='ignore', invalid='ignore'):
        r[1:] = np.where(prng > 0, ov / prng, np.nan)
    return r


def runaway_signals(time_s, high, low, close, theta, tf_minutes):
    """long اگر هم‌پوشانی ≤ θ و کندل t بالاتر از t−1 (low[t] > low[t−1] و close[t] > high[t−1])؛
    short آینه‌ای. شکاف‌های زمانی (> 1.5×TF) حذف."""
    n = len(high)
    r = overlap_ratio(high, low)
    dt = np.empty(n); dt[0] = np.inf; dt[1:] = np.diff(time_s) / 60.0
    ok = (r <= theta) & (dt <= 1.5 * tf_minutes)
    ok[0] = False
    ph = np.empty(n); ph[0] = np.nan; ph[1:] = high[:-1]
    pl = np.empty(n); pl[0] = np.nan; pl[1:] = low[:-1]
    ls = ok & (low > pl) & (close > ph)
    ss = ok & (high < ph) & (close < pl)
    return ls, ss


def main():
    out = {}
    for tf in ['M15', 'M30', 'H1', 'H2', 'H4', 'H8', 'D1']:
        d = fd.load_fast('XAUUSD', tf)
        assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
        n = len(d['close']); half = n // 2
        t = d['time'][:half]; h = d['high'][:half]; l = d['low'][:half]; c = d['close'][:half]
        yrs = (t[-1] - t[0]) / (365.25 * 86400)
        res = {}
        for th in [0.0, 0.236, 0.382]:
            ls, ss = runaway_signals(t, h, l, c, th, fd.TF_MINUTES[tf])
            res[f'th{th}'] = {'events': int(ls.sum() + ss.sum()), 'long': int(ls.sum()),
                              'short': int(ss.sum()), 'per_year': round((ls.sum() + ss.sum()) / yrs, 1)}
        out[tf] = res
        print(tf, json.dumps(res), flush=True)
    with open(os.path.join(ROOT, 'results', '_s886_feasibility.json'), 'w') as f:
        json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
