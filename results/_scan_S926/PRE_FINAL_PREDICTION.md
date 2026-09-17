# S926 — PRE-FINAL PREDICTION (committed BEFORE any holdout touch)

Date: 2026-09-07 · Prereg commit: ef0dfac5 · Grid frozen (θ{1.618,2.618}×age{young,any}×a{1.618,2.058}×side, hold=55, A_max=K/2), n_trials=24.
Data: all 19 TFs `data/mt5_full/` (asserted in `prep()`). No data incident.

## Survivors → final (9): M20, M30, H1, H2, H3, H4, H6, H8, H12
NO-SURVIVOR (10): M1–M15 (8 minute TFs, cost law 10×), D1, W1 (θ shocks too sparse with K=60/9 drift).

| TF | card (θ/age/a/side) | n_train | WR | edge | train other-age (n/edge) | flags |
|---|---|---|---|---|---|---|
| M20 | 2.618/any/2.058/long | 264 | 60.61 | +5.96 | young 163/+4.87 | minute TF — costs/DD in holdout (S925: maxDD 45–73%) |
| M30 | 2.618/any/2.058/long | 186 | 60.22 | +6.49 | young 110/+7.18 | same |
| H1 | 2.618/young/1.618/long | 62 | 66.13 | +12.86 | any 103/+4.99 | young > any by +7.9pp in train; n=62 |
| H2 | 2.618/any/2.058/both | 136 | 61.76 | +9.94 | young 78/+12.28 | young also stronger; n=136 → the most robust card |
| H3 | 2.618/young/2.058/both | 51 | 66.67 | +15.20 | any 80/+9.79 | young > any +5.4; n=51 |
| H4 | 2.618/any/1.618/both | 56 | 73.21 | +21.63 | young < 30 (F5) | n=56 bait |
| H6 | 2.618/any/2.058/both | 37 | 78.38 | +27.38 | young < 30 (F5) | **n=37 bait**; WR 78 = S91x classic |
| H8 | 1.618/any/1.618/short | 66 | 69.70 | +18.62 | young < 30 (F5) | **SHORT** — block record 0/10; n=66 |
| H12 | 1.618/young/1.618/both | 33 | 60.61 | +9.75 | any 69/+2.77 | young > any +7.0; n=33 bait |

## Predictions (accountability)
1. **Base event works in train** (every H1–H12 `any` arm has positive edge +3..+27) — the absolute c2c shock × 60d alignment carries the lineage edge as predicted in prereg §6. Whether it survives holdout is the question S925 answered negatively for the ordinal base; here the scale is absolute, so I predict **partial survival**: H2 holdout WR 54–58, lift +3..+8, z 1–2.
2. **Drift-age (the hypothesis)**: in train, `young` beat `any` at H1 (+7.9), H3 (+5.4), H12 (+7.0), H2 (+2.3); lost slightly at M20; tie M30. Where testable, young ≥ any in 5/6. **But** L-S924-2: train F3 is not evidence. Holdout F3 (report-only) decides. Prediction: young > any in holdout at H2/H3 with P ≈ 45%; young trades will be ~50–60% of any.
3. **F5 fired at H4/H6/H8**: young arm < 30 trades in train — the hypothesis is untestable at exactly the TFs where the lineage (S604/S965/S919) lives. Those cards are plain gated-shock cards on a new base.
4. **Bait cards H4/H6/H12 (n=56/37/33)** collapse (8th confirmation). **H8 short (n=66)**: L-S924-3 — shorts 0/10 — predict WR < 50 in holdout.
5. **Best realistic**: H2 both (n=136). P(ACCEPT anywhere) ≈ 15%; P(POWER-LIMITED) ≈ 30%; P(all REJECT) ≈ 55%. Best RQS2 expected 15–30.
6. M20/M30: n large (264/186) but holdout DD will be the killer; predict REJECT with lift 0..+3.

Holdout will now be touched ONCE per surviving TF (9 official runs) plus the preregistered report-only other-age simulation per TF.
— Hayek, S926
