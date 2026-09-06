# -*- coding: utf-8 -*-
"""
S607 — شوکِ انگل با دو گیتِ متعامد (drift S604 AND calm S606) — صفر پارامتر آزاد
==============================================================================
پیش‌ثبت: results/S607_PREREG_ENGLE_DUAL_GATE.md (c7d5a3d7 — قبل از هر محاسبه).
  · H8: K=60d, W=233 · H12: K=30d, W=89 · H6: K=60d, W=233 · D1 خام.
  · هم‌خطی: PR_dual/(PR_drift·PR_calm) پیش از داوری.
  · margin=0.15، وتوی پس‌ازFIFO 15%، n_trials=5177 + تنش 8000، SEED=20260823.
ماشین از s604/s605 وارد می‌شود؛ هیچ تابعی بازنویسی نمی‌شود.
اجرا: python3 strategies/s607_engle_dual_gate.py
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

SESSION = 'S607'
PREREG = 'results/S607_PREREG_ENGLE_DUAL_GATE.md'
FROZEN = {'H8': dict(K=60, W=233), 'H12': dict(K=30, W=89), 'H6': dict(K=60, W=233)}
SEED = 20260823
N_TRIALS = 5177
N_TRIALS_STRESS = 8000
VETO_SHARE = 0.15
OUT = 'results/_s607_dual_gate'
PARENT_LIFT = 12.49       # max(S604 +11.39, S606 +12.49)

B.SEED = SEED
B.N_TRIALS = N_TRIALS
B.N_TRIALS_STRESS = N_TRIALS_STRESS
B.OUT = OUT


def dual_member(m, K_days, W):
    w = m['w']
    idx, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    K = K_days * B.BARS_PER_DAY[m['tf']]
    cl = m['cl']
    reg = m['reg'][W][idx]
    calm = np.isfinite(reg) & (reg <= 1.0)
    drift_ok = np.zeros(len(idx), bool)
    for j, i in enumerate(idx):
        if i - 1 - K < 0:
            continue
        d = cl[i - 1] - cl[i - 1 - K]
        drift_ok[j] = (d > 0) if bool(isl[j]) else (d < 0)
    valid = np.isfinite(reg) & (np.arange(len(idx)) >= 0) & \
        (idx - 1 - K >= 0)
    n_valid = int(valid.sum())
    pr_d = float(drift_ok[valid].mean()) if n_valid else float('nan')
    pr_c = float(calm[valid].mean()) if n_valid else float('nan')
    dual = drift_ok & calm & valid
    pr_dual = float(dual[valid].mean()) if n_valid else float('nan')
    ratio = pr_dual / (pr_d * pr_c) if pr_d * pr_c > 0 else float('nan')
    census = dict(n_sig=int(len(idx)), n_valid=n_valid, pr_drift=round(pr_d, 4),
                  pr_calm=round(pr_c, 4), pr_dual=round(pr_dual, 4),
                  collinearity_ratio=round(ratio, 3), n_dual=int(dual.sum()))
    if dual.sum() < 5:
        return None, census
    return B.member_from_idx(m, idx[dual], isl[dual]), census


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== {SESSION} DUAL gate · {FROZEN} · seed={SEED} n_trials={N_TRIALS} ==',
          flush=True)
    raws = {tf: B.load_raw(tf) for tf in B.CARDS}
    for tf, m in raws.items():
        sig = S5.sigma_series(m['cl'])
        m['reg'] = {W: S5.regime_ratio(sig, W) for W in {89, 233}}
    raw_g = {tf: B.raw_member(raws[tf]) for tf in B.CARDS}

    members, census = [raw_g['D1']], {}
    for tf, p in FROZEN.items():
        g, c = dual_member(raws[tf], p['K'], p['W'])
        c.update(K=p['K'], W=p['W'], n_member=g['n'] if g else 0,
                 wr=g['wr'] if g else None, lift=g['lift'] if g else None,
                 lift_raw=raw_g[tf]['lift'])
        census[tf] = c
        print(f"-- {tf}-DUAL: PR drift={c['pr_drift']:.1%} calm={c['pr_calm']:.1%} "
              f"dual={c['pr_dual']:.1%} ratio={c['collinearity_ratio']} "
              f"{'⚠ هم‌خطی' if c['collinearity_ratio'] > 1.5 else '✓'} | "
              f"n={c['n_member']} WR={c['wr']} lift={c['lift']} (raw {c['lift_raw']:+.2f})",
              flush=True)
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
        B.adjudicate(pool, used, f'{SESSION}-DUAL')
    m = r.get('metrics', {})
    p1 = (m.get('skill_lift_pp') or 0) > PARENT_LIFT
    p2 = len(pool) >= 150
    print(f"\n[P1] lift={m.get('skill_lift_pp')} > {PARENT_LIFT} ⇒ {'✅' if p1 else '❌'}")
    print(f"[P2] n={len(pool)} >= 150 ⇒ {'✅' if p2 else '❌'}", flush=True)

    out = dict(session=SESSION, prereg=PREREG, frozen=FROZEN, census=census,
               veto_trace=trace_veto,
               members=[dict(card=g['card'], n=g['n'], wr=g['wr'],
                             lift=g['lift']) for g in used],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED, n_trials=N_TRIALS,
               n_trials_stress=N_TRIALS_STRESS, split_utc=split_utc,
               P1_lift_beats_parents=bool(p1), P2_n_ge_150=bool(p2),
               official=B._slim(r), stress=B._slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    json.dump(out, open(f'{OUT}/verdict.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print(f'[saved] {OUT}/verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
