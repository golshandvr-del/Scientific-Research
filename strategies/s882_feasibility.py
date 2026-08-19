#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S882 — امکان‌سنجی «برآمدگی بازگشتی Mass Index» — فقط نیمهٔ اول.

Mass Index (Dorsey): mass = rolling_sum(EMA(range,e)/EMA(EMA(range,e),e), s)
رویداد bulge: mass از بالای چندکِ بالایی qU عبور کرده و سپس به زیر qL برگردد.
جهت: معکوسِ driftِ k کندلِ اخیر (بازگشتی).
فقط شمارش نرخ رویداد — هیچ شبیه‌سازی معامله‌ای.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_s882_feasibility.json')

# چندک‌های فیبوناچی‌گون (سطوح 0.886 و 0.764 فیبوناچی) — خطای ۷ رعایت شد
QU, QL = 88.6, 76.4


def mass_vec(high, low, ema=8, summ=21):
    """Mass Index — pandas ewm (سرعت C، حافظهٔ خطی)."""
    rng = pd.Series(high - low)
    e1 = rng.ewm(span=ema, adjust=False).mean()
    e2 = e1.ewm(span=ema, adjust=False).mean()
    ratio = e1 / e2.replace(0, np.nan)
    return ratio.rolling(summ).sum().values


def bulge_events(M, qU_val, qL_val, k, close):
    """bulge: عبورِ M به زیر qL درحالی‌که در k کندل اخیر بالای qU بوده.
    جهت = معکوسِ drift همان k کندل. بدون نگاه به جلو."""
    n = len(M)
    above = M > qU_val
    was_above = np.zeros(n, dtype=bool)
    for j in range(1, k + 1):
        was_above[j:] |= above[:-j]
    prev = np.concatenate(([np.nan], M[:-1]))
    with np.errstate(invalid='ignore'):
        cross_dn = (M < qL_val) & (prev >= qL_val) & was_above
    drift = np.zeros(n)
    drift[k:] = close[k:] - close[:-k]
    long_sig = cross_dn & (drift < 0)   # بازگشت از نزول → long
    short_sig = cross_dn & (drift > 0)  # بازگشت از صعود → short
    return long_sig, short_sig


def main():
    res = {}
    for tf in ['M5', 'M15', 'M30', 'H1', 'H2', 'H4', 'H8', 'D1']:
        d = fd.load_fast('XAUUSD', tf)
        assert 'mt5_full' in d['src'], f'E-16: {d["src"]}'
        n_all = len(d['close'])
        half = n_all // 2
        high = np.asarray(d['high'][:half], dtype=np.float64)
        low = np.asarray(d['low'][:half], dtype=np.float64)
        close = np.asarray(d['close'][:half], dtype=np.float64)
        years = half * {'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H2': 120,
                        'H4': 240, 'H8': 480, 'D1': 1440}[tf] / (365.25 * 24 * 60)
        r = {}
        for ema, summ in [(8, 21), (13, 34)]:
            M = mass_vec(high, low, ema, summ)
            v = M[~np.isnan(M)]
            qU_val, qL_val = np.percentile(v, QU), np.percentile(v, QL)
            for k in [13, 21, 34]:
                ls, ss = bulge_events(M, qU_val, qL_val, k, close)
                ev = int(ls.sum() + ss.sum())
                r[f'e{ema}s{summ}k{k}'] = {'events': ev,
                                           'per_year': round(ev / years, 1)}
        res[tf] = r
        print(tf, json.dumps(r), flush=True)
    with open(OUT, 'w') as f:
        json.dump(res, f, indent=1)


if __name__ == '__main__':
    main()
