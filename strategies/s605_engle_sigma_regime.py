# -*- coding: utf-8 -*-
"""
S605 — شوکِ انگل در رژیمِ σ (CALM/STORM) — احیای کارت‌ها + تقویت استخر
======================================================================
پیش‌ثبت: results/S605_PREREG_ENGLE_SHOCK_SIGMA_REGIME.md (9db3591f — قبل از هر
محاسبه). خلاصه‌ی عهد:

  · رژیمِ علّی: reg_t = σ_t / median(σ_{t-W..t-1})، W∈{89,233,610} کندل.
    CALM ⇔ reg_t ≤ 1.0 ؛ STORM ⇔ reg_t > 1.0. گیت روی کندل سیگنال.
  · P1: لیفت CALM > لیفت STORM (کشف). اگر در ≥3 از ۴ کارت نقض شود ⇒ باطل.
  · احیا (فقط کشف، پیش از 2020-01-06T17:36): n_disc≥60 و
    lift_disc(CALM) ≥ lift_disc(raw)+2pp → بهترین W.
  · استخر: {D1خام,H8خام} ∪ گیت‌خورده‌ها (کارت خام والد مقدم)؛ margin=0.15؛
    وتوی پس‌ازFIFO: سهم قوی‌ترین <15% ⇒ حذف ضعیف‌ترین، تکرار.
  · داوری: n_trials=5175 + تنش 8000، نول منجمد S840، SEED=20260821.
  · چگالیِ CALM/STORM هر کارت پیش از داوری شمرده و ثبت می‌شود (قانون S603).

ماشینِ منجمد از strategies/s604_engle_drift.py وارد می‌شود (بدون تغییر در آن).
اجرا: python3 strategies/s605_engle_sigma_regime.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

import engine.rqs2_pool as rp
import strategies.s604_engle_drift as B
from strategies.s840_engle_shock import signals_for, ewma_z, LAMBDA

import warnings
warnings.filterwarnings('ignore')

SESSION = 'S605'
PREREG = 'results/S605_PREREG_ENGLE_SHOCK_SIGMA_REGIME.md'
W_GRID = (89, 233, 610)
SEED = 20260821
N_TRIALS = 5175
N_TRIALS_STRESS = 8000
VETO_SHARE = 0.15
OUT = 'results/_s605_sigma_regime'

# ماشین S604 با پارامترهای S605 (فقط ثابت‌های ماژول؛ هیچ تابعی بازنویسی نمی‌شود)
B.SEED = SEED
B.N_TRIALS = N_TRIALS
B.N_TRIALS_STRESS = N_TRIALS_STRESS
B.OUT = OUT


def sigma_series(cl):
    """σ_t همان σ فریزِ ewma_z (RiskMetrics λ=0.94) — بازسازیِ عینیِ فرمول S840."""
    c = np.asarray(cl, float)
    r = np.zeros(len(c))
    r[1:] = np.diff(np.log(c))
    var = np.full(len(c), np.nan)
    k0 = min(50, len(c) - 1)
    if k0 < 5:
        return var
    v = float(np.var(r[1:k0 + 1]))
    for t in range(k0 + 1, len(c)):
        var[t] = v
        v = LAMBDA * v + (1 - LAMBDA) * r[t] ** 2
    return np.sqrt(var)


def regime_ratio(sig, W):
    """reg_t = σ_t / median(σ_{t-W..t-1}) — علّی (پنجره‌ی گذشته‌ی بسته)."""
    s = pd.Series(sig)
    med = s.shift(1).rolling(W, min_periods=W).median().values
    with np.errstate(divide='ignore', invalid='ignore'):
        return sig / med


def regime_member(m, W, arm):
    w = m['w']
    idx, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    reg = m['reg'][W][idx]
    ok = np.isfinite(reg)
    calm = ok & (reg <= 1.0)
    storm = ok & (reg > 1.0)
    sel = calm if arm == 'CALM' else storm
    density = dict(n_sig=int(len(idx)), n_calm=int(calm.sum()),
                   n_storm=int(storm.sum()), n_nan=int((~ok).sum()))
    if sel.sum() < 5:
        return None, density
    return B.member_from_idx(m, idx[sel], isl[sel]), density


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== {SESSION} sigma-regime Engle · W={W_GRID} · seed={SEED} '
          f'n_trials={N_TRIALS} ==', flush=True)
    raws = {tf: B.load_raw(tf) for tf in B.CARDS}
    for tf, m in raws.items():
        sig = sigma_series(m['cl'])
        # سلامت: σ بازسازی‌شده باید با z فریز سازگار باشد (z=r/σ)
        r = np.zeros(len(m['cl'])); r[1:] = np.diff(np.log(m['cl']))
        msk = np.isfinite(m['z']) & np.isfinite(sig) & (sig > 0)
        err = float(np.nanmax(np.abs(m['z'][msk] - r[msk] / sig[msk])))
        print(f'-- {tf} σ-reconstruction max|Δz|={err:.2e} '
              f"⇒ {'✅' if err < 1e-6 else '❌'}", flush=True)
        if err >= 1e-6:
            raise RuntimeError(f'sigma reconstruction failed for {tf}')
        m['reg'] = {W: regime_ratio(sig, W) for W in W_GRID}
    raw_g = {tf: B.raw_member(raws[tf]) for tf in B.CARDS}

    # ---------------- گام ۱: P1 + احیا ----------------
    explore, revived, p1 = [], {}, {}
    for tf in B.CARDS:
        n_raw_d, wr_raw_d, lift_raw_d = B.disc_stats(raw_g[tf])
        print(f'[{tf}] raw disc: n={n_raw_d} WR={wr_raw_d:.2f} '
              f'lift={lift_raw_d:+.2f}', flush=True)
        best = None
        p1_votes = []
        for W in W_GRID:
            gc, dens = regime_member(raws[tf], W, 'CALM')
            gs, _ = regime_member(raws[tf], W, 'STORM')
            row = dict(tf=tf, W=W, **dens)
            for arm, g in (('CALM', gc), ('STORM', gs)):
                if g is None:
                    row[arm] = None
                    continue
                n_d, wr_d, lift_d = B.disc_stats(g)
                row[arm] = dict(n_full=g['n'], n_disc=n_d, wr_disc=round(wr_d, 2),
                                lift_disc=round(lift_d, 2))
            row['lift_raw_disc'] = round(lift_raw_d, 2)
            explore.append(row)
            lc = row['CALM']['lift_disc'] if row['CALM'] else None
            ls = row['STORM']['lift_disc'] if row['STORM'] else None
            print(f'  W={W:>3}: sig={dens["n_sig"]} calm={dens["n_calm"]} '
                  f'storm={dens["n_storm"]} | CALM lift={lc} '
                  f'(n_disc={row["CALM"]["n_disc"] if row["CALM"] else 0}) '
                  f'| STORM lift={ls}', flush=True)
            if lc is not None and ls is not None:
                p1_votes.append(lc > ls)
            if row['CALM'] and row['CALM']['n_disc'] >= B.MIN_N_DISC and \
                    lc >= lift_raw_d + B.REVIVE_LIFT_GAIN:
                if best is None or lc > best[1]:
                    best = (W, lc, gc)
        p1[tf] = dict(votes=p1_votes, calm_wins=bool(p1_votes and
                                                     sum(p1_votes) > len(p1_votes) / 2))
        if best:
            revived[tf] = dict(W=best[0], g=best[2])
            print(f'  ⇒ {tf} REVIVED با W={best[0]} (CALM)', flush=True)
        else:
            print(f'  ⇒ {tf}: احیا نشد', flush=True)
    n_calm_wins = sum(1 for v in p1.values() if v['calm_wins'])
    p1_falsified = (len(B.CARDS) - n_calm_wins) >= 3
    print(f'\n[P1] CALM>STORM در {n_calm_wins}/{len(B.CARDS)} کارت ⇒ '
          f"{'باطل ❌' if p1_falsified else 'تأیید ✅'}", flush=True)
    json.dump(dict(explore=explore, p1=p1, p1_falsified=p1_falsified),
              open(f'{OUT}/explore_grid.json', 'w'), ensure_ascii=False,
              indent=1, default=str)

    # ---------------- گام ۲: استخر + وتوی پس‌ازFIFO ----------------
    members = [raw_g[tf] for tf in B.RAW_POOL]
    for tf, rv in revived.items():
        if tf in B.RAW_POOL:
            continue
        members.append(rv['g'])
    print(f'\n[استخر نامزد] {[m["card"] for m in members]} '
          f'lifts={[m["lift"] for m in members]}', flush=True)
    if len(members) == len(B.RAW_POOL):
        print('[توجه] هیچ کارتی احیا نشد ⇒ استخر = والد S602 (تکرارِ محض). '
              'داوری برای ثبت حکم رسمیِ شماره‌ی S605 انجام می‌شود.', flush=True)

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
        B.adjudicate(pool, used, f'{SESSION}-SIGMA')

    out = dict(session=SESSION, prereg=PREREG,
               revived={tf: rv['W'] for tf, rv in revived.items()},
               p1=p1, p1_falsified=p1_falsified,
               explore=explore, veto_trace=trace_veto,
               members=[dict(card=g['card'], n=g['n'], wr=g['wr'],
                             lift=g['lift']) for g in used],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED, n_trials=N_TRIALS,
               n_trials_stress=N_TRIALS_STRESS, split_utc=split_utc,
               official=B._slim(r), stress=B._slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    json.dump(out, open(f'{OUT}/verdict.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print(f'[saved] {OUT}/verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
