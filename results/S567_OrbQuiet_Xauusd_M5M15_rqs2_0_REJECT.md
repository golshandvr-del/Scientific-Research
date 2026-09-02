# S567 — ORB-Quiet (Opening-Range Breakout, LONG) — XAUUSD M5/M15 — REJECT (score 0, honest death at prereg gate)

**Scientist:** Leibniz (block S560–S569)
**PREREG:** `results/S567_PREREG_ORB_QUIET_XAUUSD.md` — committed `d555d253` BEFORE any computation
**Tool:** `tools/s567_orb_quiet.py` — committed `4af4f533` before lock
**Family:** morning-structure (new family after GapOpen enclosure) — cumulative n_trials = 48
**Official verdict: REJECT — score 0** (both TFs STOPPED_DEAD at preregistered stop gate; second half VIRGIN, engine judgment forbidden by prereg — honest-death rule per S613/S533 precedent)

---

## 1. Hypothesis (from PREREG, verbatim intent)

Opening-Range Breakout: on each trading day, define the opening range (OR) as the first 60
minutes after the day break (`day_breaks` from tools/s560_gapopen_explore, BUG-BRKTHRESH-safe:
thr = max(1800s, 1.5×TF_SEC)). If price CLOSES above OR_high within a 3-hour window after the
OR completes, go LONG at the next candle open. Arms: {BARE, V78-frozen} × hold {1h, 2h} per TF.

- K_OR: M5=12 candles, M15=4 candles (=60 min)
- Window: M5=24 candles, M15=8 candles (=3 h), first crossing only
- Geometry: V-TIME family standard — SL=TP=q98(|MFE|∪|MAE|) on first-half signals only
- V78: project-frozen general quiet filter qv=78 (S404 precedent), causal
  (day k quiet if vol_ref[k−1] ≤ rolling-250d q78, min 60 samples)

## 2. Locked configuration (first half only, split 2018-10-20)

| TF | arm | n_sig | SL=TP | n_fh | WR_fh | t_fh | DD_fh |
|----|-----|-------|-------|------|-------|------|-------|
| M5 | BARE-h12 | 2339 | 67.3 | 1146 | 37.52% | −5.51 | 390% |
| M5 | **BARE-h24 (picked)** | 2339 | 98.0 | 1146 | 43.80% | −3.13 | 289% |
| M5 | V78-h12 | 1726 | 57.9 | 882 | 35.26% | −6.47 | 352% |
| M5 | V78-h24 | 1726 | 79.9 | 882 | 42.63% | −4.15 | 318% |
| M15 | BARE-h4 | 2150 | 72.0 | 1056 | 37.97% | −5.83 | 425% |
| M15 | **BARE-h8 (picked)** | 2150 | 98.1 | 1056 | 43.37% | −3.93 | 366% |
| M15 | V78-h4 | 1602 | 55.9 | 816 | 36.15% | −6.31 | 326% |
| M15 | V78-h8 | 1602 | 83.4 | 816 | 41.91% | −4.74 | 350% |

Event densities (P1 check): BARE M5 58.0%, M15 53.3%; V78 M5 59.4%, M15 55.1%.
S603 gate-density law satisfied (event well above 10%) — but note the density itself is
diagnostic: ~55–60% of ALL days produce an ORB "breakout". The event is far too common to
carry information.

## 3. Preregistered stop gate — BOTH TFs STOPPED_DEAD

Gate (from PREREG, inherited from S564): first-half lift of picked arm vs direction-matched
unconditional null (computed on first-half df only, n_perm=200) must be ≥ +4.0pp, else
STOPPED_DEAD and the second half stays VIRGIN.

| TF | picked | WR_fh | null uncond WR_fh | lift_fh | threshold | result |
|----|--------|-------|-------------------|---------|-----------|--------|
| M5 | BARE-h24 | 43.80% | 43.52% | **+0.28pp** | +4.0pp | **STOPPED_DEAD** |
| M15 | BARE-h8 | 43.37% | 43.37% | **−0.00pp** | +4.0pp | **STOPPED_DEAD** |

