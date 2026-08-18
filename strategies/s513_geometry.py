# -*- coding: utf-8 -*-
"""
S513 — جست‌وجوی هندسه برای پایهٔ بادار M30
================================================================================
پیش‌ثبت: `results/S513_PREREG_M30_GEOMETRY.md` (commit قبل از هر آزمون).
سیگنال منجمد: atr_fib_55 cross↑q90(کشف) / LONG — بدون هیچ تغییری.
خانواده: 25 سلول SL_K∈{0.618,1.0,1.272,1.618,2.058} × RR∈{1.272,1.618,2.058,2.618,3.236}.
انتخاب فقط روی کشف: n≥60 ∧ net>0 هر دو نیمه ∧ PF>PF_control؛ برنده = max PF.
داوری: null با هندسهٔ برنده + یک compute_rqs2 با n_trials=5003.

اجرا:  python3 strategies/s513_geometry.py --stage sweep|null|judge
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
    cross_above, load_card, SPLIT_FRAC, WARMUP, Q_HI, PIP, COST_PIP)

SEED = 20260819
MIN_N_DISC = 60
K_PERM = 2000
N_TRIALS = 5003
TF = 'M30'
OUT = 'results/_scan_S513'
BASE_IND = 'atr_fib_55'
SL_GRID = (0.618, 1.0, 1.272, 1.618, 2.058)
RR_GRID = (1.272, 1.618, 2.058, 2.618, 3.236)
CONTROL = (1.272, 2.058)


def build_context():
    d = load_card(TF)
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    df_full = as_dataframe({k: d[k] for k in
                            ('time', 'open', 'high', 'low', 'close', 'volume')})
    x = ib.compute(BASE_IND, df_full).to_numpy()
    x[:WARMUP] = np.nan
    thr = float(np.nanquantile(x[:split], Q_HI))
    sig_bool = np.nan_to_num(cross_above(x, thr), nan=False).astype(bool)
    sig_bool[:WARMUP] = False
    a = atr_np(d['high'], d['low'], d['close'])
    atr_med = float(np.nanmedian(a[:split]))
    return dict(d=d, n=n, split=split, half=split // 2, thr=thr,
                sig_bool=sig_bool, atr_med=atr_med)


def pf_of(pnl):
    wins = pnl[pnl > 0].sum()
    loss = -pnl[pnl <= 0].sum()
    return float(wins / loss) if loss > 0 else float('inf')


def cell_metrics(tr, half):
    if len(tr) == 0:
        return None
    pnl = tr['pnl_pip'].to_numpy() - COST_PIP        # خالص per معامله
    m1 = tr['entry_bar'].to_numpy() < half
    return dict(n=len(tr),
                net=float(pnl.mean()),
                net1=float(pnl[m1].mean()) if m1.any() else None,
                net2=float(pnl[~m1].mean()) if (~m1).any() else None,
                wr=100.0 * float((tr['outcome'] == 'win').mean()),
                pf=pf_of(pnl))


def stage_sweep():
    ctx = build_context()
    d, split, half = ctx['d'], ctx['split'], ctx['half']
    d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
    sig_idx = np.flatnonzero(ctx['sig_bool'][:split])
    print(f"[SWEEP] thr={ctx['thr']:.5g}  n_sig_disc={len(sig_idx)}  "
          f"atr_med={ctx['atr_med']:.4f}", flush=True)

    rows = {}
    for slk in SL_GRID:
        for rr in RR_GRID:
            sl_abs = slk * ctx['atr_med']
            tr = simulate(d_disc, sig_idx, sl_abs, rr)
            m = cell_metrics(tr, half)
            rows[f'{slk}x{rr}'] = dict(sl_k=slk, rr=rr, **(m or dict(n=0)))
            if m:
                print(f'  SL={slk:5.3f} RR={rr:5.3f}: n={m["n"]:3d} '
                      f'wr={m["wr"]:5.2f}% net={m["net"]:+7.3f} '
                      f'pf={m["pf"]:.3f}', flush=True)

    ctrl = rows[f'{CONTROL[0]}x{CONTROL[1]}']
    pf_ctrl = ctrl.get('pf', 0.0)
    valid = []
    for key, r in rows.items():
        if r.get('n', 0) >= MIN_N_DISC \
           and r.get('net1') is not None and r.get('net2') is not None \
           and r['net1'] > 0 and r['net2'] > 0 \
           and r['pf'] > pf_ctrl:
            valid.append(dict(key=key, **r))
    valid.sort(key=lambda r: -r['pf'])
    winner = valid[0] if valid else None
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/sweep.json', 'w') as f:
        json.dump(dict(thr=ctx['thr'], atr_med=ctx['atr_med'], split=split,
                       n_sig_disc=int(len(sig_idx)), control=ctrl,
                       pf_control=pf_ctrl, cells=rows, n_valid=len(valid),
                       valid=valid, winner=winner, seed=SEED),
                  f, ensure_ascii=False)
    print(f'[SWEEP] control pf={pf_ctrl:.3f} | valid={len(valid)}', flush=True)
    if winner:
        print(f"[SWEEP] WINNER: SL_K={winner['sl_k']} RR={winner['rr']} "
              f"pf={winner['pf']:.3f} n={winner['n']} wr={winner['wr']:.2f}% "
              f"net={winner['net']:+.3f}", flush=True)
    else:
        print('[SWEEP] هیچ سلول معتبری نیست ⇒ REJECT-by-rule', flush=True)
    print(f'saved -> {OUT}/sweep.json')


def stage_null():
    with open(f'{OUT}/sweep.json') as f:
        S = json.load(f)
    w = S['winner']
    if not w:
        raise SystemExit('no winner — null موضوعیت ندارد')
    ctx = build_context()
    d, n = ctx['d'], ctx['n']
    sl_abs = w['sl_k'] * ctx['atr_med']
    rr = w['rr']
    sig_idx = np.flatnonzero(ctx['sig_bool'])
    tr = simulate(d, sig_idx, sl_abs, rr)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f"[NULL] winner SL_K={w['sl_k']} RR={rr}: n_sig={len(sig_idx)} "
          f"n_tr={len(tr)} wr={obs_wr:.2f}%", flush=True)

    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(WARMUP, n - 2, stride, dtype=np.int64)
        t0 = simulate(d, idx, sl_abs, rr)
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
        tp_ = simulate(d, pos, sl_abs, rr)
        if len(tp_) >= 30:
            wrs.append(100.0 * float((tp_['outcome'] == 'win').mean()))
        if (k + 1) % 400 == 0:
            print(f'  perm {k+1}/{K_PERM}', flush=True)
    arr = np.asarray(wrs, float)
    perm = dict(mean=float(arr.mean()), sd=float(arr.std(ddof=1)),
                max=float(arr.max()), k=int(len(arr)))
    z = (obs_wr - perm['mean']) / perm['sd'] if perm['sd'] > 0 else float('nan')
    p_exact = float((arr >= obs_wr - 1e-9).mean())    # درس S512: p دقیق
    print(f"  perm: mean={perm['mean']:.2f} sd={perm['sd']:.2f} "
          f"max={perm['max']:.2f}  z={z:.2f}  P(perm>=obs)={p_exact:.4f}",
          flush=True)

    side_null = dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
                     perm_sd=perm['sd'], perm_max=perm['max'],
                     perm_k=perm['k'])
    empty = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
    with open(f'{OUT}/null.json', 'w') as f:
        json.dump(dict(winner=w, obs_wr=obs_wr, n_trades=len(tr),
                       sl_abs=sl_abs, rr=rr, uncond=uncond_rows, perm=perm,
                       p_exact=p_exact,
                       null={'long': side_null, 'short': empty},
                       seed=SEED, k=K_PERM, z_preview=z),
                  f, ensure_ascii=False)
    print(f'saved -> {OUT}/null.json')


def stage_judge():
    with open(f'{OUT}/null.json') as f:
        nm = json.load(f)
    w = nm['winner']
    ctx = build_context()
    d, split = ctx['d'], ctx['split']
    sl_abs = float(nm['sl_abs'])
    rr = float(nm['rr'])
    tr = simulate(d, np.flatnonzero(ctx['sig_bool']), sl_abs, rr)

    res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl_abs / PIP,
                         tp_pip=rr * sl_abs / PIP,
                         bar_time=d['time'], close=d['close'],
                         null=nm['null'], n_trials=N_TRIALS, split_bar=split)
    tag = f"S513_M30_atr_fib_55_geom_SL{w['sl_k']}_RR{w['rr']}"
    print(R.format_rqs2(tag, res))
    with open(f'{OUT}/rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/trades.csv', index=False)
    print(f'saved -> {OUT}/rqs2.json + trades.csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True, choices=['sweep', 'null', 'judge'])
    args = ap.parse_args()
    {'sweep': stage_sweep, 'null': stage_null,
     'judge': stage_judge}[args.stage]()
