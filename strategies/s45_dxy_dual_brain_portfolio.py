"""
استراتژی ۴۵: پرتفویِ دو-مغزه با گیتِ رژیمِ متقارنِ DXY (گروه G — اوجِ مسیر G)

انگیزه (از S44): گیتِ G3 «DXY<EMA200» کیفیتِ long را بالا برد (exp+0.71, PF1.27)
اما tpd فقط ۰.۸۶ بود — چون تک‌جهت است. هدفِ کاربر «≥۵ معامله/روز» با یک مغزِ
long-only شدنی نیست. راه‌حل: **دو مغزِ متقارن که تعدادشان جمع می‌شود.**

معماریِ متقارن (هر دو با تأییدِ رژیمِ DXY):
  • مغزِ صعودی (LONG):  طلا صعودی (close>EMA50>EMA200) AND دلار نزولی (DXY<EMA200)
  • مغزِ نزولی (SHORT): طلا نزولی (close<EMA50<EMA200) AND دلار صعودی (DXY>EMA200)

هر مغز مدلِ ML مستقلِ خودش را دارد (long-target / short-target)، با همان
Recipe-S25. سپس معاملاتِ دو مغز در یک پرتفویِ زمانی ادغام و مجموعاً ارزیابی می‌شوند
تا WR/PF/tpd کلِ سیستم به‌دست آید (نه هر مغز جدا).

فرضیه: جمعِ دو جریانِ باکیفیت، tpd را ~۲برابر می‌کند و چون هر دو گیتِ رژیمِ
بلندمدتِ DXY دارند، WR بالا می‌ماند.
"""
import sys, gc; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from exogenous import build_exogenous_features
import warnings; warnings.filterwarnings('ignore')

N_FOLDS=6; MIN_TRAIN_FRAC=0.40
HZ=48; TP_M=1.0; SL_M=1.5; THRESH=0.66; SPREAD=0.20
SEEDS=[42,7,123]

df=load_data(); df['dt']=pd.to_datetime(df['time'],unit='s')
n=len(df); c=df['close'].values
atr=ind.atr(df,14)
ema50=ind.ema(df['close'],50).values; ema200=ind.ema(df['close'],200).values

# featureهای زمانی S25
df['dow']=df['dt'].dt.dayofweek; df['date']=df['dt'].dt.date
df['dt_d']=pd.to_datetime(df['date'])
df['iso_year']=df['dt_d'].dt.isocalendar().year.values
df['iso_week']=df['dt_d'].dt.isocalendar().week.values
daily=df.groupby('date').agg(dow=('dow','first'),d_open=('open','first'),
    d_close=('close','last'),iso_year=('iso_year','first'),iso_week=('iso_week','first')).reset_index()
em={}
for (yr,wk),g in daily.groupby(['iso_year','iso_week']):
    g=g.sort_values('date'); e=g[g['dow'].isin([0,1,2])]
    if len(e)==0: continue
    em[(yr,wk)]=e['d_close'].iloc[-1]-e['d_open'].iloc[0]
df['early']=df.apply(lambda r:em.get((r['iso_year'],r['iso_week']),np.nan),axis=1)
atr_daily=atr.rolling(96).mean().values
early_atr=df['early'].values/(atr_daily+1e-9)
day_w=df['dow'].map({0:0.2,1:0.3,2:0.5,3:1.0,4:0.9,5:0,6:0}).values
weekly_rev=-np.sign(df['early'].values)*np.clip(np.abs(early_atr),0,3)*day_w

print("ساخت featureهای S25 ...")
feats=build_features(df); feats['weekly_rev']=weekly_rev; feats['early_atr']=early_atr
cols=list(feats.columns)

print("ساخت featureهای DXY (برای گیتِ رژیم) ...")
exo=build_exogenous_features(df)
dxy_below=(exo['dxy_above_ema200'].values==0)   # دلار نزولیِ بلندمدت
dxy_above=(exo['dxy_above_ema200'].values==1)   # دلار صعودیِ بلندمدت

cand_long =(c>ema50)&(ema50>ema200)&~np.isnan(atr.values)&dxy_below
cand_short=(c<ema50)&(ema50<ema200)&~np.isnan(atr.values)&dxy_above
print(f"کاندید long (طلا↑ & دلار↓): {int(cand_long.sum())}")
print(f"کاندید short (طلا↓ & دلار↑): {int(cand_short.sum())}")

