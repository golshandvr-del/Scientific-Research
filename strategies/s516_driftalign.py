# -*- coding: utf-8 -*-
"""
S516 — فیلتر هم‌راستایی درفت روی برندهٔ V-TIME (S515)
================================================================================
پیش‌ثبت: `results/S516_PREREG_M30_VTIME_DRIFTALIGN.md` (commit قبل از هر آزمون).
پایهٔ منجمد: atr_fib_55 cross↑q90(کشف)/LONG + V-TIME k=4 + براکت q98(کشف).
فیلتر: نگه‌داشتن سیگنال t ⟺ close[t] > close[t-L]؛ L ∈ {13,34,89,233} (۴ آزمون).
مراحل: select → identity (p دقیق ≤0.05) → null → judge (n_trials=5013).

اجرا:  python3 strategies/s516_driftalign.py --stage select|identity|null|judge
"""
import sys
import os
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R                                        # noqa: E402
from strategies.s511_gross_census import WARMUP, PIP                # noqa: E402
from strategies.s515_voltime import (                               # noqa: E402
    build_context, sim_vtime, bracket_from_discovery, t_stat, K_PERM)

SEED = 20260822
K_VT = 4
L_GRID = (13, 34, 89, 233)
MIN_N = 50
RET_LO, RET_HI = 0.25, 0.90
K_IDENTITY = 1000
N_TRIALS = 5013
OUT = 'results/_scan_S516'


def drift_keep(close, idx, L):
    """فیلتر علّی: close[t] > close[t-L] (t-L>=0)."""
    ok = idx >= L
    keep = np.zeros(len(idx), bool)
    keep[ok] = close[idx[ok]] > close[idx[ok] - L]
    return idx[keep]


def base_setup():
    ctx = build_context()
    split = ctx['split']
    sig_disc = np.flatnonzero(ctx['sig_bool'][:split])
    br = bracket_from_discovery(ctx['d'], sig_disc, K_VT, split)
    return ctx, sig_disc, br


def metrics(tr, half):
    if len(tr) == 0:
        return None
    pnl = tr['pnl_pip'].to_numpy()
    m1 = tr['entry_bar'].to_numpy() < half
    return dict(n=len(tr), net=float(pnl.mean()), t=t_stat(pnl),
                net1=float(pnl[m1].mean()) if m1.any() else None,
                net2=float(pnl[~m1].mean()) if (~m1).any() else None,
                wr=100.0 * float((tr['outcome'] == 'win').mean()))


def stage_select():
    ctx, sig_disc, br = base_setup()
    d, split, half = ctx['d'], ctx['split'], ctx['half']
    d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
    tr_b = sim_vtime(d_disc, sig_disc, K_VT, br)
    mb = metrics(tr_b, half)
    print(f"[SELECT] base: n_sig={len(sig_disc)} n_tr={mb['n']} "
          f"wr={mb['wr']:.2f}% net={mb['net']:+.3f} t={mb['t']:+.2f} "
          f"(net1={mb['net1']:+.3f} net2={mb['net2']:+.3f}) "
          f"br={br/PIP:.1f}pip", flush=True)

    rows = []
    for L in L_GRID:
        keep = drift_keep(d['close'], sig_disc, L)
        ret = len(keep) / max(len(sig_disc), 1)
        m = metrics(sim_vtime(d_disc, keep, K_VT, br), half) if len(keep) else None
        row = dict(L=L, n_keep_sig=int(len(keep)), retention=round(ret, 4))
        if m:
            row.update({k: (round(v, 3) if isinstance(v, float) else v)
                        for k, v in m.items()})
            row['valid'] = bool(m['n'] >= MIN_N and RET_LO <= ret <= RET_HI
                                and m['net1'] is not None
                                and m['net2'] is not None
                                and m['net1'] > mb['net1']
                                and m['net2'] > mb['net2'])
        else:
            row.update(n=0, valid=False)
        rows.append(row)
        if m:
            print(f"  L={L:3d}: ret={ret:.3f} n={m['n']} wr={m['wr']:.2f}% "
                  f"net={m['net']:+.3f} t={m['t']:+.2f} "
                  f"{'VALID' if row['valid'] else '-'}", flush=True)

    valid = [r for r in rows if r.get('valid')]
    valid.sort(key=lambda r: -r['t'])
    winner = valid[0] if valid else None
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/select.json', 'w') as f:
        json.dump(dict(base=mb, br_abs=br, rows=rows, n_valid=len(valid),
                       winner=winner, seed=SEED), f, ensure_ascii=False)
    if winner:
        print(f"[SELECT] WINNER: L={winner['L']} t={winner['t']:+.2f} "
              f"wr={winner['wr']:.2f}% (base {mb['wr']:.2f}%)", flush=True)
    else:
        print('[SELECT] هیچ نامزد معتبری نیست ⇒ REJECT-by-rule', flush=True)
    print(f'saved -> {OUT}/select.json')


