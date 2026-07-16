"""
استراتژی ۴۳: تزریق دادهٔ برون‌زای DXY به مدل S25 (گروه G — P37)

انگیزهٔ علمی (L1 پروژه): «افزودن یک منبع اطلاعاتی جدید، سقف WR را جابه‌جا می‌کند».
تمام featureهای قبلی از خودِ OHLCV طلا مشتق می‌شدند — هم‌خانواده و اشباع. DXY
(شاخص دلار) یک متغیر *برون‌زا*ست: همبستگی معکوس تاریخی قوی با طلا دارد
(تأیید تجربی این پروژه: میانگین corr≈−0.39، در ۹۳٪ مواقع منفی، beta≈−0.94).

روش (Recipe-S25، آزمون A/B منصفانه):
  • مدل، featureها، foldها، seedها، آستانه و نقطهٔ کاری همگی *دقیقاً* مثل S25.
  • تنها تفاوت بین دو بازو: افزودن ۱۴ featureِ برون‌زای DXY به augmented.
  • چون همه‌چیز جز منبع اطلاعات ثابت است، هر تفاوتِ عملکرد ⇐ سهم خالص DXY.

featureهای DXY (همه بدون look-ahead، هم‌ترازِ merge_asof backward):
  dxy_ret_{1,4,16,96}, dxy_rsi_14, dxy_zscore_50, dxy_dist_ema50,
  dxy_slope_20, dxy_above_ema200,
  gold_dxy_corr_{48,96}, gold_dxy_beta_{48,96}, dxy_gold_divergence

هدف: آیا DXY، WR/PF/expectancy را نسبت به S25 خالص بهبود می‌دهد؟
"""
import sys, gc; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from exogenous import build_exogenous_features, dxy_coverage_report
import warnings; warnings.filterwarnings('ignore')

N_FOLDS=6; MIN_TRAIN_FRAC=0.40
HZ=48; TP_M=1.0; SL_M=1.5; THRESH=0.68; SPREAD=0.20
SEEDS=[42,7,123]

df=load_data()
df['dt']=pd.to_datetime(df['time'],unit='s')
n=len(df)
c=df['close'].values
atr=ind.atr(df,14)
ema50=ind.ema(df['close'],50).values
ema200=ind.ema(df['close'],200).values

# ---------- featureهای زمانی S25 (weekly reversion) ----------
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
weekly_rev = -np.sign(df['early'].values) * np.clip(np.abs(early_atr),0,3) * day_w

_ARM_PRE = sys.argv[1] if len(sys.argv)>1 else 'both'
print("گزارش پوشش DXY:", dxy_coverage_report(df))
print("ساخت featureهای پایه (S25) ...")
feats=build_features(df)
feats_s25=feats.copy()
feats_s25['weekly_rev']=weekly_rev
feats_s25['early_atr']=early_atr
base_cols=list(feats_s25.columns)          # S25 خالص

print("ساخت featureهای برون‌زای DXY (هم‌ترازی as-of، بدون look-ahead) ...")
exo=build_exogenous_features(df)
exo_cols=list(exo.columns)
print(f"  {len(exo_cols)} feature برون‌زا: {exo_cols}")

# feats_aug را فقط اگر بازوی augmented لازم است می‌سازیم (صرفه‌جویی حافظه)
if _ARM_PRE in ('augmented','both'):
    feats_aug=feats_s25.copy()
    for col in exo_cols:
        feats_aug[col]=exo[col].values
    if _ARM_PRE=='augmented':
        del feats_s25; gc.collect()   # baseline لازم نیست
else:
    feats_aug=None
aug_cols =base_cols+exo_cols                # + DXY

# کاندید پایه مثل S25: روند صعودی long-only
cand=(c>ema50)&(ema50>ema200)&~np.isnan(atr.values)
print(f"کاندید پایه (uptrend long): {int(cand.sum())}")

