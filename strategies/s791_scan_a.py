# -*- coding: utf-8 -*-
"""
S791-b — اسکنِ شرطیِ ORB: فشردگیِ دامنه × قاطعیتِ شکست — XAUUSD-M15 (نیمهٔ اول)
================================================================================
⚠️ مسیر C: فقط نیمهٔ اول. ⚠️ بلوکِ شماره: S790–S799.

فرضیهٔ فیزیکی: انرژیِ انباشته در دامنهٔ *فشرده* (نسبت به نوسانِ معمول) با
شکست آزاد می‌شود — squeeze ⇒ release. دامنهٔ گشاد شکستِ بی‌معنا می‌دهد.

شرط‌ها روی پایهٔ K=5h، k_geom=2.618 (بهترین‌های رصدِ خام، ثابت):
  compression = OR_width / (ATR89 · bars_or)  — بی‌بعد
    آستانه: comp ≤ q25/q40/q60 توزیعِ خودش (صدک‌های درون‌نمونه‌ای، غیرگِرد)
  breakout thrust = (close − orb_hi)/ATR ≥ {0, 0.236}  (یا آینه برای short)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = 'M15'
d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
print('src =', d['src'])
n0 = len(df)
df = df.iloc[:n0 // 2].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values; h = df['high'].values
l = df['low'].values; c = df['close'].values
n = len(df)
tf_min = fd.TF_MINUTES[TF]

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

# پیش‌محاسبهٔ رخدادهای شکست + سنجه‌های شرطی
ev = []   # (bar, dir(+1/-1), comp, thrust)
for dd in range(1, n_days):
    s0, e0 = day_start[dd], day_end[dd]
    if e0 - s0 < bars_or + 2:
        continue
    orb_hi = np.max(h[s0:s0 + bars_or])
    orb_lo = np.min(l[s0:s0 + bars_or])
    aref = atr[s0 + bars_or]
    if not np.isfinite(aref) or aref <= 0:
        continue
    comp = (orb_hi - orb_lo) / (aref * bars_or)
    for j in range(s0 + bars_or, e0 - 1):
        if c[j] > orb_hi:
            ev.append((j, +1, comp, (c[j] - orb_hi) / aref)); break
        if c[j] < orb_lo:
            ev.append((j, -1, comp, (orb_lo - c[j]) / aref)); break

ev = np.array(ev, dtype=object)
bars = np.array([e[0] for e in ev], int)
dirs = np.array([e[1] for e in ev], int)
comps = np.array([e[2] for e in ev], float)
thr = np.array([e[3] for e in ev], float)
print(f'breakout events: {len(ev)}  comp quartiles: '
      f'q25={np.percentile(comps,25):.4f} q40={np.percentile(comps,40):.4f} '
      f'q60={np.percentile(comps,60):.4f}')

sl_arr = np.where(np.isnan(atr), 0.0, K_GEOM * atr / pip)
for cq in (25, 40, 60, 100):
    cth = np.percentile(comps, cq)
    for tth in (0.0, 0.236):
        m = (comps <= cth) & (thr >= tth)
        ls = np.zeros(n, bool); ss = np.zeros(n, bool)
        ls[bars[m & (dirs > 0) if False else (m) & (dirs > 0)]] = True
        ss[bars[m & (dirs < 0)]] = True
        tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                                 asset='XAUUSD', max_hold=MH, allow_overlap=False)
        if len(tr2) == 0:
            continue
        p = tr2['pnl_pip'].values
        isl = tr2['direction'] == 'long'
        wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else float('nan')
        ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else float('nan')
        print(f'comp<=q{cq:3d} thrust>={tth:5.3f}  n={len(tr2):5d}  '
              f'WR={np.mean(p>0)*100:5.1f}%  avg={np.mean(p):+6.2f}p  net={np.sum(p):+9.0f}p  '
              f'L {int(isl.sum())}/{wl*100:.1f}%  S {int((~isl).sum())}/{ws*100:.1f}%', flush=True)
