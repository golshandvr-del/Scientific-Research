#!/usr/bin/env python3
"""
Phase 3: Validate 3 candidate edges on XAUUSD M15 WITH REAL COSTS
Account specs: spread = 0.33 $/oz round-trip cost per trade
Edge candidates:
  A) FADE large bars: after |ret|>3sd bar, enter opposite direction, hold N bars
  B) ASIA DRIFT: buy at 01:00 UTC, hold the hour (4 bars)
  C) DOWN-STREAK BOUNCE: after k>=3 consecutive down bars, buy, hold N bars
Each tested with simple hold-N exit (no TP/SL yet) to measure RAW EDGE vs COST.
Also out-of-sample split: first 70% train, last 30% test.
"""
import csv, math, statistics
from datetime import datetime, timezone

PATH = "/home/user/webapp/data/XAUUSD_M15.csv"
SPREAD = 0.33  # $/oz total cost per round trip

rows = []
with open(PATH) as f:
    r = csv.reader(f)
    next(r)
    for line in r:
        rows.append((int(line[0]), float(line[1]), float(line[2]), float(line[3]), float(line[4])))

n = len(rows)
closes = [x[4] for x in rows]
opens = [x[1] for x in rows]
rets = [math.log(closes[i]/closes[i-1]) for i in range(1, n)]
mu = statistics.mean(rets); sd = statistics.pstdev(rets)

split = int(n*0.7)

def simulate(signals, hold):
    """signals: list of (bar_index, direction +1/-1). Enter at OPEN of bar_index+1, exit at close of bar_index+hold.
    Returns list of $ P&L per oz including spread."""
    pnls = []
    for i, d in signals:
        ei = i + 1          # entry bar
        xi = i + hold       # exit bar
        if xi >= n: continue
        entry = opens[ei]
        exitp = closes[xi]
        pnl = (exitp - entry) * d - SPREAD
        pnls.append((i, pnl))
    return pnls

def report(name, pnls, hold):
    if len(pnls) < 30:
        print(f"  {name}: n={len(pnls)} TOO FEW")
        return
    vals = [p for _, p in pnls]
    tr_vals = [p for i, p in pnls if i < split]
    te_vals = [p for i, p in pnls if i >= split]
    net = sum(vals); wr = sum(1 for v in vals if v > 0)/len(vals)
    avg = statistics.mean(vals)
    se = statistics.pstdev(vals)/math.sqrt(len(vals))
    t = avg/se if se > 0 else 0
    tr = f"IS n={len(tr_vals)} net={sum(tr_vals):+.0f} avg={statistics.mean(tr_vals):+.3f}" if tr_vals else "IS empty"
    te = f"OOS n={len(te_vals)} net={sum(te_vals):+.0f} avg={statistics.mean(te_vals):+.3f}" if te_vals else "OOS empty"
    print(f"  {name} hold={hold}: n={len(vals)} NET=${net:+.0f}/oz avg=${avg:+.3f} WR={wr:.3f} t={t:+.2f} | {tr} | {te}")

# ---- Edge A: fade large bars ----
print("=== EDGE A: FADE LARGE BARS (enter opposite after |ret|>k*sd) ===")
for k in [2.5, 3, 4]:
    sigs = []
    for i in range(1, len(rets)):
        if abs(rets[i]-mu) > k*sd:
            d = -1 if rets[i] > 0 else 1
            sigs.append((i+1, d))  # rets[i] corresponds to bar i+1 close... bar index = i+1? closes[i+1]/closes[i] -> rets index i means bar i+1
    # NOTE: rets[j] = log(closes[j+1]/closes[j]) with j from 0; bar of rets[j] is j+1
    for hold in [1, 2, 4, 8]:
        report(f"k={k}", simulate(sigs, hold), hold)

# ---- Edge B: Asia drift buy 01:00 UTC ----
print("\n=== EDGE B: ASIA DRIFT (buy at start of hour block, hold) ===")
for hour in [1]:
    for dows in [None, {1,3}, {1,2,3,4}]:  # all days, Tue+Thu only, Tue-Fri
        sigs = []
        for i in range(n):
            dt = datetime.fromtimestamp(rows[i][0], tz=timezone.utc)
            if dt.hour == hour and dt.minute == 0:
                if dows is None or dt.weekday() in dows:
                    sigs.append((i-1, 1))  # enter at open of bar i (i-1+1)
        label = f"h={hour:02d} dows={sorted(dows) if dows else 'all'}"
        for hold in [2, 4, 8]:
            report(label, simulate(sigs, hold), hold)

# ---- Edge C: down-streak bounce ----
print("\n=== EDGE C: DOWN-STREAK BOUNCE (buy after k consecutive down bars) ===")
dirs = [1 if r > 0 else (-1 if r < 0 else 0) for r in rets]
for k in [3, 4, 5, 6]:
    sigs = []
    run = 0; prev = 0
    for j in range(len(dirs)):
        d = dirs[j]
        if d == prev and d != 0: run += 1
        elif d != 0: run = 1
        else: run = 0
        prev = d
        if run == k and d == -1:
            sigs.append((j+1, 1))
    for hold in [1, 2, 4, 8]:
        report(f"k={k}", simulate(sigs, hold), hold)

# ---- Edge C2: down-streak with magnitude filter (total drop > X sd) ----
print("\n=== EDGE C2: DOWN-STREAK + MAGNITUDE (k>=3 downs AND total drop > m*sd) ===")
for k in [3, 4]:
    for m in [3, 5]:
        sigs = []
        run = 0; prev = 0; acc = 0.0
        for j in range(len(dirs)):
            d = dirs[j]
            if d == prev and d != 0:
                run += 1; acc += rets[j]
            elif d != 0:
                run = 1; acc = rets[j]
            else:
                run = 0; acc = 0
            prev = d
            if run >= k and d == -1 and abs(acc) > m*sd:
                sigs.append((j+1, 1))
                run = 0; acc = 0  # avoid immediate re-entry
        for hold in [2, 4, 8]:
            report(f"k={k} m={m}", simulate(sigs, hold), hold)
