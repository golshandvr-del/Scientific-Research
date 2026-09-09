"""
S909 — Permanent Displacement after Calm · XAUUSD-H8 · RQS2 v2.6 · Path C
============================================================================
پایه = S906 (شوک ≥2.058·ATR21[i−1] پس از ۳۴ کندل بی‌شوک، جهت بدنه) ∧ گیت
ماندگاری ρ=|close−open|/(high−low) ≥ 0.618 (بازوی A). بازوی B = ρ<0.618 (کنترل).

پیش‌ثبت: results/S909_PREREGISTRATION.md (کامیت 18507ada، قبل از هر آزمون).
گرید منجمد: k_sl∈{1.272,2.058} × hold∈{13,34}؛ RR=1.618. n_trials تجمعی = 24.
داده: data/mt5_full/XAUUSD_H8.csv (src در JSON گزارش می‌شود).
"""
from __future__ import annotations

import json
import os
import sys
import importlib.util

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2                            # noqa: E402
from tools import s434_fast_data as fd             # noqa: E402

_spec = importlib.util.spec_from_file_location(
    's906', os.path.join(ROOT, 'strategies', 's906_tranquility_break.py'))
s906 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s906)

ASSET, TF = 'XAUUSD', 'H8'
OUT = os.path.join(ROOT, 'results', '_s909')
THETA, L_DROUGHT, RR, RHO = 2.058, 34, 1.618, 0.618
GRID_KSL = (1.272, 2.058)
GRID_HOLD = (13, 34)
N_EFF = 4
N_TRIALS_CUM = 24
SPLIT_FRAC = 0.60
K_PERM = 1000
SEED_A, SEED_B = 909, 1909
MIN_N_IS = 40


def signals(d):
    """(lsA, ssA, lsB, ssB, ls0, ss0, rho) — A: ρ≥0.618، B: ρ<0.618، 0: پایهٔ S906."""
    atr_prev = s906.build_features(d)
    ls0, ss0 = s906.build_signals(d, L_DROUGHT, THETA, atr_prev)
    with np.errstate(invalid='ignore', divide='ignore'):
        rho = np.abs(d['close'] - d['open']) / (d['high'] - d['low'])
    rho = np.nan_to_num(rho, nan=0.0)
    gA = rho >= RHO
    return ls0 & gA, ss0 & gA, ls0 & ~gA, ss0 & ~gA, ls0, ss0, rho


def run(d, ls, ss, k_sl, hold):
    atr = s906.atr_pip(d)
    sl = np.nan_to_num(np.clip(k_sl * atr, 5.0, None), nan=5.0)
    return s906.sim_chunked(d, ls, ss, sl, RR * sl, hold)


def stats(tr):
    if tr is None or len(tr) == 0:
        return dict(n=0)
    return dict(n=int(len(tr)), wr=round(float((tr['pnl_pip'] > 0).mean() * 100), 3),
                net=round(float(tr['pnl_pip'].sum()), 1))


def phase_discover():
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, TF)
    n_all = int(d['n_bars']); split = int(n_all * SPLIT_FRAC)
    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v) for k, v in d.items()}
    lsA, ssA, lsB, ssB, ls0, ss0, rho = signals(d1)
    ev = ls0 | ss0
    p_rho = float((rho[ev] >= RHO).mean()) if ev.any() else None
    print(f"DATA src={d['src']} n_bars={n_all} split={split} · IS base events={int(ev.sum())} "
          f"A={int((lsA|ssA).sum())} B={int((lsB|ssB).sum())} P(rho>=0.618|S906)={p_rho}", flush=True)
    results = {}
    for k_sl in GRID_KSL:
        for hold in GRID_HOLD:
            key = f'k{k_sl}_h{hold}'
            results[key] = stats(run(d1, lsA, ssA, k_sl, hold))
            print(f'[{key}] {results[key]}', flush=True)
    json.dump(dict(tf=TF, split=split, n_bars=n_all, src=d['src'], p_rho_is=p_rho, combos=results),
              open(os.path.join(OUT, 'discover_H8.json'), 'w'), indent=1)
    best_key, best_sc = None, -1e18
    for k, r in results.items():
        if r.get('n', 0) < MIN_N_IS:
            continue
        sc = r['wr'] + 0.001 * r['net']
        if sc > best_sc:
            best_key, best_sc = k, sc
    locked = dict(tf=TF, split_bar=split, n_bars=n_all, src=d['src'], n_eff=N_EFF,
                  n_trials_cum=N_TRIALS_CUM, criterion='wr+0.001*net', min_n_is=MIN_N_IS,
                  best_key=best_key, best=results.get(best_key) if best_key else None)
    json.dump(locked, open(os.path.join(OUT, 'locked_H8.json'), 'w'), indent=1)
    print(json.dumps(locked, indent=1))


