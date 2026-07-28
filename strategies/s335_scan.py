# -*- coding: utf-8 -*-
"""
S335 — اسکنِ سیستماتیکِ پارامتر + فیلترهای تقویتی (منبعِ حقیقتِ احیا)
================================================================================
هدف: با «قانونِ بی‌نهایت بهبود» و «همه‌چیز شناور است»، بهترین ترکیبِ
  (پارامترهای reflex/trendflex/hurst + فیلترهای رژیمِ اضافه + SL/TP غیررند)
  را برای بردنِ RQS+ به بالای ۸۰ روی XAUUSD M5 پیدا کند.

فیلترهای تقویتیِ کاندیدا (از بانک، دستهٔ statistical/volatility/momentum):
  • r2(pR)  > r2Min      — روندِ خطیِ تمیز (ضدِ whipsaw)
  • chop(pC) < chopMax   — رژیمِ روندی (نه رنج)  [chop<38.2 = روند]
  • ssf شیبِ صعودی        — جهتِ روندِ کم‌تأخیر (جایگزینِ EMA خام)
  • laguerre_rsi تأیید    — اسیلاتورِ اشباعِ رژیم‌آگاه

خروجی: جدولِ مرتب‌شدهٔ کاندیداها بر پایهٔ RQS و تعدادِ گیت‌های پاس‌شده.

اجرا: python3 strategies/s335_scan.py
"""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib


def precompute(df, p_rf, p_tf, p_hu, p_r2, p_chop, p_ssf):
    """محاسبهٔ یک‌بارهٔ همهٔ سری‌ها (کش برای سرعت)."""
    return {
        'reflex': ib.reflex(df, period=p_rf).values.astype(float),
        'tflex':  ib.trendflex(df, period=p_tf).values.astype(float),
        'hurst':  ib.hurst(df, p=p_hu).values.astype(float),
        'r2':     ib.r2(df, p=p_r2).values.astype(float),
        'chop':   ib.chop(df, p=p_chop).values.astype(float),
        'ssf':    ib.ssf(df, period=p_ssf).values.astype(float),
    }


def build_signal(S, rf_dip, tf_min, hu_min, r2_min, chop_max, use_ssf):
    reflex, tflex, hurst = S['reflex'], S['tflex'], S['hurst']
    r2, chop, ssf = S['r2'], S['chop'], S['ssf']
    n = len(reflex)
    sig = np.zeros(n, dtype=bool)
    for i in range(2, n):
        if not (np.isfinite(tflex[i]) and tflex[i] > tf_min):
            continue
        if not (np.isfinite(hurst[i]) and hurst[i] > hu_min):
            continue
        if r2_min is not None and not (np.isfinite(r2[i]) and r2[i] > r2_min):
            continue
        if chop_max is not None and not (np.isfinite(chop[i]) and chop[i] < chop_max):
            continue
        if use_ssf and not (np.isfinite(ssf[i]) and np.isfinite(ssf[i - 1]) and ssf[i] > ssf[i - 1]):
            continue
        if not (np.isfinite(reflex[i]) and np.isfinite(reflex[i - 1])):
            continue
        if reflex[i - 1] <= -rf_dip and reflex[i] > reflex[i - 1]:
            sig[i] = True
    return sig


def run_one(df, asset, S, params, sl_pip, tp_pip, max_hold):
    sig = build_signal(S, **params)
    if sig.sum() < 30:
        return None, sig.sum()
    short = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, sig, short, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=asset, max_hold=max_hold, allow_overlap=False)
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip, tp_pip=tp_pip)
    return r, sig.sum()


if __name__ == '__main__':
    asset = 'XAUUSD'
    df = se.load_data('data/XAUUSD_M5.csv')
    print(f"loaded {len(df)} bars XAUUSD M5")

    # فضای اندیکاتور (پارامترهای غیررندِ فیبوناچی/لوکاس — اشتباه #۷)
    P_RF, P_TF, P_HU = 21, 34, 55
    P_R2, P_CHOP, P_SSF = 21, 21, 13
    S = precompute(df, P_RF, P_TF, P_HU, P_R2, P_CHOP, P_SSF)

    # شبکهٔ بهبود: آستانه‌ها + فیلترهای تقویتی + SL/TP غیررند
    grid_rf_dip  = [0.8, 1.2, 1.6]
    grid_tf_min  = [0.2, 0.5, 0.8]
    grid_hu_min  = [0.50, 0.53]
    grid_r2_min  = [None, 0.55, 0.68]
    grid_chop    = [None, 38.2]
    grid_ssf     = [False, True]
    grid_sltp    = [(150, 225, 48), (170, 255, 60), (135, 270, 72)]  # (sl,tp,hold) غیررند، TP≥SL

    results = []
    combos = list(itertools.product(grid_rf_dip, grid_tf_min, grid_hu_min,
                                    grid_r2_min, grid_chop, grid_ssf, grid_sltp))
    print(f"scanning {len(combos)} combos ...")
    for (rf_dip, tf_min, hu_min, r2_min, chop_max, use_ssf, (sl, tp, hold)) in combos:
        params = dict(rf_dip=rf_dip, tf_min=tf_min, hu_min=hu_min,
                      r2_min=r2_min, chop_max=chop_max, use_ssf=use_ssf)
        r, nsig = run_one(df, asset, S, params, sl, tp, hold)
        if r is None:
            continue
        m = r['metrics']; g = r['gates']
        npass = sum(g.values())
        results.append((r['rqs_score'], npass, r['verdict'], m['n_trades'], m['win_rate'],
                        m['profit_factor'], m['max_dd_pct'], m['max_consec_losses'], m['p_value'],
                        rf_dip, tf_min, hu_min, r2_min, chop_max, use_ssf, sl, tp, hold))

    results.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print("\n=== TOP 25 (by gates_passed, then RQS) ===")
    print("RQS  gP verdict  n    WR    PF    DD    MCL  p     | rf tf  hu   r2   chop ssf sl  tp  hold")
    for row in results[:25]:
        (rqsv, npass, verd, n, wr, pf, dd, mcl, pv,
         rf_dip, tf_min, hu_min, r2_min, chop_max, use_ssf, sl, tp, hold) = row
        print(f"{rqsv:4.1f} {npass}/6 {verd:6s} {n:4d} {wr:4.1f} {pf:5.2f} {dd:4.1f} {mcl:3d} {pv:.3f} | "
              f"{rf_dip} {tf_min} {hu_min} {str(r2_min):4s} {str(chop_max):4s} {int(use_ssf)} {sl:3d} {tp:3d} {hold}")
