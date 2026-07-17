"""
explore_gold_h1_swing.py — اکتشافِ لایهٔ سومِ مستقلِ طلا روی H1 (نوسان‌گیریِ تایم‌فریمِ بالا)
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر». تعریف = XAUUSD + EURUSD.

انگیزهٔ نظری (از تحقیقِ فراکتال/Hurst در research/):
  «خود-تشابهیِ Mandelbrot» می‌گوید روند در همهٔ TFها هست اما با شدتِ متفاوت؛ و کشفِ
  Hurst نشان داد H (حافظهٔ روند) در افقِ بلندتر بزرگ‌تر است (DAX: H=0.54 روزانه →
  0.82 در ۵۰ روز). ⇒ روی H1 لبهٔ روند باید قوی‌تر/تمیزتر از M15/M5 باشد و هزینهٔ
  نسبی (اسپردِ 4pip روی حرکت‌های صدها-pipیِ H1) ناچیز شود.

  S67 روی M15 و S79 روی M5 است. H1 یک تایم‌فریمِ کاملاً مستقل با همبستگیِ پایین
  است ⇒ کاندیدِ ایده‌آل برای لایهٔ سومِ پرتفوی (مثلِ روشِ S79).

این اسکریپت trend-pullback (منطقِ برندهٔ S79) را روی H1 جارو می‌کند و پایداری را
در دو نیمه و چارَک‌ها می‌سنجد. هزینهٔ واقعیِ طلا: spread=4pip(0.40$), comm=0.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

SE.ASSETS['XAUUSD_H1'] = dict(file='data/XAUUSD_H1.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
ASSET = 'XAUUSD_H1'
df = SE.load_data(SE.ASSETS[ASSET]['file'])
n = len(df)
print("=" * 100)
print(f"  XAUUSD H1 — اکتشافِ نوسان‌گیریِ trend-pullback (n={n}, {df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
print("=" * 100)

def ema(x, s): return pd.Series(x).ewm(span=s, adjust=False).mean().values
def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up=np.where(d>0,d,0); dn=np.where(d<0,-d,0)
    ru=pd.Series(up).ewm(alpha=1/p,adjust=False).mean().values
    rd=pd.Series(dn).ewm(alpha=1/p,adjust=False).mean().values
    return 100-100/(1+ru/(rd+1e-12))

c = df['close'].values

def build(ema_f, ema_s, rsi_p, rsi_th, side='long'):
    ef=ema(c,ema_f); es=ema(c,ema_s); r=rsi(c,rsi_p)
    if side=='long':
        ls=np.nan_to_num((ef>es)&(r<rsi_th)).astype(bool); ss=np.zeros(n,bool)
    else:
        ss=np.nan_to_num((ef<es)&(r>rsi_th)).astype(bool); ls=np.zeros(n,bool)
    return ls,ss

def ev(ema_f,ema_s,rsi_p,rsi_th,sl,tp,hold,side='long'):
    ls,ss=build(ema_f,ema_s,rsi_p,rsi_th,side)
    tr=SE.simulate_trades(df,ls,ss,sl,tp,ASSET,max_hold=hold)
    if len(tr)==0: return None
    s,_=SE.run_capital(tr,ASSET,compounding=False)
    half=n//2
    s1,_=SE.run_capital(tr[tr['entry_bar']<half],ASSET,compounding=False)
    s2,_=SE.run_capital(tr[tr['entry_bar']>=half],ASSET,compounding=False)
    return s,s1,s2

# روی H1: SL/TP باید بزرگ‌تر باشند (حرکت‌های بزرگ‌تر). واحد: pip=0.10$ → 100pip=10$
print("\n--- جاروی Long trend-pullback (EMA20>EMA100, RSI<th) ---")
best=None
for rsi_th in [30,35,40]:
    for sl in [150,250,350]:
        for tp in [300,500,700,1000]:
            for hold in [24,48,72]:
                res=ev(20,100,14,rsi_th,sl,tp,hold,'long')
                if res is None: continue
                s,s1,s2=res
                both=s1['net_profit']>0 and s2['net_profit']>0
                if best is None or s['net_profit']>best[0]['net_profit']:
                    best=(s,s1,s2,rsi_th,sl,tp,hold)
                if both and s['net_profit']>3000:
                    print(f"  RSI<{rsi_th} SL={sl} TP={tp} hold={hold}: net={s['net_profit']:+7.0f}$ "
                          f"n={s['n_trades']:4d} WR={s['win_rate']:4.1f}% PF={s['profit_factor']:.2f} "
                          f"H1={s1['net_profit']:+.0f} H2={s2['net_profit']:+.0f} ✅")
if best:
    s,s1,s2,rt,sl,tp,hold=best
    print(f"\n  ★ بهترین Long: RSI<{rt} SL={sl} TP={tp} hold={hold} → net={s['net_profit']:+.0f}$ "
          f"n={s['n_trades']} WR={s['win_rate']:.1f}% PF={s['profit_factor']:.2f} "
          f"DD={s['max_dd_pct']:.1f}% H1={s1['net_profit']:+.0f} H2={s2['net_profit']:+.0f}")
