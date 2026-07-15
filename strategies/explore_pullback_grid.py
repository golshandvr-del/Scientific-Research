"""
کاوش شبکه‌ای: قانون ساده pullback-in-uptrend در پنجره طلایی.
هدف: یافتن ناحیه‌ای با WR>70%، exp>0، و n>500 (معناداری آماری).

منطق: در روند صعودی (close>ema50>ema200)، در پنجره طلایی، وقتی یک pullback کوچک
رخ می‌دهد (close زیر ema20 یا RSI افت کرده)، وارد long می‌شویم. drift مثبت سشن
+ روند صعودی باید احتمال برگشت به بالا را زیاد کند.
تست انبوه TP/SL برای یافتن ناحیه هدف.
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
ema20 = ind.ema(c,20).values
ema50 = ind.ema(c,50).values
ema200 = ind.ema(c,200).values
rsi14 = ind.rsi(c,14).values
n=len(df)
golden = np.isin(df['hour'].values,[19,20,21,22,23])
uptrend = (cv>ema50)&(ema50>ema200)

# تعریف چند نوع سیگنال pullback
signals = {
    'pull_ema20': golden & uptrend & (cv < ema20),
    'pull_rsi45': golden & uptrend & (rsi14 < 45),
    'pull_rsi40': golden & uptrend & (rsi14 < 40),
    'trend_only': golden & uptrend,
}

print("جاروب pullback-in-uptrend در پنجره طلایی")
print(f"{'signal':<14}{'TP':>4}{'SL':>5}{'BE%':>7}{'n':>7}{'WR%':>8}{'exp$':>9}{'pval':>8}")
print("-"*65)
for sname, sig in signals.items():
    for tp_m, sl_m in [(0.5,1.0),(0.7,1.2),(1.0,1.5),(1.0,1.8),(0.8,1.5),(1.0,2.0),(1.2,2.0)]:
        s,t = run_backtest(df, sig, None, None, 'long', spread=0.20, max_hold=32,
                sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
        if s['n_trades']<50: continue
        be=sl_m/(tp_m+sl_m)*100
        nt=s['n_trades']; wins=int(round(s['win_rate']/100*nt))
        pval=stats.binomtest(wins,nt,be/100,alternative='greater').pvalue
        flag=""
        if s['win_rate']>70 and s['expectancy']>0 and pval<0.05:
            flag=" <== SIGNIFICANT TARGET"
        elif s['win_rate']>70 and s['expectancy']>0:
            flag=" <-- target(not sig)"
        print(f"{sname:<14}{tp_m:>4.1f}{sl_m:>5.1f}{be:>7.1f}{nt:>7}"
              f"{s['win_rate']:>8.2f}{s['expectancy']:>9.3f}{pval:>8.3f}{flag}")
    print()
