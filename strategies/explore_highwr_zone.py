"""
جستجوی هدفمند ناحیه WR>70% با n بزرگ و exp>0.
منطق ریاضی: WR بالا با TP نسبتاً نزدیک به‌دست می‌آید. برای exp>0 در WR=72%،
کافی‌ست avg_win/avg_loss > 0.39. پس TP=0.5×SL تا 0.7×SL ناحیه هدف است.
اما باید مراقب تله استراتژی ۲ بود (TP خیلی کوچک + spread => exp منفی).
اینجا فیلتر سشن/روند/pullback را با TP در ناحیه بحرانی ترکیب می‌کنیم و
دقیقاً exp و WR را رصد می‌کنیم.
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
n=len(df)
golden = np.isin(df['hour'].values,[19,20,21,22,23])
uptrend = (cv>ema50)&(ema50>ema200)

def report(sname, sig, tp_m, sl_m, hz=48):
    s,t = run_backtest(df, sig, None, None, 'long', spread=0.20, max_hold=hz,
            sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
    if s['n_trades']<100: return None
    be=sl_m/(tp_m+sl_m)*100
    nt=s['n_trades']; wins=int(round(s['win_rate']/100*nt))
    pval=stats.binomtest(wins,nt,be/100,alternative='greater').pvalue
    flag=""
    if s['win_rate']>70 and s['expectancy']>0 and pval<0.05 and nt>=200:
        flag=" <<<=== WINNER"
    elif s['win_rate']>70 and s['expectancy']>0:
        flag=" <-- target"
    print(f"{sname:<18}{tp_m:>5.2f}{sl_m:>5.1f}{be:>6.1f}{nt:>6}"
          f"{s['win_rate']:>7.2f}{s['expectancy']:>8.3f}{pval:>8.3f}{flag}")
    return s

print(f"{'signal':<18}{'TP':>5}{'SL':>5}{'BE%':>6}{'n':>6}{'WR%':>7}{'exp$':>8}{'pval':>8}")
print("-"*70)
# ناحیه TP نزدیک (WR بالا) با SL بزرگ‌تر ولی نه افراطی -> WR>70% ممکن، exp کنترل‌شده
filters = {
    'gold+up': golden & uptrend,
    'gold+up+rsi<50': golden & uptrend & (rsi14<50),
    'gold+up+rsi<55': golden & uptrend & (rsi14<55),
}
# TP/SL طوری که BE حدود 66-70% باشد اما avg_win/avg_loss کافی برای exp>0
for sname,sig in filters.items():
    for tp_m,sl_m in [(1.0,2.0),(1.2,2.5),(1.5,3.0),(1.0,2.5),(1.5,2.5),(2.0,3.0),(1.0,3.0)]:
        report(sname,sig,tp_m,sl_m)
    print()
