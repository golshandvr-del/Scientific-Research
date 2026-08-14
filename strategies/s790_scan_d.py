# -*- coding: utf-8 -*-
"""
S790-e — راستی‌آزماییِ پایداری روی نیمهٔ اول: سال‌به‌سال + همسایگیِ پارامتر + TFها
================================================================================
⚠️ مسیر C: فقط نیمهٔ اول. پیکربندیِ کاندید:
   depth>=1.0·ATR89, reclaim>=0.236·ATR89, نخستینِ روز، SL=TP=2.618·ATR89, mh=192.
سه پرسش:
  ۱) WR سال‌به‌سال پایدار است یا مالِ یک دوره؟
  ۲) به جابجاییِ جزئیِ پارامتر حساس است؟ (k∈{2.4,2.618,2.9}, depth∈{0.9,1.0,1.1})
  ۳) در TFهای دیگر همین رفتار هست؟ (این را s790_scan_c.py <TF> جدا می‌سنجد)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'M15'
d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
print('src =', d['src'], '| TF =', TF)
n0 = len(df)
df = df.iloc[:n0 // 2].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values; h = df['high'].values
l = df['low'].values; c = df['close'].values
n = len(df)

day = t // 86400
day_id = np.cumsum(np.r_[True, np.diff(day) != 0]) - 1
n_days = day_id[-1] + 1
d_high = np.full(n_days, -np.inf); d_low = np.full(n_days, np.inf)
np.maximum.at(d_high, day_id, h)
np.minimum.at(d_low, day_id, l)
prev_high = np.full(n, np.nan); prev_low = np.full(n, np.nan)
m = day_id >= 1
prev_high[m] = d_high[day_id[m] - 1]
prev_low[m] = d_low[day_id[m] - 1]

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

def build_sigs(dth, rth):
    sw_hi = (h > prev_high) & (c < prev_high) & ((h - prev_high)/atr >= dth) & ((prev_high - c)/atr >= rth)
    sw_lo = (l < prev_low) & (c > prev_low) & ((prev_low - l)/atr >= dth) & ((c - prev_low)/atr >= rth)
    def fpd(sig):
        out = np.zeros(n, dtype=bool)
        seen = np.zeros(n_days, dtype=bool)
        for i in np.where(sig)[0]:
            if not seen[day_id[i]]:
                seen[day_id[i]] = True; out[i] = True
        return out
    return fpd(sw_lo), fpd(sw_hi)

pip = 0.10

def run(dth, rth, K):
    ls, ss = build_sigs(dth, rth)
    sl_arr = np.where(np.isnan(atr), 0.0, K * atr / pip)
    return se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                              asset='XAUUSD', max_hold=192, allow_overlap=False)

# ---- ۱) سال‌به‌سال با پیکربندیِ کاندید ----
tr2 = run(1.0, 0.236, 2.618)
yr = (t[tr2['signal_bar'].values] // 31557600) + 1970   # سالِ تقریبی
print('\n--- سال‌به‌سال (کاندید: d=1.0 r=0.236 k=2.618) ---')
for y in np.unique(yr):
    p = tr2.loc[yr == y, 'pnl_pip'].values
    if len(p) == 0: continue
    print(f'  {y}: n={len(p):3d}  WR={np.mean(p>0)*100:5.1f}%  net={np.sum(p):+7.0f}p')

# ---- ۲) همسایگیِ پارامتر ----
print('\n--- همسایگیِ پارامتر ---')
for dth in (0.9, 1.0, 1.1):
    for K in (2.4, 2.618, 2.9):
        tr3 = run(dth, 0.236, K)
        p = tr3['pnl_pip'].values
        print(f'  d={dth:3.1f} k={K:5.3f}: n={len(p):4d}  WR={np.mean(p>0)*100:5.1f}%  '
              f'avg={np.mean(p):+6.2f}p  net={np.sum(p):+7.0f}p')
