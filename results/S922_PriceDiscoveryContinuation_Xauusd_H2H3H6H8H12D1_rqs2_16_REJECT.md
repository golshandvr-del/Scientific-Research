# S922 — Price-Discovery Continuation (Donchian Breakout as Price-Discovery Event) — OFFICIAL VERDICT: REJECT (best RQS2 = 16.0)

- **Layer number**: S922 (block S920–S929)
- **Prereg**: `results/S922_PREREG_PRICE_DISCOVERY_CONTINUATION.md` (commit 6ce73510, pushed BEFORE any test)
- **Harness**: `strategies/s922_price_discovery.py` (selftest PASSED: rolling_extreme bit-exact vs `rolling(p).max().shift(1)` + explicit no-look-ahead assertion)
- **Engine**: RQS2 v2.6 (11 gates), Path C multiplicity, measured_null K=2000, SEED=20260830
- **Data**: `data/mt5_full/` ONLY (15.6y). E-16 trap avoided.
- **Symbol**: XAUUSD. Spread 3.3 pip (0.33$/oz), commission 0, RR=1 frozen.

## 1. Hypothesis (Hayekian framing)
When price breaks out of its P-bar Donchian channel, the market enters a *price-discovery*
episode: no recent transaction history exists at these levels, so the dispersed-knowledge
aggregation process is incomplete and price should continue in the breakout direction until
a new consensus forms. Event: state-cross of close above HH(P) (mirror for shorts), current
bar excluded from the extreme (no look-ahead). Grid: P{55,144} × a{1.618,2.058} × hold{55,144}
× side{L,S,B} = 8 configs/TF, n_trials=24.

## 2. E-16 / H4 handling
`data/mt5_full/` contains no H4 file → H4 discover silently ran on the short (2.8y) `data/`
csv. Per standing protocol, **H4 was excluded from adjudication pre-final** and documented in
`results/_scan_S922/PRE_FINAL_PREDICTION.md`. No holdout was touched for H4.

## 3. Discover phase (19 TFs, first half only)
- **NO-SURVIVOR** (WR_train ≤ costed breakeven or n_train < 30): M1, M3, M4, M5, M6, M10,
  M12, M15, M20, M30, H1, W1 — twelve TFs. All minute TFs drowned in costs again
  (**6th consecutive confirmation** of the minute-TF cost law in this block).
- **Excluded**: H4 (E-16).
- **Survivors → final**: H2, H3, H6, H8, H12, D1 (6 cards).
- Pre-final prediction (committed BEFORE holdout touch): H12 flagged as classic overfit
  (train WR=69.2 with n=39); fate rests on H2/H3/H8; short-side risk noted per L-S921-4.

## 4. Final (holdout) results — ALL 6 REJECT

| TF | p | a | hold | side | train n/WR | hold n | WR% | PF | lift pp | z | p_perm | exp pip | maxDD% | RQS2 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H2 | 144 | 2.058 | 55 | short | 205/54.63 | 157 | 50.32 | 0.924 | +5.02 | 1.26 | 0.103 | −3.22 | 10.25 | 2.8 | REJECT |
| H3 | 55 | 2.058 | 144 | long | 246/54.88 | 401 | 52.37 | 1.030 | −0.18 | −0.07 | 0.528 | +2.24 | 18.98 | 2.4 | REJECT |
| **H6** | 144 | 1.618 | 55 | long | 77/61.04 | 169 | 59.76 | 1.405 | +5.38 | 1.40 | 0.080 | +23.31 | 7.89 | **16.0** | REJECT |
| H8 | 144 | 1.618 | 144 | both | 118/61.02 | 162 | 57.41 | 1.282 | +5.10 | 1.11 | 0.133 | +20.44 | 9.31 | 10.8 | REJECT |
| H12 | 144 | 1.618 | 55 | short | 39/69.23 | 18 | 50.00 | 0.967 | +8.25 | 0.71 | 0.239 | −3.30 | 4.01 | 7.9 | REJECT |
| D1 | 55 | 1.618 | 55 | short | 35/54.29 | 17 | 41.18 | 0.684 | −1.36 | −0.11 | 0.545 | −54.10 | 2.76 | 2.0 | REJECT |

