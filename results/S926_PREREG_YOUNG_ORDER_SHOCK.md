# S926 PREREG — Young-Order Shock (Absolute Settlement Shock × Drift-Age) — XAUUSD

**Scientist**: Friedrich Hayek (block S920–S929) · **Date**: 2026-09-06 · **Status**: committed BEFORE any test
**Judge**: RQS2 v2.6 (`engine/rqs2.py`, untouched) · **Data**: `data/mt5_full/XAUUSD_*.csv` only (runtime assert: `mt5_full` in src AND span ≥14y; H4 = official S908-derived file).

## 1. Hayekian rationale and lineage
The block's six failures (S920–S925) and the lesson ledger say: on gold, the informative event is a **shock with absolute scale** (ATR-multiple / z / BV — S604, S950, S965, S919, S1520, S1911), and the **60-day drift gate is real out of sample** (S925 F3-holdout: +7..+13pp WR at H4–H12 even on a dead base; S604/S966/S919). Every accepted gated layer treats the drift as a binary *state*: aligned or not. None asks **how old the drift is**.

Hayek (1945, 1968): a spontaneous order is *most* informative at its birth — when new knowledge has not yet been diffused into prices and imitators have not yet crowded the signal. Late in an order, aligned shocks are increasingly imitation and herding (cf. S1780 frog-in-the-pan POWER-LIMITED). Hypothesis: **an aligned absolute shock that occurs while the 60-day drift is *young* (few bars since its last sign change) continues more strongly than one occurring in an *old* drift.**

Collision audit (`results/S*.md`, `strategies/`): "drift age / bars since drift flip / regime age / young trend / trend birth" → only S753 (chop-collapse trend birth, ADX-based, REJECT) and my own S924. No layer conditions a shock on the *age* of the drift. Base event novelty: absolute **close-to-close** shock (|Δclose| ≥ θ·ATR21[t−1]) — distinct from S965 (range/ATR + ρ), S602/S840 (EWMA z), S950 (BV), S925 (ordinal record). `grep "close.to.close.*ATR|c2c shock|settlement shock"` → 0.

## 2. Signal (causal; computed on bar t; entry open of t+1)
- `ATR21[t−1]`: Wilder ATR (ewm α=1/21) of true range, lagged one bar (causal, S965 convention).
- **Shock**: `|close[t] − close[t−1]| ≥ θ × ATR21[t−1]`, θ ∈ {1.618, 2.618}. Direction = sign(close[t] − close[t−1]). Follow.
- **Drift** (S604 convention): `D[t] = close[t−1] − close[t−1−K]`, K = bars in 60 calendar days per TF (H1 1440, H2 720, H3 480, H4 360, H6 240, H8 180, H12 120, D1 60, W1 9; minute TFs 60d equivalent).
- **Alignment**: long shock requires D[t] > 0; short shock requires D[t] < 0 (all arms are aligned — the *unconditional* alignment gate is the proven prior, not the hypothesis under test).
- **Drift age**: `age[t]` = run length of consecutive bars ending at t−1 over which sign(D) has been unchanged.
- **Age arms** (the hypothesis): `young`: age ≤ A_max with A_max = K/2 (drift established within the last ~30 days); `any`: no age condition (control = plain S604-style gate on this base). F3-holdout compares them.
- SL = TP = a × ATR21[t] with a ∈ {1.618, 2.058} (RR=1, block convention); hold = 55 bars; one position at a time.

## 3. Frozen grid (n_trials = 24)
- θ ∈ {1.618, 2.618}; age ∈ {young, any}; a ∈ {1.618, 2.058}; side ∈ {long, short, both} → 2×2×2×3 = 24 arms per TF; hold=55 fixed; A_max = K/2 fixed (not searched).
- TFs: all 19 gold TFs. Warmup = K + 60 bars.
- Path C: multiplicity search on FIRST HALF only. Survivor rule: `WR_train > costed breakeven AND n_train ≥ 30` → best train `edge×√n` per TF. Pre-final prediction committed; holdout touched ONCE per TF (guard `{tf}_final.json`).
- Null: geometry-matched measured_null (random entry times, same SL/TP/hold, same simulator), K=2000, seed = 20260907.
- Costs: spread 3.3 pip, commission 0, contract 100, $10k, 1% risk (engine defaults).

## 4. Report-only holdout diagnostic (declared in advance; no verdict, no card)
- **F3-holdout**: for each finalised TF, the *other* age arm with identical θ/a/side is simulated once on holdout; WR/n/exp reported next to the official card. One extra holdout simulation per TF.

## 5. Falsifiers
- **F1**: no final card lift > +4pp → base event dead on gold.
- **F2**: best z < H5 luck bound → skill unproven.
- **F3-holdout**: `young` does not beat `any` on holdout lift where both have n ≥ 30 → drift age carries no information; the layer reduces to a S604-style gate on a new base (report as such).
- **F4**: shorts negative while longs positive → residual = secular drift (block record 0/10 shorts).
- **F5**: `young` arm n_train < 30 on H6–D1 → hypothesis untestable at the TFs where the lineage works.

## 6. Personal prediction (accountability)
- Minute TFs NO-SURVIVOR (cost law 9×); H1/H2 thin.
- Base (θ=1.618 c2c shock, aligned, `any`) should carry the lineage edge: H6/H8 lift +8..+15pp, n 80–200 in train. If it does not, the close-to-close field is inferior to range/ATR (S965) — informative either way.
- `young` arm: fewer trades (≈ 30–45% of `any`); prediction: **+3..+8pp higher WR than `any` on holdout at H6/H8** with P ≈ 40%; P(young < any) ≈ 35%.
- Best card most likely H8 or H6, long or both, θ=1.618. P(ACCEPT) ≈ 20%; P(POWER-LIMITED) ≈ 30%; P(all REJECT) ≈ 50%. Small-n cards (n<100) collapse (7× confirmed).

## 7. Integrity statement
No pooling; no parameter change after this commit; A_max fixed at K/2 and not searched; verdict verbatim from `compute_rqs2`; every JSON records `src`; I do not touch other scientists' files or numbers.

— Friedrich Hayek, S920–S929
