# -*- coding: utf-8 -*-
"""
S514 — داوری مستقیم نامزد رتبهٔ ۲ سرشماری M30: trix_fib_34 cross↑q90 / LONG
================================================================================
پیش‌ثبت: `results/S514_PREREG_M30_TRIX_RANK2.md` (commit قبل از هر آزمون).
صفر درجهٔ آزادی جدید: سیگنال از سرشماری S511، هندسهٔ کنترل منجمد.
مراحل: null → judge (یک compute_rqs2، n_trials=5004).

اجرا:  python3 strategies/s514_trix_rank2.py --stage null|judge
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R                                        # noqa: E402
from engine import indicator_bank as ib                             # noqa: E402
from tools.s434_fast_data import as_dataframe                       # noqa: E402
from strategies.s510_rr_lowtf_wpr import atr_np, simulate           # noqa: E402
from strategies.s511_gross_census import (                          # noqa: E402
    cross_above, load_card, SPLIT_FRAC, WARMUP, SL_K, RR, Q_HI, PIP)

SEED = 20260820
K_PERM = 2000
N_TRIALS = 5004
TF = 'M30'
OUT = 'results/_scan_S514'
IND = 'trix_fib_34'


def build_context():
    d = load_card(TF)
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    df_full = as_dataframe({k: d[k] for k in
                            ('time', 'open', 'high', 'low', 'close', 'volume')})
    x = ib.compute(IND, df_full).to_numpy()
    x[:WARMUP] = np.nan
    thr = float(np.nanquantile(x[:split], Q_HI))
    sig_bool = np.nan_to_num(cross_above(x, thr), nan=False).astype(bool)
    sig_bool[:WARMUP] = False
    a = atr_np(d['high'], d['low'], d['close'])
    sl_abs = float(np.nanmedian(a[:split])) * SL_K
    return dict(d=d, n=n, split=split, thr=thr, sig_bool=sig_bool,
                sl_abs=sl_abs)


def stage_null():
    ctx = build_context()
    d, n = ctx['d'], ctx['n']
    sig_idx = np.flatnonzero(ctx['sig_bool'])
    tr = simulate(d, sig_idx, ctx['sl_abs'], RR)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f"[NULL] {IND}↑q90 thr={ctx['thr']:.5g}  n_sig={len(sig_idx)}  "
          f"n_tr={len(tr)}  wr={obs_wr:.2f}%", flush=True)

    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(WARMUP, n - 2, stride, dtype=np.int64)
        t0 = simulate(d, idx, ctx['sl_abs'], RR)
        wr0 = 100.0 * float((t0['outcome'] == 'win').mean()) if len(t0) else None
        uncond_rows.append((stride, wr0, len(t0)))
        print(f'  uncond stride={stride}: n={len(t0)} wr={wr0:.2f}%', flush=True)
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)

    rng = np.random.default_rng(SEED)
    space = np.arange(WARMUP, n - 2, dtype=np.int64)
    wrs = []
    for k in range(K_PERM):
        pos = np.sort(rng.choice(space, size=min(len(sig_idx), len(space)),
                                 replace=False))
        tp_ = simulate(d, pos, ctx['sl_abs'], RR)
        if len(tp_) >= 30:
            wrs.append(100.0 * float((tp_['outcome'] == 'win').mean()))
        if (k + 1) % 400 == 0:
            print(f'  perm {k+1}/{K_PERM}', flush=True)
    arr = np.asarray(wrs, float)
    perm = dict(mean=float(arr.mean()), sd=float(arr.std(ddof=1)),
                max=float(arr.max()), k=int(len(arr)))
    z = (obs_wr - perm['mean']) / perm['sd'] if perm['sd'] > 0 else float('nan')
    p_exact = float((arr >= obs_wr - 1e-9).mean())
    print(f"  perm: mean={perm['mean']:.2f} sd={perm['sd']:.2f} "
          f"max={perm['max']:.2f}  z={z:.2f}  P(perm>=obs)={p_exact:.4f}",
          flush=True)

    side_null = dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
                     perm_sd=perm['sd'], perm_max=perm['max'],
                     perm_k=perm['k'])
    empty = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/null.json', 'w') as f:
        json.dump(dict(ind=IND, thr=ctx['thr'], obs_wr=obs_wr,
                       n_trades=len(tr), sl_abs=ctx['sl_abs'],
                       uncond=uncond_rows, perm=perm, p_exact=p_exact,
                       null={'long': side_null, 'short': empty},
                       seed=SEED, k=K_PERM, z_preview=z),
                  f, ensure_ascii=False)
    print(f'saved -> {OUT}/null.json')


def stage_judge():
    with open(f'{OUT}/null.json') as f:
        nm = json.load(f)
    ctx = build_context()
    d, split = ctx['d'], ctx['split']
    sl_abs = float(nm['sl_abs'])
    tr = simulate(d, np.flatnonzero(ctx['sig_bool']), sl_abs, RR)

    res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_abs / PIP,
                         tp_pip=RR * sl_abs / PIP,
                         bar_time=d['time'], close=d['close'],
                         null=nm['null'], n_trials=N_TRIALS, split_bar=split)
    tag = f'S514_M30_{IND}_q90_long'
    print(R.format_rqs2(tag, res))
    with open(f'{OUT}/rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/trades.csv', index=False)
    print(f'saved -> {OUT}/rqs2.json + trades.csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True, choices=['null', 'judge'])
    args = ap.parse_args()
    {'null': stage_null, 'judge': stage_judge}[args.stage]()
