#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S883 — امکان‌سنجی «شکست فشردگی NR» — فقط نیمهٔ اول، فقط شمارش رویداد.

رویداد: کندل i دامنهٔ (high−low) اکیداً کوچک‌تر از هر یک از m−1 کندل قبلی دارد
(NR-m آناتومیک، بدون چندک منجمد). سپس در kc کندل بعدی، اولین کندلی که
بالای high[i] ببندد → long؛ زیر low[i] ببندد → short. بدون نگاه به جلو:
سیگنال روی کندل تأیید j ثبت می‌شود، ورود open کندل j+1 (موتور).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_s883_feasibility.json')


def nr_flags(high, low, m):
    """کندل i دامنهٔ اکیداً کوچک‌تر از هر m−1 کندل قبلی — برداری."""
    rng = high - low
    n = len(rng)
    ok = np.ones(n, dtype=bool)
    ok[:m - 1] = False
    for j in range(1, m):
        ok[j:] &= rng[j:] < rng[:-j]
    ok[:j] = False
    return ok


def breakout_signals(high, low, close, m, kc):
    """سیگنال شکست: اولین close خارج از دامنهٔ NR در kc کندل بعد."""
    n = len(close)
    nr = nr_flags(high, low, m)
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    idx = np.where(nr)[0]
    for i in idx:
        hi, lo = high[i], low[i]
        for j in range(i + 1, min(i + 1 + kc, n)):
            if close[j] > hi:
                long_sig[j] = True
                break
            if close[j] < lo:
                short_sig[j] = True
                break
    return long_sig, short_sig


def main():
    res = {}
    tf_min = {'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60, 'H2': 120,
              'H4': 240, 'H8': 480, 'D1': 1440}
    for tf, mins in tf_min.items():
        d = fd.load_fast('XAUUSD', tf)
        assert 'mt5_full' in d['src'], f'E-16: {d["src"]}'
        half = len(d['close']) // 2
        high = np.asarray(d['high'][:half], dtype=np.float64)
        low = np.asarray(d['low'][:half], dtype=np.float64)
        close = np.asarray(d['close'][:half], dtype=np.float64)
        years = half * mins / (365.25 * 24 * 60)
        r = {}
        for m in [5, 8, 13]:
            for kc in [2, 3]:
                ls, ss = breakout_signals(high, low, close, m, kc)
                ev = int(ls.sum() + ss.sum())
                r[f'm{m}kc{kc}'] = {'events': ev, 'per_year': round(ev / years, 1)}
        res[tf] = r
        print(tf, json.dumps(r), flush=True)
    with open(OUT, 'w') as f:
        json.dump(res, f, indent=1)


if __name__ == '__main__':
    main()
