# S924 — Knowledge Signal-to-Noise (Volatility-Scaled Momentum Threshold Cross) — OFFICIAL VERDICT: REJECT (best RQS2 = 10.5, D1)

- **Layer number**: S924 (block S920–S929) · **Scientist**: Friedrich Hayek · **Date**: 2026-09-05
- **Judge**: RQS2 v2.6 (official engine, untouched — 11 veto gates, `R.compute_rqs2`)
- **Prereg**: `results/S924_PREREG_KNOWLEDGE_SIGNAL_TO_NOISE.md` (commit `686a5649`, BEFORE any test)
- **Pre-final prediction**: `results/_scan_S924/PRE_FINAL_PREDICTION.md` (committed BEFORE holdout touch)
- **Harness**: `strategies/s924_signal_to_noise.py` (selftest PASSED: SNR vs naive loop 3.6e-14, no look-ahead, runtime E-16 span guard ≥14y in `prep()`)
- **Data**: **all 19 TFs from `data/mt5_full/`** — 18 files span 15.59y (M1 = 5,000,000 bars = 14.34y, MT5 export cap); H4 from `data/mt5_full/XAUUSD_H4.csv` (S908-derived from official H1, bit-exact validated against official H8; the old `data/XAUUSD_H4.csv` was deleted upstream mid-run — H4 was re-discovered on the official file, **same card selected**, then finalised once). `src` recorded in every JSON.
- **Data incident (documented)**: a first partial discover run happened while `mt5_full/*.csv.gz` were still unpacked after a sandbox reset → loader fell back to short `data/*.csv`; the span guard fired on M5/M15, the partial run was **purged from git** before any holdout touch, files unpacked, all 19 TFs re-run. No holdout was touched in the bad run.
- **Path C**: multiplicity search on first half only; holdout touched ONCE per TF (guard files); n_trials=24 frozen; geometry-matched measured_null K=2000, seed 20260905.

## 1. Hypothesis (as preregistered)
Price is a telecommunication system; K-bar drift is the *message*, K-bar realised volatility the *noise*. When SNR = drift_K / (σ_K·√K) first crosses θ, the channel carries a high-fidelity message → continuation. Entry open of next bar, SL=TP=a×ATR21 (RR=1), hold 55. Grid K{55,144}×θ{1.0,1.618}×a{1.618,2.058}×side (24 trials). F3 diagnostic: raw-drift sign cross (plain TSM) with same geometry.

## 2. Discover (first half)
- Survivors (8): H1, H2, H3, H4, H6, H8, H12, D1. NO-SURVIVOR (11): M1–M30 (10 minute TFs — **8th confirmation of the cost law**), W1.
- **F3 on train PASSED in 7/8 survivors**: SNR normalisation added +7..+15pp edge over raw-drift sign crosses (which are mostly *negative* on gold: plain TSM sign flips lose at these horizons). Failed only at H12 (raw drift +13.4 > SNR +7.8).

## 3. Final (holdout, single touch) — ALL 8 REJECT

| TF | cfg (K/θ/a/side) | train n/WR | hold n | WR | PF | lift | z | exp (pip) | maxDD % | RQS2 |
|---|---|---|---|---|---|---|---|---|---|---|
| H1 | 144/1.618/1.618/short | 165/56.97 | 147 | 47.62 | 0.796 | +1.04 | 0.25 | −5.71 | 19.88 | 0.4 |
| H2 | 55/1.618/1.618/short | 158/56.96 | 138 | 44.20 | 0.726 | −1.33 | −0.31 | −11.55 | 23.94 | 0.0 |
| H3 | 144/1.0/2.058/long | 106/59.43 | 184 | 51.09 | 0.984 | −3.88 | −1.06 | −0.29 | 24.38 | 0.7 |
| H4 | 55/1.0/2.058/short | 147/59.18 | 127 | 41.73 | 0.679 | −3.09 | −0.70 | −24.43 | 22.74 | 0.0 |
| H6 | 144/1.618/1.618/long | 30/63.33 | 77 | 55.84 | 1.207 | +0.64 | 0.11 | +12.54 | 7.44 | 7.5 |
| H8 | 144/1.618/1.618/both | 40/65.00 | 70 | 51.43 | 1.010 | −2.96 | −0.44 | +1.07 | 6.38 | 6.6 |
| H12 | 55/1.0/2.058/short | 53/58.49 | 47 | 38.30 | 0.604 | −4.49 | −0.62 | −60.56 | 13.19 | 0.0 |
| **D1** | 144/1.0/1.618/both | 34/52.94 | 36 | 52.78 | 1.022 | −0.70 | −0.07 | +12.66 | 5.52 | **10.5** |

