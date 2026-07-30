# -*- coding: utf-8 -*-
"""S346 — تشخیصِ مقیاس: ATRِ تطبیقی نسبت به هزینهٔ واقعیِ رفت‌وبرگشت در هر TF.

چرا لازم است؟ در اسکنِ اولِ M5 دیدیم PF<1 برای همهٔ ترکیب‌ها. علتِ کاندید:
SL = k×ATR_adaptive روی M5 طلا فقط ~۶ pip می‌شود در حالی که هزینهٔ رفت‌وبرگشت
۳.۳ pip است ⇒ هزینه ۵۰٪ از SL! هیچ لبه‌ای زنده نمی‌ماند. این اسکریپت نسبتِ
`ATR_a / cost` را برای هر کارت اندازه می‌گیرد تا شبکهٔ sl_k **per-TF** و
واقع‌بینانه انتخاب شود (رفعِ اشتباهِ رایج #۶: SL/TP یکسان برای همهٔ TFها).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                      # noqa: E402
from strategies.s346_adaptive_channel import adaptive_channel  # noqa: E402

CARDS = [
    ('XAU-M5', 'data/XAUUSD_M5.csv', 'XAUUSD'),
    ('XAU-M15', 'data/XAUUSD_M15.csv', 'XAUUSD'),
    ('XAU-M30', 'data/XAUUSD_M30.csv', 'XAUUSD'),
    ('XAU-H1', 'data/XAUUSD_H1.csv', 'XAUUSD'),
    ('XAU-H4', 'data/XAUUSD_H4.csv', 'XAUUSD'),
    ('XAU-D1', 'data/XAUUSD_D1.csv', 'XAUUSD'),
    ('EUR-M1', 'data/EURUSD_M1.csv', 'EURUSD'),
    ('EUR-M5', 'data/EURUSD_M5.csv', 'EURUSD'),
    ('EUR-M15', 'data/EURUSD_M15.csv', 'EURUSD'),
    ('EUR-M30', 'data/EURUSD_M30.csv', 'EURUSD'),
]

if __name__ == '__main__':
    print(f"{'card':8s} {'p':>3s} {'bars':>7s} {'medATRa':>8s} {'cost':>5s} "
          f"{'ATRa/cost':>9s} {'ER_med':>7s}")
    for card, path, asset in CARDS:
        df = se.load_data(path)
        pip = se.ASSETS[asset]['pip']
        cost = se.ASSETS[asset]['spread_pip'] + 2 * se.ASSETS[asset]['slip_pip']
        for p in (21, 55):
            ch = adaptive_channel(df, p=p, mult=1.618)
            a = float(np.nanmedian(ch['atr_a'][300:]) / pip)
            er = float(np.nanmedian(ch['er'][300:]))
            print(f"{card:8s} {p:3d} {len(df):7d} {a:8.2f} {cost:5.1f} "
                  f"{a / cost:9.2f} {er:7.3f}")
