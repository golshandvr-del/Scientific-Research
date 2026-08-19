# -*- coding: utf-8 -*-
"""
S832 — کاوشِ ۱: سرشماری ساعتی فعالیت — XAUUSD-H1 (فقط ۶۰٪ اکتشاف)
====================================================================
پیش‌نیاز فرضیه‌ی «شکست رنج سشن آرام»: باید بدانیم ساعت‌های آرام/پرتحرک
در منطقه‌ی زمانی بروکر (MT5) کدام‌اند — حدس نمی‌زنیم، اندازه می‌گیریم.
خروجی: میانگین TR نرمال‌شده و |r| به تفکیک ساعت + سهم حجم حرکت.
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd

SPLIT_IDX = 54798
d = fd.load_fast('XAUUSD', 'H1')
t = d['time'][:SPLIT_IDX].astype(np.int64)
c = d['close'][:SPLIT_IDX].astype(np.float64)
h = d['high'][:SPLIT_IDX].astype(np.float64)
l = d['low'][:SPLIT_IDX].astype(np.float64)
hour = (t // 3600) % 24
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
# نرمال‌سازی با میانگین متحرک بلند تا رژیم‌ها قاطی نشوند
atr_slow = np.convolve(tr, np.ones(500)/500, mode='same')
ntr = tr / np.maximum(atr_slow, 1e-9)

print(f'explore bars={SPLIT_IDX:,}  src={d["src"]}', flush=True)
print('hour |  mean nTR | share_of_day_range', flush=True)
tot = []
for hh in range(24):
    m = hour == hh
    tot.append(float(ntr[m].mean()))
s = sum(tot)
for hh in range(24):
    bar = '#' * int(round(tot[hh] / max(tot) * 40))
    print(f'{hh:4d} | {tot[hh]:9.3f} | {tot[hh]/s*100:5.2f}%  {bar}', flush=True)
q = sorted(range(24), key=lambda x: tot[x])
print('\nآرام‌ترین ۷ ساعت:', q[:7], flush=True)
print('پرتحرک‌ترین ۵ ساعت:', q[-5:], flush=True)
