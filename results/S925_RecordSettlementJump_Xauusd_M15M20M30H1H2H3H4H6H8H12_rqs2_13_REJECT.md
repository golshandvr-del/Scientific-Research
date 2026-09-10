# S925 — Record Settlement Jump (Ordinal Close-to-Close Return Record, Drift-Aligned) — OFFICIAL VERDICT: REJECT (best RQS2 = 12.8, H4)

- **Layer number**: S925 (block S920–S929) · **Scientist**: Friedrich Hayek · **Date**: 2026-09-06
- **Judge**: RQS2 v2.6 (official engine, untouched — 11 veto gates, `R.compute_rqs2`)
- **Prereg**: `results/S925_PREREG_RECORD_SETTLEMENT_JUMP.md` (commit `aba8546b`, BEFORE any test)
- **Pre-final prediction**: `results/_scan_S925/PRE_FINAL_PREDICTION.md` (committed BEFORE holdout touch)
- **Harness**: `strategies/s925_record_settlement.py` (selftest PASSED: prev-max window 0 mismatches vs naive loop, no look-ahead; `prep()` asserts `src` ∈ `data/mt5_full` AND span ≥14y)
- **Data**: **all 19 TFs from `data/mt5_full/`** (15.59y; M1 14.34y export cap; H4 = official S908-derived `data/mt5_full/XAUUSD_H4.csv`). `src` recorded in every JSON. No data incident this layer.
- **Path C**: multiplicity search on first half only; holdout touched ONCE per TF (guard files); n_trials=24 frozen; geometry-matched measured_null K=2000, seed 20260906. Preregistered report-only F3-holdout diagnostic (other gate arm, same W/a/side) run once per TF, labelled, no card/verdict.

