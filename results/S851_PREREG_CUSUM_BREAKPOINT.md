# S851 — PREREGISTRATION: CUSUM Drift Breakpoint (XAUUSD only)

**Date**: 2026-08-14 (commit timestamp = preregistration timestamp)
**Author persona**: Benoit Mandelbrot | **Block**: S850–S859 (my lane; no other block touched)
**Status**: PRE-REGISTERED BEFORE ANY FINAL TEST (audit rule ③)

---

## 1. Hypothesis

Gold's returns are locally standardizable: `z_i = r_i / σ_i` with a causal EWMA σ.
A one-sided **CUSUM** accumulator detects the onset of a drift regime:

- `S⁺_i = max(0, S⁺_{i−1} + z_i − k_drift)` → **LONG** signal at the first bar where `S⁺_i > h`, then `S⁺ := 0` (reset).
- `S⁻_i = max(0, S⁻_{i−1} − z_i − k_drift)` → **SHORT** mirror.

Claim: crossing `h` marks a genuine change-point in drift (trend-following entry),
not noise. Dimensionless z-space is the fractal-scaling-friendly formulation:
the rule's meaning is invariant across TFs (S139 lesson honored).
σ: causal EWMA of r² with λ=0.97 (as in s830 exploration), floor 1e-12.
Zero additional filters. Both sides. Lesson from S850 applied: this detector fires
far more often than alignment-birth, attacking the n-starvation seen at high TFs.

## 2. Frozen signal grid

- `k_drift ∈ {0.5, 1.0}` (drift allowance per bar, in σ units)
- `h ∈ {5, 8, 13}` (Fibonacci thresholds, in σ units)
⇒ 6 signal variants.

## 3. Frozen geometry grid

- `SL = k · ATR(34)` (pip floor 5), k ∈ {1.618, 2.058}
- `TP = rr · SL`, rr ∈ {1.272, 1.618} — TP ≥ SL always (budget preservation)
- `max_hold = 34`. Triple-lock: (2.058·1.618)² ≈ 11.1 ≤ 34 ✅
⇒ 4 geometry combos. Total grid = 6 × 4 = **24 combos**; `n_trials = 48` (× 2 sides).

## 4. Multiplicity path: **C (hold-out)** — registered here

- `split_bar = floor(0.60 · n_bars)`; exploration on first 60% only.
- Winner rule: highest expectancy with n ≥ 30 in exploration; ties → larger n.
- One judgment: single `compute_rqs2` call on full data with `split_bar`, `n_trials=48`.
- Path C viability: needs lift·√n ≥ 78 (acknowledged).

## 5. Null protocol

- Measured permutation null per side, K = **600** ≥ 500, SEED = **20260814**,
  random entries with the same frozen per-bar SL/TP arrays and hold, same costs.
- Memory hygiene (S850 lesson): null candidate pool capped at 1M bars, uncond
  sample capped at 50k — random-of-random remains random; statistics unaffected.

## 6. Pre-registered POWER-LIMITED rescue (pooling)

If ≥2 TF cards return POWER-LIMITED (economic gates pass, only power gates fail,
lift>0, z>0), I will pool those cards' trades via `engine/rqs2_pool.py`
(the documented sample-pooling route used by historical winners) and report the
pooled verdict as a separate, pre-registered judgment. No other rescue.

## 7. Data / MTF / account

- Source `data/mt5_full/XAUUSD_<TF>.csv` via `tools/s434_fast_data.load_fast`; `src` reported.
- MTF law: start M1, then all 19 TFs, each judged separately with own geometry.
- **EURUSD excluded (explicit user exception).**
- Account: CONTRACT_SIZE=100, spread 3.3 pip, comm 0, margin $40/lot.
- Checkpoints `results/_scan_S851/<TF>.json`, commit+push per batch (اندک اندک).

## 8. Anti-cheat commitments

1. Engine verdict verbatim; no manual conversions.
2. No post-hoc filters; any new idea ⇒ S852+ with fresh prereg.
3. tp_pip / bar_time / close / split_bar / null / n_trials always passed.
4. Overlap audit for any non-REJECT card (event-driven simulator); CUSUM grep
   confirmed virgin in repo before this prereg.
5. Score rank-only; gates decide.

*"A change-point is where the cascade re-roots itself; CUSUM is simply the
microscope focused on that re-rooting."* — B.M.
