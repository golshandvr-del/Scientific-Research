#!/usr/bin/env python3
"""
Phase 7: ECONOMIC validation of the LOW-SWEEP (stop-hunt reversal) edge
on XAUUSD M15 with real demo-account costs (spread $0.33/oz, no commission).

Candidate rule (from phase5/6 discoveries, combined Nash-style):
  ENTER LONG when:
    - bar's low breaks the prior N-bar low (liquidity sweep)
    - bar CLOSES back above that prior low (trapped shorts)
    - sweep depth is not "too deep" (deep = real breakdown, not a trap)
  Optional filters to test factorially:
    - vol regime (16-bar realized range)
    - dead-hours exclusion (23,5,6,7 UTC from phase2)
    - symbolic confirmation: current bar is a LARGE down bar (D-accel)
  Exit: time-based (hold H bars) OR TP/SL bracket.

Outputs: net $/oz after costs, WR, t-stat, IS(70%)/OOS(30%), yearly PnL.
"""
import numpy as np, pandas as pd, math, datetime

SPREAD = 0.33
df = pd.read_csv('data/XAUUSD_M15.csv')
t, o, h, l, c = df.time.values, df.open.values, df.high.values, df.low.values, df.close.values
n = len(c)
years = np.array([datetime.datetime.utcfromtimestamp(x).year for x in t])
hours = np.array([datetime.datetime.utcfromtimestamp(x).hour for x in t])

def eval_trades(entries, hold):
    """entries: list of bar index i (signal bar); enter at open[i+1] + spread; exit close[i+hold]"""
    pnl, yr = [], []
    for i in entries:
        if i+1+hold >= n: continue
        entry = o[i+1] + SPREAD
        exitp = c[i+1+hold-1] if hold > 0 else c[i+1]
        pnl.append(exitp - entry)
        yr.append(years[i])
    return np.array(pnl), np.array(yr)

def eval_bracket(entries, tp, sl, max_hold=48):
    pnl, yr = [], []
    for i in entries:
        if i+2 >= n: continue
        entry = o[i+1] + SPREAD
        res = None
        for j in range(i+1, min(i+1+max_hold, n)):
            # pessimistic: SL checked first within same bar
            if l[j] <= entry - sl: res = -sl; break
            if h[j] >= entry + tp: res = tp; break
        if res is None: res = c[min(i+max_hold, n-1)] - entry
        pnl.append(res); yr.append(years[i])
    return np.array(pnl), np.array(yr)

def report(tag, pnl, yr):
    if len(pnl) < 30:
        print(f"{tag}: n={len(pnl)} TOO FEW"); return
    avg = pnl.mean(); se = pnl.std()/math.sqrt(len(pnl))
    wr = (pnl > 0).mean()
    cut = int(len(pnl)*0.7)
    is_p, oos_p = pnl[:cut], pnl[cut:]
    ys = " ".join(f"{y}:{pnl[yr==y].sum():+.0f}" for y in sorted(set(yr)))
    pos_years = sum(1 for y in set(yr) if pnl[yr==y].sum() > 0)
    print(f"{tag}: n={len(pnl)} NET=${pnl.sum():+.0f} avg=${avg:+.3f} WR={wr:.3f} t={avg/se:+.2f} "
          f"| IS avg={is_p.mean():+.3f} OOS avg={oos_p.mean():+.3f} | +yrs={pos_years}/{len(set(yr))}")
    print(f"      yearly: {ys}")

# precompute
N = 48
prior_low = pd.Series(l).rolling(N).min().shift(1).values
sweep = (l < prior_low) & (c > prior_low)
depth = prior_low - l
rv16 = pd.Series(h-l).rolling(16).mean().shift(1).values
r = np.diff(np.log(c), prepend=np.log(c[0]))
q2 = np.quantile(np.abs(r[1:]), 2/3)
large_dn = (r < -q2)   # current bar large down
dead = np.isin(hours, [23,5,6,7])

base_idx = np.where(sweep)[0]
base_idx = base_idx[(base_idx > N) & (base_idx < n-60)]
print(f"total low-sweeps N={N}: {len(base_idx)}")

# depth quantiles among sweeps
dq = np.quantile(depth[base_idx], [0.33, 0.66])
print(f"depth terciles: {dq}")

print("\n--- factorial filter scan (hold=4 bars = 1h) ---")
variants = {
    "raw": base_idx,
    "depth<=q66": base_idx[depth[base_idx] <= dq[1]],
    "depth mid-tercile": base_idx[(depth[base_idx] > dq[0]) & (depth[base_idx] <= dq[1])],
    "no-dead-hours": base_idx[~dead[base_idx]],
    "large-dn bar": base_idx[large_dn[base_idx]],
    "depth<=q66 + no-dead": base_idx[(depth[base_idx] <= dq[1]) & (~dead[base_idx])],
    "depth<=q66 + large-dn": base_idx[(depth[base_idx] <= dq[1]) & large_dn[base_idx]],
    "depth<=q66 + no-dead + large-dn": base_idx[(depth[base_idx] <= dq[1]) & (~dead[base_idx]) & large_dn[base_idx]],
}
for tag, idx in variants.items():
    pnl, yr = eval_trades(idx, 4)
    report(f"[hold4] {tag}", pnl, yr)

print("\n--- hold scan on best filter ---")
best = base_idx[(depth[base_idx] <= dq[1]) & (~dead[base_idx]) & large_dn[base_idx]]
for hold in [2, 4, 8, 16, 32]:
    pnl, yr = eval_trades(best, hold)
    report(f"[hold={hold}]", pnl, yr)

print("\n--- vol regime split on best filter (hold=8) ---")
rvq = np.nanquantile(rv16, [0.25, 0.5, 0.75])
for lo, hi, tag in [(0, rvq[0], "Q1 calm"), (rvq[0], rvq[1], "Q2"), (rvq[1], rvq[2], "Q3"), (rvq[2], 1e9, "Q4 wild")]:
    sel = best[(rv16[best] >= lo) & (rv16[best] < hi)]
    pnl, yr = eval_trades(sel, 8)
    report(f"[{tag}]", pnl, yr)

print("\n--- TP/SL brackets on best filter (vol-scaled and fixed) ---")
for tp, sl in [(2,2), (3,2), (4,3), (6,4), (8,5)]:
    pnl, yr = eval_bracket(best, tp, sl)
    report(f"[TP={tp} SL={sl}]", pnl, yr)
# vol-scaled brackets: tp = a*rv16, sl = b*rv16
for a, b in [(2,1.5), (3,2), (4,3)]:
    pnl, yr = [], []
    for i in best:
        if np.isnan(rv16[i]) or i+2 >= n: continue
        tp_, sl_ = a*rv16[i], b*rv16[i]
        entry = o[i+1] + SPREAD
        res = None
        for j in range(i+1, min(i+49, n)):
            if l[j] <= entry - sl_: res = -sl_; break
            if h[j] >= entry + tp_: res = tp_; break
        if res is None: res = c[min(i+48, n-1)] - entry
        pnl.append(res); yr.append(years[i])
    report(f"[volTP={a}xRV volSL={b}xRV]", np.array(pnl), np.array(yr))
