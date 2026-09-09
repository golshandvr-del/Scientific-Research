# S996 PREREG — OlsChannelBreakPool (XAUUSD {H4,H6,H8}) — Lagrange decade S990–S999

**Committed BEFORE any second-half (holdout) number.** Route C + RQS2-POOL (`engine/rqs2_pool`, unchanged; adjudication machinery copied from S604/S606/S607 unchanged).

## Hypothesis (least-squares channel — Lagrange/Gauss)
In a window W the OLS line close ~ a + b·t is the minimum-energy description of the trend. The standardised residual
zres_t = (close_t − fit_t)/σ_e, σ_e = √(SSE/(W−2)), measures how far price has left that description.
A **fresh** exit from the channel (|zres| crosses θ from inside, first bar only) **in the direction of the slope** is a
trend-acceleration event: the market abandons its own linear fit upward while already rising (or downward while falling).
Fade and counter-slope arms are controls. No layer in the repo uses OLS residuals as the edge coordinate (0 references).
Distinct from new ACCEPTs reviewed today (S589/S749/S1511/S1521 = fresh-record families; S1911 = Kyle shock × calm): those are
price-record or intrabar-range events; this is a regression-residual event with slope alignment.

## Exploration (first half only) — `research/s996_explore/ols_channel.json`, 210 cells
- TF∈{H4,H6,H8} × W∈{34,55,89} × θ∈{2.0,2.5} × arms{break, fade, cbrk} × side × rr∈{1.0,1.5}.
- **break** (slope-aligned) is the only broadly positive arm; W55/θ2.0 rr1.0 is positive on all six (TF,side) cards:
  H4-long +13.9 (n92, 7/8y) · H4-short +7.4 (n86) · H6-long +5.3 (n62) · H6-short +17.0 (n60, 7/8y) · H8-long +2.2 (n39) · H8-short +17.2 (n41).
- Four cells z≥2.5 (H4 W55 long rr1.0; H6 W55 short rr1.0/1.5; H6 W55 θ2.5 long rr1.5) — none alone has n≥150 → pool.
- W89 short positive / W89 long negative on H4/H6 (asymmetry noted, not used). W34 mixed.

## Frozen rule (no free parameter remains)
- W = 55, θ = 2.0; event = zres crosses +θ (long) / −θ (short) from inside, first bar only; slope > 0 for long, < 0 for short.
- Per card: SL = 1.5 × median(rolling-mean TR100)/0.1 pip on the card's holdout half (geometry only); **TP = SL** (rr 1.0). max_hold H4:30, H6:24, H8:21. allow_overlap False.
- **Pool members frozen from first half** (lift>0, homogeneous 5–17pp): H4-long, H4-short, H6-long, H6-short, H8-short. H8-long excluded (first-half +2.2, rr1.5 negative).
  `pool_cards` receives the **first-half** lifts, so member selection is holdout-blind; FIFO on calendar time (concurrency 1).
- Null per card: hardest unconditional stride {3,7,13} per side; permutation K=500 unconditional, seed 996996; blended by pool share (S604 `blend_null`, copied).
- Adjudication: `compute_rqs2(pool, 'XAUUSD', sl_pip=share-weighted SL, tp_pip=share-weighted TP, bar_time=hourly axis, close=H1 close on axis, null=blend, holdout_mask = t_entry ≥ 70% quantile of holdout entries, n_trials=NT)`.
- n_trials honest = 210 (cells) + 5 (member/rr freezing decisions) = **215**. One official run; one stress run at n_trials=1000 reported alongside (does not replace the official).

## Predictions (falsifiable)
- Expected pooled n ≈ 250–350 on the second half; if real: lift ≥ +8pp, z ≥ 3.
- Honest prior: **50/50 POWER-LIMITED vs ACCEPT**; REJECT if pooled lift < +4pp (then OLS channel break is in-sample geometry noise; family CLOSED).
- If ACCEPT → STOP and report to the user; overlap audit vs S526/S749/S965/S966/S606/S607/S1911 to follow.

Verdict MD: `results/S996_OlsChannelBreakPool_Xauusd_H4H6H8_rqs2_<score>_<verdict>.md`.
