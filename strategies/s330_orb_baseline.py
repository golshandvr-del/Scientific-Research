# -*- coding: utf-8 -*-
"""
s330_orb_baseline.py — بیس‌لاینِ احیای S21 (Session-ORB).

هدف: تأییدِ سوختگیِ نسخهٔ خامِ ORB با RQS+ و سپس نشان‌دادنِ اثرِ اولین بهبود
(LONG-only هم‌راستا با long-biasِ طلا) — روی XAUUSD M5.

اجرا:
    python3 strategies/s330_orb_baseline.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_orb import SessionORB


def run(tag, strat, tf, asset='XAUUSD', warmup=300):
    df = TS.load_data(tf)
    tr, eq = TS.simulate(df, strat, asset, tf=tf.split('_')[-1], warmup=warmup)
    r = RQS.compute_rqs(tr, asset)
    print(RQS.format_report(tag, r))
    return r


if __name__ == '__main__':
    print("=" * 110)
    print("S330 — Session-ORB baseline (XAUUSD M5). سشنِ لندن(7) و نیویورک(13).")
    print("=" * 110)

    # ---- الف) ORB خامِ دوطرفه (بازتولیدِ عصرِ WR): سشنِ لندن، بدون فیلتر، RR متقارن ----
    run("A1 raw BOTH London",
        SessionORB(session_start_hour=7, or_bars=12, trade_window_bars=48,
                   side='BOTH', atr_max=0.0, trend_ema=0, k_sl=1.0, k_tp=1.0,
                   max_hold=48), 'XAUUSD_M5')

    run("A2 raw BOTH NewYork",
        SessionORB(session_start_hour=13, or_bars=12, trade_window_bars=48,
                   side='BOTH', atr_max=0.0, trend_ema=0, k_sl=1.0, k_tp=1.0,
                   max_hold=48), 'XAUUSD_M5')

    # ---- ب) بهبودِ اول: LONG-only (long-biasِ طلا) ----
    run("B1 LONG London",
        SessionORB(session_start_hour=7, or_bars=12, trade_window_bars=48,
                   side='LONG', atr_max=0.0, trend_ema=0, k_sl=1.0, k_tp=1.0,
                   max_hold=48), 'XAUUSD_M5')

    run("B2 LONG NewYork",
        SessionORB(session_start_hour=13, or_bars=12, trade_window_bars=48,
                   side='LONG', atr_max=0.0, trend_ema=0, k_sl=1.0, k_tp=1.0,
                   max_hold=48), 'XAUUSD_M5')

    # ---- ج) + coiled-spring + فیلترِ جهتِ EMA200 ----
    run("C1 LONG+spring+ema London",
        SessionORB(session_start_hour=7, or_bars=12, trade_window_bars=48,
                   side='LONG', atr_max=1.2, trend_ema=200, k_sl=1.0, k_tp=1.0,
                   max_hold=48), 'XAUUSD_M5')

    run("C2 LONG+spring+ema NewYork",
        SessionORB(session_start_hour=13, or_bars=12, trade_window_bars=48,
                   side='LONG', atr_max=1.2, trend_ema=200, k_sl=1.0, k_tp=1.0,
                   max_hold=48), 'XAUUSD_M5')
