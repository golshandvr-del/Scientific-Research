# -*- coding: utf-8 -*-
"""
s330g_asia_rqs.py — تستِ نهاییِ «تنها روزنهٔ امید» با موتورِ RQS+ کامل.
================================================================================
از اسکن‌های S330c/d/e/f نتیجه شد: ORB روی XAUUSD/EURUSD در نمونه‌های بزرگ WR~۵۰٪
(random walk) دارد. تنها استثنا: سشنِ آسیا (h=0 UTC) + منطقِ FADE، که در M5/M15
WRِ ۵۵–۷۰٪ نشان داد اما با n کوچک و WF ناپایدار (پنجرهٔ اول شدیداً منفی).

این اسکریپت آن روزنه را با شبیه‌سازِ رویداد-محورِ رسمی + RQS+ کامل می‌سنجد تا گیتِ
G4 (پایداریِ walk-forward) حرفِ آخر را بزند.

نکاتِ کارایی (برای اجتناب از فریزِ سندباکس):
    • هر فایلِ داده فقط **یک‌بار** با cache بارگذاری می‌شود.
    • فقط چند پیکربندیِ منتخبِ سشنِ آسیا آزمایش می‌شود (نه grid صدتایی).
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_orb import SessionORB


def run(label, strat, tf, asset='XAUUSD'):
    df = TS.load_data(tf)
    tr, eq = TS.simulate(df, strat, asset, warmup=300)
    rep = RQS.compute_rqs(tr, asset)
    print(RQS.format_report(label, rep))
    return rep


if __name__ == '__main__':
    print("=" * 110)
    print("S330g — Asia-session (h=0) FADE با RQS+ کامل. تنها روزنهٔ امیدِ ORB.")
    print("=" * 110)

    # منطقِ FADE: side='FADE' در SessionORB (شکستِ کاذب → معاملهٔ معکوس).
    # پیکربندی‌های منتخب از S330f (h=0، M5/M15/M30، or_bars/rr گوناگون).
    configs = [
        ('A1 M5  ob12 rr1.0', dict(session_start_hour=0, or_bars=12, trade_window_bars=48,
                                   side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48), 'XAUUSD_M5'),
        ('A2 M15 ob8  rr1.0', dict(session_start_hour=0, or_bars=8, trade_window_bars=48,
                                   side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48), 'XAUUSD_M15'),
        ('A3 M15 ob12 rr1.0', dict(session_start_hour=0, or_bars=12, trade_window_bars=36,
                                   side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48), 'XAUUSD_M15'),
        ('A4 M30 ob6  rr1.0', dict(session_start_hour=0, or_bars=6, trade_window_bars=24,
                                   side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=24), 'XAUUSD_M30'),
    ]
    for label, kw, tf in configs:
        try:
            run(label, SessionORB(**kw), tf)
        except Exception as e:
            print(f"{label:20s} | ERROR: {e}")
