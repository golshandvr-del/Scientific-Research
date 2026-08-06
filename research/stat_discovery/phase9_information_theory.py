#!/usr/bin/env python3
"""
Phase 9: INFORMATION THEORY (Turing-style codebreaking) on XAUUSD M15
A) Conditional entropy of direction given past k directions -- global + BY HOUR
   -> WHERE (in time) does the market leak information?
B) Lempel-Ziv complexity in sliding windows -> compressibility as regime signal
   -> does LOW complexity (compressible = ordered) predict future returns/vol?
C) Mutual information I(volume-quantile ; next return sign/size)
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
c = np.array([r[4] for r in rows])
v = np.array([r[5] for r in rows])
ret = np.diff(np.log(c))
sign = (ret > 0).astype(int)  # 1=up, 0=down (zero-returns counted as down; rare)
hours = np.array([datetime.fromtimestamp(x, tz=timezone.utc).hour for x in t[1:]])
n = len(ret)
print(f"N returns = {n}")

def H(p):
    p = p[p > 0]
    return -np.sum(p * np.log2(p))

# ---------- A) conditional entropy H(next | past k) ----------
print("\n=== A: conditional entropy of direction (bits; 1.0 = pure coin flip) ===")
for k in [1, 2, 3, 4, 5]:
    # build context integer
    ctx = np.zeros(n - k, dtype=int)
    for j in range(k):
        ctx = ctx * 2 + sign[j:n - k + j]
    nxt = sign[k:]
    # H(next|ctx) = H(joint) - H(ctx)
    joint = ctx * 2 + nxt
    pj = np.bincount(joint, minlength=2**(k+1)) / len(joint)
    pc = np.bincount(ctx, minlength=2**k) / len(ctx)
    hc = H(pj) - H(pc)
    print(f"  k={k}: H(next|past)={hc:.5f} bits  info-leak={1-hc:.5f} bits")

print("\n=== A2: info leak BY HOUR (k=3) -- when is the cipher weakest? ===")
k = 3
ctx = np.zeros(n - k, dtype=int)
for j in range(k):
    ctx = ctx * 2 + sign[j:n - k + j]
nxt = sign[k:]
hrs = hours[k:]
leaks = []
for h in range(24):
    m = hrs == h
    if m.sum() < 2000: continue
    cj = ctx[m] * 2 + nxt[m]
    pj = np.bincount(cj, minlength=16) / m.sum()
    pc = np.bincount(ctx[m], minlength=8) / m.sum()
    leak = 1 - (H(pj) - H(pc))
    leaks.append((leak, h, m.sum()))
leaks.sort(reverse=True)
for leak, h, cnt in leaks[:6]:
    print(f"  h={h:02d}: leak={leak*1000:.2f} milli-bits (n={cnt})")
print("  ... least predictable:")
for leak, h, cnt in leaks[-3:]:
    print(f"  h={h:02d}: leak={leak*1000:.2f} milli-bits (n={cnt})")

# ---------- B) Lempel-Ziv complexity as regime detector ----------
def lz76(s):
    # Lempel-Ziv 1976 complexity of a binary string (list of 0/1)
    i, cnt, l = 0, 1, 1
    k, kmax = 1, 1
    nn = len(s)
    while True:
        if s[i + k - 1] == s[l + k - 1]:
            k += 1
            if l + k > nn:
                cnt += 1; break
        else:
            if k > kmax: kmax = k
            i += 1
            if i == l:
                cnt += 1; l += kmax
                if l + 1 > nn: break
                i = 0; k = 1; kmax = 1
            else:
                k = 1
    return cnt

W = 96  # one day of M15 bars
norm = W / math.log2(W)  # expected complexity of random string ~ n/log2(n)
print(f"\n=== B: LZ complexity (window={W} bars=1 day), normalized (1.0≈random) ===")
step = 24
lz_vals, fwd_ret, fwd_vol, idxs = [], [], [], []
rv_all = np.abs(ret)
for start in range(0, n - W - 96, step):
    s = sign[start:start + W].tolist()
    lz = lz76(s) / norm
    fr = np.sum(ret[start + W: start + W + 96])          # next-day return
    fv = np.mean(rv_all[start + W: start + W + 96])      # next-day realized vol
    lz_vals.append(lz); fwd_ret.append(fr); fwd_vol.append(fv); idxs.append(start)
lz_vals = np.array(lz_vals); fwd_ret = np.array(fwd_ret); fwd_vol = np.array(fwd_vol)
print(f"  windows={len(lz_vals)}  LZ mean={lz_vals.mean():.3f}  sd={lz_vals.std():.3f}  min={lz_vals.min():.3f}  max={lz_vals.max():.3f}")
q = np.quantile(lz_vals, [0.1, 0.25, 0.75, 0.9])
for tag, m in [("LZ lowest 10% (ordered)", lz_vals <= q[0]),
               ("LZ low 25%", lz_vals <= q[1]),
               ("LZ high 25%", lz_vals >= q[2]),
               ("LZ highest 10% (random)", lz_vals >= q[3])]:
    fr = fwd_ret[m]; fv = fwd_vol[m]
    se = fr.std() / math.sqrt(len(fr))
    print(f"  {tag:26s}: n={m.sum():4d} E[next-day ret]={fr.mean()*1e4:+.2f}bp t={fr.mean()/se:+.2f}  next-day vol={fv.mean()*1e4:.2f}bp")
# correlation LZ vs future vol
cc = np.corrcoef(lz_vals, fwd_vol)[0, 1]
cr = np.corrcoef(lz_vals, np.abs(fwd_ret))[0, 1]
print(f"  corr(LZ, next-day vol) = {cc:+.3f}   corr(LZ, |next-day ret|) = {cr:+.3f}")

# ---------- C) mutual information volume -> next bar ----------
print("\n=== C: does VOLUME leak info about the NEXT bar? ===")
vq = np.searchsorted(np.quantile(v[1:], [0.2, 0.4, 0.6, 0.8]), v[1:-0 or None])  # vol quantile of current bar
vq = vq[:-1]; nxt_sign = sign[1:]; nxt_abs = np.abs(ret[1:])
# MI(volume-quintile ; next sign)
pj = np.zeros((5, 2))
for a in range(5):
    m = vq == a
    pj[a, 0] = np.sum(nxt_sign[m] == 0); pj[a, 1] = np.sum(nxt_sign[m] == 1)
pj /= pj.sum()
mi = H(pj.sum(axis=1)) + H(pj.sum(axis=0)) - H(pj.flatten())
print(f"  MI(vol-quintile ; next-sign) = {mi*1000:.3f} milli-bits (direction: ~nothing expected)")
# but SIZE:
print("  next-bar |ret| by current volume quintile:")
for a in range(5):
    m = vq == a
    print(f"    vq={a}: E|ret_next|={nxt_abs[m].mean()*1e4:.2f}bp  (n={m.sum()})")
# volume spike + direction interaction
vs = v[1:-1] > np.quantile(v, 0.95)
up = sign[:-1] == 1
for tag, m in [("vol-spike & UP bar", vs & up[:len(vs)]), ("vol-spike & DOWN bar", vs & ~up[:len(vs)])]:
    r2 = ret[1:][m]
    se = r2.std() / math.sqrt(m.sum())
    print(f"  {tag}: n={m.sum()} E[next ret]={r2.mean()*1e4:+.2f}bp t={r2.mean()/se:+.2f}")
