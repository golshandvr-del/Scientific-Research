"""
اعتبارسنجی نهایی S25 (AUGMENTED با weekly_rev):
  - پایداری در ۵ بلوک زمانی مساوی OOS
  - فرکانس واقعی معامله در روز (روش «روزهای فعال» مثل گزارش S14)
  - اهمیت feature (importance) weekly_rev در مدل
"""
import sys; sys.path.insert(0,'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS=6; MIN_TRAIN_FRAC=0.40
HZ=48; TP_M=1.0; SL_M=1.5; THRESH=0.68; SPREAD=0.20

df=load_data(); n=len(df); c=df['close'].values
atr=ind.atr(df,14); ema50=ind.ema(df['close'],50).values; ema200=ind.ema(df['close'],200).values

df['dow']=df['dt'].dt.dayofweek; df['date']=df['dt'].dt.date
df['dt_d']=pd.to_datetime(df['date'])
df['iso_year']=df['dt_d'].dt.isocalendar().year.values
df['iso_week']=df['dt_d'].dt.isocalendar().week.values
daily=df.groupby('date').agg(dow=('dow','first'),d_open=('open','first'),
                             d_close=('close','last'),iso_year=('iso_year','first'),
                             iso_week=('iso_week','first')).reset_index()
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

feats=build_features(df); feats['weekly_rev']=weekly_rev; feats['early_atr']=early_atr
cols=list(feats.columns)
cand=(c>ema50)&(ema50>ema200)&~np.isnan(atr.values)

def walk_forward(seed):
    y=make_target(df,HZ,TP_M,SL_M,atr,'long')
    data=feats.copy(); data['y']=y; data['cand']=cand
    valid=data.dropna(subset=cols+['y']); valid=valid[valid['cand']]
    X=valid[cols].values; Y=valid['y'].values.astype(int); idx=valid.index.values
    N=len(X); mt=int(N*MIN_TRAIN_FRAC); fold=(N-mt)//N_FOLDS
    proba=np.full(n,np.nan); imp=np.zeros(len(cols))
    for k in range(N_FOLDS):
        tr_end=mt+k*fold; te_end=tr_end+fold if k<N_FOLDS-1 else N
        m=lgb.LGBMClassifier(n_estimators=500,learning_rate=0.025,num_leaves=32,
            max_depth=6,subsample=0.8,colsample_bytree=0.75,min_child_samples=80,
            reg_lambda=2.0,random_state=seed,verbose=-1)
        m.fit(X[:tr_end],Y[:tr_end]); imp+=m.feature_importances_
        proba[idx[tr_end:te_end]]=m.predict_proba(X[tr_end:te_end])[:,1]
    return proba, imp

probas=[]; imps=np.zeros(len(cols))
for s in [42,7,123]:
    p,im=walk_forward(s); probas.append(p); imps+=im
ens=np.nanmean(np.vstack(probas),axis=0)

ent=cand & ~np.isnan(ens) & (ens>=THRESH)
s,tr=run_backtest(df,ent,None,None,'long',SPREAD,HZ,
                  sl_series=SL_M*atr.values,tp_series=TP_M*atr.values,allow_overlap=False)
nt=s['n_trades']
print("="*70)
print(f"S25 AUGMENTED نهایی: n={nt} WR={s['win_rate']:.2f}% exp={s['expectancy']:+.3f}$ "
      f"pnl={s['total_pnl']:+.1f}$")
be=SL_M/(TP_M+SL_M)*100
from scipy.stats import binomtest
wins=int(round(s['win_rate']/100*nt))
print(f"BE={be:.0f}% p(WR>BE)={binomtest(wins,nt,be/100,alternative='greater').pvalue:.4f}")

# فرکانس واقعی: معاملات به تفکیک روز
tr['entry_date']=df['dt'].iloc[tr['entry_bar'].values].dt.date.values
per_day=tr.groupby('entry_date').size()
active_days=len(per_day)
total_calendar_days=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days
# روزهای معاملاتی تقریبی = تعداد تاریخ‌های یکتای دیتاست
trading_days=df['date'].nunique()
print(f"\nفرکانس: معاملات={nt}, روزهای فعال={active_days}, "
      f"میانگین در روز فعال={per_day.mean():.2f}, median={per_day.median():.0f}")
print(f"روزهای معاملاتی کل دیتاست={trading_days}, "
      f"نرمال‌شده (nt/trading_days)={nt/trading_days:.2f} معامله/روز")
# چون مدل فقط روی OOS (۶۰٪ آخر داده) معامله می‌کند، فرکانس واقعی روی بازهٔ فعال:
oos_days=tr['entry_date'].nunique()
oos_span=(pd.to_datetime(tr['entry_date'].max())-pd.to_datetime(tr['entry_date'].min())).days
print(f"بازهٔ OOS: {oos_span} روز تقویمی, نرمال‌شده روی روزهای کاری={nt/oos_span*7/5:.2f}/روز")

# پایداری ۵ بلوک
print("\nپایداری در ۵ بلوک زمانی مساوی OOS:")
tr=tr.reset_index(drop=True)
blocks=np.array_split(tr,5)
for i,b in enumerate(blocks,1):
    w=(b['outcome']=='win').mean()*100
    print(f"  بلوک {i}: n={len(b)} WR={w:.2f}% exp={b['pnl'].mean():+.3f}$")

# اهمیت feature ها (top 15)
print("\nمهم‌ترین feature ها (importance تجمعی ۳ seed):")
imp_df=pd.DataFrame({'feat':cols,'imp':imps}).sort_values('imp',ascending=False)
for _,r in imp_df.head(15).iterrows():
    star=" <== زمانی جدید" if r['feat'] in ('weekly_rev','early_atr') else ""
    print(f"  {r['feat']:<20}{r['imp']:>8.0f}{star}")
wr_rank=imp_df.reset_index(drop=True)
pos=wr_rank[wr_rank['feat']=='weekly_rev'].index[0]+1
print(f"\nرتبهٔ weekly_rev در بین {len(cols)} feature: #{pos}")
print("تمام.")
