#!/usr/bin/env python3
"""
S629 — Fresh-High Continuation LONG (naked 55-bar-high crossing) — XAUUSD H6/H8/H12
PREREG: results/S629_PREREG_XAUUSD_fresh_high_continuation_long_pathC.md (commit 52f1bf3a)
Path C: search FIRST HALF ONLY. Holdout [n/2, n) never touched.
Event: close[i]>Hmax55[i] AND close[i-1]<=Hmax55[i-1] AND drift90>0. Entry open[i+1]+slip.
Null: unconditional entries in drift>0 valid bars, same frozen geometry (S346+S612).
SEED=20260821
"""
import sys, os, json, gc, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import indicator_bank as ib
from engine import scalp_engine as se

SEED = 20260821
LOOK = 55
DRIFT_LAG = 90
KSLS = [1.5, 2.0]
RRS = [1.0, 1.5]
MAX_HOLD = {'H6': 56, 'H8': 42, 'H12': 28}
N_BASE = 20000

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', '_scan_S629')
os.makedirs(OUT_DIR, exist_ok=True)


def wr_exp(tr):
    if tr is None or len(tr) == 0:
        return None, None, 0
    return (100.0 * float((tr['pnl_pip'] > 0).mean()),
            float(tr['pnl_pip'].mean()), int(len(tr)))


def run_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    src = d['src']
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)
    del df_full; d.clear(); gc.collect()

    hi = df['high'].values; cl = df['close'].values
    n = len(df)
    mh = MAX_HOLD[tf]
    print(f'[S629/{tf}] src={src} n_full={n_full} search_half={n} mh={mh}', flush=True)

    atr = ib.atr_s(df, 100)  # pip units

    hmax = pd.Series(hi).rolling(LOOK).max().shift(1).values

    drift = np.zeros(n, dtype=bool)
    drift[DRIFT_LAG:] = cl[DRIFT_LAG - 1:n - 1] > cl[:n - DRIFT_LAG]

    valid = (~np.isnan(atr)) & (atr > 0) & (~np.isnan(hmax))
    valid[:max(LOOK, DRIFT_LAG) + 2] = False
    valid[n - mh - 2:] = False

    above = cl > hmax
    prev_above = np.zeros(n, dtype=bool)
    prev_above[1:] = above[:-1]
    ev = valid & drift & above & ~prev_above
    n_ev = int(ev.sum())

    pool = np.where(valid & drift)[0]
    print(f'[S629/{tf}] events={n_ev} | drift-valid bars={len(pool)}', flush=True)
    if n_ev < 5 or len(pool) < 100:
        print(f'[S629/{tf}] SKIP: insufficient events', flush=True)
        return

    rng = np.random.default_rng(SEED)
    samp = rng.choice(pool, size=min(N_BASE, len(pool)), replace=False)
    bsig = np.zeros(n, dtype=bool)
    bsig[samp] = True
    no_short = np.zeros(n, dtype=bool)

    results = []
    for k_sl in KSLS:
        sl_arr = k_sl * atr
        for rr in RRS:
            tr = se.simulate_trades(df, bsig, no_short, sl_arr, rr * sl_arr,
                                    'XAUUSD', max_hold=mh, allow_overlap=False)
            ref_wr, ref_exp, ref_n = wr_exp(tr)
            del tr
            trs = se.simulate_trades(df, ev, no_short, sl_arr, rr * sl_arr,
                                     'XAUUSD', max_hold=mh, allow_overlap=False)
            wr, expp, nb = wr_exp(trs)
            del trs
            gc.collect()
            if nb == 0 or ref_wr is None:
                continue
            lift = wr - ref_wr
            lsn = lift * np.sqrt(nb)
            p0 = ref_wr / 100.0
            n_req = (3.09 * 100.0 * np.sqrt(p0 * (1 - p0)) / lift) ** 2 if lift > 0 else float('inf')
            row = {'k_sl': k_sl, 'rr': rr, 'n': nb, 'n_events': n_ev,
                   'wr': round(wr, 3), 'ref_wr': round(ref_wr, 3),
                   'ref_n': ref_n, 'ref_exp': round(ref_exp, 3),
                   'lift': round(lift, 3), 'exp_pip': round(expp, 3),
                   'lift_sqrt_n': round(lsn, 1),
                   'n_req': (int(n_req) if np.isfinite(n_req) else -1)}
            results.append(row)
            tag = ''
            if lift >= 4.0 and expp > 0 and nb >= n_req:
                tag = '✓ QUALIFIER'
            elif lift >= 4.0 and expp > 0:
                tag = '✗n'
            print(f'[S629/{tf}] k={k_sl} rr={rr}: wr={wr:.2f} ref={ref_wr:.2f} '
                  f'lift={lift:+.2f} n={nb} n_req={row["n_req"]} exp={expp:+.2f} {tag}', flush=True)

    out = os.path.join(OUT_DIR, f'{tf}.json')
    with open(out, 'w') as f:
        json.dump({'tf': tf, 'seed': SEED, 'search_half': n, 'mh': mh,
                   'look': LOOK, 'n_events': n_ev, 'results': results}, f, indent=1)
    print(f'[S629/{tf}] تمام ({time.time()-t0:.0f}s) → {tf}.json', flush=True)


if __name__ == '__main__':
    for tf in (sys.argv[1:] or ['H8', 'H6', 'H12']):
        run_tf(tf)
        gc.collect()
