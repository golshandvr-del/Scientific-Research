# S993 PREREG — ErShockCalmShort (XAUUSD H1) — Lagrange decade S990–S999

**Committed BEFORE any second-half (holdout) number is computed.** Route C.

## Lineage (honest)
- S992 (REJECT 17.8): Kaufman ER-shock LONG on H1, holdout lift +6.07pp, z=1.29 — real but power-starved.
- S993 exploration (`research/s993_explore/er_gated.json`, 54 cells, first half only): ER W13 edge × gate arms.
  Decisive P1 pattern on **H1 SHORT**: raw arm lift +2.26 (n=112) → CALM arm **+11.23** (n=63, 7/8 yrs, pnl +16.94 pip, power 89)
  → ANTICALM arm **−10.61** (n=49, 1/8 yrs). The σ-regime gate separates signal from noise, not just shrinks n.
- Drift gate (181-bar, H8 scale) kills lift on H1 (drift% ≈ 5%) — rejected as gate; noted, not used.

## Frozen rule (no free parameter remains)
- TF: **H1**, side: **SHORT**, max_hold = 48 bars, allow_overlap = False.
- ER_13 = |close − close.shift(13)| / Σ|Δclose|_13.
- Edge: ER_13 > 0.70 AND min(ER_13[i−3..i−1]) < 0.30, first bar only (edge & ~edge.shift(1)).
- Direction: net = close − close.shift(13) < 0 (short leg).
- CALM gate: ATR13_t ≤ median(ATR13_{t−233..t−1}) (S606 law).
- Signal = edge & (net<0) & calm.
- SL = 1.5 × median(rolling-mean TR, 100) / 0.1 pip (measured on holdout half, geometry-only; no lift used); TP = 1.5 × SL.

## Null / trials
- Null: hardest-stride baseline {3,7,13} within gate, per side; permutation K=500 within gate, seed 993993.
- n_trials (honest): 54 (S993 cells) + 146 (S992 ER-family debt) = **200**.
- split_bar = 0.70 × len(holdout).

## Predictions (falsifiable)
- Expected n ≈ 60–90 on holdout (second half denser? unknown).
- If lift ≥ +4pp and pnl > 0: ER-CALM family confirmed as *real-but-small*; verdict likely POWER-LIMITED/REJECT unless n ≥ 150.
- If lift < 0: σ-regime gating of ER shock is in-sample artefact → ER family CLOSED for the decade.
- Honest prior: **REJECT** (p_perm unlikely ≤0.001 at n<100).

## One run only. Verdict MD: `results/S993_ErShockCalmShort_Xauusd_H1_rqs2_<score>_<verdict>.md`.
