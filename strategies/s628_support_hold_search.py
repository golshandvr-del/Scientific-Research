#!/usr/bin/env python3
"""
S628 — Rolling-Support Hold LONG (55-bar low test-and-hold) — XAUUSD H1/H2/H4
PREREG: results/S628_PREREG_XAUUSD_rolling_support_hold_long_pathC.md (commit a0cba9ef)
Path C: search FIRST HALF ONLY. Holdout [n/2, n) never touched.
Event: low>=Lmin(55) AND low<=Lmin+tau AND close>Lmin+tau AND drift90>0. Entry open[i+1]+slip.
Null: unconditional entries in drift>0 valid bars, same frozen geometry (S346+S612 laws).
SEED=20260820
"""
import sys, os, json, gc, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import indicator_bank as ib
from engine import scalp_engine as se

SEED = 20260820
LOOK = 55            # frozen a-priori (Fibonacci), not searched
DRIFT_LAG = 90       # frozen from S950
CS = [0.1, 0.2]
KSLS = [1.5, 2.0]
RRS = [1.0, 1.5]
MAX_HOLD = {'H1': 96, 'H2': 64, 'H4': 48}
N_BASE = 20000
PIP = 0.10

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', '_scan_S628')
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

    lo = df['low'].values; cl = df['close'].values
    n = len(df)
    mh = MAX_HOLD[tf]
    print(f'[S628/{tf}] src={src} n_full={n_full} search_half={n} mh={mh}', flush=True)

    atr = ib.atr_s(df, 100)          # pip units
    atr_price = atr * PIP

    # causal rolling min of low over [i-LOOK, i-1]
    lmin = pd.Series(lo).rolling(LOOK).min().shift(1).values

    drift = np.zeros(n, dtype=bool)
    drift[DRIFT_LAG:] = cl[DRIFT_LAG - 1:n - 1] > cl[:n - DRIFT_LAG]

    valid = (~np.isnan(atr_price)) & (atr_price > 0) & (~np.isnan(lmin))
    valid[:LOOK + 2] = False
    valid[n - mh - 2:] = False

    rng = np.random.default_rng(SEED)
    no_short = np.zeros(n, dtype=bool)

    pool = np.where(valid & drift)[0]
    print(f'[S628/{tf}] drift>0 valid bars = {len(pool)}', flush=True)
    if len(pool) < 100:
        print(f'[S628/{tf}] SKIP', flush=True)
        return
    samp = rng.choice(pool, size=min(N_BASE, len(pool)), replace=False)
    bsig = np.zeros(n, dtype=bool)
    bsig[samp] = True

    baselines = {}
    for k_sl in KSLS:
        sl_arr = k_sl * atr
        for rr in RRS:
            tr = se.simulate_trades(df, bsig, no_short, sl_arr, rr * sl_arr,
                                    'XAUUSD', max_hold=mh, allow_overlap=False)
            wr, expp, nb = wr_exp(tr)
            baselines[(k_sl, rr)] = {'wr': wr, 'n': nb, 'exp': expp}
            print(f'[S628/{tf}] baseline k={k_sl} rr={rr}: wr={wr:.2f} n={nb} exp={expp:.2f}', flush=True)
            del tr
    gc.collect()

    results = []
    for c in CS:
        tau = c * atr_price
        ev = valid & drift & (lo >= lmin) & (lo <= lmin + tau) & (cl > lmin + tau)
        n_ev = int(ev.sum())
        for k_sl in KSLS:
            sl_arr = k_sl * atr
            for rr in RRS:
                b = baselines[(k_sl, rr)]
                if n_ev < 5:
                    continue
                tr = se.simulate_trades(df, ev, no_short, sl_arr, rr * sl_arr,
                                        'XAUUSD', max_hold=mh, allow_overlap=False)
                wr, expp, nb = wr_exp(tr)
                del tr
                if nb == 0 or b['wr'] is None:
                    continue
                lift = wr - b['wr']
                lsn = lift * np.sqrt(nb)
                p0 = b['wr'] / 100.0
                n_req = (3.09 * 100.0 * np.sqrt(p0 * (1 - p0)) / lift) ** 2 if lift > 0 else float('inf')
                row = {'c': c, 'k_sl': k_sl, 'rr': rr, 'n': nb, 'n_events': n_ev,
                       'wr': round(wr, 3), 'ref_wr': round(b['wr'], 3),
                       'lift': round(lift, 3), 'exp_pip': round(expp, 3),
                       'lift_sqrt_n': round(lsn, 1),
                       'n_req': (int(n_req) if np.isfinite(n_req) else -1)}
                results.append(row)
                tag = ''
                if lift >= 4.0 and expp > 0 and nb >= n_req:
                    tag = '✓ QUALIFIER'
                elif lift >= 4.0 and expp > 0:
                    tag = '✗n'
                print(f'[S628/{tf}] c={c} k={k_sl} rr={rr}: wr={wr:.2f} ref={b["wr"]:.2f} '
                      f'lift={lift:+.2f} n={nb} n_req={row["n_req"]} exp={expp:+.2f} {tag}', flush=True)
        print(f'[S628/{tf}] c={c} done (events={n_ev})', flush=True)
        gc.collect()

    out = os.path.join(OUT_DIR, f'{tf}.json')
    with open(out, 'w') as f:
        json.dump({'tf': tf, 'seed': SEED, 'search_half': n, 'mh': mh,
                   'look': LOOK, 'results': results}, f, indent=1)
    print(f'[S628/{tf}] تمام ({time.time()-t0:.0f}s) → {tf}.json', flush=True)


if __name__ == '__main__':
    for tf in (sys.argv[1:] or ['H1', 'H2', 'H4']):
        run_tf(tf)
        gc.collect()
