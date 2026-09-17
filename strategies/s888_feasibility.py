#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S888 — امکان‌سنجی «شوک در لبهٔ دامنه» (Range-Edge Shock) — فقط نیمهٔ اول، فقط شمارش.

پایه: شوک بزرگ `high−low ≥ θ×ATR21[t−1]` (علّی) + follow با بدنه (خانوادهٔ زندهٔ S965/S919/S1911).
گیت بیرونی بکر: **جایگاه بستهٔ شوک در دامنهٔ قبلیِ W کندل** (Donchian قبل از کندل شوک، علّی):
    pos = (close[t] − min(low[t−W..t−1])) / (max(high[t−W..t−1]) − min(low[t−W..t−1]))
EDGE: شوک صعودی با pos ≥ 1 − ε (نزدیک/بالای سقف دامنه) ، شوک نزولی با pos ≤ ε.
MID:  شوک با ε < pos < 1−ε  (کنترل P1 — خارج از انتخاب).
فرضیه: شوکِ لبه‌ای = «اطلاعات + شکستِ ساختار» (S802/S1520 هر دو ACCEPT، ترکیب شوک×مکان) ؛
شوکِ میان‌دامنه = بازتوزیع درون رنج (S653/S986 سبک) و بی‌ادامه.
هیچ شبیه‌سازی معامله‌ای در این فایل نیست.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from strategies.s884_feasibility import rolling_max_prev, rolling_min_prev
from strategies.s887_feasibility import atr_prev

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W_RANGE = 55


def build_s888(high, low, close, open_, W=W_RANGE):
    atr = atr_prev(high, low, close, 21)
    hi = rolling_max_prev(high, W); lo = rolling_min_prev(low, W)
    span = hi - lo
    with np.errstate(divide='ignore', invalid='ignore'):
        pos = np.where(span > 0, (close - lo) / span, np.nan)
    return dict(atr=atr, rng=high - low, pos=pos, up=close > open_, dn=close < open_)


def s888_signals(pre, theta, eps, zone='edge'):
    """zone='edge' ⇒ گیت لبه؛ zone='mid' ⇒ کنترل؛ zone='all' ⇒ شوک بی‌گیت."""
    shock = (pre['rng'] >= theta * pre['atr']) & np.isfinite(pre['pos'])
    if zone == 'edge':
        ls = shock & pre['up'] & (pre['pos'] >= 1.0 - eps)
        ss = shock & pre['dn'] & (pre['pos'] <= eps)
    elif zone == 'mid':
        mid = (pre['pos'] > eps) & (pre['pos'] < 1.0 - eps)
        ls = shock & pre['up'] & mid; ss = shock & pre['dn'] & mid
    else:
        ls = shock & pre['up']; ss = shock & pre['dn']
    return ls, ss


def main():
    out = {}
    for tf in ['H1', 'H2', 'H4', 'H6', 'H8', 'H12', 'D1']:
        d = fd.load_fast('XAUUSD', tf)
        assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
        n = len(d['close']); half = n // 2
        h, l, c, o, t = (np.asarray(d[k][:half], dtype=np.float64) for k in ('high', 'low', 'close', 'open', 'time'))
        yrs = (t[-1] - t[0]) / (365.25 * 86400)
        pre = build_s888(h, l, c, o)
        res = {}
        for th in [1.618, 2.618]:
            la, sa = s888_signals(pre, th, 0, 'all')
            res[f'th{th}_all'] = int(la.sum() + sa.sum())
            for eps in [0.0, 0.1, 0.236]:
                ls, ss = s888_signals(pre, th, eps, 'edge')
                res[f'th{th}_edge_eps{eps}'] = {'events': int(ls.sum() + ss.sum()), 'long': int(ls.sum()),
                                                'short': int(ss.sum()), 'per_year': round((ls.sum() + ss.sum()) / yrs, 1)}
        out[tf] = res
        print(tf, json.dumps(res), flush=True)
    with open(os.path.join(ROOT, 'results', '_s888_feasibility.json'), 'w') as f:
        json.dump(out, f, indent=1)


if __name__ == '__main__':
    main()
