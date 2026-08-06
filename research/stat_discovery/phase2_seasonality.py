#!/usr/bin/env python3
"""
Phase 2: Intraday & weekly seasonality on XAUUSD M15
- Volatility by hour of day (UTC)
- Directional drift by hour of day
- Day-of-week effects
- Hour x Day interaction hot spots
"""
import csv, math, statistics
from collections import defaultdict
from datetime import datetime, timezone

PATH = "/home/user/webapp/data/XAUUSD_M15.csv"

rows = []
with open(PATH) as f:
    r = csv.reader(f)
    next(r)
    for line in r:
        rows.append((int(line[0]), float(line[1]), float(line[2]), float(line[3]), float(line[4]), float(line[5])))

n = len(rows)
closes = [x[4] for x in rows]
rets = []
for i in range(1, n):
    t = rows[i][0]
    dt = datetime.fromtimestamp(t, tz=timezone.utc)
    r_ = math.log(closes[i]/closes[i-1])
    rng = (rows[i][2]-rows[i][3])/closes[i]  # bar range normalized
    rets.append((dt, r_, rng))

sd_all = statistics.pstdev([x[1] for x in rets])

# --- By hour of day ---
by_hour = defaultdict(list)
for dt, r_, rng in rets:
    by_hour[dt.hour].append((r_, rng))

print("HOUR-OF-DAY (UTC): n, mean_ret(sd units *1000), sd_ret(rel to overall), mean_range(bp), P(up)")
for h in range(24):
    v = by_hour[h]
    if not v: continue
    rs = [x[0] for x in v]
    rngs = [x[1] for x in v]
    m = statistics.mean(rs)
    s = statistics.pstdev(rs)
    pup = sum(1 for x in rs if x > 0)/len(rs)
    se = statistics.pstdev(rs)/math.sqrt(len(rs))
    tstat = m/se if se > 0 else 0
    print(f"  h={h:02d}: n={len(v):6d} drift={m/sd_all*1000:+7.1f} t={tstat:+5.2f} vol={s/sd_all:5.2f}x range={statistics.mean(rngs)*10000:5.1f}bp P(up)={pup:.3f}")

# --- By day of week ---
by_dow = defaultdict(list)
for dt, r_, rng in rets:
    by_dow[dt.weekday()].append(r_)
days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
print("\nDAY-OF-WEEK: n, total drift per day (sd units), t-stat, P(up)")
for d in range(7):
    v = by_dow[d]
    if not v: continue
    m = statistics.mean(v)
    se = statistics.pstdev(v)/math.sqrt(len(v))
    pup = sum(1 for x in v if x > 0)/len(v)
    print(f"  {days[d]}: n={len(v):6d} drift/bar={m/sd_all*1000:+7.1f} t={m/se:+5.2f} P(up)={pup:.3f}")

# --- Hour x DOW hotspots (only cells with |t| > 2.5) ---
by_cell = defaultdict(list)
for dt, r_, rng in rets:
    by_cell[(dt.weekday(), dt.hour)].append(r_)
print("\nHOTSPOTS (DOWxHOUR with |t|>2.5):")
hot = []
for (d, h), v in sorted(by_cell.items()):
    if len(v) < 200: continue
    m = statistics.mean(v)
    se = statistics.pstdev(v)/math.sqrt(len(v))
    t = m/se if se > 0 else 0
    if abs(t) > 2.5:
        hot.append((t, d, h, len(v), m))
for t, d, h, cnt, m in sorted(hot, key=lambda x: -abs(x[0])):
    print(f"  {days[d]} h={h:02d}: n={cnt} drift={m/sd_all*1000:+7.1f}(sd/1000) t={t:+5.2f}")

# --- volatility signature: first hour of each session ---
# London open ~ 07-08 UTC, NY open ~ 13-14 UTC (varies with DST)
print("\nRANGE EXPANSION: ratio of hour range to daily avg (find session opens)")
hr_range = {}
for h in range(24):
    v = by_hour[h]
    if v:
        hr_range[h] = statistics.mean([x[1] for x in v])
avg = statistics.mean(hr_range.values())
for h in range(24):
    if h in hr_range:
        bar = "#" * int(hr_range[h]/avg*20)
        print(f"  h={h:02d}: {hr_range[h]/avg:5.2f}x {bar}")