def walk_forward(cand, direction, seed):
    y=make_target(df,HZ,TP_M,SL_M,atr,direction)
    data=feats[cols].copy(); data['y']=y; data['cand']=cand
    valid=data.dropna(subset=cols+['y']); valid=valid[valid['cand']]
    X=valid[cols].values.astype(np.float32); Y=valid['y'].values.astype(int); idx=valid.index.values
    del data,valid; gc.collect()
    N=len(X); mt=int(N*MIN_TRAIN_FRAC); fold=(N-mt)//N_FOLDS
    proba=np.full(n,np.nan)
    for k in range(N_FOLDS):
        tr_end=mt+k*fold; te_end=tr_end+fold if k<N_FOLDS-1 else N
        m=lgb.LGBMClassifier(n_estimators=500,learning_rate=0.025,num_leaves=32,
            max_depth=6,subsample=0.8,colsample_bytree=0.75,min_child_samples=80,
            reg_lambda=2.0,random_state=seed,verbose=-1,n_jobs=1)
        m.fit(X[:tr_end],Y[:tr_end]); proba[idx[tr_end:te_end]]=m.predict_proba(X[tr_end:te_end])[:,1]
        del m; gc.collect()
    del X,Y; gc.collect(); return proba

def ensemble(cand,direction):
    e=np.zeros(n); cnt=np.zeros(n)
    for sd in SEEDS:
        pr=walk_forward(cand,direction,sd); mask=~np.isnan(pr); e[mask]+=pr[mask]; cnt[mask]+=1
        del pr; gc.collect()
    return np.where(cnt>0,e/np.maximum(cnt,1),np.nan)

print("مغزِ صعودی (LONG) ...")
p_long=ensemble(cand_long,'long')
print("مغزِ نزولی (SHORT) ...")
p_short=ensemble(cand_short,'short')

# ---- بک‌تستِ هر مغز جدا، سپس ادغامِ پرتفویی ----
def bt(cand,proba,direction):
    ent=cand & ~np.isnan(proba) & (proba>=THRESH)
    s,tr=run_backtest(df,ent,None,None,direction,SPREAD,HZ,
        sl_series=SL_M*atr.values,tp_series=TP_M*atr.values,allow_overlap=False)
    return s,tr

sL,trL=bt(cand_long,p_long,'long')
sS,trS=bt(cand_short,p_short,'short')

def report(name,s,tr):
    nt=s['n_trades']
    if nt==0: print(f"{name}: no trades"); return None
    span=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    tpd=nt/span*7/5; be=SL_M/(TP_M+SL_M)*100
    wins=int(round(s['win_rate']/100*nt))
    pv=binomtest(wins,nt,be/100,alternative='greater').pvalue
    pf=-(s['avg_win']*wins)/(s['avg_loss']*(nt-wins)) if (nt-wins)>0 and s['avg_loss']!=0 else float('inf')
    print(f"{name}: n={nt} WR={s['win_rate']:.2f}% exp={s['expectancy']:+.3f}$ "
          f"PF={pf:.3f} pnl={s['total_pnl']:+.0f}$ tpd={tpd:.2f} p={pv:.4f}")
    return dict(n=nt,wr=s['win_rate'],exp=s['expectancy'],pf=pf,pnl=s['total_pnl'],tpd=tpd,pv=pv)

print("\n=== نتایجِ هر مغز ===")
report('LONG  brain (طلا↑ دلار↓)',sL,trL)
report('SHORT brain (طلا↓ دلار↑)',sS,trS)

# ادغامِ پرتفویی: همهٔ معاملاتِ دو مغز را کنار هم می‌گذاریم
print("\n=== پرتفویِ ادغام‌شده (دو مغز با هم) ===")
allt=pd.concat([trL,trS],ignore_index=True) if len(trL)+len(trS)>0 else pd.DataFrame()
if len(allt)>0:
    nt=len(allt); wins=int((allt['outcome']=='win').sum())
    wr=wins/nt*100; exp=allt['pnl'].mean(); pnl=allt['pnl'].sum()
    aw=allt[allt.outcome=='win']['pnl'].mean(); al=allt[allt.outcome=='loss']['pnl'].mean()
    pf=-(aw*wins)/(al*(nt-wins)) if (nt-wins)>0 and al!=0 else float('inf')
    span=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days; tpd=nt/span*7/5
    be=SL_M/(TP_M+SL_M)*100; pv=binomtest(wins,nt,be/100,alternative='greater').pvalue
    print(f"PORTFOLIO: n={nt} WR={wr:.2f}% exp={exp:+.3f}$ PF={pf:.3f} "
          f"pnl={pnl:+.0f}$ tpd={tpd:.2f} p(WR>60)={pv:.4f}")
print("\nتمام.")
