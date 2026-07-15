"""
اکتشاف: آیا شرطی پرفرکانس با P(win)>70% در RR متعادل/کم وجود دارد؟
هدف: حل تضاد «WR بالا ↔ فرکانس بالا». بدون قید session.
ایده‌ها: volatility regime، بازگشت به میانگین کوتاه‌مدت، فیلتر رژیم range.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
from backtest import load_data
import indicators as ind

df = load_data()
close = df['close'].values; high=df['high'].values; low=df['low'].values; o=df['open'].values
n=len(df)
atr = ind.atr(df,14).values
adx,pdi,mdi = ind.adx(df,14); adx=adx.values
rsi = ind.rsi(df['close'],14).values
ema50=ind.ema(df['close'],50).values; ema200=ind.ema(df['close'],200).values
bbl,bbm,bbu = ind.bollinger(df['close'],20,2.0); bbl,bbm,bbu=bbl.values,bbm.values,bbu.values
atr_ratio = (ind.atr(df,14)/ind.atr(df,14).rolling(50).mean()).values

def fwd(entry_i, direction, tp_mult, sl_mult, horizon=32):
    a=atr[entry_i]
    if np.isnan(a): return np.nan
    if direction=='long':
        tp=close[entry_i]+tp_mult*a; sl=close[entry_i]-sl_mult*a
        for j in range(entry_i+1,min(entry_i+1+horizon,n)):
            if high[j]>=tp: return 1
            if low[j]<=sl: return 0
    else:
        tp=close[entry_i]-tp_mult*a; sl=close[entry_i]+sl_mult*a
        for j in range(entry_i+1,min(entry_i+1+horizon,n)):
            if low[j]<=tp: return 1
            if high[j]>=sl: return 0
    return np.nan

def test(name, mask, direction, tp, sl, sample=1):
    ii=np.where(mask)[0]; ii=ii[(ii>300)&(ii<n-40)]
    if sample>1: ii=ii[::sample]
    if len(ii)==0: print(f"{name}: n=0"); return
    r=np.array([fwd(i,direction,tp,sl) for i in ii]); r=r[~np.isnan(r)]
    if len(r)==0: print(f"{name}: n=0"); return
    days=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    fulln=mask[(300<np.arange(n))&(np.arange(n)<n-40)].sum()
    print(f"{name}: n(test)={len(r)} full={fulln} P(win)={r.mean()*100:.2f}% ~{fulln/days:.2f}/day")

range_regime = adx<20  # رژیم رنج
trend_up = (close>ema50)&(ema50>ema200)

print("=== بازگشت به میانگین در رژیم رنج (RR متعادل 1:1) ===")
test("رنج + close<BBlower (long)", range_regime&(close<bbl), 'long',1.0,1.0)
test("رنج + close>BBupper (short)", range_regime&(close>bbu), 'short',1.0,1.0)
test("رنج + RSI<25 (long)", range_regime&(rsi<25),'long',1.0,1.0)
test("رنج + RSI>75 (short)", range_regime&(rsi>75),'short',1.0,1.0)

print("\n=== TP کوچک‌تر از SL برای WR بالا، اما در رژیم مناسب (TP0.8/SL1.2 BE=60%) ===")
test("رنج + close<BBlower (long)", range_regime&(close<bbl),'long',0.8,1.2)
test("رنج + RSI<30 (long)", range_regime&(rsi<30),'long',0.8,1.2)
test("رنج + RSI>70 (short)", range_regime&(rsi>70),'short',0.8,1.2)

print("\n=== volatility contraction (فشردگی نوسان) سپس بازگشت ===")
low_vol = atr_ratio<0.8
test("فشردگی + RSI<30 (long)", low_vol&(rsi<30),'long',1.0,1.0)
test("فشردگی + close<BBlower (long)", low_vol&(close<bbl),'long',1.0,1.0)

print("\n=== TP خیلی کوچک برای WR بالا (scalp TP0.5/SL1.0 BE=66.7%) در رژیم رنج ===")
test("رنج+RSI<30 long", range_regime&(rsi<30),'long',0.5,1.0)
test("رنج+RSI<20 long", range_regime&(rsi<20),'long',0.5,1.0)
test("رنج+BBlower long", range_regime&(close<bbl),'long',0.5,1.0)
