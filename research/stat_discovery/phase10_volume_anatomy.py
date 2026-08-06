#!/usr/bin/env python3
"""
Phase 10: VOLUME ANATOMY on XAUUSD M15 -- the untouched column
A) Deseasonalized relative volume (RVOL): volume vs same-time-of-day median
B) Effort vs Result (Wyckoff): high volume + small range = absorption -> what next?
C) Volume-price divergence over swings
D) Does RVOL at 00:00-01:00 predict the strength of the Asia drift that day?
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
v = np.array([r[5] for r in rows])
n = len(c)
dts = [datetime.fromtimestamp(x, tz=timezone.utc) for x in t]
tod = np.array([d.hour * 4 + d.minute // 15 for d in dts])   # 96 slots
ret = np.diff(np.log(c))

# ---------- A) RVOL: deseasonalize volume by time-of-day median ----------
med = np.zeros(96)
for s in range(96):
    med[s] = np.median(v[tod == s])
rvol = v / med[tod]
print("=== A: RVOL (volume / same-slot median) ===")
print(f"  median RVOL={np.median(rvol):.2f}  p90={np.quantile(rvol,0.9):.2f}  p99={np.quantile(rvol,0.99):.2f}")

# does RVOL predict next-bar |ret| better than raw volume? (rank corr proxy)
nb = np.abs(ret)
r_rank = rvol[:-1].argsort().argsort(); n_rank = nb.argsort().argsort()
v_rank = v[:-1].argsort().argsort()
cr = np.corrcoef(r_rank, n_rank)[0, 1]; cv = np.corrcoef(v_rank, n_rank)[0, 1]
print(f"  rank-corr(RVOL, next|ret|)={cr:+.3f}   rank-corr(rawVOL, next|ret|)={cv:+.3f}")

# ---------- B) Wyckoff effort-vs-result ----------
print("\n=== B: Wyckoff EFFORT vs RESULT (per bar) ===")
rng = h - l
rng_med = np.zeros(96)
for s in range(96):
    rng_med[s] = np.median(rng[tod == s])
rrng = rng / rng_med[tod]   # relative range
body = c - o

hi_v = rvol > 2.0
sm_r = rrng < 1.0
big_r = rrng > 2.0
cases = [
    ("ABSORPTION: RVOL>2 & range<median", hi_v & sm_r),
    ("CLIMAX: RVOL>2 & range>2x", hi_v & big_r),
    ("NO-DEMAND: RVOL<0.5 & range>1.5x", (rvol < 0.5) & (rrng > 1.5)),
]
for tag, m in cases:
    idx = np.where(m[:-8])[0]
    idx = idx[idx > 0]
    if len(idx) < 50:
        print(f"  {tag}: n={len(idx)} (too few)"); continue
    # split by bar direction
    for dtag, dm in [("after UP bar", body[idx] > 0), ("after DOWN bar", body[idx] < 0)]:
        ii = idx[dm]
        if len(ii) < 50: continue
        fwd4 = c[ii + 4] - c[ii]
        fwd8 = c[ii + 8] - c[ii]
        se4 = fwd4.std() / math.sqrt(len(ii)); se8 = fwd8.std() / math.sqrt(len(ii))
        print(f"  {tag} {dtag}: n={len(ii)}  E[4bar]=${fwd4.mean():+.3f} t={fwd4.mean()/se4:+.2f} | E[8bar]=${fwd8.mean():+.3f} t={fwd8.mean()/se8:+.2f}")

# ---------- C) volume divergence on swings ----------
print("\n=== C: NEW HIGH/LOW with weak vs strong volume (48-bar swing) ===")
N = 48
roll_max = np.array([h[max(0, i - N):i].max() if i > 0 else h[0] for i in range(n)])
roll_min = np.array([l[max(0, i - N):i].min() if i > 0 else l[0] for i in range(n)])
new_hi = (h > roll_max) & (np.arange(n) > N)
new_lo = (l < roll_min) & (np.arange(n) > N)
for tag, brk, in [("NEW HIGH", new_hi), ("NEW LOW", new_lo)]:
    idx = np.where(brk[:-8])[0]
    if len(idx) < 100: continue
    weak = idx[rvol[idx] < 1.0]   # breakout on weak volume
    strong = idx[rvol[idx] > 2.0]
    for vt, ii in [("weak vol (RVOL<1)", weak), ("strong vol (RVOL>2)", strong)]:
        if len(ii) < 80: continue
        fwd = c[ii + 8] - c[ii]
        se = fwd.std() / math.sqrt(len(ii))
        print(f"  {tag} on {vt}: n={len(ii)}  E[8bar fwd]=${fwd.mean():+.3f}  t={fwd.mean()/se:+.2f}  P(up)={(fwd>0).mean():.3f}")

# ---------- D) does 00:00-01:00 RVOL predict that day's Asia drift? ----------
print("\n=== D: does midnight RVOL predict the 01:00 Asia-drift quality? ===")
# find bars at 00:00-00:45 (slots 0..3) and the 01:00->02:00 move of same day
by_day = {}
for i, d in enumerate(dts):
    key = (d.year, d.month, d.day)
    by_day.setdefault(key, []).append(i)
pre_rv, drift = [], []
for key, idxs in by_day.items():
    slot_map = {tod[i]: i for i in idxs}
    pre = [slot_map[s] for s in range(0, 4) if s in slot_map]      # 00:00-00:45
    if len(pre) < 3: continue
    i0 = slot_map.get(4); i1 = slot_map.get(12)                     # 01:00 open -> 03:00 open
    if i0 is None or i1 is None: continue
    pre_rv.append(np.mean(rvol[pre])); drift.append(c[i1] - o[i0])
pre_rv = np.array(pre_rv); drift = np.array(drift)
print(f"  days={len(drift)}  mean drift(01->03)=${drift.mean():+.3f}")
qs = np.quantile(pre_rv, [0.25, 0.5, 0.75])
for tag, m in [("midnight RVOL Q1 (quiet)", pre_rv <= qs[0]),
               ("Q2", (pre_rv > qs[0]) & (pre_rv <= qs[1])),
               ("Q3", (pre_rv > qs[1]) & (pre_rv <= qs[2])),
               ("Q4 (busy midnight)", pre_rv > qs[2])]:
    dd = drift[m]
    se = dd.std() / math.sqrt(m.sum())
    wr = (dd > 0).mean()
    print(f"  {tag:26s}: n={m.sum():4d}  E[drift]=${dd.mean():+.3f}  t={dd.mean()/se:+.2f}  WR={wr:.3f}")