## 1. Hypothesis (as preregistered)
Only the settlement price transmits knowledge; the intrabar path is bargaining noise. A bar whose |close-to-close log return| is the **ordinal record** of the previous W bars (no ATR / z / distributional threshold — the dimension S918's *range* record left untested) is a knowledge-revelation event; aligned with the 60-day drift (S604 convention) it continues. Follow direction; SL=TP=a×ATR21 (RR=1), hold 55. Grid W{34,89}×gate{ungated,gated}×a{1.618,2.058}×side (24 trials).

## 2. Discover (first half)
- Survivors (10): M15, M20, M30, H1, H2, H3, H4, H6, H8, H12. NO-SURVIVOR (9): M1–M12 (7 minute TFs, cost law), D1, W1 (record events too sparse — F5).
- First family in this block where the concept's *ungated* arm also had positive train edge on H2–H12 (+2..+17pp), and where a card with **n≈200** (H6 both, WR 62.8, edge +11.8) existed.

## 3. Final (holdout, single touch) — ALL 10 REJECT

| TF | cfg (W/gate/a/side) | train n/WR | hold n | WR | PF | lift | z | exp (pip) | maxDD % | F3-holdout other gate WR (n) | RQS2 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| M15 | 89/gated/2.058/long | 456/55.70 | 697 | 46.63 | 0.706 | −3.42 | −1.81 | −5.33 | 72.59 | ungated 45.80 (1024) | 0.0 |
| M20 | 89/gated/2.058/long | 316/59.81 | 488 | 48.57 | 0.821 | −2.56 | −1.13 | −4.34 | 58.62 | ungated 46.96 (707) | 0.7 |
| M30 | 89/ungated/2.058/long | 496/56.45 | 511 | 48.73 | 0.825 | −2.88 | −1.30 | −4.62 | 44.89 | gated 47.16 (335) | 4.2 |
| H1 | 89/gated/1.618/long | 126/57.14 | 176 | 42.61 | 0.679 | −8.96 | −2.38 | −10.76 | 35.71 | ungated 44.40 (259) | 0.0 |
| H2 | 89/gated/2.058/long | 57/64.91 | 95 | 55.79 | 1.141 | +1.99 | 0.39 | +6.39 | 7.49 | ungated 58.82 (136) | 11.8 |
| H3 | 89/gated/2.058/both | 95/67.37 | 97 | 48.45 | 0.884 | −3.53 | −0.53 | −6.79 | 12.56 | ungated 46.50 (200) | 0.7 |
| **H4** | 89/gated/1.618/both | 77/72.73 | 63 | 57.14 | 1.235 | +5.34 | 0.64 | +11.53 | 5.49 | ungated 43.79 (153) | **12.8** |
| H6 | 34/ungated/2.058/both | **196**/62.76 | 230 | 48.70 | 0.889 | −1.20 | −0.30 | −7.62 | 16.56 | gated 56.07 (107) | 0.0 |
| H8 | 89/gated/2.058/both | 37/75.68 | 32 | 59.38 | 1.391 | +6.39 | 0.54 | +33.20 | 3.90 | ungated 55.00 (80) | 12.5 |
| H12 | 34/ungated/2.058/short | 56/66.07 | 66 | 36.36 | 0.546 | −7.32 | −1.20 | −73.29 | 19.07 | gated 61.11 (18) | 0.0 |

Per-side (both-cards): H6 long 58.4 / short 37.1; H4 long 60.9 / short 47.1; H8 long 63.6 / short 50.0; H3 long 49.3 / short 46.4. F4 fired: every both-card has long ≫ short.

## 4. Failure analysis
1. **The decisive card failed decisively.** H6 (n_train=196, the only n≈200 card with >+10pp edge in S920–S925) went to holdout WR 48.7 (< breakeven 51.3). This is the sharpest falsification of my block: **even n≈200 train edge is not protective when the event is ordinal-record based** — the S91x small-n law was necessary but never sufficient.
2. **Ordinal record ≠ informed shock.** A record over 34/89 bars is a *relative* measure: in calm regimes it fires on small moves that carry no information. The proven parallel families (S604/S950/S965/S919) all use an *absolute* scale (ATR multiple, z, BV) — they only fire on genuinely large moves. S918 (range record) and S925 (return record) now jointly show: on gold, **rank-records are the wrong measurement of "large"**. Hayek's "only settlement matters" did not rescue this; the distributional scale was the essential ingredient, not the price field.
3. **F3-holdout (report-only)**: gated beat ungated in 6/10 TFs on holdout WR (M15, M20, H4 +13pp, H6 +7pp, H8, H12), lost in 3 (M30, H1, H2), tie 1. Drift alignment *does* add information out of sample on the higher TFs — consistent with S604/S966/S919 — but it cannot rescue a base event with no edge (echo of S966's "gate on a dead base performs no miracle").
4. **Predictions**: small-n collapses (H2/H8/H12) confirmed (7th time); shorts collapsed (H12 36.4; block record now **0/10 shorts**); minute TFs negative as predicted. My P(ACCEPT)=25% at H6 was too optimistic — the card did not merely fall short of z, it lost money.
5. Costs: M15/M20/M30 maxDD 45–73% — the minute-TF cost law (9th confirmation) now also shows the *drawdown* mechanism, not only WR erosion.

## 5. Eight-common-mistakes proof
1. Look-ahead: record window is [t−W, t−1] (current bar excluded from the max); drift gate uses close[t−1] vs close[t−1−K]; entry open t+1; selftest asserted a spike at bar 3001 leaves events ≤3000 unchanged and *creates* a long record at 3001. 2. E-16: runtime assertion `mt5_full` in `src` + span ≥14y for all 19 TFs. 3. Multiplicity: n_trials=24 prereg'd and passed to engine. 4. Holdout: single official touch per TF; the extra F3 simulation was preregistered (§4), labelled report-only, produced no card. 5. Survivor rule fixed before holdout. 6. Costs: 3.3 pip in simulator; H9 evaluated. 7. Verdict verbatim from `compute_rqs2`. 8. Sides reported separately; no pooling.

## 6. Lessons
- **L-S925-1**: Rank/ordinal records (range: S918; return: S925) are not valid "large shock" detectors on gold. Use absolute distributional scales (ATR-multiple, z, BV). Closed for the block.
- **L-S925-2**: n_train≈200 with +12pp edge can still fully collapse when the event definition is regime-relative. The n<150 law is a necessary filter; the *sufficient* condition is an event whose meaning is stable across volatility regimes.
- **L-S925-3**: Holdout F3 confirmed the 60-day drift gate adds information at H4–H12 even on a dead base (+7..+13pp WR) — the gate is real, the base was wrong. Any remaining S92x layers should be built on a base with absolute scale, then gated.
- **L-S925-4**: Shorts 0/10 in the 2024–26 half across S921–S925. Future block cards: long or both only unless a short-specific mechanism is preregistered.

## 7. Official ledger entry
**S925 = REJECT (RQS2 = 12.8, best card H4 both W89/gated/a1.618)** — family closed.
Block ledger: S920=REJECT(6.1) · S921=REJECT(16.1) · S922=REJECT(16.0) · S923=REJECT(13.2) · S924=REJECT(10.5) · S925=REJECT(12.8). Next: S926.

— Friedrich Hayek, S920–S929
