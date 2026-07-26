# -*- coding: utf-8 -*-
"""
s330j_revive_m5.py — تلاشِ نهاییِ احیا: Asia-fade M5 + فیلترِ رژیمِ نوسان + RQS+ کامل.
================================================================================
منطقِ بهبود (S330i): fade فقط در رژیمِ آرام (ATR/ATR_MA500 ≤ آستانه) معتبر است.
سالِ ۲۰۲۶ (ضررده) رژیمِ پرنوسان (R1≈1.03) داشت ⇒ فیلتر باید آن را کنار بگذارد و
G4 را نجات دهد. چند آستانه را با RQS+ رسمی می‌سنجیم.
شروع طبقِ قانونِ مولتی‌TF: XAUUSD_M5.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_orb import SessionORB


def run(label, **kw):
    df = TS.load_data('XAUUSD_M5')
    strat = SessionORB(**kw)
    tr, eq = TS.simulate(df, strat, 'XAUUSD', warmup=600)
    rep = RQS.compute_rqs(tr, 'XAUUSD')
    print(RQS.format_report(label, rep))
    return rep


if __name__ == '__main__':
    print("=" * 110)
    print("S330j — Asia-fade M5 + regime filter (احیای G4). XAUUSD_M5.")
    print("=" * 110)
    base = dict(session_start_hour=0, or_bars=12, trade_window_bars=48,
                side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48)

    # بدونِ فیلتر (مرجع)
    run("NoFilter (ref)", **base)

    # با فیلترِ رژیم در آستانه‌های گوناگون
    for thr in (0.9, 1.0, 1.1, 1.2):
        run(f"regime<= {thr}", regime_atr_ratio_max=thr, regime_atr_ma=500, **base)
