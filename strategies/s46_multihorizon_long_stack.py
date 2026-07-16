"""
استراتژی ۴۶: تراکمِ چند-افقیِ مغزِ long باکیفیت (گروه G — دنبالهٔ S44/S45)

انگیزه: S44/G3 بهترین کیفیتِ long را داد (exp+0.71, PF1.27) اما tpd~0.86.
S45 نشان داد افزودنِ جهتِ ضعیف (short) WR را قربانی می‌کند (L24). پس به‌جای
جهتِ جدید، **تعدادِ سیگنالِ همان مغزِ long باکیفیت** را بالا می‌بریم.

روش: سه مدلِ ML موازی با **افق‌های متفاوت** (HZ=24/48/96 کندل، هرکدام TP/SL
متناسبِ خودش) روی همان کاندیدِ باکیفیتِ «uptrend AND DXY<EMA200» می‌سازیم. هر
افق در لحظاتِ متفاوتی سیگنال می‌دهد (کوتاه‌مدت زودتر، بلندمدت دیرتر) ⇒ جریان‌های
زمانیِ نیمه‌مستقل که tpd را جمع می‌کنند. چون همگی از رژیمِ باکیفیتِ G3 می‌آیند،
انتظارِ حفظِ WR داریم.

هر افق پرتفویِ مستقلِ خودش را بک‌تست می‌کند (allow_overlap=False درونِ افق)، سپس
سه جریان ادغام و مجموعاً ارزیابی می‌شوند. این «تراکمِ زمانی» است، نه «جهتِ جدید».
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
SPREAD=0.20; THRESH=0.66; SEEDS=[42,7,123]
# سه افق با TP/SL متناسب (همه RR≈1:1.5 مثل S25)
HORIZONS=[(24,1.0,1.5),(48,1.0,1.5),(96,1.2,1.8)]

df=load_data(); df['dt']=pd.to_datetime(df['time'],unit='s')
n=len(df); c=df['close'].values
atr=ind.atr(df,14)
ema50=ind.ema(df['close'],50).values; ema200=ind.ema(df['close'],200).values

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

print("ساخت featureهای DXY (گیتِ G3) ...")
exo=build_exogenous_features(df)
dxy_below=(exo['dxy_above_ema200'].values==0)
cand=(c>ema50)&(ema50>ema200)&~np.isnan(atr.values)&dxy_below
print(f"کاندید long باکیفیت (uptrend & DXY<EMA200): {int(cand.sum())}")

def walk_forward(HZ,TP_M,SL_M,seed):
    y=make_target(df,HZ,TP_M,SL_M,atr,'long')
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

def report(name,nt,wr,exp,pf,pnl,tpd,pv):
    print(f"{name}: n={nt} WR={wr:.2f}% exp={exp:+.3f}$ PF={pf:.3f} pnl={pnl:+.0f}$ tpd={tpd:.2f} p={pv:.4f}")

span=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days
all_trades=[]
print("\n=== هر افق جداگانه ===")
for HZ,TP_M,SL_M in HORIZONS:
    e=np.zeros(n); cnt=np.zeros(n)
    for sd in SEEDS:
        pr=walk_forward(HZ,TP_M,SL_M,sd); mask=~np.isnan(pr); e[mask]+=pr[mask]; cnt[mask]+=1
        del pr; gc.collect()
    proba=np.where(cnt>0,e/np.maximum(cnt,1),np.nan)
    ent=cand & ~np.isnan(proba) & (proba>=THRESH)
    s,tr=run_backtest(df,ent,None,None,'long',SPREAD,HZ,
        sl_series=SL_M*atr.values,tp_series=TP_M*atr.values,allow_overlap=False)
    nt=s['n_trades']
    if nt>0:
        tr=tr.copy(); tr['hz']=HZ; all_trades.append(tr)
        be=SL_M/(TP_M+SL_M)*100; wins=int(round(s['win_rate']/100*nt))
        pv=binomtest(wins,nt,be/100,alternative='greater').pvalue
        pf=-(s['avg_win']*wins)/(s['avg_loss']*(nt-wins)) if (nt-wins)>0 and s['avg_loss']!=0 else float('inf')
        report(f'HZ={HZ:3d} TP={TP_M} SL={SL_M}',nt,s['win_rate'],s['expectancy'],pf,s['total_pnl'],nt/span*7/5,pv)

# ادغام: اگر یک کندل در چند افق سیگنال داشت، هر معامله جدا شمرده می‌شود
# (در عمل نزدیک هم‌اند؛ اما جریان‌های زمانیِ متفاوت tpd را بالا می‌برند)
print("\n=== پرتفویِ چند-افقی (ادغامِ سه جریان) ===")
allt=pd.concat(all_trades,ignore_index=True) if all_trades else pd.DataFrame()
if len(allt)>0:
    # حذفِ معاملاتِ کاملاً تکراری (همان entry_bar در چند افق) تا دوباره‌شماری نشود
    allt=allt.sort_values('entry_bar').drop_duplicates(subset=['entry_bar'],keep='first')
    nt=len(allt); wins=int((allt['outcome']=='win').sum()); wr=wins/nt*100
    exp=allt['pnl'].mean(); pnl=allt['pnl'].sum()
    aw=allt[allt.outcome=='win']['pnl'].mean(); al=allt[allt.outcome=='loss']['pnl'].mean()
    pf=-(aw*wins)/(al*(nt-wins)) if (nt-wins)>0 and al!=0 else float('inf')
    tpd=nt/span*7/5; pv=binomtest(wins,nt,0.6,alternative='greater').pvalue
    report('PORTFOLIO (dedup entry_bar)',nt,wr,exp,pf,pnl,tpd,pv)
print("\nتمام.")
