# S998 PREREG — CurvatureReigniteShort (XAUUSD H4) — Lagrange decade S990–S999

**Committed BEFORE any second-half (holdout) number.** Route C.

## Hypothesis (second-order term)
Local model p(t) ≈ p0 + v·t + ½a·t² on EMA(W) of close: v_t = m_t − m_{t−1}, a_t = v_t − v_{t−1}.
Edge = curvature sign flip re-aligned with an existing slope (down-trend that slowed then re-accelerates: a crosses from ≥0 to <0 while v<0 → SHORT; mirror → LONG).
Controls: flip without slope condition (state) and counter-trend inflection. No layer in the repo uses curvature/second derivative (0 references).

## Exploration (first half only) — `research/s998_explore/curvature.json`, 216 cells
- TF∈{H1,H2,H4} × W∈{8,13,21} × q∈{0,0.5} × 6 arms × rr∈{1.0,1.5}. **No cell z ≥ 1.5.** High-power null (n in the hundreds to thousands).
- Best: H4 W21 q0 reignite-SHORT rr1.5 — n=667, lift +2.88pp, pnl +7.31, z 1.49, 7/8 yrs. Long side ≈ 0. Controls ≈ 0.
- Honest reading: the second derivative of a smoothed price carries no directional information on gold at H1–H4.

## Frozen rule (max-power cell; no free parameter remains)
- TF **H4**, side **SHORT**, max_hold 30, allow_overlap False. EMA span 21; a_t<0 & a_{t−1}≥0 & v_t<0 (q=0).
- SL = 1.5 × median(rolling-mean TR100)/0.1 pip on holdout (geometry only); TP = 1.5 × SL.
- Null: unconditional habitat (hardest stride {3,7,13}; perm K=500, seed 998998). split_bar = 0.70·len.
- n_trials honest = 216.

## Prediction
- **REJECT** (lift < +4pp; z < 2). If lift ≥ +4pp with pnl>0 the family reopens in S999; otherwise curvature family CLOSED.

One run only. Verdict MD: `results/S998_CurvatureReigniteShort_Xauusd_H4_rqs2_<score>_<verdict>.md`.
