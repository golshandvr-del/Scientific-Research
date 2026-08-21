#!/usr/bin/env python3
"""
S626 — Round-Number Rejection NATIVE-COARSE + Drift Gate — XAUUSD H1/H2/H4
PREREG: results/S626_PREREG_XAUUSD_round_number_native_coarse_drift_pathC.md (commit e527f08b)
Path C: search FIRST HALF ONLY. Holdout [n/2, n) never touched here.
Null: drift-conditioned unconditional entries (S346 lesson — drift beta is not skill).
SEED=20260818
"""
import sys, os, json, gc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import indicator_bank as ib
from engine import scalp_engine as se

SEED = 20260818
PIP = 0.10
SPREAD_PIP = 3.3
SLIP_PIP = 0.5
COST = SPREAD_PIP + 2 * SLIP_PIP

GRIDS = [50.0, 100.0]
CS = [0.1, 0.2]
KSLS = [1.5, 2.0]
RRS = [1.0, 1.5]
MAX_HOLD = {'H1': 96, 'H2': 64, 'H4': 48}
DRIFT_LAG = 90  # frozen from S950: close[i-1] > close[i-90]
N_BASE = 20000

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'mt5_full')
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', '_scan_S626')
os.makedirs(OUT_DIR, exist_ok=True)


def run_tf(tf):
    d = fd.load_fast('XAUUSD', tf)
    src = d['src']
    df_full = fd.as_dataframe(d)
    n_full = len(df_full)
    half = n_full // 2
    df = df_full.iloc[:half].reset_index(drop=True)
    del df_full; d.clear(); gc.collect()

    op = df['open'].values; hi = df['high'].values
    lo = df['low'].values; cl = df['close'].values
    tm = df['time'].values
    n = len(df)
    print(f'[S626/{tf}] src={src} n_full={n_full} search_half={n} mh={MAX_HOLD[tf]}', flush=True)

    atr = ib.atr_s(df, 100)  # pip units
    atr_price = atr * PIP
    mh = MAX_HOLD[tf]

    # frozen drift gate (S950): close[i-1] > close[i-90], causal
    drift = np.zeros(n, dtype=bool)
    drift[DRIFT_LAG:] = cl[DRIFT_LAG - 1:n - 1] > cl[:n - DRIFT_LAG]

    valid = np.zeros(n, dtype=bool)
    valid[100:] = ~np.isnan(atr_price[100:]) & (atr_price[100:] > 0)
    # entry at open of i+1 => need i+1+mh < n
    valid[max(0, n - mh - 2):] = False

    rng = np.random.default_rng(SEED)
    no_short = np.zeros(n, dtype=bool)

    def wr_exp(tr):
        if tr is None or len(tr) == 0:
            return None, None, 0
        wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
        return wr, float(tr['pnl_pip'].mean()), int(len(tr))

    # ---- drift-conditioned unconditional baselines per (k_sl, rr) ----
    base_pool = np.where(valid & drift)[0]
    print(f'[S626/{tf}] drift>0 valid bars = {len(base_pool)}', flush=True)
    if len(base_pool) == 0:
        print(f'[S626/{tf}] SKIP: no drift-valid bars', flush=True)
        return
    samp = rng.choice(base_pool, size=min(N_BASE, len(base_pool)), replace=False)
    bsig = np.zeros(n, dtype=bool)
    bsig[samp] = True
    baselines = {}
    for k_sl in KSLS:
        sl_arr = k_sl * atr  # pip units, full-length array
        for rr in RRS:
            tr = se.simulate_trades(df, bsig, no_short, sl_arr, rr * sl_arr,
                                    'XAUUSD', max_hold=mh, allow_overlap=False)
            wr, expp, nb = wr_exp(tr)
            baselines[(k_sl, rr)] = {'wr': wr, 'n': nb, 'exp': expp}
            print(f'[S626/{tf}] baseline drift-cond k={k_sl} rr={rr}: wr={wr:.2f} n={nb} exp={expp:.2f}', flush=True)
            del tr
    gc.collect()

    results = []
    for G in GRIDS:
        for c in CS:
            tau = c * atr_price
            R = np.round(lo / G) * G
            ev = valid & drift & (np.abs(lo - R) <= tau) & (cl > R + tau)
            n_ev = int(ev.sum())
            for k_sl in KSLS:
                sl_arr = k_sl * atr
                for rr in RRS:
                    b = baselines[(k_sl, rr)]
                    if n_ev < 5:
                        results.append({'G': G, 'c': c, 'k_sl': k_sl, 'rr': rr,
                                        'n': 0, 'n_events': n_ev, 'wr': None,
                                        'ref_wr': b['wr'], 'lift': None, 'exp_pip': None,
                                        'lift_sqrt_n': None})
                        continue
                    tr = se.simulate_trades(df, ev, no_short, sl_arr, rr * sl_arr,
                                            'XAUUSD', max_hold=mh, allow_overlap=False)
                    wr, expp, nb = wr_exp(tr)
                    del tr
                    if nb == 0:
                        continue
                    lift = wr - b['wr']
                    lsn = lift * np.sqrt(nb)
                    p0 = b['wr'] / 100.0
                    n_req = (3.09 * 100.0 * np.sqrt(p0 * (1 - p0)) / lift) ** 2 if lift > 0 else float('inf')
                    row = {'G': G, 'c': c, 'k_sl': k_sl, 'rr': rr,
                           'n': int(nb), 'n_events': n_ev,
                           'wr': round(wr, 3), 'ref_wr': round(b['wr'], 3),
                           'lift': round(lift, 3), 'exp_pip': round(expp, 3),
                           'lift_sqrt_n': round(lsn, 1),
                           'n_req': (int(n_req) if np.isfinite(n_req) else -1)}
                    results.append(row)
                    if lift >= 4.0 and expp > 0 and nb >= n_req:
                        print(f'[S626/{tf}] ✓ QUALIFIER G={G} c={c} k={k_sl} rr={rr}: '
                              f'lift={lift:.2f} n={nb}>=n_req={int(n_req)} exp={expp:.2f}', flush=True)
                    elif lift >= 4.0 and expp > 0:
                        print(f'[S626/{tf}] ✗n G={G} c={c} k={k_sl} rr={rr}: '
                              f'lift={lift:.2f} n={nb}<n_req={int(n_req)} exp={expp:.2f}', flush=True)
            print(f'[S626/{tf}] G={G} c={c} done (events={n_ev})', flush=True)
            gc.collect()

    out = os.path.join(OUT_DIR, f'{tf}.json')
    with open(out, 'w') as f:
        json.dump({'tf': tf, 'seed': SEED, 'search_half': n, 'mh': mh,
                   'drift_lag': DRIFT_LAG, 'results': results}, f, indent=1)
    print(f'[S626/{tf}] تمام: {len(results)} پیکربندی → {tf}.json', flush=True)


if __name__ == '__main__':
    tfs = sys.argv[1:] or ['H1', 'H2', 'H4']
    for tf in tfs:
        run_tf(tf)
        gc.collect()
