# S612 PREREG — VWAP Confluence Momentum on XAUUSD **H1** — Formal RQS2 Adjudication of the S611 Lead

**Scientist**: Évariste Galois (decade S610–S619)
**Date**: 2026-08-21 — committed **BEFORE any decisive computation on H1 beyond the already-logged S611 MTF reporting row**
**Lineage**: S153 (archive, short-data) → S611 (full-data M5 rejudge, REJECT 11.4, REGIME-ONLY #3) → S611 MTF table → **this adjudication**

---

## 1. Hypothesis

H_habitat: the VWAP-confluence-momentum event (daily-VWAP z>1.5 stretch + EMA200 uptrend + momentum candle)
carries genuine, era-robust long edge on XAUUSD **H1** — the coarsest TF before the structural zero-signal
boundary — where per-bar noise and relative cost are lowest.

**Evidence motivating (already logged, already charged):** S611 MTF row H1: n=1070, WR=63.74, net=+13,831.8 pip,
halves 64.89/62.78 (net +4,234/+9,598) — the **only** TF among 19 whose first (pre-2019) half is the *stronger* half.

## 2. Frozen configuration (ZERO search — bit-identical to S153/S611)

```
signal:  daily_vwap_z(dev_window=60) > 1.5  ∧  close > EMA200  ∧  green candle  ∧  range ≥ 0.5×ATR14
gate:    cooldown = 48 bars (H1 ⇒ 48h)
exec:    LONG only, entry open[sb+1], SL=80 pip, TP=700 pip, BE=+6, trail=6, max_hold=48 bars
costs:   spread 3.3 pip, no commission | engine: exact simulate_trades semantics (bit-exact table, validated in S611)
data:    data/mt5_full/XAUUSD_H1.csv (15.59y, 91,331 bars), loader tools/s434_fast_data
```
No parameter may be changed. If the frozen config fails, the verdict stands — **no post-hoc filter search
in this layer** (improvement, if any, becomes S613+ with its own prereg).

## 3. Multiplicity budget (honest counting)

| Source | trials |
|---|---|
| S611 lineage (archive 192-grid + manual + rejudge, prereg-locked) | 200 |
| S611 MTF table — 19 TF looks (reporting, but *used to select H1*) | 19 |
| Selection-of-best-of-19 penalty margin | 31 |
| **n_trials (locked)** | **250** |

K_PERM = 500, seed = 20260821, split_bar = 70% of H1 bars, null = canonical
{uncond stride + permutation of eligible bars, FIFO applied per permutation}, reference = max(uncond, perm_mean).

## 4. Preregistered predictions

- **P1 (survival)**: P(ACCEPT) ≈ 30%. The trailing/BE geometry inflates WR everywhere; the decisive question
  is the **permutation null on H1** — random long entries with trail=6/BE=6 on a secular-bull asset may
  themselves reach WR ≈ 58–61%. If perm_mean ≥ 60%, lift < 4pp and H3/H5 die.
- **P2 (regime)**: unlike M5, pre-2023 H1 stays net-positive (halves evidence). If pre-2023 net < 0 ⇒
  REGIME-ONLY #4 and the family is closed for me.
- **P3 (economics)**: H1-gate risk — avg win is small (trail exits); PF may again land in 1.1–1.3 dead zone.
  PF < 1.3 ⇒ REJECT regardless of z.
- **P4 (power)**: n=1070; with z_luck ≈ 3.72 (n_trials=250), needed lift ≈ 3.72×perm_sd. If perm_sd ≈ 1.5pp,
  needed ≈ +5.6pp over reference. Observed raw WR−uncond gap must clear that.

## 5. Locked plan (single pass, no iteration)

1. Run adjudicator (adapted from `strategies/s611_vwap_rejudge.py`, TF=H1): sanity — n must equal 1070
   (bit-identity guard with the MTF row); otherwise HALT and debug loader only.
2. Compute canonical null (uncond + K=500 perm, FIFO per perm, seed 20260821).
3. Single `compute_rqs2` call with all 5 mandatory inputs (tp_pip=700, null, n_trials=250, split_bar, bar_time, close).
4. Regime decomposition pre/post 2023-09 + yearly table (evidence, not adjudication).
5. If ACCEPT/POWER-LIMITED ⇒ immediate overlap audit vs site ACCEPT layers (Overlap law). If REJECT ⇒ report as-is.
6. One result MD: `S612_VwapConfluenceMomentumH1_Xauusd_H1_rqs2_<score>_<verdict>.md`. Checkpoint commits throughout.

**Falsification lines (any ⇒ REJECT/close):** PF<1.3 · z below the 250-trial luck bar · pre-2023 net<0 · holdout collapse.

— Galois: «انتخاب H1 از میان ۱۹ نگاه، خودش یک آزمون است؛ آن را می‌شمارم تا قضاوت شرافتمندانه بماند.»
