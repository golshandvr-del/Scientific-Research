#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S883 — جستجوی IS (فقط نیمهٔ اول) — شکست فشردگی NR.

پیش‌ثبت: results/S883_PREREG_NRBreakout_PathC.md (commit bb9ec536)
فضا: m∈{5,8,13} × kc∈{2,3} × b∈{1.0,1.5} × hold∈{34,55,89} = 36
usage: python3 strategies/s883_nr_breakout_scan.py <TF> [<TF> ...]
"""
import sys, os, json, time, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from strategies.s880_entropy_collapse_scan import wr_of, atr_pip
from strategies.s883_feasibility import breakout_signals

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_scan_S883')
os.makedirs(OUT, exist_ok=True)

SPREAD_PIP = 3.3
A_SL = 1.6
M_LIST = [5, 8, 13]
KC_LIST = [2, 3]
B_LIST = [1.0, 1.5]
HOLD_LIST = [34, 55, 89]


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
    rng = np.random.default_rng(883)

    out = {'tf': tf, 'src': src, 'n_all': n_all, 'half_idx': half,
           'atr89_median_pip': apip, 'sl_pip': sl, 'configs': []}

    for m in M_LIST:
        for kc in KC_LIST:
            ls, ss = breakout_signals(high, low, close, m, kc)
            nL, nS = int(ls.sum()), int(ss.sum())
            if nL + nS < 10:
                continue
            for b in B_LIST:
                tp = round(b * sl, 1)
                be = 100.0 * (sl + SPREAD_PIP) / (sl + tp)
                for hold in HOLD_LIST:
                    tr = se.simulate_trades(df1, ls, ss, sl_pip=sl, tp_pip=tp,
                                            asset='XAUUSD', max_hold=hold,
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
                        {'m': m, 'kc': kc, 'b': b, 'hold': hold,
                         'sl_pip': sl, 'tp_pip': tp, 'be_wr': round(be, 2),
                         'n': n, 'wr': round(wr, 2), 'nL_sig': nL, 'nS_sig': nS,
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
          'best=', (f"m={b['m']} kc={b['kc']} n={b['n']} wr={b['wr']} lift={b['lift']} score={b['score']}" if b else None),
          f"({out['elapsed_s']}s)", flush=True)


if __name__ == '__main__':
    for tf in sys.argv[1:]:
        scan_tf(tf)
