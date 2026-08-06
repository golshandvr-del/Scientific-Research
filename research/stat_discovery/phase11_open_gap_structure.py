#!/usr/bin/env python3
"""
Phase 11: DAILY-OPEN STRUCTURE (discovered by accident: broker has a 00:00-01:00 daily break!)
So 01:00 UTC bar = FIRST bar of the trading day. The "Asia drift" is actually an OPEN drift.
A) confirm break structure; measure the overnight gap (prev day last close -> today first open)
B) gap statistics: does the gap fill? does gap direction predict day?
C) opening-range (first hour) breakout vs fade: does the first hour's range define the day?
D) weekend gap (Fri close -> Mon open) separately
"""
import csv, math
import numpy as np
from datetime import datetime, timezone

rows = []
with open('/home/user/webapp/data/XAUUSD_M15.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        rows.append((int(float(r[0])), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])))

t = np.array([r[0] for r in rows])
o = np.array([r[1] for r in rows]); h = np.array([r[2] for r in rows])
l = np.array([r[3] for r in rows]); c = np.array([r[4] for r in rows])
n = len(c)
dts = [datetime.fromtimestamp(x, tz=timezone.utc) for x in t]

# ---------- A) session structure ----------
gaps_t = np.diff(t)
print("=== A: time-gap structure between consecutive bars ===")
vals, cnts = np.unique(gaps_t, return_counts=True)
for gv, gc in sorted(zip(vals, cnts), key=lambda x: -x[1])[:5]:
    print(f"  dt={gv:6d}s ({gv/3600:.2f}h): {gc} times")

# day boundaries: gap >= 30 min
brk = np.where(gaps_t >= 1800)[0]   # index i: bar i is last of day, i+1 first of next day
print(f"  breaks found: {len(brk)}")

# ---------- B) overnight gap ----------
print("\n=== B: overnight gap (prev close -> next open), intraday-week only ===")
gap_list = []
for i in brk:
    d_prev, d_next = dts[i], dts[i + 1]
    gap_hrs = (t[i + 1] - t[i]) / 3600
    gap = o[i + 1] - c[i]
    is_weekend = d_prev.weekday() == 4 and d_next.weekday() == 0
    # forward from first bar of day: fill = does price return to prev close within the day (96 bars)?
    j0 = i + 1
    j1 = min(j0 + 96, n - 1)
    if gap > 0:
        filled = (l[j0:j1] <= c[i]).any()
    elif gap < 0:
        filled = (h[j0:j1] >= c[i]).any()
    else:
        filled = True
    day_move = c[min(j0 + 47, n - 1)] - o[j0]   # ~12h move
    gap_list.append((gap, filled, day_move, is_weekend, gap_hrs, dts[j0].year))

g = np.array([x[0] for x in gap_list])
filled = np.array([x[1] for x in gap_list])
daymove = np.array([x[2] for x in gap_list])
wknd = np.array([x[3] for x in gap_list])
years = np.array([x[5] for x in gap_list])

for tag, m in [("DAILY break gaps", ~wknd), ("WEEKEND gaps", wknd)]:
    gg, ff, dm = g[m], filled[m], daymove[m]
    print(f"  {tag}: n={m.sum()}  mean gap=${gg.mean():+.3f}  |gap| median=${np.median(np.abs(gg)):.2f}  P(fill within day)={ff.mean():.3f}")
    # split by gap sign & size
    big = np.abs(gg) > np.quantile(np.abs(gg), 0.7)
    for st, sm in [("gap UP big", (gg > 0) & big), ("gap DOWN big", (gg < 0) & big)]:
        if sm.sum() < 30: continue
        dmm = dm[sm]
        se = dmm.std() / math.sqrt(sm.sum())
        print(f"    {st}: n={sm.sum()}  P(fill)={ff[sm].mean():.3f}  E[12h day move]=${dmm.mean():+.3f} t={dmm.mean()/se:+.2f}")

# ---------- C) opening range (first 4 bars = first hour) ----------
print("\n=== C: OPENING RANGE (first hour of day) -> rest of day ===")
or_res = {"break_up": [], "break_dn": [], }
or_year = {"break_up": [], "break_dn": [], }
for i in brk:
    j0 = i + 1
    if j0 + 52 >= n: continue
    or_hi = h[j0:j0 + 4].max(); or_lo = l[j0:j0 + 4].min()
    # first breakout after opening hour, within next 24 bars
    dir_ = 0; ei = None
    for j in range(j0 + 4, j0 + 28):
        if h[j] > or_hi: dir_ = 1; ei = j; break
        if l[j] < or_lo: dir_ = -1; ei = j; break
    if dir_ == 0: continue
    entry = or_hi if dir_ == 1 else or_lo
    fwd = (c[min(ei + 16, n - 1)] - entry) * dir_   # 4h after breakout
    key = "break_up" if dir_ == 1 else "break_dn"
    or_res[key].append(fwd); or_year[key].append(dts[j0].year)
for key in or_res:
    vv = np.array(or_res[key])
    se = vv.std() / math.sqrt(len(vv))
    wr = (vv > 0).mean()
    print(f"  OR {key}: n={len(vv)}  E[4h after break]=${vv.mean():+.3f} t={vv.mean()/se:+.2f}  WR={wr:.3f}  (gross, before spread)")
    # yearly consistency
    yy = np.array(or_year[key])
    ys = " ".join(f"{y}:{vv[yy==y].mean():+.2f}" for y in sorted(set(yy)))
    print(f"     yearly avg: {ys}")

# ---------- D) first-hour drift refined: is it liquidity-refill? ----------
print("\n=== D: first-bar vs rest-of-first-hour decomposition ===")
fb, rest, fh = [], [], []
for i in brk:
    j0 = i + 1
    if j0 + 4 >= n: continue
    fb.append(c[j0] - o[j0])           # first 15m bar
    rest.append(c[j0 + 3] - c[j0])     # next 45m
    fh.append(c[j0 + 3] - o[j0])       # full first hour
for tag, vv in [("first 15m bar", fb), ("next 45m", rest), ("full first hour", fh)]:
    vv = np.array(vv)
    se = vv.std() / math.sqrt(len(vv))
    print(f"  {tag}: n={len(vv)}  E=${vv.mean():+.3f}  t={vv.mean()/se:+.2f}  P(up)={(vv>0).mean():.3f}")