def walk_forward(feature_df, fc, seed=42, keep_last=False):
    y=make_target(df,HZ,TP_M,SL_M,atr,'long')
    data=feature_df[fc].copy(); data['y']=y; data['cand']=cand
    valid=data.dropna(subset=fc+['y']); valid=valid[valid['cand']]
    X=valid[fc].values.astype(np.float32); Y=valid['y'].values.astype(int); idx=valid.index.values
    del data, valid; gc.collect()
    N=len(X); mt=int(N*MIN_TRAIN_FRAC); fold=(N-mt)//N_FOLDS
    proba=np.full(n,np.nan); last_m=None
    for k in range(N_FOLDS):
        tr_end=mt+k*fold; te_end=tr_end+fold if k<N_FOLDS-1 else N
        m=lgb.LGBMClassifier(n_estimators=500,learning_rate=0.025,num_leaves=32,
            max_depth=6,subsample=0.8,colsample_bytree=0.75,min_child_samples=80,
            reg_lambda=2.0,random_state=seed,verbose=-1,n_jobs=1)
        m.fit(X[:tr_end],Y[:tr_end])
        proba[idx[tr_end:te_end]]=m.predict_proba(X[tr_end:te_end])[:,1]
        if keep_last and k==N_FOLDS-1: last_m=m
        else: del m
        gc.collect()
    del X,Y; gc.collect()
    return proba, last_m

def evaluate(proba, label):
    ent=cand & ~np.isnan(proba) & (proba>=THRESH)
    s,_=run_backtest(df,ent,None,None,'long',SPREAD,HZ,
                     sl_series=SL_M*atr.values,tp_series=TP_M*atr.values,allow_overlap=False)
    nt=s['n_trades']
    if nt==0:
        print(f"{label}: no trades"); return None
    span_days=(df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    tpd=nt/span_days*7/5
    be=SL_M/(TP_M+SL_M)*100
    wins=int(round(s['win_rate']/100*nt))
    pv=binomtest(wins,nt,be/100,alternative='greater').pvalue
    pf = -(s['avg_win']*wins)/(s['avg_loss']*(nt-wins)) if (nt-wins)>0 and s['avg_loss']!=0 else float('inf')
    print(f"{label}: n={nt} WR={s['win_rate']:.2f}% exp={s['expectancy']:+.3f}$ "
          f"PF={pf:.3f} pnl={s['total_pnl']:+.1f}$ tpd={tpd:.2f} p(WR>{be:.0f})={pv:.4f}")
    return dict(n=nt,wr=s['win_rate'],exp=s['expectancy'],pf=pf,pnl=s['total_pnl'],tpd=tpd,pv=pv)

# ---- انتخاب بازو از آرگومان خط‌فرمان تا حافظهٔ هر بازو مستقل آزاد شود ----
# (این sandbox فقط ~۱GB RAM دارد؛ اجرای هر دو بازو با هم OOM می‌شود.)
ARM = sys.argv[1] if len(sys.argv)>1 else 'both'
arms=[]
if ARM in ('baseline','both'): arms.append(('BASELINE (S25)      ', feats_s25, base_cols, False))
if ARM in ('augmented','both'): arms.append(('AUGMENTED (+DXY)    ', feats_aug, aug_cols, True))

print(f"\n=== A/B با ensemble 3-seed | ARM={ARM} ===")
last_model=None
for label, fdf, cols, is_aug in arms:
    ens=np.zeros(n); cnt=np.zeros(n)
    for si,sd in enumerate(SEEDS):
        keep = (is_aug and si==len(SEEDS)-1)
        pr,m=walk_forward(fdf,cols,seed=sd,keep_last=keep)
        if keep: last_model=m
        mask=~np.isnan(pr); ens[mask]+=pr[mask]; cnt[mask]+=1
        del pr; gc.collect()
    ens=np.where(cnt>0, ens/np.maximum(cnt,1), np.nan)
    evaluate(ens,label)
    gc.collect()

if last_model is None:
    print("\n(این بازو baseline بود — گزارش اهمیت DXY فقط در بازوی augmented.)")
    print("\nتمام."); sys.exit(0)

# اهمیت featureها (از آخرین مدل augmented)
print("\n=== رتبهٔ اهمیت featureهای DXY در مدل augmented ===")
imp=last_model.feature_importances_
imp_df=pd.DataFrame({'feature':aug_cols,'importance':imp}).sort_values('importance',ascending=False).reset_index(drop=True)
imp_df['rank']=imp_df.index+1
dxy_ranks=imp_df[imp_df['feature'].isin(exo_cols)]
print(dxy_ranks[['rank','feature','importance']].to_string(index=False))
print(f"\nتعداد کل feature: {len(aug_cols)} | بهترین رتبهٔ DXY: {int(dxy_ranks['rank'].min())}")
print("\nتمام.")
