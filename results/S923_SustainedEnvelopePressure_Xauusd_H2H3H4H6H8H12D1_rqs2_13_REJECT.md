# S923 — Sustained Envelope Pressure (Band-Walk Persistence) — OFFICIAL VERDICT: REJECT (best RQS2 = 13.2, H8)

- **Layer number**: S923 (block S920–S929) · **Scientist**: Friedrich Hayek · **Date**: 2026-09-04/05
- **Judge**: RQS2 v2.6 (official engine, untouched — 11 veto gates, `R.compute_rqs2`)
- **Prereg**: `results/S923_PREREG_SUSTAINED_ENVELOPE_PRESSURE.md` (commit `4876f7be`, BEFORE any test)
- **Pre-final prediction**: `results/_scan_S923/PRE_FINAL_PREDICTION.md` (committed BEFORE holdout touch)
- **Harness**: `strategies/s923_envelope_pressure.py` (selftest PASSED: streak bit-exact, Bollinger max_abs_diff=0, no look-ahead)
- **Data**: `data/mt5_full/` 15.6y for 18 TFs; H4 from `data/XAUUSD_H4.csv` **verified full-span** (23,755 bars, 2011-01→2026 — same span as mt5_full, S526 precedent). E-16 exclusion condition did NOT hold → H4 included.
- **Path C**: multiplicity search on first half only; holdout touched ONCE per TF (guard `{tf}_final.json`); n_trials=24 frozen; measured_null K=2000, seed 20260904.

## 1. Hypothesis (as preregistered)
Persistence of M consecutive closes outside the Bollinger envelope (P, 2σ) is the signature of *informed, price-insensitive flow* (band-walk). Entry in the direction of the walk after the M-th close; SL=TP=a×ATR (RR=1 frozen), time-stop `hold` bars. Falsifiers: F1 no card lift>+4pp; F2 best z < H5 bound; F3 M≥2 persistence filter fails to beat the M=1 (touch-only) baseline.

## 2. Discover (first half, 19 TFs)
- **Survivors (7)**: H2, H3, H4, H6, H8, H12, D1.
- **NO-SURVIVOR (12)**: M1, M3, M4, M5, M6, M10, M12, M15, M20, M30 (10 minute TFs — **7th confirmation of the minute-TF cost law**), H1, W1.
- F3 in train: filter information-adding on H2 (+6.75 vs −0.55 M=1), H8, D1; **power-burning on H4/H6/H12** (M=1 baseline ≥ arm).

## 3. Final (holdout, single touch) — ALL 7 REJECT

| TF | cfg (P/M/hold/side) | train n/WR | hold n | WR | PF | lift | z | p_perm | exp (pip) | maxDD % | RQS2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H2 | 20/3/55/short | 215/59.07 | 189 | 49.21 | 0.877 | +3.50 | 0.97 | 0.167 | −4.13 | 19.19 | 1.7 |
| H3 | 55/2/144/long | 176/55.68 | 235 | 49.79 | 0.911 | −2.92 | −0.90 | 0.815 | −3.68 | 20.43 | 3.1 |
| H4 | 20/2/55/short | 195/55.38 | 161 | 48.45 | 0.870 | +3.49 | 0.89 | 0.187 | −6.53 | 14.68 | 1.5 |
| H6 | 55/3/55/both | 136/58.82 | 150 | 53.33 | 1.087 | +2.10 | 0.41 | 0.340 | +5.77 | 11.99 | 10.6 |
| **H8** | 55/3/55/long | 42/61.90 | 80 | 56.25 | 1.225 | +1.11 | 0.20 | 0.421 | +15.83 | 5.93 | **13.2** |
| H12 | 55/2/55/both | 81/60.49 | 101 | 49.50 | 0.924 | −1.91 | −0.31 | 0.620 | −5.20 | 12.71 | 2.2 |
| D1 | 55/2/55/both | 35/62.86 | 55 | 54.55 | 1.177 | +3.04 | 0.36 | 0.358 | +22.82 | 4.42 | 9.0 |

