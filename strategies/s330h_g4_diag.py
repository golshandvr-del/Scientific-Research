# -*- coding: utf-8 -*-
"""
s330h_g4_diag.py — تشخیصِ G4: کدام پنجرهٔ walk-forwardِ A1 (Asia-fade M5) منفی است؟
================================================================================
A1 همهٔ گیت‌ها جز G4 را پاس کرد (WR67٪ PF1.71 p=0.007). برای احیا باید بفهمیم
لبه دقیقاً در کدام دورهٔ زمانی می‌شکند تا فیلترِ رژیمِ هدفمند بسازیم.
خروجی: net هر یک از ۴ پنجره + هر نیمه + سالِ هر معامله + رابطهٔ برد/باخت با
شاخصِ رژیم (ADX / نسبتِ range به ATR در لحظهٔ ورود).
"""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import rqs as RQS
from strategies.sim_orb import SessionORB


def main():
    df = TS.load_data('XAUUSD_M5')
    strat = SessionORB(session_start_hour=0, or_bars=12, trade_window_bars=48,
                       side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48)
    tr, eq = TS.simulate(df, strat, 'XAUUSD', warmup=300)
    tr = tr.sort_values('exit_bar').reset_index(drop=True)
    n = len(tr)
    print(f"n_trades={n}")

    # net هر معامله بر حسب pnl_pip
    pnl = tr['pnl_pip'].to_numpy()
    print("ستون‌ها:", list(tr.columns))

    # ۴ پنجرهٔ مساوی
    q = n // 4
    print("\n=== ۴ پنجرهٔ walk-forward (بر حسبِ ترتیبِ زمانی) ===")
    for a in range(4):
        seg = pnl[a*q:(a+1)*q] if a < 3 else pnl[a*q:]
        wr = (seg > 0).mean() * 100 if len(seg) else 0
        print(f"  W{a+1}: n={len(seg):3d}  net_pip={seg.sum():8.2f}  WR={wr:5.1f}%")

    print("\n=== دو نیمه ===")
    half = n // 2
    for a, seg in enumerate([pnl[:half], pnl[half:]]):
        wr = (seg > 0).mean() * 100 if len(seg) else 0
        print(f"  H{a+1}: n={len(seg):3d}  net_pip={seg.sum():8.2f}  WR={wr:5.1f}%")

    # سالِ ورودِ هر معامله (اگر ستونِ entry_bar باشد)
    if 'entry_bar' in tr.columns:
        dt = df['dt']
        yrs = [dt.dt.year.iloc[int(b)] if 0 <= int(b) < len(df) else -1 for b in tr['entry_bar']]
        yrs = np.array(yrs)
        print("\n=== net بر حسبِ سال ===")
        for y in sorted(set(yrs)):
            m = yrs == y
            print(f"  {y}: n={m.sum():3d}  net_pip={pnl[m].sum():8.2f}  WR={(pnl[m]>0).mean()*100:5.1f}%")


if __name__ == '__main__':
    main()
