# -*- coding: utf-8 -*-
"""
S790 — رصدِ اکتشافیِ شکافِ بازگشاییِ هفته (Weekend Gap) روی XAUUSD
================================================================================
⚠️ قیدِ مسیرِ C (پیش‌ثبت): این اسکریپت **فقط نیمهٔ اولِ** داده را می‌بیند.
نیمهٔ دوم تا آزمونِ نهایی دست‌نخورده می‌ماند.

پرسش‌های رصد:
  ۱) شکافِ بازگشاییِ هفته (openِ اولین کندلِ هفته − closeِ آخرین کندلِ هفتهٔ قبل)
     چه توزیعی دارد؟ (اندازه بر حسبِ pip = 0.1$)
  ۲) چند درصدِ شکاف‌ها در همان روزِ دوشنبه/همان هفته «پُر» می‌شوند؟
     (پر شدن = قیمت به closeِ جمعهٔ قبل برگردد)
  ۳) آیا fade کردنِ شکاف (معامله در جهتِ پُر شدن) پس از هزینهٔ کامل لبه دارد؟
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd

d = fd.load_fast('XAUUSD', 'M1')
print('src =', d['src'])
t = d['time']; o = d['open']; h = d['high']; l = d['low']; c = d['close']
n = len(t)
print('bars:', n, 'range:', np.datetime64(int(t[0]), 's'), '→', np.datetime64(int(t[-1]), 's'))

# ---- فقط نیمهٔ اول (مسیر C) ----
half = n // 2
t, o, h, l, c = t[:half], o[:half], h[:half], l[:half], c[:half]
print('EXPLORATION HALF ONLY:', np.datetime64(int(t[0]), 's'), '→', np.datetime64(int(t[-1]), 's'), f'({half} bars)')

# شکافِ هفته: جایی که فاصلهٔ زمانی دو کندلِ متوالی > 24 ساعت (تعطیلی آخر هفته)
dt = np.diff(t)
gap_idx = np.where(dt > 24 * 3600)[0]   # اندیسِ کندلِ قبل از شکاف
print('weekend gaps found:', len(gap_idx))

pip = 0.10
gaps = []
for gi in gap_idx:
    fri_close = c[gi]
    mon_open = o[gi + 1]
    gap_pip = (mon_open - fri_close) / pip
    gaps.append((gi, gap_pip))

g = np.array([x[1] for x in gaps])
print('\n--- توزیعِ شکاف (pip؛ 10pip = 1$) ---')
for q in (5, 25, 50, 75, 95):
    print(f'  q{q}: {np.percentile(g, q):+.1f}')
print(f'  |gap| median: {np.median(np.abs(g)):.1f}   mean: {np.mean(np.abs(g)):.1f}')
for th in (10, 20, 30, 50, 80):
    print(f'  |gap| >= {th} pip: {int(np.sum(np.abs(g) >= th))} ({np.mean(np.abs(g) >= th)*100:.1f}%)')

# ---- نرخِ پُر شدن در پنجره‌های زمانی مختلف ----
print('\n--- نرخِ پُرشدن (بازگشت قیمت به closeِ جمعه) ---')
for th in (10, 20, 30, 50):
    for win_h in (4, 12, 24, 120):   # ساعت پس از بازگشایی
        filled = 0; total = 0
        for gi, gp in gaps:
            if abs(gp) < th:
                continue
            total += 1
            fri_close = c[gi]
            t0 = t[gi + 1]
            # پنجرهٔ بررسی
            j_end = np.searchsorted(t, t0 + win_h * 3600)
            hi = h[gi + 1:j_end]; lo = l[gi + 1:j_end]
            if len(hi) == 0:
                continue
            if gp > 0:       # شکاف بالا ⇒ پُرشدن یعنی low <= fri_close
                if np.min(lo) <= fri_close:
                    filled += 1
            else:            # شکاف پایین ⇒ پُرشدن یعنی high >= fri_close
                if np.max(hi) >= fri_close:
                    filled += 1
        if total:
            print(f'  |gap|>={th:3d}pip  window={win_h:4d}h  fill={filled}/{total} = {filled/total*100:.1f}%')
