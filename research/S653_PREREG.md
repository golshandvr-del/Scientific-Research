# S653 PREREG — Distributed Multi-Bar Shock Continuation (XAUUSD, all TFs)

**Scientist:** Ramanujan (block S650–S659) · **Protocol:** Path C (audit §6.2) · **Engine:** RQS2 v2.6
**Status:** LOCKED before any hold-out (second-half) number is computed.
**Data:** `data/mt5_full/XAUUSD_<TF>.csv` (E-16 guard: script asserts `'mt5_full' in src`).

## 1. Hypothesis

The 5 independent ACCEPTs in the database (S602, S604, S606, S770, S950, S965) all share one law:
*one large **single-bar** absolute shock in a coarse TF + continuation + TP ≥ SL*.
S653 asks the complementary question (Kyle 1985, gradual information incorporation):

> Does a shock of the same **total** size, but **distributed over k bars with no single dominant bar**,
> carry continuation too?

Event (long side, mirror for short), at bar t with `atr_ref = ATR21[t-k-1]` (strictly pre-window):
- `mv = close[t] - close[t-k]  >=  θ · atr_ref`  (total move)
- `max(range[t-k+1..t]) < 1.618 · atr_ref`  (NO single dominant bar — this is what makes S653 disjoint from the S60x/S96x family)
- state edge only (`state[t] & ~state[t-1]`) — fresh signal, no re-fire while the state persists.

Geometry frozen from the exploration script (not tuned on hold-out):
`SL = 1.272 · atr_ref`, `TP = 2.058 · atr_ref` (RR = 1.618), `max_hold = 16` bars, no overlapping trades.

## 2. Honest grid disclosure

- **Grid A** (k∈{3,5,8} × θ∈{2.618, 4.236}) was smoke-tested on H1 first half only: n ≤ 31 events — too sparse.
  Artifact kept: `results/_scan_S653/explore_H1_gridA_theta2618_4236.json`. Discarded for lack of power, **not** for direction of result.
- **Grid B** (k∈{3,5,8} × θ∈{1.618, 2.618}) = 6 combos per TF, run on first half of all 19 TFs.
  Selection rule fixed before looking: `best_by_zmin` = combo maximising min(z_long, z_short).
- Total search cost for the family: 6 combos × 17 usable TFs ≈ 102 looks on the first half; hold-out will be touched exactly once per TF.

## 3. Locked TF → (k, θ) table (from `results/_scan_S653/explore_<TF>.json`, first half only)

| TF | k | θ | n_L | lift_L | z_L | n_S | lift_S | z_S | z_min |
|---|---|---|---|---|---|---|---|---|---|
| M1 | 8 | 1.618 | 48523 | -0.68 | -3.23 | 49704 | -1.07 | -5.16 | -5.16 |
| M3 | 3 | 2.618 | 974 | -5.41 | -3.49 | 924 | -3.51 | -2.20 | -3.49 |
| M4 | 3 | 2.618 | 632 | -5.76 | -2.99 | 579 | -3.54 | -1.75 | -2.99 |
| M5 | 3 | 2.618 | 449 | -4.20 | -1.84 | 382 | -4.45 | -1.78 | -1.84 |
| M6 | 3 | 2.618 | 349 | -6.27 | -2.41 | 269 | -3.17 | -1.07 | -2.41 |
| M10 | 3 | 2.618 | 182 | -4.50 | -1.25 | 115 | -1.35 | -0.30 | -1.25 |
| M12 | 3 | 2.618 | 143 | -3.63 | -0.89 | 79 | -4.34 | -0.79 | -0.89 |
| M15 | 5 | 2.618 | 280 | -2.58 | -0.89 | 266 | -2.66 | -0.89 | -0.89 |
| M20 | 8 | 2.618 | 365 | -2.88 | -1.13 | 317 | +1.07 | +0.39 | -1.13 |
| M30 | 8 | 2.618 | 243 | -0.66 | -0.21 | 195 | -1.67 | -0.48 | -0.48 |
| H1 | 8 | 1.618 | 579 | +4.18 | +2.06 | 532 | +2.03 | +0.95 | +0.95 |
| H2 | 8 | 1.618 | 309 | +4.31 | +1.55 | 274 | +4.32 | +1.46 | +1.46 |
| H3 | 5 | 1.618 | 193 | +0.60 | +0.17 | 185 | +2.38 | +0.66 | +0.17 |
| H6 | 5 | 1.618 | 120 | -1.12 | -0.25 | 117 | +3.88 | +0.85 | -0.25 |
| H8 | 5 | 1.618 | 100 | +6.27 | +1.29 | 91 | +0.49 | +0.10 | +0.10 |
| H12 | 8 | 1.618 | 55 | +7.26 | +1.11 | 65 | +5.62 | +0.92 | +0.92 |
| D1 | 5 | 1.618 | 42 | +3.02 | +0.41 | 41 | +0.22 | +0.03 | +0.03 |
| W1 / MN1 | — | — | TOO_SHORT | | | | | | |

