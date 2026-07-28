# -*- coding: utf-8 -*-
"""
s336_explore_scalp_oscillators.py — اکتشافِ نوسان‌گرهای اسکالپِ نو (نه‌MACD)
=============================================================================
هدف (User Note): استراتژیِ اسکالپِ *پُرمعامله* برای گرفتنِ نوسان‌های ریزِ روزانه
(~۶$ = ۶۰pip) روی XAUUSD/M5، ترجیحاً SHORT.

فلسفه: از MACD (که n بسیار پایین می‌داد) عبور می‌کنیم و به سراغِ نوسان‌گرهای
سریعِ چرخشی می‌رویم که در docs/indicators به‌عنوان «تریگرِ اسکالپ» معرفی شده‌اند:
    fisher (Fisher Transform), crsi (Connors RSI), kdj_j, zscore, laguerre_rsi
+ گیتِ رژیم (chop/r2/hurst) + گیتِ افراط.

این اسکریپت فقط *اکتشاف* است: توزیع اندیکاتورها و نرخِ رخدادِ سیگنال را چاپ می‌کند
تا بفهمیم کدام‌یک برای اسکالپِ پُرمعامله مناسب‌اند. هیچ چیزی را ثبت نمی‌کند.
"""
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicator_bank as ib


def explore(asset='XAUUSD', tf='M5'):
    cfg = se.ASSETS[asset].copy()
    fname = f'data/{asset}_{tf}.csv'
    df = se.load_data(fname)
    n = len(df)
    print(f"=== EXPLORE {asset}/{tf} — n_candles={n} ===")
    pip = cfg['pip']
    rng = (df['high'] - df['low'])
    print(f"median candle range: ${rng.median():.2f} = {rng.median()/pip:.0f}pip | "
          f"spread={cfg['spread_pip']}pip")

    # محاسبهٔ نوسان‌گرهای کاندیدا
    cand = {}
    for nm in ['fisher', 'crsi', 'kdj_j', 'zscore_fib_21', 'laguerre_rsi', 'ifish_rsi',
               'cmo', 'cg', 'reflex', 'trendflex']:
        try:
            s = ib.compute(nm, df)
            cand[nm] = s
            v = s.dropna()
            print(f"{nm:16s} min={v.min():8.3f} p10={v.quantile(.10):8.3f} "
                  f"med={v.median():8.3f} p90={v.quantile(.90):8.3f} max={v.max():8.3f} "
                  f"nan%={s.isna().mean()*100:4.1f}")
        except Exception as e:
            print(f"{nm:16s} ERR {e}")
    return df, cand


if __name__ == '__main__':
    explore('XAUUSD', 'M5')
