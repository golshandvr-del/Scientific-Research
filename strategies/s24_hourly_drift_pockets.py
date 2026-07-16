"""
استراتژی ۲۴: Directional Hourly-Drift Pockets (اثر زمانی ساعت×روز)

پایه (از explore_time_dow.py، بخش ۴):
  چند «جیب» (DOW × ساعت) با P(up) خام بالای ۶۰٪ و p<0.001 پیدا شد، مثل:
    Wed h23: P(up)=62.0% (n=1212), Mon h23: P(up)=58.4% (n=1108),
    Wed h22: 56.7%, Fri h22: 54.3% ...
  این‌ها در سطح «جهت خام کندل آینده» بودند. حالا بررسی می‌کنیم آیا با یک
  معاملهٔ واقعی (SL/TP، اسپرد، بدون look-ahead) هم WR>60 می‌دهند و — مهم‌تر —
  آیا در تقسیم IN-SAMPLE / OUT-OF-SAMPLE پایدارند یا صرفاً cherry-pick اند.

روش ضدِ overfitting:
  1. جیب‌ها را فقط روی نیمهٔ اول داده (train) کشف می‌کنیم (P(up)>threshold, p<0.01).
  2. همان جیب‌ها را روی نیمهٔ دوم (test/OOS) بدون تغییر بک‌تست می‌کنیم.
  3. فقط اگر WR در OOS هم >60 و exp>0 بماند، edge واقعی است.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data()
df['dow']=df['dt'].dt.dayofweek; df['hour']=df['dt'].dt.hour
c=df['close'].values; n=len(df)
atr=ind.atr(df,14).values
DOW=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

split=n//2
train_mask=np.zeros(n,bool); train_mask[:split]=True
test_mask=~train_mask

# forward direction (8-candle) برای کشف جیب
ret8=np.full(n,np.nan); ret8[:-8]=c[8:]-c[:-8]

print("="*80)
print("S24: کشف جیب‌های ساعتی روی TRAIN، اعتبارسنجی روی OOS")
print("="*80)

# ---- گام ۱: کشف جیب‌های صعودی و نزولی روی TRAIN ----
pockets=[]
for d in range(5):
    for hr in range(24):
        m=train_mask&(df['dow'].values==d)&(df['hour'].values==hr)&~np.isnan(ret8)
        if m.sum()<200: continue
        rr=ret8[m]; pup=np.mean(rr>0)*100
        t,p=stats.ttest_1samp(rr,0)
        if p<0.02 and (pup>=58 or pup<=42):
            direction='long' if pup>50 else 'short'
            pockets.append((d,hr,direction,m.sum(),pup,p))

print(f"\nجیب‌های کشف‌شده روی TRAIN (p<0.02 و P(up) دور از ۵۰):")
for d,hr,dr,nn,pup,p in pockets:
    print(f"  {DOW[d]} h{hr:02d} -> {dr:5s}  train:P(up)={pup:.1f}% n={nn} p={p:.4f}")

if not pockets:
    print("هیچ جیب معناداری روی TRAIN یافت نشد."); sys.exit()

# ---- گام ۲: بک‌تست همان جیب‌ها با SL/TP روی TRAIN و OOS جداگانه ----
def run_pocket_set(pockets, seg_mask, tp_m, sl_m, max_hold):
    long_sig=np.zeros(n,bool); short_sig=np.zeros(n,bool)
    for d,hr,dr,_,_,_ in pockets:
        sel=seg_mask&(df['dow'].values==d)&(df['hour'].values==hr)
        if dr=='long': long_sig|=sel
        else: short_sig|=sel
    sL,_=run_backtest(df,long_sig,None,None,'long',0.20,max_hold,
                      sl_series=sl_m*atr,tp_series=tp_m*atr,allow_overlap=False)
    sS,_=run_backtest(df,short_sig,None,None,'short',0.20,max_hold,
                      sl_series=sl_m*atr,tp_series=tp_m*atr,allow_overlap=False)
    nn=sL['n_trades']+sS['n_trades']
    if nn==0: return None
    w=sL['win_rate']/100*sL['n_trades']+sS['win_rate']/100*sS['n_trades']
    pnl=sL['total_pnl']+sS['total_pnl']
    return dict(n=nn,wr=w/nn*100,exp=pnl/nn,pnl=pnl,nL=sL['n_trades'],nS=sS['n_trades'])

print("\nبک‌تست جیب‌ها با SL/TP — مقایسهٔ TRAIN vs OOS")
print(f"{'tp':>4}{'sl':>5}{'BE%':>6}  | {'TRAIN: n/WR%/exp':<28} | {'OOS: n/WR%/exp':<28}")
print("-"*80)
for tp_m,sl_m in [(1.0,1.0),(1.0,1.3),(1.0,1.5),(1.5,1.0),(0.8,1.2),(1.2,1.5)]:
    for max_hold in [8,16,32]:
        tr=run_pocket_set(pockets,train_mask,tp_m,sl_m,max_hold)
        oos=run_pocket_set(pockets,test_mask,tp_m,sl_m,max_hold)
        if tr is None or oos is None: continue
        be=sl_m/(tp_m+sl_m)*100
        flag=""
        if oos['wr']>60 and oos['exp']>0: flag=" <== OOS WR>60 & exp>0 !!"
        print(f"{tp_m:>4.1f}{sl_m:>5.1f}{be:>6.1f}  | "
              f"n={tr['n']:<5} WR={tr['wr']:.1f}% exp={tr['exp']:+.3f}    | "
              f"n={oos['n']:<5} WR={oos['wr']:.1f}% exp={oos['exp']:+.3f}{flag}")

print("\nتمام.")
