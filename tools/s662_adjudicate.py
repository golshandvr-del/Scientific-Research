# -*- coding: utf-8 -*-
"""
s662_adjudicate.py — داور نهایی S662 (استخر منجمد {H8,D1} — یک لمس نیمهٔ دوم)
================================================================================
پیش‌ثبت حاکم: results/S662_PREREG2_FROZEN_POOL_H8D1.md (کامیت ba6330c2)
معماری عیناً S661 (99a10929) — فقط سیگنال عوض شده: flip سوپرترند p=21 m=2.0.
گاردها: GEOMDRIFT/WRUNITS/PERMK/NULLUNCOND/PIPGUESS/SCOREKEY/AXIS/SPAN/قید۲.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import rqs2                                   # noqa: E402
from engine import scalp_engine as se                     # noqa: E402
from engine.rqs2_pool import pool_cards                   # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402
from tools.s662_explore import (                          # noqa: E402
    _supertrend, atr_wilder, WARMUP, MAX_HOLD)

SCAN = os.path.join(ROOT, 'results', '_scan_S662')
OUTD = os.path.join(ROOT, 'results', '_s662_final')
os.makedirs(OUTD, exist_ok=True)

ASSET = 'XAUUSD'
MEMBERS = ('H8', 'D1')
P = 21
M = 2.0
SEED = 20260817
N_PERM = 600
N_TRIALS_FAMILY = 460
N_TRIALS_STRICT = 696


def build_member(tf: str):
    with open(os.path.join(SCAN, f'explore_{tf}.json')) as f:
        sc = json.load(f)
    sl_pip = float(sc['sl_pip'])
    tp_pip = float(sc['tp_pip'])
    cell = [c for c in sc['cells'] if c['p'] == P and c['m'] == M][0]
    lift_fh = float(cell['lift_pp'])

    d = fd.load_fast(ASSET, tf)
    src = d['src']
    assert 'mt5_full' in src, f'E-16! {src}'
    n = len(d['close'])
    half = n // 2
    h = np.ascontiguousarray(d['high'], dtype=np.float64)
    l = np.ascontiguousarray(d['low'], dtype=np.float64)
    c = np.ascontiguousarray(d['close'], dtype=np.float64)
    o = np.ascontiguousarray(d['open'], dtype=np.float64)
    tsec = np.asarray(d['time'], dtype=np.int64)
    del d
    df = pd.DataFrame({'open': o, 'high': h, 'low': l, 'close': c})

    atrp = atr_wilder(h, l, c, P)
    trend = _supertrend(h, l, c, atrp, M)
    up = trend == 1
    le = up & ~np.concatenate(([True], up[:-1]))
    dn = trend == -1
    sh = dn & ~np.concatenate(([False], dn[:-1]))
    valid = np.zeros(n, bool)
    valid[WARMUP:n - MAX_HOLD - 1] = True
    le &= valid
    sh &= valid

    tr = se.simulate_trades(df, le, sh, sl_pip, tp_pip, ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
    n_tr = 0 if tr is None else len(tr)
    dl = tr['direction'].values
    wr = 100.0 * float((tr['pnl_pip'].values > 0).mean())
    print(f'[{tf}] src={os.path.basename(src)} n_bar={n:,} half={half:,} '
          f'sig L={int(le.sum())} S={int(sh.sum())} | trades n={n_tr} '
          f'WR={wr:.3f}% net={float(tr["pnl_pip"].sum()):.1f}pip', flush=True)

    rng = np.random.default_rng(SEED)
    vidx = np.flatnonzero(valid)
    z = np.zeros(n, bool)

    def _wr_pct(t):
        return (float(100.0 * (t['pnl_pip'].values > 0).mean())
                if t is not None and len(t) else None)

    null = {}
    for side_name, side_mask in (('long', le), ('short', sh)):
        k_side = int(side_mask.sum())
        if k_side == 0:
            null[side_name] = dict(uncond_wr=None, perm_mean=None,
                                   perm_sd=None, perm_max=None, perm_k=0)
            continue
        if side_name == 'long':
            t_unc = se.simulate_trades(df, valid, z, sl_pip, tp_pip, ASSET,
                                       max_hold=MAX_HOLD, allow_overlap=True)
        else:
            t_unc = se.simulate_trades(df, z, valid, sl_pip, tp_pip, ASSET,
                                       max_hold=MAX_HOLD, allow_overlap=True)
        uncond_wr = _wr_pct(t_unc)
        perm_wrs = []
        for _ in range(N_PERM):
            pick = rng.choice(vidx, size=k_side, replace=False)
            pm = np.zeros(n, bool)
            pm[pick] = True
            if side_name == 'long':
                tp_ = se.simulate_trades(df, pm, z, sl_pip, tp_pip, ASSET,
                                         max_hold=MAX_HOLD,
                                         allow_overlap=False)
            else:
                tp_ = se.simulate_trades(df, z, pm, sl_pip, tp_pip, ASSET,
                                         max_hold=MAX_HOLD,
                                         allow_overlap=False)
            w = _wr_pct(tp_)
            if w is not None:
                perm_wrs.append(w)
        pa = np.asarray(perm_wrs)
        null[side_name] = dict(
            uncond_wr=uncond_wr,
            perm_mean=float(pa.mean()),
            perm_sd=float(pa.std(ddof=1)),
            perm_max=float(pa.max()),
            perm_k=int(pa.size),
        )
        print(f'[{tf}] null[{side_name}]: uncond={uncond_wr:.3f}% '
              f'perm_mean={pa.mean():.3f} sd={pa.std(ddof=1):.3f} '
              f'max={pa.max():.3f} k={pa.size}', flush=True)

    dt = pd.to_datetime(tsec, unit='s').values
    unc_blend = np.average(
        [null[s]['uncond_wr'] for s in ('long', 'short')
         if null[s]['uncond_wr'] is not None],
        weights=[int((dl == s).sum()) for s in ('long', 'short')
                 if null[s]['uncond_wr'] is not None])
    lift_full = wr - float(unc_blend)
    return dict(card=tf, tr=tr, dt=dt, lift=lift_full, lift_fh=lift_fh,
                null=null, sl_pip=sl_pip, tp_pip=tp_pip, n=n_tr,
                t_half=int(tsec[half]), src=src)


def blend_pool_null(members_used, pool_df):
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
            if w <= 0:
                continue
            dd = m['null'][side]
            if dd.get('uncond_wr') is not None:
                num_u += dd['uncond_wr'] * w
                den_u += w
            if dd.get('perm_mean') is not None and dd.get('perm_sd') is not None:
                num_m += dd['perm_mean'] * w
                num_s += (dd['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = dd.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def main():
    t0 = time.time()
    print(f'== S662-POOL {MEMBERS} p={P} m={M} seed={SEED} ==', flush=True)
    members = [build_member(tf) for tf in MEMBERS]

    th = [m['t_half'] for m in members]
    assert abs(th[0] - th[1]) < 10 * 86400, f'مرزهای نیمه ناسازگار: {th}'
    split_ns = int(max(th)) * 1_000_000_000

    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                           lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] هیچ عضو معتبری نماند.', flush=True)
        return
    pool = res['pool']
    print(f"[استخر] used={[u['card'] for u in res['used']]} "
          f"dropped={[(x['card'], x['reason']) for x in res['dropped']]} "
          f"n_before={res['n_before']} n_after={res['n_after']}", flush=True)

    used = [m for m in members if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used, pool)
    print(f'[نول استخر] {json.dumps(null, ensure_ascii=False)}', flush=True)

    if len(pool) < 30:
        print('قید ۲: n<30 ⇒ بدون حکم.', flush=True)
        return

    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by = {m['card']: m for m in used}
    sl_w = float(sum(by[c]['sl_pip'] * w for c, w in shares.items() if c in by))
    tp_w = float(sum(by[c]['tp_pip'] * w for c, w in shares.items() if c in by))

    STEP_NS = 3600 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    dh1 = fd.load_fast(ASSET, 'H1')
    ref_t = (np.asarray(dh1['time'], np.int64) * 1_000_000_000)
    ref_c = np.asarray(dh1['close'], float)
    del dh1
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_entry'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_exit'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    te = pool['t_entry'].values.astype(np.int64)
    holdout = te >= split_ns
    print(f'[مسیر C] مرز={np.datetime64(split_ns, "ns")} · '
          f'اکتشاف={int((~holdout).sum())} · هولدآوت={int(holdout.sum())}',
          flush=True)

    wr_pool = 100.0 * float((pool['pnl_pip'].values > 0).mean())
    print(f'[استخر نهایی] n={len(pool)} WR={wr_pool:.3f}% '
          f'net={float(pool["pnl_pip"].sum()):.1f}pip', flush=True)

    results = {}
    for tag, ntr in (('family_460', N_TRIALS_FAMILY),
                     ('strict_696', N_TRIALS_STRICT)):
        r = rqs2.compute_rqs2(pool, ASSET, sl_pip=sl_w, tp_pip=tp_w,
                              bar_time=axis_dt, close=axis_close, null=null,
                              holdout_mask=holdout, n_trials=ntr,
                              allow_overlap=False)
        m = r.get('metrics', {})
        print(f'\n===== n_trials={ntr} ({tag}) =====', flush=True)
        print('verdict :', r['verdict'], flush=True)
        print('score   :', r['rqs2_score'], flush=True)
        print('gates   :', r['gates'], flush=True)
        print('z       :', m.get('skill_z'),
              '| p_perm:', m.get('skill_p_perm'),
              '| z_luck_bound:', m.get('z_luck_bound'), flush=True)
        print('lift_pp :', m.get('skill_lift_pp'), flush=True)
        results[tag] = dict(n_trials=ntr, verdict=r['verdict'],
                            rqs2_score=r['rqs2_score'], gates=r['gates'],
                            metrics=m, notes=r.get('notes'))

    def _clean(x):
        if isinstance(x, dict):
            return {k: _clean(v) for k, v in x.items()}
        if isinstance(x, (np.floating, np.integer)):
            return float(x)
        return x

    out = dict(layer='S662-POOL', asset=ASSET, members=list(MEMBERS),
               p=P, m=M, seed=SEED, n_perm=N_PERM,
               used=[u['card'] for u in res['used']], dropped=res['dropped'],
               n_before=res['n_before'], n_after=res['n_after'],
               member_stats=[dict(card=mm['card'], n=mm['n'],
                                  lift_full=mm['lift'], lift_fh=mm['lift_fh'],
                                  sl_pip=mm['sl_pip'], src=mm['src'])
                             for mm in members],
               sl_pip_w=sl_w, tp_pip_w=tp_w,
               pool_n=len(pool), pool_wr=wr_pool, split_ns=split_ns,
               null=_clean(null), results=_clean(results),
               elapsed_s=round(time.time() - t0, 1))
    fp = os.path.join(OUTD, 'verdict_POOL_H8D1.json')
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f'\nذخیره شد: {fp}', flush=True)


if __name__ == '__main__':
    main()
