"""
استراتژی ۸: قانون ساختاری (Golden+Uptrend+Pullback) + ML به‌عنوان فیلتر کیفیت

بینش نهایی از کل تحقیق:
- قانون خام «پنجره طلایی + روند صعودی + pullback (RSI<50)» با TP=1.0/SL=2.5×ATR
  یک پایه ~۷۰٪ WR با n≈۴۰۰ می‌دهد (سیگنال کاندید کافی).
- به‌جای آستانه ML روی *کل بازار* (که n را به ~۵۰ می‌رساند و نامعنادار می‌شود)،
  ML را فقط به‌عنوان فیلتر روی همین کاندیداهای ساختاری اعمال می‌کنیم.
- این ترکیب: n پایه کافی از قانون + بالا بردن WR توسط ML = هدف WR>70% معنادار + exp>0.

طراحی:
- کاندیدها: golden(19-23) & close>ema50>ema200 & RSI14<50
- هدف: TP=1.0×ATR, SL=2.5×ATR, hz=48 (BE=71.4%)
- ML (LightGBM) روی feature-set استاندارد، walk-forward، فقط روی کاندیدها آموزش می‌بیند
  (تخصصی‌سازی مدل روی زیرفضای مسئله).
- آستانه ملایم (چون پایه خوب است) تا n بالای ۲۰۰ بماند.
- آزمون معناداری دوجمله‌ای علیه BE.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 5; MIN_TRAIN_FRAC = 0.45
GOLDEN=[19,20,21,22,23]

def eval_rr(df, feats, fc, cand, atr, atr_arr, n, hz, tp_m, sl_m):
    y = make_target(df, hz, tp_m, sl_m, atr, 'long')
    data=feats.copy(); data['y']=y; data['cand']=cand
    valid = data.dropna(subset=fc+['y'])
    valid = valid[valid['cand']]
    X=valid[fc].values; Y=valid['y'].values.astype(int); idx=valid.index.values
    N=len(X)
    be=sl_m/(tp_m+sl_m)*100
    min_train=int(N*MIN_TRAIN_FRAC); fold=(N-min_train)//N_FOLDS
    proba=np.full(n,np.nan)
    for k in range(N_FOLDS):
        tr_end=min_train+k*fold
        te_end=tr_end+fold if k<N_FOLDS-1 else N
        m=lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=24,
            max_depth=5, subsample=0.85, colsample_bytree=0.8, min_child_samples=40,
            reg_lambda=3.0, random_state=42, verbose=-1)
        m.fit(X[:tr_end],Y[:tr_end])
        proba[idx[tr_end:te_end]]=m.predict_proba(X[tr_end:te_end])[:,1]
    print(f"\n### RR TP={tp_m} SL={sl_m} hz={hz} | BE={be:.1f}% | base WR={Y.mean()*100:.1f}% | کاندید={N}")
    print(f"{'thr':>6}{'n':>6}{'WR%':>8}{'exp$':>9}{'pnl$':>9}{'pval':>8}")
    for thr in [0.0,0.50,0.55,0.58,0.60,0.62,0.65,0.68]:
        entries = (cand & (proba>=thr) & (~np.isnan(proba))) if thr>0 else (cand & (~np.isnan(proba)))
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

def main():
    df = load_data(); df['hour']=df['dt'].dt.hour
    atr = ind.atr(df,14); atr_arr=atr.values
    c=df['close']; cv=c.values
    ema50=ind.ema(c,50).values; ema200=ind.ema(c,200).values
    rsi14=ind.rsi(c,14).values
    n=len(df)
    feats=build_features(df); fc=list(feats.columns)
    golden=np.isin(df['hour'].values,GOLDEN)
    cand = golden & (cv>ema50) & (ema50>ema200) & (rsi14<50)
    # چند RR با BE پایین‌تر تا WR~72% از BE عبور کند و exp قاطع مثبت شود
    for hz,tp_m,sl_m in [(48,1.0,2.0),(48,1.2,2.0),(32,1.0,1.8),(48,1.0,1.8)]:
        eval_rr(df, feats, fc, cand, atr, atr_arr, n, hz, tp_m, sl_m)

if __name__=='__main__':
    main()