def stage_identity():
    with open(f'{OUT}/select.json') as f:
        S = json.load(f)
    w = S['winner']
    if not w:
        raise SystemExit('no winner')
    ctx, sig_disc, br = base_setup()
    d, split = ctx['d'], ctx['split']
    d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
    k_keep = int(w['n_keep_sig'])

    rng = np.random.default_rng(SEED)
    wrs = []
    for k in range(K_IDENTITY):
        sub = np.sort(rng.choice(sig_disc, size=k_keep, replace=False))
        t = sim_vtime(d_disc, sub, K_VT, br)
        if len(t) >= 10:
            wrs.append(100.0 * float((t['outcome'] == 'win').mean()))
        if (k + 1) % 250 == 0:
            print(f'  identity {k+1}/{K_IDENTITY}', flush=True)
    arr = np.asarray(wrs, float)
    obs = float(w['wr'])
    p_ge = float((arr >= obs - 1e-9).mean())          # p دقیق — درس S512
    passed = bool(p_ge <= 0.05)
    print(f'[IDENTITY] obs_wr={obs:.2f}%  random: mean={arr.mean():.2f} '
          f'p95={np.percentile(arr, 95):.2f} max={arr.max():.2f} '
          f'P(rand>=obs)={p_ge:.4f}  ->  {"PASS" if passed else "FAIL"}',
          flush=True)
    with open(f'{OUT}/identity.json', 'w') as f:
        json.dump(dict(winner=w, obs_wr=obs, p_exact=p_ge,
                       mean=float(arr.mean()), max=float(arr.max()),
                       p95=float(np.percentile(arr, 95)), k=len(arr),
                       passed=passed, seed=SEED), f, ensure_ascii=False)
    print(f'saved -> {OUT}/identity.json')


def full_signals(ctx, L):
    sig_full = np.flatnonzero(ctx['sig_bool'])
    return drift_keep(ctx['d']['close'], sig_full, L)


def stage_null():
    with open(f'{OUT}/identity.json') as f:
        ident = json.load(f)
    if not ident['passed']:
        raise SystemExit('identity FAIL — داوری ممنوع (REJECT-by-identity)')
    w = ident['winner']
    with open(f'{OUT}/select.json') as f:
        br = float(json.load(f)['br_abs'])
    ctx = build_context()
    d, n = ctx['d'], ctx['n']
    sig_idx = full_signals(ctx, int(w['L']))
    tr = sim_vtime(d, sig_idx, K_VT, br)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f"[NULL] L={w['L']}: n_sig={len(sig_idx)} n_tr={len(tr)} "
          f"wr={obs_wr:.2f}%", flush=True)

    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(WARMUP, n - K_VT - 1, stride, dtype=np.int64)
        t0 = sim_vtime(d, idx, K_VT, br)
        wr0 = 100.0 * float((t0['outcome'] == 'win').mean()) if len(t0) else None
        uncond_rows.append((stride, wr0, len(t0)))
        print(f'  uncond stride={stride}: n={len(t0)} wr={wr0:.2f}%', flush=True)
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)

    rng = np.random.default_rng(SEED)
    space = np.arange(WARMUP, n - K_VT - 1, dtype=np.int64)
    wrs = []
    for k in range(K_PERM):
        pos = np.sort(rng.choice(space, size=min(len(sig_idx), len(space)),
                                 replace=False))
        tp_ = sim_vtime(d, pos, K_VT, br)
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
    with open(f'{OUT}/null.json', 'w') as f:
        json.dump(dict(winner=w, br_abs=br, obs_wr=obs_wr, n_trades=len(tr),
                       uncond=uncond_rows, perm=perm, p_exact=p_exact,
                       null={'long': side_null, 'short': empty},
                       seed=SEED, k=K_PERM, z_preview=z),
                  f, ensure_ascii=False)
    print(f'saved -> {OUT}/null.json')


def stage_judge():
    with open(f'{OUT}/null.json') as f:
        nm = json.load(f)
    w = nm['winner']
    br = float(nm['br_abs'])
    ctx = build_context()
    d, split = ctx['d'], ctx['split']
    tr = sim_vtime(d, full_signals(ctx, int(w['L'])), K_VT, br)
    tr2 = tr.drop(columns=['exit_kind'])

    res = R.compute_rqs2(tr2, 'XAUUSD', sl_pip=br / PIP, tp_pip=br / PIP,
                         bar_time=d['time'], close=d['close'],
                         null=nm['null'], n_trials=N_TRIALS, split_bar=split)
    tag = f"S516_M30_vtime_k4_drift{w['L']}"
    print(R.format_rqs2(tag, res))
    with open(f'{OUT}/rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/trades.csv', index=False)
    print(f'saved -> {OUT}/rqs2.json + trades.csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True,
                    choices=['select', 'identity', 'null', 'judge'])
    args = ap.parse_args()
    {'select': stage_select, 'identity': stage_identity,
     'null': stage_null, 'judge': stage_judge}[args.stage]()
