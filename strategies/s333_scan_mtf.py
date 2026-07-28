# -*- coding: utf-8 -*-
"""اسکنِ مولتی‌تایم‌فریمِ S333 — هستهٔ pullback + فیلترهای رژیمِ بانک.
هر TF جدا؛ per-TF geometry غیررند؛ فیلترهای stack‌شونده (hurst + r2/er/chop).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from strategies import s333_s79_pullback_revival as S
from engine import scalp_engine as SE
from engine import indicator_bank as ib


def scan_asset(asset, geos, mh, hths, second_filters, rths=(35,), min_n=35):
    df = SE.load_data(SE.ASSETS[asset]['file'])
    hu = ib.compute('hurst', df).values
    fseries = {name: ib.compute(name, df).values for (name, _, _) in second_filters}
    print('=== %s (rows=%d) ===' % (asset, len(df)))
    best = None
    for rth in rths:
        base = S.core_signal(df, 20, 100, 21, rth)
        for hth in hths:
            hgate = base & (np.nan_to_num(hu, nan=-1) > hth)
            filt_variants = [('none', None, None)] + second_filters
            for (fname, _, fth) in filt_variants:
                if fname == 'none':
                    sig = hgate
                else:
                    fs = fseries[fname]
                    sig = hgate & (np.nan_to_num(fs, nan=-1) > fth)
                for SL, TP in geos:
                    tr, r = S.evaluate(df, sig, asset, SL, TP, mh)
                    if tr is None or len(tr) < min_n:
                        continue
                    if r['passed']:
                        print('  rsi<%d hu>%.2f %s>%s SL=%d TP=%d | %s'
                              % (rth, hth, fname, fth, SL, TP, S.brief(r)))
                        if best is None or r['rqs_score'] > best[0]:
                            best = (r['rqs_score'], rth, hth, fname, fth, SL, TP)
    print('  >>> BEST %s: %s\n' % (asset, best))
    return best


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M15'
    CFG = {
        'XAUUSD_M15': dict(
            geos=[(160,140),(180,160),(180,180),(200,180),(200,200),(220,200),(240,220)],
            mh=96, hths=[0.55,0.57,0.60],
            second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                            ('er_lucas_29','gt',0.25),('chop_fib_21','gt',-1e9)]),
        'XAUUSD_M30': dict(
            geos=[(240,200),(280,240),(300,300),(340,300),(380,340),(420,380)],
            mh=80, hths=[0.55,0.57,0.60],
            second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                            ('er_lucas_29','gt',0.25)]),
        'XAUUSD_H1': dict(
            geos=[(350,320),(400,380),(450,450),(500,450),(550,500),(600,560)],
            mh=64, hths=[0.53,0.55,0.57],
            second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                            ('er_lucas_29','gt',0.25)]),
        'XAUUSD_H4': dict(
            geos=[(700,650),(800,750),(900,900),(1000,900),(1100,1000)],
            mh=48, hths=[0.50,0.53,0.55],
            second_filters=[('r2_fib_89','gt',0.40),('r2_fib_89','gt',0.50)], ),
    }
    c = CFG[target]
    scan_asset(target, c['geos'], c['mh'], c['hths'], c['second_filters'],
               min_n=(30 if 'H4' in target else 35))
