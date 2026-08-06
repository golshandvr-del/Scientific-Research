#!/usr/bin/env python3
"""
Phase 4: Deep robustness test of ASIA DRIFT edge (buy 01:00 UTC) on XAUUSD M15
1) Year-by-year stability (the essence of consistency/rqs2 thinking)
2) Sensitivity to entry hour (00,01,02) - is 01 special or artifact?
3) Add realistic TP/SL variants vs pure time exit
4) Max drawdown & profit factor per year
Costs: spread 0.33 $/oz per round trip.
"""
import csv, math, statistics
from collections import defaultdict
from datetime import datetime, timezone

PATH = "/home/user/webapp/data/XAUUSD_M15.csv"
SPREAD = 0.33

rows = []
with open(PATH) as f:
    r = csv.reader(f)
    next(r)
    for line in r:
        rows.append((int(line[0]), float(line[1]), float(line[2]), float(line[3]), float(line[4])))
n = len(rows)

def trades_time_exit(hour, hold, dows=None):
    """Enter long at open of first bar of given hour, exit at close after `hold` bars."""
    out = []
    for i in range(n - hold - 1):
        dt = datetime.fromtimestamp(rows[i][0], tz=timezone.utc)
        if dt.hour == hour and dt.minute == 0 and (dows is None or dt.weekday() in dows):
            entry = rows[i][1]  # open of the 01:00 bar itself
            exitp = rows[i + hold - 1][4]  # close of bar i+hold-1 (hold bars total)
            pnl = exitp - entry - SPREAD
            out.append((dt, pnl))
    return out

def trades_tpsl(hour, tp, sl, max_hold, dows=None):
    """Enter long at open of 01:00 bar; TP/SL in $; time-stop after max_hold bars."""
    out = []
    for i in range(n - max_hold - 2):
        dt = datetime.fromtimestamp(rows[i][0], tz=timezone.utc)
        if dt.hour == hour and dt.minute == 0 and (dows is None or dt.weekday() in dows):
            entry = rows[i][1]
            pnl = None
            for j in range(i, i + max_hold):
                hi = rows[j][2]; lo = rows[j][3]
                # conservative: SL checked first within a bar
                if lo <= entry - sl:
                    pnl = -sl - SPREAD; break
                if hi >= entry + tp:
                    pnl = tp - SPREAD; break
            if pnl is None:
                pnl = rows[i + max_hold - 1][4] - entry - SPREAD
            out.append((dt, pnl))
    return out

def yearly_report(name, trades):
    by_year = defaultdict(list)
    for dt, pnl in trades:
        by_year[dt.year].append(pnl)
    print(f"\n--- {name} (total n={len(trades)}) ---")
    total_net = 0; pos_years = 0; tot_years = 0
    for y in sorted(by_year):
        v = by_year[y]
        net = sum(v); wr = sum(1 for x in v if x > 0)/len(v)
        gp = sum(x for x in v if x > 0); gl = -sum(x for x in v if x < 0)
        pf = gp/gl if gl > 0 else float('inf')
        # max drawdown on cumulative
        cum = 0; peak = 0; mdd = 0
        for x in v:
            cum += x
            peak = max(peak, cum)
            mdd = max(mdd, peak - cum)
        total_net += net; tot_years += 1
        if net > 0: pos_years += 1
        print(f"  {y}: n={len(v):4d} net=${net:+8.1f} avg=${net/len(v):+.3f} WR={wr:.3f} PF={pf:.2f} MDD=${mdd:.1f}")
    all_v = [p for _, p in trades]
    avg = statistics.mean(all_v)
    se = statistics.pstdev(all_v)/math.sqrt(len(all_v))
    print(f"  TOTAL: net=${total_net:+.1f} avg=${avg:+.3f} t={avg/se:+.2f} POSITIVE_YEARS={pos_years}/{tot_years}")
    return pos_years, tot_years, total_net

# 1) hour sensitivity with pure time exit hold=8 (2 hours)
print("======== HOUR SENSITIVITY (time exit, hold=8 bars = 2h, Tue-Fri) ========")
for h in [0, 1, 2, 3]:
    tr = trades_time_exit(h, 8, dows={1,2,3,4})
    if tr:
        v = [p for _, p in tr]
        avg = statistics.mean(v); se = statistics.pstdev(v)/math.sqrt(len(v))
        print(f"h={h:02d}: n={len(v)} net=${sum(v):+.0f} avg=${avg:+.3f} t={avg/se:+.2f}")

# 2) yearly stability for the main candidates
print("\n======== YEARLY STABILITY ========")
yearly_report("BUY 01:00 hold=8 ALL DAYS", trades_time_exit(1, 8, None))
yearly_report("BUY 01:00 hold=8 Tue-Fri", trades_time_exit(1, 8, {1,2,3,4}))
yearly_report("BUY 01:00 hold=4 Tue-Fri", trades_time_exit(1, 4, {1,2,3,4}))

# 3) TP/SL variants (asymmetric, SL > TP forbidden-check: use SL >= TP to keep WR honest)
print("\n======== TP/SL VARIANTS (Tue-Fri, max_hold=8) ========")
for tp, sl in [(3, 3), (4, 4), (5, 5), (6, 4), (8, 5)]:
    tr = trades_tpsl(1, tp, sl, 8, dows={1,2,3,4})
    v = [p for _, p in tr]
    if v:
        avg = statistics.mean(v); se = statistics.pstdev(v)/math.sqrt(len(v))
        wr = sum(1 for x in v if x > 0)/len(v)
        print(f"TP={tp} SL={sl}: n={len(v)} net=${sum(v):+.0f} avg=${avg:+.3f} WR={wr:.3f} t={avg/se:+.2f}")
