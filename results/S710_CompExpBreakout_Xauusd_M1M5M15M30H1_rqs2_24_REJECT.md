# S710 — Compression→Expansion Breakout (chop_fib_55 squeeze + 13-bar channel break) — XAUUSD — **REJECT**

- **Scientist**: Muhammad al-Khwarizmi (block S710–S719)
- **Prereg**: `results/S710_PREREG_compression_expansion_breakout.md` (committed 6ce8e14b BEFORE any test)
- **Judge**: `strategies/s710_compression_expansion.py` + `strategies/s710_m1_lean.py` (M1 memory-lean, parity-gated) + `strategies/s710_pool.py` (pool rescue)
- **Engine**: `engine/rqs2.compute_rqs2` v2.6 — all verdicts machine-produced, none hand-written
- **Seed**: 20260805 | n_trials=7 (cards), 8 (pool) | allow_overlap=False | split=70% quantile of entry times

## Mechanism (frozen in prereg)
Volatility compression (`chop_fib_55 ≥ 61.8`, shift 1) followed by 13-bar channel breakout (shift 1).
SL = 1.000×ATR(21), TP = 1.618×SL (TP≥SL ✓), hold = hold_bars_for(tf, 24h). All parameters Fibonacci/golden, non-round.

## Verdict table (engine output, verbatim)

| Card | src | n | WR | PF | lift vs null | RQS2 | Verdict |
|---|---|---|---|---|---|---|---|
| M1 | data/mt5_full/XAUUSD_M1.csv | 7716 | 32.6% | 0.28 | null=None¹ | 0.0 | **REJECT** |
| M5 | data/mt5_full/XAUUSD_M5.csv | — | — | 0.53 | −0.7pp | 0.0 | **REJECT** |
| M15 | data/mt5_full/XAUUSD_M15.csv | — | — | 0.63 | −0.5pp | 1.2 | **REJECT** |
| M30 | data/mt5_full/XAUUSD_M30.csv | — | — | 1.21 | +11.2pp (z=2.1) | 12.7 | **REJECT** |
| H1 | data/mt5_full/XAUUSD_H1.csv | ~90 | — | — | +19.96pp (z=2.36) | 27.9 | **POWER-LIMITED** |
| H4 (info) | data/XAUUSD_H4.csv | 15 | — | — | — | 24.3 | REJECT (n too small) |
| D1 (info) | data/mt5_full/XAUUSD_D1.csv | — | — | — | — | 13.7 | REJECT |
| **POOL {H1,M30}** | pooled, FIFO conc=1 | **227** | **51.5%** | **1.36** | **+13.42pp, z=3.00** | **23.8** | **REJECT** |

¹ M1: permutation null computationally infeasible in the 985MB sandbox (hold=1440 bars × 7716 trades × 500 perms; 3 OOM kills).
Judged honestly with `null=None` → H3/H4/H5 UNKNOWN; economic gates (exp=−3.24pip, PF=0.28) decisive on their own. Absence of a control was NOT counted as evidence.

## Pool autopsy (the near-miss)
- Engine line: `S710_CompExp_POOL | REJECT RQS2= 23.8 | n= 227 WR=51.54% PF=1.36 lift= +13.42pp z= 3.0 | H0:✓ H1:✓ H2:✓ H3:✗ H4:✓ H5:✓ H6:✓ H7:✗ H8:✗ H9:✓ H10:✓`
- **H3 ✗**: z=3.00 vs required 3.09 (p_perm=0.00136 vs ≤0.001) — missed by 0.09σ.
- **H7 ✗**: OOS WR=45.6% passed wr_req=42.6% but OOS PF=1.156 too weak.
- **H8 ✗ (economic)**: maxDD=13.47% > 8.0% cap (MAXDD_MAX_PCT, engine/rqs2.py:135) — this alone kills POWER-LIMITED eligibility, so no rescue verdict was possible even with H3 marginal.
- Pool judged on artificial 5-min grid axis (S431 pattern: avoids BUG-QUANT and BUG-SPAN), holdout_mask at 70% quantile of trade entry times (BUG-SPLITDIR lesson), H10 close sampled with `searchsorted(...,'right')-1` (no future price).

## Side findings (permanent value for the database)
1. **BUG-EPOCH (new, documented)**: `fd.load_fast()['time']` is unix **seconds** (int64). `astype('datetime64[ns]')` directly interprets them as nanoseconds → everything collapses to Jan 1970. Correct: `astype('datetime64[s]').astype('datetime64[ns]')`. Fixed in `strategies/s710_pool.py`.
2. **Parity gate caught a real look-ahead**: `scipy.ndimage.maximum_filter1d` needs `origin=+(p-1)//2` for the past-looking window `[i−p+1, i]`; the negative sign is future-looking. Bit-equality vs official `indicator_bank` on a 200k-bar M15 slice proved the fix (chop/hh13/ll13/atr/signals all identical).
3. **Confirmation of the S692 geometry law**: on M1/M5 the mechanism's raw lift is swallowed by spread/cost geometry (SL≈few pips vs ~3.3pip cost) — compression-breakout skill, if any, only survives from M30 upward.
4. Compression→expansion has a genuine but **glass-ceilinged** positive tendency on H1 (+20pp lift, z=2.36, only ~5.5 signals/year) — too few trades for H3 power, and pooling with M30 both diluted PF and blew the maxDD cap.

## Proof: the 8 common mistakes were avoided
| # | Mistake | How avoided |
|---|---|---|
| 1 | Look-ahead | All signals shift(1); parity gate actively caught & fixed a scipy origin look-ahead; H10 price via right-searchsorted−1 |
| 2 | Survivorship/cherry-pick | Full 15.6y `data/mt5_full/`; all family TFs {M1,M5,M15,M30,H1} judged, none dropped |
| 3 | Multiplicity | Prereg Path B committed BEFORE test; n_trials=7 declared to engine; single frozen parameter set |
| 4 | Hand-written verdicts | Every verdict from `compute_rqs2`; JSONs archived in `results/_scan_S710/` |
| 5 | Overlap double-count | allow_overlap=False; pool re-FIFO'd on calendar (concurrency=1) |
| 6 | No null control | Measured permutation nulls (K=500 M5, K=2000 others) with the layer's OWN geometry via queue_rr; M1 honestly null=None with H3 UNKNOWN |
| 7 | Round-number params | 55, 61.8, 13, 21, 1.000, 1.618 — Fibonacci/golden throughout |
| 8 | TP<SL | TP=1.618×SL ≥ SL by construction; queue_rr shield `tp=max(rr·sl, sl)` |

## Eternal death registered
The exact combo — chop_fib_55≥61.8 compression + 13-bar breakout + SL=1.000×ATR(21) + TP=1.618×SL + 24h hold on XAUUSD {M1,M5,M15,M30,H1} and its {H1,M30} pool — is **dead forever**. Do not retest.

## Next
Per standing law: brief report → git fetch/review new layers → S711 (new virgin mechanism, same block).
