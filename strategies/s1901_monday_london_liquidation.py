"""
S1901 — Monday London Liquidation · XAUUSD-H8 · RQS2 v2.6 · Path C
====================================================================
سیگنال روی کندل آسیای دوشنبه (dow=0, UTC 00) که کندل بعدش لندن (UTC 08) است:
  A: آسیا صعودی ⇒ SHORT در open لندن.   B (کنترل): هر آسیای دوشنبه ⇒ SHORT.
  P2 (کنترل): SHORT لندن در dow 1..4 با همان هندسه.
null سخت: perm + uncond واقعیِ SHORT روی همهٔ لندن‌ها (هر روز).

پیش‌ثبت: results/S1901_PREREGISTRATION.md (قبل از هر آزمون).
گرید A: k_sl∈{1.272,2.058} × RR∈{1.0,1.618} × hold∈{1,2} ⇒ N_eff=8.
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
OUT = os.path.join(ROOT, 'results', '_s1901')
GRID_KSL = (1.272, 2.058)
GRID_RR = (1.0, 1.618)
GRID_HOLD = (1, 2)
N_EFF = 8
SPLIT_FRAC = 0.60
K_PERM = 1000
SEED = 1901
MIN_N_IS = 150
ASIA_H, LONDON_H = 0, 8


def masks(d):
    t = pd.to_datetime(d['time'], unit='s')
    hour = t.hour.values; dow = t.dayofweek.values
    n = len(hour)
    next_is_london = np.zeros(n, dtype=bool); next_is_london[:-1] = hour[1:] == LONDON_H
    asia_pre_london = (hour == ASIA_H) & next_is_london
    asia_pre_london[:91] = False
    up = d['close'] > d['open']
    A = asia_pre_london & (dow == 0) & up                 # آسیای دوشنبهٔ صعودی
    B = asia_pre_london & (dow == 0)                      # هر آسیای دوشنبه
    P2 = asia_pre_london & (dow >= 1) & (dow <= 4)        # سایر روزها (کنترل جهت)
    UNC = asia_pre_london                                 # همهٔ لندن‌ها (uncond null)
    return A, B, P2, UNC


def run_short(d, sig, k_sl, rr, hold):
    atr = s906.atr_pip(d)
    sl = np.nan_to_num(np.clip(k_sl * atr, 5.0, None), nan=5.0)
    zeros = np.zeros(len(sig), dtype=bool)
    return s906.sim_chunked(d, zeros, sig, sl, rr * sl, hold)


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
    A, B, P2, UNC = masks(d1)
    print(f"DATA src={d['src']} n_bars={n_all} split={split} · IS A={A.sum()} B={B.sum()} P2={P2.sum()} UNC={UNC.sum()}", flush=True)
    results = {}
    for k_sl in GRID_KSL:
        for rr in GRID_RR:
            for hold in GRID_HOLD:
                key = f's{k_sl}_rr{rr}_h{hold}'
                r = stats(run_short(d1, A, k_sl, rr, hold))
                r['armB'] = stats(run_short(d1, B, k_sl, rr, hold))
                r['P2_other_days'] = stats(run_short(d1, P2, k_sl, rr, hold))
                results[key] = r
                print(f'[{key}] A={dict(n=r["n"], wr=r.get("wr"), net=r.get("net"))} B_wr={r["armB"].get("wr")} P2_wr={r["P2_other_days"].get("wr")}', flush=True)
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
    print('locked:', best_key, locked['best'])


def parse_key(key):
    p = {}
    for tok in key.split('_'):
        if tok.startswith('s'): p['k_sl'] = float(tok[1:])
        elif tok.startswith('rr'): p['rr'] = float(tok[2:])
        elif tok.startswith('h'): p['hold'] = int(tok[1:])
    return p


def judge(d, sig, p, split, null, label):
    tr = run_short(d, sig, p['k_sl'], p['rr'], p['hold'])
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=d['time'], null=null,
                          n_trials=N_EFF, split_bar=split, close=d['close'])
    m = r.get('metrics', {})
    is_ = tr[tr['signal_bar'] < split]; oos = tr[tr['signal_bar'] >= split]
    out = dict(label=label, n_trades=int(len(tr)), sl_med=round(sl_med, 1), tp_med=round(tp_med, 1),
               verdict=r['verdict'], score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in m.items()},
               notes=r.get('notes'), is_stats=stats(is_), oos_stats=stats(oos))
    print(f"\n{label}: VERDICT={r['verdict']} score={r.get('rqs2_score')} n={m.get('n_trades')} wr={m.get('win_rate')} "
          f"null_ref={m.get('null_ref_wr')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} PF={m.get('profit_factor')}"
          f"\n  gates={json.dumps(r.get('gates'))}\n  notes={r.get('notes')}\n  IS={out['is_stats']} OOS={out['oos_stats']}", flush=True)
    return out


def phase_final():
    locked = json.load(open(os.path.join(OUT, 'locked_H8.json')))
    if not locked['best_key']:
        print('NO LOCKED CONFIG — INCOMPLETE.'); return
    p = parse_key(locked['best_key']); split = int(locked['split_bar'])
    d = fd.load_fast(ASSET, TF)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    print(f"FINAL S1901 H8 · locked={locked['best_key']} · n_trials={N_EFF} · split_bar={split} · src={d['src']}", flush=True)
    A, B, P2, UNC = masks(d)
    zeros = np.zeros(len(A), dtype=bool)
    # null سخت برای A: perm روی ورودهای A + uncond = WR واقعی SHORT روی همهٔ لندن‌ها
    tr_unc = run_short(d, UNC, p['k_sl'], p['rr'], p['hold'])
    unc_wr = float((tr_unc['pnl_pip'] > 0).mean() * 100)
    def mk_null(sig, seed):
        nl = s906.build_null_perm(d, zeros, sig, p['hold'], K=K_PERM, seed=seed)
        for side in ('long', 'short'): nl[side]['uncond_wr'] = unc_wr
        return nl
    outA = judge(d, A, p, split, mk_null(A, SEED), 'ARM-A Monday London SHORT after up-Asia')
    outB = judge(d, B, p, split, mk_null(B, SEED + 1), 'ARM-B Monday London SHORT unconditional (control)')
    outP2 = judge(d, P2, p, split, mk_null(P2, SEED + 2), 'P2 London SHORT dow1-4 (direction control)')
    out = dict(tf=TF, locked_key=locked['best_key'], src=d['src'], span_years=d['span_years'],
               uncond_london_short_all_days=dict(stats(tr_unc), wr_used_as_null=unc_wr),
               arm_A=outA, arm_B=outB, P2=outP2)
    json.dump(out, open(os.path.join(OUT, 'final_H8.json'), 'w'), indent=1, default=str)
    print(f"\nuncond London SHORT all days: {out['uncond_london_short_all_days']}")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)()
