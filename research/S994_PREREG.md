# S994 PREREG — SeasonalVolumeShockLong (XAUUSD M30) — Lagrange decade S990–S999

**Committed BEFORE any second-half (holdout) number.** Route C.

## Hypothesis (Admati–Pfleiderer 1988 intraday seasonality)
Raw tick-volume shocks (S916/S917 Keynes, REJECT) are contaminated by hour-of-day seasonality and a 4× secular volume growth.
Deseasonalised relative volume rv_t = volume_t / median(volume of the SAME time-of-day slot over the previous 20 sessions, causal)
isolates "unexpected" participation. Direction = candle body (follow, S965 convention).

## Exploration (first half only) — `research/s994_explore/seasonal_volume.json`, 64 cells
- M30/H1 × θ∈{2,3} × ρ_min∈{0,0.5} × {follow,fade} × side × rr∈{1.0,1.5}.
- Result: NO cell with z ≥ 2.5. Best: M30 θ=3 ρ≥0 follow LONG rr1.5 — n=484, lift +3.43pp, z=1.51, pnl −1.01 pip, 4/8 yrs.
- Follow-SHORT is systematically NEGATIVE (z down to −3.37, 0/8 yrs): high-volume down-candles are absorbed, not continued.
- Honest reading: deseasonalised volume shock carries ~no directional information on gold at M30/H1 (high-power null, n in the hundreds).

## Frozen rule (max-power cell; no free parameter remains)
- TF **M30**, side **LONG**, max_hold 64, allow_overlap False.
- rv_t ≥ 3.0 (same-slot 20-session median, shift(1), min_periods 10); close > open (bull body); ρ_min = 0.
- Null habitat: unconditional (hardest stride {3,7,13} over whole holdout; perm K=500, seed 994994).
- SL = 1.5 × median(rolling-mean TR100)/0.1 pip on holdout half (geometry-only); TP = 1.5 × SL.
- n_trials honest = 64.

## Prediction
- **REJECT** (expected lift < +4pp, pnl ≈ 0 or negative). If the holdout shows lift ≥ +4pp with pnl > 0 and p_perm ≤ 0.01, the volume-seasonality family reopens for S995 in a different habitat; otherwise CLOSED for the decade.

One run only. Verdict MD: `results/S994_SeasonalVolumeShockLong_Xauusd_M30_rqs2_<score>_<verdict>.md`.
