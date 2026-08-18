# -*- coding: utf-8 -*-
"""
S791-d — هندسهٔ ORB رژیم‌آگاه: RR≥1 و مقیاسِ SL — XAUUSD-M15 (نیمهٔ اول)
================================================================================
⚠️ مسیر C: فقط نیمهٔ اول. ⚠️ بلوکِ شماره: S790–S799.
رخداد قفل شد (از s791_scan_b): K=5h، شکستِ close، thrust>=0.236،
هم‌جهت با رانشِ L=144 روزه. آزاد: k_sl ∈ {1.618, 2.618} × rr ∈ {1.0, 1.618, 2.618}
(TP = rr·SL — همیشه TP>=SL). max_hold تا پایان روز و نسخهٔ ۲ روزه برای rr بزرگ.
+ پایداری: سال‌به‌سال برای بهترین.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

d = fd.load_fast('XAUUSD', 'M15')
df = fd.as_dataframe(d)
print('src =', d['src'])
n0 = len(df)
df = df.iloc[:n0 // 2].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values; h = df['high'].values
l = df['low'].values; c = df['close'].values
n = len(df)

day = t // 86400
day_id = np.cumsum(np.r_[True, np.diff(day) != 0]) - 1
n_days = day_id[-1] + 1
day_start = np.zeros(n_days, dtype=np.int64)
seen = np.zeros(n_days, dtype=bool)
for i in range(n):
    dd = day_id[i]
    if not seen[dd]:
        seen[dd] = True; day_start[dd] = i
day_end = np.r_[day_start[1:], n]
day_close = np.array([c[day_end[dd] - 1] for dd in range(n_days)])

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

pip = 0.10
bars_or = 20            # 5h در M15
L = 144
THR = 0.236

drift = np.zeros(n_days)
for dd in range(n_days):
    if dd - 1 - L >= 0:
        drift[dd] = day_close[dd - 1] - day_close[dd - 1 - L]

ls = np.zeros(n, bool); ss = np.zeros(n, bool)
for dd in range(1, n_days):
    s0, e0 = day_start[dd], day_end[dd]
    if e0 - s0 < bars_or + 2:
        continue
    ds = np.sign(drift[dd])
    if ds == 0:
        continue
    orb_hi = np.max(h[s0:s0 + bars_or])
    orb_lo = np.min(l[s0:s0 + bars_or])
    aref = atr[s0 + bars_or]
    if not np.isfinite(aref) or aref <= 0:
        continue
    for j in range(s0 + bars_or, e0 - 1):
        if c[j] > orb_hi:
            if ds > 0 and (c[j] - orb_hi) / aref >= THR:
                ls[j] = True
            break
        if c[j] < orb_lo:
            if ds < 0 and (orb_lo - c[j]) / aref >= THR:
                ss[j] = True
            break
print(f'signals: long={ls.sum()} short={ss.sum()}')

for ksl in (1.618, 2.618):
    sl_arr = np.where(np.isnan(atr), 0.0, ksl * atr / pip)
    for rr in (1.0, 1.618, 2.618):
        tp_arr = sl_arr * rr
        for mh in (76, 192):     # تا پایان روز / ~۲ روز
            tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                                     asset='XAUUSD', max_hold=mh, allow_overlap=False)
            if len(tr2) == 0:
                continue
            p = tr2['pnl_pip'].values
            print(f'ksl={ksl:5.3f} rr={rr:5.3f} mh={mh:3d}  n={len(tr2):4d}  '
                  f'WR={np.mean(p>0)*100:5.1f}%  avg={np.mean(p):+6.2f}p  '
                  f'net={np.sum(p):+8.0f}p', flush=True)

# سال‌به‌سال برای منتخبِ احتمالی (ksl=2.618, rr=1.618, mh=192)
sl_arr = np.where(np.isnan(atr), 0.0, 2.618 * atr / pip)
tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr * 1.618,
                         asset='XAUUSD', max_hold=192, allow_overlap=False)
yr = (t[tr2['signal_bar'].values] // 31557600) + 1970
print('\n--- سال‌به‌سال (ksl=2.618 rr=1.618 mh=192) ---')
for y in np.unique(yr):
    p = tr2.loc[yr == y, 'pnl_pip'].values
    print(f'  {y}: n={len(p):3d}  WR={np.mean(p>0)*100:5.1f}%  net={np.sum(p):+7.0f}p')
