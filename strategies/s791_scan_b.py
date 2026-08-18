# -*- coding: utf-8 -*-
"""
S791-c — ORB رژیم‌آگاه: شکست فقط هم‌جهت با رانشِ بلندمدت — XAUUSD-M15 (نیمهٔ اول)
================================================================================
⚠️ مسیر C: فقط نیمهٔ اول. ⚠️ بلوکِ شماره: S790–S799.

درسِ S790 (counter_drift): سودِ ضدرژیمی بتاست و می‌میرد. اینجا وارونه‌اش را
می‌سازیم: فقط شکست‌هایی که با علامتِ رانشِ L-روزه هم‌جهت‌اند. فیلترِ
خودتطبیق: در بازارِ خرسی short، در ابرروند long می‌شود — بدون دستکاریِ دستی.

اسکن: L ∈ {34, 89, 144} روز (فیبوناچی) · thrust ∈ {0, 0.236} · هندسه ثابت
(K=5h، SL=TP=2.618·ATR89، تا پایان روز). مقایسه: aligned در برابر counter.
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
tf_min = 15

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
# closeِ پایانِ هر روز (برای رانشِ روزانه)
day_close = np.array([c[day_end[dd] - 1] for dd in range(n_days)])

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

pip = 0.10
K_H = 5
bars_or = int(round(K_H * 60 / tf_min))
K_GEOM = 2.618
MH = int(round((24 - K_H) * 60 / tf_min))

ev = []
for dd in range(1, n_days):
    s0, e0 = day_start[dd], day_end[dd]
    if e0 - s0 < bars_or + 2:
        continue
    orb_hi = np.max(h[s0:s0 + bars_or])
    orb_lo = np.min(l[s0:s0 + bars_or])
    aref = atr[s0 + bars_or]
    if not np.isfinite(aref) or aref <= 0:
        continue
    for j in range(s0 + bars_or, e0 - 1):
        if c[j] > orb_hi:
            ev.append((j, +1, dd, (c[j] - orb_hi) / aref)); break
        if c[j] < orb_lo:
            ev.append((j, -1, dd, (orb_lo - c[j]) / aref)); break

bars = np.array([e[0] for e in ev], int)
dirs = np.array([e[1] for e in ev], int)
edays = np.array([e[2] for e in ev], int)
thr = np.array([e[3] for e in ev], float)
print(f'breakout events: {len(ev)}')

sl_arr = np.where(np.isnan(atr), 0.0, K_GEOM * atr / pip)

def run(mask, label):
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[bars[mask & (dirs > 0)]] = True
    ss[bars[mask & (dirs < 0)]] = True
    tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                             asset='XAUUSD', max_hold=MH, allow_overlap=False)
    if len(tr2) == 0:
        print(f'{label}: n=0'); return
    p = tr2['pnl_pip'].values
    isl = tr2['direction'] == 'long'
    wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else float('nan')
    ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else float('nan')
    print(f'{label}  n={len(tr2):5d}  WR={np.mean(p>0)*100:5.1f}%  '
          f'avg={np.mean(p):+6.2f}p  net={np.sum(p):+9.0f}p  '
          f'L {int(isl.sum())}/{wl*100:.1f}%  S {int((~isl).sum())}/{ws*100:.1f}%', flush=True)

for L in (34, 89, 144):
    # رانش تا *پایانِ روزِ قبل* (بدونِ نگاه به آینده)
    drift = np.zeros(n_days)
    for dd in range(n_days):
        if dd - 1 - L >= 0:
            drift[dd] = day_close[dd - 1] - day_close[dd - 1 - L]
    dsign = np.sign(drift[edays])
    valid = dsign != 0
    for tth in (0.0, 0.236):
        base = valid & (thr >= tth)
        run(base & (dirs == dsign), f'L={L:3d} thr>={tth:5.3f} ALIGNED')
        run(base & (dirs == -dsign), f'L={L:3d} thr>={tth:5.3f} COUNTER')
    print()
