"""
S1900 — Asian Re-accumulation after NY Sell-off · XAUUSD-H8 · RQS2 v2.6 · Path C
==================================================================================
کندل NY (UTC 16) با بدنهٔ ≤ −k·ATR21[NY−1] ⇒ سیگنال LONG روی همان کندل ⇒ ورود
open کندل بعد (آسیا، UTC 00). فقط اگر کندل بعد واقعاً ساعت 00 باشد.
آینهٔ SHORT (NY-up ⇒ SHORT) فقط کنترل P2. null سخت: perm + uncond واقعیِ آسیای بی‌قید.

پیش‌ثبت: results/S1900_PREREGISTRATION.md (قبل از هر آزمون).
گرید: k∈{0.5,1.0} × k_sl∈{1.272,2.058} × RR∈{1.0,1.618} × hold∈{1,3} ⇒ N_eff=16.
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
_spec.loader.exec_module(s906)                     # sim_chunked, atr_pip(ATR89 pip), build_null_perm

ASSET, TF = 'XAUUSD', 'H8'
OUT = os.path.join(ROOT, 'results', '_s1900')
GRID_K = (0.5, 1.0)
GRID_KSL = (1.272, 2.058)
GRID_RR = (1.0, 1.618)
GRID_HOLD = (1, 3)
N_EFF = 16
SPLIT_FRAC = 0.60
K_PERM = 1000
SEED = 1900
MIN_N_IS = 180
NY_H, ASIA_H = 16, 0


def features(d):
    h, l, c, o = d['high'], d['low'], d['close'], d['open']
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr21_prev = pd.Series(tr).rolling(21).mean().shift(1).values
    hour = pd.to_datetime(d['time'], unit='s').hour.values
    n = len(c)
    next_is_asia = np.zeros(n, dtype=bool)
    next_is_asia[:-1] = hour[1:] == ASIA_H
    ny_ok = (hour == NY_H) & next_is_asia
    ny_ok[:91] = False
    body = c - o
    return atr21_prev, hour, ny_ok, body


def signals(d, k):
    atr21_prev, hour, ny_ok, body = features(d)
    with np.errstate(invalid='ignore'):
        ls = ny_ok & (body <= -k * atr21_prev)          # LONG: فروش NY
        ss_mirror = ny_ok & (body >= k * atr21_prev)    # کنترل: SHORT پس از خرید NY
    ls = np.nan_to_num(ls, nan=False).astype(bool)
    ss_mirror = np.nan_to_num(ss_mirror, nan=False).astype(bool)
    uncond = ny_ok.copy()                                 # همهٔ NY→Asia بی‌قید (برای uncond_wr)
    return ls, ss_mirror, uncond


def run(d, ls, ss, k_sl, rr, hold):
    atr = s906.atr_pip(d)
    sl = np.nan_to_num(np.clip(k_sl * atr, 5.0, None), nan=5.0)
    return s906.sim_chunked(d, ls, ss, sl, rr * sl, hold)


def stats(tr):
    if tr is None or len(tr) == 0:
        return dict(n=0)
    return dict(n=int(len(tr)), wr=round(float((tr['pnl_pip'] > 0).mean() * 100), 3),
                net=round(float(tr['pnl_pip'].sum()), 1))


def phase_discover():
    os.makedirs(OUT, exist_ok=True)
    d = fd.load_fast(ASSET, TF)
    n_all = int(d['n_bars']); split = int(n_all * SPLIT_FRAC)
    d1 = {kk: (v[:split] if isinstance(v, np.ndarray) else v) for kk, v in d.items()}
    print(f"DATA src={d['src']} n_bars={n_all} split={split}", flush=True)
    zeros = np.zeros(split, dtype=bool)
    results = {}
    for k in GRID_K:
        ls, ssm, unc = signals(d1, k)
        for k_sl in GRID_KSL:
            for rr in GRID_RR:
                for hold in GRID_HOLD:
                    key = f'k{k}_s{k_sl}_rr{rr}_h{hold}'
                    r = stats(run(d1, ls, zeros, k_sl, rr, hold))
                    r['n_sig'] = int(ls.sum())
                    # تشخیصی P1/P2 در IS (نه انتخاب)
                    r['uncond_asia_long'] = stats(run(d1, unc, zeros, k_sl, rr, hold))
                    r['mirror_short'] = stats(run(d1, zeros, ssm, k_sl, rr, hold))
                    results[key] = r
                    print(f'[{key}] {dict(n=r["n"], wr=r.get("wr"), net=r.get("net"))} '
                          f'uncond={r["uncond_asia_long"].get("wr")} mirror={r["mirror_short"].get("wr")}', flush=True)
    json.dump(dict(tf=TF, split=split, n_bars=n_all, src=d['src'], combos=results),
              open(os.path.join(OUT, 'discover_H8.json'), 'w'), indent=1)
    best_key, best_sc = None, -1e18
    for kk, r in results.items():
        if r.get('n', 0) < MIN_N_IS:
            continue
        sc = r['wr'] + 0.001 * r['net']
        if sc > best_sc:
            best_key, best_sc = kk, sc
    locked = dict(tf=TF, split_bar=split, n_bars=n_all, src=d['src'], n_eff=N_EFF, n_trials=N_EFF,
                  criterion='wr+0.001*net', min_n_is=MIN_N_IS, best_key=best_key,
                  best=results.get(best_key) if best_key else None)
    json.dump(locked, open(os.path.join(OUT, 'locked_H8.json'), 'w'), indent=1)
    print(json.dumps({k: v for k, v in locked.items() if k != 'best'}, indent=1))
    print('best:', locked['best'])


def parse_key(key):
    p = {}
    for tok in key.split('_'):
        if tok.startswith('k'): p['k'] = float(tok[1:])
        elif tok.startswith('s'): p['k_sl'] = float(tok[1:])
        elif tok.startswith('rr'): p['rr'] = float(tok[2:])
        elif tok.startswith('h'): p['hold'] = int(tok[1:])
    return p


def phase_final():
    locked = json.load(open(os.path.join(OUT, 'locked_H8.json')))
    if not locked['best_key']:
        print('NO LOCKED CONFIG — INCOMPLETE, holdout untouched.'); return
    p = parse_key(locked['best_key']); split = int(locked['split_bar'])
    d = fd.load_fast(ASSET, TF)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    print(f"FINAL S1900 H8 · locked={locked['best_key']} · n_trials={N_EFF} · split_bar={split} · src={d['src']}", flush=True)
    n = int(d['n_bars']); zeros = np.zeros(n, dtype=bool)
    ls, ssm, unc = signals(d, p['k'])
    tr = run(d, ls, zeros, p['k_sl'], p['rr'], p['hold'])
    # null سخت: perm + uncond واقعی
    null = s906.build_null_perm(d, ls, zeros, p['hold'], K=K_PERM, seed=SEED)
    tr_unc = run(d, unc, zeros, p['k_sl'], p['rr'], p['hold'])
    unc_wr = float((tr_unc['pnl_pip'] > 0).mean() * 100)
    for side in ('long', 'short'):
        null[side]['uncond_wr'] = unc_wr
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=d['time'], null=null,
                          n_trials=N_EFF, split_bar=split, close=d['close'])
    m = r.get('metrics', {})
    tr_mir = run(d, zeros, ssm, p['k_sl'], p['rr'], p['hold'])
    is_ = tr[tr['signal_bar'] < split]; oos = tr[tr['signal_bar'] >= split]
    out = dict(tf=TF, locked_key=locked['best_key'], src=d['src'], span_years=d['span_years'],
               n_trades=int(len(tr)), sl_med=round(sl_med, 1), tp_med=round(tp_med, 1),
               verdict=r['verdict'], score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in m.items()},
               notes=r.get('notes'), null=null, uncond_asia_long_full=stats(tr_unc),
               mirror_short_full=stats(tr_mir), is_stats=stats(is_), oos_stats=stats(oos))
    json.dump(out, open(os.path.join(OUT, 'final_H8.json'), 'w'), indent=1, default=str)
    print(f"\nVERDICT={r['verdict']} score={r.get('rqs2_score')}\ngates={json.dumps(r.get('gates'))}")
    print(f"n={m.get('n_trades')} wr={m.get('win_rate')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} "
          f"p={m.get('skill_p_perm')} PF={m.get('profit_factor')} null_ref={m.get('null_ref_wr')}")
    print(f"notes={r.get('notes')}")
    print(f"uncond Asia-LONG full={out['uncond_asia_long_full']}  mirror SHORT full={out['mirror_short_full']}")
    print(f"IS={out['is_stats']} OOS={out['oos_stats']}")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)()
