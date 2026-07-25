# -*- coding: utf-8 -*-
"""
S321j — اعتبارسنجیِ مولتی-تایم‌فریم و دو-جفت‌ارزِ config نهاییِ MA-Ribbon (S321)
================================================================================
config نهاییِ برنده (از S321i، RQS=۸۸.۲ روی XAUUSD M30):
  both-sided | ord0.40 wz0.15 pull[0.05,0.82] rsi[45,85] slope0.055 sl2.7 tp2.7 mh36
این اسکریپت همین config را روی همهٔ TFها و هر دو ارز اجرا می‌کند تا مطابقِ «قانونِ
مولتی-تایم‌فریم» گزارشِ مرحله‌به‌مرحله ساخته شود (اجتنابِ اشتباهِ رایج #5).
هر TF بهبودِ متناسبِ خود را می‌تواند بخواهد؛ اینجا ابتدا با config یکسان می‌سنجیم.
اجرا: python3 strategies/s321j_ribbon_final_mtf.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from engine import scalp_engine as se
from engine import rqs
import strategies.s321f_ribbon_m30_slopefilter as S

FINAL = dict(ord_thr=0.40, wz_gate=0.15, pull_min=0.05, pull_max=0.82,
             rsi_min=45, rsi_max=85, slope_min=0.055,
             sl_mult=2.7, tp_mult=2.7, be_mult=0.0, max_hold=36)

FILES = {
    'XAUUSD': ['M5', 'M15', 'M30', 'H1', 'H4'],
    'EURUSD': ['M5', 'M15', 'M30'],
}


def lite(trades):
    n = len(trades)
    if n == 0:
        return 0, 0, 0, 0
    pnl = trades['pnl_pip'].values
    wr = (pnl > 0).sum() / n * 100
    gp = pnl[pnl > 0].sum(); gl = -pnl[pnl < 0].sum()
    pf = gp / gl if gl > 0 else 999
    return n, wr, pf, pnl.sum()


def main():
    print("config: both-sided slope0.055 sl2.7 tp2.7 mh36")
    print("=" * 100)
    for asset, tfs in FILES.items():
        pip = se.ASSETS[asset]['pip']
        for tf in tfs:
            try:
                df = se.load_data(f'data/{asset}_{tf}.csv')
            except Exception as e:
                print(f"{asset} {tf}: load error {e}"); continue
            feats = S.build_features(df, pip)
            ls, ss, sl, tp = S.make_signals(feats, FINAL, 'both')
            tr = se.simulate_trades(df, ls, ss, sl, tp, asset,
                                    max_hold=FINAL['max_hold'], allow_overlap=False)
            n, wr, pf, net = lite(tr)
            if n < rqs.N_FLOOR:
                print(f"{asset} {tf:3s}: n={n} (<{rqs.N_FLOOR}) — skip"); continue
            med_tp = float(np.median(tp[ls | ss]))
            r = rqs.compute_rqs(tr, asset, sl_pip=float(np.median(tr['sl_pip'])), tp_pip=med_tp)
            g = r['gates']
            gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
            m = r['metrics']
            print(f"{asset} {tf:3s}: RQS={r['rqs_score']:5.1f} {'PASS' if r['passed'] else 'FAIL'} "
                  f"G[{gl}] n={m['n_trades']:3d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
                  f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
                  f"net={m['net_profit']:.0f} wf={m['wf_nets']}")


if __name__ == '__main__':
    main()
