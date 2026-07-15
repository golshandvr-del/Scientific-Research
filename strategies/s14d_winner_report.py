"""
گزارش نهایی نسخه برنده استراتژی ۱۴:
Long-only, VWAP-Regime Selective ML Ensemble, RR=TP1.0/SL1.5 (BE=60%), thr=0.68.
خروجی: آمار کامل + پایداری per-fold زمانی + توزیع معامله/روز، برای ثبت در فایل MD
و استفاده در ربات MT5.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS=6; MIN_TRAIN_FRAC=0.40; SEEDS=[42,7,123]
HZ, TP_M, SL_M, THR = 48, 1.0, 1.5, 0.68
BE = SL_M/(TP_M+SL_M)*100

def wf_proba(df, feats, fc, cand, n, seed):
    atr = ind.atr(df,14); y = make_target(df, HZ, TP_M, SL_M, atr, 'long')
    data = feats.copy(); data['y']=y; data['cand']=cand
    valid = data.dropna(subset=fc+['y']); valid=valid[valid['cand']]
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

df = load_data(); df['hour']=df['dt'].dt.hour
atr=ind.atr(df,14); atr_arr=atr.values
c=df['close']; cv=c.values
ema50=ind.ema(c,50).values; ema200=ind.ema(c,200).values
n=len(df); feats=build_features(df); fc=list(feats.columns)
cand=(cv>ema50)&(ema50>ema200)
proba=np.nanmean(np.vstack([wf_proba(df,feats,fc,cand,n,sd) for sd in SEEDS]),axis=0)
oos=~np.isnan(proba)
entries=cand&(proba>=THR)&oos
s,tr=run_backtest(df, entries, None, None, 'long', spread=0.20, max_hold=HZ,
                  sl_series=SL_M*atr_arr, tp_series=TP_M*atr_arr, allow_overlap=False)
nt=s['n_trades']; wins=int(round(s['win_rate']/100*nt))
pval=stats.binomtest(wins,nt,BE/100,alternative='greater').pvalue
span_days=(df['dt'].max()-df['dt'].min()).days; trading_days=span_days*5/7
oos_frac=oos.sum()/n
tpd=(nt/trading_days)/oos_frac

print("="*60)
print("نسخه برنده استراتژی ۱۴ (Long-only ensemble)")
print(f"RR: TP={TP_M}xATR / SL={SL_M}xATR | BE={BE:.1f}% | thr={THR} | hz={HZ}")
print("="*60)
print(f"n_trades         = {nt}")
print(f"Win Rate         = {s['win_rate']:.2f}%")
print(f"Expectancy       = {s['expectancy']:+.3f}$ / trade")
print(f"Total PnL        = {s['total_pnl']:+.1f}$")
print(f"avg_win          = {s['avg_win']:+.3f}$")
print(f"avg_loss         = {s['avg_loss']:+.3f}$")
print(f"avg_bars_held    = {s['avg_bars_held']:.1f}")
print(f"trades/day(norm) = {tpd:.2f}")
print(f"edge (WR-BE)     = {s['win_rate']-BE:+.2f}%")
print(f"p-value(WR>BE)   = {pval:.4f}")
print(f"OOS coverage     = {oos_frac*100:.1f}% of data")

# پایداری per-fold زمانی (۵ بلوک مساوی روی معاملات OOS)
tr=tr.sort_values('entry_bar').reset_index(drop=True)
print("\n--- پایداری زمانی (۵ بلوک مساوی) ---")
blocks=np.array_split(tr, 5)
for i,b in enumerate(blocks):
    if len(b)==0: continue
    w=(b['outcome']=='win').sum(); tt=len(b)
    print(f"  بلوک {i+1}: n={tt} WR={w/tt*100:.2f}% exp={b['pnl'].mean():+.3f}$")

# توزیع معامله در روز
tr['day']=df['dt'].iloc[tr['entry_bar'].values].dt.date.values
per_day=tr.groupby('day').size()
print(f"\n--- فرکانس ---")
print(f"روزهای دارای معامله: {len(per_day)}")
print(f"میانگین معامله در روزهای فعال: {per_day.mean():.2f}")
print(f"median: {per_day.median():.0f} | max: {per_day.max()}")
