# S999 PREREG — NestedRecordLong (XAUUSD H1 inside H4 record regime) — Lagrange decade S990–S999 (last number)

**Committed BEFORE any second-half (holdout) number.** Route C.

## Hypothesis
Fresh-record edge (S526/S1511/S1520/S1521) is real on H6/H8 but dies on H1–H3. Conjecture: an H1 fresh 90-record occurring while the
last *closed* H4 bar itself set a fresh 90-record (parent regime, L=1, causal via bar close times) inherits the parent's information.
Controls (S965 P1): raw H1 record; anti-gate (parent NOT at record). No layer in the repo tests lower-TF record nested in higher-TF record (0 references).

## Exploration (first half only) — `research/s999_explore/nested_record.json`, 48 cells
- W1∈{55,90} × parent∈{H4,H8} × L∈{1,3} × side × rr, plus raw/anti controls.
- **Every nested cell is NEGATIVE** (lift −0.1 … −5.8pp, pnl < 0), while raw/anti ≈ 0…+3. The hypothesis is falsified in-sample with the
  opposite sign: an H1 record *inside* a parent record is exhaustion, not reinforcement (parent record already consumed the move).
- No cell z ≥ 2.5 in either direction (min z −1.63).

## Frozen rule (primary cell declared before exploration: nested, parent H4, L=1, long, W1=90)
- TF **H1**, side **LONG**, max_hold 48, allow_overlap False. Edge: close > max(close[t−90..t−1]) and not on t−1. Gate: last closed H4 bar set close > max(prev 90 H4 closes).
- SL = 1.5 × median(rolling-mean TR100)/0.1 pip on holdout (geometry only); TP = 1.5 × SL.
- Null within gate: hardest gated stride {3,7,13}; permutation K=500 within gate, seed 999999. split_bar = 0.70·len. n_trials honest = 48.

## Prediction
- **REJECT** with negative lift (transfer of the in-sample −5.8pp). If holdout lift ≥ +4pp the first half was the anomaly (recorded, not pursued).
- The inverse (fading nested records) is NOT tested here — it would be a new hypothesis born from a burned family (S636 projection law); left for a future decade with its own PREREG.

One run only. Verdict MD: `results/S999_NestedRecordLong_Xauusd_H1_rqs2_<score>_<verdict>.md`.