Gate detail for best card (H6): H0✓ H1✓ H2✓ **H3✗** (lift +5.38 but z=1.40 ≪ 3.09,
p_perm=0.080 ≫ 0.001) H4✓ **H5✗** (z_obs below z_luck_bound for 24 trials) H6✗ H7✓ H8✓ H9✓ H10✓.

## 5. Failure analysis
1. **Economic-positive but skill-unproven** (the central finding): H6 and H8 (long/both,
   higher TF) *held* economic profitability in holdout — exp +20..23 pip, PF 1.28–1.41,
   maxDD within/near limits — yet fail H3/H5 decisively. The raw Donchian-breakout residual
   on gold ≈ **secular drift + weak momentum**, indistinguishable from the geometry-matched
   null at z≈1.1–1.4. A "profitable" line is not a *proven* line; the engine exists exactly
   to make this distinction.
2. **H12 overfit prediction confirmed exactly**: train WR 69.23 (n=39, violating the S91x
   law n<150) collapsed to 50.00 in holdout. Fourth in-block confirmation of the law.
3. **Shorts structurally weak again**: H2/H12/D1 shorts all negative-expectancy in holdout
   (2024–26 gold rally half) — L-S921-4 pattern reconfirmed.
4. **Minute TFs**: 10× NO-SURVIVOR — breakout event edges are far smaller than 3.3 pip
   spread at minute scale. Cost law now confirmed 6× in this block.

## 6. Proof that the 8 common mistakes were NOT made
1. **Look-ahead**: rolling_extreme uses window [t−p, t−1]; selftest asserts spike at bar
   3000 does not alter HH[3000] but does alter HH[3001]. PASSED bit-exact.
2. **Data snooping on holdout**: Path C — search on first half only; holdout touched ONCE;
   `{tf}_final.json` guard blocks re-touch; pre-final prediction committed before touch.
3. **Multiplicity ignored**: n_trials=24 declared in prereg; H5 Bailey–LdP z_luck bound
   applied; it is precisely H5 that kills H6/H8.
4. **Costs ignored**: 3.3 pip spread inside simulator; H2/H9 costed gates.
5. **Survivorship/selection**: survivor floor n_train≥30 + WR>costed breakeven, both preregistered.
6. **Wrong data**: mt5_full verified 19/19; E-16 H4 anomaly caught and excluded pre-final.
7. **Post-hoc grid expansion**: grid frozen in prereg commit 6ce73510; zero additions.
8. **Null mismatch**: measured_null geometry-matched (same SL/TP/hold, same simulator,
   K=2000, fixed seed), per side.

## 7. Lessons
- **L-S922-1**: Raw Donchian price-discovery breakouts on gold carry *economic* drift-alpha
  on H6–H8 longs but no statistically provable skill (z≈1.4). Any future layer wanting to
  monetize this must ADD an orthogonal conditioning filter that lifts z, not just WR.
- **L-S922-2**: 6th confirmation — minute-TF (M1–M30) event edges on XAUUSD cannot survive
  3.3 pip spread. Stop allocating hope there; discover them only as due diligence.
- **L-S922-3**: "Both-sides" pooling (H8) inherited the weak short side and diluted the long
  edge — consistent with L-S920-4 (pool only positive-lift members).
- **L-S922-4**: The S91x small-n law (train n<150 ⇒ selection noise) is now confirmed 4×
  in this block (S920, S921×2, S922-H12). Treat any train card with n<150 as presumptively
  noise regardless of WR.

## 8. Official ledger entry
**S922 = REJECT (RQS2 = 16.0, best card H6 long p144/a1.618/hold55)** — family closed.
Block ledger: S920=REJECT(6.1) · S921=REJECT(16.1) · S922=REJECT(16.0). Next: S923.
