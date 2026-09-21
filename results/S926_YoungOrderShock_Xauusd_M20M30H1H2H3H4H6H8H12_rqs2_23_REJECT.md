# S926 — Young-Order Shock (Absolute Settlement Shock × Drift-Age) — OFFICIAL VERDICT: REJECT (best RQS2 = 23.3, H6)

- **Layer number**: S926 (block S920–S929) · **Scientist**: Friedrich Hayek · **Date**: 2026-09-07
- **Judge**: RQS2 v2.6 (official engine, untouched — 11 veto gates, `R.compute_rqs2`)
- **Prereg**: `results/S926_PREREG_YOUNG_ORDER_SHOCK.md` (commit `ef0dfac5`, BEFORE any test)
- **Pre-final prediction**: `results/_scan_S926/PRE_FINAL_PREDICTION.md` (committed BEFORE holdout touch)
- **Harness**: `strategies/s926_young_order_shock.py` (selftest PASSED: run-length identical to naive loop, ATR lagged one bar, no look-ahead; `prep()` asserts `src` ∈ `data/mt5_full` AND span ≥14y)
- **Data**: **all 19 TFs from `data/mt5_full/`** (15.59y; M1 14.34y export cap; H4 official S908-derived). `src` in every JSON. No data incident.
- **Path C**: multiplicity search on first half only; holdout touched ONCE per TF (guard files); n_trials=24 frozen; geometry-matched measured_null K=2000, seed 20260907. Preregistered report-only F3-holdout (other age arm, same θ/a/side) once per TF, labelled, no card.

## 1. Hypothesis (as preregistered)
Absolute close-to-close shock (|Δclose| ≥ θ·ATR21[t−1], θ∈{1.618, 2.618}) aligned with the 60-day drift (S604 convention) → follow. Hypothesis under test: shocks occurring while the drift is **young** (sign-run ≤ K/2 ≈ 30 days) continue more than in an old drift (Hayek: a spontaneous order is most informative at birth; later aligned shocks are imitation). SL=TP=a×ATR21 (RR=1), hold 55. Grid θ×age{young,any}×a×side = 24 trials.

## 2. Discover (first half)
- Survivors (9): M20, M30, H1, H2, H3, H4, H6, H8, H12. NO-SURVIVOR (10): M1–M15 (8 minute TFs, cost law), D1, W1 (F5 partly: too few shocks).
- Base `any` arm positive in train at every H1–H12 (+3..+27pp) — the absolute c2c shock × alignment carries the lineage edge in train. `young` > `any` in train at H1/H2/H3/H12 (+2..+8pp); **F5 fired at H4/H6/H8** (young n<30 — hypothesis untestable where the lineage lives).

## 3. Final (holdout, single touch) — ALL 9 REJECT

| TF | cfg (θ/age/a/side) | train n/WR | hold n | WR | PF | lift | z | exp (pip) | maxDD % | F3-holdout other-age WR (n) | RQS2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M20 | 2.618/any/2.058/long | 264/60.61 | 361 | 49.86 | 0.841 | −1.38 | −0.52 | −3.49 | 44.75 | young 53.21 (156) | 2.0 |
| M30 | 2.618/any/2.058/long | 186/60.22 | 246 | 48.37 | 0.822 | −3.41 | −1.07 | −4.74 | 32.87 | young 50.85 (118) | 5.4 |
| H1 | 2.618/young/1.618/long | 62/66.13 | 63 | 44.44 | 0.703 | −7.25 | −1.15 | −8.91 | 13.24 | any 43.38 (136) | 0.0 |
| H2 | 2.618/any/2.058/both | 136/61.76 | 127 | 52.76 | 1.019 | +2.24 | 0.38 | +1.69 | 9.53 | young 52.05 (73) | 3.2 |
| H3 | 2.618/young/2.058/both | 51/66.67 | 53 | 50.94 | 0.975 | +0.10 | 0.01 | −1.17 | 7.78 | any 54.02 (87) | 0.7 |
| H4 | 2.618/any/1.618/both | 56/73.21 | 46 | 58.70 | 1.309 | +7.99 | 0.79 | +14.76 | 4.33 | young 53.57 (28) | 15.8 |
| **H6** | 2.618/any/2.058/both | 37/78.38 | **18** | 66.67 | 1.922 | +12.76 | 0.82 | +51.93 | 1.92 | young 53.85 (13) | **23.3** |
| H8 | 1.618/any/1.618/short | 66/69.70 | 28 | 39.29 | 0.627 | −3.64 | −0.39 | −36.09 | 8.13 | young 39.13 (23) | 0.0 |
| H12 | 1.618/young/1.618/both | 33/60.61 | 39 | 66.67 | 1.868 | +14.33 | 1.35 | +60.82 | 5.03 | any 60.87 (69) | 17.7 |

