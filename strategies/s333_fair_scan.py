# -*- coding: utf-8 -*-
"""اسکنِ منصفانهٔ S333 — WR فقط از دقتِ ورود + فیلترِ رژیم، با هندسهٔ TP>=SL.

اصلِ روش‌شناختی (تصحیحِ کاربر): هرگز TP<SL برای تورمِ مصنوعیِ WR استفاده نمی‌شود.
هندسه منصفانه است (breakeven <= 50%)، پس هر WR>50% لبهٔ واقعی است. WR را با:
  (الف) تأییدِ بازگشتِ pullback  (ب) فیلترِ رژیمِ persistence  بالا می‌بریم.
اجرا:  python strategies/s333_fair_scan.py XAUUSD_M5
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from strategies import s333_s79_pullback_revival as S
from engine import scalp_engine as SE
from engine import indicator_bank as ib


def scan(asset, geos, mh, hths, second_filters, confirms, rsi_ths, min_n=35):
    df = SE.load_data(SE.ASSETS[asset]['file'])
    print(f'=== {asset} (rows={len(df)}) — FAIR geometry TP>=SL, entry-precision ===')
    # پیش‌محاسبهٔ اندیکاتورهای رژیم یک‌بار
    reg = {'hurst': ib.compute('hurst', df).values}
    for (nm, _, _) in second_filters:
        if nm not in reg:
            reg[nm] = ib.compute(nm, df).values
    best = None
    for confirm in confirms:
        for rth in rsi_ths:
            base = S.core_signal_confirmed(df, 20, 100, 21, rth, confirm=confirm)
            n_base = int(base.sum())
            if n_base < min_n:
                continue
            for hth in hths:
                hu_ok = np.nan_to_num(reg['hurst'], nan=-1.0) > hth
                # الف) فقط hurst
                combos = [('hurstOnly', hu_ok)]
                # ب) hurst + یک فیلترِ دوم
                for (nm, op, thr) in second_filters:
                    s = np.nan_to_num(reg[nm], nan=(-1e9 if op == 'gt' else 1e9))
                    f2 = (s > thr) if op == 'gt' else (s < thr)
                    combos.append((f'{nm}{op}{thr}', hu_ok & f2))
                for (label, mask) in combos:
                    sig = base & mask
                    for (SL, TP) in geos:
                        if TP < SL:      # قانونِ منصفانه: هرگز TP<SL
                            continue
                        tr, r = S.evaluate(df, sig, asset, SL, TP, mh)
                        if tr is None or len(tr) < min_n:
                            continue
                        if r['passed']:
                            line = (f"  {confirm} rsi<{rth} hu>{hth} +{label} "
                                    f"SL={SL} TP={TP} | " + S.brief(r))
                            print(line)
                            if best is None or r['rqs_score'] > best[0]:
                                best = (r['rqs_score'], confirm, rth, hth, label, SL, TP)
    print('  >>> BEST', asset, ':', best)
    return best


CFG = {
    # هندسهٔ منصفانه: TP>=SL همیشه. اعدادِ غیررند.
    'XAUUSD_M5': dict(
        geos=[(120,120),(140,150),(150,150),(150,180),(170,170),(180,200),(200,200)],
        mh=96, hths=[0.53,0.55,0.57], rsi_ths=[32,35,38],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                        ('er_lucas_29','gt',0.25),('chop_fib_21','lt',45)]),
    'XAUUSD_M15': dict(
        geos=[(160,160),(180,180),(200,200),(200,240),(240,240),(260,300)],
        mh=96, hths=[0.55,0.57,0.60], rsi_ths=[32,35,38],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                        ('er_lucas_29','gt',0.25)]),
    'XAUUSD_M30': dict(
        geos=[(240,240),(280,280),(300,300),(300,360),(340,340),(380,420)],
        mh=80, hths=[0.53,0.55,0.57], rsi_ths=[32,35,38],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                        ('er_lucas_29','gt',0.25)]),
    'XAUUSD_H1': dict(
        geos=[(350,350),(400,400),(450,450),(450,520),(500,500),(550,600)],
        mh=64, hths=[0.50,0.53,0.55], rsi_ths=[32,35,38],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                        ('er_lucas_29','gt',0.25)]),
    'XAUUSD_H4': dict(
        geos=[(700,700),(800,800),(900,900),(1000,1000)],
        mh=48, hths=[0.48,0.50,0.53], rsi_ths=[35,38,40],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.40),('r2_fib_89','gt',0.50)]),
    'EURUSD_M5': dict(
        geos=[(90,90),(110,110),(120,140),(140,140),(160,180)],
        mh=96, hths=[0.53,0.55,0.57], rsi_ths=[32,35,38],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                        ('er_lucas_29','gt',0.25)]),
    'EURUSD_M15': dict(
        geos=[(140,140),(160,180),(180,180),(200,240),(220,220)],
        mh=96, hths=[0.55,0.57,0.60], rsi_ths=[32,35,38],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55),
                        ('er_lucas_29','gt',0.25)]),
    'EURUSD_M30': dict(
        geos=[(180,180),(220,240),(240,240),(280,320),(320,320)],
        mh=80, hths=[0.55,0.57,0.60], rsi_ths=[32,35,38],
        confirms=['none','rsi_turn','price_turn'],
        second_filters=[('r2_fib_89','gt',0.45),('r2_fib_89','gt',0.55)]),
}


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M5'
    c = CFG[target]
    scan(target, c['geos'], c['mh'], c['hths'], c['second_filters'],
         c['confirms'], c['rsi_ths'], min_n=(30 if 'H4' in target else 35))
