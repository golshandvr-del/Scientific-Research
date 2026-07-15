"""
استراتژی ۲: آزمون عدم‌تقارن TP/SL (High Win-Rate Trap Study)

هدف: بررسی این فرضیه که آیا صرفاً با کوچک کردن TP و بزرگ کردن SL می‌توان
به Win Rate > 70% رسید، و آیا این استراتژی سودآور است.

ورود: mean-reversion ساده مبتنی بر RSI
- LONG: RSI(14) < 35
- SHORT: RSI(14) > 65
TP/SL: مضارب مختلف ATR (جاروب پارامتری)
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind

df = load_data()
close = df['close']
rsi = ind.rsi(close, 14)
atr = ind.atr(df, 14).values
long_sig = (rsi < 35).fillna(False).values
short_sig = (rsi > 65).fillna(False).values

print(f"{'TPx':>5}{'SLx':>5}{'dir':>6}{'trades':>8}{'WR%':>8}{'exp$':>9}{'PnL$':>10}")
for tpx, slx in [(0.5,2.0),(0.5,3.0),(1.0,3.0),(0.3,2.0)]:
    for sig, dr in [(long_sig,'long'),(short_sig,'short')]:
        s, t = run_backtest(df, sig, None, None, dr, spread=0.20, max_hold=100,
                            sl_series=slx*atr, tp_series=tpx*atr)
        print(f"{tpx:>5}{slx:>5}{dr:>6}{s['n_trades']:>8}{s['win_rate']:>8.1f}"
              f"{s['expectancy']:>9.3f}{s['total_pnl']:>10.1f}")
