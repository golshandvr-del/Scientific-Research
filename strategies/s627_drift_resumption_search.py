#!/usr/bin/env python3
"""
S627 — Drift-Resumption Cross LONG — XAUUSD M30/H1/H2
PREREG: results/S627_PREREG_XAUUSD_drift_resumption_cross_long_pathC.md (commit 2682f826)
Path C: search FIRST HALF ONLY. Holdout [n/2, n) never touched here.
Event: drift_slow(360)>0 AND drift_fast(90) crosses from <=0 to >0. Entry open[i]+slip.
Null: random entries in the double-drift-positive space, same frozen geometry
      (S612 law: null wears the winner's geometry; S346 law: drift beta is not skill).
SEED=20260819
"""
import sys, os, json, gc, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import indicator_bank as ib
from engine import scalp_engine as se

SEED = 20260819
FAST, SLOW = 90, 360          # frozen: 90 from S950 ACCEPT; 360 = 4x90 a-priori
KSLS = [1.5, 2.0]
RRS = [1.0, 1.5]
MAX_HOLD = {'M30': 128, 'H1': 96, 'H2': 64}
N_BASE = 20000

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', '_scan_S627')
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

    cl = df['close'].values
    n = len(df)
    mh = MAX_HOLD[tf]
    print(f'[S627/{tf}] src={src} n_full={n_full} search_half={n} mh={mh}', flush=True)

    atr = ib.atr_s(df, 100)  # pip units

    # causal drifts evaluated at bar i using info up to close[i-1]
    drift_fast = np.full(n, np.nan)
    drift_fast[FAST + 1:] = cl[FAST:n - 1] - cl[:n - 1 - FAST]
    drift_slow = np.full(n, np.nan)
    drift_slow[SLOW + 1:] = cl[SLOW:n - 1] - cl[:n - 1 - SLOW]

    valid = (~np.isnan(atr)) & (atr > 0) & (~np.isnan(drift_slow))
    valid[:SLOW + 2] = False
    valid[n - mh - 2:] = False

    # EVENT: slow>0 AND fast crosses <=0 -> >0
    prev_fast = np.full(n, np.nan)
    prev_fast[1:] = drift_fast[:-1]
    ev = valid & (drift_slow > 0) & (drift_fast > 0) & (prev_fast <= 0)
    n_ev = int(ev.sum())

    # NULL SPACE: double-drift-positive (post-event regime), same validity
    null_space = valid & (drift_slow > 0) & (drift_fast > 0)
    pool = np.where(null_space)[0]
    print(f'[S627/{tf}] events={n_ev} | null-space bars={len(pool)}', flush=True)
    if n_ev < 5 or len(pool) < 100:
        print(f'[S627/{tf}] SKIP: insufficient events/null space', flush=True)
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
            print(f'[S627/{tf}] k={k_sl} rr={rr}: wr={wr:.2f} ref={ref_wr:.2f} '
                  f'lift={lift:+.2f} n={nb} n_req={row["n_req"]} exp={expp:+.2f} {tag}', flush=True)

    out = os.path.join(OUT_DIR, f'{tf}.json')
    with open(out, 'w') as f:
        json.dump({'tf': tf, 'seed': SEED, 'search_half': n, 'mh': mh,
                   'fast': FAST, 'slow': SLOW, 'n_events': n_ev,
                   'results': results}, f, indent=1)
    print(f'[S627/{tf}] تمام ({time.time()-t0:.0f}s) → {tf}.json', flush=True)


if __name__ == '__main__':
    for tf in (sys.argv[1:] or ['H1', 'H2', 'M30']):
        run_tf(tf)
        gc.collect()
