#!/usr/bin/env python3
"""
Phase 20: SOROS IV -- CAPITULATION BUY refined with the REFLEXIVITY DECELERATION FILTER
Insight from phase17-B: inside a down-move, PARABOLIC acceleration -> more downside (t=-2.41),
but STEADY/decelerating decline -> bounce (t=+1.81). Soros: "ride the bust until it exhausts".
Test: E2 (5d trend down & 5d vol >= causal q75) split by deceleration condition:
    DECEL = today's |daily ret| <= 1.5 * mean(|ret| of prev 2 days)
Also combine with hold=8/10d (best raw horizons) and vol-scaled stop.
Spread=$0.33. Causal thresholds only. Non-overlapping.
"""
import pandas as pd, numpy as np, math

SPREAD = 0.33
df = pd.read_csv('data/XAUUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
df['date'] = df['dt'].dt.date
g = df.groupby('date')
daily = pd.DataFrame({'o': g['open'].first(), 'h': g['high'].max(), 'l': g['low'].min(),
                      'c': g['close'].last(), 'n': g['close'].size()})
daily = daily[daily.n >= 40]
c = daily.c.values; l = daily.l.values
years = np.array([d.year for d in daily.index])
r = np.diff(np.log(c))
W = 5
vols = pd.Series(r).rolling(W).std().values
trends = pd.Series(r).rolling(W).sum().values

def report(tag, pnl, yy):
    pnl = np.array(pnl); yy = np.array(yy)
    if len(pnl) < 15:
        print(f"  {tag}: n={len(pnl)} TOO FEW"); return
    se = pnl.std()/math.sqrt(len(pnl))
    cut = int(len(pnl)*0.7)
    pos = sum(1 for y in sorted(set(yy)) if pnl[yy == y].sum() > 0)
    print(f"  {tag}: n={len(pnl)} NET=${pnl.sum():+.0f} avg=${pnl.mean():+.2f} WR={(pnl>0).mean():.3f} "
          f"t={pnl.mean()/se:+.2f} | IS={pnl[:cut].mean():+.2f} OOS={pnl[cut:].mean():+.2f} | +yrs={pos}/{len(set(yy))}")
    print(f"      yearly: {' '.join(f'{y}:{pnl[yy==y].sum():+.0f}' for y in sorted(set(yy)))}")

def run(hold, mode, use_stop=False):
    pnl, yy = [], []
    i = W + 100
    while i < len(r) - hold:
        hist = vols[W:i]
        q75 = np.nanquantile(hist, 0.75)
        base = trends[i] < 0 and vols[i] >= q75
        if base:
            prev2 = np.mean(np.abs(r[i-2:i]))
            decel = prev2 > 0 and abs(r[i]) <= 1.5*prev2
            ok = decel if mode == 'decel' else (not decel) if mode == 'accel' else True
        else:
            ok = False
        if ok:
            e_idx = i + 1
            x_idx = min(e_idx + hold, len(c)-1)
            if use_stop:
                # vol-scaled stop: 2x daily sigma (causal) below entry, checked on daily lows
                sig_d = vols[i]*c[e_idx]
                stop = c[e_idx] - 2.0*sig_d
                res = None
                for j2 in range(e_idx+1, x_idx+1):
                    if l[j2] <= stop:
                        res = stop - c[e_idx]; break
                if res is None: res = c[x_idx] - c[e_idx]
                pnl.append(res - SPREAD)
            else:
                pnl.append(c[x_idx] - c[e_idx] - SPREAD)
            yy.append(years[e_idx])
            i += hold
        else:
            i += 1
    return pnl, yy

print("=== capitulation split by reflexivity filter (hold=8d) ===")
for mode in ['all', 'decel', 'accel']:
    p, y = run(8, mode)
    report(f"hold=8  {mode:5s}", p, y)

print("\n=== hold=10d ===")
for mode in ['all', 'decel', 'accel']:
    p, y = run(10, mode)
    report(f"hold=10 {mode:5s}", p, y)

print("\n=== decel + vol-scaled stop (2 sigma), hold=8/10 ===")
for hold in [8, 10]:
    p, y = run(hold, 'decel', use_stop=True)
    report(f"hold={hold} decel+stop", p, y)

# placebo: same rule on random years shuffle is meaningless here; instead placebo = trend UP & high vol (should be bad per phase17-D)
print("\n=== placebo: trend UP & vol>=q75 (phase17-D said this is the BUST zone, expect ~0/negative) ===")
pnl, yy = [], []
i = W + 100
hold = 10
while i < len(r) - hold:
    hist = vols[W:i]
    q75 = np.nanquantile(hist, 0.75)
    if trends[i] > 0 and vols[i] >= q75:
        e_idx = i + 1; x_idx = min(e_idx + hold, len(c)-1)
        pnl.append(c[x_idx] - c[e_idx] - SPREAD)
        yy.append(years[e_idx]); i += hold
    else:
        i += 1
report("UP+highvol long", pnl, yy)
