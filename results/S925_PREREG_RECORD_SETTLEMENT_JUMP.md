# S925 PREREG — Record Settlement Jump (Rank-Record Close-to-Close Return, Drift-Aligned) — XAUUSD

**Scientist**: Friedrich Hayek (block S920–S929) · **Date**: 2026-09-05 · **Status**: committed BEFORE any test
**Judge**: RQS2 v2.6 (`engine/rqs2.py`, untouched) · **Data**: `data/mt5_full/XAUUSD_*.csv` only (15.6y; H4 = `data/mt5_full/XAUUSD_H4.csv` S908-derived; runtime span guard ≥14y; `src` asserted to contain `mt5_full`).

## 1. Hayekian rationale and lineage
Four independent parallel ACCEPTs (S604 Engle-z shock, S950 BV-jump, S965/S966 Kyle range-shock + ρ, S919 = S965 × S604 drift, S749 strong-close) converge on one spontaneous order: **a large, decisive price shock aligned with the medium-term drift continues**. Every one of them measures "large" against a *distributional scale* (ATR multiple, z-score, BV). S918 (Keynes) tried an *ordinal* record on **range** (34-bar) and failed (REJECT 3.1) — range records are dominated by wick-noise.

Hayek: only the *settlement* price transmits knowledge; the intrabar path is bargaining noise. So the informative record is the **close-to-close return**, not the range. Hypothesis: **a bar whose absolute close-to-close log return is the largest of the last W bars (an ordinal record — no distributional threshold, no ATR, no z) is a knowledge-revelation event; when it is aligned with the 60-day drift it continues.**

Collision audit (results/S*.md + strategies): "record close-to-close / record return / largest return in W" → 0 hits. Distinct from: S918 (range record), S602/S840 (z-scored return), S950 (BV jump), S965 (range/ATR + ρ), S526/S896 (price-level records), S545 (body acceleration), my own S920–S924.

## 2. Signal (causal; all computed on bar t; entry at open of t+1)
- `r[t] = ln(close[t]/close[t-1])`; `R[t] = |r[t]|`
- **Record**: `R[t] > max(R[t-W..t-1])` (strictly greater than every one of the previous W bars; current bar excluded from the window).
- **Direction**: follow sign of r[t].
- **Drift gate (S604 convention, fixed K per TF = bars in ~60 calendar days)**: `close[t-1] > close[t-1-K]` for long, `<` for short. K by TF: H1 1440 → but capped by data; concretely K = round(60 days × 24h / TF_hours) for H1–D1: H1=1440, H2=720, H3=480, H4=360, H6=240, H8=180, H12=120, D1=60; minute TFs use the same 60-day rule (M30=2880 … M1=86400); W1: K=9 (≈60 days).
- Gate mode is a grid arm: `gated` (aligned only) vs `ungated`. F3 (see §5) compares them **on holdout**.
- SL = TP = a × ATR21[t] (RR = 1 frozen, block convention); time-stop `hold` = 55 bars; one position at a time.

## 3. Frozen grid (n_trials = 24)
- W ∈ {34, 89}; gate ∈ {ungated, gated}; a ∈ {1.618, 2.058}; side ∈ {long, short, both} → 2×2×2×3 = 24 arms per TF. hold=55 fixed.
- TFs: all 19 gold TFs. Warmup = max(W, K) + 60 bars.
- Path C: multiplicity search on FIRST HALF only. Survivor rule: `WR_train > costed breakeven AND n_train ≥ 30` → best train `edge×√n` per TF. Pre-final prediction committed, then holdout touched ONCE per TF (guard `{tf}_final.json`).
- Null: geometry-matched measured_null (random entry times, same SL/TP/hold, same simulator), K=2000, seed = 20260906.
- Costs: spread 3.3 pip, commission 0, contract 100, $10k, 1% risk (engine defaults).

## 4. Report-only holdout diagnostics (computed AFTER the single official holdout run, from the same holdout trades; no influence on verdict)
- **F3-holdout**: for the winning TF card, the *other* gate arm with identical W/a/side is simulated on holdout and reported (lift comparison). This is one extra holdout simulation per TF, disclosed here in advance; it produces no verdict and no card.

## 5. Falsifiers
- **F1**: no final card with lift > +4pp → concept dead.
- **F2**: best z < H5 luck bound → skill unproven.
- **F3-holdout**: gated arm does not beat ungated arm on holdout lift → drift alignment adds nothing beyond the record itself (or vice-versa).
- **F4**: shorts negative while longs positive in holdout → residual = secular drift (block record: shorts 0/9 in S921–S924).
- **F5**: record events on H6–D1 are < 30 in train for W=89 → family untestable at high TF (expected: W=89 on D1 yields ~n/89 events).

## 6. Personal prediction (accountability)
- Minute TFs NO-SURVIVOR (cost law 8×). Survivors H1–D1.
- Best card most likely H6 or H8, gated, long or both, W=34, lift +5..+12pp, n 60–150, z 1.5–2.5 → POWER-LIMITED or REJECT. P(ACCEPT) ≈ 15% (higher than my prior families because the lineage is proven; lower than S919 because the ordinal record is untested and S918's range-record failed).
- Small-n cards (n<100) will collapse (S91x law, 6× confirmed).

## 7. Anti-collision / integrity statement
No pooling; no parameter change after this commit; verdict verbatim from `compute_rqs2`; every JSON records `src`; the F3-holdout diagnostic is declared here and will be clearly labelled report-only. I do not touch any other scientist's files or numbers.

— Friedrich Hayek, S920–S929
