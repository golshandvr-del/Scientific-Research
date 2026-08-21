# S611 — VWAP Confluence Momentum (S153) Full-Data Rejudge — XAUUSD M5 — RQS2 v2.6

**Verdict: REJECT — score 11.4 / 100**
**Judge**: Évariste Galois (decade S610–S619)
**Date**: 2026-08-21 | **Prereg**: `results/S611_PREREG_VWAP_CONFLUENCE_FULLDATA_REJUDGE.md` (commit 7de1abe1, committed BEFORE any decisive number)
**Adjudicator**: `strategies/s611_vwap_rejudge.py` | **Evidence**: `results/_s611_vwap/{repro_short.json, full_verdict.json, full_trades.csv, mtf/*.json}`

---

## 1. What was judged

The archive strategy **S153 GoldVWAPConfluenceMomentum** (`strategies/s153_gold_vwap_confluence_momentum.py`,
archive result `results/GoldVWAPConfluenceMomentum_NetProfit_206050.md`) was built and celebrated on the
**SHORT dataset** (`data/XAUUSD_M5.csv`, 2023-09-18 onward ≈ 2.9y) — the classic **E-16 trap** window.
It had never been judged by RQS2 on full data. S611 = zero-search rejudge of the **frozen** config on
`data/mt5_full` M5 (15.59 years).

**Frozen config (no degree of freedom):**
`z_entry=1.5, ema_trend=200, atr_mult=0.5, cooldown=48, SL=80 pip, TP=700 pip, BE=6, trail=6, mh=48, LONG-only`
Signal: daily-anchored VWAP z-score > 1.5 ∧ close > EMA200 ∧ green candle ∧ range ≥ 0.5×ATR14.

**Budget (locked in prereg): n_trials = 200** (archive 192-grid + manual cooldown pass + this rejudge + margin).
K_PERM = 500, seed = 20260819, split_bar = 70%, spread = 3.3 pip, engine-semantics table validated **bit-exact**
against `engine/scalp_engine.simulate_trades` on both short and full data (guard against S811-style divergence).

## 2. Health gates (both PASSED before adjudication)

| Gate | Requirement | Result |
|---|---|---|
| A: Archive reproduction | n=2221, net≈+$14,135 on short data | ✅ exact: n=2221, net=+14135 |
| B: Vectorized table vs official engine | bit-exact sb/pnl on short AND full data | ✅ match=True / True |

## 3. Decisive full-data verdict (15.59y M5, src=mt5_full)

**n = 11,284 trades | WR = 44.29% | uncond = 43.04% | perm_mean = 43.28% (sd 0.473) | lift ≈ +1.0 pp**

| Gate | Pass | Note |
|---|---|---|
| H0 sanity | ✅ | |
| H1 economics | ❌ | **PF = 1.097 < 1.3** |
| H2 sample size | ✅ | n=11284 |
| H3 luck vs null | ❌ | z vs perm null far below bar |
| H4 holdout | ❌ | |
| H5 stability | ❌ | |
| H6 calendar | ❌ | |
| H7 cost realism | ✅ | |
| H8 regime robustness | ❌ | see §4 |
| H9 | ❌ | |
| H10 | ❌ | |

**Score 11.4 → REJECT.** The archive's +$206k/+$14k headline was a regime artifact of the short window.

## 4. Regime decomposition — REGIME-ONLY case #3

From `full_trades.csv` (11,284 trades with bar_dt):

| Regime | n | WR | net (pip) |
|---|---|---|---|
| **PRE 2023-09** | 9,011 | 40.71% | **−10,612** |
| **POST 2023-09** | 2,273 | 58.51% | **+14,557** |

Yearly: 2012–2019 **all negative** (WR as low as 30.4%); 2024/2025/2026 = +1,624 / +4,912 / +8,146 pip.

This is the **third documented REGIME-ONLY pattern** on this site:
1. S355 → S530 (rejudged, killed)
2. S334 → S580 (rejudged, killed)
3. **S153 → S611 (this case)**

**Law reinforced**: any strategy validated only on post-2023 gold data expresses the 2023–2026 gold
super-bull, not skill. Full-data rejudge is mandatory before any deployment claim.

## 5. Prereg settlement (P1–P5)

| Prediction | Outcome |
|---|---|
| P1: structural survival probability ~25% | ✅ correctly low — REJECT |
| P2: REGIME-ONLY (~60% prior) | ✅ **CONFIRMED** — exactly the S355/S334 signature |
| P3: H6/H10 calendar tilt | ✅ both failed |
| P4: TFs ≥ H3 structurally zero signals (VWAP z needs ≥10 intraday bars) | ✅ confirmed (H3..W1 = 0 signals) |
| P5: M1 cost-dead | ✅ confirmed spectacularly (§6) |

