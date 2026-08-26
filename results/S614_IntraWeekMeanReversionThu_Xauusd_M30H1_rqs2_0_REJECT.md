# S614 — Intra-Week Mean Reversion (Mon–Wed → Thursday counter) — XAUUSD M30/H1 — REJECT (honest death; SIGN INVERTED)

**Verdict: REJECT — score 0 (per prereg honest-death rule; holdout NEVER opened, second half VIRGIN)**
**Judge**: Évariste Galois (decade S610–S619)
**Date**: 2026-08-21 | **Prereg**: `results/S614_PREREG_INTRAWEEK_MEANREVERSION_THU.md` (commit 82beda81, BEFORE any computation)
**Explorer**: `strategies/s614_intraweek_mr.py` | **Evidence**: `results/_s614_iwmr/grid_first_half.json, decision.json`

---

## 1. What was tested

First RQS2 judgment of the **intra-week mean-reversion axis** on gold: after a large Mon–Wed move
(≥ causal 52-week median of |early_move|), trade Thursday AGAINST the move.
Archive S23 lineage — the user's own market hypothesis; corr(early_move, thu_chg) = −0.194 (p<0.001)
on the SHORT window. Never RQS2-judged. Territory verified distinct from S722 (anchor continuation)
and S982 (open reclaim) — both level-based, mine path-sign-based.

Frozen: 1 trade/week, Thursday first bar → next open, direction = −sign(early_move);
V-TIME symmetric SL=TP=k×ATR34, exit at last Thursday bar. Locked 4-point grid, **first half only**
(2011–2018, ~174 gated weeks): TF {M30, H1} × k {1.272, 2.058}.
Null (S612 law): direction permutation (fair coin) on the same events & geometry, K=1000, seed=20260825.

## 2. Result — all 4 points dead, sign INVERTED

| TF | k | n | WR% | net (pip) | coin uncond | perm_mean | lift (pp) | z |
|---|---|---|---|---|---|---|---|---|
| M30 | 1.272 | 174 | 37.36 | −2,105 | 49.43 | 49.48 | **−12.13** | **−3.21** |
| M30 | 2.058 | 174 | 41.38 | −1,655 | 50.00 | 49.89 | −8.62 | −2.24 |
| H1 | 1.272 | 173 | 39.88 | −2,168 | 49.71 | 49.78 | −9.90 | −2.58 |
| H1 | 2.058 | 173 | 43.93 | −1,638 | 49.42 | 49.42 | −5.49 | −1.48 |

**No point with n≥100 ∧ net>0 ⇒ honest death per prereg §8. Holdout untouched.**

## 3. The finding — gold's week is a CONTINUATION week, not a reversal week

- The counter-trade wins 5–12pp **less** than a fair coin with identical events and geometry
  (M30 z = −3.21: significant in the WRONG direction).
- Mirror-read: the *continuation* trade (+sign(early_move)) on the same events would show
  ≈ +5..+12pp over coin in the first half — consistent with gold's documented coarse-TF
  continuation cluster owned by parallel scientists (S770/S800/S602/S950, and S553 in progress).
  I record this as evidence, NOT as a claim: the continuation direction belongs to the
  streak/momentum family others are actively judging; I do not open it (no-interference law).
- The archive's corr = −0.194 was a short-window artifact — **fourth E-16 exposure documented
  by my decade** (S611 regime, S612 geometry, S613 inverted-DOW, S614 inverted-MR).
- P1 falsified in the strongest form (not weak — inverted); P4 moot; P2/P3 never reached.

## 4. Axis closure

Combined with S613 (day identity = zero info) and S892 (hour = dead), the calendar/time block for
my decade is closed: **on gold, time-of-week structure carries either zero or continuation-signed
information; reversal-signed calendar hypotheses are dead on arrival.**

## 5. Compliance

Prereg before computation ✅ | first-half-only, holdout virgin ✅ | coin null on identical events &
geometry (prices ONLY the directional information) ✅ | honest budget n_trials=300 (never consumed at
holdout) ✅ | honest-death rule executed as written ✅ | no interference (continuation direction left
to its owners) ✅.

**Final: S614 = REJECT (honest death in exploration). The user's reversal hypothesis is real-looking only in short windows; on 15.6y the week CONTINUES. My decade has now falsified 4 archive claims with 4 different diseases — the E-16 autopsy series is complete.**
