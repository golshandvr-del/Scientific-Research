# -*- coding: utf-8 -*-
"""
S332 — اسکنِ سریع از روی کش (سیگنال از .npz خوانده می‌شود؛ فقط RQS+ اجرا می‌شود)
================================================================================
اجرا:  python3 strategies/s332_cachedscan.py --sym EURUSD --tf M30
"""
import os
import sys
import argparse
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import strategies.s332_squeeze_rqs_revival as S
import strategies.s332_cache_signals as C

MAXHOLD = {'M5': 288, 'M15': 96, 'M30': 64, 'H1': 48, 'H4': 24}


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def scan(sym, tf, sqz=0.25, brk=6):
    p = C.cache_path(sym, tf, sqz, brk)
    if not os.path.exists(p):
        print(f"no cache; run: python3 strategies/s332_cache_signals.py --sym {sym} --tf {tf}")
        return
    z = np.load(p)
    sig = z['sig']; adx_ = z['adx']; pdi = z['pdi']; mdi = z['mdi']
    r14 = z['rsi']; e20 = z['e20']; e50 = z['e50']; e100 = z['e100']; atr_ = z['atr']
    df = S.load_tf(sym, tf)
    mh = MAXHOLD[tf]
    pip = S.se.ASSETS[sym]['pip']

    def clean(m):
        return np.nan_to_num(m.astype(float), nan=0.0).astype(bool)

    filts = {
        'none':                 np.ones(len(df), dtype=bool),
        'adx>22&pdi>mdi':       clean((adx_ > 22) & (pdi > mdi)),
        'adx>25&pdi>mdi':       clean((adx_ > 25) & (pdi > mdi)),
        'adx>30&pdi>mdi':       clean((adx_ > 30) & (pdi > mdi)),
        'adx>25&pdi>mdi&rsi<72': clean((adx_ > 25) & (pdi > mdi) & (r14 < 72)),
        'adx>28&pdi-mdi>8':     clean((adx_ > 28) & ((pdi - mdi) > 8)),
        'adx>25&e20>e50':       clean((adx_ > 25) & (e20 > e50) & (pdi > mdi)),
    }
    print(f"== {sym} {tf} | signals={int(sig.sum())} mh={mh} ==")
    print(f"{'filt':24s} {'geom':>12s} | {'WR':>5s} {'net':>8s} {'PF':>5s} {'DD':>5s} {'MCL':>3s} {'n':>4s} | gates RQS")

    fixed = [(500, 350), (600, 400), (450, 300), (350, 220)]
    atrm = [(5.0, 3.5), (4.0, 2.8), (6.0, 4.0)]
    rows = []
    for fn, fm in filts.items():
        geoms = [('fix', tp, sl) for tp, sl in fixed] + [('atr', kt, ks) for kt, ks in atrm]
        for kind, a1, a2 in geoms:
            if kind == 'fix':
                tp_arg, sl_arg, label = a1, a2, f"{a1}/{a2}"
            else:
                tp_arg = np.nan_to_num(a1 * atr_ / pip, nan=0.0)
                sl_arg = np.where(np.nan_to_num(a2 * atr_ / pip, nan=0.0) < 1, 1e9, a2 * atr_ / pip)
                label = f"ATR{a1}/{a2}"
            try:
                r, tr = S.evaluate(df, sym, sig, sl_pip=sl_arg, tp_pip=tp_arg, max_hold=mh, filt=fm)
            except Exception:
                continue
            m = r['metrics']
            if m.get('n_trades', 0) < 30:
                continue
            g = gates_str(r); ng = g.count('1')
            rows.append((r['passed'], ng, m['net_profit'], fn, label, m['win_rate'],
                         m['profit_factor'], m['max_dd_pct'], m['max_consec_losses'],
                         m['n_trades'], g, r['rqs_score']))
            if r['passed'] or ng >= 5:
                print(f"{fn:24s} {label:>12s} | {m['win_rate']:>5.1f} {m['net_profit']:>8.0f} "
                      f"{m['profit_factor']:>5.2f} {m['max_dd_pct']:>5.1f} {m['max_consec_losses']:>3d} "
                      f"{m['n_trades']:>4d} | {g} {r['rqs_score']:.1f}{'  PASS' if r['passed'] else ''}")

    rows.sort(key=lambda x: (-int(x[0]), -x[1], -x[2]))
    print(f"\n-- top 6 --")
    for b in rows[:6]:
        ok, ng, net, fn, geom, wr, pf, dd, mcl, n, g, rqsv = b
        print(f"  {'PASS' if ok else '    '} ng={ng} RQS={rqsv:5.1f} net={net:>8.0f} {fn:24s} {geom:>12s} "
              f"WR={wr:.1f} PF={pf:.2f} DD={dd:.1f} MCL={mcl} n={n} {g}")
    npass = sum(1 for r in rows if r[0])
    print(f"== {sym} {tf}: {npass} PASS / {len(rows)} valid ==")
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', default='EURUSD')
    ap.add_argument('--tf', default='M30')
    ap.add_argument('--sqz', type=float, default=0.25)
    ap.add_argument('--brk', type=int, default=6)
    a = ap.parse_args()
    scan(a.sym, a.tf, a.sqz, a.brk)
