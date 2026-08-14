#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S880 — حسابِ امکان‌سنجی («قبل از نوشتنِ یک خط کدِ استراتژی، این حساب را بکن»)

⚠️ فقط روی **نیمهٔ اولِ** داده (Path C) — نیمهٔ دوم دست‌نخورده می‌ماند.

سؤال: رویدادِ «افتِ ناگهانیِ آنتروپی» (گذار نویز→ساختار) چند بار در سال شلیک
می‌کند؟ آیا n برای بهای Path C (lift·√n ≥ 78) کافی است؟

خروجی: نرخِ شلیک به‌ازای هر TF و هر تعریفِ افت — بدونِ هیچ بک‌تستی، بدونِ WR.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import indicator_bank as ib

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s880_feasibility.json')

def entropy_fast(close, p, bins=8):
    """آنتروپیِ شانونِ بازده — بازنویسیِ برداریِ همان الگوریتمِ بانک (bit-identical منطق)."""
    n = len(close)
    ret = np.zeros(n)
    ret[1:] = np.where(close[:-1] != 0, (close[1:] - close[:-1]) / close[:-1], 0.0)
    out = np.full(n, np.nan)
    # sliding window min/max/hist — حلقهٔ پایتونی همان بانک ولی با بافرِ محلی
    for i in range(p, n):
        w = ret[i - p + 1:i + 1]
        mn = w.min(); mx = w.max(); rng = (mx - mn) or 1e-10
        idx = np.minimum(bins - 1, ((w - mn) / rng * bins).astype(int))
        hist = np.bincount(idx, minlength=bins)
        pr = hist[hist > 0] / p
        out[i] = -(pr * np.log2(pr)).sum()
    return out

def main():
    res = {}
    # TFهای نمایندهٔ سه رده — M5 (تند)، M30 (میانه)، H1 (کند). M1 بعداً در اسکن اصلی.
    for tf in ['M5', 'M15', 'M30', 'H1', 'H4']:
        try:
            d = fd.load_fast('XAUUSD', tf)
        except FileNotFoundError:
            # H4 در mt5_full نیست — از H1 resample در اسکنِ اصلی؛ اینجا رد شو
            res[tf] = {'skip': 'no file'}
            continue
        close = np.asarray(d['close'], dtype=float)
        t = np.asarray(d['time'], dtype=np.int64)
        n_all = len(close)
        half = n_all // 2          # مرزِ Path C — فقط نیمهٔ اول
        c1 = close[:half]; t1 = t[:half]
        years1 = (t1[-1] - t1[0]) / (365.25 * 86400)
        tf_res = {'n_half': int(half), 'years_half': round(float(years1), 2),
                  'range': [int(t1[0]), int(t1[-1])], 'events': {}}
        for p in (21, 34, 55):     # دوره‌های فیبوناچی، غیررند (اشتباه #۷)
            e = entropy_fast(c1, p)
            v = e[~np.isnan(e)]
            q30, q70 = np.nanquantile(v, 0.30), np.nanquantile(v, 0.70)
            # رویداد: آنتروپی در k کندلِ اخیر بالای q70 بوده و حالا زیرِ q30 می‌رود
            for k in (8, 13):
                was_hi = np.zeros(half, dtype=bool)
                # rolling max of (e> q70) over past k bars, shifted 1 (بدونِ نگاهِ جلو)
                hi = e > q70
                run = np.zeros(half, dtype=bool)
                for j in range(1, k + 1):
                    run[j:] |= hi[:-j]
                cross_dn = (e < q30) & run
                # فقط لبهٔ ورود (نه هر کندلِ داخلِ ناحیه)
                edge = cross_dn & ~np.concatenate(([False], cross_dn[:-1]))
                n_ev = int(edge.sum())
                tf_res['events'][f'p{p}_k{k}'] = {
                    'n_events_half': n_ev,
                    'per_year': round(n_ev / years1, 1)}
        res[tf] = tf_res
        print(tf, json.dumps(tf_res['events'], ensure_ascii=False))
    with open(OUT, 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('saved ->', OUT)

if __name__ == '__main__':
    main()
