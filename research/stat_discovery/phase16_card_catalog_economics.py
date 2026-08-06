#!/usr/bin/env python3
"""
Phase 16: REJEWSKI CARD CATALOG + economic validation (spread=$0.33)
  A) Card catalog: classify each day by 3 observable traits at end of first hour:
       gap sign (vs yesterday close), first-hour direction, yesterday direction
     -> conditional E[rest-of-day return]. 8 cards.
  B) Economic test of best cards: enter at end of first hour, exit at day close,
     stop = first-hour extreme (uses the 97.4% discovery as trailing logic).
  C) Economic test: Monday-after-down-weekend-gap first bar long.
  D) 'First-hour low break' as a MANAGEMENT rule: for a long held from open,
     compare exit-at-close vs exit-on-first-hour-low-break.
"""
import csv, math
from datetime import datetime, timezone
import numpy as np
from collections import defaultdict

SPREAD = 0.33
t, o, h, l, c = [], [], [], [], []
with open('data/XAUUSD_M15.csv') as f:
    rd = csv.reader(f); next(rd)
    for r in rd:
        t.append(int(float(r[0]))); o.append(float(r[1])); h.append(float(r[2]))
        l.append(float(r[3])); c.append(float(r[4]))
t = np.array(t); o = np.array(o); h = np.array(h); l = np.array(l); c = np.array(c)
dts = [datetime.fromtimestamp(x, tz=timezone.utc) for x in t]

day_idx = defaultdict(list)
for i, d in enumerate(dts):
    day_idx[d.date()].append(i)
days = [d for d in sorted(day_idx) if len(day_idx[d]) >= 80]

def report(tag, pnl, yrs):
    pnl = np.array(pnl); yrs = np.array(yrs)
    if len(pnl) < 20:
        print(f"  {tag}: n={len(pnl)} (too few)"); return
    se = pnl.std()/math.sqrt(len(pnl))
    cut = int(len(pnl)*0.7)
    ys = sorted(set(yrs)); pos = sum(1 for y in ys if pnl[yrs==y].sum() > 0)
    print(f"  {tag}: n={len(pnl)} NET=${pnl.sum():+.0f} avg=${pnl.mean():+.3f} WR={(pnl>0).mean():.3f} t={pnl.mean()/se:+.2f} | IS avg={pnl[:cut].mean():+.3f} OOS avg={pnl[cut:].mean():+.3f} | +yrs={pos}/{len(ys)}")

print("=== A: card catalog (8 cards), E[rest-of-day after first hour] ===")
cards = defaultdict(list)
prev_close = None; prev_dir = 0
for d in days:
    ii = day_idx[d]
    if len(ii) < 12: continue
    op = o[ii[0]]; fh_close = c[ii[3]]
    if prev_close is not None:
        gap = 'G+' if op > prev_close else 'G-'
        fh  = 'F+' if fh_close > op else 'F-'
        pd  = 'P+' if prev_dir > 0 else 'P-'
        rest = c[ii[-1]] - fh_close
        cards[(gap, fh, pd)].append((rest, d.year, ii))
    prev_close = c[ii[-1]]; prev_dir = 1 if c[ii[-1]] > o[ii[0]] else -1
for k in sorted(cards):
    v = np.array([x[0] for x in cards[k]])
    se = v.std()/math.sqrt(len(v))
    print(f"  card {k}: n={len(v):3d} E[rest]=${v.mean():+.3f} t={v.mean()/se:+.2f} WR={(v>0).mean():.3f}")

print("\n=== B: economic: enter end of first hour LONG, stop=first-hour low, exit=close ===")
for tag, cond in [
    ("ALL days", lambda g,f,p: True),
    ("F+ only (first hour up)", lambda g,f,p: f=='F+'),
    ("G- & F+ (gap dn, fh up)", lambda g,f,p: g=='G-' and f=='F+'),
    ("F+ & P+ ", lambda g,f,p: f=='F+' and p=='P+'),
]:
    pnl, yrs = [], []
    for k, lst in cards.items():
        g, f, p = k
        if not cond(g, f, p): continue
        for rest, yr, ii in lst:
            entry = c[ii[3]] + SPREAD  # buy at end of first hour
            stop = l[ii[:4]].min()
            res = None
            for j in ii[4:]:
                if l[j] <= stop:
                    res = stop - entry; break
            if res is None:
                res = c[ii[-1]] - entry
            pnl.append(res); yrs.append(yr)
    report(tag, pnl, yrs)

print("\n=== C: Monday after weekend gap-DOWN: long first bar (15 min) ===")
pnl, yrs = [], []
prev_fri_close = None
for d in days:
    ii = day_idx[d]
    if d.weekday() == 4: prev_fri_close = c[ii[-1]]
    if d.weekday() == 0 and prev_fri_close is not None:
        gap = o[ii[0]] - prev_fri_close
        if gap < 0:
            pnl.append(c[ii[0]] - o[ii[0]] - SPREAD); yrs.append(d.year)
report("Mon gap-down 15m long", pnl, yrs)
# stronger: also require gap smaller than median (bigger down gap)
gaps_all = []
prev_fri_close = None
for d in days:
    ii = day_idx[d]
    if d.weekday() == 4: prev_fri_close = c[ii[-1]]
    if d.weekday() == 0 and prev_fri_close is not None:
        gaps_all.append(o[ii[0]] - prev_fri_close)
med_dn = np.median([g for g in gaps_all if g < 0])
pnl, yrs = [], []
prev_fri_close = None
for d in days:
    ii = day_idx[d]
    if d.weekday() == 4: prev_fri_close = c[ii[-1]]
    if d.weekday() == 0 and prev_fri_close is not None:
        gap = o[ii[0]] - prev_fri_close
        if gap < med_dn:
            pnl.append(c[ii[0]] - o[ii[0]] - SPREAD); yrs.append(d.year)
report("Mon BIG gap-down 15m long", pnl, yrs)

print("\n=== D: management rule value: exit long on first-hour-low break vs hold to close ===")
# hypothetical long from day open (proxy for any long layer active that day)
hold_pnl, mgmt_pnl = [], []
for d in days:
    ii = day_idx[d]
    if len(ii) < 12: continue
    entry = o[ii[0]] + SPREAD
    stop = l[ii[:4]].min()
    hold_pnl.append(c[ii[-1]] - entry)
    res = None
    for j in ii[4:]:
        if l[j] <= stop:
            res = stop - entry; break
    if res is None: res = c[ii[-1]] - entry
    mgmt_pnl.append(res)
hp = np.array(hold_pnl); mp = np.array(mgmt_pnl)
print(f"  hold to close : E=${hp.mean():+.3f} sd={hp.std():.2f} worst=${hp.min():+.1f} sum=${hp.sum():+.0f}")
print(f"  exit on break : E=${mp.mean():+.3f} sd={mp.std():.2f} worst=${mp.min():+.1f} sum=${mp.sum():+.0f}")
print(f"  -> risk (sd) reduced by {(1-mp.std()/hp.std())*100:.0f}%, worst-day cut from {hp.min():+.1f} to {mp.min():+.1f}")
