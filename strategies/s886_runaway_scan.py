#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S886 — جستجوی IS (فقط نیمهٔ اول) — شکاف فرار (Runaway Overlap Gap).
پیش‌ثبت: results/S886_PREREG_RunawayGap_PathC.md (commit f289aa87).

فضا: θ∈{0.236,0.382} × gate∈{none,drift90} × b∈{1.0,1.618} × hold∈{21,34,55} × side∈{both,long} = 48
usage: python3 strategies/s886_runaway_scan.py <TF> [<TF> ...]
"""
import sys, os, json, time, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from strategies.s880_entropy_collapse_scan import wr_of, atr_pip
from strategies.s886_feasibility import runaway_signals

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_scan_S886')
os.makedirs(OUT, exist_ok=True)

SPREAD_PIP = 3.3
A_SL = 1.6
TH_LIST = [0.236, 0.382]
GATE_LIST = ["none", "drift90"]
DRIFT_N = 90
B_LIST = [1.0, 1.618]
HOLD_LIST = [21, 34, 55]
SIDE_LIST = ['both', 'long']


def uncond_wr(df, side, n_sig, sl, tp, hold, rng, draws=3):
    n = len(df)
    lo, hi = 200, n - hold - 2
    if hi <= lo:
        return None
    pool = np.arange(lo, hi)
    z = np.zeros(n, dtype=bool)
    ws = []
    for _ in range(draws):
        pick = rng.choice(pool, size=min(max(n_sig, 50), len(pool)), replace=False)
        s = np.zeros(n, dtype=bool); s[pick] = True
        t = se.simulate_trades(df, s if side == 'long' else z,
                               z if side == 'long' else s,
                               sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                               max_hold=hold, allow_overlap=False)
        w, m = wr_of(t)
        if w is not None:
            ws.append(w)
    return float(np.mean(ws)) if ws else None


def scan_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    src = d['src']
    assert 'mt5_full' in src, f'E-16 trap: {src}'
    n_all = len(d['close'])
    half = n_all // 2
    df1 = pd.DataFrame({c: np.asarray(d[c][:half], dtype=np.float64)
                        for c in ('open', 'high', 'low', 'close')})
    df1['time'] = np.asarray(d['time'][:half])
    del d; gc.collect()

    high = df1['high'].values; low = df1['low'].values
    close = df1['close'].values
    apip = atr_pip(high, low, close)
    sl = round(A_SL * apip, 1)
    rng = np.random.default_rng(886)

    out = {'tf': tf, 'src': src, 'n_all': n_all, 'half_idx': half,
           'atr89_median_pip': apip, 'sl_pip': sl, 'configs': []}

    zeros = np.zeros(half, dtype=bool)
    tsec = df1['time'].values.astype(np.float64)
    warm = DRIFT_N + 5
    up = np.zeros(half, dtype=bool); dn = np.zeros(half, dtype=bool)
    # drift علّی: close[t-1] > close[t-1-90] (سیگنال روی کندل t)
    up[DRIFT_N + 1:] = close[DRIFT_N:-1] > close[:-DRIFT_N - 1]
    dn[DRIFT_N + 1:] = close[DRIFT_N:-1] < close[:-DRIFT_N - 1]
    for th in TH_LIST:
        ls0, ss0 = runaway_signals(tsec, high, low, close, th, fd.TF_MINUTES[tf])
        ls0[:warm] = False; ss0[:warm] = False
        for gate in GATE_LIST:
            ls = ls0 & up if gate == 'drift90' else ls0
            ss = ss0 & dn if gate == 'drift90' else ss0
            nL, nS = int(ls.sum()), int(ss.sum())
            if nL + nS < 10:
                continue
            for side in SIDE_LIST:
                use_ss = ss if side == 'both' else zeros
                if side == 'long' and nL < 10:
                    continue
                for b in B_LIST:
                    tp = round(b * sl, 1)
                    be = 100.0 * (sl + SPREAD_PIP) / (sl + tp)
                    for hold in HOLD_LIST:
                        tr = se.simulate_trades(df1, ls, use_ss, sl_pip=sl,
                                                tp_pip=tp, asset='XAUUSD',
                                                max_hold=hold,
                                                allow_overlap=False)
                        wr, n = wr_of(tr)
                        if n == 0:
                            continue
                        nl = int((tr['direction'] == 'long').sum())
                        wl = round(100.0 * float((tr[tr['direction'] == 'long']['pnl_pip'] > 0).mean()), 2) if nl else None
                        wsh = round(100.0 * float((tr[tr['direction'] == 'short']['pnl_pip'] > 0).mean()), 2) if n - nl else None
                        uw = uncond_wr(df1, 'long' if nl >= n - nl else 'short',
                                       n, sl, tp, hold, rng)
                        lift = round(wr - uw, 2) if (uw is not None and wr is not None) else None
                        out['configs'].append(
                            {'theta': th, 'gate': gate, 'side': side, 'b': b,
                             'hold': hold, 'sl_pip': sl, 'tp_pip': tp,
                             'be_wr': round(be, 2), 'n': n,
                             'wr': round(wr, 2), 'nL_sig': nL, 'nS_sig': nS,
                             'wr_long': wl, 'wr_short': wsh,
                             'uncond_wr': round(uw, 2) if uw is not None else None,
                             'lift': lift,
                             'score': round(lift * np.sqrt(n), 1) if lift is not None else None})

    elig = [c for c in out['configs']
            if c['n'] >= 30 and c['lift'] is not None and c['lift'] > 0
            and c['wr'] > c['be_wr']]
    out['best'] = max(elig, key=lambda c: c['score']) if elig else None
    out['elapsed_s'] = round(time.time() - t0, 1)

    with open(os.path.join(OUT, f'XAUUSD_{tf}.json'), 'w') as f:
        json.dump(out, f, indent=1)
    b = out['best']
    print(tf, 'configs=', len(out['configs']),
          'best=', (f"th={b['theta']} gate={b['gate']} side={b['side']} n={b['n']} wr={b['wr']} lift={b['lift']} score={b['score']}" if b else None),
          f"({out['elapsed_s']}s)", flush=True)


if __name__ == '__main__':
    for tf in sys.argv[1:]:
        scan_tf(tf)
