"""
استراتژی ۲۵: ML + Weekly-Reversion Context Feature (تلفیق یافتهٔ زمانی با ML)

انگیزه: استراتژی ۲۳ نشان داد اثر mean-reversion هفتگی (corr=-0.217, p<0.001)
یک منبع اطلاعاتی معنادار است اما خام به WR>60 نمی‌رسد. استراتژی ۲۴ نشان داد
جیب‌های ساعتی overfit اند. طبق درس پروژه، راه اصلی پیشرفت افزودن یک منبع
اطلاعاتی جدید به مدل ML برنده (S14) است.

این استراتژی یک feature زمانی جدید می‌سازد:
    weekly_rev = -sign(early_move) * |early_move|/atr_daily * day_weight
که «فشار برگشت هفتگی» را کمی‌سازی می‌کند (در Thu/Fri وزن بالاتر). سپس آن را به
مجموعهٔ کامل feature های S14 اضافه کرده و با همان Walk-Forward/Ensemble بک‌تست
می‌کند. آزمون A/B: baseline (بدون feature زمانی) در برابر augmented (با آن).

هدف: آیا feature زمانی WR یا expectancy یا فرکانس را نسبت به S14 بهبود می‌دهد؟
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS=6; MIN_TRAIN_FRAC=0.40
HZ=48; TP_M=1.0; SL_M=1.5; THRESH=0.68; SPREAD=0.20

df=load_data()
n=len(df)
c=df['close'].values
atr=ind.atr(df,14)
ema50=ind.ema(df['close'],50).values
ema200=ind.ema(df['close'],200).values

# ---- ساخت feature زمانی جدید: weekly reversion pressure ----
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
# وزن روز: Thu/Fri بالاترین (اثر برگشت آنجا قوی‌تر بود)، Mon-Wed کم
day_w=df['dow'].map({0:0.2,1:0.3,2:0.5,3:1.0,4:0.9,5:0,6:0}).values
weekly_rev = -np.sign(df['early'].values) * np.clip(np.abs(early_atr),0,3) * day_w
df['weekly_rev']=weekly_rev

print("ساخت feature ها ...")
feats=build_features(df)
feats_aug=feats.copy()
feats_aug['weekly_rev']=weekly_rev
feats_aug['early_atr']=early_atr

# کاندید پایه مثل S14: روند صعودی long-only
cand = (c>ema50)&(ema50>ema200)
cand = cand & ~np.isnan(atr.values)
print(f"کاندید پایه (uptrend long): {int(cand.sum())}")

base_cols=[col for col in feats.columns]
aug_cols=base_cols+['weekly_rev','early_atr']

def walk_forward(feature_df, fc, seed=42):
    y=make_target(df,HZ,TP_M,SL_M,atr,'long')
    data=feature_df.copy(); data['y']=y; data['cand']=cand
    valid=data.dropna(subset=fc+['y']); valid=valid[valid['cand']]
    X=valid[fc].values; Y=valid['y'].values.astype(int); idx=valid.index.values
    N=len(X); mt=int(N*MIN_TRAIN_FRAC); fold=(N-mt)//N_FOLDS
    proba=np.full(n,np.nan)
    for k in range(N_FOLDS):
        tr_end=mt+k*fold; te_end=tr_end+fold if k<N_FOLDS-1 else N
        m=lgb.LGBMClassifier(n_estimators=500,learning_rate=0.025,num_leaves=32,
            max_depth=6,subsample=0.8,colsample_bytree=0.75,min_child_samples=80,
            reg_lambda=2.0,random_state=seed,verbose=-1)
        m.fit(X[:tr_end],Y[:tr_end])
        proba[idx[tr_end:te_end]]=m.predict_proba(X[tr_end:te_end])[:,1]
    return proba

def evaluate(proba, label):
    ent=cand & ~np.isnan(proba) & (proba>=THRESH)
    s,_=run_backtest(df,ent,None,None,'long',SPREAD,HZ,
                     sl_series=SL_M*atr.values,tp_series=TP_M*atr.values,allow_overlap=False)
    nt=s['n_trades']
    if nt==0:
        print(f"{label}: no trades"); return None
    # فرکانس معامله/روز نرمال‌شده
    span_days=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    tpd=nt/span_days*7/5  # نرمال به روزهای کاری
    be=SL_M/(TP_M+SL_M)*100
    from scipy.stats import binomtest
    wins=int(round(s['win_rate']/100*nt))
    pv=binomtest(wins,nt,be/100,alternative='greater').pvalue
    print(f"{label}: n={nt} WR={s['win_rate']:.2f}% exp={s['expectancy']:+.3f}$ "
          f"pnl={s['total_pnl']:+.1f}$ tpd={tpd:.2f} p(WR>{be:.0f})={pv:.3f}")
    return dict(n=nt,wr=s['win_rate'],exp=s['expectancy'],pnl=s['total_pnl'],tpd=tpd,pv=pv)

print("\n=== A/B با ensemble 3-seed ===")
for label, fdf, cols in [('BASELINE (S14 feats)', feats, base_cols),
                          ('AUGMENTED (+weekly_rev)', feats_aug, aug_cols)]:
    probas=[walk_forward(fdf,cols,seed=s) for s in [42,7,123]]
    ens=np.nanmean(np.vstack(probas),axis=0)
    evaluate(ens,label)

print("\nتمام.")
