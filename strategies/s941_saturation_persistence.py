# -*- coding: utf-8 -*-
"""
S941 — «پایداری در اشباع» (Saturation Persistence) · XAUUSD · RQS2 v2.6 · مسیر C
================================================================================

فرضیه (پیش‌ثبت: results/S941_PREREG_SATURATION_PERSISTENCE.md @ 0c7420e8):
streakِ حضورِ Williams %R در ناحیهٔ اشباع که دقیقاً به طول D می‌رسد =
تأییدِ روندِ واقعی (نه نویز) ⇒ ورودِ ادامه. رویداد است نه حالت: شلیک فقط
در کندلِ D-اُم. کنترلِ علمی: بازوی against (خواندنِ کلاسیکِ بازگشتی).

گریدِ منجمد: p∈{8,14,21} × e∈{8,13,21} × D∈{3,5,8} × logic∈{with,against}
             × k_sl∈{1.3,1.7,2.1} × RR∈{1.0,1.5,2.0} × hold∈{48,96} = 972

زیرساختِ مشترک (نول numba، ATR هندسه، run_combo) از s940 وارد می‌شود —
کدِ داوری یکسان، فقط مولدِ سیگنال نو.
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

from engine import scalp_engine as se                     # noqa: E402
from engine import rqs2                                   # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402
from strategies.s940_volatility_birth import (            # noqa: E402
    atr_geom_pip, run_combo, build_null, SL_FLOOR_PIP,
)

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_scan_S941')

GRID_P    = (8, 14, 21)
GRID_E    = (8, 13, 21)
GRID_D    = (3, 5, 8)
GRID_LOG  = ('with', 'against')
GRID_KSL  = (1.3, 1.7, 2.1)
GRID_RR   = (1.0, 1.5, 2.0)
GRID_HOLD = (48, 96)
N_EFF_DECLARED = 972

SPLIT_FRAC = 0.60
MIN_TRADES_DISC = 150
K_PERM = 1000
SEED = 941


def williams_r(d, p):
    h = pd.Series(d['high']).rolling(p).max().values
    l = pd.Series(d['low']).rolling(p).min().values
    c = d['close']
    rng = h - l
    with np.errstate(divide='ignore', invalid='ignore'):
        wr = np.where(rng > 0, -100.0 * (h - c) / rng, np.nan)
    return wr


def streak_events(in_zone, D):
    """True در کندلی که streakِ حضور در ناحیه *دقیقاً* به D می‌رسد (شلیکِ یک‌باره)."""
    z = np.nan_to_num(in_zone, nan=False).astype(bool)
    n = len(z)
    ev = np.zeros(n, dtype=bool)
    run = 0
    for i in range(n):
        if z[i]:
            run += 1
            if run == D:
                ev[i] = True
        else:
            run = 0
    return ev


def build_signals(d, wr, e, D, logic):
    ob = wr > -float(e)             # اشباعِ خرید
    os_ = wr < -100.0 + float(e)    # اشباعِ فروش
    ev_ob = streak_events(ob, D)
    ev_os = streak_events(os_, D)
    if logic == 'with':             # ادامه: اشباعِ خرید ⇒ long
        return ev_ob, ev_os
    return ev_os, ev_ob             # against: خواندنِ کلاسیکِ بازگشتی


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
    print(f'discovery bars={split:,} (first {SPLIT_FRAC:.0%})', flush=True)

    t0 = time.time()
    results = dict(done)
    i = 0
    n_total = N_EFF_DECLARED
    save_every = 10 if tf in ('M1', 'M3', 'M4', 'M5') else 1
    dirty = 0
    for p in GRID_P:
        wr = williams_r(d1, p)
        for e in GRID_E:
            for D in GRID_D:
                for logic in GRID_LOG:
                    ls, ss = build_signals(d1, wr, e, D, logic)
                    n_sig = int(ls.sum() + ss.sum())
                    for k_sl in GRID_KSL:
                        for rr in GRID_RR:
                            for hold in GRID_HOLD:
                                i += 1
                                key = (f'p{p}_e{e}_D{D}_{logic}'
                                       f'_k{k_sl}_rr{rr}_h{hold}')
                                if key in results:
                                    continue
                                if n_sig < 10:
                                    results[key] = dict(n=0)
                                else:
                                    r = run_combo(df1, d1, atr_g, ls, ss,
                                                  k_sl, rr, hold)
                                    results[key] = r if r else dict(n=0)
                                dirty += 1
                                if dirty >= save_every:
                                    with open(ckpt_fp, 'w') as f:
                                        json.dump(dict(tf=tf, split=split,
                                                       n_bars=n_all,
                                                       src=d['src'],
                                                       combos=results),
                                                  f, indent=1)
                                    dirty = 0
                                rr_ = results[key]
                                print(f'[{i:3d}/{n_total}] {key:<38} '
                                      f'n={rr_.get("n", 0):>6} '
                                      f'wr={rr_.get("wr", "-")} '
                                      f'lift={rr_.get("lift", "-")} '
                                      f'score={rr_.get("score", "-")} '
                                      f'({time.time() - t0:.0f}s)', flush=True)
    with open(ckpt_fp, 'w') as f:
        json.dump(dict(tf=tf, split=split, n_bars=n_all, src=d['src'],
                       combos=results), f, indent=1)

    best_key, best_score = None, -1e18
    for key, r in results.items():
        if r.get('n', 0) < MIN_TRADES_DISC or r.get('net', -1) <= 0:
            continue
        if r['score'] > best_score:
            best_key, best_score = key, r['score']
    locked = dict(layer='S941', tf=tf, split_bar=split, n_bars=n_all,
                  src=d['src'], n_eff_declared=N_EFF_DECLARED,
                  criterion='max lift*sqrt(n) s.t. n>=150 & net>0',
                  min_trades=MIN_TRADES_DISC, best_key=best_key,
                  best=results.get(best_key) if best_key else None,
                  score=round(best_score, 3) if best_key else None)
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp, 'w') as f:
        json.dump(locked, f, indent=2)
    print(f'\nLOCKED -> {lock_fp}')
    print(json.dumps(locked, indent=2))
    print('\nNEXT: commit lock, THEN --phase final (one-shot holdout).',
          flush=True)


def parse_key(key):
    toks = key.split('_')
    return dict(p=int(toks[0][1:]), e=int(toks[1][1:]), D=int(toks[2][1:]),
                logic=toks[3], k_sl=float(toks[4][1:]),
                rr=float(toks[5][2:]), hold=int(toks[6][1:]))


def phase_final(tf):
    lock_fp = os.path.join(OUT, f'lock_XAUUSD-{tf}.json')
    with open(lock_fp) as f:
        locked = json.load(f)
    if not locked.get('best_key'):
        print(f'NO LOCKED CONFIG for {tf} — TF verdict = NO-CANDIDATE.',
              flush=True)
        return
    p = parse_key(locked['best_key'])
    d = fd.load_fast(ASSET, tf)
    assert d['src'] == locked['src'], 'data source changed since lock!'
    assert int(d['n_bars']) == int(locked['n_bars']), 'n_bars changed!'
    split = int(locked['split_bar'])
    n_all = int(d['n_bars'])
    print(f"FINAL ONE-SHOT S941 {tf} · locked={locked['best_key']} · "
          f'holdout=[{split:,},{n_all:,}) · n_trials=1', flush=True)

    df = fd.as_dataframe(d)
    atr_g = atr_geom_pip(d)
    wr = williams_r(d, p['p'])
    ls, ss = build_signals(d, wr, p['e'], p['D'], p['logic'])
    ls[:split] = False
    ss[:split] = False

    sl = np.nan_to_num(np.clip(p['k_sl'] * atr_g, SL_FLOOR_PIP, None),
                       nan=SL_FLOOR_PIP)
    tp = p['rr'] * sl
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=p['hold'], allow_overlap=False)
    print(f'holdout trades = {len(tr)}', flush=True)
    if len(tr) == 0:
        print('ZERO trades on holdout — dead for this TF.', flush=True)
        return

    null = build_null(d, ls, ss, sl, p['rr'], p['hold'], split, n_all,
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
    out = dict(layer='S941', tf=tf, locked_key=locked['best_key'],
               src=d['src'], n_bars=n_all, span_years=d['span_years'],
               holdout_from=split, nested_split=nested_split,
               n_trades=int(len(tr)), sl_med=round(sl_med, 1),
               tp_med=round(tp_med, 1), n_trials=1,
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=r.get('notes'))
    fp = os.path.join(OUT, f'final_XAUUSD-{tf}.json')
    with open(fp, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nVERDICT={r['verdict']}  score={r.get('rqs2_score')}")
    print(f"skill_p_perm={r.get('metrics', {}).get('skill_p_perm')}")
    print(f'SAVED -> {fp}', flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    ap.add_argument('--tf', required=True)
    a = ap.parse_args()
    if a.phase == 'discover':
        phase_discover(a.tf)
    else:
        phase_final(a.tf)
