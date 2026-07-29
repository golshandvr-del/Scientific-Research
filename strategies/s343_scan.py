# -*- coding: utf-8 -*-
"""
S343 scanner — جاروی فضای پارامترِ measured-move fade روی یک فایلِ داده.
اعداد **غیررند و per-TF** (اشتباهِ رایجِ #۷/#۶). خروجی: بهترین ترکیب‌ها بر پایهٔ RQS+.
اجرا:  PYTHONPATH=. python3 strategies/s343_scan.py data/XAUUSD_M5.csv XAUUSD
"""
import sys
import itertools
import numpy as np
from engine import scalp_engine as se
from engine import rqs
from strategies.s343_brooks_ttr_mmfade import build_signals


def scan(path, asset, tp_grid, sl_grid, max_hold_grid,
         N_grid=(13, 21, 34), smallMult_grid=(0.5, 0.7, 0.9),
         k_grid=(0.6, 1.0, 1.5), climax_grid=(0.8, 1.2, 1.6),
         gap_mode='N', side_grid=('both', 'short', 'long'),
         atrLen=21, top=15, min_trades=30):
    df = se.load_data(path)
    results = []
    combos = list(itertools.product(N_grid, smallMult_grid, k_grid, climax_grid, side_grid))
    for (N, sm, k, cx, side) in combos:
        gap = N if gap_mode == 'N' else int(gap_mode)
        ls, ss = build_signals(df, N=N, atrLen=atrLen, smallMult=sm, k=k,
                               climaxMult=cx, gap=gap, side=side)
        if int(ls.sum() + ss.sum()) < min_trades:
            continue
        for tp, sl, mh in itertools.product(tp_grid, sl_grid, max_hold_grid):
            trades = se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp,
                                        asset=asset, max_hold=mh, allow_overlap=False)
            if len(trades) < min_trades:
                continue
            trades['tp_pip'] = tp
            r = rqs.compute_rqs(trades, asset, sl_pip=sl, tp_pip=tp)
            m = r['metrics']
            results.append(dict(N=N, sm=sm, k=k, cx=cx, side=side, tp=tp, sl=sl,
                                mh=mh, rqs=r['rqs_score'], verdict=r['verdict'],
                                n=m.get('n_trades', 0), wr=m.get('win_rate', 0),
                                pf=m.get('profit_factor', 0), dd=m.get('max_dd_pct', 0),
                                mcl=m.get('max_consec_losses', 0), p=m.get('p_value', 1),
                                net=m.get('net_profit', 0)))
    results.sort(key=lambda x: (x['rqs'], x['net']), reverse=True)
    return results


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'data/XAUUSD_M5.csv'
    asset = sys.argv[2] if len(sys.argv) > 2 else 'XAUUSD'
    # گریدِ TP/SL غیررند، متناسب با طلا M5 (pip موتور = 0.10$)
    tp_grid = (140, 200, 280, 380)
    sl_grid = (90, 130, 180)
    mh_grid = (24, 48, 96)
    res = scan(path, asset, tp_grid, sl_grid, mh_grid)
    print(f"=== S343 scan: {path} ({asset}) — {len(res)} valid combos ===")
    print(f"{'RQS':>5} {'verd':>6} {'N':>3} {'sm':>4} {'k':>4} {'cx':>4} {'side':>5} "
          f"{'tp':>4} {'sl':>4} {'mh':>3} {'n':>4} {'WR':>5} {'PF':>5} {'DD':>5} {'MCL':>3} {'p':>5} {'net':>10}")
    for x in res[:20]:
        print(f"{x['rqs']:5.1f} {x['verdict']:>6} {x['N']:3d} {x['sm']:4.1f} {x['k']:4.1f} "
              f"{x['cx']:4.1f} {x['side']:>5} {x['tp']:4d} {x['sl']:4d} {x['mh']:3d} {x['n']:4d} "
              f"{x['wr']:5.1f} {x['pf']:5.2f} {x['dd']:5.1f} {x['mcl']:3d} {x['p']:5.3f} {x['net']:10.0f}")
