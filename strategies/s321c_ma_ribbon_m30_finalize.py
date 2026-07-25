# -*- coding: utf-8 -*-
"""
S321c — نهایی‌سازیِ احیای MA-Ribbon روی XAUUSD M30 (سبک، ضدِ انجماد)
================================================================================
یافتهٔ اسکنِ چند-TF (S321/S321b):
  رفتارِ ribbon-pullback به‌شدت **غیریکنواخت با تایم‌فریم** است:
    M5 : WR≈55 PF≈1.22 (مرزی)   M15: WR≈47 PF≈0.87 (ضررده)
    M30: WR≈57 PF≈1.72 (بهترین) H1 : WR≈36 PF≈0.73 (فاجعه)
  ⇒ تمرکز روی M30. مانعِ باقی‌مانده: trade-off G0(WR≥60) ↔ G2(PF≥1.3).
  ابزارِ شکستنِ trade-off = break-even trailing (be×ATR) مثلِ S313.

این اسکریپت عمداً سبک است (grid کوچک، فقط M30) تا سندباکس منجمد نشود.
اجرا: python3 strategies/s321c_ma_ribbon_m30_finalize.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from engine import scalp_engine as se
from engine import rqs
import strategies.s321b_ma_ribbon_enhanced as S


def run(cfg, feats, df, atr_med):
    ls, ss, sl, tp = S.make_signals(feats, cfg, 'long')
    be = None if cfg['be_mult'] <= 0 else cfg['be_mult'] * atr_med
    tr = se.simulate_trades(df, ls, ss, sl, tp, 'XAUUSD',
                            max_hold=cfg['max_hold'], allow_overlap=False,
                            be_trigger_pip=be)
    sig = ls | ss
    med_tp = float(np.median(tp[sig])) if sig.any() else float(np.median(tp))
    r = rqs.compute_rqs(tr, 'XAUUSD',
                        sl_pip=float(np.median(tr['sl_pip'])) if len(tr) else cfg['sl_mult'],
                        tp_pip=med_tp)
    return r


def main():
    pip = se.ASSETS['XAUUSD']['pip']
    df = se.load_data('data/XAUUSD_M30.csv')
    feats = S.build_features(df, pip)
    atr_med = float(np.nanmedian(feats['atr_pip']))
    base = dict(ord_thr=0.45, wz_gate=0.20, pull_min=0.05, pull_max=0.82,
                rsi_min=50, rsi_max=88, sl_mult=2.2, tp_mult=2.8, max_hold=48)

    # جاروی کوچکِ be برای شکستنِ trade-off (فقط ~۶ اجرا ⇒ سبک)
    best = None
    print(f"atr_med(M30)={atr_med:.1f}pip")
    for be_mult in [0.0, 0.35, 0.5, 0.65, 0.8, 1.0]:
        cfg = dict(base); cfg['be_mult'] = be_mult
        r = run(cfg, feats, df, atr_med)
        m, g = r['metrics'], r['gates']
        gl = ''.join('1' if g[k] else '0' for k in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])
        print(f"be{be_mult:<4} RQS={r['rqs_score']:5.1f} {'PASS' if r['passed'] else 'FAIL'} "
              f"G[{gl}] n={m['n_trades']:3d} WR={m['win_rate']:4.1f} PF={m['profit_factor']:.2f} "
              f"DD={m['max_dd_pct']:.1f} MCL={m['max_consec_losses']} p={m['p_value']:.3f} "
              f"net={m['net_profit']:.0f} wf={m['wf_nets']}")
        key = (r['passed'], r['rqs_score'])
        if best is None or key > best[0]:
            best = (key, be_mult, cfg, r)
    _, be_mult, cfg, r = best
    print("\nBEST:", 'PASS' if r['passed'] else 'FAIL', 'RQS=', r['rqs_score'], 'be=', be_mult)
    out = dict(cfg=cfg, rqs=r['rqs_score'], passed=r['passed'],
               gates=r['gates'], metrics=r['metrics'])
    with open('results/_s321_ma_ribbon_m30.json', 'w') as f:
        json.dump(out, f, indent=2, default=float)
    print("saved results/_s321_ma_ribbon_m30.json")


if __name__ == '__main__':
    main()
