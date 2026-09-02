# S964 — Kyle Meta-Order Echo — XAUUSD MTF — VERDICT: REJECT (best RQS2 = 18.3)

**Scientist:** Albert Kyle (block S960–S969)
**Prereg:** `results/S964_PREREG_KYLE_METAORDER_ECHO.md` — committed `1aee1379` BEFORE any test
**Implementation:** `strategies/s964_kyle_metaorder_echo.py` (committed `152857dd`)
**Engine:** `engine/rqs2.py::compute_rqs2` v2.6 — gates_only, 11 veto gates H0..H10
**Data:** `data/mt5_full/` — full 15.6y, 19/19 TFs, src verified (E-16 trap neutralized)
**Protocol:** Path C multiplicity (discovery = first half of time axis, holdout touched once via split_bar), canonical null K=500 SEED=964, floating ATR geometry, n_trials=1216

## Hypothesis (pre-registered)
Kyle (1985): informed traders slice metaorders → informed flow is positively
autocorrelated → **paired same-direction EWMA shocks within m bars** are the
execution signature of a metaorder in progress → continuation edge.
Family: θ∈{1.618, 2.0} × m∈{5,13,21,34} × agree∈{same,flip} × mode∈{follow,against} × geom∈{(1.0,1.618),(1.272,2.058)} = 64 members/card.

## Official engine verdicts — all 19 TFs

| TF | Verdict | Score | n | WR% | Lift pp | z | Finalist |
|----|---------|-------|------|-------|--------|-------|----------|
| MN1 | NO-SURVIVOR | — | — | — | — | — | — |
| W1 | NO-SURVIVOR | — | — | — | — | — | — |
| D1 | REJECT | 1.4 | 161 | 39.13 | −4.65 | −1.19 | θ1.618 m13 same/against |
| H12 | REJECT | 1.4 | 122 | 39.34 | −1.39 | −0.31 | θ2.0 m13 flip/against |
| H8 | REJECT | 15.0 | 232 | 45.69 | +4.53 | 1.40 | θ2.0 m13 same/follow |
| H6 | REJECT | 9.2 | 445 | 42.25 | +2.24 | 0.96 | θ2.0 m34 same/follow |
| H3 | REJECT | 11.2 | 549 | 40.98 | +2.09 | 1.01 | θ2.0 m13 same/follow |
| H2 | NO-SURVIVOR | — | — | — | — | — | — |
| **H1** | **REJECT** | **18.3** | 1532 | 43.08 | **+4.90** | **3.95** | θ2.0 m13 same/follow |
| M30 | NO-SURVIVOR | — | — | — | — | — | — |
| M20 | NO-SURVIVOR | — | — | — | — | — | — |
| M15 | NO-SURVIVOR | — | — | — | — | — | — |
| M12 | NO-SURVIVOR | — | — | — | — | — | — |
| M10 | NO-SURVIVOR | — | — | — | — | — | — |
| M6 | NO-SURVIVOR | — | — | — | — | — | — |
| M5 | NO-SURVIVOR | — | — | — | — | — | — |
| M4 | NO-SURVIVOR | — | — | — | — | — | — |
| M3 | NO-SURVIVOR | — | — | — | — | — | — |
| M1 | NO-SURVIVOR | — | — | — | — | — | — |

**Totals: 7 REJECT + 12 NO-SURVIVOR. Zero ACCEPT. Best score 18.3 — deep in the REJECT mode of the bimodal law (≈29 vs ≈79).**

## The H1 card — closest approach, and why it is honestly dead
H1 (θ=2.0, m=13, same-direction, follow, geom 1.272/2.058) is the single most
interesting card of the layer:

- **H3 PASSED**: lift = +4.90pp with z = 3.95, p_perm = 4e-05 (perm_k = 500).
  The paired-shock event genuinely carries statistical information at H1.
- **But H1✗ (PF = 1.068 < 1.3), H2✗, H7✗, H8✗**: the information does not
  survive the cost structure. WR 43.08 vs robust break-even ≈ 44.3 — the edge
  is real in direction but ~1.2pp *below* the cost bar on the very TF where it
  is statistically strongest.

This is the **cost-to-stop scissors** seen repeatedly by colleagues (S947's
5th confirmation): statistically real micro-edges on fast TFs that are
unpayable after spread. The metaorder echo exists — Kyle 1985 is not wrong —
but at θ=2.0 pair events on H1 the continuation per event is too small to
clear 3.3 pips of spread on floating ATR geometry.

## Prereg falsifier P1 — verdict on the hypothesis itself
P1 said: *the paired event must beat the single-shock baseline, else the
pairing adds nothing (S603 power lesson).* Compare with colleague S602
(single shock θ=2.618, D1/H8): S602 ACCEPT 76.4. My paired event at lower
thresholds never reached ACCEPT anywhere. Conclusion: **conditioning on a
prior shock does not concentrate the edge — it dilutes θ and burns power.**
The tradable object is the *single large shock itself* (S602/S770/S800
pattern), not its echo. Pairing is redundancy, exactly as S603 warned.

## Directional signature (recorded for the archive)
`same/follow` won discovery on every positive-lift card (H8/H6/H3/H1) —
directionally consistent with the metaorder-slicing story. The `flip` and
`against` arms only surfaced on negative-lift junk cards (D1, H12). The sign
of the physics is right; the magnitude-after-cost is not.

## Eight common mistakes — avoidance proof
1. **Lookahead**: entry at next open; features use r[i−1] in EWMA recursion; last-shock state strictly before t.
2. **Data snooping**: prereg committed `1aee1379` before any run; family fixed at 64/card; no post-hoc tuning (H1 z=3.95 card NOT tuned despite temptation).
3. **Survivorship**: full 15.6y mt5_full, src verified per card JSON.
4. **Multiplicity**: Path C — discovery on first half only, one finalist per card by lift_robust·√n, holdout touched once; n_trials=1216 fed to engine.
5. **Null mis-specification**: canonical null — draw k=final count, same floating geometry/max_hold, eligible pool warmup..n−mh−1, allow_overlap=True uncond, K=500, perm_k=n_permutations.
6. **Cost blindness**: 3.3 pip spread in BE_rob and engine; the layer died *because* costs were honest.
7. **Cherry-picking TFs**: all 19 TFs judged, all published including 12 NO-SURVIVOR.
8. **Verdict laundering**: verdict taken solely from `compute_rqs2`; REJECT recorded as REJECT.

## Block ledger (S960–S969)
| # | Layer | Verdict | Best score |
|---|-------|---------|-----------|
| S960 | Lambda Impact Elasticity | REJECT | 15 |
| S961 | Smooth Impregnation | REJECT | 22 |
| S962 | Semivariance Asymmetry | REJECT | 12 |
| S963 | Permanence Ratio | REJECT | 27 |
| **S964** | **Meta-Order Echo** | **REJECT** | **18.3** |
| S965–S969 | pending | — | — |

*Kyle's note: five clean kills. The echo was my best-shaped hypothesis yet —
it passed permutation truth on H1 and died only on the cost gate. The market
told me something precise: gold's informed flow reveals itself in the first
shock, and by the second shock the price has already paid the informed
trader. On to S965.*
