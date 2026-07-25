# -*- coding: utf-8 -*-
"""
S321i — تثبیتِ احیای MA-Ribbon روی XAUUSD M30 بالای RQS=۸۰ (ریزتنظیمِ غیر-رند)
================================================================================
S321h به RQS=۷۹.۸ (PASS، همهٔ ۶ گیت) رسید با slope0.05 sl2.6 tp2.6 mh40 دوطرفه.
۷۹.۸ مرزیِ ۸۰ است؛ طبق «قانونِ بی‌نهایتِ بهبود» و اجتنابِ از اعدادِ رند (اشتباه #7)،
اینجا با گام‌های ریزِ غیر-رند حولِ نقطهٔ برنده جارو می‌زنیم تا حاشیهٔ امنِ ≥۸۰ و
پایداری در همسایگی (نه تک‌نقطهٔ overfit) به‌دست آید.
اجرا: python3 strategies/s321i_ribbon_m30_refine.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import itertools

from engine import scalp_engine as se
from engine import rqs
import strategies.s321f_ribbon_m30_slopefilter as S


def lite_stats(trades):
    n = len(trades)
    if n == 0:
        return 0, 0, 0, 0
    pnl = trades['pnl_pip'].values
    wr = (pnl > 0).sum() / n * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 999
    return n, wr, pf, pnl.sum()


def main():
    asset = 'XAUUSD'; tf = 'M30'; side = 'both'
    pip = se.ASSETS[asset]['pip']
    df = se.load_data(f'data/{asset}_{tf}.csv')
    print(f"[{asset} {tf}] rows={len(df)} side={side}")
    feats = S.build_features(df, pip)
    atr_med = float(np.nanmedian(feats['atr_pip']))
    base = dict(ord_thr=0.40, wz_gate=0.15, pull_min=0.05, pull_max=0.82,
                rsi_min=45, rsi_max=85)
    # گام‌های ریزِ غیر-رند حولِ نقطهٔ برنده
    slope_grid = [0.040, 0.048, 0.055, 0.062, 0.070]
    sl_grid = [2.45, 2.55, 2.60, 2.70, 2.80]
    tp_grid = [2.45, 2.55, 2.60, 2.70]
    mh_grid = [36, 40, 48]
    res = []
    t0 = time.time()
    for slope_min, sl_mult, tp_mult, mh in itertools.product(
            slope_grid, sl_grid, tp_grid, mh_grid):
        cfg = dict(base); cfg.update(slope_min=slope_min, sl_mult=sl_mult,
                                     tp_mult=tp_mult, be_mult=0.0, max_hold=mh)
        ls, ss, sl, tp = S.make_signals(feats, cfg, side)
        tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh,
                                allow_overlap=False)
        n, wr, pf, net = lite_stats(tr)
        if n >= rqs.N_FLOOR and wr >= 60 and pf >= 1.3:
            med_tp = float(np.median(tp[ls | ss]))
            r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
            if r['passed']:
                res.append((r['rqs_score'], cfg, r['metrics'], r['gates']))
    res.sort(key=lambda x: x[0], reverse=True)
    print(f"PASSING candidates (all 6 gates): {len(res)}  ({time.time()-t0:.0f}s)")
    print("=" * 118)
    for score, cfg, m, g in res[:20]:
        print(f"RQS={score:5.1f} n={m['n_trades']:3d} WR={m['win_rate']:4.1f} "
              f"PF={m['profit_factor']:.2f} DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} "
              f"p={m['p_value']:.3f} net={m['net_profit']:.0f} wf={m['wf_nets']} | "
              f"slope{cfg['slope_min']} sl{cfg['sl_mult']}tp{cfg['tp_mult']} mh{cfg['max_hold']}")
    if not res:
        print("NONE fully passed — fallback to S321h config (RQS 79.8)")


if __name__ == '__main__':
    main()