5/5 predictions correct. The prereg model of this strategy family was accurate.

## 6. Multi-TF law — full 19-TF reporting table

Reporting only (frozen rule; **no adjudication budget spent**, per prereg §6; the 19 looks are logged and
must be charged to any future prereg that uses them). M1 computed OOM-safe
(`strategies/s611_m1_slim.py`: chunked read, day=time//86400).

| TF | n | WR% | net (pip) | WR h1/h2 | net h1/h2 |
|---|---|---|---|---|---|
| M1 | 48,993 | 31.24 | **−123,568.7** | 26.53 / 35.69 | −73,569 / −50,000 (cost-death, P5) |
| M3 | 18,739 | 39.35 | −11,718.6 | 34.60 / 43.84 | −18,964 / +7,246 |
| M4 | 13,984 | 42.43 | −2,895.9 | 37.12 / 47.42 | −11,126 / +8,230 |
| M5 | 11,284 | 44.29 | +3,945.6 | 38.27 / 49.90 | **−8,134** / +12,080 |
| M6 | 9,495 | 46.08 | +9,756.1 | 40.33 / 51.45 | −5,216 / +14,972 |
| M10 | 5,813 | 50.16 | +8,364.9 | 45.78 / 54.16 | −215 / +8,580 |
| M12 | 4,946 | 52.99 | +12,802.5 | 48.54 / 57.05 | +1,022 / +11,781 |
| M15 | 3,936 | 55.77 | +20,460.6 | 50.80 / 60.29 | +2,921 / +17,539 |
| M20 | 3,058 | 56.34 | +11,315.7 | 52.23 / 60.09 | +1,258 / +10,057 |
| M30 | 2,088 | 59.00 | +17,978.4 | 57.02 / 60.71 | +6,519 / +11,459 |
| **H1** | **1,070** | **63.74** | **+13,831.8** | **64.89 / 62.78** | **+4,234 / +9,598** |
| H2 | 468 | 63.68 | +9,609.9 | 63.29 / 63.98 | +1,269 / +8,341 |
| H3–W1 | 0 | — | — | — | structural zero-signal (P4) |

(Exact per-TF JSON: `results/_s611_vwap/mtf/<TF>.json`.)

**Monotone structure**: edge quality rises with TF until the structural boundary. On M5 the noise and
cost drown the signal; on H1 the same frozen rule shows WR 63.74 with **both halves positive** —
unlike M5 whose first half loses. This is a habitat statement, not a verdict.

## 7. 🔭 LEAD recorded: H1 habitat (for a future prereg)

**H1 | n=1070 | WR 63.74 | net +13,832 pip | halves 64.89/62.78, both positive.**
NOT adjudicated here. Any future prereg (e.g. S612) that adjudicates H1 must:
- count an honest n_trials including these **19 MTF looks** plus the S611 rejudge lineage,
- pass full RQS2 with permutation null on H1,
- survive the pre-2023 regime test explicitly (H1 halves both positive is encouraging but not proof).

## 8. Laws & mistake-catalog compliance

- **E-16 (short-window trap)**: this case IS the E-16 autopsy — third confirmed instance.
- **Zero-search path**: config frozen from archive; prereg before any decisive number; budget honest (n_trials=200).
- **Engine-fidelity**: bit-exact table validation (anti-S811).
- **Multi-TF law**: all 19 TFs reported separately, per-TF checkpoint commits.
- **Incremental law**: OOM-safe M1, per-TF processes, checkpoint commits (7de1abe1, 72b396ba, 0cb4acb3).
- **No interference**: territory verified virgin via census + prereg greps before claiming.
- **TP>SL budget**: untouched — frozen config judged as-is; improvement layers not opened because the
  structural cause of death (regime dependence) is not filterable by entry filters.

## 9. Eternal-death assessment

The **M5 deployment claim** of S153 is dead: the edge on M5 is a regime artifact (H1 gate PF=1.097,
pre-2023 net −10.6k pip). No entry filter can rescue a signal whose entire economics flip sign by era —
filters select bars, they cannot select decades a trader hasn't lived yet.
**However**, the strategy *family* is not eternally dead: the H1 habitat is a live, recorded lead.

**Final: S611 = REJECT 11.4. Archive S153 M5 claim falsified on full data. REGIME-ONLY case #3. H1 lead preserved for a properly budgeted future prereg.**
