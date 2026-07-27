# -*- coding: utf-8 -*-
"""
S332 — تأییدِ ضدِ overfit + جزئیاتِ walk-forward برای هر ترکیبِ (sym,tf) پاس‌شده
================================================================================
برای هر پیکربندیِ برنده:
  A) گزارشِ کاملِ RQS+ + WF-nets + half-nets + expectancy.
  B) آزمونِ همسایگیِ پارامتر (ضدِ اشتباهِ #۷): TP/SL/ADX/BE را کمی جابه‌جا کن؛
     اگر همسایه‌ها هم پاس بمانند ⇒ ناحیهٔ پایدار، نه یک نقطهٔ تصادفی.

اجرا:  python3 strategies/s332_confirm.py --sym XAUUSD --tf H4 --tp 400 --sl 250 --filt adx22pdi
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

MAXHOLD = {'M5': 288, 'M15': 96, 'M30': 64, 'H1': 48, 'H4': 24}


def make_filter(df, name, adx_min):
    c = df['close'].values.astype(float)
    adx_, pdi, mdi = S.adx(df, 14)
    r14 = S.rsi(c, 14)

    def clean(m):
        return np.nan_to_num(m.astype(float), nan=0.0).astype(bool)

    if name == 'adx22pdi':
        return clean((adx_ > adx_min) & (pdi > mdi))
    if name == 'pdi':
        return clean(pdi > mdi)
    if name == 'adx':
        return clean(adx_ > adx_min)
    if name == 'adxrsi':
        return clean((adx_ > adx_min) & (r14 >= 50) & (r14 <= 78))
    return np.ones(len(df), dtype=bool)


def gates_str(r):
    return ''.join('1' if r['gates'][x] else '0' for x in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5'])


def one(df, sym, tf, tp, sl, adx_min, be, fname):
    fm = make_filter(df, fname, adx_min)
    r, tr = S.evaluate(df, sym, S._SIG, sl_pip=sl, tp_pip=tp,
                       max_hold=MAXHOLD[tf], be_trigger_pip=be, filt=fm)
    return r, tr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', default='XAUUSD')
    ap.add_argument('--tf', default='H4')
    ap.add_argument('--tp', type=int, default=400)
    ap.add_argument('--sl', type=int, default=250)
    ap.add_argument('--adx', type=int, default=22)
    ap.add_argument('--be', default='None')
    ap.add_argument('--filt', default='adx22pdi')
    ap.add_argument('--sqz', type=float, default=0.25)
    ap.add_argument('--brk', type=int, default=6)
    a = ap.parse_args()
    be = None if a.be == 'None' else int(a.be)

    df = S.load_tf(a.sym, a.tf)
    S._SIG = S.build_squeeze_signal(df, sqz_pct=a.sqz, breakout_lookback=a.brk)
    print(f"== {a.sym} {a.tf} | signals={int(S._SIG.sum())} | "
          f"center: tp={a.tp} sl={a.sl} adx>{a.adx} be={be} filt={a.filt} ==\n")

    # A) مرکز
    r, tr = one(df, a.sym, a.tf, a.tp, a.sl, a.adx, be, a.filt)
    m = r['metrics']
    from engine import rqs as RQS
    print(RQS.format_report(f'{a.sym}-{a.tf} CENTER', r))
    print(f"   └─ net=${m.get('net_profit'):.0f}  exp={m.get('expectancy_pip'):.2f}pip  "
          f"WF={m.get('wf_nets')}  halves={m.get('half_nets')}\n")

    # B) همسایگی
    print("   آزمونِ همسایگی (ضدِ overfit — اشتباهِ #۷):")
    neigh = [
        ('tp-50',  dict(tp=a.tp - 50)),
        ('tp+50',  dict(tp=a.tp + 50)),
        ('sl-40',  dict(sl=a.sl - 40)),
        ('sl+40',  dict(sl=a.sl + 40)),
        ('adx-3',  dict(adx=a.adx - 3)),
        ('adx+3',  dict(adx=a.adx + 3)),
        ('sqz-.05', dict(sqz=round(a.sqz - 0.05, 2))),
        ('sqz+.05', dict(sqz=round(a.sqz + 0.05, 2))),
        ('brk-2',  dict(brk=a.brk - 2)),
        ('brk+2',  dict(brk=a.brk + 2)),
    ]
    npass = 0
    ntot = 0
    for label, chg in neigh:
        tp = chg.get('tp', a.tp)
        sl = chg.get('sl', a.sl)
        adx_min = chg.get('adx', a.adx)
        sqz = chg.get('sqz', a.sqz)
        brk = chg.get('brk', a.brk)
        if 'sqz' in chg or 'brk' in chg:
            sig2 = S.build_squeeze_signal(df, sqz_pct=sqz, breakout_lookback=brk)
        else:
            sig2 = S._SIG
        fm = make_filter(df, a.filt, adx_min)
        rr, _ = S.evaluate(df, a.sym, sig2, sl_pip=sl, tp_pip=tp,
                           max_hold=MAXHOLD[a.tf], be_trigger_pip=be, filt=fm)
        mm = rr['metrics']
        if mm.get('n_trades', 0) < 30:
            print(f"     {label:8s}: n<30 ({mm.get('n_trades',0)})  skip")
            continue
        ntot += 1
        ok = rr['passed']
        if ok:
            npass += 1
        print(f"     {label:8s}: RQS={rr['rqs_score']:5.1f} {'PASS' if ok else 'fail'} "
              f"(WR={mm['win_rate']:.1f} PF={mm['profit_factor']:.2f} "
              f"DD={mm['max_dd_pct']:.1f} MCL={mm['max_consec_losses']} n={mm['n_trades']}) "
              f"{gates_str(rr)}")
    print(f"\n   ⇒ {npass}/{ntot} همسایه پاس (پایداری{'ِ خوب ✅' if npass >= ntot*0.6 else 'ِ ضعیف ⚠️'})")


if __name__ == '__main__':
    main()