The ORB breakout signal is statistically INDISTINGUISHABLE from entering LONG at random
times with the same geometry. Zero conditional information. Every single arm also has
negative first-half t (−3.1 to −6.5): with symmetric SL=TP the raw expectancy is dominated
by spread and the sub-50% WR of a symmetric barrier on a drifting-but-noisy series.

## 4. Prereg predictions — scored

- **P1** (event in 30–50% of days): **FAILED upward** — 53–60%. The breakout is near-universal,
  not selective. This alone predicted death.
- **P2** (V78 > BARE): **FAILED** — V78 arms were uniformly WORSE (t more negative). Quiet
  days do not make ORB cleaner on gold; they just shrink the geometry.
- **P3** (~35% success prior): consistent — layer died. Personal prior honest.

## 5. Heritage law burned into the block

**ORB-breakout on gold is a null event.** A 60-minute opening range is crossed upward on
more than half of all days; conditioning on it adds ZERO winrate lift over unconditional
entry (+0.28pp / −0.00pp measured). Intraday "structure" defined purely by early-session
price extremes carries no directional information on XAUUSD at M5/M15. This complements:
- S563: bare day-open drift = dead
- S404 (parallel): gap events at M30 need the GAP condition, not the range condition
- S330 archive: ORB-fade was also never able to complete — both directions of ORB are barren.

**Morning-structure family status:** day-open drift (S563) dead, ORB breakout (S567) dead,
ORB fade (S330, archived incomplete) unpromising. The family is near-enclosed; any future
morning-structure layer must condition on an EVENT (like gap), not on universal structure.

## 6. Eight common mistakes — proof of avoidance

1. **Look-ahead bias:** OR defined on first 60 min, entry strictly at next candle open after
   the closing crossing candle; quiet flag uses vol_ref of the PREVIOUS completed day vs
   rolling history strictly before it (causal, min 60 samples). Signal excluded if no room
   for entry within data.
2. **Data snooping / multiplicity:** PREREG committed (d555d253) before any computation;
   8 arms declared in advance; cumulative family n_trials 40→48 recorded; NO exploration
   beyond the declared arms.
3. **Survivorship / selection on second half:** second half NEVER touched — both TFs died
   at the preregistered first-half gate. Judgment forbidden by prereg; VIRGIN halves stay virgin.
4. **In-sample optimization leakage:** arm pick and geometry (q98 MFE/MAE) computed on first
   half only; split_bar via searchsorted at 2018-10-20 UTC (calendar.timegm).
5. **Cost blindness:** spread $0.33/oz applied in engine geometry; symmetric SL=TP makes
   spread drag explicit — visible in sub-null WRs.
6. **Small-n illusions:** n_fh = 816–1146 per arm — abundant; constraint-2 (n<30) not at issue.
   Death is a POWER-RICH death: the effect is truly zero, not undersampled.
7. **Null-model dishonesty:** stop-gate null is direction-matched (LONG) unconditional on the
   first-half df only (BUG-NULLUNCOND-safe), n_perm=200; not a shuffled-pnl strawman.
8. **Verdict fabrication:** score 0 REJECT is by the honest-death rule (prereg-mandated
   STOPPED_DEAD ⇒ no engine call, score 0), identical to S564/S613/S533 handling. No
   hand-written engine numbers exist in this report.

## 7. Artifacts

- `results/S567_PREREG_ORB_QUIET_XAUUSD.md` (d555d253)
- `tools/s567_orb_quiet.py` (4af4f533)
- `results/_s567_arms/locked_config.json` — full arm table + stop_check for both TFs

**S567 official verdict: REJECT, score 0. Block ledger: S560 ACCEPT 96 · S561 REJECT 36 ·
S562 ACCEPT 96 · S563 REJECT 19 · S564 REJECT 0 · S565 REJECT 20 · S566 REJECT 12 ·
S567 REJECT 0 · S568/S569 pending.**
