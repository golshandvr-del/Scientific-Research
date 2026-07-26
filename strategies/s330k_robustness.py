# -*- coding: utf-8 -*-
"""
s330k_robustness.py — تستِ پایداریِ لبهٔ احیاشده (اجتناب از overfit — اشتباهِ رایجِ #۷).
================================================================================
پیکربندیِ برنده: Asia-fade M5, or_bars=12, regime_atr_ratio_max=1.1, RR=1:1.
اگر لبه واقعی باشد باید در همسایگیِ هر پارامتر پایدار بماند (نه یک نقطهٔ تیز).
حساسیت‌سنجی: or_bars، k_sl/k_tp (RR)، regime_atr_ma، آستانهٔ رژیم (قبلاً [1.0,1.1] ✓).
هر تغییر فقط RQS و verdict را چاپ می‌کند.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_orb import SessionORB

DF = TS.load_data('XAUUSD_M5')  # cache یک‌بار


def run(label, **kw):
    strat = SessionORB(**kw)
    tr, eq = TS.simulate(DF, strat, 'XAUUSD', warmup=600)
    rep = RQS.compute_rqs(tr, 'XAUUSD')
    m = rep['metrics']; g = rep['gates']
    gates = ''.join('1' if g.get(f'G{i}') else '0' for i in range(6))
    print(f"{label:26s} | {rep['verdict']:6s} RQS={rep['rqs_score']:5.1f} "
          f"n={m.get('n_trades',0):3d} WR={m.get('win_rate',0):4.1f}% "
          f"PF={m.get('profit_factor',0):.2f} | G012345={gates}")
    return rep


if __name__ == '__main__':
    base = dict(session_start_hour=0, side='FADE', atr_max=99, trend_ema=0,
                k_sl=1.0, k_tp=1.0, max_hold=48, trade_window_bars=48,
                regime_atr_ratio_max=1.1, regime_atr_ma=500)
    print("=== مرجعِ برنده ===")
    run("or_bars=12 (WIN)", or_bars=12, **base)

    print("\n=== حساسیت به or_bars (بازهٔ افتتاحیه) ===")
    for ob in (9, 10, 11, 13, 14, 15):
        run(f"or_bars={ob}", or_bars=ob, **{k: v for k, v in base.items()})

    print("\n=== حساسیت به regime_atr_ma (طولِ SMAِ رژیم) ===")
    for ma in (300, 400, 600, 750):
        run(f"regime_ma={ma}", or_bars=12, session_start_hour=0, side='FADE',
            atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48,
            trade_window_bars=48, regime_atr_ratio_max=1.1, regime_atr_ma=ma)

    print("\n=== حساسیت به RR (k_tp) ===")
    for ktp in (0.8, 0.9, 1.1, 1.2):
        run(f"k_tp={ktp}", or_bars=12, session_start_hour=0, side='FADE',
            atr_max=99, trend_ema=0, k_sl=1.0, k_tp=ktp, max_hold=48,
            trade_window_bars=48, regime_atr_ratio_max=1.1, regime_atr_ma=500)

    print("\n=== حساسیت به trade_window_bars ===")
    for tw in (36, 42, 54, 60):
        run(f"window={tw}", or_bars=12, session_start_hour=0, side='FADE',
            atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48,
            trade_window_bars=tw, regime_atr_ratio_max=1.1, regime_atr_ma=500)
