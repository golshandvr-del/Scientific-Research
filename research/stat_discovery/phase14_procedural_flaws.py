#!/usr/bin/env python3
"""
Phase 14: PROCEDURAL FLAWS (Rejewski-style) on XAUUSD M15
Rejewski broke Enigma by exploiting *operating procedures*, not the machine itself.
Our "operator" is the broker. Questions:
  A) Does the daily break (00:00->01:00) shift with DST? Is the "01:00 edge"
     anchored to the BROKER CLOCK (first bar of day) or to a wall-clock hour?
  B) Weekend structure: Friday-close -> Monday-first-bar gap; Monday open drift.
  C) Does EURUSD share the same break structure (same procedural flaw)?
"""
import csv, math
from datetime import datetime, timezone
import numpy as np

def load(path):
    t, o, h, l, c, v = [], [], [], [], [], []
    with open(path) as f:
        rd = csv.reader(f); next(rd)
        for r in rd:
            t.append(int(float(r[0]))); o.append(float(r[1])); h.append(float(r[2]))
            l.append(float(r[3])); c.append(float(r[4])); v.append(float(r[5]))
    return (np.array(t), np.array(o), np.array(h), np.array(l), np.array(c), np.array(v))

t, o, h, l, c, v = load('data/XAUUSD_M15.csv')
dts = [datetime.fromtimestamp(x, tz=timezone.utc) for x in t]
dates = np.array([d.date() for d in dts])
hours = np.array([d.hour for d in dts])
mins  = np.array([d.minute for d in dts])

# group bars by calendar day
day_first = {}   # date -> index of first bar
day_last  = {}
for i, d in enumerate(dates):
    if d not in day_first: day_first[d] = i
    day_last[d] = i
days = sorted(day_first)

print("=== A: first-bar-of-day time, by year-month (DST detector) ===")
from collections import Counter, defaultdict
bym = defaultdict(Counter)
for d in days:
    i = day_first[d]
    bym[(d.year, d.month)][f"{hours[i]:02d}:{mins[i]:02d}"] += 1
for ym in sorted(bym):
    top = bym[ym].most_common(3)
    print(f"  {ym[0]}-{ym[1]:02d}: {dict(top)}")

print("\n=== A2: edge anchored to clock or to first bar? ===")
# compare first-bar drift when day starts at 01:00 vs other times
grp = defaultdict(list)
for d in days:
    i = day_first[d]
    grp[f"{hours[i]:02d}:{mins[i]:02d}"].append(c[i] - o[i])
for k in sorted(grp):
    vv = np.array(grp[k])
    if len(vv) < 30: continue
    se = vv.std()/math.sqrt(len(vv))
    print(f"  day starts {k}: n={len(vv):4d} E[first bar]=${vv.mean():+.3f} t={vv.mean()/se:+.2f} P(up)={(vv>0).mean():.3f}")

print("\n=== B: weekend structure ===")
# Friday last bar -> Monday first bar
wk = np.array([d.weekday() for d in dts])
fri_close, mon_open, mon_first_pnl, mon_dates = [], [], [], []
prev_fri_i = None
for d in days:
    i0, i1 = day_first[d], day_last[d]
    wd = d.weekday()
    if wd == 4: prev_fri_i = i1
    if wd == 0 and prev_fri_i is not None:
        gap = o[i0] - c[prev_fri_i]
        fri_close.append(c[prev_fri_i]); mon_open.append(o[i0])
        mon_first_pnl.append((gap, c[i0]-o[i0], c[min(i0+3, i1)]-o[i0], d))
gaps = np.array([x[0] for x in mon_first_pnl])
fb   = np.array([x[1] for x in mon_first_pnl])
fh   = np.array([x[2] for x in mon_first_pnl])
print(f"  Mondays n={len(gaps)}  weekend gap: mean=${gaps.mean():+.3f} sd=${gaps.std():.2f} P(gap>0)={(gaps>0).mean():.3f}")
for tag, mask in [("gap DOWN", gaps < 0), ("gap UP", gaps > 0),
                  ("gap DOWN big", gaps < np.median(gaps[gaps<0]) if (gaps<0).sum()>10 else gaps<0),
                  ("gap UP big", gaps > np.median(gaps[gaps>0]) if (gaps>0).sum()>10 else gaps>0)]:
    if mask.sum() < 10: continue
    for lab, arr in [("first bar", fb), ("first hour", fh)]:
        vv = arr[mask]; se = vv.std()/math.sqrt(len(vv))
        print(f"    {tag:12s} {lab:9s}: n={len(vv):3d} E=${vv.mean():+.3f} t={vv.mean()/se:+.2f} WR={(vv>0).mean():.3f}")

print("\n=== B2: does weekend gap FILL like the daily gap (98%)? ===")
filled = 0; tot = 0
for gap, _, _, d in mon_first_pnl:
    i0, i1 = day_first[d], day_last[d]
    target = o[i0] - gap  # friday close
    if gap > 0:   hit = (l[i0:i1+1] <= target).any()
    elif gap < 0: hit = (h[i0:i1+1] >= target).any()
    else: continue
    tot += 1; filled += int(hit)
print(f"  P(weekend gap filled same Monday) = {filled/tot:.3f}  (n={tot})")

print("\n=== C: EURUSD procedural comparison ===")
t2, o2, h2, l2, c2, v2 = load('data/EURUSD_M15.csv')
dts2 = [datetime.fromtimestamp(x, tz=timezone.utc) for x in t2]
day_first2 = {}
for i, dt_ in enumerate(dts2):
    d = dt_.date()
    if d not in day_first2: day_first2[d] = (i, dt_.hour, dt_.minute)
cnt = Counter(f"{hh:02d}:{mm:02d}" for _, hh, mm in day_first2.values())
print(f"  EURUSD first-bar-of-day times: {dict(cnt.most_common(5))}")
# EURUSD first-bar drift (pip value: 1 pip = 0.0001)
grp2 = defaultdict(list)
for d, (i, hh, mm) in day_first2.items():
    grp2[f"{hh:02d}:{mm:02d}"].append((c2[i]-o2[i])*1e4)
for k in sorted(grp2):
    vv = np.array(grp2[k])
    if len(vv) < 30: continue
    se = vv.std()/math.sqrt(len(vv))
    print(f"  EURUSD day starts {k}: n={len(vv):4d} E[first bar]={vv.mean():+.2f}pip t={vv.mean()/se:+.2f} P(up)={(vv>0).mean():.3f}")
