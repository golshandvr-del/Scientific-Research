# S924 — PRE-FINAL PREDICTION (committed BEFORE any holdout touch)

Date: 2026-09-05 · Prereg commit: 686a5649 · Grid frozen (K{55,144}×θ{1.0,1.618}×a{1.618,2.058}×side, hold=55), n_trials=24.

## Data provenance (E-16)
All 18 TFs loaded from `data/mt5_full/` (span 15.59y; M1 = 5,000,000 bars = 14.34y, MT5 export cap — the trap
files are 2.8y/6.4y). H4 from `data/XAUUSD_H4.csv`, span **15.53y** (full, S526/S923 precedent). Runtime span
guard (≥14y) asserted in `prep()` for every TF. A first partial run made while `mt5_full/*.csv.gz` was still
unpacked (sandbox reset) fell back to short files — it was **purged from git** before any holdout touch and
fully re-run; no holdout was touched in that run.

## Survivors → final (9): H1, H2, H3, H4, H6, H8, H12, D1  (+ none of minute TFs)
NO-SURVIVOR (11): M1, M3, M4, M5, M6, M10, M12, M15, M20, M30 (cost law — **8th confirmation**), W1.

| TF | card (K/θ/a/side) | n_train | WR | edge | raw-drift baseline edge (same K, same side) | F3 (SNR adds info?) | flags |
|---|---|---|---|---|---|---|---|
| H1 | 144/1.618/1.618/short | 165 | 56.97 | +3.70 | −3.17 | YES (+6.9pp) | thin; SHORT in rally-half holdout (L-S921-4) |
| H2 | 55/1.618/1.618/short | 158 | 56.96 | +4.64 | −2.85 | YES (+7.5pp) | short risk |
| H3 | 144/1.0/2.058/long | 106 | 59.43 | +7.97 | −7.11 | YES (+15pp) | n<150 |
| H4 | 55/1.0/2.058/short | 146 | 59.59 | +8.34 | −4.29 | YES (+12.6pp) | short risk; n≈150 |
| H6 | 144/1.618/1.618/long | 30 | 63.33 | +12.07 | −2.38 | YES but n=30 | **bait: n=30 at survivor floor** |
| H8 | 144/1.618/1.618/both | 40 | 65.00 | +13.92 | +3.09 | YES (+10.8pp) | **bait: n=40** |
| H12 | 55/1.0/2.058/short | 53 | 58.49 | +7.82 | **+13.43** | **NO — raw drift beats SNR** | n=53; F3 fails here |
| D1 | 144/1.0/1.618/both | 34 | 52.94 | +2.37 | −13.07 | YES but thin | n=34, edge +2.4 ≈ noise |

## Predictions (accountability)
1. **F3 on train: PASS in 7/8 survivors** — SNR normalisation lifts edge +7..+15pp over raw-drift sign flips
   (which are mostly negative: plain TSM sign cross loses on gold at these horizons). Failure at H12.
   This is the first family in my block where the concept's own diagnostic passes clearly in train.
2. **Small-n cards H6/H8/D1/H12 (n=30/40/34/53)**: S91x law (5× confirmed) → expect collapse toward 0 lift.
3. **Decisive cards: H1/H2/H4 shorts (n=146–165)** and **H3 long (n=106)**. Shorts face the 2024–26 rally
   headwind; S923-H2 short (n=215, filter adding in train) still failed. I predict H1/H2/H4 holdout
   WR ≈ 48–52 → REJECT. H3 long is the single most plausible card: predicted holdout lift +2..+6pp, z 1–2.
4. **Family expectation**: most likely ALL REJECT, best RQS2 15–30; P(any ACCEPT) ≈ 10%, P(POWER-LIMITED) ≈ 20%.
5. Shorts negative / longs positive in holdout (F4) would mean residual = secular drift — will report honestly.

Holdout will now be touched ONCE per surviving TF. Guard files enforce single touch.
— Hayek, S924
