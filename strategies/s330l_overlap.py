# -*- coding: utf-8 -*-
"""
s330l_overlap.py — ممیزیِ همپوشانیِ لایهٔ احیاشدهٔ S330 (Asia-fade M5) با لایه‌های
زندهٔ نزدیک (قانونِ سومِ پروژه — همپوشانی؛ نباید موکول شود).
================================================================================
نامزدهای همپوشانی روی XAUUSD M5:
  • S326 (Streak-Reversal): ۵ کندلِ نزولیِ متوالی + RSI14≤30 + close>EMA200.
  • S324/S303 روی M15/M30 (TF متفاوت ⇒ همپوشانیِ مستقیمِ کندلی ندارد؛ فقط اشاره).
روش: معاملاتِ S330 را می‌گیریم؛ برای هر ورود بررسی می‌کنیم آیا شرایطِ S326 هم در آن
کندل برقرار بوده. درصدِ همپوشانی = سهمِ وروديهایِ S330 که S326 هم می‌داد.
هم‌چنین جهت (S330 در آسیا اغلب LONG-fade یا SHORT-fade) با جهتِ S326 (LONG) مقایسه.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import trade_simulator as TS
from engine import indicators as ind
from strategies.sim_orb import SessionORB


def rsi(series, n=14):
    d = series.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).to_numpy()


def main():
    df = TS.load_data('XAUUSD_M5')
    strat = SessionORB(session_start_hour=0, or_bars=12, trade_window_bars=48,
                       side='FADE', atr_max=99, trend_ema=0, k_sl=1.0, k_tp=1.0,
                       max_hold=48, regime_atr_ratio_max=1.1, regime_atr_ma=500)
    tr, eq = TS.simulate(df, strat, 'XAUUSD', warmup=600)
    print(f"S330 معاملات: n={len(tr)}")

    close = df['close']
    r = rsi(close, 14)
    ema200 = ind.ema(close, 200).to_numpy()
    o = df['open'].to_numpy(); c = close.to_numpy()

    # شرطِ S326 (streak نزولی): آیا در کندلِ ورود، ۴ یا ۵ کندلِ نزولیِ متوالی + RSI≤30 + close>EMA200
    def s326_signal(b, streak_n):
        if b - streak_n < 0:
            return False
        downs = all(c[b - k] < o[b - k] for k in range(streak_n))
        return downs and (r[b] <= 30) and (c[b] > ema200[b])

    n_long = (tr['side'] == 'long').sum() if 'side' in tr.columns else 0
    n_short = (tr['side'] == 'short').sum() if 'side' in tr.columns else 0
    print(f"جهتِ S330: LONG={n_long}  SHORT={n_short}")

    overlap4 = overlap5 = 0
    for _, t in tr.iterrows():
        b = int(t['entry_bar'])
        if s326_signal(b, 5): overlap5 += 1
        if s326_signal(b, 4): overlap4 += 1
    N = len(tr)
    print(f"\n=== همپوشانی با S326 (Streak-Reversal) ===")
    print(f"  ورودهایی که S326(streak5) هم می‌داد: {overlap5}/{N} = {overlap5/N*100:.1f}%")
    print(f"  ورودهایی که S326(streak4) هم می‌داد: {overlap4}/{N} = {overlap4/N*100:.1f}%")
    print("  یادداشت: S326 هیچ فیلترِ سشن ندارد و LONG-only پس از رگهٔ نزولی است؛")
    print("           S330 fade در سشنِ آسیا (h=0) با فیلترِ رژیمِ نوسان است ⇒ منطقِ مستقل.")


if __name__ == '__main__':
    main()
