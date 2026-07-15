"""
تحلیل اکتشافی: کدام نوع setup اکشن قیمت واقعاً edge دارد؟
بررسی می‌کنیم که پس از انواع رویدادهای ساختاری، توزیع بازده آینده چگونه است.
هدف: پیدا کردن یک شرط price-action که P(up) را معنادار از baseline بالا ببرد.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from backtest import load_data
import indicators as ind
import structure as st

df = load_data()
close = df['close'].values
high = df['high'].values
low = df['low'].values
o = df['open'].values
n = len(df)
hour = df['dt'].dt.hour.values

atr = ind.atr(df, 14).values
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
rsi = ind.rsi(df['close'], 14).values

piv = st.pivots(df, left=6, right=6)
sr = st.sr_levels(df, piv)
res = sr['resistance'].values
sup = sr['support'].values

# baseline: بازده افق h کندل جلوتر (برای long: آیا +1ATR قبل از -1ATR؟)
def fwd_updown(entry_i, tp_mult=1.0, sl_mult=1.0, horizon=48):
    a = atr[entry_i]
    if np.isnan(a): return np.nan
    tp = close[entry_i] + tp_mult*a
    sl = close[entry_i] - sl_mult*a
    for j in range(entry_i+1, min(entry_i+1+horizon, n)):
        if high[j] >= tp: return 1
        if low[j] <= sl: return 0
    return np.nan

# baseline کلی
idxs = np.arange(300, n-60)
base = np.array([fwd_updown(i) for i in idxs[::7]])
base = base[~np.isnan(base)]
print(f"BASELINE long P(TP1.0 before SL1.0) = {base.mean()*100:.2f}%  (n={len(base)})")

def test_condition(name, mask, tp_mult=1.0, sl_mult=1.0):
    ii = np.where(mask)[0]
    ii = ii[(ii>300)&(ii<n-60)]
    if len(ii)==0:
        print(f"{name}: n=0"); return
    r = np.array([fwd_updown(i, tp_mult, sl_mult) for i in ii])
    r = r[~np.isnan(r)]
    if len(r)==0:
        print(f"{name}: n=0"); return
    print(f"{name}: n={len(r)}  P(win)={r.mean()*100:.2f}%")

# نزدیکی به حمایت در روند صعودی (pullback به حمایت) — long
dist_sup = (close - sup)/atr
near_sup = (dist_sup > 0) & (dist_sup < 0.5)
uptrend = (close > ema50) & (ema50 > ema200)
golden = (hour>=19)&(hour<=23)

print("\n--- شرایط LONG (TP1.0/SL1.0) ---")
test_condition("نزدیک حمایت", near_sup)
test_condition("نزدیک حمایت + روند صعودی", near_sup & uptrend)
test_condition("نزدیک حمایت + روند صعودی + golden", near_sup & uptrend & golden)
test_condition("روند صعودی + golden (بدون S/R)", uptrend & golden)
test_condition("روند صعودی + golden + RSI<50", uptrend & golden & (rsi<50))
test_condition("روند صعودی + golden + RSI<40", uptrend & golden & (rsi<40))

# فاصله از مقاومت بالا (فضای زیاد تا مقاومت = پتانسیل رشد)
room = (res - close)/atr
test_condition("روند صعودی + golden + فضای>3ATR تا مقاومت", uptrend & golden & (room>3))
test_condition("روند صعودی + golden + نزدیک حمایت + فضای>2ATR", uptrend & golden & near_sup & (room>2))

print("\n--- با TP1.0/SL2.0 (BE=66.7%) ---")
test_condition("روند صعودی + golden + نزدیک حمایت", near_sup & uptrend & golden, 1.0, 2.0)
test_condition("روند صعودی + golden + RSI<45", uptrend & golden & (rsi<45), 1.0, 2.0)
test_condition("روند صعودی + golden + نزدیک حمایت + فضا>2ATR", uptrend & golden & near_sup & (room>2), 1.0, 2.0)
