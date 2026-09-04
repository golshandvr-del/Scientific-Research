# -*- coding: utf-8 -*-
"""
S711 — نجاتِ استخری طبق بند ۵ پیش‌ثبت — دستورکار اثبات‌شدهٔ S431/S710.
یک بار، بدون تغییر هیچ آستانه‌ای. اعضا: کارت‌های خانواده با lift>0.
محور: شبکهٔ مصنوعیِ ۵دقیقه‌ای (BUG-QUANT/BUG-SPAN)؛ تقسیم: چندکِ ۷۰٪ِ زمانِ
ورود (BUG-SPLITDIR)؛ زمان: astype('datetime64[s]') (BUG-EPOCH).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import rqs2                                             # noqa: E402
from engine.rqs2_pool import pool_cards                             # noqa: E402
from tools import s434_fast_data as fd                              # noqa: E402
from strategies.s431_lpsb_multicard_pool import blend_pool_null     # noqa: E402
from strategies.s711_dsf import ASSET, FAMILY, OUT, git_checkpoint  # noqa: E402

N_TRIALS_POOL = 11          # prereg §3: 10 + 1
SPLIT_FRAC = 0.70


def load_member(tf):
    d = json.load(open(f'{OUT}/{tf}.json'))
    tr = pd.read_csv(f'{OUT}/{tf}_trades.csv')
    dd = fd.load_fast(ASSET, tf)
    dt = dd['time'].astype('int64').astype('datetime64[s]').astype('datetime64[ns]')
    null = d['null']
    nl = int((tr['direction'] == 'long').sum()); ns = len(tr) - nl
    wr = float((tr['pnl_pip'] > 0).mean() * 100)
    unc = (null['long']['uncond_wr'] * nl + null['short']['uncond_wr'] * ns) / max(1, nl + ns)
    lift = wr - unc
    print(f'  member {tf}: n={len(tr)} wr={wr:.2f} uncond={unc:.2f} lift={lift:+.2f}pp '
          f'verdict={d["rqs2"]["verdict"]}', flush=True)
    return dict(card=tf, tr=tr, dt=dt, lift=lift, null=null)


def main():
    members = [load_member(tf) for tf in FAMILY if os.path.exists(f'{OUT}/{tf}.json')]
    res = pool_cards(members)
    if res is None:
        print('pool: no valid members'); return
    pool = res['pool']
    used = [u['card'] for u in res['used']]
    print(f'  used={used} dropped={res["dropped"]} n_before={res["n_before"]} '
          f'n_after={res["n_after"]}', flush=True)
    used_members = [m for m in members if m['card'] in used]
    null = blend_pool_null(used_members, pool)

    STEP_NS = 5 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS, dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')

    ref = fd.load_fast(ASSET, 'H1')
    ref_t = ref['time'].astype('int64').astype('datetime64[s]').astype('datetime64[ns]').astype(np.int64)
    ref_c = ref['close'].astype(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, pool['t_entry'].values, 'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(axis_t, pool['t_exit'].values, 'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'  axis {axis_dt[0]} → {axis_dt[-1]} ({len(axis_t):,} buckets); split='
          f'{np.datetime64(split_ns, "ns")} IS={int((~holdout).sum())} OOS={int(holdout.sum())}', flush=True)

    sl_med = float(np.median(pool['sl_pip'])); tp_med = float(np.median(pool['tp_pip']))
    r = rqs2.compute_rqs2(pool, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt,
                          close=axis_close, null=null, holdout_mask=holdout,
                          n_trials=N_TRIALS_POOL, allow_overlap=False)
    print(rqs2.format_rqs2('S711_DSF_POOL', r), flush=True)

    payload = dict(used=used, dropped=res['dropped'], n_before=res['n_before'],
                   n_after=res['n_after'], selection=res['selection'],
                   members=[dict(card=m['card'], n=len(m['tr']), lift=m['lift']) for m in members],
                   null=null, n_trials=N_TRIALS_POOL, split_frac=SPLIT_FRAC,
                   src=[json.load(open(f'{OUT}/{tf}.json'))['src'] for tf in used],
                   rqs2=r)
    json.dump(payload, open(f'{OUT}/POOL.json', 'w'), indent=1, ensure_ascii=False, default=str)
    pool.to_csv(f'{OUT}/POOL_trades.csv', index=False)
    git_checkpoint('POOL')


if __name__ == '__main__':
    main()
