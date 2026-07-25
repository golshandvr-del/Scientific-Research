# -*- coding: utf-8 -*-
"""
S321h — احیای S52 MA-Ribbon روی XAUUSD M30: راهکارِ «دوطرفهٔ متقارن» (B7) — کلیدِ G4
================================================================================
کشفِ تعیین‌کنندهٔ S321g→h (نگاشتِ walk-forward به سمتِ معامله):
  LONG  only: wf=[260, -213, 134, 1729]   ← W2 (رنجِ ۲۰۱۶–۲۰۲۰) منفی
  SHORT only: wf=[ 25,  579, 646, -509]   ← دقیقاً مکملِ long؛ در همان رنج قوی سود می‌دهد
  BOTH      : wf=[325,  479, 399, 1254] allpos=True  ← هر ۴ پنجره مثبت! G4 حل شد.
  BOTH+slope0.05: wf=[570,301,504,122] allpos=True, WR=61.4  ← G0 و G4 هم‌زمان.

منطقِ علمی: ribbon-pullback یک ستاپِ «روند-همسو»ی متقارن است. در رژیمِ روندیِ صعودی
(۲۰۲۳–۲۰۲۶) long غالب است؛ در رنج/روندِ نزولیِ ۲۰۱۶–۲۰۲۳ short لبه دارد. ترکیبِ
دوطرفه ریسکِ رژیم را «هج» می‌کند و پایداریِ walk-forward می‌سازد — بدونِ هیچ فیلترِ
مصنوعیِ زمان‌محور (رعایتِ اشتباهِ رایج #1).

بهبودها: B5 شیبِ ریبون + B7 دوطرفهٔ متقارن + RR/be/max_hold شناور.
اجرا: python3 strategies/s321h_ribbon_m30_bothsides.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import itertools

from engine import scalp_engine as se
from engine import rqs
import strategies.s321f_ribbon_m30_slopefilter as S   # build_features + make_signals (با slope)


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
    slope_grid = [0.03, 0.05, 0.08, 0.12]
    sl_grid = [2.3, 2.6, 3.0]
    tp_grid = [2.4, 2.6, 3.0]
    be_grid = [0.0, 0.6, 1.0]
    mh_grid = [40, 64]
    res = []
    t0 = time.time()
    for slope_min, sl_mult, tp_mult, be_mult, mh in itertools.product(
            slope_grid, sl_grid, tp_grid, be_grid, mh_grid):
        cfg = dict(base); cfg.update(slope_min=slope_min, sl_mult=sl_mult,
                                     tp_mult=tp_mult, be_mult=be_mult, max_hold=mh)
        ls, ss, sl, tp = S.make_signals(feats, cfg, side)
        be = None if be_mult <= 0 else be_mult * atr_med
        tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh,
                                allow_overlap=False, be_trigger_pip=be)
        n, wr, pf, net = lite_stats(tr)
        if n >= rqs.N_FLOOR and wr >= 59 and pf >= 1.28:
            med_tp = float(np.median(tp[ls | ss]))
            r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
            res.append((r['rqs_score'], r['passed'], cfg, r['metrics'], r['gates']))
    res.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f"candidates WR>=59 & PF>=1.28: {len(res)}  ({time.time()-t0:.0f}s)")
    print("=" * 118)
    for score, passed, cfg, m, g in res[:20]:
        gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f"RQS={score:5.1f} {'PASS' if passed else 'FAIL'} G[{gl}] "
              f"n={m['n_trades']:3d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} wf={m['wf_nets']} | "
              f"slope{cfg['slope_min']} sl{cfg['sl_mult']}tp{cfg['tp_mult']} "
              f"be{cfg['be_mult']} mh{cfg['max_hold']}")
    if not res:
        print("NONE reached WR>=59 & PF>=1.28")


if __name__ == '__main__':
    main()
