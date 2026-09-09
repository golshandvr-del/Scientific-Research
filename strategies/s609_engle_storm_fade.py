# -*- coding: utf-8 -*-
"""
S609 — ضدِ آزمون: شوکِ STORM با mode=fade — H8/H6/H12
====================================================
پیش‌ثبت: results/S609_PREREG_ENGLE_STORM_FADE.md (f63bb56c — قبل از هر محاسبه).
  · فقط mode معکوس می‌شود (fade)؛ z_thr/sl_k/rr/hold از is_winner منجمد S840.
  · گیت STORM: σ_t > median(σ_{t-W..t-1}) — W: H8/H6=233، H12=89.
  · نول منجمد per-side S840؛ margin=0.15؛ وتوی FIFO 15%.
  · n_trials=5179 + تنش 8000، SEED=20260825. داده: data/mt5_full.
اجرا: python3 strategies/s609_engle_storm_fade.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import engine.rqs2_pool as rp
import strategies.s604_engle_drift as B
import strategies.s605_engle_sigma_regime as S5
from strategies.s840_engle_shock import signals_for

import warnings
warnings.filterwarnings('ignore')

SESSION = 'S609'
PREREG = 'results/S609_PREREG_ENGLE_STORM_FADE.md'
CARDS_W = {'H8': 233, 'H6': 233, 'H12': 89}
SEED = 20260825
N_TRIALS = 5179
N_TRIALS_STRESS = 8000
VETO_SHARE = 0.15
OUT = 'results/_s609_storm_fade'

B.SEED = SEED
B.N_TRIALS = N_TRIALS
B.N_TRIALS_STRESS = N_TRIALS_STRESS
B.OUT = OUT


def storm_fade_member(m, W):
    w = m['w']
    idx, isl = signals_for(m['z'], m['atr'], w['z_thr'], 'fade', m['warmup'])
    reg = m['reg'][W][idx]
    ok = np.isfinite(reg)
    storm = ok & (reg > 1.0)
    census = dict(W=W, n_sig=int(len(idx)), n_valid=int(ok.sum()),
                  n_storm=int(storm.sum()),
                  pass_rate=round(float(storm[ok].mean()) if ok.any() else 0, 4))
    if storm.sum() < 5:
        return None, census
    return B.member_from_idx(m, idx[storm], isl[storm]), census


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== {SESSION} STORM-fade · {CARDS_W} · seed={SEED} n_trials={N_TRIALS} ==',
          flush=True)
    members, census = [], {}
    for tf, W in CARDS_W.items():
        m = B.load_raw(tf)
        B.raw_member(m)                             # سلامت follow خام
        sig = S5.sigma_series(m['cl'])
        m['reg'] = {W: S5.regime_ratio(sig, W)}
        g, c = storm_fade_member(m, W)
        c.update(n_member=g['n'] if g else 0, wr=g['wr'] if g else None,
                 lift=g['lift'] if g else None,
                 n_long=int((g['tr']['direction'] == 'long').sum()) if g else 0)
        census[tf] = c
        print(f"-- {tf}-STORM-fade(W={W}): pass={c['pass_rate']:.1%} n={c['n_member']} "
              f"WR={c['wr']} lift={c['lift']}", flush=True)
        if g is not None:
            members.append(g)
    json.dump(census, open(f'{OUT}/census.json', 'w'), ensure_ascii=False, indent=1)

    lifts = {tf: c['lift'] for tf, c in census.items() if c['lift'] is not None}
    p1 = sum(1 for v in lifts.values() if v > 3.0) >= 2
    p2 = all(-3.0 <= v <= 3.0 for v in lifts.values())
    print(f"\n[P1] fade lift>+3 در ≥2/3 ⇒ {'✅' if p1 else '❌'} {lifts}")
    print(f"[P2] همه در [-3,+3] (بی‌اطلاع) ⇒ {'✅' if p2 else '❌'}", flush=True)

    base = dict(session=SESSION, prereg=PREREG, cards_W=CARDS_W, census=census,
                P1_reversal=bool(p1), P2_uninformative=bool(p2), seed=SEED,
                n_trials=N_TRIALS, n_trials_stress=N_TRIALS_STRESS)
    res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'], lift=g['lift'])
                         for g in members]) if members else None
    if res is None:
        print('[حکم] هیچ عضوِ هم‌جهتی (lift>0) نماند ⇒ REJECT بدونِ داوریِ ممکن.',
              flush=True)
        json.dump(dict(base, verdict='REJECT', rqs2_score=None,
                       note='all members lift<=0 — pool_cards rejected all'),
                  open(f'{OUT}/verdict.json', 'w'), ensure_ascii=False, indent=1,
                  default=str)
        print('FINISHED', flush=True)
        return

    trace_veto = []
    while True:
        pool = res['pool']
        share = pool['src_card'].value_counts(normalize=True)
        used = [g for g in members if g['card'] in set(pool['src_card'])]
        strongest = max(used, key=lambda g: g['lift'])
        s_share = float(share.get(strongest['card'], 0.0))
        print(f'[FIFO shares] {share.round(3).to_dict()} dropped={res["dropped"]}',
              flush=True)
        if s_share >= VETO_SHARE or len(used) <= 2:
            break
        weakest = min(used, key=lambda g: g['lift'])
        trace_veto.append(dict(removed=weakest['card'], strongest_share=round(s_share, 4)))
        members = [g for g in members if g['card'] != weakest['card']]
        res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'], lift=g['lift'])
                             for g in members])
    fifo_cut = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f'[نهایی] members={[g["card"] for g in used]} n={len(pool)} '
          f'(FIFO cut {fifo_cut:.1f}%)', flush=True)
    r, r_st, null, sl_med, tp_med, split_utc, share, holdout = \
        B.adjudicate(pool, used, f'{SESSION}-STORMFADE')
    out = dict(base, veto_trace=trace_veto, dropped=res['dropped'],
               members=[dict(card=g['card'], n=g['n'], wr=g['wr'], lift=g['lift'])
                        for g in used],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2), member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, split_utc=split_utc,
               official=B._slim(r), stress=B._slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    json.dump(out, open(f'{OUT}/verdict.json', 'w'), ensure_ascii=False, indent=1,
              default=str)
    print(f'[saved] {OUT}/verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
