#!/usr/bin/env python3
"""
Phase 15: CYCLE STRUCTURE (Rejewski's permutation cycles) on XAUUSD M15
Rejewski deduced rotor wiring from cycle lengths. Our analog: the internal
cycle of the trading day -- WHEN are the daily HIGH and LOW made?
If low-of-day clusters early and high-of-day clusters late (consistent with
the structural updrift), that is an exploitable day-shape.
  A) distribution of high-time and low-time within the day
  B) P(low is made in first K bars) -- "buy the early dip" foundation
  C) day-shape conditional: if first hour is DOWN, when is the low?
  D) range expansion: by what fraction of the day is X% of range done?
"""
import csv, math
from datetime import datetime, timezone
import numpy as np
from collections import defaultdict

t, o, h, l, c = [], [], [], [], []
with open('data/XAUUSD_M15.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        t.append(int(float(r[0]))); o.append(float(r[1])); h.append(float(r[2]))
        l.append(float(r[3])); c.append(float(r[4]))
t = np.array(t); o = np.array(o); h = np.array(h); l = np.array(l); c = np.array(c)
dts = [datetime.fromtimestamp(x, tz=timezone.utc) for x in t]

# build day slices (only full-ish days: >= 80 bars of max 92)
day_idx = defaultdict(list)
for i, d in enumerate(dts):
    day_idx[d.date()].append(i)
days = [d for d in sorted(day_idx) if len(day_idx[d]) >= 80]
print(f"full days: {len(days)}")

hi_pos, lo_pos, nb_list = [], [], []
hi_hour, lo_hour = [], []
for d in days:
    ii = day_idx[d]
    hh = h[ii]; ll = l[ii]
    hi_i = int(np.argmax(hh)); lo_i = int(np.argmin(ll))
    nb = len(ii)
    hi_pos.append(hi_i / nb); lo_pos.append(lo_i / nb)
    hi_hour.append(dts[ii[hi_i]].hour); lo_hour.append(dts[ii[lo_i]].hour)
    nb_list.append(nb)
hi_pos = np.array(hi_pos); lo_pos = np.array(lo_pos)
hi_hour = np.array(hi_hour); lo_hour = np.array(lo_hour)

print("\n=== A: where in the day are extremes made? (deciles of day) ===")
print("  decile |  P(HIGH here) | P(LOW here)  (uniform = 0.100)")
for k in range(10):
    ph = ((hi_pos >= k/10) & (hi_pos < (k+1)/10)).mean()
    pl = ((lo_pos >= k/10) & (lo_pos < (k+1)/10)).mean()
    print(f"    {k+1:2d}   |     {ph:.3f}     |   {pl:.3f}   {'#'*int(ph*100)}|{'#'*int(pl*100)}")

print("\n=== A2: extremes by UTC hour ===")
for hh in range(24):
    ph = (hi_hour == hh).mean(); pl = (lo_hour == hh).mean()
    if ph > 0.01 or pl > 0.01:
        print(f"  h={hh:02d}: P(high)={ph:.3f} P(low)={pl:.3f}")

print("\n=== B: P(low of day already made after first K bars) ===")
for K in [1, 2, 4, 8, 12, 16]:
    p_lo = (np.array(lo_pos) * np.array(nb_list) < K).mean()
    p_hi = (np.array(hi_pos) * np.array(nb_list) < K).mean()
    print(f"  K={K:2d} bars (~{K*15/60:.1f}h): P(low done)={p_lo:.3f}  P(high done)={p_hi:.3f}")

print("\n=== C: conditional day shape ===")
# if first hour (4 bars) is DOWN, when is the low? and what is close vs open?
fh_dir, lo_pos_c, day_ret = [], [], []
for d in days:
    ii = day_idx[d]
    if len(ii) < 8: continue
    fh = c[ii[3]] - o[ii[0]]
    lo_i = int(np.argmin(l[ii])); nb = len(ii)
    fh_dir.append(1 if fh > 0 else -1)
    lo_pos_c.append(lo_i / nb)
    day_ret.append(c[ii[-1]] - o[ii[0]])
fh_dir = np.array(fh_dir); lo_pos_c = np.array(lo_pos_c); day_ret = np.array(day_ret)
for tag, m in [("first hour UP", fh_dir > 0), ("first hour DOWN", fh_dir < 0)]:
    early_lo = (lo_pos_c[m] < 0.25).mean()
    dr = day_ret[m]; se = dr.std()/math.sqrt(m.sum())
    print(f"  {tag}: n={m.sum()} P(low in first quarter)={early_lo:.3f}  E[day ret]=${dr.mean():+.3f} t={dr.mean()/se:+.2f}")

print("\n=== C2: 'first-hour low holds' test ===")
# if the low of the FIRST HOUR is never broken, day closes up? and P(hold)?
hold, ret_hold, ret_broken = 0, [], []
for d in days:
    ii = day_idx[d]
    if len(ii) < 12: continue
    fh_lo = l[ii[:4]].min()
    rest_lo = l[ii[4:]].min()
    dr = c[ii[-1]] - o[ii[0]]
    if rest_lo >= fh_lo - 0.01:
        hold += 1; ret_hold.append(dr)
    else:
        ret_broken.append(dr)
rh = np.array(ret_hold); rb = np.array(ret_broken)
print(f"  P(first-hour low holds all day) = {len(rh)/(len(rh)+len(rb)):.3f}")
print(f"  day ret | low holds : n={len(rh)} E=${rh.mean():+.3f} t={rh.mean()/(rh.std()/math.sqrt(len(rh))):+.2f} P(up)={(rh>0).mean():.3f}")
print(f"  day ret | low broken: n={len(rb)} E=${rb.mean():+.3f} t={rb.mean()/(rb.std()/math.sqrt(len(rb))):+.2f} P(up)={(rb>0).mean():.3f}")

print("\n=== D: range expansion curve (median fraction of final range done) ===")
fracs = np.linspace(0.1, 1.0, 10)
curves = []
for d in days:
    ii = day_idx[d]
    nb = len(ii)
    full_range = h[ii].max() - l[ii].min()
    if full_range <= 0: continue
    row = []
    for f in fracs:
        k = max(1, int(nb * f))
        rr = h[ii[:k]].max() - l[ii[:k]].min()
        row.append(rr / full_range)
    curves.append(row)
curves = np.array(curves)
for j, f in enumerate(fracs):
    print(f"  by {int(f*100):3d}% of day: median range done = {np.median(curves[:,j]):.3f}")
