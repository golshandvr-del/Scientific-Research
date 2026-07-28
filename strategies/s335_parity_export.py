# -*- coding: utf-8 -*-
"""
s335_parity_export.py — استخراجِ مقادیرِ مرجعِ پایتون برای تستِ برابریِ TS↔Python.
خروجی: strategies/s335_parity_ref.json شامل کندل‌های خام + مقادیرِ اندیکاتورهای
reflex/trendflex/hurst/r2/chop روی همان کندل‌ها (پارامترهای پیش‌فرضِ بانک).
harnessِ TS همین اندیکاتورها را دوباره محاسبه و مقایسه می‌کند.
"""
import sys, os, json
sys.path.insert(0, '/home/user/webapp')
os.chdir('/home/user/webapp')
import numpy as np
from engine import scalp_engine as se
from engine import indicator_bank as ib

# پارامترهای پیش‌فرضِ بانک (همان‌که ماژولِ TS با آن‌ها فراخوانی می‌کند)
P_RF = 20   # reflex period
P_TF = 20   # trendflex period
P_HU = 64   # hurst period
P_R2 = 20   # r2 period
P_CH = 14   # chop period

def main():
    # زیرمجموعه‌ای معنادار از M5 (سریع و کافی برای برابری)
    df = se.load_data('data/XAUUSD_M5.csv').iloc[:6000].reset_index(drop=True)
    reflex = ib.reflex(df, period=P_RF).values.astype(float)
    tflex  = ib.trendflex(df, period=P_TF).values.astype(float)
    hurst  = ib.hurst(df, p=P_HU).values.astype(float)
    r2     = ib.r2(df, p=P_R2).values.astype(float)
    chop   = ib.chop(df, p=P_CH).values.astype(float)

    def clean(a):
        return [None if (not np.isfinite(x)) else round(float(x), 6) for x in a]

    out = {
        'params': {'p_rf': P_RF, 'p_tf': P_TF, 'p_hu': P_HU, 'p_r2': P_R2, 'p_ch': P_CH},
        'candles': [
            {'time': int(df['time'].iloc[i]),
             'open': round(float(df['open'].iloc[i]), 5),
             'high': round(float(df['high'].iloc[i]), 5),
             'low':  round(float(df['low'].iloc[i]), 5),
             'close':round(float(df['close'].iloc[i]), 5)}
            for i in range(len(df))
        ],
        'reflex': clean(reflex),
        'trendflex': clean(tflex),
        'hurst': clean(hurst),
        'r2': clean(r2),
        'chop': clean(chop),
    }
    path = 'strategies/s335_parity_ref.json'
    with open(path, 'w') as f:
        json.dump(out, f)
    print(f"wrote {path}  bars={len(df)}")
    # یک نمونهٔ سریع برای چشم
    for name, arr in [('reflex',reflex),('trendflex',tflex),('hurst',hurst),('r2',r2),('chop',chop)]:
        v = arr[np.isfinite(arr)]
        print(f"  {name:10s} valid={len(v)}/{len(arr)} last5={[round(float(x),4) for x in arr[-5:]]}")

if __name__ == '__main__':
    main()
