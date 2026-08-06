#!/usr/bin/env python3
"""
Phase 1: Pure statistical discovery on XAUUSD M15
- Return distribution (fat tails, skew, kurtosis, normality)
- Autocorrelation of returns (momentum vs mean reversion)
- Conditional probabilities after consecutive up/down bars
NO indicators, NO docs — raw statistics only.
"""
import csv, math, statistics
from collections import defaultdict

PATH = "/home/user/webapp/data/XAUUSD_M15.csv"

rows = []
with open(PATH) as f:
    r = csv.reader(f)
    next(r)
    for line in r:
        t = int(line[0]); o = float(line[1]); h = float(line[2])
        l = float(line[3]); c = float(line[4]); v = float(line[5])
        rows.append((t, o, h, l, c, v))

n = len(rows)
closes = [r[4] for r in rows]
# log returns per bar
rets = [math.log(closes[i]/closes[i-1]) for i in range(1, n)]

print(f"BARS={n}  RETURNS={len(rets)}")
mu = statistics.mean(rets)
sd = statistics.pstdev(rets)
# skew & kurtosis (excess)
m3 = sum((x-mu)**3 for x in rets)/len(rets)
m4 = sum((x-mu)**4 for x in rets)/len(rets)
skew = m3/sd**3
kurt = m4/sd**4 - 3
print(f"MEAN_RET={mu:.3e}  SD={sd:.3e}  SKEW={skew:.3f}  EXCESS_KURT={kurt:.2f}")
print(f"ANNUALIZED_DRIFT≈{mu*4*24*252*100:.1f}%  (M15 bars)")

# tail analysis: how often do we exceed k*sd vs normal expectation
import bisect
abs_r = sorted(abs(x-mu) for x in rets)
for k in [2,3,4,5,6]:
    cnt = len(abs_r) - bisect.bisect_left(abs_r, k*sd)
    frac = cnt/len(rets)
    # normal expectation two-sided
    norm_exp = math.erfc(k/math.sqrt(2))
    print(f"TAIL |r|>{k}sd: observed={frac:.5%}  normal={norm_exp:.5%}  ratio={frac/norm_exp if norm_exp>0 else float('inf'):.1f}x")

# Autocorrelation of returns, lags 1..20
def autocorr(x, lag):
    m = statistics.mean(x)
    num = sum((x[i]-m)*(x[i-lag]-m) for i in range(lag, len(x)))
    den = sum((xi-m)**2 for xi in x)
    return num/den

print("\nAUTOCORRELATION of returns (lag: ac, significance ~ +/-{:.4f} at 95%)".format(1.96/math.sqrt(len(rets))))
for lag in range(1, 21):
    ac = autocorr(rets, lag)
    sig = "**" if abs(ac) > 1.96/math.sqrt(len(rets)) else ""
    print(f"  lag={lag:2d}: {ac:+.4f} {sig}")

# Autocorrelation of ABSOLUTE returns (volatility clustering)
abs_rets = [abs(x) for x in rets]
print("\nAUTOCORRELATION of |returns| (volatility clustering)")
for lag in [1,2,3,4,5,10,20,48,96]:
    ac = autocorr(abs_rets, lag)
    print(f"  lag={lag:3d}: {ac:+.4f}")

# Conditional probability: after k consecutive up bars, P(next up)?
dirs = [1 if rets[i] > 0 else (-1 if rets[i] < 0 else 0) for i in range(len(rets))]
print("\nCONDITIONAL: after k consecutive UP bars -> P(next up), and mean next ret (in sd units)")
for k in range(1, 8):
    ups_next_up = 0; ups_total = 0; sum_next = 0.0
    downs_next_up = 0; downs_total = 0; sum_next_d = 0.0
    run = 0; prev = 0
    for i in range(len(dirs)-1):
        d = dirs[i]
        if d == prev and d != 0:
            run += 1
        elif d != 0:
            run = 1
        else:
            run = 0
        prev = d
        if run == k and d == 1:
            ups_total += 1
            sum_next += rets[i+1]
            if dirs[i+1] == 1: ups_next_up += 1
        if run == k and d == -1:
            downs_total += 1
            sum_next_d += rets[i+1]
            if dirs[i+1] == 1: downs_next_up += 1
    if ups_total > 30 and downs_total > 30:
        pu = ups_next_up/ups_total
        pd = downs_next_up/downs_total
        mu_u = (sum_next/ups_total)/sd
        mu_d = (sum_next_d/downs_total)/sd
        # binomial se
        se_u = math.sqrt(pu*(1-pu)/ups_total)
        se_d = math.sqrt(pd*(1-pd)/downs_total)
        print(f"  k={k}: afterUP n={ups_total:6d} P(up)={pu:.3f}±{se_u:.3f} E[next]={mu_u:+.3f}sd | afterDOWN n={downs_total:6d} P(up)={pd:.3f}±{se_d:.3f} E[next]={mu_d:+.3f}sd")

# Large bar reaction: after a bar > 2sd move, what happens next?
print("\nREACTION to large bars (|ret| > k*sd): next-bar mean return in same direction units")
for k in [1.5, 2, 2.5, 3, 4]:
    cont = 0; rev = 0; tot = 0; sum_signed = 0.0
    for i in range(len(rets)-1):
        if abs(rets[i]-mu) > k*sd:
            tot += 1
            same = rets[i+1]*(1 if rets[i]>0 else -1)
            sum_signed += same
            if same > 0: cont += 1
            elif same < 0: rev += 1
    if tot > 30:
        print(f"  k={k}: n={tot:5d} P(continue)={cont/tot:.3f} P(reverse)={rev/tot:.3f} E[same-dir next]={sum_signed/tot/sd:+.3f}sd")
