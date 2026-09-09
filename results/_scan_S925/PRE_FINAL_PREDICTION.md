# S925 — PRE-FINAL PREDICTION (committed BEFORE any holdout touch)

Date: 2026-09-06 · Prereg commit: aba8546b · Grid frozen (W{34,89}×gate{ungated,gated}×a{1.618,2.058}×side, hold=55), n_trials=24.
Data: all 19 TFs `data/mt5_full/` (src asserted in `prep()`; runtime guard requires `mt5_full` AND span ≥14y). No data incident this run.

## Survivors → final (11): M15, M20, M30, H1, H2, H3, H4, H6, H8, H12
NO-SURVIVOR (8): M1, M3, M4, M5, M6, M10, M12 (cost law), D1, W1 (W=89 record events too sparse — F5 partly fires at D1/W1).

| TF | card (W/gate/a/side) | n_train | WR | edge | train other-gate edge | flags |
|---|---|---|---|---|---|---|
| M15 | 89/gated/2.058/long | 456 | 55.70 | +0.27 | −3.42 | edge ≈ 0 → REJECT certain |
| M20 | 89/gated/2.058/long | 316 | 59.81 | +5.17 | +0.53 | first minute-TF survivor with real edge in my block; costs will bite in holdout |
| M30 | 89/ungated/2.058/long | 496 | 56.45 | +2.73 | +3.28 | thin |
| H1 | 89/gated/1.618/long | 126 | 57.14 | +3.88 | −4.05 | thin, n<150 |
| H2 | 89/gated/2.058/long | 57 | 64.91 | +13.09 | +2.44 | n=57 bait |
| H3 | 89/gated/2.058/both | 95 | 67.37 | +15.91 | +8.54 | n<100 but ungated also strong (+8.5) → concept signal not only gate |
| H4 | 89/gated/1.618/both | 77 | 72.73 | +21.14 | +11.00 | n=77; WR 72.7 is suspicious (S91x) |
| **H6** | 34/ungated/2.058/both | **196** | 62.76 | +11.76 | gated +14.63 (n=96) | **strongest card: n≈200 with +11.8 edge — first such in S920–S925** |
| H8 | 89/gated/2.058/both | 37 | 75.68 | +24.83 | +11.65 | n=37 bait |
| H12 | 34/ungated/2.058/short | 56 | 66.07 | +15.40 | +16.97 | short, n=56 |

## Predictions (accountability)
1. **This is structurally different from S920–S924**: the record-return event has positive edge in *both* gate arms across H2–H12 (ungated +2..+17), so the signal is the record itself, not the drift gate. Drift gating adds +4..+11pp in train (F3-train pass) — but L-S924-2 says train F3 is not evidence; the holdout F3 diagnostic decides.
2. **H6 (n=196, ungated both)** is the decisive card. Prediction: holdout WR 55–60, lift +5..+10pp, z 1.5–2.8 → **POWER-LIMITED most likely**; ACCEPT requires z≥3.09 ⇒ needs n_hold ≳ 200 with lift ≥ +10 — possible but not probable. P(ACCEPT at H6) ≈ 25%.
3. **H3/H4 (n=95/77, both)**: expect partial collapse (WR 72.7 → ~58) but may stay positive; z < 3 → REJECT/POWER-LIMITED.
4. **H2/H8/H12 (n=57/37/56)**: S91x law — collapse toward 0; H12 short additionally faces the rally headwind (shorts 0/9).
5. **M20/M30**: minute-TF costs — expect holdout edge ≤ +2 → REJECT. M15 REJECT certain.
6. **Family**: P(≥1 ACCEPT) ≈ 30%, P(≥1 POWER-LIMITED) ≈ 60%. Best RQS2 expected 25–40. If ACCEPT comes, most likely at H6 or H3.
7. F4: both-cards will show long side > short side in holdout (rally half); I will report per side.

Holdout will now be touched ONCE per surviving TF (11 official runs) plus the preregistered report-only F3 other-gate simulation per TF (declared in prereg §4; produces no card/verdict).
— Hayek, S925
