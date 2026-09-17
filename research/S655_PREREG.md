# S655 PREREG — NFP Announcement-Bar Informed Continuation (XAUUSD, M1…D1)

**Scientist:** Ramanujan (block S650–S659, #6 of 10) · **Protocol:** Path A — zero free parameters, one decisive run on the FULL 15.6-year `data/mt5_full` data; no exploration phase (nothing is searched); engine `split_bar = 0.70·len` handles H-gate stability as in S382/S547.
**Status:** LOCKED before any PnL number. No script exists yet.
**Engine:** RQS2 v2.6 `compute_rqs2` — verdict only from the engine. Exploration only — nothing is deployed to the site.

## 1. Virginity census (before design)
- `grep -il "NFP|payroll|non-farm|first friday" results/S*rqs2*.md` → only S311 (pre-RQS2, INCOMPLETE, never adjudicated) and S312 (mid-month drift, unrelated). Zero RQS2-era layers on the announcement bar itself.
- All living gold ACCEPTs are *endogenous* shocks (range/z/jump/record). S655 is the first **exogenous, scheduled** shock in the RQS2 era. Calendar ACCEPTs (S547 pre-holiday, S312 mid-month) are drifts, not announcement reactions.

## 2. Hypothesis (Ederington–Lee 1993; Andersen–Bollerslev 1998; Kyle 1985)
Scheduled macro news is incorporated in two phases: an immediate jump and a slower drift while the information is digested. On gold, the US payroll release is the most price-relevant scheduled announcement. The **direction of the bar that contains the release**, when that bar is *informed* (retention ρ ≥ 0.618 — S965 law), should continue over the next 16 bars.

Event (per TF): the bar `t` whose interval `[time_t, time_t + TF)` contains the release instant **08:30 America/New_York** on the release day (DST via zoneinfo; server = UTC verified: D1 bars at 00:00, week opens Monday 00:00).
Release-day rule (mechanical, external, not tuned): first Friday of the month; if that Friday is a US federal holiday → the preceding Thursday. Known imperfection: BLS occasionally shifts to another day (e.g. 2 Jul 2020); such months contribute a non-announcement bar = noise dilution, not bias. Disclosed; not corrected post hoc.
Direction: follow the body of bar `t` (close>open → LONG, close<open → SHORT). Arms:
- **RHO (primary):** `ρ = |close−open|/(high−low) ≥ 0.618` on bar t.
- **ALL (control for P1):** no ρ filter.
Entry: open of bar `t+1`. Geometry in units of the announcement bar's own range `R = high_t − low_t` (self-scaling, φ-based, frozen): `SL = 0.618·R`, `TP = 1.000·R` (RR 1.618, TP>SL ✓), `max_hold = 16`, `allow_overlap=False`, spread 3.3 pip. No other parameters exist.
Null: K=600 subsets of unconditional bars with the **same rule** (SL=0.618·R_bar, TP=1.0·R_bar, hold 16), `select_non_overlap`, per side; SEED = 655655.
TFs: M1, M3, M4, M5, M6, M10, M12, M15, M20, M30, H1, H2, H3, H6, H8, H12, D1. W1/MN1: N/A.
n_trials passed to engine = **34** (17 TFs × 2 arms — every engine call counted).

## 3. Falsifiable predictions (before any number)
- **P0 (blind sanity, computed BEFORE any PnL, reported regardless):** median `R/ATR21[t−1]` of schedule bars on M15 ≥ 2.0 — proves the schedule lands on the shock. If < 1.5 the calendar is wrong ⇒ INCOMPLETE, no PnL claimed.
- **P1 (informed > all):** on every TF with n ≥ 30 in both arms, lift(RHO) > lift(ALL). If not on ≥ 60 % of such TFs, the S965 retention law does not transfer to exogenous shocks — reported as a falsification.
- **P2 (primary verdict, pessimistic):** best card ≤ POWER-LIMITED. n ≈ 180 per TF (≈110–140 in RHO arm); H3 needs z ≥ 3.09 ⇒ lift ≳ +14 pp at n≈120. Honest expectation: M1–M5 REJECT (post-spike mean reversion — S652/S653 lesson), M15–H1 POWER-LIMITED/UNPROVEN, H6+ REJECT (bar too wide).
- **P3 (pool clause):** ≥ 2 co-directional POWER-LIMITED cards ⇒ pool addendum permitted (separate file); otherwise none.
- All-REJECT ⇒ layer dead, lesson: "the payroll jump is fully priced within the announcement bar; no bar-scale drift".

## 4. Protocol constants
| item | value |
|---|---|
| data | `data/mt5_full/XAUUSD_<TF>.csv`, full span, `assert 'mt5_full' in src` |
| tz | 08:30 `America/New_York` → UTC via zoneinfo |
| seed / K | 655655 / 600 |
| n_trials | 34 |
| split_bar | 0.70·len(df) |
| result file | `results/S655_NfpAnnouncementBarContinuation_Xauusd_M1toD1_rqs2_<best>_<verdict>.md` |
| artifacts | `results/_scan_S655/final_<TF>.json` (both arms), committed + pushed per TF |

## 5. Eight common mistakes
1. Look-ahead: direction/ρ of bar t known at its close; entry t+1 open. 2. No hold-out contamination: no search. 3. No tuning: all constants φ-based/inherited, written here first. 4. Engine-only verdict. 5. n_trials = every engine call. 6. All 17 TFs, both arms published. 7. mt5_full guard. 8. No overlap; non-overlapping null. Calendar imperfection disclosed.

*Ramanujan — S655 — committed before `strategies/s655_nfp_final.py` exists.*
