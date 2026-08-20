# -*- coding: utf-8 -*-
"""
S573 — گسترش استخر آینه‌ای S323 با عضو M15: XAUUSD M15+M30+H1 (TP≥SL)
================================================================================
پیش‌ثبت: `results/S573_PREREG_s323_mirror_pool_add_m15.md` (کامیت 8387a392،
قبل از این اجرا).

تفاوت با S572: (۱) عضو M15 اضافه شد؛ (۲) محور مصنوعی ۱۵دقیقه‌ای؛
(۳) قید توقف C5⁗-الف: اگر greedy عضو M15 را حذف کند ⇒ توقف بدون داوری
(استخر همان S572 قبلاً-داوری‌شده می‌شود — ضد double-dip).

عهدها: n_trials=2803 (تنش 5606) · C5⁗-ب: lift_pool ≥ +8.0pp وگرنه REJECT-STOP ·
یک داوری؛ حکم عیناً · فقط XAUUSD.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, '.')

import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs2 as R2
from engine.rqs2_pool import pool_cards
from tools import s434_fast_data as fd

from strategies.s357_s323_v24_rejudge import (
    DEPLOYED_CFG, signals_backtested, build_null, empirical_p,
)

import warnings
warnings.filterwarnings('ignore')

N_TRIALS = 2803
N_TRIALS_STRESS = 5606
PERM_K = 2000
SEEDS = (23, 101, 777)
SPLIT_FRAC = 0.60
C5B_MIN_POOL_LIFT = 8.0
OUT = 'results/_s573_mirror_m15'
MEMBER_CARDS = ['XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1']
NEW_MEMBER = 'XAUUSD-M15'   # قید C5⁗-الف روی همین است

os.makedirs(OUT, exist_ok=True)


def build_member(card: str) -> dict:
    """عضو با سیگنالِ منجمد + هندسهٔ آینه‌ای slMult↔tpMult (عیناً S572)."""
    asset, tf = card.split('-')
    d = fd.load_fast(asset, tf)
    df = fd.as_dataframe(d)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    cfg = DEPLOYED_CFG[card]

    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    atr_pip_med = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['tpMult'] * atr_pip_med, 1)   # آینه‌ای
    tp = round(cfg['slMult'] * atr_pip_med, 1)
    assert tp >= sl, f"{card}: mirror must give TP>=SL"
    mh = int(cfg['maxHold'])

    sig = signals_backtested(df, asset, dict(
        nearMax=cfg['nearMax'], roomMin=cfg['roomMin'], rsiMax=cfg['rsiMax'],
        slopeMin=cfg['slopeMin'], adxMin=cfg['adxMin'], golden=cfg['golden'],
        hLo=cfg['hLo'], hHi=cfg['hHi']))

    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    n = len(tr)
    wr = 100.0 * float((tr['pnl_pip'] > 0).sum()) / n

    nulls = {}
    for seed in SEEDS:
        null, draws = build_null(df, asset, sig, sl, tp, mh, PERM_K, seed)
        p_emp, _ = empirical_p(draws, wr)
        nulls[seed] = dict(null=null, p_emp=float(p_emp))
    ref = nulls[23]['null']['long']['uncond_wr']
    lift = wr - ref

    print(f"[{card}] src={d['src']} bars={len(df)} n={n} WR={wr:.2f} "
          f"null={ref:.2f} lift={lift:+.2f}pp SL={sl} TP={tp} "
          f"(RR={tp/sl:.2f}) mh={mh}", flush=True)

    return dict(card=card, asset=asset, tf=tf, tr=tr,
                dt=df['dt'].values, sl_pip=sl, tp_pip=tp, mh=mh,
                n=n, wr=wr, lift=float(lift), nulls=nulls, src=d['src'])


def blend_pool_null(members_used, pool_df, seed):
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = 0.0
        num_m = num_s = den_p = 0.0
        kmin = None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
            if w <= 0:
                continue
            dd = m['nulls'][seed]['null'][side]
            if dd.get('uncond_wr') is not None:
                num_u += dd['uncond_wr'] * w
                den_u += w
            if dd.get('perm_mean') is not None and dd.get('perm_sd') is not None:
                num_m += dd['perm_mean'] * w
                num_s += (dd['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = dd.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        if den_p > 0:
            out[side] = dict(uncond_wr=(num_u / den_u) if den_u else None,
                             perm_mean=num_m / den_p,
                             perm_sd=float(np.sqrt(num_s)) / den_p,
                             perm_max=None, perm_k=int(kmin or 0))
        else:
            out[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                             perm_max=None, perm_k=0)
    return out


def main():
    t0 = time.time()
    print(f"S573 — استخر آینه‌ای M15+M30+H1 | n_trials={N_TRIALS}/{N_TRIALS_STRESS} "
          f"K={PERM_K}", flush=True)

    members = [build_member(c) for c in MEMBER_CARDS]

    with open(os.path.join(OUT, 'members.json'), 'w', encoding='utf-8') as fh:
        json.dump([{k: v for k, v in m.items() if k not in ('tr', 'dt', 'nulls')}
                   | {'p_emp_23': m['nulls'][23]['p_emp']} for m in members],
                  fh, ensure_ascii=False, indent=1, default=str)

    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'], lift=m['lift'])
                      for m in members])
    if res is None:
        print('[توقف] هیچ عضو معتبری نماند.', flush=True)
        return
    pool = res['pool']
    used_cards = {u['card'] for u in res['used']}
    print(f"\n[استخر] before={res['n_before']} after_FIFO={res['n_after']} "
          f"used={sorted(used_cards)} dropped={res['dropped']}", flush=True)

    # ── C5⁗-الف: اگر M15 حذف شد ⇒ توقف (استخر = S572 قبلاً داوری‌شده) ──
    if NEW_MEMBER not in used_cards:
        stop = dict(status='C5A_NEW_MEMBER_DROPPED', new_member=NEW_MEMBER,
                    used=sorted(used_cards), dropped=res['dropped'],
                    note='greedy عضو جدید را حذف کرد ⇒ استخر همان S572 است ⇒ '
                         'توقف بدون داوری (ضد double-dip، پیش‌ثبت §۳)')
        with open(os.path.join(OUT, 'c5a_stop.json'), 'w', encoding='utf-8') as fh:
            json.dump(stop, fh, ensure_ascii=False, indent=1)
        print(f"[C5⁗-الف] {NEW_MEMBER} توسط همگنی حذف شد ⇒ توقف بدون داوری.",
              flush=True)
        return

    members_used = [m for m in members if m['card'] in used_cards]

    wr_pool = 100.0 * float((pool['pnl_pip'] > 0).sum()) / len(pool)
    null23 = blend_pool_null(members_used, pool, 23)
    lift_pool = wr_pool - null23['long']['uncond_wr']
    print(f"[استخر] n={len(pool)} WR={wr_pool:.2f} "
          f"null={null23['long']['uncond_wr']:.2f} lift={lift_pool:+.2f}pp",
          flush=True)
    if lift_pool < C5B_MIN_POOL_LIFT:
        stop = dict(status='C5B_VIOLATION', lift_pool=round(lift_pool, 2),
                    bar=C5B_MIN_POOL_LIFT,
                    note='رقیق‌سازی طبق پیش‌ثبت §۳ ⇒ REJECT-STOP')
        with open(os.path.join(OUT, 'c5b_violation.json'), 'w', encoding='utf-8') as fh:
            json.dump(stop, fh, ensure_ascii=False, indent=1)
        print(f"[C5⁗-ب نقض] lift_pool={lift_pool:.2f} < {C5B_MIN_POOL_LIFT} ⇒ توقف",
              flush=True)
        return

    # محور ۱۵دقیقه‌ای (ریزترین عضو = M15)
    STEP_NS = 15 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS, dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f"[محور] ۱۵دقیقه‌ای {axis_dt[0]} → {axis_dt[-1]} · {len(axis_t):,} سطل",
          flush=True)

    dh = fd.load_fast('XAUUSD', 'H1')
    ref_t = (dh['time'].astype(np.int64)) * 1_000_000_000
    ref_c = dh['close']
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, pool['t_entry'].values, 'left'),
                                0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(axis_t, pool['t_exit'].values, 'left'),
                               0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    te = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te, SPLIT_FRAC))
    holdout = te >= split_ns
    print(f"[تقسیم] مرز={np.datetime64(split_ns, 'ns')} · "
          f"اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}",
          flush=True)

    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by = {m['card']: m for m in members_used}
    sl_med = float(sum(by[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by[c]['tp_pip'] * w for c, w in shares.items()))
    assert tp_med >= sl_med, "پیش‌ثبت §۳: هندسهٔ وزنی باید TP>=SL بدهد"
    print(f"[هندسه] SL={sl_med:.1f} TP={tp_med:.1f} RR={tp_med/sl_med:.2f} "
          f"shares={shares}", flush=True)

    out_all = {}
    for seed in SEEDS:
        null = blend_pool_null(members_used, pool, seed)
        rr = {}
        for label, nt in (('honest', N_TRIALS), ('stress', N_TRIALS_STRESS)):
            r = R2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                                bar_time=axis_dt, close=axis_close, null=null,
                                n_trials=nt, holdout_mask=holdout,
                                allow_overlap=False)
            rr[label] = dict(verdict=r.get('verdict'), score=r.get('rqs2_score'),
                             gates=r.get('gates'), metrics=r.get('metrics'),
                             notes=r.get('notes'))
            if seed == 23 and label == 'honest':
                print('\n' + R2.format_rqs2('S573-M15POOL', r), flush=True)
        m0 = rr['honest']['metrics']
        g = rr['honest']['gates']
        gl = ''.join('1' if g.get(k) else ('?' if g.get(k) is None else '0')
                     for k in R2.GATE_NAMES)
        print(f"seed={seed} | lift={m0.get('skill_lift_pp')} z={m0.get('skill_z')} "
              f"honest={rr['honest']['verdict']}({rr['honest']['score']}) "
              f"stress={rr['stress']['verdict']}({rr['stress']['score']}) G[{gl}]",
              flush=True)
        out_all[str(seed)] = rr

    rec = dict(session='S573', variant='mirror_pool_plus_M15',
               members=[dict(card=m['card'], n=m['n'], wr=round(m['wr'], 2),
                             lift=round(m['lift'], 2), sl=m['sl_pip'],
                             tp=m['tp_pip'], src=m['src']) for m in members],
               used=sorted(used_cards), dropped=res['dropped'],
               selection=res['selection'],
               n_before=res['n_before'], n_after=res['n_after'],
               pool_wr=round(wr_pool, 2), pool_lift=round(lift_pool, 2),
               shares=shares, sl_pip=sl_med, tp_pip=tp_med,
               rr_ratio=round(tp_med / sl_med, 3),
               split_utc=str(np.datetime64(split_ns, 'ns')),
               n_trials=N_TRIALS, seeds=out_all,
               elapsed_s=round(time.time() - t0, 1))
    with open(os.path.join(OUT, 'S573_verdict.json'), 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1, default=str)
    print(f"\n→ wrote {OUT}/S573_verdict.json  ({rec['elapsed_s']}s)", flush=True)


if __name__ == '__main__':
    main()
