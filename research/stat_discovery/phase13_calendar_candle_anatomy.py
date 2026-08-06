#!/usr/bin/env python3
"""
Phase 13: remaining uncovered territory
A) CALENDAR: day-of-month effect, turn-of-month (TOM), month-of-year on daily returns
B) CANDLE ANATOMY: shadow (wick) asymmetry as next-bar predictor
C) INTRADAY U-SHAPE check on RANGE by slot (15-min resolution, not hourly)
D) ROBUSTNESS of phase12's star: gap-down-big open-bar long -- placebo tests
   (shifted entries, random-day placebo, sign test by year-halves)
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

gaps_t = np.diff(t)
brk = np.where(gaps_t >= 1800)[0]
day_first = brk + 1                      # first bar index of each day
day_last = np.append(brk[1:], n - 1)     # last bar of that day (next break)
# build day table
days = []
for k in range(len(day_first)):
    j0, j1 = day_first[k], day_last[k]
    if j1 <= j0: continue
    d = dts[j0]
    days.append((d, o[j0], c[j1], j0, j1))
print(f"trading days: {len(days)}")

dret = np.array([(x[2] - x[1]) for x in days])          # day open->close $ move
dobj = [x[0] for x in days]

# ---------- A) calendar ----------
print("\n=== A1: day-of-month (grouped) day-return ===")
dom = np.array([d.day for d in dobj])
for tag, m in [("1-5", (dom >= 1) & (dom <= 5)), ("6-10", (dom >= 6) & (dom <= 10)),
               ("11-15", (dom >= 11) & (dom <= 15)), ("16-20", (dom >= 16) & (dom <= 20)),
               ("21-25", (dom >= 21) & (dom <= 25)), ("26-31", dom >= 26)]:
    v = dret[m]; se = v.std() / math.sqrt(m.sum())
    print(f"  dom {tag:6s}: n={m.sum():4d} E[day]=${v.mean():+.3f} t={v.mean()/se:+.2f}")

print("\n=== A2: turn-of-month (last 2 + first 3 trading days) ===")
# trading-day index within month
tom = np.zeros(len(dobj), dtype=bool)
by_month = {}
for i, d in enumerate(dobj):
    by_month.setdefault((d.year, d.month), []).append(i)
for key, idxs in by_month.items():
    idxs = sorted(idxs)
    for j in idxs[:3]: tom[j] = True     # first 3
    for j in idxs[-2:]: tom[j] = True    # last 2
for tag, m in [("TOM days", tom), ("non-TOM", ~tom)]:
    v = dret[m]; se = v.std() / math.sqrt(m.sum())
    print(f"  {tag:9s}: n={m.sum():4d} E[day]=${v.mean():+.3f} t={v.mean()/se:+.2f}")

print("\n=== A3: month-of-year ===")
mon = np.array([d.month for d in dobj])
for mm in range(1, 13):
    m = mon == mm
    if m.sum() < 20: continue
    v = dret[m]; se = v.std() / math.sqrt(m.sum())
    star = " *" if abs(v.mean() / se) > 2 else ""
    print(f"  month={mm:2d}: n={m.sum():4d} E[day]=${v.mean():+.3f} t={v.mean()/se:+.2f}{star}")

# ---------- B) candle anatomy: wick asymmetry ----------
print("\n=== B: wick asymmetry -> next bar (all bars) ===")
body = c - o
up_wick = h - np.maximum(c, o)
dn_wick = np.minimum(c, o) - l
rng = h - l
ok = rng > 0
# hammer-like: long lower wick (>60% of range), small body
ham = ok & (dn_wick / np.where(rng == 0, 1, rng) > 0.6)
star = ok & (up_wick / np.where(rng == 0, 1, rng) > 0.6)
ret_next = np.diff(c)
for tag, m in [("HAMMER (lower wick>60%)", ham), ("SHOOTING STAR (upper wick>60%)", star)]:
    idx = np.where(m[:-1])[0]
    v = ret_next[idx]
    se = v.std() / math.sqrt(len(v))
    print(f"  {tag}: n={len(idx)} E[next]=${v.mean():+.4f} t={v.mean()/se:+.2f} P(up)={(v>0).mean():.3f}")
    # conditioned on big range (meaningful wicks)
    big = idx[rng[idx] > np.quantile(rng, 0.8)]
    v2 = ret_next[big]
    if len(v2) > 100:
        se2 = v2.std() / math.sqrt(len(v2))
        print(f"     ... only big-range bars: n={len(big)} E[next]=${v2.mean():+.4f} t={v2.mean()/se2:+.2f} P(up)={(v2>0).mean():.3f}")

# ---------- D) robustness of the star finding ----------
print("\n=== D: ROBUSTNESS of gap-down-big open-bar long ===")
all_gaps = np.array([o[i + 1] - c[i] for i in brk])
thr = np.quantile(np.abs(all_gaps), 0.5)
sel = [i for i in brk if (o[i + 1] - c[i]) < -thr and i + 2 < n]
pnl = np.array([c[i + 1] - o[i + 1] - SPREAD for i in sel])
yrs = np.array([dts[i + 1].year for i in sel])
print(f"  base: n={len(pnl)} avg={pnl.mean():+.3f} t={pnl.mean()/(pnl.std()/math.sqrt(len(pnl))):+.2f}")
# placebo 1: same days, but enter at 2nd bar instead of 1st
p2 = np.array([c[i + 2] - o[i + 2] - SPREAD for i in sel])
print(f"  placebo enter@2nd bar: avg={p2.mean():+.3f} t={p2.mean()/(p2.std()/math.sqrt(len(p2))):+.2f}")
# placebo 2: gap-up-big days same trade
sel_up = [i for i in brk if (o[i + 1] - c[i]) > thr and i + 2 < n]
pu = np.array([c[i + 1] - o[i + 1] - SPREAD for i in sel_up])
print(f"  placebo gap-UP days:   avg={pu.mean():+.3f} t={pu.mean()/(pu.std()/math.sqrt(len(pu))):+.2f}")
# half-by-half consistency
half = len(pnl) // 2
for tag, v in [("first half", pnl[:half]), ("second half", pnl[half:])]:
    se = v.std() / math.sqrt(len(v))
    print(f"  {tag}: n={len(v)} avg={v.mean():+.3f} t={v.mean()/se:+.2f} WR={(v>0).mean():.3f}")
# gap size continuity: deciles of gap-down magnitude
gd = np.array([-(o[i + 1] - c[i]) for i in sel])  # positive magnitude
qs = np.quantile(gd, [0.33, 0.66])
for tag, m in [("small third", gd <= qs[0]), ("mid third", (gd > qs[0]) & (gd <= qs[1])), ("big third", gd > qs[1])]:
    v = pnl[m]; se = v.std() / math.sqrt(m.sum())
    print(f"  gap-magnitude {tag:12s}: n={m.sum()} avg={v.mean():+.3f} t={v.mean()/se:+.2f} WR={(v>0).mean():.3f}")
# how much of the open-bar drift is just gap refill? correlation
print(f"  corr(gap magnitude, open-bar pnl) = {np.corrcoef(gd, pnl)[0,1]:+.3f}")
