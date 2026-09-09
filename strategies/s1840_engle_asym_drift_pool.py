# -*- coding: utf-8 -*-
"""
S1840 — استخر همگنِ شوک × درفت انگل (Pool of S849 {H6,H8,H12,D1})
===================================================================
پیش‌ثبت: results/S1840_PREREG_engle_asym_drift_homogeneous_pool.md (کامیت 43a9a185)
دستور پخت S431/S843. اعضا و نول‌ها عیناً از results/_scan_S849/{TF}.json خوانده
می‌شوند (صفر پارامتر آزاد). یک استخر، یک آزمون. n_trials رسمی = 101.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2                                  # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402
from strategies.s840_engle_shock import (                # noqa: E402
    ASSET, TF_HOLD, SPLIT_FRAC, atr_series, ewma_z, queue_frozen)
from strategies.s849_engle_asym_shock_drift import asym_signals, RR_FIXED  # noqa: E402
from strategies.s843_engle_shock_pool import fifo_calendar, blend_pool_null  # noqa: E402

OUT = 'results/_scan_S1840'
SRC = 'results/_scan_S849'
MEMBER_TFS = ('H6', 'H8', 'H12', 'D1')
N_TRIALS_OFFICIAL = 101         # 24×4 IS + 4 per-TF judgments + 1 (this)
N_TRIALS_STRESS = 500
STEP_NS = 3600 * 1_000_000_000


def load_member(tf):
    ck = json.load(open(os.path.join(SRC, f'{tf}.json')))
    assert ck.get('verdict') == 'POWER-LIMITED', f'{tf} not PL in S849'
    w = ck['is_winner']
    return dict(tf=tf, z_up=w['z_up'], z_dn=w['z_dn'], K=w['K'],
                sl_k=w['sl_k'], null=ck['null'])


def reproduce_member(m):
    tf = m['tf']
    hold = TF_HOLD[tf]
    d = fd.load_fast(ASSET, tf)
    assert 'mt5_full' in str(d.get('src')), f'{tf}: data not mt5_full — STOP'
    df = fd.as_dataframe(d)
    n = len(df)
    warmup = 250 if n >= 5000 else max(60, n // 10)
    split = int(n * SPLIT_FRAC)
    t = df['time'].values.astype(np.int64) * 1_000_000_000
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    z, _ = ewma_z(cl)
    sig, isl = asym_signals(z, cl, atr, m['z_up'], m['z_dn'], m['K'], warmup)
    st = queue_frozen(df, sig, isl, m['sl_k'] * atr[sig], hold, RR_FIXED)
    if st is None:
        return None
    eb = st['entry_bar'].astype(int)
    xb = np.minimum(st['exit_bar'].astype(int), n - 1)
    tr = pd.DataFrame(dict(
        pnl_pip=st['pnl'],
        outcome=np.where(st['win'], 'win', 'loss'),
        sl_pip=st['sl_pip'], tp_pip=st['tp_pip'],
        direction=np.where(st['is_long'], 'long', 'short'),
        t_entry=t[eb], t_exit=t[xb], src_card=tf))
    split_t = int(t[split])
    print(f"  [{tf}] reproduced n={len(tr)} WR={st['wr']:.2f}% "
          f"exp={st['exp']:+.3f}pip sl_med={np.median(st['sl_pip']):.1f} "
          f"split_time={np.datetime64(split_t, 'ns')} src={d.get('src')}",
          flush=True)
    return dict(tf=tf, trades=tr, split_t=split_t, null=m['null'],
                sl_med=float(np.median(st['sl_pip'])),
                tp_med=float(np.median(st['tp_pip'])), n_member=len(tr),
                wr_member=round(st['wr'], 2))


def _slim(r):
    keep = dict(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
                gates=dict(r.get('gates', {})), notes=r.get('notes'))
    mm = r.get('metrics', {})
    keep['metrics'] = {k: mm[k] for k in mm if isinstance(
        mm[k], (int, float, str, bool, type(None)))}
    return keep


def main():
    os.makedirs(OUT, exist_ok=True)
    members = [load_member(tf) for tf in MEMBER_TFS]
    print(f"{'=' * 88}\n=== S1840 Engle Asym-Shock×Drift HOMOGENEOUS POOL :: "
          f"{ASSET} members={list(MEMBER_TFS)} ===", flush=True)
    for m in members:
        print(f"  frozen {m['tf']}: z_up={m['z_up']} z_dn={m['z_dn']} "
              f"K={m['K']} sl_k={m['sl_k']} rr={RR_FIXED}", flush=True)

    reps = [r for r in (reproduce_member(m) for m in members) if r is not None]
    all_tr = pd.concat([r['trades'] for r in reps], ignore_index=True)
    n_before = len(all_tr)

    pool = fifo_calendar(all_tr)
    n_after = len(pool)
    share = pool['src_card'].value_counts(normalize=True)
    print(f"\n[FIFO] n_before={n_before} → n_after={n_after} "
          f"(cut {100 * (1 - n_after / max(n_before, 1)):.1f}%)", flush=True)
    print(f"[share post-FIFO] {share.round(3).to_dict()}", flush=True)

    null = blend_pool_null(reps, pool)
    print(f"[pool null] {json.dumps(null, ensure_ascii=False, default=str)}",
          flush=True)
    shares = share.to_dict()
    by_tf = {r['tf']: r for r in reps}
    sl_med = float(sum(by_tf[c]['sl_med'] * w for c, w in shares.items()))
    tp_med = float(sum(by_tf[c]['tp_med'] * w for c, w in shares.items()))
    print(f"[weighted geometry] SL={sl_med:.1f} TP={tp_med:.1f} pip", flush=True)

    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    d_h1 = fd.load_fast(ASSET, 'H1')
    assert 'mt5_full' in str(d_h1.get('src')), 'H1 axis not mt5_full — STOP'
    ref_t = d_h1['time'].astype(np.int64) * 1_000_000_000
    ref_c = np.asarray(d_h1['close'], dtype=np.float64)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, pool['t_entry'].values,
                                                'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(axis_t, pool['t_exit'].values,
                                               'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    boundary = max(r['split_t'] for r in reps)
    te = pool['t_entry'].values.astype(np.int64)
    holdout = te >= boundary
    wr_disc = float((pool.loc[~holdout, 'pnl_pip'] > 0).mean() * 100)
    wr_hold = float((pool.loc[holdout, 'pnl_pip'] > 0).mean() * 100)
    print(f"[holdout] boundary={np.datetime64(boundary, 'ns')} "
          f"discovery n={int((~holdout).sum())} WR={wr_disc:.2f} · "
          f"holdout n={int(holdout.sum())} WR={wr_hold:.2f}", flush=True)

    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt, null=null,
                  close=axis_close, holdout_mask=holdout, allow_overlap=False)
    res_off = rqs2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_OFFICIAL, **common)
    res_nt1 = rqs2.compute_rqs2(pool, ASSET, n_trials=1, **common)
    res_str = rqs2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print(rqs2.format_rqs2(f'POOL OFFICIAL(n_t={N_TRIALS_OFFICIAL}) ', res_off),
          flush=True)
    print(rqs2.format_rqs2('POOL SENS(n_t=1)       ', res_nt1), flush=True)
    print(rqs2.format_rqs2(f'POOL STRESS(n_t={N_TRIALS_STRESS})  ', res_str),
          flush=True)

    lifts = []
    for r in reps:
        ck = json.load(open(os.path.join(SRC, f"{r['tf']}.json")))
        lifts.append(ck['rqs2_official']['metrics'].get('skill_lift_pp'))
    m_off = res_off.get('metrics', {})
    p1 = (m_off.get('skill_lift_pp') is not None
          and m_off['skill_lift_pp'] >= min(lifts) - 2.0)
    p2 = bool(share.max() <= 0.70)
    p3 = bool(wr_hold >= wr_disc - 5.0)
    print(f"[falsifiers] P1(lift>={min(lifts) - 2:.1f})={p1} "
          f"P2(max share<=70%)={p2} P3(holdout WR)={p3}", flush=True)

    out = dict(
        asset=ASSET, members=[{k: v for k, v in m.items() if k != 'null'}
                              for m in members],
        member_stats={r['tf']: dict(n=r['n_member'], wr=r['wr_member'])
                      for r in reps},
        n_before=n_before, n_after=n_after, share=share.round(4).to_dict(),
        sl_med=round(sl_med, 2), tp_med=round(tp_med, 2), null=null,
        boundary=str(np.datetime64(boundary, 'ns')),
        n_discovery=int((~holdout).sum()), n_holdout=int(holdout.sum()),
        wr_discovery=round(wr_disc, 2), wr_holdout=round(wr_hold, 2),
        pool_wr=round(float((pool['pnl_pip'] > 0).mean() * 100), 2),
        pool_exp=round(float(pool['pnl_pip'].mean()), 4),
        n_trials_official=N_TRIALS_OFFICIAL,
        falsifiers=dict(P1=p1, P2=p2, P3=p3, member_lifts=lifts),
        rqs2_official=_slim(res_off), rqs2_sens_nt1=_slim(res_nt1),
        rqs2_stress_nt500=_slim(res_str))
    with open(os.path.join(OUT, 'pool.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\ncheckpoint saved → {OUT}/pool.json", flush=True)
    print(f"\nVERDICT: {res_off.get('verdict')} score={res_off.get('rqs2_score')}",
          flush=True)


if __name__ == '__main__':
    main()
