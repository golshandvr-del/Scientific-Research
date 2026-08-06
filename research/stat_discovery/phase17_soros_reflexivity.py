#!/usr/bin/env python3
"""
Phase 17: SOROS I -- REFLEXIVITY & BOOM-BUST ANATOMY on XAUUSD (daily, built from M15)
Questions (Soros-style):
  A) Does a trend feed on itself? (daily momentum: after k same-sign days)
  B) Parabolic acceleration: when a trend accelerates, is it near exhaustion? (reflexive climax)
  C) Drawdown anatomy: boom-bust asymmetry -- decline speed vs recovery speed
  D) Vol-trend feedback loop: does a strong trend BREED volatility (reflexivity signature)?
"""
import pandas as pd, numpy as np, math

df = pd.read_csv('data/XAUUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
df['date'] = df['dt'].dt.date
g = df.groupby('date')
daily = pd.DataFrame({'o': g['open'].first(), 'h': g['high'].max(),
                      'l': g['low'].min(), 'c': g['close'].last(), 'n': g['close'].size()})
daily = daily[daily.n >= 40].copy()
c = daily.c.values
rv = np.diff(np.log(c))
sgn = np.sign(rv)
print(f"days={len(c)}  mean_daily={rv.mean()*100:+.3f}%  sd={rv.std()*100:.3f}%  P(up)={(rv>0).mean():.3f}")

# ---------- A: daily momentum after k consecutive same-sign days ----------
print("\n=== A: after EXACTLY k consecutive same-sign days -> next day ===")
runs = np.zeros(len(sgn), int)
for i in range(len(sgn)):
    if sgn[i] == 0: runs[i] = 0
    elif i > 0 and sgn[i] == sgn[i-1]: runs[i] = runs[i-1] + 1
    else: runs[i] = 1
for d, lab in [(1, 'UP'), (-1, 'DOWN')]:
    for k in range(1, 7):
        m = (sgn[:-1] == d) & (runs[:-1] == k)
        if m.sum() < 25: continue
        nxt = rv[1:][m]
        se = nxt.std()/math.sqrt(len(nxt))
        print(f"  {lab:4s} run={k}: n={m.sum():4d}  P(next up)={(nxt>0).mean():.3f}  "
              f"E[next]={nxt.mean()*100:+.3f}%  t={nxt.mean()/se:+.2f}")

# ---------- B: reflexive acceleration (parabolic climax) ----------
print("\n=== B: inside an up-run>=3: is TODAY parabolic (ret>1.5x mean of prev 2 run-days)? ===")
for d, lab in [(1, 'UP-run'), (-1, 'DOWN-run')]:
    acc, norm = [], []
    for i in range(2, len(rv)-1):
        if runs[i] >= 3 and sgn[i] == d:
            prev_mean = np.mean(np.abs(rv[i-2:i]))
            if prev_mean > 0 and abs(rv[i]) > 1.5*prev_mean:
                acc.append(rv[i+1])
            else:
                norm.append(rv[i+1])
    for tag, v in [('parabolic', acc), ('steady   ', norm)]:
        v = np.array(v)
        if len(v) < 15: continue
        se = v.std()/math.sqrt(len(v))
        print(f"  {lab} {tag}: n={len(v):4d}  E[next]={v.mean()*100:+.3f}%  "
              f"P(up)={(v>0).mean():.3f}  t={v.mean()/se:+.2f}")

# ---------- C: drawdown anatomy (boom-bust asymmetry) ----------
print("\n=== C: drawdown episodes (depth >= 3% from running max) ===")
runmax = np.maximum.accumulate(c)
dd = (c - runmax)/runmax
episodes = []
i = 0
while i < len(c):
    if dd[i] < -0.03:
        peak = i
        while peak > 0 and dd[peak-1] < 0: peak -= 1
        peak = max(peak-1, 0)
        j = i
        trough = i
        while j < len(c) and dd[j] < 0:
            if dd[j] < dd[trough]: trough = j
            j += 1
        episodes.append((peak, trough, min(j, len(c)-1), dd[trough]))
        i = j
    else:
        i += 1
dec = [t-p for p, t, e, d_ in episodes]
rec = [e-t for p, t, e, d_ in episodes if dd[e] >= 0 or e < len(c)-1]
dep = [d_ for _, _, _, d_ in episodes]
print(f"  episodes={len(episodes)}  median depth={np.median(dep)*100:.1f}%  max depth={min(dep)*100:.1f}%")
print(f"  median decline={np.median(dec):.0f} days  vs  median recovery={np.median(rec):.0f} days"
      f"  -> bust/boom speed ratio={np.median(rec)/max(np.median(dec),1):.2f}x")
up_days = rv[rv > 0]; dn_days = rv[rv < 0]
print(f"  up-day mean=+{up_days.mean()*100:.3f}%  down-day mean={dn_days.mean()*100:.3f}%  "
      f"|down|/up={abs(dn_days.mean())/up_days.mean():.2f}  count up/down={len(up_days)}/{len(dn_days)}")

# ---------- D: vol-trend feedback (reflexivity signature) ----------
print("\n=== D: reflexivity loop: 5d trend strength -> NEXT 5d volatility, and vice versa ===")
w = 5
s = pd.Series(rv)
trend = s.rolling(w).sum()
vol = s.rolling(w).std()
fwd_vol = vol.shift(-w)
fwd_ret = trend.shift(-w)
msk = trend.notna() & fwd_vol.notna()
rc1 = pd.Series(np.abs(trend[msk])).rank().corr(pd.Series(fwd_vol[msk]).rank())
rc2 = pd.Series(vol[msk]).rank().corr(pd.Series(np.abs(fwd_ret[msk])).rank())
print(f"  rank-corr(|trend_5d|, fwd vol_5d) = {rc1:+.3f}   (trend breeds vol?)")
print(f"  rank-corr(vol_5d, |fwd ret_5d|)  = {rc2:+.3f}   (vol breeds trend?)")
print("\n  bucket: trend sign x vol quartile -> E[next 5d ret]")
vq = pd.qcut(vol[msk], 4, labels=False)
tt = trend[msk]; fr = fwd_ret[msk]
for sgn_lab, cond in [('UP  ', tt > 0), ('DOWN', tt < 0)]:
    for q in range(4):
        m2 = cond & (vq == q)
        v = fr[m2].dropna().values
        if len(v) < 25: continue
        se = v.std()/math.sqrt(len(v))
        print(f"    trend {sgn_lab} volQ{q+1}: n={len(v):4d}  E[fwd 5d]={v.mean()*100:+.3f}%  t={v.mean()/se:+.2f}")
