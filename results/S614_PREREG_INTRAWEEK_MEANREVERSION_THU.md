# S614 PREREG — Intra-Week Mean Reversion (Mon–Wed move → Thursday counter-trade) — XAUUSD — Full-Data RQS2

**Scientist**: Évariste Galois (decade S610–S619)
**Date**: 2026-08-21 — committed **BEFORE any computation on this hypothesis**
**Lineage**: S23 archive (`Weekly_MeanReversion_Thursday_57.md`; user's own market hypothesis;
corr(early_move, thu_chg) = −0.194, p<0.001 on SHORT window; burned on WR>60-at-cost criterion, never RQS2-judged)

---

## 1. Territory audit (done first)

- S722 (decade S720, parallel) = weekly-open **anchor continuation**; S982 (parallel) = weekly-open
  **reclaim**. Both use the weekly-open *level*. Mine uses the **cumulative Mon–Wed return sign** —
  different state variable, different mechanism (reversal, not continuation). No collision.
- No RQS2-era result/prereg matches "weekly reversion / early_move / intra-week" (grep verified).
- Distinction from my dead S613: there the *day identity* was the signal (zero info). Here the day
  is only the execution slot; the signal is the week's prior path. Academic: weekly reversal effect
  (short-horizon reversal literature, Lehmann 1990; gold-specific weekly MR untested here).

## 2. Hypothesis

H_wmr: after an unusually large Mon–Wed move, Thursday's price drifts AGAINST that move
(institutional rebalancing / profit-taking before week close), era-robust on 15.6y,
above a direction-permuted geometry-matched null.

## 3. Frozen event (zero search)

- Week = Monday-based (dow 0..4). `early_move` = close(last Wed bar) − open(first Mon bar).
- **Gate (frozen)**: |early_move| ≥ causal rolling median of |early_move| over the prior 52 weeks
  (min 26 samples). No threshold search.
- **Event**: first bar of Thursday (dow=3) ⇒ enter at next bar open, direction = −sign(early_move).
- One trade per week. Exit: V-TIME — bracket SL = TP = k×ATR34(Wilder, causal at signal); if
  untouched, exit at close of last Thursday bar (dow=3) of that week.
- Costs: spread 3.3 pip; official SL-precedence scan semantics.

## 4. Locked grid (Path C — FIRST HALF ONLY, 4 points)

TF ∈ {M30, H1} × k ∈ {1.272, 2.058}.
Winner rule (locked): highest z vs null among points with n ≥ 100 ∧ net > 0.
Power precondition (locked): winner lift ≥ z_luck × perm_sd, z_luck = 3.72 (one-sided, n_trials=300);
else HONEST DEATH, second half stays VIRGIN.

## 5. Null (S612/S613 law: same geometry, same habitat, price ONLY the information)

Direction permutation: K = 1000, seed = 20260825. Each permutation keeps the same Thursday events
and the same geometry but assigns each trade a random direction (fair coin). This prices exactly
the directional information of early_move. uncond reference = WR of the same events with coin-flip
direction expectation (perm_mean); reference = max(uncond_coin, perm_mean).

## 6. Multiplicity budget (honest)

| Source | trials |
|---|---|
| Archive S23 sweep (hours × horizons × thresholds, full sweep documented) | 240 |
| This grid (4) + winner selection (4) | 8 |
| Prior family knowledge (S613 DOW map, no reuse but seen) | 20 |
| Margin | 32 |
| **n_trials (locked)** | **300** |

Expected n ≈ 390 gated Thursdays (≈810 weeks × ~50% gate). With perm_sd ≈ 2.5pp at that n,
needed lift ≈ +9.3pp. Honest P(ACCEPT) ≈ 15% — reversal effects on gold have died repeatedly
(S326/S327 streak/climax family), but this exact state variable is untested; the finding value
is closing the intra-week MR question with a clean conditioned null.

## 7. Preregistered predictions

- **P1**: directional correlation exists (negative) on full data but magnitude is the killer —
  most likely death: lift < power bar (POWER-LIMITED-like exploration death or REJECT).
- **P2**: if any arm survives, it is k=2.058 on H1 (reversal needs room; S532 geometry law).
- **P3**: NOT regime-only — if the effect exists it should hold pre-2023 (rebalancing is structural).
- **P4**: the gate (large |early_move|) is essential — ungated Thursdays carry ≈ zero info
  (consistent with S613: day identity alone is dead).

## 8. Falsification lines (any ⇒ death as-is, no filter search in this layer)

- No grid point with n≥100 ∧ net>0 in first half ⇒ HONEST DEATH (holdout virgin).
- Power precondition failed ⇒ HONEST DEATH (holdout virgin).
- Holdout single touch: PF<1.3 ∨ z below 300-trial bar ∨ pre-2023 net<0 ⇒ REJECT as-is.

## 9. Compliance

Zero free parameters beyond the 4-point locked grid. Multi-TF law: M30/H1 are the family; wider
report-only table only upon survival (no extra budget). Overlap audit immediately upon any ACCEPT
(candidate kin: S432 mid-month — different axis; S722/S982 — different state variable).
Checkpoint commits per phase. No interference with parallel decades.

— Galois: «S613 گفت "روز" هیچ اطلاعی ندارد؛ S614 می‌پرسد آیا "مسیرِ هفته" اطلاع دارد. null فقط همان اطلاع را قیمت‌گذاری می‌کند.»
