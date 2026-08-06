#!/usr/bin/env python3
"""
Phase 12: ECONOMIC validation (spread=$0.33) of the two Phase-11 discoveries
A) OPEN-BAR LONG: buy at open of first bar of trading day, exit close of bar k
   - yearly breakdown, IS/OOS, by weekday
B) GAP-FADE: big gap-down at daily open -> long toward prev close (TP=prev close)
C) Combining: does gap direction/size modulate the open-bar edge?
"""
import csv, math
import numpy as np
from datetime import datetime, timezone

SPREAD = 0.33
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
years = np.array([d.year for d in dts])
wd = np.array([d.weekday() for d in dts])

gaps_t = np.diff(t)
brk = np.where(gaps_t >= 1800)[0]  # bar i last of day; i+1 first of new day

def report(tag, pnl, yr):
    pnl = np.array(pnl); yr = np.array(yr)
    if len(pnl) < 30:
        print(f"  {tag}: n={len(pnl)} too few"); return
    se = pnl.std() / math.sqrt(len(pnl))
    wr = (pnl > 0).mean()
    cut = int(len(pnl) * 0.7)
    is_, oos = pnl[:cut], pnl[cut:]
    ys = " ".join(f"{y}:{pnl[yr==y].sum():+.0f}" for y in sorted(set(yr)))
    pos_years = sum(1 for y in set(yr) if pnl[yr == y].sum() > 0)
    print(f"  {tag}: n={len(pnl)} NET=${pnl.sum():+.0f} avg=${pnl.mean():+.3f} WR={wr:.3f} t={pnl.mean()/se:+.2f} | IS avg={is_.mean():+.3f} OOS avg={oos.mean():+.3f} | +yrs={pos_years}/{len(set(yr))}")
    print(f"      yearly: {ys}")

# ---------- A) open-bar long, various holds ----------
print("=== A: LONG at first-bar open of trading day (NET of $0.33 spread) ===")
for hold in [1, 2, 4, 8]:
    pnl, yr = [], []
    for i in brk:
        j0 = i + 1
        if j0 + hold >= n: continue
        pnl.append(c[j0 + hold - 1] - o[j0] - SPREAD)
        yr.append(years[j0])
    report(f"hold={hold} bars ({hold*15}min)", pnl, yr)

print("\n--- A2: hold=1 by weekday of the NEW day ---")
for w in range(5):
    pnl, yr = [], []
    for i in brk:
        j0 = i + 1
        if j0 + 1 >= n or wd[j0] != w: continue
        pnl.append(c[j0] - o[j0] - SPREAD)
        yr.append(years[j0])
    report(f"weekday={w} (0=Mon)", pnl, yr)

print("\n--- A3: hold=1, split weekend-open vs daily-break-open ---")
for tag, cond in [("after WEEKEND", lambda i: gaps_t[i] > 100000),
                  ("after DAILY break", lambda i: gaps_t[i] <= 100000)]:
    pnl, yr = [], []
    for i in brk:
        j0 = i + 1
        if j0 + 1 >= n or not cond(i): continue
        pnl.append(c[j0] - o[j0] - SPREAD)
        yr.append(years[j0])
    report(tag, pnl, yr)

# ---------- B) gap-fade ----------
print("\n=== B: GAP-FADE LONG on big gap-down (TP=prev close, SL=2x gap, max 96 bars) NET ===")
for thresh_q in [0.6, 0.7, 0.8]:
    # compute gap threshold from daily-break gaps only
    all_gaps = np.array([o[i + 1] - c[i] for i in brk])
    thr = np.quantile(np.abs(all_gaps), thresh_q)
    pnl, yr = [], []
    for i in brk:
        j0 = i + 1
        gap = o[j0] - c[i]
        if gap >= -thr: continue  # only big gap-down
        entry = o[j0] + SPREAD
        tp = c[i]                      # prev close
        sl = o[j0] + 2 * gap           # symmetric-ish stop below
        res = None
        for j in range(j0, min(j0 + 96, n)):
            if l[j] <= sl: res = sl - entry; break
            if h[j] >= tp: res = tp - entry; break
        if res is None: res = c[min(j0 + 95, n - 1)] - entry
        pnl.append(res); yr.append(years[j0])
    report(f"|gap|>q{int(thresh_q*100)} (${thr:.2f})", pnl, yr)

# ---------- C) open-bar edge conditioned on gap ----------
print("\n=== C: open-bar long (hold=1) conditioned on overnight gap sign/size ===")
all_gaps = np.array([o[i + 1] - c[i] for i in brk])
thr = np.quantile(np.abs(all_gaps), 0.5)
conds = [("gap DOWN big", lambda g: g < -thr), ("gap DOWN small", lambda g: -thr <= g < 0),
         ("gap UP small", lambda g: 0 <= g < thr), ("gap UP big", lambda g: g >= thr)]
for tag, cf in conds:
    pnl, yr = [], []
    for i in brk:
        j0 = i + 1
        if j0 + 1 >= n: continue
        gap = o[j0] - c[i]
        if not cf(gap): continue
        pnl.append(c[j0] - o[j0] - SPREAD)
        yr.append(years[j0])
    report(tag, pnl, yr)
