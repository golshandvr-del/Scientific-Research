# -*- coding: utf-8 -*-
"""
S333 — قانونِ همپوشانی بند ۳: آیا فیلترِ رژیمِ S333 لایهٔ زندهٔ Brooks High-2 را ارتقا می‌دهد؟
================================================================================
همپوشانیِ S333 با Triple-SMA/Brooks-pullback بالا بود (81-91%). طبقِ بند ۳ قانونِ
همپوشانی باید بررسی کنیم آیا بخشِ همپوشان (= فیلترِ رژیمِ Hurst/ER) می‌تواند به‌عنوانِ
«فیلترِ بهبود» روی لایهٔ زندهٔ Brooks High-2 (WR 48.8٪، PF 1.10 — احتمالاً RQS+ مردود)
اعمال شود و آن را احیا کند.

می‌سازیم: هستهٔ Brooks High-2 (شمارندهٔ causal، دقیقاً مثلِ brooks_high2.ts)
سپس (خام) vs (+Hurst) vs (+Hurst+ER) را با RQS+ می‌سنجیم.
اجرا:  python strategies/s333_brooks_regime_filter.py > /tmp/s333_brooks.txt
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from strategies import s333_s79_pullback_revival as S
from engine import scalp_engine as SE
from engine import indicator_bank as ib
import warnings; warnings.filterwarnings('ignore')


def brooks_high2_signal(df, ema_fast=20, ema_slow=50):
    """بازتولیدِ دقیقِ شمارندهٔ causalِ Brooks High-2 (LONG) از brooks_high2.ts."""
    c = df['close'].values; h = df['high'].values
    ef = S.ema(c, ema_fast); es = S.ema(c, ema_slow)
    n = len(c)
    sig = np.zeros(n, bool)
    up_count = 0; saw_pull = False
    for i in range(1, n):
        bull = ef[i] > es[i]
        if bull:
            if h[i] < h[i-1]:
                saw_pull = True
            elif h[i] > h[i-1] and saw_pull:
                up_count += 1; saw_pull = False
                if up_count == 2:
                    sig[i] = True; up_count = 0
                elif up_count >= 4:
                    up_count = 0
        else:
            up_count = 0; saw_pull = False
    return sig


# هندسهٔ منصفانه per-TF (TP>=SL). از پلاتوی S333 الهام؛ Brooks اصلی R:R=1.5 بود.
GEO = {
    'XAUUSD_M5':  [(120,120),(150,150),(150,180)],
    'XAUUSD_M15': [(180,180),(200,240),(240,240)],
    'XAUUSD_M30': [(300,300),(340,340),(380,420)],
    'XAUUSD_H1':  [(450,450),(450,520),(500,500)],
}
MH = {'XAUUSD_M5':96,'XAUUSD_M15':96,'XAUUSD_M30':80,'XAUUSD_H1':64}


def main():
    print('S333/بند۳ — احیای Brooks High-2 با فیلترِ رژیمِ S333 (Hurst/ER). هندسهٔ منصفانه TP>=SL.')
    print('=' * 92)
    for tf in ['XAUUSD_M5','XAUUSD_M15','XAUUSD_M30','XAUUSD_H1']:
        df = SE.load_data(SE.ASSETS[tf]['file'])
        base = brooks_high2_signal(df)
        hu = np.nan_to_num(ib.compute('hurst', df).values, nan=-1.0)
        er = np.nan_to_num(ib.compute('er_lucas_29', df).values, nan=-1.0)
        variants = {
            'RAW':        base,
            '+Hurst0.55': base & (hu > 0.55),
            '+Hurst0.55+ER0.25': base & (hu > 0.55) & (er > 0.25),
            '+Hurst0.57+ER0.30': base & (hu > 0.57) & (er > 0.30),
        }
        print(f'--- {tf} (Brooks raw signals={int(base.sum())}) ---')
        for label, sig in variants.items():
            best = None
            for SL, TP in GEO[tf]:
                tr, r = S.evaluate(df, sig, tf, SL, TP, MH[tf])
                if tr is None or len(tr) < 30:
                    continue
                if best is None or r['rqs_score'] > best[1]['rqs_score']:
                    best = ((SL, TP), r)
            if best is None:
                print(f'   {label:20s} n<30 (نمونهٔ ناکافی)')
            else:
                (SL, TP), r = best
                print(f'   {label:20s} SL={SL} TP={TP} | ' + S.brief(r))
    print('=' * 92)


if __name__ == '__main__':
    main()