Per-side (both-cards): H8 long 51.6 / short 50.0; D1 long 55.2 / short 42.9. No card with lift > +4pp (F1 fired). No z > 0.3 (F2 fired). Shorts collapsed hardest (F4 fired: H2/H4/H12 shorts WR 38–44).

## 4. Failure analysis
1. **Train F3 pass was not portable.** The SNR filter's train advantage over raw drift (+7..+15pp) evaporated entirely out of sample: every card's lift is within ±4pp of zero. A diagnostic that passes in train on the *same* half the grid was searched on is itself subject to selection — F3 must be evaluated on holdout too (lesson for S925+).
2. **All predictions confirmed**: small-n H6/H8/D1/H12 collapsed (6th confirmation of the S91x law); shorts H1/H2/H4 failed in the rally half (L-S921-4); H3 long (the "most plausible" card) went to WR 51.1 = breakeven. Prediction "ALL REJECT, best 15–30" was slightly optimistic — best was 10.5.
3. **Why the concept fails on gold**: vol-scaling *lowers* thresholds in calm regimes and *raises* them in violent ones. On gold, the profitable continuation events (S604/S950/S965/S966) are precisely the violent ones — shocks. Normalising by noise therefore *filters out* the informative shocks and *admits* calm-regime drifts that then mean-revert. The Hayekian metaphor was inverted: on gold the noise *is* the message.
4. Minute TFs: 10× NO-SURVIVOR — cost law 8× confirmed.

## 5. Eight-common-mistakes proof
1. Look-ahead: SNR uses closes ≤ t; entry at open t+1; selftest asserted a spike at bar 3001 leaves all events ≤ 3000 unchanged. 2. E-16: every TF from mt5_full with runtime span guard; incident with short files documented and purged pre-holdout; H4 re-run on official derived file. 3. Multiplicity: n_trials=24 prereg'd and passed to engine. 4. Holdout: single touch per TF, guard files; prediction committed first. 5. Survivor rule fixed before holdout (WR>breakeven & n≥30). 6. Costs: 3.3 pip spread in simulator; H9 at 2× spread. 7. Verdict verbatim from `compute_rqs2`. 8. Sides reported separately; no pooling.

## 6. Lessons
- **L-S924-1**: Volatility-normalised momentum is anti-informative on gold at H1–D1: it discards the shock events that carry gold's continuation edge. Do not revisit vol-scaled TSM as an entry event.
- **L-S924-2**: A train-side F3 pass (concept beats its naive baseline) is *not* evidence — it shares the selection bias of the grid. From S925 on, diagnostics of "does the filter add information" will be preregistered as *holdout* comparisons.
- **L-S924-3**: Shorts in the 2024–26 half are now 0/9 across S921–S924 — any future short card in this block needs a separate, stronger prior justification.
- **L-S924-4 (operational)**: after a sandbox reset, unpack `data/mt5_full/*.csv.gz` BEFORE any run and assert `src` contains `mt5_full`; the loader's silent fallback to `data/*.csv` is the E-16 trap in action.

## 7. Official ledger entry
**S924 = REJECT (RQS2 = 10.5, best card D1 both K144/θ1.0/a1.618)** — family closed.
Block ledger: S920=REJECT(6.1) · S921=REJECT(16.1) · S922=REJECT(16.0) · S923=REJECT(13.2) · S924=REJECT(10.5). Next: S925.

— Friedrich Hayek, S920–S929
