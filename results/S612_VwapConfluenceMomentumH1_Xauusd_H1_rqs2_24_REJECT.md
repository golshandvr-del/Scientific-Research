# S612 — VWAP Confluence Momentum — XAUUSD H1 — RQS2 v2.6 Adjudication of the S611 Lead

**Verdict: REJECT — score 24.3 / 100**
**Judge**: Évariste Galois (decade S610–S619)
**Date**: 2026-08-21 | **Prereg**: `results/S612_PREREG_VWAP_CONFLUENCE_H1_ADJUDICATION.md` (commit 3d446376, BEFORE any decisive H1 computation)
**Adjudicator**: `strategies/s612_vwap_h1_adjudicate.py` | **Evidence**: `results/_s612_vwap_h1/{h1_verdict.json, h1_trades.csv}`
**Lineage**: S153 (archive) → S611 (M5 REJECT 11.4, REGIME-ONLY #3) → S611 MTF table (H1 lead) → **S612 (this)**

---

## 1. What was judged

The single most promising row of the S611 19-TF table: frozen S153 rule on **XAUUSD H1**, 15.59y —
the only TF whose *first* half was the stronger half (WR 64.89 vs 62.78, both nets positive).
Zero search. Honest budget **n_trials = 250** (200 lineage + 19 MTF looks + 31 best-of-19 selection penalty).
K_PERM=500, seed=20260821, split=70%.

**Health gates (both PASSED):**
- A) Identity: n_trades = **1070** exactly (bit-identity with the logged S611 MTF row) ✅
- B) Vectorized outcome table bit-exact vs `simulate_trades` on H1 ✅

## 2. The decisive numbers

| Quantity | Value |
|---|---|
| n_trades | 1,070 |
| WR (strategy) | **63.74%** |
| net | +13,831.8 pip |
| **uncond WR (all eligible bars, same geometry)** | **62.61%** |
| **perm null: mean / sd / max (K=500, FIFO per perm)** | **62.54 / 1.497 / 67.28** |
| reference (max of uncond, perm_mean) | 62.61 |
| **lift over reference** | **+1.13 pp** |
| z vs perm null | ≈ 0.80 |
| p_emp | ~0.22 |

| Gate | Pass | Gate | Pass |
|---|---|---|---|
| H0 sanity | ✅ | H6 calendar | ✅ |
| H1 economics | ✅ | H7 cost realism | ✅ |
| H2 sample | ✅ | H8 regime | ❌ |
| H3 luck vs null | ❌ | H9 | ✅ |
| H4 holdout | ❌ | H10 | ✅ |
| H5 multiplicity | ❌ | | |

**Score 24.3 → REJECT.** 7/11 gates green, but the three that measure *skill above null* (H3/H4/H5) are all red.

## 3. Prereg settlement

| Prediction | Outcome |
|---|---|
| **P1**: perm null with trail=6/BE=6 geometry on secular-bull gold may itself hit WR ≈ 58–61; if perm_mean ≥ 60 the layer dies on lift | ✅ **EXACTLY CONFIRMED** — perm_mean = 62.54 (even above my range); lift +1.13pp << needed ≈ 3.72×1.497 ≈ 5.6pp |
| P2: pre-2023 stays net-positive (not REGIME-ONLY) | ✅ pre-2023: n=838, WR=65.39, **+8,376 pip**; every single year 2011–2025 net-positive |
| P3: PF risk in the 1.1–1.3 dead zone | ❌ (pleasant surprise) H1-gate economics passed |
| P4: needed lift ≈ +5.6pp at perm_sd≈1.5 | ✅ perm_sd = 1.497 — the power arithmetic was exact |

## 4. The scientific finding — the geometry IS the "edge"

This is the cleanest demonstration on this site of the **geometry-carries-the-WR illusion**:

- **Random long entries** on XAUUSD H1, with SL=80/TP=700/BE=6/trail=6/mh=48, win **62.5%** of the time.
- The VWAP-confluence signal wins 63.7% — a mere **+1.1pp of conditional information**.
- The +13.8k pip net and the beautiful year-by-year consistency (2011–2025 all green) belong to
  **{long-only + tight-trail geometry + gold's secular drift}**, not to the signal.

The S611 MTF monotone structure is now fully explained: as TF coarsens, the *unconditional* trail-geometry
WR rises (cost shrinks relative to bar range, drift per bar grows) — the signal was never adding much at
any TF. On M5 the null was 43.3 vs strategy 44.3 (+1.0pp); on H1 the null is 62.5 vs 63.7 (+1.1pp).
**The signal's conditional information is ≈ +1pp everywhere; only the backdrop changes.**

This echoes and reinforces the site laws from S532 («geometry is not the carrier of edge — the edge lives
in the event») and the S523 conditioned-null lesson: **a null that doesn't share the winner's geometry and
habitat is not a null.** WR without a geometry-matched null is meaningless.

## 5. Regime evidence (for the record)

pre-2023-09: n=838, WR=65.39, +8,376 pip | post: n=232, WR=57.76, +5,456 pip.
Yearly 2011–2025 all net-positive; 2026 partial (n=41, WR 31.7, +396).
The *portfolio behavior* is era-robust — but it is the geometry's behavior, reproducible with random entries.

## 6. Family closure (decade S610–S619)

- S611: M5 claim = REGIME-ONLY artifact → REJECT 11.4.
- S612: H1 habitat = geometry/drift artifact, signal info ≈ +1pp → REJECT 24.3.
- The two deaths are *different diseases*, and together they close the S153/VWAP-confluence family **for me**:
  the signal carries ≈+1pp conditional information at every TF, far below any honest multiplicity bar.
  No filter search can multiply information that isn't there (pip-edge law: filters select bars, they
  cannot create conditional information).
- **Eternal-death status of the family**: dead for this signal definition. A materially different VWAP
  construction (session-anchored, mean-reversion side, symmetric SHORT) would be a NEW hypothesis
  needing its own prereg — not a revival of this one.

## 7. Compliance

Prereg before decisive number ✅ | zero-search single pass ✅ | budget honest (250, incl. 19 looks +
best-of-19 penalty) ✅ | engine bit-exact validation ✅ | identity gate vs MTF row ✅ |
Multi-TF law: 19-TF table delivered in S611 ✅ | Overlap audit: N/A (REJECT) ✅ |
no interference with parallel decades ✅ | checkpoint commits ✅.

**Final: S612 = REJECT 24.3. The H1 lead was the geometry wearing the signal's clothes. VWAP-confluence family closed with a valuable methodological finding: on trail/BE long-only gold systems, ALWAYS price the null in the same geometry.**
