#!/usr/bin/env python3
"""
Phase 5: GAME-THEORETIC patterns on XAUUSD M15
A) Schelling focal points: round-number levels ($10/$25/$50/$100 grid)
   - digit clustering of closes (do prices avoid/attract round levels?)
   - bounce probability after touching a round level from above/below
B) Stop-hunt / liquidity sweep (turtle-soup):
   - bar breaks N-bar low but CLOSES back above it -> trapped shorts -> up?
   - symmetric for highs
All probabilities compared vs unconditional baseline with binomial z.
"""
import numpy as np, pandas as pd, math

df = pd.read_csv('data/XAUUSD_M15.csv')
o, h, l, c = df.open.values, df.high.values, df.low.values, df.close.values
n = len(c)
ret = np.diff(c)
P_UP = (ret > 0).mean()
print(f"BARS={n} baseline P(up)={P_UP:.4f}")

def zscore(p_hat, p0, cnt):
    if cnt < 30: return 0.0
    se = math.sqrt(p0*(1-p0)/cnt)
    return (p_hat - p0)/se

# ---------- A1: digit clustering ----------
print("\n=== A1: close price clustering around round levels ===")
frac1 = np.mod(c, 1.0)          # cents
frac10 = np.mod(c, 10.0)        # within $10 grid
# how often close lands within +-0.10 of an integer dollar vs uniform expectation 20%
near_int = ((frac1 < 0.10) | (frac1 > 0.90)).mean()
print(f"P(close within ±$0.10 of integer) = {near_int:.4f}  (uniform=0.20)")
# within $10 grid: near x0.00 levels
near_10 = ((frac10 < 0.50) | (frac10 > 9.50)).mean()
print(f"P(close within ±$0.50 of $10-level) = {near_10:.4f} (uniform=0.10)")
# histogram of $10-grid deciles
hist, _ = np.histogram(frac10, bins=10, range=(0,10))
print("$10-grid decile occupancy (uniform=0.100 each):")
for i, v in enumerate(hist):
    print(f"  [{i}..{i+1}): {v/n:.4f}")

# ---------- A2: bounce after touching round level from above ----------
print("\n=== A2: reaction after TOUCH of round level ===")
for grid, eps in [(10.0, 0.30), (25.0, 0.40), (50.0, 0.50), (100.0, 0.60)]:
    levels_below = np.floor(l/grid)*grid + grid  # nearest grid at/above low? compute touch:
    # touch from above: open above level, low dips to within eps of level (or slightly below), level = floor(open/grid)*grid
    L = np.floor(o/grid)*grid
    touch = (o > L + eps) & (l <= L + eps) & (l >= L - eps) & (c > L)  # dipped to level, closed above
    idx = np.where(touch[:-4])[0]
    if len(idx) < 50: continue
    fwd1 = c[idx+1] - c[idx]
    fwd4 = c[idx+4] - c[idx]
    p_up1 = (fwd1 > 0).mean()
    print(f"grid=${grid:.0f} touches={len(idx)}  P(next up)={p_up1:.3f} z={zscore(p_up1,P_UP,len(idx)):+.2f}  "
          f"E[fwd1]=${fwd1.mean():+.3f}  E[fwd4]=${fwd4.mean():+.3f}")
    # symmetric: touch from below (resistance)
    Lr = np.ceil(o/grid)*grid
    touch_r = (o < Lr - eps) & (h >= Lr - eps) & (h <= Lr + eps) & (c < Lr)
    idx = np.where(touch_r[:-4])[0]
    if len(idx) >= 50:
        fwd1 = c[idx+1] - c[idx]; fwd4 = c[idx+4] - c[idx]
        p_dn1 = (fwd1 < 0).mean()
        print(f"       resistance touches={len(idx)}  P(next dn)={p_dn1:.3f} z={zscore(p_dn1,1-P_UP,len(idx)):+.2f}  "
              f"E[fwd1]=${fwd1.mean():+.3f}  E[fwd4]=${fwd4.mean():+.3f}")

# ---------- B: stop-hunt / turtle soup ----------
print("\n=== B: liquidity sweep (break N-bar extreme, close back inside) ===")
for N in [8, 20, 48, 96]:
    # rolling prior extremes (exclusive of current bar)
    prior_low = pd.Series(l).rolling(N).min().shift(1).values
    prior_high = pd.Series(h).rolling(N).max().shift(1).values
    sweep_lo = (l < prior_low) & (c > prior_low)          # swept lows, closed back above
    sweep_hi = (h > prior_high) & (c < prior_high)        # swept highs, closed back below
    for name, mask, sign in [("LOW-sweep->long", sweep_lo, +1), ("HIGH-sweep->short", sweep_hi, -1)]:
        idx = np.where(mask[:-8])[0]
        idx = idx[idx > N]
        if len(idx) < 50: continue
        for hold in [1, 4, 8]:
            fwd = (c[idx+hold] - c[idx]) * sign
            p_win = (fwd > 0).mean()
            base = P_UP if sign > 0 else 1-P_UP
            avg = fwd.mean()
            se = fwd.std()/math.sqrt(len(fwd))
            print(f"N={N:3d} {name:18s} n={len(idx):5d} hold={hold}: P(win)={p_win:.3f} z={zscore(p_win,base,len(idx)):+.2f} "
                  f"E=${avg:+.3f} t={avg/se:+.2f}")
        print()

# ---------- B2: sweep DEPTH matters? (game theory: deeper sweep = more stops harvested) ----------
print("=== B2: sweep depth vs reaction (N=20) ===")
N = 20
prior_low = pd.Series(l).rolling(N).min().shift(1).values
sweep = (l < prior_low) & (c > prior_low)
idx = np.where(sweep[:-8])[0]; idx = idx[idx > N]
depth = prior_low[idx] - l[idx]     # how far below stops were harvested
q = np.quantile(depth, [0.33, 0.66])
for lo_q, hi_q, tag in [(0, q[0], "shallow"), (q[0], q[1], "mid"), (q[1], 1e9, "deep")]:
    sel = idx[(depth >= lo_q) & (depth < hi_q)]
    fwd = c[sel+4] - c[sel]
    se = fwd.std()/math.sqrt(len(fwd))
    print(f"{tag:8s} (depth {lo_q:.2f}-{min(hi_q,99):.2f}$): n={len(sel)} P(up)={(fwd>0).mean():.3f} E[4bar]=${fwd.mean():+.3f} t={fwd.mean()/se:+.2f}")
