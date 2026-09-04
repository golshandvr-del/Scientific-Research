# S923 PREREG — Sustained Envelope Pressure (Band-Walk Persistence) — XAUUSD

**Scientist**: Friedrich Hayek (block S920–S929) · **Date**: 2026-09-04
**Status**: PREREG — committed BEFORE any test. Zero numbers computed as of this commit.
**Engine**: RQS2 v2.6 official, untouched (11 veto gates). Path C multiplicity.
**Data**: `data/mt5_full/` ONLY (15.6y, 19 TFs). E-16 trap known: H4 absent from mt5_full → if H4 discover silently loads short csv, H4 is EXCLUDED pre-final (as in S921/S922).

## 1. Hypothesis (Hayekian coordination persistence)
A single close beyond the statistical envelope may be noise (S922 lesson: raw breakout ≈ drift,
z≈1.4). But *sustained pressure* — M consecutive closes beyond the Bollinger envelope — is the
signature of persistent, informed order flow: dispersed knowledge being continuously impounded
faster than the envelope can adapt. Analogous to S965's insight (shape/quality filter on the
event is information-ADDING, lifting z, not power-burning): here the persistence count M is the
quality filter on the envelope-breach event.

**Event (fresh edge only, no state accumulation — S963/S526 law):**
- `mid = SMA(close, P)`, `sd = rolling_std(close, P, ddof=0)`, `upper = mid + 2.0·sd`,
  `lower = mid − 2.0·sd`. All computed on bars ≤ t (close[t] vs band[t] built from window
  ending at t is standard Bollinger; entry at next bar open → no look-ahead).
- `above[t] = close[t] > upper[t]`; `run_up[t]` = length of current consecutive `above` streak.
- **long_event[t]**: `run_up[t] == M` and `run_up[t−1] == M−1` (streak *just* reached M — fires
  once per streak).
- Mirror short: `below = close < lower`, `run_dn`, short_event at streak==M.

## 2. Frozen grid (NOTHING added after this commit)
- P ∈ {20, 55} (20 = canonical Bollinger; 55 = Fibonacci, block precedent)
- M ∈ {2, 3} (persistence count)
- a = **1.618 FROZEN** (SL = TP = a×ATR(21)[t], RR=1 frozen; block precedent: economically
  surviving cards in S921/S922 all had a=1.618)
- hold ∈ {55, 144} (max_hold bars)
- side ∈ {long, short, both}
- **n_trials = 2×2×2×3 = 24 per TF** (reported to engine)
- SEED = 20260904 · warmup = P + 60 · entry at next-bar open, conservative simulator
  (`se.simulate_trades`), spread 3.3 pip inside.

## 3. Protocol (identical to S920–S922, Path C)
1. `selftest`: run_up/run_dn streak logic verified vs naive loop, bit-exact; explicit
   no-look-ahead assertion (perturbing close[t+1] must not change event[t]).
2. `discover TF` on ALL 19 TFs — search on FIRST HALF only (split_bar = n//2).
   Survivor rule: WR_train > costed breakeven AND n_train ≥ 30. Per S91x law, any survivor
   with n_train < 150 is flagged presumptively-noise in pre-final prediction.
3. PRE_FINAL_PREDICTION.md committed BEFORE any holdout touch.
4. `final TF` for survivors only: holdout touched ONCE, guard file `{tf}_final.json` blocks
   re-touch. measured_null geometry-matched per side (same SL/TP/hold, same simulator,
   K = 2000, fixed seed).
5. Official verdict = `R.compute_rqs2(...)` verbatim. Save
   `S923_SustainedEnvelopePressure_Xauusd_<TFs>_rqs2_<score>_<verdict>.md`.

## 4. Anti-collision audit (performed before this prereg)
- grep "band.walk|bandwalk|ride band|upper band streak" → **zero hits**. Family virgin.
- Bollinger hits are all SQUEEZE (S91/S225/S313/S332/S501/S800/S951 — bandwidth compression
  → expansion) or MEAN-REVERSION (BB_RSI, Range_BB) — none is persistence-continuation
  beyond the band.
- Distinct from S922 (Donchian price extreme, single cross) — here the event requires the
  close to remain beyond a *volatility-scaled* envelope for M bars: different object
  (σ-envelope vs price extreme), different filter (persistence vs first-touch).
- Distinct from S526/S629 (fresh rolling-high of close): those are price-level records;
  this is a deviation-from-mean-in-σ-units sustained state.
- Not touching any live/parallel numbers; my block only.

## 5. Falsifiers (declared now)
- F1: If no TF card has holdout lift > +4pp → concept dead, REJECT report.
- F2: If best z < 3.09 (H3/H5) → REJECT regardless of economic profit (S922 lesson applies).
- F3: If the M=2/M=3 arms do NOT beat a hypothetical M=1 baseline in train lift, the
  persistence filter is power-burning (S964 death mode) — will be reported honestly.
  (M=1 baseline computed on TRAIN ONLY as diagnostic, not a trial card.)
- Personal prediction (accountability): peak edge, if any, on H6–H8 long (block + parallel
  precedent: gold momentum-friendly, shorts structurally weak in 2024–26 half). Minute TFs
  will be NO-SURVIVOR (cost law, 6× confirmed).

— Friedrich Hayek, S920–S929
