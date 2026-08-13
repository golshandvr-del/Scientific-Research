# S850 — PREREGISTRATION: Multiscale Resonance (XAUUSD only)

**Date**: 2026-08-13 (commit timestamp = preregistration timestamp)
**Author persona**: Benoit Mandelbrot (fractal/scaling)
**Status**: PRE-REGISTERED BEFORE ANY FINAL TEST (audit rule ③, multiplicity path committed to git before running)

---

## 1. Hypothesis (the fractal claim)

Markets are approximately self-similar across scales. When the *sign of return* agrees
across three widely-separated candle-space lookbacks, the price process is momentarily
in a **cross-scale resonance** — a transient departure from the null (scale-independent
sign randomness). I claim this resonance carries directional information at its **birth**
(the bar where alignment first appears), not during its persistence.

- Scales (candle space, Fibonacci): **L = (8, 34, 144)** bars.
- Alternative scale set (registered as part of the same grid, NOT a later addition): **(5, 21, 89)**.
- Signal: `s_k(i) = sign(close[i] − close[i−L_k])` for k=1..3.
- **LONG raw signal** at bar i: all three s_k(i) = +1 AND NOT all three were +1 at bar i−1 (transition birth).
- **SHORT raw signal**: mirror with −1.
- Both directions traded. **Zero additional filters** (no hour, no dow, no regime gate).
- Candle-space scales are deliberate: the self-similarity hypothesis itself says the rule's
  *meaning* is preserved across TFs when expressed in bars, unlike wall-clock rules (S139 lesson).

## 2. Frozen geometry grid (18 combos total)

- `ATR = ATR(34)` (plain Wilder ATR on the tested TF), converted to pips.
- `SL = k · ATR34`, k ∈ {1.272, 1.618, 2.058}  (per-bar array, floor 5 pips)
- `TP = rr · SL`, rr ∈ {1.0, 1.272, 1.618}  — **TP ≥ SL always** (budget-preservation law)
- `max_hold = 34` bars.
- Triple-Lock check: worst case (k=2.058 unused in lock; rr_max=1.618) → hold ≥ (k_sl·rr)² = (2.058·1.618)² ≈ 11.1 ≤ 34 ✅
- Combos: 2 scale-sets × 3 k × 3 rr = **18**; `n_trials = 36` (18 × 2 sides).

## 3. Multiplicity path: **C (hold-out)** — registered here

- `split_bar = floor(0.60 · n_bars)`.
- Exploration: choose the single best combo by **expectancy per trade** on the first 60%,
  requiring n ≥ 30 in exploration; ties broken by higher n.
- Judgment: exactly **one** call to `compute_rqs2` on full data with `split_bar` set,
  `n_trials=36`. No second look, no re-selection after seeing holdout.
- Path C viability threshold acknowledged: needs lift·√n ≥ 78.

## 4. Null protocol (measured permutation null)

- Per side: K = **600** permutations (≥500 required), random entry bars with the SAME
  frozen per-bar SL/TP arrays and max_hold, same costs.
- `SEED = 20260811`. Null dict in canonical rqs2 form
  (`{'long': {uncond_wr, perm_mean, perm_sd, perm_max, perm_k}, 'short': {...}}`).

## 5. Costs / account (fixed by user)

- XAUUSD: CONTRACT_SIZE=100, spread = 3.3 pip (0.33$/oz), commission 0, margin $40/lot.
- Engine `ASSETS['XAUUSD']` matches (spread_pip=3.3, comm=0.0).

## 6. Data & MTF protocol

- Source: `data/mt5_full/XAUUSD_<TF>.csv` (15.6y, M1 = 5,000,001 candles), loaded via
  `tools/s434_fast_data.load_fast` — `src` reported in every result MD (E-16 trap avoided).
- MTF law: start **XAUUSD-M1**, then every TF separately (all 19), each with its own
  per-TF exploration/holdout and its own SL/TP (ATR-scaled so geometry auto-adapts).
- **EURUSD excluded by explicit user exception.**
- Checkpoints: `results/_scan_S850/<TF>.json` committed+pushed per TF (incremental law).

## 7. Anti-cheat commitments

1. No manual verdict conversion — engine verdict reported verbatim.
2. No post-hoc filter additions after seeing holdout; any new filter = new strategy number, new prereg.
3. tp_pip explicit; bar_time, close, split_bar, null, n_trials all passed → no INCOMPLETE by omission.
4. Overlap audit vs existing accepted layers (S312/S344/S355/S356/S382/S431/S432) via
   event-driven `engine/trade_simulator.py` for any non-REJECT card; overlapping part
   tested as filter immediately.
5. Score is rank-only; gates decide (ADMISSION_RULE='gates_only').

*"The fractal geometry of nature is not an accident; if gold's cascade is real, three
scales whispering the same sign is the moment the cascade becomes audible."* — B.M.
