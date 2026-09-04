# S923 — PRE-FINAL PREDICTION (committed BEFORE any holdout touch)

Date: 2026-09-04 · Prereg commit: 4876f7be · Grid frozen, n_trials=24.

## H4 status (E-16 re-verification)
Unlike S921/S922 assumption, `data/XAUUSD_H4.csv` was **verified this time**: spans
1294012800 (2011-01) → 1784188800 (2026) = **15.6y, 23,755 bars — FULL SPAN**, same as
mt5_full files. Precedent: S526 ACCEPT explicitly used this file at 15.53y. Per prereg
language ("if H4 discover silently loads SHORT csv → exclude"), the exclusion condition
does NOT hold → **H4 is INCLUDED in final** (7 survivor cards).

## Survivors → final (7): H2, H3, H4, H6, H8, H12, D1
NO-SURVIVOR (12): M1–M30 (10 minute TFs — cost law, 7th confirmation), H1, W1.

| TF | card | n_train | WR | edge | M1-baseline edge (p20/p55) | flags |
|---|---|---|---|---|---|---|
| H2 | p20 m3 h55 **short** | 215 | 59.07 | +6.75 | −0.55 / +1.82 | filter adds strongly; SHORT side = L-S921-4 risk in 2024–26 rally half |
| H3 | p55 m2 h144 long | 176 | 55.68 | +3.82 | +1.46 / +2.61 | modest filter gain; thin edge |
| H4 | p20 m2 h55 short | 195 | 55.38 | +3.80 | +3.54 / **+4.81** | **F3 warning: p55 M1 baseline BEATS the arm → persistence filter power-burning here**; short risk |
| H6 | p55 m3 h55 both | 136 | 58.82 | +7.56 | +3.63 / **+7.66** | F3 warning: p55 M1 baseline ≈ arm (no info added); n<150 noise flag |
| H8 | p55 m3 h55 long | 42 | 61.90 | +10.83 | +3.96 / +3.52 | **n=42 ≪ 150 → S91x law: presumptively selection noise** |
| H12 | p55 m2 h55 both | 81 | 60.49 | +9.64 | +5.26 / **+9.89** | F3 warning + n<150 noise flag |
| D1 | p55 m2 h55 both | 35 | 62.86 | +12.28 | −2.62 / +6.03 | **n=35 ≪ 150 → presumptively noise** (S922-H12 déjà vu) |

## Predictions (accountability, before holdout)
1. **H8/H12/D1 (n=42/81/35)**: expect train edge to collapse toward 0 in holdout — the
   S91x small-n law has been confirmed 4× in this block. These are the bait cards.
2. **H2 short (n=215)**: the only card where the persistence filter clearly ADDS
   information vs M=1 (+6.75 vs −0.55). But it is a SHORT card and the holdout half is
   the 2024–26 gold rally — L-S921-4 predicts holdout deterioration. This is the
   decisive test: filter-quality vs regime-headwind.
3. **H3 long (n=176)**: thin (+3.82); expect holdout edge ≈ +0..3pp, z < 2 → REJECT.
4. **H4/H6**: F3 warnings — persistence filter did not beat M=1 baseline; even economic
   survival would credit the *envelope*, not the *persistence* concept.
5. **Family expectation**: most likely ALL REJECT with best score 15–30; only path to
   ACCEPT is H2 surviving both regime headwind and z≥3.09 — prior probability low.
6. F3 verdict (train): persistence filter is information-adding on H2/H8/D1, power-burning
   on H4/H6/H12 — mixed, weaker than S965's clean P1 pass. Will report honestly.

Holdout will now be touched ONCE per surviving TF. Guard files enforce single touch.
— Hayek, S923
