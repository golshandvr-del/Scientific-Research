# S995 PREREG — SeasonalRangeShockLong (XAUUSD H2) — Lagrange decade S990–S999

**Committed BEFORE any second-half (holdout) number.** Route C.

## Hypothesis
S965 (ACCEPT 86, H6/H8) fails on H3 (lift +2.9). Lagrange conjecture: at intraday TFs, ATR21 is blind to hour-of-day seasonality —
the London/NY opening candles are *always* large and generate false "shocks". Deseasonalise the range instead:
rr_t = (high−low)_t / median(range of the SAME time-of-day slot over the previous 20 sessions, causal, shift(1), min_periods 10).
Edge = rr_t ≥ θ AND retention ρ = |c−o|/(h−l) ≥ ρ_min → follow the body (S965 convention). Novel in repo (no deseasonalised-range layer exists).

## Exploration (first half only) — `research/s995_explore/seasonal_range.json`, 96 cells
- TF∈{M30,H1,H2} × θ∈{2.5,3.5} × ρ∈{0.618,0.8} × {follow,fade} × side × rr∈{1.0,1.5}. No cell z ≥ 2.5.
- Structure is monotone and physically sensible on **H2 follow LONG**: θ2.5/ρ.618 → +3.4pp (n=291); θ3.5/ρ.618 → **+7.74pp (n=109, pnl +7.5, z 1.62)**; θ3.5/ρ.8 → +9.97pp (n=51, pnl +10.7).
- M30 follow-SHORT strongly negative (z −3.8, 0/8 yrs) — same absorption asymmetry seen in S994: large down-candles on gold get bought.
- Fade-long on M30 (z 1.74) has pnl < 0 → not tradeable, ignored.

## Frozen rule (max-power positive-pnl cell; no free parameter remains)
- TF **H2**, side **LONG**, max_hold 40, allow_overlap False.
- rr_t ≥ 3.5; ρ ≥ 0.618; close > open.
- Null: unconditional habitat (hardest stride {3,7,13}; perm K=500, seed 995995). split_bar = 0.70·len(holdout).
- SL = 1.5 × median(rolling-mean TR100)/0.1 pip on holdout (geometry-only); TP = 1.5 × SL.
- n_trials honest = 96 (S995 cells) + 64 (S994 same-slot normalisation family debt) = **160**.

## Prediction
- Honest prior **REJECT / POWER-LIMITED**: expected n ≈ 100–130 on holdout, lift +4…+8pp, z < 3.09.
- If lift ≥ +4pp with pnl > 0 → deseasonalised-range family is real-but-underpowered; S996 may pool TFs. If lift < 0 → CLOSED.

One run only. Verdict MD: `results/S995_SeasonalRangeShockLong_Xauusd_H2_rqs2_<score>_<verdict>.md`.
