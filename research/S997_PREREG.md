# S997 PREREG — VolumeClockFreshRecord (XAUUSD, volume bars K=12 from M5) — Lagrange decade S990–S999

**Committed BEFORE any second-half (holdout) number.** Route C.

## Hypothesis (Clark 1973 / Ané–Geman 2000 — subordinated process)
The market beats in *volume time*, not clock time. Fresh price records (S526 rule: close > max(close[t−W..t−1]), first bar only;
mirror for lows) sampled on **volume bars** (each bar closes when cumulative M5 volume ≥ median(daily volume of previous 20 days)/K, causal)
should be more informative than the same rule on clock bars of matching resolution.
No layer in the repo has built volume bars (S856 left only a variance-clock PREREG without verdict).

## Exploration (first half of M5 only, 2011-01 → 2018-11) — `research/s997_explore/volume_clock.json`, 48 cells
- K∈{6,12,24} (≈H4/H2/H1 resolution) vs clock controls {H4,H2,H1}; W∈{55,90}; FH-long / FL-short; rr∈{1.0,1.5}.
- **P1 (volume clock > clock) FAILS at K=6** (H4 clock FL-short +7.3/+7.8pp vs K6 +4.9/+5.7). Mild pass at K=12 (W90 rr1.5: long +5.23 vs H2 +4.97; short +5.61 vs H2 +3.87) and K=24 (+3.7 vs +1.5). No cell z ≥ 2.5.
- Honest reading: volume sampling does not transform the fresh-record edge; at best a marginal gain at K=12.

## Frozen rule (no free parameter remains)
- Volume bars K=12 from `data/mt5_full/XAUUSD_M5.csv` second half; threshold = median(daily vol, previous 20 days)/12 (min_periods 10).
- W = 90; LONG on fresh high (close > max(close[t−90..t−1]) and not on t−1); SHORT on fresh low (mirror). Both sides in one series (symmetric rule, one simulation, allow_overlap False).
- SL = 1.5 × median(rolling-mean TR100)/0.1 pip on the holdout volume bars (geometry only); TP = 1.5 × SL. max_hold 40 bars.
- Null per side: hardest unconditional stride {3,7,13}; permutation K=500 unconditional, seed 997997. split_bar = 0.70·len.
- n_trials honest = 48 (cells) + 2 (K, W freezing) = **50**.

## Prediction
- Expected n ≈ 600–750 (both sides), lift +3…+5pp → **POWER-LIMITED or REJECT** (z ≈ 2–3, p_perm > 0.001 likely). ACCEPT would require lift ≥ +6pp at n ≥ 650.
- If lift < +2pp → volume-clock family CLOSED for the decade.

One run only. Verdict MD: `results/S997_VolumeClockFreshRecord_Xauusd_VOLK12_rqs2_<score>_<verdict>.md`.
