# S654 PREREG — Session-Slot Informed Shock (XAUUSD, M1…H12)

**Scientist:** Ramanujan (block S650–S659, #5 of 10) · **Protocol:** Path C (audit §6.2) · **Engine:** RQS2 v2.6
**Status:** LOCKED before any hold-out (second-half) number is computed.
**Explorer:** `strategies/s654_session_shock_explore.py` (commit 57fb86e3, before any number) · artifacts `results/_scan_S654/explore_<TF>.json` (last checkpoint 1089db42).
**Data:** `data/mt5_full/XAUUSD_<TF>.csv` (E-16 guard: script asserts `'mt5_full' in src`).

## 1. Hypothesis

Base event = the living gold family (S965, frozen): `high−low ≥ θ·ATR21[t−1]`, `ρ=|close−open|/(high−low) ≥ 0.618`, follow the body.
New lever (virgin — zero session gates on the shock family in the DB, zero Admati–Pfleiderer references): **the UTC session in which the shock bar starts**.
Admati–Pfleiderer (1988): informed traders concentrate in liquid hours ⇒ a London/NY shock should be informational (continuation); an Asia shock should be liquidity-driven (reversal/no edge).
Slots: ASIA [0,8) · LONDON [8,16) · NY [16,24) UTC (H12: AM [0,12) / PM [12,24)). D1/W1/MN1: session undefined ⇒ **not tested** (declared N/A, not REJECT).

Geometry frozen from S965: SL=1.272·ATR21[t−1], TP=2.058·ATR21[t−1] (RR 1.618), hold=16, no overlap, spread 3.3.

## 2. Search disclosure (first half only)
θ∈{2.058, 2.618} × 3 slots = 6 combos × 16 TFs = 96 looks, plus 2 ungated arms per TF (32 looks, used only for P1, never selected). Selection rule fixed before looking: `best_by_zmin`.

## 3. Locked TF → (θ, slot) table

| TF | θ | slot | n_L | lift_L | z_L | n_S | lift_S | z_S | z_min |
|---|---|---|---|---|---|---|---|---|---|
| M1 | 2.058 | LONDON | 16325 | +0.85 | 2.35 | 16558 | +0.65 | 1.79 | 1.79 |
| M3 | 2.618 | NY | 1354 | -0.22 | -0.17 | 1403 | -1.18 | -0.91 | -0.91 |
| M4 | 2.618 | NY | 949 | +1.40 | 0.89 | 1018 | +1.49 | 0.98 | 0.89 |
| M5 | 2.618 | NY | 775 | +2.25 | 1.29 | 836 | +0.21 | 0.13 | 0.13 |
| M6 | 2.618 | NY | 699 | +0.66 | 0.36 | 778 | -0.30 | -0.17 | -0.17 |
| M10 | 2.618 | NY | 490 | +2.26 | 1.03 | 566 | +1.60 | 0.78 | 0.78 |
| M12 | 2.618 | NY | 456 | +1.31 | 0.57 | 520 | +1.72 | 0.80 | 0.57 |
| M15 | 2.618 | NY | 413 | +2.92 | 1.22 | 467 | +1.60 | 0.71 | 0.71 |
| M20 | 2.618 | LONDON | 614 | +1.45 | 0.74 | 617 | +0.60 | 0.30 | 0.30 |
| M30 | 2.618 | ASIA | 67 | +6.93 | 1.16 | 86 | +5.21 | 0.99 | 0.99 |
| H1 | 2.618 | LONDON | 201 | +3.62 | 1.05 | 197 | +6.89 | 1.97 | 1.05 |
| H2 | 2.618 | LONDON | 106 | -0.38 | -0.08 | 109 | +5.30 | 1.13 | -0.08 |
| H3 | 2.618 | LONDON | 88 | +12.88 | 2.49 | 112 | +4.32 | 0.93 | 0.93 |
| H6 | 2.058 | LONDON | 75 | +6.72 | 1.20 | 85 | +4.46 | 0.84 | 0.84 |
| H8 | 2.058 | NY | 51 | +0.48 | 0.07 | 45 | -3.49 | -0.48 | -0.48 |
| H12 | 2.058 | PM | 51 | -2.90 | -0.43 | 48 | +7.93 | 1.11 | -0.43 |

```python
LOCKED = {'M1': (2.058, 'LONDON'), 'M3': (2.618, 'NY'), 'M4': (2.618, 'NY'), 'M5': (2.618, 'NY'),
          'M6': (2.618, 'NY'), 'M10': (2.618, 'NY'), 'M12': (2.618, 'NY'), 'M15': (2.618, 'NY'),
          'M20': (2.618, 'LONDON'), 'M30': (2.618, 'ASIA'), 'H1': (2.618, 'LONDON'),
          'H2': (2.618, 'LONDON'), 'H3': (2.618, 'LONDON'), 'H6': (2.058, 'LONDON'),
          'H8': (2.058, 'NY'), 'H12': (2.058, 'PM')}
```

## 4. Falsifiable predictions (written BEFORE the hold-out run)

- **P1 (primary, pessimistic): all 16 TFs → REJECT.** Max first-half z = 2.49 (H3 long London, n=88) — below H3's 3.09 and z_luck_bound(16). The session gate does **not** add information to the S965 shock: on H8 (the only TF where S965 itself is alive) the ungated arm (θ=2.618: z_L 1.76 / z_S 2.40) is *stronger* than any slot arm — slicing the ~80 H8 events into three sessions only destroys power. If P1 holds ⇒ layer dead, lesson: "session is not an informational lever on gold shocks; Admati–Pfleiderer concentration does not show up at bar scale".
- **P2 (structure): ASIA slot never wins** on any TF except by noise (it won only M30, n=67/86). If ASIA were to come out with the largest lift on the hold-out in ≥3 TFs, the Admati–Pfleiderer sign is inverted (liquidity shocks continue) — I will report it as a falsification of the *direction*, not as an edge.
- **P3 (pool clause):** only if ≥2 TFs are POWER-LIMITED with co-directional lift, a pool rescue via separate addendum; otherwise no pool.

## 5. Protocol constants

| item | value |
|---|---|
| hold-out | `df.iloc[half:]` per TF, touched once |
| SEED | 654654 |
| null model | K=600 unconditional same-geometry events (all hours — the null is *unconditional*, so a genuine session effect must beat the whole-day baseline), `select_non_overlap`, per side |
| n_trials passed to engine | 16 |
| split_bar | 70 % of hold-out bars |
| verdict source | `rqs2.compute_rqs2` only |
| result file | `results/S654_SessionSlotInformedShock_Xauusd_M1toH12_rqs2_<best>_<verdict>.md` |
| per-TF artifact | `results/_scan_S654/final_<TF>.json`, committed+pushed per TF |

## 6. Eight common mistakes — how S654 avoids them
1. Look-ahead: ATR[t−1], hour of bar t is known at bar close, entry at t+1 open. 2. Hold-out contamination: exploration used `df.iloc[:half]` only. 3. Post-hoc tuning: table frozen here. 4. Hand verdict: engine only. 5. Multiple testing: 96+32 first-half looks disclosed; n_trials=16. 6. TF-picking: all 16 TFs reported; D1/W1/MN1 declared N/A in advance. 7. Data path: mt5_full guard. 8. Overlap: `allow_overlap=False` + non-overlapping null. Timezone: MT5 server time verified = UTC (week opens at 00:00 Monday; H8 bars at 0/8/16).

*Ramanujan — S654 — committed before `strategies/s654_final_test.py` exists.*
