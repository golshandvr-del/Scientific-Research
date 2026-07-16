"""
S54a — کاوشِ خام: آیا edge روند-پیرو روی EURUSD/AUDUSD/USDCHF در نیمهٔ اول هست؟
================================================================================
فرضیهٔ علمی (پاسخ به User Note اول، در ادامهٔ L29):
  طلا در نیمهٔ اول (۲۰۲۱–۲۰۲۲) بی‌روند بود (eff-ratio≈0.004) و هیچ سیستمِ روند-پیرو
  در آن سود نمی‌دهد. اما جفت‌ارزهای دیگر (EUR/AUD/CHF) در همان بازهٔ زمانی روندهای
  مستقلِ خودشان را داشتند. اگر همان کاندیدای روند-پیروِ ساده (EMA50>EMA200 و بالعکس)
  را روی آن‌ها بزنیم، آیا در نیمهٔ اول P(fav) > 0.5 است؟

  این «مرحلهٔ ۱ Recipe» است: قبل از هزینهٔ ML، فقط جهت‌گیریِ خام را می‌سنجیم.
  edge خام = P(به TP رسیدن قبل از SL) با TP=1*ATR, SL=1.5*ATR (همان S49).

هیچ ML اینجا نیست؛ فقط آمار توصیفیِ کاندیدای خام روی هر دارایی و هر نیمه.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
from features import make_target
import warnings; warnings.filterwarnings('ignore')

HZ = 48; TP_M = 1.0; SL_M = 1.5
ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']


def probe(asset):
    df = load_data(f'data/{asset}_M15.csv')
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    cand_long = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
    cand_short = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
    yL = make_target(df, HZ, TP_M, SL_M, atr, 'long')
    yS = make_target(df, HZ, TP_M, SL_M, atr, 'short')
    mid = n // 2

    def stat(cand, y, lo, hi):
        m = cand & ~np.isnan(y)
        m[:lo] = False; m[hi:] = False
        yy = y[m]
        if len(yy) == 0:
            return (0, np.nan)
        return (len(yy), np.nanmean(yy))

    print(f"\n=== {asset} (n={n}) ===")
    for name, cand, y in [('LONG', cand_long, yL), ('SHORT', cand_short, yS)]:
        nA, pA = stat(cand, y, 0, mid)      # نیمهٔ اول
        nB, pB = stat(cand, y, mid, n)      # نیمهٔ دوم
        nT, pT = stat(cand, y, 0, n)        # کل
        flag1 = '✅' if pA > 0.5 else '❌'
        flag2 = '✅' if pB > 0.5 else '❌'
        print(f"  {name}: نیمه۱ P(fav)={pA:.3f}{flag1}(n={nA})  "
              f"نیمه۲ P(fav)={pB:.3f}{flag2}(n={nB})  کل={pT:.3f}(n={nT})")


for a in ASSETS:
    probe(a)

print("\n— تفسیر —")
print("اگر ارزی در نیمهٔ اول P(fav)>0.5 داشت، منبعِ بالقوهٔ پایداریِ سبد است")
print("که طلا در آن دوره فاقدش بود (L29). این مبنای S54b (پرتفویِ واقعیِ چند-دارایی).")
print("\nتمام.", flush=True)
