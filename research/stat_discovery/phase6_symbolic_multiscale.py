#!/usr/bin/env python3
"""
Phase 6: SYMBOLIC DYNAMICS + MULTI-SCALE MEMORY on XAUUSD M15
A) Symbolic dynamics: encode each bar as a letter from alphabet built on
   (direction, magnitude-tercile) -> 6 letters. Scan all 3-letter words:
   which words are "forbidden" (occur far less than Markov expectation)
   and which words PREDICT the next letter beyond chain expectation.
B) Variance Ratio test (Lo-MacKinlay): VR(q) over q=2..96 to find the
   time scale where gold switches between mean-reversion and momentum.
C) Rough Hurst exponent by regime (high-vol vs low-vol) - does memory
   structure CHANGE with regime? (this is the 'floating rules' law)
"""
import numpy as np, pandas as pd, math

df = pd.read_csv('data/XAUUSD_M15.csv')
c = df.close.values
r = np.diff(np.log(c))
n = len(r)
sd = r.std()

# ---------- A: symbolic dynamics ----------
print("=== A: symbolic dynamics (6-letter alphabet) ===")
# letters: direction U/D x magnitude small/mid/large (terciles of |r|)
q1, q2 = np.quantile(np.abs(r), [1/3, 2/3])
mag = np.where(np.abs(r) < q1, 0, np.where(np.abs(r) < q2, 1, 2))
dirn = (r > 0).astype(int)
letter = dirn*3 + mag   # 0..5 : D-small,D-mid,D-large,U-small,U-mid,U-large
names = ['d','D','𝔻','u','U','𝕌']  # small/mid/LARGE down, small/mid/LARGE up

# unconditional letter probs
p_letter = np.bincount(letter, minlength=6)/n

# all 2-letter contexts -> next letter distribution; find strongest deviations
from collections import defaultdict
ctx_next = defaultdict(lambda: np.zeros(6))
for i in range(2, n):
    ctx_next[(letter[i-2], letter[i-1])][letter[i]] += 1

rows = []
for ctx, cnts in ctx_next.items():
    tot = cnts.sum()
    if tot < 300: continue
    for nx in range(6):
        p_hat = cnts[nx]/tot
        p0 = p_letter[nx]
        z = (p_hat-p0)/math.sqrt(p0*(1-p0)/tot)
        rows.append((abs(z), z, ctx, nx, p_hat, p0, tot))
rows.sort(reverse=True)
print("top 15 strongest word->next-letter deviations:")
for absz, z, ctx, nx, p_hat, p0, tot in rows[:15]:
    w = names[ctx[0]]+names[ctx[1]]
    print(f"  '{w}' -> '{names[nx]}': P={p_hat:.3f} vs base {p0:.3f}  z={z:+.1f} (n={int(tot)})")

# directional consequence: for top contexts, what's E[next return | ctx]?
print("\ncontexts with strongest E[next r] (in sd units):")
rows2 = []
for ctx, cnts in ctx_next.items():
    tot = int(cnts.sum())
    if tot < 500: continue
    idx = [i for i in range(2, n) if letter[i-2]==ctx[0] and letter[i-1]==ctx[1]]
    e = r[idx].mean()/sd
    t = e*math.sqrt(len(idx))/(r[idx].std()/sd)
    rows2.append((abs(t), t, ctx, e, tot))
rows2.sort(reverse=True)
for abst, t, ctx, e, tot in rows2[:10]:
    w = names[ctx[0]]+names[ctx[1]]
    print(f"  '{w}': E[next]={e:+.4f}sd  t={t:+.2f}  n={tot}")

# ---------- B: variance ratio ----------
print("\n=== B: Variance Ratio VR(q)  (VR<1 mean-reversion, VR>1 momentum) ===")
for q in [2, 4, 8, 16, 32, 64, 96, 192]:
    # sum of q consecutive returns
    rq = np.add.reduceat(r[:n//q*q], np.arange(0, n//q*q, q))
    vr = rq.var()/(q*r.var())
    # asymptotic z under iid (rough)
    z = (vr-1)*math.sqrt(len(rq))/math.sqrt(2*(2*q-1)*(q-1)/(3*q))
    scale_min = q*15
    print(f"  q={q:3d} ({scale_min/60:5.1f}h): VR={vr:.4f}  z={z:+.2f}")

# ---------- C: memory by volatility regime ----------
print("\n=== C: lag-1 autocorr of returns BY vol regime (16-bar realized vol) ===")
rv = pd.Series(np.abs(r)).rolling(16).mean().shift(1).values
qs = np.nanquantile(rv, [0.25, 0.5, 0.75])
labels = ['Q1 calm', 'Q2', 'Q3', 'Q4 wild']
bounds = [(-1, qs[0]), (qs[0], qs[1]), (qs[1], qs[2]), (qs[2], 1e9)]
for (lo, hi), lab in zip(bounds, labels):
    m = (rv >= lo) & (rv < hi)
    m[:17] = False
    idx = np.where(m[:-1])[0]
    x, y = r[idx], r[idx+1]
    ac = np.corrcoef(x, y)[0,1]
    z = ac*math.sqrt(len(x))
    print(f"  {lab:8s}: n={len(x):6d}  AC1={ac:+.4f}  z={z:+.2f}")
