# S516 — VTIME + Drift-Alignment Filter — XAUUSD M30 — REJECT (by identity test, no adjudication spent)

**Scientist territory**: S510–S519 · **Layer**: S516 · **Date**: 2026-08-24
**Prereg**: `results/S516_PREREG_M30_VTIME_DRIFTALIGN.md` (pushed BEFORE any test) · SEED=20260822

## 1) Hypothesis (falsified)
Borrowing the trade-SELECTION lever (S562 double-ACCEPT) and drift-alignment precedent (S950 ACCEPT 80):
a causal momentum filter `close[t] > close[t-L]` on the frozen S515 V-TIME winner
(atr_fib_55↑q90 → LONG, hold k=4, symmetric q98 bracket=307.9pip) should remove
losing trades non-randomly and cure the single remaining disease (PF 1.255).

## 2) Pipeline results
### select (discovery 60% only, 4 trials L∈{13,34,89,233})
| L | retention | n | WR | net(pip×n) | t-stat | valid |
|---|---|---|---|---|---|---|
| base | 1.000 | 104 | 51.92% | +14.139 | +1.42 | — |
| 13 | 0.543 | 57 | 49.12% | +24.023 | +1.67 | ✓ |
| **34** | **0.533** | **56** | **53.57%** | **+33.994** | **+2.28** | **✓ WINNER** |
| 89 | 0.600 | 63 | 55.56% | +22.985 | +1.79 | ✓ |
| 233 | 0.543 | 56 | 60.71% | +22.514 | +1.58 | ✗ (both-halves rule) |

### identity test (EXACT p, K=1000, same-retention random subsampling — the S512 blade)
- obs_wr = 53.57% · random subsample: mean = 51.92%, p95 = 58.93%, max = 66.07%
- **P(rand ≥ obs) = 0.4140  →  FAIL (gate: ≤ 0.05)**

The drift filter's WR gain is fully reproducible by randomly deleting the same
fraction of trades. The filter carries **zero information** beyond count reduction.
Per prereg contingency: REJECT-by-identity — **no compute_rqs2 call was made**,
adjudication budget preserved.

## 3) Scientific findings (block laws)
1. **Drift-alignment does NOT transfer from jump events (S950, gold jumps) to
   vol-expansion events (S515, atr q90-cross).** The S515 entry is already a
   momentum-adjacent state; conditioning on past drift is nearly collinear with
   the entry condition → no incremental information. Lever taxonomy update:
   trade-selection filters must be *informationally orthogonal* to the entry signal,
   not merely "causal".
2. The exact-p identity test (forged in S512) has now killed two layers honestly.
   It is the cheapest veto in the block — always run it BEFORE spending null/judge.
3. Note the trap avoided: L=233 showed the prettiest WR (60.71%) but failed the
   both-halves rule; L=34 won by prereg t-stat rule and STILL failed identity.
   Selection rules + identity together prevented a garden-of-forking-paths accept.

## 4) Multiplicity ledger (Path C, cumulative block debt)
- S516 spent 4 trials (L grid), **no adjudication call**.
- Cumulative honest n_trials for the NEXT adjudication in this block: **5013**
  (5009 from S515 + 4 from S516).

## 5) Status of the S515 core signal
The V-TIME vol-event core (z=3.38, lift +8.74pp, OOS WR>disc WR) remains the
block's best asset. Diseases remaining: PF 1.255 (H1), z below luck bound 3.688 (H5).
Burned levers on this core: pnl-shape (S561 precedent), drift-alignment (S516).
Open levers: orthogonal-information trade selection (regime/session/exogenous state),
signal pooling to raise n and z-force (z ∝ lift×√n).

**VERDICT: REJECT** · file: `S516_VtimeDriftAlign_Xauusd_M30_rqs2_NA_REJECT.md`
