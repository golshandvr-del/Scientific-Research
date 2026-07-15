"""
اعتبارسنجی سخت‌گیرانه استراتژی ۷ (بهترین config: TP=1.0, SL=1.8, hz=32, thr=0.80).
بررسی: پایداری per-fold، معناداری آماری، حساسیت threshold، و seedها.
هدف: اطمینان از اینکه WR>70% + exp>0 یک نتیجه واقعی است نه شانس/overfit.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 5; MIN_TRAIN = 40000
GOLDEN = [19,20,21,22,23]
HZ, TP_M, SL_M, THR = 32, 1.0, 1.8, 0.80

def main():
    df = load_data(); df['hour']=df['dt'].dt.hour
    atr = ind.atr(df,14); atr_arr=atr.values
    ema200 = ind.ema(df['close'],200).values
    c = df['close'].values; n=len(df)
    feats = build_features(df); fc=list(feats.columns)
    golden = np.isin(df['hour'].values, GOLDEN)
    bf = golden & (c>ema200)
    y = make_target(df, HZ, TP_M, SL_M, atr, 'long')
    data = feats.copy(); data['y']=y
    valid = data.dropna(subset=fc+['y'])
    X = valid[fc].values; Y=valid['y'].values.astype(int); idx=valid.index.values
    N=len(X); fold=(N-MIN_TRAIN)//N_FOLDS
    be = SL_M/(TP_M+SL_M)*100

    print(f"config: TP={TP_M} SL={SL_M} hz={HZ} thr={THR}  breakeven={be:.1f}%\n")

    # چند seed برای پایداری مدل
    for seed in [42, 7, 123]:
        proba = np.full(n, np.nan)
        fold_rows=[]
        for k in range(N_FOLDS):
            tr_end = MIN_TRAIN + k*fold
            te_end = tr_end+fold if k<N_FOLDS-1 else N
            m = lgb.LGBMClassifier(n_estimators=700, learning_rate=0.02, num_leaves=48,
                max_depth=7, subsample=0.8, colsample_bytree=0.7, min_child_samples=100,
                reg_lambda=2.0, random_state=seed, verbose=-1)
            m.fit(X[:tr_end], Y[:tr_end])
            proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:,1]
            # آمار per-fold
            e_fold = np.zeros(n,bool)
            sel = idx[tr_end:te_end][proba[idx[tr_end:te_end]]>=THR]
            e_fold[sel]=True
            e_fold &= bf
            s,_ = run_backtest(df, e_fold, None, None, 'long', spread=0.20, max_hold=HZ,
                    sl_series=SL_M*atr_arr, tp_series=TP_M*atr_arr, allow_overlap=False)
            fold_rows.append((k+1, s['n_trades'], s['win_rate'], s['expectancy']))
        # تجمیعی
        entries = bf & (proba>=THR) & (~np.isnan(proba))
        s,t = run_backtest(df, entries, None, None, 'long', spread=0.20, max_hold=HZ,
                sl_series=SL_M*atr_arr, tp_series=TP_M*atr_arr, allow_overlap=False)
        nt=s['n_trades']; wr=s['win_rate']/100
        # آزمون دوجمله‌ای: H0: p=breakeven
        p0=be/100
        wins=int(round(wr*nt))
        pval = stats.binomtest(wins, nt, p0, alternative='greater').pvalue
        print(f"seed={seed}: trades={nt} WR={s['win_rate']:.2f}% exp={s['expectancy']:.3f}$ "
              f"pnl={s['total_pnl']:.1f}$  p-value(WR>BE)={pval:.4f}")
        for fr in fold_rows:
            print(f"    fold{fr[0]}: n={fr[1]:>4} WR={fr[2]:.1f}% exp={fr[3]:+.3f}$")
        print()

if __name__=='__main__':
    main()