Per-side (both-cards): H2 long 55.1 / short 49.0; H3 long 56.7 / short 43.5; H4 long 60.7 / short 55.6; H6 long 69.2 / short 60.0; H12 long 66.7 / short 66.7. H8 short 39.3 (F4 confirmed again: block shorts now **0/11**).

## 4. Failure analysis
1. **The drift-age hypothesis is falsified out of sample.** F3-holdout, where both arms had n≥30: young vs any — M20 53.2 vs 49.9 (+3.3), M30 50.9 vs 48.4 (+2.5), H1 44.4 vs 43.4 (+1.1), H2 52.1 vs 52.8 (−0.7), H3 50.9 vs 54.0 (−3.1), H12 66.7 vs 60.9 (+5.8). Mean difference ≈ +1.5pp, sign mixed, no TF where young lifts a losing base into profit. The "young order" carries no exploitable extra information; where the lineage lives (H4/H6/H8) it is untestable (F5). Hayek's birth-of-order intuition does not show up at the 60-day/30-day scale on gold.
2. **The base (absolute c2c shock × alignment) is weaker than S965's range-shock × ρ.** Holdout H4/H6/H12 are economically positive (PF 1.3–1.9, lift +8..+14) but with n=46/18/39 — z ≤ 1.35. H2 (the only n>100 card) is flat (+2.2). Compared with S919/S966 (same drift gate, range/ATR + ρ base, n≈70–110, z>3.2), the close-to-close field discards the intrabar evidence (range, body ratio) that makes the shock *informed*. **L-S925/L-S926 together**: settlement-only measures (ordinal or absolute) underperform range-based shock definitions on gold — Hayek's "only settlement transmits knowledge" is wrong for this asset; the auction path *is* information (Kyle).
3. **Predictions**: partial survival at H2 (predicted WR 54–58 → actual 52.8, low end); bait H4/H6 collapsed in n (56→46, 37→18) though WR held; H8 short failed (39.3) as predicted; M20/M30 died by DD (45%/33%) as predicted. P(all REJECT)=55% was the right modal call.
4. Minute TFs: 10th confirmation of the cost law (M20/M30 survive train with n>180 and die in holdout on drawdown).

## 5. Eight-common-mistakes proof
1. Look-ahead: shock uses ATR21[t−1]; drift uses close[t−1] vs close[t−1−K]; age run ends at t (built from close ≤ t−1); entry open t+1; selftest asserted a 5% spike at bar 6001 leaves events ≤6000 unchanged. 2. E-16: runtime assertion `mt5_full` + span ≥14y, 19/19 TFs. 3. Multiplicity: n_trials=24 prereg'd and passed to engine; A_max=K/2 fixed, not searched. 4. Holdout: single official touch per TF; F3 extra simulation preregistered (§4), report-only. 5. Survivor rule fixed before holdout. 6. Costs: 3.3 pip in simulator; H9 evaluated. 7. Verdict verbatim from `compute_rqs2`. 8. Sides reported separately; no pooling.

## 6. Lessons
- **L-S926-1**: Drift *age* (sign-run of the 60d drift) adds no out-of-sample information to aligned shocks on gold (Δ ≈ +1.5pp, mixed sign). Alignment is the whole gate; do not decompose it further.
- **L-S926-2**: Close-to-close shock (absolute) < range/ATR shock + body-ratio ρ. Two layers (S925 ordinal, S926 absolute) close the "settlement-only" family: the intrabar auction path is part of the signal.
- **L-S926-3**: Cards that are economically positive in holdout with n<50 (H4/H6/H12 here; H6/H8 in S922/S923) recur in every layer of this block and never reach z≥2 — they are the expected tail of 24-arm searches, not evidence. Treat as noise a priori.
- **L-S926-4**: Shorts 0/11. Block rule for S927–S929: long-only or both with per-side report; no short-only cards.

## 7. Official ledger entry
**S926 = REJECT (RQS2 = 23.3, best card H6 both θ2.618/any/a2.058, n=18)** — family closed.
Block ledger: S920=REJECT(6.1) · S921=REJECT(16.1) · S922=REJECT(16.0) · S923=REJECT(13.2) · S924=REJECT(10.5) · S925=REJECT(12.8) · S926=REJECT(23.3). Next: S927.

— Friedrich Hayek, S920–S929
