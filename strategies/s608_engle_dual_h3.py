# -*- coding: utf-8 -*-
"""
S608 — احیای کارتِ سوخته‌ی H3 با گیت DUAL منجمدِ S607 — داوری تک‌کارتی
=====================================================================
پیش‌ثبت: results/S608_PREREG_ENGLE_DUAL_GATE_H3_REVIVAL.md (3a00cfed — قبل از هر
محاسبه). H3: K=60d=480 کندل، W=233؛ کارت خام از is_winner منجمد S840.
n_trials=5178 + تنش 8000، SEED=20260824. داده: data/mt5_full/XAUUSD_H3.csv.
ماشین از s604/s605/s607 وارد می‌شود؛ هیچ تابعی بازنویسی نمی‌شود.
اجرا: python3 strategies/s608_engle_dual_h3.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine.rqs2_pool as rp
import strategies.s604_engle_drift as B
import strategies.s605_engle_sigma_regime as S5
import strategies.s607_engle_dual_gate as S7

import warnings
warnings.filterwarnings('ignore')

SESSION = 'S608'
PREREG = 'results/S608_PREREG_ENGLE_DUAL_GATE_H3_REVIVAL.md'
TF = 'H3'
K_DAYS, W = 60, 233
SEED = 20260824
N_TRIALS = 5178
N_TRIALS_STRESS = 8000
OUT = 'results/_s608_dual_h3'
EXPECTED_H3 = dict(n=1038, wr=44.99)

B.SEED = SEED
B.N_TRIALS = N_TRIALS
B.N_TRIALS_STRESS = N_TRIALS_STRESS
B.OUT = OUT
B.BARS_PER_DAY = dict(B.BARS_PER_DAY, H3=8)     # ۸ کندلِ H3 در روز — از پیش‌ثبت
B.EXPECTED = dict(B.EXPECTED, H3=EXPECTED_H3)


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== {SESSION} DUAL gate on burnt H3 · K={K_DAYS}d W={W} · seed={SEED} '
          f'n_trials={N_TRIALS} ==', flush=True)
    m = B.load_raw(TF)
    print(f"data src: {m['df'].attrs.get('src', 'data/mt5_full')} bars={len(m['df'])}",
          flush=True)
    sig = S5.sigma_series(m['cl'])
    m['reg'] = {W: S5.regime_ratio(sig, W)}
    raw = B.raw_member(m)                       # سلامت: 1038 / 44.99
    g, c = S7.dual_member(m, K_DAYS, W)
    c.update(K=K_DAYS, W=W, n_member=g['n'] if g else 0,
             wr=g['wr'] if g else None, lift=g['lift'] if g else None,
             lift_raw=raw['lift'], wr_raw=raw['wr'], n_raw=raw['n'])
    print(f"-- H3-DUAL: PR drift={c['pr_drift']:.1%} calm={c['pr_calm']:.1%} "
          f"dual={c['pr_dual']:.1%} ratio={c['collinearity_ratio']} | "
          f"n={c['n_member']} WR={c['wr']} lift={c['lift']} "
          f"(raw n={raw['n']} WR={raw['wr']} lift={raw['lift']:+.2f})", flush=True)
    json.dump(c, open(f'{OUT}/census.json', 'w'), ensure_ascii=False, indent=1)
    if g is None:
        print('[توقف] عضو تهی.', flush=True)
        return
    p1 = g['n'] >= 150 and g['lift'] >= raw['lift'] + 2.0
    p2 = g['wr'] >= 50.0
    print(f"[P1] n={g['n']}>=150 & lift {g['lift']:+.2f} >= raw+2 ⇒ {'✅' if p1 else '❌'}")
    print(f"[P2] WR={g['wr']} >= 50 ⇒ {'✅' if p2 else '❌'}", flush=True)

    res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'], lift=g['lift'])])
    if res is None:
        print('[توقف] pool_cards عضو را رد کرد (lift<=0).', flush=True)
        verdict = dict(session=SESSION, prereg=PREREG, census=c,
                       verdict='REJECT', rqs2_score=None,
                       note='lift<=0 — not co-directional; no adjudication possible')
        json.dump(verdict, open(f'{OUT}/verdict.json', 'w'), ensure_ascii=False,
                  indent=1, default=str)
        return
    pool = res['pool']
    fifo_cut = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f'[FIFO] n={len(pool)} (cut {fifo_cut:.1f}%)', flush=True)
    r, r_st, null, sl_med, tp_med, split_utc, share, holdout = \
        B.adjudicate(pool, [g], f'{SESSION}-H3DUAL')
    out = dict(session=SESSION, prereg=PREREG, tf=TF, K_days=K_DAYS, W=W,
               census=c, P1=bool(p1), P2=bool(p2),
               member=dict(card=g['card'], n=g['n'], wr=g['wr'], lift=g['lift']),
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED, n_trials=N_TRIALS,
               n_trials_stress=N_TRIALS_STRESS, split_utc=split_utc,
               official=B._slim(r), stress=B._slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    json.dump(out, open(f'{OUT}/verdict.json', 'w'), ensure_ascii=False,
              indent=1, default=str)
    print(f'[saved] {OUT}/verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
