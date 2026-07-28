# -*- coding: utf-8 -*-
"""
S335 — runner مقاوم‌به‌ریست: همهٔ (asset × TF) را ترتیبی اسکن می‌کند و نتیجهٔ
هر بلوک را بلافاصله (flush) در strategies/s335_results.txt می‌نویسد.
اجرا در پس‌زمینه:  nohup python3 strategies/s335_runner.py &
"""
import sys, os, itertools, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from engine import scalp_engine as se
from engine import rqs
import strategies.s335_mtf as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 's335_results.txt')

# لیستِ کارهای باقی‌مانده (M5/M15 قبلاً تأیید شده‌اند؛ برای بازتولید کامل هم می‌آیند)
JOBS = [
    ('XAUUSD', 'M5'), ('XAUUSD', 'M15'), ('XAUUSD', 'M30'),
    ('XAUUSD', 'H1'), ('XAUUSD', 'H4'),
    ('EURUSD', 'M5'), ('EURUSD', 'M15'), ('EURUSD', 'M30'),
    ('EURUSD', 'H1'), ('EURUSD', 'H4'),
]


def scan_block(asset, tf, fh):
    fpath = f'data/{asset}_{tf}.csv'
    if not os.path.exists(fpath):
        fh.write(f"\n[skip] {fpath} not found\n"); fh.flush(); return
    t0 = time.time()
    df = se.load_data(fpath)
    S = M.precompute(df)
    sltp = (M.SLTP_BY_TF_EUR if asset == 'EURUSD' else M.SLTP_BY_TF)[tf]

    grid_trig   = ['dip_turn', 'zero_up']
    grid_rf_dip = [0.6, 0.8, 1.0]
    grid_tf_min = [0.2, 0.5]
    grid_hu_min = [0.50, 0.53]
    grid_r2_min = [None, 0.50, 0.55]
    grid_chop   = [None, 38.2]

    results = []
    combos = list(itertools.product(grid_trig, grid_rf_dip, grid_tf_min, grid_hu_min,
                                    grid_r2_min, grid_chop, sltp))
    for (trig, rf_dip, tf_min, hu_min, r2_min, chop_max, (sl, tp, hold)) in combos:
        sig = M.build_signal(S, trig, rf_dip, tf_min, hu_min, r2_min, chop_max)
        if sig.sum() < 30:
            continue
        short = np.zeros(len(df), dtype=bool)
        trades = se.simulate_trades(df, sig, short, sl_pip=sl, tp_pip=tp,
                                    asset=asset, max_hold=hold, allow_overlap=False)
        r = rqs.compute_rqs(trades, asset, sl_pip=sl, tp_pip=tp)
        m = r['metrics']; g = r['gates']; npass = sum(g.values())
        results.append((r['rqs_score'], npass, r['verdict'], m['n_trades'], m['win_rate'],
                        m['profit_factor'], m['max_dd_pct'], m['max_consec_losses'], m['p_value'],
                        trig, rf_dip, tf_min, hu_min, r2_min, chop_max, sl, tp, hold))

    accepts = [r for r in results if r[1] == 6]
    accepts.sort(key=lambda x: (x[3], x[0]), reverse=True)  # n سپس RQS
    dt = time.time() - t0
    fh.write(f"\n===== {asset} {tf} — {len(accepts)} ACCEPT / {len(results)} tested "
             f"(bars={len(df)}, {dt:.0f}s) =====\n")
    fh.write("RQS  gP  n    WR    PF    DD   MCL  p     | trig     rf  tf  hu   r2   chop  sl   tp   hold\n")
    show = accepts[:12] if accepts else sorted([r for r in results if r[1] == 5],
                                               key=lambda x: x[0], reverse=True)[:8]
    tag = "" if accepts else "  (no ACCEPT — best 5/6 shown)"
    fh.write(f"top rows{tag}:\n")
    for row in show:
        (rqsv, npass, verd, n, wr, pf, dd, mcl, pv,
         trig, rf_dip, tf_min, hu_min, r2_min, chop_max, sl, tp, hold) = row
        fh.write(f"{rqsv:4.1f} {npass}/6 {n:4d} {wr:4.1f} {pf:5.2f} {dd:4.1f} {mcl:3d} {pv:.3f} | "
                 f"{trig:8s} {rf_dip} {tf_min} {hu_min} {str(r2_min):4s} {str(chop_max):4s} "
                 f"{sl:4d} {tp:4d} {hold}\n")
    fh.flush()
    os.fsync(fh.fileno())


if __name__ == '__main__':
    with open(OUT, 'w') as fh:
        fh.write("S335 Reflex-TrendFlex Cycle-Turn — MTF runner results\n")
        fh.write("=" * 70 + "\n")
        fh.flush()
        for asset, tf in JOBS:
            try:
                scan_block(asset, tf, fh)
            except Exception as e:
                fh.write(f"\n[ERROR] {asset} {tf}: {e}\n"); fh.flush()
        fh.write("\n=== DONE ALL JOBS ===\n"); fh.flush()