```python
LOCKED = {'M1': (8, 1.618), 'M3': (3, 2.618), 'M4': (3, 2.618), 'M5': (3, 2.618), 'M6': (3, 2.618),
          'M10': (3, 2.618), 'M12': (3, 2.618), 'M15': (5, 2.618), 'M20': (8, 2.618), 'M30': (8, 2.618),
          'H1': (8, 1.618), 'H2': (8, 1.618), 'H3': (5, 1.618), 'H6': (5, 1.618), 'H8': (5, 1.618),
          'H12': (8, 1.618), 'D1': (5, 1.618)}
```

## 4. Falsifiable predictions (written BEFORE the hold-out run)

- **P1 (primary, pessimistic):** all 17 TFs → **REJECT**. Max in-sample z is only +2.06 (H1 long) and z_luck_bound(n_trials=17) ≈ 2.7; the first half contains no cell that clears H3 (lift ≥ 4pp AND z ≥ 3.09) on both sides. Distributed shocks = *slow* information → already priced in by the time k bars have passed (efficient-market default). If P1 holds: **layer dead, no retuning**, lesson logged: "magnitude must be concentrated, not distributed".
- **P2 (structure):** z_min is monotone increasing from M1 → H2 (fine TFs mean-revert after a distributed move — S652 lesson — coarse TFs do not). Will be checked on the hold-out output.
- **P3 (pool clause):** only if ≥ 2 TFs come out POWER-LIMITED with co-directional lift, a pool rescue is allowed via a *separate* addendum + separate pool test; otherwise no pool.

## 5. Protocol constants

| item | value |
|---|---|
| hold-out | `df.iloc[half:]` per TF, touched once |
| SEED | 653653 |
| null model | K=600 unconditional same-geometry events, `select_non_overlap`, per side |
| n_trials passed to engine | 17 (one look per TF) |
| split_bar (H-gate stability) | 70 % of hold-out bars |
| verdict source | `rqs2.compute_rqs2` only — never hand-written |
| result file | `results/S653_DistributedMultiBarShock_Xauusd_AllTFs_rqs2_<best>_<verdict>.md` |
| per-TF artifact | `results/_scan_S653/final_<TF>.json`, committed+pushed per TF |

## 6. Eight common mistakes — how S653 avoids them

1. Look-ahead: `atr_ref = ATR[t-k-1]`, window ends at t, entry at t+1 open (engine).  2. Hold-out contamination: second half never loaded in exploration (`df.iloc[:half]`).  3. Post-hoc tuning: table above is frozen in this commit.  4. Hand verdict: engine only.  5. Multiple-testing: n_trials=17 declared; total first-half looks disclosed (≈102 + 6 grid-A).  6. Survivorship / TF-picking: all 17 TFs reported, incl. negatives.  7. Data path: mt5_full guard.  8. Overlap inflation: `allow_overlap=False` + non-overlapping null.

*Ramanujan — S653 — committed before `strategies/s653_final_test.py` exists.*
