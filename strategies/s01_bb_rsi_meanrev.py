"""
استراتژی ۱: بازگشت به میانگین (Mean Reversion) با Bollinger Bands + RSI

منطق:
- LONG وقتی close زیر باند پایینی بولینگر و RSI < 30 (اشباع فروش)
- SHORT وقتی close بالای باند بالایی بولینگر و RSI > 70 (اشباع خرید)
- TP و SL بر مبنای ATR
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from backtest import load_data, run_backtest, summary_line
import indicators as ind

df = load_data()
close = df['close']
lo, mid, up = ind.bollinger(close, 20, 2.0)
rsi = ind.rsi(close, 14)
atr = ind.atr(df, 14)

# سیگنال‌ها
long_sig = (close < lo) & (rsi < 30)
short_sig = (close > up) & (rsi > 70)

atr_arr = atr.values
# TP = 1.5*ATR, SL = 1.5*ATR (RR = 1:1)
sl_series = 1.5 * atr_arr
tp_series = 1.5 * atr_arr

print("=== LONG ===")
sL, tL = run_backtest(df, long_sig.fillna(False).values, None, None, 'long',
                      spread=0.20, max_hold=100, sl_series=sl_series, tp_series=tp_series)
print(summary_line("BB_RSI_long", sL))

print("=== SHORT ===")
sS, tS = run_backtest(df, short_sig.fillna(False).values, None, None, 'short',
                      spread=0.20, max_hold=100, sl_series=sl_series, tp_series=tp_series)
print(summary_line("BB_RSI_short", sS))

# ترکیب
allt = pd.concat([tL, tS])
if len(allt):
    wr = (allt['outcome']=='win').mean()*100
    print(f"\n=== COMBINED === trades={len(allt)}, win_rate={wr:.2f}%, "
          f"total_pnl={allt['pnl'].sum():.1f}$, expectancy={allt['pnl'].mean():.3f}$")
