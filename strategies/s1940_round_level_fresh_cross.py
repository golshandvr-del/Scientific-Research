#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S1940 — عبور تازه از سطح رُند (Round-Level Fresh Cross) · XAUUSD · مسیر C
پیش‌ثبت: results/S1940_PREREG_ROUND_LEVEL_FRESH_CROSS.md (کامیت b72966df — قبل از این فایل)

رویداد: close از سطح k·G دلاری عبور می‌کند و سلول جدید در W کندل اخیر close نداشته.
follow: close_i>close_{i-1} → LONG وگرنه SHORT. fade = آینهٔ کنترل.
هندسه: SL=k×ATR100_geom (کف 5pip) · TP=RR×SL · خروج زمانی hold کندل.

زیرساخت شبیه‌ساز/نال/داور عیناً از s940_volatility_birth (راستی‌آزمایی‌شده).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                       # noqa: E402
from engine import rqs2                                     # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402
from strategies.s940_volatility_birth import (              # noqa: E402
    atr_geom_pip, run_combo, build_null, SL_FLOOR_PIP)

ASSET = 'XAUUSD'
OUT = 'results/_scan_S1940'
SEED = 1940
K_PERM = 1000
SPLIT_FRAC = 0.60
MIN_TRADES_DISC = 150
POWER_GATE = 78.0

# ---- شبکهٔ منجمدِ پیش‌ثبت (۹۶ ترکیب) ----
GRID_G = [25.0, 50.0, 100.0]           # شبکهٔ دلاری
GRID_W = [34, 89]                        # تازگی (کندل)
GRID_DIR = ['follow', 'fade']            # fade = آینهٔ کنترل
GRID_KSL = [2.058, 3.141]
GRID_RR = [1.0, 1.5]
GRID_HOLD = [34, 55]


# ---------------------------------------------------------------- سطح رُند
def round_cells(close, G):
    """شمارهٔ سلول شبکهٔ G دلاری برای هر close."""
    return np.floor(close / G).astype(np.int64)


def fresh_cross(cell, W):
    """event[i] = cell[i] != cell[i-1]  و  cell[i] در W کندل اخیر (i-W..i-1) دیده نشده."""
    n = len(cell)
    ev = np.zeros(n, dtype=bool)
    cross = np.zeros(n, dtype=bool)
    cross[1:] = cell[1:] != cell[:-1]
    for i in np.where(cross)[0]:
        if i < W:
            continue
        if not np.any(cell[i - W:i] == cell[i]):
            ev[i] = True
    return ev


def build_signals(d, G, W, direction, cache):
    """cache = round_cells(close, G)."""
    c = d['close']
    cell = cache
    n = len(c)
    ev = fresh_cross(cell, W)
    up = np.zeros(n, dtype=bool)
    up[1:] = c[1:] > c[:-1]
    ls = np.zeros(n, dtype=bool)
    ss = np.zeros(n, dtype=bool)
    if direction == 'follow':
        ls[ev & up] = True
        ss[ev & ~up] = True
    else:                                   # آینهٔ کنترل
        ls[ev & ~up] = True
        ss[ev & up] = True
    return ls, ss


