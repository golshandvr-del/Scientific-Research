"""
یافتن نقطه شیرین: n متوسط (>=200) + WR>70% + exp>0 + p<0.05.
کاوش فیلترهای مختلف pullback با شدت متغیر، در پنجره طلایی و کل روز.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data(); df['hour']=df['dt'].dt.hour
atr = ind.atr(df,14); atr_arr=atr.values
c = df['close']; cv=c.values
ema50 = ind.ema(c,50).values
ema200 = ind.ema(c,200).values
rsi14 = ind.rsi(c,14).values
stoch_k,stoch_d = ind.stoch(df,14,3); sk=stoch_k.values
zscore20 = ind.zscore(c,20).values
n=len(df)
golden = np.isin(df['hour'].values,[19,20,21,22,23])
ext_golden = np.isin(df['hour'].values,[18,19,20,21,22,23])
uptrend = (cv>ema50)&(ema50>ema200)

def report(sname, sig, tp_m, sl_m, hz=32):
    s,t = run_backtest(df, sig, None, None, 'long', spread=0.20, max_hold=hz,
            sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
    if s['n_trades']<40: return
    be=sl_m/(tp_m+sl_m)*100
    nt=s['n_trades']; wins=int(round(s['win_rate']/100*nt))
    pval=stats.binomtest(wins,nt,be/100,alternative='greater').pvalue
    flag=""
    if s['win_rate']>70 and s['expectancy']>0 and pval<0.05 and nt>=150:
        flag=" <== SIGNIFICANT+ENOUGH_N"
    elif s['win_rate']>70 and s['expectancy']>0 and pval<0.05:
        flag=" <== SIGNIFICANT"
    elif s['win_rate']>70 and s['expectancy']>0:
        flag=" <-- target"
    print(f"{sname:<22}{tp_m:>4.1f}{sl_m:>5.1f}{be:>6.1f}{nt:>6}"
          f"{s['win_rate']:>7.2f}{s['expectancy']:>8.3f}{pval:>8.3f}{flag}")

print(f"{'signal':<22}{'TP':>4}{'SL':>5}{'BE%':>6}{'n':>6}{'WR%':>7}{'exp$':>8}{'pval':>8}")
print("-"*72)
# فیلترهای مختلف با شدت متغیر
filters = {
    'gold+up+rsi<42': golden & uptrend & (rsi14<42),
    'gold+up+rsi<45': golden & uptrend & (rsi14<45),
    'gold+up+rsi<48': golden & uptrend & (rsi14<48),
    'gold+up+stoch<30': golden & uptrend & (sk<30),
    'gold+up+stoch<40': golden & uptrend & (sk<40),
    'gold+up+z<-0.5': golden & uptrend & (zscore20<-0.5),
    'gold+up+z<0': golden & uptrend & (zscore20<0),
    'extgold+up+rsi<45': ext_golden & uptrend & (rsi14<45),
    'extgold+up+stoch<40': ext_golden & uptrend & (sk<40),
}
for sname,sig in filters.items():
    for tp_m,sl_m in [(1.0,1.5),(1.0,1.8),(1.0,2.0),(1.2,2.0)]:
        report(sname,sig,tp_m,sl_m)
    print()