def judge(d, ls, ss, k_sl, hold, seed, split, label):
    tr = run(d, ls, ss, k_sl, hold)
    if tr is None or len(tr) == 0:
        print(f'{label}: no trades'); return dict(label=label, n_trades=0, verdict='NO TRADES')
    null = s906.build_null_perm(d, ls, ss, hold, K=K_PERM, seed=seed)
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = RR * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=d['time'],
                          null=null, n_trials=N_TRIALS_CUM, split_bar=split, close=d['close'])
    m = r.get('metrics', {})
    is_ = tr[tr['signal_bar'] < split]; oos = tr[tr['signal_bar'] >= split]
    out = dict(label=label, n_trades=int(len(tr)), sl_med=round(sl_med, 1), tp_med=round(tp_med, 1),
               verdict=r['verdict'], score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in m.items()},
               notes=r.get('notes'), null=null,
               is_stats=stats(is_), oos_stats=stats(oos),
               long=stats(tr[tr['direction'] == 'long']), short=stats(tr[tr['direction'] == 'short']))
    print(f"\n{label}: VERDICT={r['verdict']} score={r.get('rqs2_score')} n={m.get('n_trades')} "
          f"wr={m.get('win_rate')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} "
          f"PF={m.get('profit_factor')}\n  gates={json.dumps(r.get('gates'))}\n  notes={r.get('notes')}\n"
          f"  IS={out['is_stats']} OOS={out['oos_stats']} long={out['long']} short={out['short']}", flush=True)
    return out


def phase_final():
    locked = json.load(open(os.path.join(OUT, 'locked_H8.json')))
    if not locked['best_key']:
        print('NO LOCKED CONFIG — INCOMPLETE, holdout untouched.'); return
    k_sl = float(locked['best_key'].split('_')[0][1:]); hold = int(locked['best_key'].split('_')[1][1:])
    split = int(locked['split_bar'])
    d = fd.load_fast(ASSET, TF)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    print(f"FINAL S909 H8 · locked={locked['best_key']} · n_trials={N_TRIALS_CUM} · split_bar={split} · src={d['src']}", flush=True)
    lsA, ssA, lsB, ssB, ls0, ss0, rho = signals(d)
    ev = ls0 | ss0
    p_rho = float((rho[ev] >= RHO).mean())
    print(f'base S906 events={int(ev.sum())}  A={int((lsA|ssA).sum())}  B={int((lsB|ssB).sum())}  P(rho>=0.618|S906)={p_rho:.3f}')
    outA = judge(d, lsA, ssA, k_sl, hold, SEED_A, split, 'ARM-A rho>=0.618')
    outB = judge(d, lsB, ssB, k_sl, hold, SEED_B, split, 'ARM-B rho<0.618 (control)')
    base = stats(run(d, ls0, ss0, k_sl, hold))
    print(f'\nP1 diag — S906 base same geometry: {base}')
    json.dump(dict(tf=TF, locked_key=locked['best_key'], src=d['src'], span_years=d['span_years'],
                   p_rho_given_s906=p_rho, arm_A=outA, arm_B=outB, s906_base_same_geometry=base),
              open(os.path.join(OUT, 'final_H8.json'), 'w'), indent=1, default=str)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)()
