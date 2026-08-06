#!/usr/bin/env python3
"""
Phase 8: ANATOMY OF GOLD'S RISE — where does the drift actually live?
Gold went ~$1620 -> ~$4170 over the sample (+157%). Decompose the TOTAL
cumulative gain into hour-of-day buckets: if you only held gold during
hour H (every day, all 6.5 years), how much of the total move did you get?

This is the deepest structural question: drift is not uniform in time.
Also: overnight (Asia 0-7 UTC) vs London (7-13) vs NY (13-21) vs late (21-24).
And: interaction of the 01:00 drift with volatility regime and with
the previous day's direction (conditional drift).
"""
import numpy as np, pandas as pd, math, datetime

df = pd.read_csv('data/XAUUSD_M15.csv')
t, o, c = df.time.values, df.open.values, df.close.values
n = len(c)
dt = [datetime.datetime.fromtimestamp(x, datetime.timezone.utc) for x in t]
hours = np.array([d.hour for d in dt])
dows = np.array([d.weekday() for d in dt])
years = np.array([d.year for d in dt])
r = np.diff(c)                      # $ move per bar (close-to-close)
hr_r = hours[1:]                    # hour of the bar whose close ends the move
yr_r = years[1:]

total = c[-1] - c[0]
print(f"TOTAL move over sample: ${total:+.0f}  ({c[0]:.0f} -> {c[-1]:.0f})")

print("\n=== cumulative $ gain by hour-of-day (hold only that hour, all years) ===")
gains = {}
for hh in range(24):
    g = r[hr_r == hh].sum()
    gains[hh] = g
srt = sorted(gains.items(), key=lambda kv: -kv[1])
for hh, g in srt:
    bar = "#" * max(0, int(abs(g)/40))
    sign = "+" if g >= 0 else "-"
    print(f"  h={hh:02d}: ${g:+7.0f}  {sign}{bar}")

print("\n=== session decomposition ===")
sessions = {"Asia 00-07": range(0,7), "London 07-13": range(7,13),
            "NY 13-21": range(13,21), "Late 21-24": range(21,24)}
for name, rng in sessions.items():
    g = r[np.isin(hr_r, list(rng))].sum()
    print(f"  {name:14s}: ${g:+7.0f}  ({100*g/total:+.0f}% of total move)")

print("\n=== hour-drift stability across years (top-3 hours) ===")
top3 = [hh for hh, _ in srt[:3]]
for hh in top3:
    ys = " ".join(f"{y}:{r[(hr_r==hh)&(yr_r==y)].sum():+.0f}" for y in sorted(set(yr_r)))
    pos = sum(1 for y in set(yr_r) if r[(hr_r==hh)&(yr_r==y)].sum() > 0)
    print(f"  h={hh:02d}: {ys}  | +years {pos}/{len(set(yr_r))}")

print("\n=== per-bar mean by hour with t-stat (which hours have REAL drift?) ===")
for hh in range(24):
    v = r[hr_r == hh]
    if len(v) < 100: continue
    avg = v.mean(); se = v.std()/math.sqrt(len(v))
    t_ = avg/se
    flag = " <<<" if abs(t_) > 3 else (" <" if abs(t_) > 2 else "")
    print(f"  h={hh:02d}: n={len(v):5d} mean=${avg:+.4f} t={t_:+.2f}{flag}")

print("\n=== conditional drift: hour-1 drift GIVEN previous day's direction ===")
# previous day = last 96 bars ending at 00:00
day_key = np.array([d.date() for d in dt])
# build day closes
df2 = pd.DataFrame({'d': day_key, 'c': c})
day_close = df2.groupby('d')['c'].last()
day_ret = day_close.diff()
# for each bar at hour==1, previous day's return
mask_h1 = hours == 1
pnl_after_up, pnl_after_dn = [], []
dates = sorted(day_close.index)
dpos = {d:i for i, d in enumerate(dates)}
for i in np.where(mask_h1[:-9])[0]:
    d = day_key[i]
    j = dpos.get(d)
    if j is None or j < 1: continue
    prev = day_ret.iloc[j-1] if j-1 < len(day_ret) else np.nan
    if np.isnan(prev): continue
    move = c[i+8] - c[i]   # hold 2 hours from 01:00 bar
    (pnl_after_up if prev > 0 else pnl_after_dn).append(move)
for tag, v in [("prev day UP", pnl_after_up), ("prev day DOWN", pnl_after_dn)]:
    v = np.array(v)
    se = v.std()/math.sqrt(len(v))
    print(f"  {tag}: n={len(v)} mean=${v.mean():+.3f} t={v.mean()/se:+.2f} sum=${v.sum():+.0f}")
