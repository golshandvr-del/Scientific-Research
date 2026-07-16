"""
استراتژی ۴۴: گیتِ رژیمِ متعامدِ DXY روی مدل S25 (گروه G — دنبالهٔ S43)

یافتهٔ S43: DXY به‌صورت featureِ *موازی* اطلاعاتِ افزوده نداد (هم‌خطیِ اطلاعاتی
با قیمت طلا) — هرچند رتبهٔ اهمیتش بالا بود. قانون L22.

فرضیهٔ S44: DXY را به‌جای feature، به‌عنوان **گیتِ تأییدِ متعامد** به کار ببریم.
منطق: در رابطهٔ معکوس، سیگنالِ long روی طلا وقتی «تمیزتر» است که دلار هم‌زمان
**ضعیف/نزولی** باشد. اگر DXY صعودی باشد اما مدل بخواهد long بزند، آن سیگنال در
تضاد با نیروی کلانِ دلار است ⇒ کنار بگذاریم. این «کیفیتِ سیگنال» را بالا می‌برد
حتی اگر تعداد را کم کند (trade-off مورد انتظار: WR↑ ، tpd↓).

روش: احتمالِ S25 (ensemble ۳-seed) را یک‌بار می‌سازیم؛ سپس چند تعریفِ گیتِ DXY را
ارزان روی همان احتمال اعمال و A/B می‌کنیم. مدل و همه‌چیز جز گیت ثابت است.

گیت‌ها (همه بدون look-ahead — فقط از کندلِ بستهٔ DXY تا زمان سیگنال):
  G0  بدون گیت (= baseline S25)
  G1  dxy_slope_20 < 0         (روند کوتاه‌مدت دلار نزولی)
  G2  dxy_ret_16   < 0         (دلار در ۴ ساعت گذشته افت کرده)
  G3  dxy_above_ema200 == 0    (رژیم بلندمدت دلار نزولی)
  G4  dxy_slope_20 < 0 AND corr_96 < -0.3  (نزولی + رابطهٔ معکوسِ سالم/قوی)
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
HZ=48; TP_M=1.0; SL_M=1.5; THRESH=0.68; SPREAD=0.20
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

print("ساخت featureهای DXY برای گیت ...")
exo=build_exogenous_features(df)

cand=(c>ema50)&(ema50>ema200)&~np.isnan(atr.values)
print(f"کاندید (uptrend long): {int(cand.sum())}")

def walk_forward(seed):
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

print("محاسبهٔ احتمال S25 (ensemble ۳-seed) ...")
ens=np.zeros(n); cnt=np.zeros(n)
for sd in SEEDS:
    pr=walk_forward(sd); mask=~np.isnan(pr); ens[mask]+=pr[mask]; cnt[mask]+=1
    del pr; gc.collect()
ens=np.where(cnt>0, ens/np.maximum(cnt,1), np.nan)

# ---- گیت‌های DXY (بدون look-ahead؛ همگی از کندلِ بستهٔ فعلی) ----
slope=exo['dxy_slope_20'].values
ret16=exo['dxy_ret_16'].values
above200=exo['dxy_above_ema200'].values
corr96=exo['gold_dxy_corr_96'].values
# در نبودِ دادهٔ DXY (NaN)، گیت را «رد» می‌کنیم (محافظه‌کارانه: معامله نزن)
gates={
 'G0 بدون گیت (=S25)          ': np.ones(n,bool),
 'G1 dxy_slope<0              ': (slope<0),
 'G2 dxy_ret16<0              ': (ret16<0),
 'G3 dxy_below_ema200         ': (above200==0),
 'G4 slope<0 & corr96<-0.3    ': (slope<0)&(corr96<-0.3),
}

def evaluate(gate_mask,label):
    ent=cand & ~np.isnan(ens) & (ens>=THRESH) & gate_mask
    s,_=run_backtest(df,ent,None,None,'long',SPREAD,HZ,
        sl_series=SL_M*atr.values,tp_series=TP_M*atr.values,allow_overlap=False)
    nt=s['n_trades']
    if nt==0: print(f"{label}: no trades"); return
    span=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    tpd=nt/span*7/5; be=SL_M/(TP_M+SL_M)*100
    wins=int(round(s['win_rate']/100*nt))
    pv=binomtest(wins,nt,be/100,alternative='greater').pvalue
    pf=-(s['avg_win']*wins)/(s['avg_loss']*(nt-wins)) if (nt-wins)>0 and s['avg_loss']!=0 else float('inf')
    print(f"{label}: n={nt} WR={s['win_rate']:.2f}% exp={s['expectancy']:+.3f}$ "
          f"PF={pf:.3f} pnl={s['total_pnl']:+.0f}$ tpd={tpd:.2f} p={pv:.4f}")

print("\n=== A/B گیت‌های DXY روی احتمالِ ثابتِ S25 ===")
for label,mask in gates.items():
    evaluate(mask,label)
print("\nتمام.")
