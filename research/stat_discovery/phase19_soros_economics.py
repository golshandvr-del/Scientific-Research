#!/usr/bin/env python3
"""
Phase 19: SOROS III -- ECONOMIC validation (spread=$0.33/oz) of phase17/18 candidates
  E1: QUIET-TREND RIDER  : 5d trend up & 5d vol NOT in top quartile -> long 5 days
  E2: CAPITULATION BUY   : 5d trend down & 5d vol in top quartile   -> long 5 days
  E3: EUR->XAU CATCH-UP  : EUR 1h move > +1sd, XAU flat -> long XAU 1h
All signals use ONLY past data (vol quartile threshold = expanding-window quantile).
IS = first 70%, OOS = last 30%. Yearly breakdown. Non-overlapping entries.
"""
import pandas as pd, numpy as np, math

SPREAD = 0.33

def report(tag, pnl, yrs):
    pnl = np.array(pnl); yrs = np.array(yrs)
    if len(pnl) < 20:
        print(f"  {tag}: n={len(pnl)} TOO FEW"); return
    se = pnl.std()/math.sqrt(len(pnl))
    cut = int(len(pnl)*0.7)
    is_, oos = pnl[:cut], pnl[cut:]
    ylist = []
    for y in sorted(set(yrs)):
        v = pnl[yrs == y]
        ylist.append(f"{y}:{v.sum():+.0f}")
    print(f"  {tag}: n={len(pnl)} NET=${pnl.sum():+.0f}/oz avg=${pnl.mean():+.3f} "
          f"WR={(pnl>0).mean():.3f} t={pnl.mean()/se:+.2f} | IS avg={is_.mean():+.3f} OOS avg={oos.mean():+.3f} "
          f"| +yrs={sum(1 for y in sorted(set(yrs)) if pnl[yrs==y].sum()>0)}/{len(set(yrs))}")
    print(f"      yearly: {' '.join(ylist)}")

# ---------------- daily data ----------------
df = pd.read_csv('data/XAUUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
df['date'] = df['dt'].dt.date
g = df.groupby('date')
daily = pd.DataFrame({'o': g['open'].first(), 'c': g['close'].last(), 'n': g['close'].size()})
daily = daily[daily.n >= 40]
c = daily.c.values; o = daily.o.values
years = np.array([d.year for d in daily.index])
r = np.diff(np.log(c))
W, H = 5, 5   # lookback window, holding days

print("=== E1: QUIET-TREND RIDER (long, causal vol quantile) ===")
print("=== E2: CAPITULATION BUY (long, causal vol quantile) ===")
for name, want_up, want_high_vol in [("E1 quiet-trend", True, False), ("E2 capitulation", False, True)]:
    pnl, yy = [], []
    i = W + 100  # need burn-in for expanding quantile
    vols = pd.Series(r).rolling(W).std().values
    trends = pd.Series(r).rolling(W).sum().values
    while i < len(r) - H:
        hist = vols[W:i]                     # past vol values only
        q75 = np.nanquantile(hist, 0.75)
        tr, vl = trends[i], vols[i]
        sig = (tr > 0 and vl < q75) if want_up and not want_high_vol else \
              (tr < 0 and vl >= q75)
        if sig:
            entry = c[i+1 - 1]               # r[i] uses c[i+1]; enter at close of that day = c[i+1]
            entry_idx = i + 1
            exit_idx = min(entry_idx + H, len(c)-1)
            pnl.append(c[exit_idx] - c[entry_idx] - SPREAD)
            yy.append(years[entry_idx])
            i += H                           # non-overlapping
        else:
            i += 1
    report(name, pnl, yy)

# ---------------- E3: EUR->XAU catch-up (M15) ----------------
print("\n=== E3: EUR->XAU 1h CATCH-UP (long XAU 1h, causal sd) ===")
xau = df.set_index('dt')[['close']].rename(columns={'close': 'x'})
eurdf = pd.read_csv('data/EURUSD_M15.csv')
eurdf['dt'] = pd.to_datetime(eurdf['time'], unit='s', utc=True)
eur = eurdf.set_index('dt')[['close']].rename(columns={'close': 'e'})
j = xau.join(eur, how='inner')
cx = j.x.values; ce = j.e.values
ts = j.index
rx = np.diff(np.log(cx)); re_ = np.diff(np.log(ce))
H4 = 4
eh = pd.Series(re_).rolling(H4).sum().values
xh = pd.Series(rx).rolling(H4).sum().values
# causal rolling sd (30 days = 2880 bars)
sde = pd.Series(re_).rolling(2880).std().values
sdx = pd.Series(rx).rolling(2880).std().values
yrs_bar = np.array([t.year for t in ts[1:]])
for tag, dirn in [("EUR up -> long XAU", 1), ("EUR dn -> short XAU", -1)]:
    pnl, yy = [], []
    i = 2880
    while i < len(rx) - H4:
        if np.isnan(eh[i]) or np.isnan(sde[i]): i += 1; continue
        se1 = sde[i]*math.sqrt(H4); sx1 = sdx[i]*math.sqrt(H4)
        sig = (eh[i] > se1 if dirn == 1 else eh[i] < -se1) and abs(xh[i]) < 0.25*sx1
        if sig:
            entry_idx = i + 1                # trade next bar open ~ close[i+1] proxy: use close-to-close
            exit_idx = min(entry_idx + H4, len(cx)-1)
            raw = (cx[exit_idx] - cx[entry_idx]) * dirn
            pnl.append(raw - SPREAD)
            yy.append(yrs_bar[i])
            i += H4
        else:
            i += 1
    report(tag, pnl, yy)

# ---------------- E1/E2 with management: exit-on-first-hour-low? quick TP/SL variants ----------------
print("\n=== E2 variants: capitulation with fixed horizons ===")
vols = pd.Series(r).rolling(W).std().values
trends = pd.Series(r).rolling(W).sum().values
for H2 in [1, 2, 3, 5, 8, 10]:
    pnl, yy = [], []
    i = W + 100
    while i < len(r) - H2:
        hist = vols[W:i]
        q75 = np.nanquantile(hist, 0.75)
        if trends[i] < 0 and vols[i] >= q75:
            entry_idx = i + 1
            exit_idx = min(entry_idx + H2, len(c)-1)
            pnl.append(c[exit_idx] - c[entry_idx] - SPREAD)
            yy.append(years[entry_idx])
            i += H2
        else:
            i += 1
    report(f"hold={H2}d", pnl, yy)
