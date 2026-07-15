"""
اعتبارسنجی هم‌ارزی (parity) feature بین پایتون و MQL5.
=====================================================
این اسکریپت مقادیر ۵۷ feature را برای چند کندل مشخص از انتهای دیتاست چاپ می‌کند
تا بتوان با خروجی EA در MT5 (با InpVerbose و چاپ feat[]) مقایسه کرد.

هشدارهای مهم اختلاف احتمالی بین بک‌تست پایتون و اجرای زندهٔ MT5:
1. حجم: آموزش با ستون `volume` دیتاست انجام شد؛ MT5 از tick_volume استفاده می‌کند.
   feature‌های مبتنی بر حجم (vol_ratio, vol_z20) ممکن است کمی متفاوت شوند.
2. ATR/RSI/ADX: پیاده‌سازی MT5 (Wilder/EMA) با features.py (ewm) عملاً یکسان است
   اما ممکن است در ارقام آخر تفاوت جزئی داشته باشد.
3. VWAP لنگرشده: تعریف روز تقویمی باید یکی باشد (UTC). دیتاست از unix timestamp
   ساخته شده که UTC است؛ سرور بروکر ممکن است timezone متفاوت داشته باشد → مرز روز
   جابه‌جا می‌شود. توصیه: سرور را روی UTC تنظیم کنید یا offset را در EA لحاظ کنید.

خروجی: چاپ ۵ ردیف آخرِ معتبر با تمام ۵۷ feature.
"""
import sys, os
ENGINE = os.path.join(os.path.dirname(__file__), '..', 'engine')
sys.path.insert(0, ENGINE)
import numpy as np
import pandas as pd
import indicators as ind
from backtest import load_data
from features import build_features
import warnings; warnings.filterwarnings('ignore')

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')


def main():
    df = load_data(DATA)
    feats = build_features(df)
    fc = list(feats.columns)
    # ۵ کندل آخرِ کاملاً معتبر
    valid = feats.dropna()
    tail = valid.tail(5)
    print(f"تعداد feature: {len(fc)}")
    print("=" * 70)
    for idx, row in tail.iterrows():
        t = df.loc[idx, 'dt']
        print(f"\nکندل idx={idx} زمان={t} close={df.loc[idx,'close']:.2f}")
        for i, name in enumerate(fc):
            print(f"  [{i:2d}] {name:20s} = {row[name]:+.6f}")


if __name__ == '__main__':
    main()
