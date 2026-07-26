# -*- coding: utf-8 -*-
"""
s330i_regime_split.py — آیا یک فیلترِ رژیمِ *علّی* معاملاتِ ضررده (۲۰۲۶) را از
سوددهِ (۲۰۲۴/۲۵) جدا می‌کند؟  (احیای G4 بدون data-snooping)
================================================================================
یافتهٔ S330h: Asia-fade در W1-3 (تا ۲۰۲۵) عالی، در W4 (۲۰۲۶) می‌شکند ⇒ تغییرِ رژیم.
هدف: یافتنِ متغیرِ رژیمی که در لحظهٔ ورود (بدونِ نگاه به آینده) قابل‌محاسبه است و
معاملاتِ بد را کنار می‌گذارد. کاندیداها:
  R1) نوسانِ نسبی: ATR(14) در لحظهٔ ورود ÷ میانگینِ بلندمدتِ ATR  (رژیمِ پرنوسان؟)
  R2) اندازهٔ بازهٔ افتتاحیه: or_range ÷ ATR   (بازهٔ پهن = روزِ ترندی)
  R3) موقعیتِ قیمت نسبت به EMA200 (فاصلهٔ نرمال‌شده با ATR) — کشش/ترند
برای هر معامله این سه را ثبت و با outcome مقایسه می‌کنیم.
"""
import os
import sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import indicators as ind
from strategies.sim_orb import SessionORB


def main():
    df = TS.load_data('XAUUSD_M5')
    strat = SessionORB(session_start_hour=0, or_bars=12, trade_window_bars=48,
                       side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0, max_hold=48)
    tr, eq = TS.simulate(df, strat, 'XAUUSD', warmup=300)
    tr = tr.sort_values('exit_bar').reset_index(drop=True)

    atr = ind.atr(df, 14).to_numpy()
    atr_long = ind.ema(df['close'], 1).to_numpy()  # placeholder
    # میانگینِ متحرکِ بلندِ ATR (رژیمِ نوسان) — SMA 500 کندلی
    import pandas as pd
    atr_ma = pd.Series(atr).rolling(500, min_periods=50).mean().to_numpy()
    ema200 = ind.ema(df['close'], 200).to_numpy()
    close = df['close'].to_numpy()
    yrs = df['dt'].dt.year.to_numpy()

    rows = []
    for _, t in tr.iterrows():
        b = int(t['entry_bar'])
        if b <= 0 or b >= len(df):
            continue
        r1 = atr[b] / atr_ma[b] if atr_ma[b] and np.isfinite(atr_ma[b]) and atr_ma[b] > 0 else np.nan
        r3 = (close[b] - ema200[b]) / atr[b] if atr[b] > 0 else np.nan
        win = 1 if t['outcome'] == 'win' else 0
        rows.append((yrs[b], win, t['pnl_pip'], r1, abs(r3)))

    arr = np.array(rows, dtype=float)
    yr, win, pnl, r1, r3abs = arr[:,0], arr[:,1], arr[:,2], arr[:,3], arr[:,4]

    def stat(mask, name):
        if mask.sum() == 0:
            print(f"  {name:32s} n=0"); return
        print(f"  {name:32s} n={int(mask.sum()):3d}  WR={win[mask].mean()*100:5.1f}%  net={pnl[mask].sum():8.2f}")

    print("=== R1: نوسانِ نسبی ATR/ATR_MA500 (رژیمِ نوسان) ===")
    good = np.isfinite(r1)
    med1 = np.nanmedian(r1[good])
    print(f"  median(R1)={med1:.3f}")
    stat(good & (r1 <= med1), "R1 پایین (بازارِ آرام)  fade→")
    stat(good & (r1 > med1),  "R1 بالا (بازارِ پرنوسان) fade→")
    for thr in (0.9, 1.0, 1.1, 1.2, 1.3):
        stat(good & (r1 <= thr), f"R1<= {thr}")

    print("\n=== R3: |فاصله از EMA200| بر حسبِ ATR (کشش/ترند) ===")
    good3 = np.isfinite(r3abs)
    med3 = np.nanmedian(r3abs[good3])
    print(f"  median(|R3|)={med3:.3f}")
    for thr in (2, 3, 5, 8, 12):
        stat(good3 & (r3abs <= thr), f"|R3|<= {thr} (نزدیک به EMA200)")

    print("\n=== توزیعِ R1 بر حسبِ سال (آیا ۲۰۲۶ رژیمِ متفاوتی دارد؟) ===")
    for y in sorted(set(yr.astype(int))):
        m = yr == y
        print(f"  {y}: n={int(m.sum()):3d}  R1_mean={np.nanmean(r1[m]):.3f}  |R3|_mean={np.nanmean(r3abs[m]):.2f}  WR={win[m].mean()*100:5.1f}%")


if __name__ == '__main__':
    main()
