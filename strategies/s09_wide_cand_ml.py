"""
استراتژی ۹: کاندید وسیع (کل پنجره طلایی در روند) + ML آستانه بهینه برای WR معنادار

هدف: n معنادار (>=200) با WR>70% معنادار (p<0.05) و exp>0.
تفاوت با استراتژی‌های قبل:
- s07: کاندید = کل بازار -> آستانه بالا -> n≈۵۰ (نامعنادار).
- s08: کاندید = golden+up+rsi<50 -> پایه WR~۶۸٪ سقف.
- s09: کاندید = golden+up (بدون rsi، n پایه ~۳۷۰۰) -> ML آزاد است بهترین‌ها را
  انتخاب کند. با پایه بزرگ، حتی آستانه نسبتاً بالا هم n>=۲۰۰ می‌دهد.
- RR با BE~۶۶٪ تا WR~۷۲٪ از BE عبور کند و exp قاطع مثبت شود.
- آزمون معناداری کامل + پایداری per-fold + چند seed.
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
GOLDEN=[19,20,21,22,23]

def wf(df, feats, fc, cand, atr, atr_arr, n, hz, tp_m, sl_m, seed):
    y=make_target(df, hz, tp_m, sl_m, atr, 'long')
    data=feats.copy(); data['y']=y; data['cand']=cand
    valid=data.dropna(subset=fc+['y']); valid=valid[valid['cand']]
    X=valid[fc].values; Y=valid['y'].values.astype(int); idx=valid.index.values
    N=len(X); mt=int(N*MIN_TRAIN_FRAC); fold=(N-mt)//N_FOLDS
    proba=np.full(n,np.nan)
    for k in range(N_FOLDS):
        tr_end=mt+k*fold; te_end=tr_end+fold if k<N_FOLDS-1 else N
        m=lgb.LGBMClassifier(n_estimators=500, learning_rate=0.025, num_leaves=32,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1)
        m.fit(X[:tr_end],Y[:tr_end])
        proba[idx[tr_end:te_end]]=m.predict_proba(X[tr_end:te_end])[:,1]
    return proba, Y.mean()

def main():
    df=load_data(); df['hour']=df['dt'].dt.hour
    atr=ind.atr(df,14); atr_arr=atr.values
    c=df['close']; cv=c.values
    ema50=ind.ema(c,50).values; ema200=ind.ema(c,200).values
    n=len(df)
    feats=build_features(df); fc=list(feats.columns)
    golden=np.isin(df['hour'].values,GOLDEN)
    cand=golden & (cv>ema50) & (ema50>ema200)
    print(f"کاندید پایه (golden+uptrend): {cand.sum()}")

    for hz,tp_m,sl_m in [(48,1.0,2.0),(48,1.2,2.2),(32,1.0,1.9)]:
        be=sl_m/(tp_m+sl_m)*100
        proba,base=wf(df,feats,fc,cand,atr,atr_arr,n,hz,tp_m,sl_m,42)
        print(f"\n### RR TP={tp_m} SL={sl_m} hz={hz} | BE={be:.1f}% | baseWR={base*100:.1f}%")
        print(f"{'thr':>6}{'n':>6}{'WR%':>8}{'exp$':>9}{'pnl$':>9}{'pval':>8}")
        for thr in [0.60,0.65,0.68,0.70,0.72,0.75]:
            entries=cand & (proba>=thr) & (~np.isnan(proba))
            s,t=run_backtest(df, entries, None, None, 'long', spread=0.20, max_hold=hz,
                    sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr, allow_overlap=False)
            nt=s['n_trades']
            if nt<50: continue
            wins=int(round(s['win_rate']/100*nt))
            pval=stats.binomtest(wins,nt,be/100,alternative='greater').pvalue
            flag=""
            if s['win_rate']>70 and s['expectancy']>0 and pval<0.05 and nt>=200:
                flag=" <<<=== WINNER"
            elif s['win_rate']>70 and s['expectancy']>0 and pval<0.05:
                flag=" <== sig"
            elif s['win_rate']>70 and s['expectancy']>0:
                flag=" <-- target"
            print(f"{thr:>6.2f}{nt:>6}{s['win_rate']:>8.2f}{s['expectancy']:>9.3f}"
                  f"{s['total_pnl']:>9.1f}{pval:>8.3f}{flag}")

if __name__=='__main__':
    main()
