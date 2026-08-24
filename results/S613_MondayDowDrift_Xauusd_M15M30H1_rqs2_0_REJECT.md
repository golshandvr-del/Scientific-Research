# S613 — Monday Day-of-Week Drift (S140 lineage) — XAUUSD M15/M30/H1 — REJECT (honest death in exploration)

**Verdict: REJECT — score 0 (per prereg honest-death rule; holdout NEVER opened, second half stays VIRGIN)**
**Judge**: Évariste Galois (decade S610–S619)
**Date**: 2026-08-21 | **Prereg**: `results/S613_PREREG_MONDAY_DOW_DRIFT_FULLDATA.md` (commit 5caa6be4, BEFORE any computation)
**Explorer**: `strategies/s613_monday_drift.py` | **Evidence**: `results/_s613_monday/grid_first_half.json, decision.json`

---

## 1. What was tested

First RQS2 full-data judgment of the **day-of-week (Monday) calendar axis** on gold —
the last unjudged calendar dimension (mid-month ALIVE via S432 ACCEPT; hour-of-day DEAD via S434/S892).
Archive S140 claimed +$175,246 with Mon t=+6.11 (short window).

Frozen event: Monday, first hour-18 bar ⇒ LONG next open, 1/week.
Geometry: V-TIME symmetric SL=TP=k×ATR34, exit at window close (hour 22).
Locked 6-point grid, **first half only** (2011–2018, 397 Mondays): TF {M15,M30,H1} × k {1.272, 2.058}.
Null (S612 law — geometry & habitat matched): same-week non-Monday weekday permutation, K=1000, seed=20260823.

## 2. The result — all 6 points dead, and not merely weak: NEGATIVE

| TF | k | n | WR% | net (pip) | uncond (non-Mon) | perm_mean | lift (pp) | z |
|---|---|---|---|---|---|---|---|---|
| M15 | 1.272 | 397 | 41.31 | −2,351 | 49.21 | 49.08 | **−7.90** | **−3.77** |
| M15 | 2.058 | 397 | 39.80 | −2,544 | 47.95 | 47.73 | −8.15 | −3.71 |
| M30 | 1.272 | 397 | 42.57 | −1,806 | 48.64 | 48.29 | −6.07 | −2.80 |
| M30 | 2.058 | 397 | 42.57 | −1,680 | 46.75 | 46.46 | −4.18 | −1.91 |
| H1 | 1.272 | 395 | 42.53 | −1,382 | 44.72 | 44.68 | −2.19 | −1.03 |
| H1 | 2.058 | 395 | 42.03 | −2,022 | 44.59 | 44.56 | −2.57 | −1.26 |

**No point satisfies n≥150 ∧ net>0 ⇒ honest death per prereg §7. Holdout untouched.**

## 3. The finding — Monday 18h was ANTI-edge in the first era

- Monday-18h longs win **6–8pp LESS** than the identical trade on Tue–Fri at the same hour with the
  same geometry (M15 z = −3.77 — statistically significant in the WRONG direction).
- Archive S140's t=+6.11 was measured on the short window: this is now the **strongest E-16 exposure
  measured in my decade** — the "effect" was not merely inflated, it had the opposite sign pre-2019.
- P5 of the prereg anticipated exactly this exit: "if archive t was E-16 inflated, first-half exploration
  will show it ⇒ honest death without touching holdout." ✅
- P1/P2 falsified (no positive structural drift); P3/P4 moot.

## 4. Family-level law (calendar axes on gold, now complete)

| Axis | Status | Evidence |
|---|---|---|
| Mid-month (dom) | **ALIVE** | S312/S432 ACCEPT (parallel scientists' territory) |
| Turn-of-month | dead | S306 lineage judged in old paradigm; RQS2-era rejections |
| Hour-of-day | dead | S434 REJECT 19, S892 all-16-cards REJECT |
| **Day-of-week (Monday)** | **dead — ANTI-edge pre-2019** | **S613 (this)** |
| Calendar-event (fix/EOM) | dead | S430/S521/S551/S583 dilution family |

The only calendar information on gold that survives era-robust judgment is the **mid-month
institutional-flow window**. Weekday identity carries zero (actually negative) exploitable information.

## 5. Compliance

Prereg before any computation ✅ | first-half-only exploration, holdout virgin ✅ |
geometry-matched conditioned null (S612 law) ✅ | honest budget n_trials=600 (counted although never
consumed at holdout) ✅ | honest-death rule executed exactly as written ✅ | no interference ✅.

**Final: S613 = REJECT (honest death in exploration). The Monday effect on gold is an E-16 artifact with inverted sign in history. Calendar-axis map of gold is now complete: only mid-month lives.**