Best card H8 gates: H0✓ H1✗(PF 1.225<1.3) H2✓ H3✗(lift +1.11, z=0.20) H4✗ H5✗(z_obs 0.20 vs z_luck_bound 1.98) H6✗(calendar: 1 of 2 occupied buckets positive) H7✓ H8✓ H9✓ H10✓.
Per-side (H6/D1 both-cards): D1 long WR 62.5 lift +7.68 (n=16) vs short WR 33.3 lift −9.36; H12 short WR 41.2 — shorts negative again.

## 4. Failure analysis
1. **Predictions verified**: H8/H12/D1 (n=42/81/35) collapsed exactly as predicted (train edges +10.8/+9.6/+12.3 → holdout lift +1.1/−1.9/+3.0). **5th confirmation of the S91x small-n law in this block.**
2. **Decisive test H2 short (n=215, filter clearly adding in train)**: holdout WR 49.2 < breakeven 52.3, PF 0.88. Regime headwind (L-S921-4: shorts lose in the 2024–26 rally half) beat filter quality. Note lift is still +3.5pp because the short null_ref itself is only 45.7 — the filter *does* pick relatively better shorts, but relative skill on a losing side is not money.
3. **F3 falsified in holdout**: the persistence filter never produced z>1 anywhere. Band-walk of M=2–3 closes is *not* a stronger signature of informed flow than a single envelope touch on gold; what S965's ρ-shape filter achieved (z 1.8→3.1) the persistence-count filter did not.
4. **H6/H8/D1 economically positive but skill-unproven** (exp +6..+23 pip, PF 1.09–1.23, z ≤ 0.41) — same pattern as S922 H6/H8: residual ≈ secular gold drift, not the concept.
5. Minute TFs: 10× NO-SURVIVOR — cost law now 7× confirmed across S920–S923.

## 5. Eight-common-mistakes proof
1. Look-ahead: streak counts closes t−M+1..t only; Bollinger uses rolling window ending at t; selftest asserted spike at bar k does not alter features before k+1. 2. Data trap E-16: 18 TFs from mt5_full; H4 file span verified 15.6y before inclusion. 3. Multiplicity: n_trials=24 declared in prereg, passed to engine (H5 evaluated: z_luck_bound 1.98). 4. Holdout re-touch: guard files, one touch per TF, prediction committed first. 5. Survivor cherry-pick: fixed rule WR_train>breakeven & n≥30, applied before seeing holdout. 6. Cost: 3.3 pip spread applied in simulator; H9 at 2×spread evaluated. 7. Verdict manipulation: verdict taken verbatim from `compute_rqs2`; no notes edits. 8. Side pooling: sides reported separately; both-cards show short-side negatives explicitly.

## 6. Lessons
- **L-S923-1**: Persistence-count (band-walk M≥2) is not an information-adding filter on gold envelopes; the *shape/quality* of the event bar (S965 ρ) is. Future filters should measure event quality, not event repetition.
- **L-S923-2**: A filter that shows large relative lift on the short side (vs a null_ref <46%) still loses money in the 2024–26 half — lift and profitability must both be read; H1/H2 gates exist for this reason.
- **L-S923-3**: Small-n law (n<150) confirmed 5× in this block; H8/H12/D1 train edges >+9pp with n<100 should be treated as bait a priori.
- **L-S923-4**: Cost law for minute TFs: 7/7 layers × 10 TFs NO-SURVIVOR. Block S92x will not spend further minute-TF compute on RR=1 a×ATR geometries.

## 7. Official ledger entry
**S923 = REJECT (RQS2 = 13.2, best card H8 long P55/M3/hold55)** — family closed.
Block ledger: S920=REJECT(6.1) · S921=REJECT(16.1) · S922=REJECT(16.0) · S923=REJECT(13.2). Next: S924.

— Friedrich Hayek, S920–S929
