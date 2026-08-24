# S613 PREREG — Monday Day-of-Week Drift (S140 lineage) — XAUUSD — Full-Data RQS2 Adjudication

**Scientist**: Évariste Galois (decade S610–S619)
**Date**: 2026-08-21 — committed **BEFORE any computation on this hypothesis**
**Lineage**: S140 archive (+$175,246, short-window, old paradigm) → S222b (WR60-era filter dressing, NOT RQS2) → **S613 (first RQS2 full-data judgment of the DOW dimension)**

---

## 1. Why this target (territory audit done first)

- Calendar family on gold is *provably alive* under RQS2: Mid-Month S432 pool = ACCEPT 84 (parallel scientist).
- Hour-of-day dimension is dead (S434 REJECT 19; S892 all 16 cards REJECT).
- **Day-of-week (Monday) has never been RQS2-judged on full data.** Archive exploration
  (`explore_gold_dow_hour`) showed Mon t=+6.11 on 24-candle horizon — strongest pure-DOW axis —
  but measured on the short window (E-16 exposure unknown).
- Academic grounding: weekend-news digestion + institutional liquidity return
  (Cross 1973; French 1980; Ball–Torous–Tschoegl 1982 for gold).
- Virginity checks: no S-number RQS2 result/prereg judges DOW on full data (greps over
  results/S*_rqs2_*, preregs, census). S810 = weekend GAP (different mechanism, different owner).

## 2. Hypothesis

H_dow: gold has a structural upward drift in the Monday liquidity-return window
(archive window: server hours 18–21) that is era-robust across 15.6y, above a
**day-of-week-permuted, geometry-matched null**.

## 3. Frozen event & locked exploration grid (Path C)

**Event (frozen from archive S140):** first bar of Monday (dow=0) with hour == 18 (server time,
as stored in data — same convention as archive) ⇒ LONG at next bar open.
One trade per Monday maximum. No other filters (S222b's ADX/ATR dressing is post-hoc — excluded).

**Geometry (era-robust per S532 law — ATR-scaled, symmetric, TP=SL ⇒ RR=1.0, budget law respected):**
V-TIME: bracket SL = TP = k×ATR34(Wilder, causal at signal) ; if untouched ⇒ exit at close of the
bar covering end-of-window; window end = hour 22 same day (archive window 18–21 + close).

**Locked grid (6 points, FIRST HALF ONLY):** TF ∈ {M15, M30, H1} × k ∈ {1.272, 2.058}.
Winner rule (locked): highest z vs conditioned null among points with n ≥ 150 and net > 0.
**Power precondition (locked)**: winner's first-half lift must satisfy
lift ≥ z_luck×sd_null with z_luck from n_trials below; else HONEST DEATH — holdout never opened.

**Second half / holdout**: single touch, one compute_rqs2 call on the winner only.

## 4. The null (S612 law applied: same geometry, same habitat)

Conditioned permutation: K = 1000, seed = 20260823. Each permutation replaces each Monday event
with a random **non-Monday weekday** (Tue–Fri) at the same hour-18 slot, same week, same geometry,
FIFO. This prices exactly "Monday-ness" — not the long-bias of the geometry, not the hour effect.
Reference = max(uncond-weekday-WR, perm_mean). uncond = all weekday hour-18 events, same geometry.

## 5. Multiplicity budget (honest)

| Source | trials |
|---|---|
| Archive DOW×hour matrix exploration (7×24 cells × ~3 horizons) | 504 |
| Archive S140 window/config picks + S222b dressing (not reused but seen) | 60 |
| This grid (6) + winner selection penalty (6) | 12 |
| Margin | 24 |
| **n_trials (locked)** | **600** |

z_luck(600) ≈ 3.91 one-sided. With ~810 Mondays/15.6y and expected n≈700 per TF card,
needed lift ≈ 3.91×sd_perm. If sd_perm ≈ 1.9pp (n~700), needed ≈ +7.4pp. Archive t=+6.11 suggests
raw drift may be strong; honest P(ACCEPT) ≈ 20–25%.

## 6. Preregistered predictions

- **P1**: The Monday effect exists directionally on full data (positive lift) but the decisive
  question is magnitude vs the 600-trial bar; most likely outcome POWER-LIMITED or REJECT-with-positive-z.
- **P2**: NOT regime-only — DOW flow effects are structural; pre-2023 net should be ≥ 0.
- **P3**: The k=2.058 (wider bracket) arm beats k=1.272 (drift needs room; tight brackets die on noise — S532).
- **P4**: H1 card has best signal-to-cost (fewest bars, lowest relative spread).
- **P5**: If archive t=+6.11 was E-16 inflated, first-half exploration will already show it (net≤0 pre-2019)
  ⇒ honest death without touching holdout.

## 7. Falsification lines (any ⇒ death, no filter search in this layer)

- No grid point with n≥150 ∧ net>0 in first half ⇒ HONEST DEATH.
- Power precondition failed ⇒ HONEST DEATH (holdout virgin).
- Holdout: PF<1.3, or z below 600-trial bar, or pre-2023 net<0 ⇒ REJECT as-is.

## 8. Compliance

Zero free parameters beyond the 6-point locked grid. Official engine semantics (V-TIME simulator
with SL-precedence, spread 3.3). Multi-TF law: the 3 TFs of the grid ARE the family; remaining TFs
get a report-only table ONLY if the layer survives (no extra budget). Overlap audit immediately upon
any ACCEPT (candidate kin: S432 mid-month pool — different calendar axis; S312). Checkpoint commits.

— Galois: «دوشنبه آخرین بُعد تقویمی داوری‌نشده است؛ با null هم‌جنسِ خودش محاکمه‌اش می‌کنم — درسی که S612 با خون داد.»
