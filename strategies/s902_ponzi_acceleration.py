"""
S902 — Ponzi Acceleration · XAUUSD · RQS2 v2.6 · Path C
=========================================================
فرضیهٔ مینسکی: فاز پانزیِ روند = لحظهٔ آغاز شتاب‌گیری EMA (مشتق دوم مثبت
می‌شود در روند مثبت). رویداد یال‌محور (edge-triggered) — نه سطح.

پیش‌ثبت: results/S902_PREREGISTRATION.md (کامیت beab284f — قبل از هر آزمون)
گرید منجمد: L∈{21,55} × a∈{8,13} × k_sl∈{1.5,2.5} × RR∈{1.5,2.0}
            × hold∈{34,89}  ⇒  N_eff=32.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s902')

GRID_L = (21, 55)
GRID_A = (8, 13)
GRID_KSL = (1.5, 2.5)
GRID_RR = (1.5, 2.0)
GRID_HOLD = (34, 89)
N_EFF = 32
assert len(GRID_L)*len(GRID_A)*len(GRID_KSL)*len(GRID_RR)*len(GRID_HOLD) == N_EFF

ATR_P = 14
SPLIT_FRAC = 0.60
K_PERM = 1000
SEED = 902


def atr_pip(d):
    h, l, c = d['high'], d['low'], d['close']
    pip = se.ASSETS[ASSET]['pip']
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return pd.Series(tr).rolling(ATR_P).mean().values / pip


def ema(x, L):
    return pd.Series(x).ewm(span=L, adjust=False).mean().values


def build_signals(d, L, a):
    """آغازِ شتاب: accel از غیرمثبت به مثبت (long) — یال، نه سطح."""
    e = ema(d['close'], L)
    slope = np.full_like(e, np.nan)
    slope[a:] = e[a:] - e[:-a]
    accel = np.full_like(e, np.nan)
    accel[a:] = slope[a:] - slope[:-a]
    prev_accel = np.concatenate(([np.nan], accel[:-1]))
    ls = (slope > 0) & (accel > 0) & (prev_accel <= 0)
    ss = (slope < 0) & (accel < 0) & (prev_accel >= 0)
    ls = np.nan_to_num(ls, nan=False).astype(bool)
    ss = np.nan_to_num(ss, nan=False).astype(bool)
    return ls, ss


def run_combo(df, atr, ls, ss, k_sl, rr, hold):
    sl = np.nan_to_num(np.clip(k_sl * atr, 5.0, None), nan=5.0)
    tp = rr * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    wr = float((tr['pnl_pip'] > 0).mean() * 100.0)
    net = float(tr['pnl_pip'].sum())
    return dict(n=len(tr), wr=round(wr, 3), net=round(net, 1))


def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    ckpt_fp = os.path.join(OUT, f'discover_{tf}.json')
    done = {}
    if os.path.exists(ckpt_fp):
        with open(ckpt_fp) as f:
            done = json.load(f).get('combos', {})
        print(f'[resume] {len(done)} combos checkpointed')

    d = fd.load_fast(ASSET, tf)
    print(f"DATA src={d['src']} n_bars={d['n_bars']:,} span={d['span_years']}y",
          flush=True)
    n_all = int(d['n_bars'])
    split = int(n_all * SPLIT_FRAC)
    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v) for k, v in d.items()}
    df1 = fd.as_dataframe(d1)
    atr = atr_pip(d1)

    t0 = time.time()
    results = dict(done)
    i = 0
    for L in GRID_L:
        for a in GRID_A:
            ls, ss = build_signals(d1, L, a)
            for k_sl in GRID_KSL:
                for rr in GRID_RR:
                    for hold in GRID_HOLD:
                        i += 1
                        key = f'L{L}_a{a}_k{k_sl}_rr{rr}_h{hold}'
                        if key in results:
                            continue
                        r = run_combo(df1, atr, ls, ss, k_sl, rr, hold)
                        results[key] = r or dict(n=0)
                        with open(ckpt_fp, 'w') as f:
                            json.dump(dict(tf=tf, split=split, n_bars=n_all,
                                           src=d['src'], combos=results), f, indent=1)
                        v = results[key]
                        print(f'[{i:2d}/{N_EFF}] {key:<26} n={v.get("n",0):>6} '
                              f'wr={v.get("wr","-")} net={v.get("net","-")} '
                              f'({time.time()-t0:.0f}s)', flush=True)

    floor = 400 if tf == 'M1' else 60
    best_key, best_score = None, -1e18
    for key, r in results.items():
        if r.get('n', 0) < floor:
            continue
        score = r['wr'] + 0.001 * r['net']
        if score > best_score:
            best_key, best_score = key, score
    locked = dict(tf=tf, split_bar=split, n_bars=n_all, src=d['src'],
                  n_eff=N_EFF, criterion='wr+0.001*net', min_trades=floor,
                  best_key=best_key, best=results.get(best_key) if best_key else None,
                  score=round(best_score, 4) if best_key else None)
    with open(os.path.join(OUT, f'locked_{tf}.json'), 'w') as f:
        json.dump(locked, f, indent=2)
    print('\nLOCKED:', json.dumps(locked, indent=2))


def build_null_perm(d, ls, ss, hold, K=K_PERM, seed=SEED):
    sig_idx = np.where(ls | ss)[0]
    n = len(sig_idx)
    if n < 30:
        return None
    c = d['close']
    rng = np.random.default_rng(seed)
    N = len(c)
    fwd = np.full(n, np.nan)
    for j, ei in enumerate(sig_idx):
        k = min(ei + hold, N - 1)
        fwd[j] = c[k] - c[ei]
    fwd = fwd[np.isfinite(fwd)]
    if len(fwd) < 30:
        return None
    base_wins = fwd > 0
    m = len(fwd)
    wrs = np.empty(K)
    for t in range(K):
        signs = rng.integers(0, 2, size=m).astype(bool)
        wrs[t] = np.where(signs, base_wins, ~base_wins).mean() * 100.0
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs, ddof=1)),
                perm_max=float(np.max(wrs)), perm_k=int(K))
    return {'long': dict(side), 'short': dict(side)}


def parse_key(key):
    p = {}
    for tok in key.split('_'):
        if tok.startswith('L'):
            p['L'] = int(tok[1:])
        elif tok.startswith('a'):
            p['a'] = int(tok[1:])
        elif tok.startswith('k'):
            p['k_sl'] = float(tok[1:])
        elif tok.startswith('rr'):
            p['rr'] = float(tok[2:])
        elif tok.startswith('h'):
            p['hold'] = int(tok[1:])
    return p


def phase_final(tf):
    with open(os.path.join(OUT, f'locked_{tf}.json')) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print('NO LOCKED CONFIG — no test to run.')
        return
    p = parse_key(locked['best_key'])
    print(f"FINAL S902 {tf} · locked={locked['best_key']} · "
          f"n_trials={N_EFF} · split_bar={locked['split_bar']}")
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    df = fd.as_dataframe(d)
    atr = atr_pip(d)
    ls, ss = build_signals(d, p['L'], p['a'])
    sl = np.nan_to_num(np.clip(p['k_sl'] * atr, 5.0, None), nan=5.0)
    tp = p['rr'] * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=p['hold'], allow_overlap=False)
    print(f'trades total={len(tr)}')
    null = build_null_perm(d, ls, ss, p['hold'])
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_EFF, split_bar=locked['split_bar'],
                          close=df['close'].values)
    out = dict(tf=tf, locked_key=locked['best_key'], src=d['src'],
               n_bars=d['n_bars'], span_years=d['span_years'],
               n_trades=int(len(tr)), sl_med=round(sl_med, 1),
               tp_med=round(tp_med, 1), verdict=r['verdict'],
               score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics=r.get('metrics'), notes=r.get('notes'))
    with open(os.path.join(OUT, f'final_{tf}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={r['verdict']} score={r.get('rqs2_score')}")
    print(f"skill_p_perm={r.get('metrics', {}).get('skill_p_perm')}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)(a.tf)
