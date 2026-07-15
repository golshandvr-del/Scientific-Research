"""
استراتژی ۷: LONG با RR نامتقارن ملایم + Multi-Edge Stacking + ML انتخابی

هدف: رسیدن هم‌زمان به WR>70% و expectancy>0.
منطق ریاضی: اگر breakeven را روی ~۶۰-۶۵٪ تنظیم کنیم (TP=1.0, SL=1.5..2.0)،
آنگاه رسیدن به WR>70% -> expectancy قطعاً مثبت.
کلید: بالا بردن WR واقعی مدل تا بالای ۷۰٪ با انتخاب بسیار سخت‌گیرانه سیگنال.

روش:
- فقط LONG، فقط پنجره طلایی (19-23 UTC) + فیلتر روند (close>ema200).
- هدف RR نامتقارن: TP=1.0×ATR، SL=1.5×ATR (BE=60%).
- ML LightGBM با آستانه بالا (فقط پراطمینان‌ترین سیگنال‌ها).
- Walk-Forward ۵ fold، out-of-sample.
- گزارش منحنی WR-vs-threshold تا سقف WR مدل مشخص شود.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 5
MIN_TRAIN = 40000
GOLDEN = [19, 20, 21, 22, 23]

def wf_proba(X, Y, idx, n):
    proba = np.full(n, np.nan)
    N = len(X); fold = (N - MIN_TRAIN)//N_FOLDS
    for k in range(N_FOLDS):
        tr_end = MIN_TRAIN + k*fold
        te_end = tr_end + fold if k < N_FOLDS-1 else N
        m = lgb.LGBMClassifier(n_estimators=700, learning_rate=0.02, num_leaves=48,
            max_depth=7, subsample=0.8, colsample_bytree=0.7, min_child_samples=100,
            reg_lambda=2.0, random_state=42, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:,1]
    return proba

def main():
    df = load_data(); df['hour'] = df['dt'].dt.hour
    atr = ind.atr(df,14); atr_arr = atr.values
    ema200 = ind.ema(df['close'],200).values
    c = df['close'].values; n = len(df)
    feats = build_features(df); fc = list(feats.columns)
    golden = np.isin(df['hour'].values, GOLDEN)
    base_filter = golden & (c > ema200)

    print("استراتژی ۷: LONG RR نامتقارن + stacking + ML انتخابی (walk-forward)")
    print(f"{'TP':>4}{'SL':>5}{'BE%':>7}{'thr':>6}{'trades':>8}{'WR%':>8}{'exp$':>9}{'pnl$':>9}")
    print("-"*60)

    best=None
    for hz, tp_m, sl_m in [(24,1.0,1.5),(32,1.0,1.5),(24,1.0,1.8),(32,1.0,2.0),(24,1.0,2.0)]:
        y = make_target(df, hz, tp_m, sl_m, atr, 'long')
        data = feats.copy(); data['y']=y
        # فقط روی نمونه‌های پنجره طلایی + روند train می‌کنیم تا مدل تخصصی شود
        data['bf'] = base_filter
        valid = data.dropna(subset=fc+['y'])
        X = valid[fc].values; Y = valid['y'].values.astype(int); idx = valid.index.values
        proba = wf_proba(X, Y, idx, n)
        be = sl_m/(tp_m+sl_m)*100
        for thr in [0.72, 0.75, 0.78, 0.80, 0.82, 0.85]:
            entries = base_filter & (proba>=thr) & (~np.isnan(proba))
            s,t = run_backtest(df, entries, None, None, 'long', spread=0.20,
                    max_hold=hz, sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr,
                    allow_overlap=False)
            if s['n_trades']<80: continue
            flag=""
            if s['win_rate']>70 and s['expectancy']>0:
                flag=" <== TARGET"
                if best is None or s['expectancy']>best['exp']:
                    best={'hz':hz,'tp':tp_m,'sl':sl_m,'thr':thr,'wr':s['win_rate'],
                          'exp':s['expectancy'],'n':s['n_trades'],'pnl':s['total_pnl']}
            print(f"{tp_m:>4.1f}{sl_m:>5.1f}{be:>7.1f}{thr:>6.2f}{s['n_trades']:>8}"
                  f"{s['win_rate']:>8.2f}{s['expectancy']:>9.3f}{s['total_pnl']:>9.1f}{flag}")
        print()
    print("BEST:", best if best else "هیچ ترکیبی به هدف نرسید")

if __name__=='__main__':
    main()