# ---------------------------------------------------------------- فاز کشف
def phase_discover(tf):
    os.makedirs(OUT, exist_ok=True)
    ckpt_fp = os.path.join(OUT, f'discover_{tf}.json')
    done = {}
    if os.path.exists(ckpt_fp):
        with open(ckpt_fp) as f:
            done = json.load(f).get('combos', {})
        print(f'[resume] {len(done)} combos checkpointed', flush=True)

    d = fd.load_fast(ASSET, tf)
    print(f"DATA src={d['src']}  n_bars={d['n_bars']:,}  "
          f"span={d['span_years']}y", flush=True)
    n_all = int(d['n_bars'])
    split = int(n_all * SPLIT_FRAC)
    d1 = {k: (v[:split] if isinstance(v, np.ndarray) else v)
          for k, v in d.items()}
    df1 = fd.as_dataframe(d1)
    atr_g = atr_geom_pip(d1)

    t0 = time.time()
    results = dict(done)
    i, n_total = 0, (len(GRID_G) * len(GRID_W) * len(GRID_DIR)
                     * len(GRID_KSL) * len(GRID_RR) * len(GRID_HOLD))
    for G in GRID_G:
        cache = round_cells(d1['close'], G)
        for W in GRID_W:
            for direction in GRID_DIR:
                ls, ss = build_signals(d1, G, W, direction, cache)
                n_sig = int(ls.sum() + ss.sum())
                for k_sl in GRID_KSL:
                    for rr in GRID_RR:
                        for hold in GRID_HOLD:
                            i += 1
                            key = (f'G{int(G)}_W{W}_{direction}'
                                   f'_k{k_sl}_rr{rr}_hd{hold}')
                            if key in results:
                                continue
                            if n_sig < 10:
                                results[key] = dict(n=0)
                            else:
                                r = run_combo(df1, d1, atr_g, ls, ss,
                                              k_sl, rr, hold)
                                results[key] = r if r else dict(n=0)
                            with open(ckpt_fp, 'w') as f:
                                json.dump(dict(tf=tf, split=split,
                                               n_bars=n_all,
                                               src=d['src'],
                                               combos=results), f, indent=1)
                            rr_ = results[key]
                            print(f'[{i:2d}/{n_total}] {key:<36} '
                                  f'n={rr_.get("n", 0):>6} '
                                  f'wr={rr_.get("wr", "-")} '
                                  f'lift={rr_.get("lift", "-")} '
                                  f'score={rr_.get("score", "-")} '
                                  f'({time.time() - t0:.0f}s)', flush=True)

    # قفل: بیشینهٔ lift·√n | فقط follow (fade کنترل) | کف‌ها + سد توان 78
    best_key, best_score = None, -1e18
    for key, r in results.items():
        if '_fade_' in key:
            continue
        if r.get('n', 0) < MIN_TRADES_DISC or r.get('net', -1) <= 0:
            continue
        if r['score'] > best_score:
            best_key, best_score = key, r['score']
    power_ok = best_key is not None and best_score >= POWER_GATE
    locked = dict(layer='S1940', tf=tf, split_bar=split, n_bars=n_all,
                  src=d['src'],
                  criterion='max lift*sqrt(n) | follow-only | n>=150 & net>0 '
                            f'& power lift*sqrt(n)>={POWER_GATE}',
                  best_key=best_key if power_ok else None,
                  best=results.get(best_key) if power_ok else None,
                  best_unpowered=(dict(key=best_key,
                                       **results.get(best_key))
                                  if (best_key and not power_ok) else None),
                  score=round(best_score, 2) if best_key else None,
                  power_ok=bool(power_ok))
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp, 'w') as f:
        json.dump(locked, f, indent=2)
    print(f'\nLOCKED -> {lock_fp}')
    print(json.dumps(locked, indent=2), flush=True)


# ---------------------------------------------------------------- فاز نهایی
def parse_key(key):
    t = key.split('_')
    return dict(G=float(t[0][1:]), W=int(t[1][1:]), direction=t[2],
                k_sl=float(t[3][1:]), rr=float(t[4][2:]), hold=int(t[5][2:]))


def phase_final(tf):
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print(f'{tf}: NO-CANDIDATE (discovery floor/power unmet) — '
              'holdout stays virgin.', flush=True)
        return
    p = parse_key(locked['best_key'])
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    assert int(d['n_bars']) == int(locked['n_bars']), 'n_bars changed!'
    split = int(locked['split_bar'])
    n_all = int(d['n_bars'])
    hold = p['hold']
    print(f"FINAL ONE-SHOT S1940 {tf} · locked={locked['best_key']} · "
          f'holdout=[{split:,},{n_all:,}) · n_trials=1', flush=True)

    df = fd.as_dataframe(d)
    atr_g = atr_geom_pip(d)
    cache = round_cells(d['close'], p['G'])
    ls, ss = build_signals(d, p['G'], p['W'], p['direction'], cache)
    ls[:split] = False
    ss[:split] = False

    sl = np.nan_to_num(np.clip(p['k_sl'] * atr_g, SL_FLOOR_PIP, None),
                       nan=SL_FLOOR_PIP)
    tp = p['rr'] * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=hold, allow_overlap=False)
    print(f'holdout trades = {len(tr)}', flush=True)
    if len(tr) == 0:
        print('ZERO trades on holdout — dead for this TF.', flush=True)
        return

    null = build_null(d, ls, ss, sl, p['rr'], hold, split, n_all,
                      K=K_PERM, seed=SEED)
    with open(os.path.join(OUT, f'null_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(null, f, indent=2)

    nested_split = split + int(0.60 * (n_all - split))
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = p['rr'] * sl_med
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=1, split_bar=nested_split,
                          close=df['close'].values)
    out = dict(layer='S1940', tf=tf, locked_key=locked['best_key'],
               src=d['src'], n_bars=n_all, span_years=d['span_years'],
               holdout_from=split, nested_split=nested_split,
               hold_bars=hold, n_trades=int(len(tr)),
               sl_med=round(sl_med, 1), tp_med=round(tp_med, 1), n_trials=1,
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    with open(os.path.join(OUT, f'final_XAUUSD-{tf}.json'), 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={r['verdict']}  score={r.get('rqs2_score')}")
    print(f"skill_p_perm={r.get('metrics', {}).get('skill_p_perm')}",
          flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', required=True)
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)(a.tf)
