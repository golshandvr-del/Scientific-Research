# -*- coding: utf-8 -*-
"""
S335 — اسکنِ ریزِ حولِ نقطهٔ برندهٔ M5 (استحکام‌سنجی)
================================================================================
نقطهٔ برنده از s335_scan.py:
  rf_dip=0.8, hu_min=0.53, r2_min=0.55, chop_max=38.2, ssf=0, SL=170/TP=255/hold=60
  → RQS=90.4 (6/6) اما n=35 (نزدیکِ کفِ G0=30 → ریسکِ نمونهٔ کوچک).

این اسکن حولِ همان نقطه، آستانه‌ها/SL/TP را کمی می‌لرزاند تا ترکیبی با n بالاتر
(نمونهٔ مستحکم‌تر) و RQS≥80 بیابد، و حساسیتِ نتیجه را بسنجد (پایداریِ لبه).
"""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib
from s335_scan import precompute, build_signal, run_one  # type: ignore

if __name__ == '__main__':
    asset = 'XAUUSD'
    df = se.load_data('data/XAUUSD_M5.csv')
    print(f"loaded {len(df)} bars XAUUSD M5")

    # کش با پارامترهای اندیکاتورِ ثابت (همان اسکنِ اصلی)
    S = precompute(df, p_rf=21, p_tf=34, p_hu=55, p_r2=21, p_chop=21, p_ssf=13)

    grid_rf_dip = [0.6, 0.8, 1.0]
    grid_hu_min = [0.50, 0.52, 0.53]
    grid_r2_min = [0.45, 0.50, 0.55]
    grid_chop   = [38.2, 45.0, None]
    grid_sltp   = [(170, 255, 60), (160, 260, 64), (180, 270, 72), (150, 240, 55)]

    results = []
    combos = list(itertools.product(grid_rf_dip, grid_hu_min, grid_r2_min, grid_chop, grid_sltp))
    print(f"scanning {len(combos)} refine combos ...")
    for (rf_dip, hu_min, r2_min, chop_max, (sl, tp, hold)) in combos:
        params = dict(rf_dip=rf_dip, tf_min=0.2, hu_min=hu_min,
                      r2_min=r2_min, chop_max=chop_max, use_ssf=False)
        r, nsig = run_one(df, asset, S, params, sl, tp, hold)
        if r is None:
            continue
        m = r['metrics']; g = r['gates']; npass = sum(g.values())
        results.append((r['rqs_score'], npass, r['verdict'], m['n_trades'], m['win_rate'],
                        m['profit_factor'], m['max_dd_pct'], m['max_consec_losses'], m['p_value'],
                        rf_dip, hu_min, r2_min, chop_max, sl, tp, hold))

    # مرتب‌سازی: اول ACCEPTها، بعد n بالاتر (استحکام)، بعد RQS
    accepts = [r for r in results if r[1] == 6]
    accepts.sort(key=lambda x: (x[3], x[0]), reverse=True)  # n سپس RQS
    print(f"\n=== {len(accepts)} ACCEPT combos (6/6) — sorted by n then RQS ===")
    print("RQS  gP  n    WR    PF    DD   MCL  p     | rf   hu   r2   chop  sl  tp  hold")
    for row in accepts[:20]:
        (rqsv, npass, verd, n, wr, pf, dd, mcl, pv,
         rf_dip, hu_min, r2_min, chop_max, sl, tp, hold) = row
        print(f"{rqsv:4.1f} {npass}/6 {n:4d} {wr:4.1f} {pf:5.2f} {dd:4.1f} {mcl:3d} {pv:.3f} | "
              f"{rf_dip} {hu_min} {r2_min} {str(chop_max):4s} {sl:3d} {tp:3d} {hold}")
    if not accepts:
        print("no 6/6 accepts in refine grid; showing best 5/6:")
        fives = sorted([r for r in results if r[1] == 5], key=lambda x: x[0], reverse=True)
        for row in fives[:10]:
            print(row)
