#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S887 — جستجوی IS (فقط نیمهٔ اول) — شوک خط‌راست (Straight-Line Shock).
پیش‌ثبت: results/S887_PREREG_StraightLineShock_PathC.md (commit 605edaa8).

فضا: θ∈{1.618,2.618} × m∈{1.618,2.618} × b∈{1.0,1.618} × hold∈{21,34,55} × side∈{both,long} = 48
+ کنترل P1: m=0 (شوک بی‌گیت) برای هر (θ,b,hold,side) — ثبت می‌شود، در انتخاب نیست.
usage: python3 strategies/s887_straight_scan.py <TF> [<TF> ...]
"""
import sys, os, json, time, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from strategies.s880_entropy_collapse_scan import wr_of, atr_pip
from strategies.s887_feasibility import build_s887, s887_signals, SUB_TF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'results', '_scan_S887')
os.makedirs(OUT, exist_ok=True)

SPREAD_PIP = 3.3
A_SL = 1.6
TH_LIST = [1.618, 2.618]
M_LIST = [1.618, 2.618]
B_LIST = [1.0, 1.618]
HOLD_LIST = [21, 34, 55]
SIDE_LIST = ['both', 'long']
WARM = 233 + 21 + 5


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


def load_halves(tf):
    d = fd.load_fast('XAUUSD', tf)
    src = d['src']
    assert 'mt5_full' in src, f'E-16 trap: {src}'
    n_all = len(d['close']); half = n_all // 2
    df1 = pd.DataFrame({c: np.asarray(d[c][:half], dtype=np.float64)
                        for c in ('open', 'high', 'low', 'close')})
    df1['time'] = np.asarray(d['time'][:half])
    del d; gc.collect()
    ds = fd.load_fast('XAUUSD', SUB_TF)
    assert 'mt5_full' in ds['src'], f'E-16 trap (sub): {ds["src"]}'
    t_end = float(df1['time'].values[-1]) + fd.TF_MINUTES[tf] * 60
    msk = ds['time'] < t_end
    sub = {k: np.asarray(ds[k][msk], dtype=np.float64) for k in ('time', 'open', 'close')}
    del ds; gc.collect()
    return df1, sub, src, n_all, half


def scan_tf(tf):
    t0 = time.time()
    df1, sub, src, n_all, half = load_halves(tf)
    big = {k: df1[k].values.astype(np.float64) for k in ('time', 'open', 'high', 'low', 'close')}
    pre = build_s887(big, sub, tf)
    apip = atr_pip(big['high'], big['low'], big['close'])
    sl = round(A_SL * apip, 1)
    rng = np.random.default_rng(887)
    out = {'tf': tf, 'src': src, 'sub_tf': SUB_TF, 'n_all': n_all, 'half_idx': half,
           'atr89_median_pip': apip, 'sl_pip': sl, 'configs': [], 'p1_control': []}
    zeros = np.zeros(half, dtype=bool)
    for th in TH_LIST:
        for m in [0.0] + M_LIST:
            ls, ss = s887_signals(pre, th, m)
            ls = ls.copy(); ss = ss.copy(); ls[:WARM] = False; ss[:WARM] = False
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
                        tr = se.simulate_trades(df1, ls, use_ss, sl_pip=sl, tp_pip=tp,
                                                asset='XAUUSD', max_hold=hold,
                                                allow_overlap=False)
                        wr, n = wr_of(tr)
                        if n == 0:
                            continue
                        nl = int((tr['direction'] == 'long').sum())
                        wl = round(100.0 * float((tr[tr['direction'] == 'long']['pnl_pip'] > 0).mean()), 2) if nl else None
                        wsh = round(100.0 * float((tr[tr['direction'] == 'short']['pnl_pip'] > 0).mean()), 2) if n - nl else None
                        uw = uncond_wr(df1, 'long' if nl >= n - nl else 'short', n, sl, tp, hold, rng)
                        lift = round(wr - uw, 2) if (uw is not None and wr is not None) else None
                        rec = {'theta': th, 'm': m, 'side': side, 'b': b, 'hold': hold,
                               'sl_pip': sl, 'tp_pip': tp, 'be_wr': round(be, 2), 'n': n,
                               'wr': round(wr, 2), 'nL_sig': nL, 'nS_sig': nS,
                               'wr_long': wl, 'wr_short': wsh,
                               'uncond_wr': round(uw, 2) if uw is not None else None,
                               'lift': lift,
                               'score': round(lift * np.sqrt(n), 1) if lift is not None else None}
                        (out['p1_control'] if m == 0.0 else out['configs']).append(rec)

    elig = [c for c in out['configs']
            if c['n'] >= 30 and c['lift'] is not None and c['lift'] > 0 and c['wr'] > c['be_wr']]
    out['best'] = max(elig, key=lambda c: c['score']) if elig else None
    # P1: WR گیت‌دار در برابر کنترل بی‌گیت با همان (θ,side,b,hold)
    p1 = []
    for c in out['configs']:
        ctrl = [k for k in out['p1_control'] if k['theta'] == c['theta'] and k['side'] == c['side']
                and k['b'] == c['b'] and k['hold'] == c['hold']]
        if ctrl:
            p1.append(c['wr'] - ctrl[0]['wr'])
    out['p1_gate_minus_control_wr_mean'] = round(float(np.mean(p1)), 2) if p1 else None
    out['p1_gate_wins_frac'] = round(float(np.mean(np.asarray(p1) > 0)), 2) if p1 else None
    out['elapsed_s'] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, f'XAUUSD_{tf}.json'), 'w') as f:
        json.dump(out, f, indent=1)
    b = out['best']
    print(tf, 'configs=', len(out['configs']),
          'best=', (f"th={b['theta']} m={b['m']} side={b['side']} n={b['n']} wr={b['wr']} lift={b['lift']} score={b['score']}" if b else None),
          f"P1: dWR={out['p1_gate_minus_control_wr_mean']} wins={out['p1_gate_wins_frac']}",
          f"({out['elapsed_s']}s)", flush=True)


if __name__ == '__main__':
    for tf in sys.argv[1:]:
        scan_tf(tf)
