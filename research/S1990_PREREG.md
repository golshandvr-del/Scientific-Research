# S1990 PREREG — AsianFreshLowFadeLong (XAUUSD H1) — Lagrange decade S1990–S1999

**Committed BEFORE any second-half (holdout) number.** Route C. Exploration only — no site changes.

## Path to this rule (three families searched on the first half, per corrective rule 3)
- A. Bear-shock absorption fade (`research/s1990_explore/bear_shock_absorption.json`, 160 cells): null; best z 1.47 with pnl<0. Closed.
- B. Fresh 90-record × server session (`record_session.json`, 48 cells): session gate does not create an edge for following records
  (H4 fresh-low short +7.8pp raw ≈ +9.9pp gated on half the n → P1 fails). Side finding: H1 fresh LOWS made in the Asian session (00–08 server)
  fail systematically when followed (short lift −10.7pp, z −2.95, 1/8 yrs).
- C. Direct test of the fade (12 cells, output in commit message / this file): H1 LONG on Asian fresh-low: n=188 lift +5.76/+5.79pp (rr 1.0/1.5), z 1.58, 5/8 yrs, pnl +1.2/+3.1;
  H2 +7.6pp z 1.71 (n=125). Control (fade Asian fresh HIGH → short): −6.2pp — the effect is one-sided (thin Asian liquidity + gold's secular long drift), not "Asian records are noise". CALM gate destroys it (n→59, lift<0).
- No cell reaches z_fair ≥ 2.5. Per the user's numbering law the number gets an official verdict on the most novel, P1-consistent, max-power cell.

## Frozen rule (no free parameter remains)
- TF **H1**, side **LONG**, max_hold 48, allow_overlap False.
- Event: close_t < min(close[t−90..t−1]) and not on t−1 (fresh 90-low, S526 mirror) AND server hour of bar t ∈ [00,08).
- Entry: next bar open (engine convention). SL = 1.5 × median(rolling-mean TR100)/0.1 pip on holdout (geometry only); TP = 1.5 × SL.
- Null within the Asian gate: hardest gated stride {3,7,13}; permutation K=500 within gate, seed 19901990. split_bar = 0.70·len.
- n_trials honest = 160 + 48 + 12 = **220**.

## Prediction
- **REJECT / POWER-LIMITED** (expected n ≈ 180–220, lift +3…+6pp, z < 3). ACCEPT would require lift ≥ +10pp.
- If holdout lift < 0 → Asian-liquidity family CLOSED for the decade.

One run only. Verdict MD: `results/S1990_AsianFreshLowFadeLong_Xauusd_H1_rqs2_<score>_<verdict>.md`.
