# -*- coding: utf-8 -*-
"""
S606 — استخرِ CALM خالصِ شوکِ انگل (نسخه‌ی گیت‌خورده جانشینِ خام)
=================================================================
پیش‌ثبت: results/S606_PREREG_ENGLE_CALM_POOL.md (ea75dc9b — قبل از هر محاسبه).
  · اعضا: {D1 خام, H8-CALM(W=233), H12-CALM(W=89), H6-CALM(W=233)} — W منجمد از S605.
  · هیچ گریدِ تازه‌ای. margin=0.15، وتوی پس‌ازFIFO 15%.
  · n_trials=5176 + تنش 8000، نولِ منجمد S840، SEED=20260822.
  · pass-rate گیت (قانون گاوس S529) پیش از داوری گزارش می‌شود.
ماشین از s605 (و از آن‌جا s604/s840) وارد می‌شود؛ هیچ تابعی بازنویسی نمی‌شود.
اجرا: python3 strategies/s606_engle_calm_pool.py
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

import warnings
warnings.filterwarnings('ignore')

SESSION = 'S606'
PREREG = 'results/S606_PREREG_ENGLE_CALM_POOL.md'
FROZEN_W = {'H8': 233, 'H12': 89, 'H6': 233}     # از S605؛ D1 خام
SEED = 20260822
N_TRIALS = 5176
N_TRIALS_STRESS = 8000
VETO_SHARE = 0.15
OUT = 'results/_s606_calm_pool'
PARENT_Z = 3.888          # S602 z_obs
PARENT_LIFT = 10.20       # S602 lift pp

B.SEED = SEED
B.N_TRIALS = N_TRIALS
B.N_TRIALS_STRESS = N_TRIALS_STRESS
B.OUT = OUT


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== {SESSION} pure CALM pool · W={FROZEN_W} · seed={SEED} '
          f'n_trials={N_TRIALS} ==', flush=True)
    raws = {tf: B.load_raw(tf) for tf in B.CARDS}
    for tf, m in raws.items():
        sig = S5.sigma_series(m['cl'])
        m['reg'] = {W: S5.regime_ratio(sig, W) for W in set(FROZEN_W.values())}
    raw_g = {tf: B.raw_member(raws[tf]) for tf in B.CARDS}   # سلامت S840

    members, census = [raw_g['D1']], {}
    for tf, W in FROZEN_W.items():
        g, dens = S5.regime_member(raws[tf], W, 'CALM')
        pr = dens['n_calm'] / max(dens['n_sig'] - dens['n_nan'], 1)
        census[tf] = dict(W=W, **dens, pass_rate=round(pr, 4),
                          n_member=g['n'] if g else 0,
                          wr=g['wr'] if g else None, lift=g['lift'] if g else None,
                          lift_raw=raw_g[tf]['lift'])
        print(f'-- {tf}-CALM(W={W}): pass-rate={pr:.1%} '
              f"{'⚠ >75% (گیت مرده)' if pr > 0.75 else '✓'} | n={g['n'] if g else 0} "
              f"WR={g['wr'] if g else 0} lift={g['lift'] if g else 0:+.2f} "
              f"(raw {raw_g[tf]['lift']:+.2f})", flush=True)
        if g is not None:
            members.append(g)
    json.dump(census, open(f'{OUT}/census.json', 'w'), ensure_ascii=False, indent=1)

    print(f'\n[استخر نامزد] {[m["card"] for m in members]} '
          f'lifts={[round(m["lift"], 2) for m in members]}', flush=True)
    trace_veto = []
    while True:
        res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'],
                                  lift=g['lift']) for g in members])
        if res is None:
            print('[توقف] pool تهی.', flush=True)
            return
        pool = res['pool']
        share = pool['src_card'].value_counts(normalize=True)
        used = [g for g in members if g['card'] in set(pool['src_card'])]
        strongest = max(used, key=lambda g: g['lift'])
        s_share = float(share.get(strongest['card'], 0.0))
        print(f'[FIFO shares] {share.round(3).to_dict()} · '
              f'strongest={strongest["card"]} share={s_share:.3f}', flush=True)
        if s_share >= VETO_SHARE or len(used) <= 2:
            break
        weakest = min(used, key=lambda g: g['lift'])
        trace_veto.append(dict(removed=weakest['card'],
                               strongest_share=round(s_share, 4)))
        print(f'[وتوی پس‌ازFIFO] حذف {weakest["card"]} — تکرار', flush=True)
        members = [g for g in members if g['card'] != weakest['card']]

    fifo_cut = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f'[نهایی] members={[g["card"] for g in used]} n={len(pool)} '
          f'(FIFO cut {fifo_cut:.1f}%)', flush=True)

    r, r_st, null, sl_med, tp_med, split_utc, share, holdout = \
        B.adjudicate(pool, used, f'{SESSION}-CALM')
    m = r.get('metrics', {})
    p1 = (m.get('z_obs') or 0) > PARENT_Z
    p2 = (m.get('skill_lift_pp') or 0) > PARENT_LIFT
    print(f"\n[P1] z_obs={m.get('z_obs')} > {PARENT_Z} ⇒ {'✅' if p1 else '❌'}")
    print(f"[P2] lift={m.get('skill_lift_pp')} > {PARENT_LIFT} ⇒ {'✅' if p2 else '❌'}",
          flush=True)

    out = dict(session=SESSION, prereg=PREREG, frozen_W=FROZEN_W, census=census,
               veto_trace=trace_veto,
               members=[dict(card=g['card'], n=g['n'], wr=g['wr'],
                             lift=g['lift']) for g in used],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED, n_trials=N_TRIALS,
               n_trials_stress=N_TRIALS_STRESS, split_utc=split_utc,
               P1_z_beats_parent=bool(p1), P2_lift_beats_parent=bool(p2),
               official=B._slim(r), stress=B._slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    json.dump(out, open(f'{OUT}/verdict.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print(f'[saved] {OUT}/verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
