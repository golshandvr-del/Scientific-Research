# S924 PREREG — Knowledge Signal-to-Noise (Volatility-Scaled Momentum Threshold Cross) — XAUUSD

**Scientist**: Friedrich Hayek (block S920–S929) · **Date**: 2026-09-05 · **Status**: committed BEFORE any test
**Judge**: RQS2 v2.6 (`engine/rqs2.py`, untouched) · **Data**: `data/mt5_full/XAUUSD_*.csv` only (15.6y; E-16 trap: `data/*.csv` are short except H4 which was verified full-span in S923 — H4 will be loaded from `data/XAUUSD_H4.csv` and its span re-asserted ≥15y at runtime, else excluded).

## 1. Hayekian rationale
Prices are a telecommunication system that compresses dispersed knowledge. A drift is a *message*; realized volatility is the *noise* on the channel. The information content of the message is its signal-to-noise ratio, not its raw size. Raw drift gates (S604/S966: `close[i-1] > close[i-1-K]`) ignore the noise term — they treat a +1% drift in a calm market and a +1% drift in a violent market as identical. Hypothesis: **when the K-bar drift, scaled by K-bar realized volatility, first exceeds a threshold θ, the channel is transmitting a high-fidelity message and the price continues in that direction.**

Literature anchor: time-series momentum (Moskowitz–Ooi–Pedersen 2012), volatility-managed momentum (Barroso & Santa-Clara 2015; Daniel & Moskowitz 2016). Novelty vs project: drift has only ever been used as a binary *gate* on other events; vol-normalised momentum has never been the *entry event* (collision audit: 0 hits for "vol-scaled/risk-adjusted/sharpe momentum"; S544 upstreak, S991 autocorr-mom and S545 body-acceleration are raw-count/raw-return momentum → REJECT — none normalised by noise).

## 2. Signal definition (causal, all on bar t, entry at open of t+1)
- `r[t] = ln(close[t]/close[t-1])`
- `drift_K[t] = ln(close[t]/close[t-K])`
- `noise_K[t] = std(r[t-K+1..t]) × sqrt(K)` (population std over the K returns ending at t)
- `SNR[t] = drift_K[t] / noise_K[t]` (undefined → NaN → no event)
- **Long event**: `SNR[t] ≥ θ` AND `SNR[t-1] < θ` (state-cross; one event per crossing). **Short event**: mirror (`SNR[t] ≤ −θ` AND `SNR[t-1] > −θ`).
- Entry open of t+1; SL = TP = a × ATR21[t] (RR=1 frozen, consistent with S920–S923); time-stop `hold`=55 bars; one position at a time (simulator default).

## 3. Frozen grid (n_trials = 24)
- K ∈ {55, 144}; θ ∈ {1.0, 1.618}; a ∈ {1.618, 2.058}; hold = 55 (fixed); side ∈ {long, short, both} → 2×2×2×3 = 24 arms per TF.
- TFs: all 19 gold TFs (M1…W1). Warmup = K + 60 bars.
- Path C: multiplicity search on FIRST HALF only. Survivor rule: `WR_train > costed breakeven AND n_train ≥ 30` → best train edge per TF. Pre-final prediction committed, then holdout touched ONCE per TF (guard `{tf}_final.json`).
- Null: geometry-matched measured_null (random entry times, same SL/TP/hold, same simulator), K=2000, seed = 20260905.
- Costs: spread 3.3 pip, commission 0, contract 100, $10k, 1% risk (engine defaults).

## 4. Report-only diagnostic (no verdict influence)
- F3 baseline: raw-drift sign cross (θ=0 on `drift_K`, i.e. plain TSM sign flip) with same a/hold → does vol-normalisation add information (lift) over the raw message? Computed on train only.

## 5. Falsifiers
- **F1**: no final card with lift > +4pp → concept dead.
- **F2**: best z < H5 luck bound → skill unproven.
- **F3**: SNR arm does not beat raw-drift-sign baseline on train lift in the surviving TFs → normalisation adds nothing; the family reduces to plain TSM.
- **F4**: shorts negative in holdout while longs positive → what remains is secular drift, not the concept (L-S921-4 pattern).

## 6. Personal prediction (accountability)
- Minute TFs: NO-SURVIVOR (cost law 7× confirmed). Survivors likely H2–D1.
- θ=1.618 will produce few events on K=144 (n<100) → bait cards; small-n law predicts collapse.
- Realistic best card: H6/H8 long, K=55, θ=1.0, lift +3..+8pp, z 1–2 → REJECT or POWER-LIMITED. Prior P(ACCEPT) ≈ 10%. Shorts weak in holdout half.

## 7. Anti-collision statement
Not S604/S966 (drift as gate on shocks), not S544/S991/S545 (raw momentum counts/returns), not S587/S529 (drift-aligned revivals of other events), not S920–S923 (my own closed families). No pooling; no parameter change after prereg; verdict verbatim from `compute_rqs2`.

— Friedrich Hayek, S920–S929
