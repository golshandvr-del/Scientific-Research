"""
استراتژی ۶: LONG در پنجره طلایی شبانه + فیلتر احتمال LightGBM (Walk-Forward)

بینش‌های تجمیعی از تحقیق قبلی + تحلیل اکتشافی جدید:
1. طلا بایاس صعودی ساختاری دارد (روند بلندمدت صعودی).
2. یک edge ساعتی قوی و پایدار وجود دارد: در ساعات 19-23 UTC (سشن آمریکا/بسته‌شدن)
   میانگین بازده آینده مثبت و P(up) تا ~55% است (baseline ~52%).
3. ادامه‌روند (breakout) کار نمی‌کند؛ اما ورود long در پنجره طلایی edge خام دارد.

طراحی:
- فقط LONG و فقط در کندل‌هایی که ساعت شروع در {19,20,21,22,23} UTC است.
- مدل LightGBM روی همان feature-set استاندارد train می‌شود اما هدف = رسیدن TP قبل SL.
- Walk-Forward با ۵ fold (out-of-sample کامل).
- جاروب چند (RR, threshold) تا ترکیبی با WR>70% و expectancy>0 پیدا شود.

معیار موفقیت پروژه: WR>70% به‌همراه expectancy>0 (طبق درس استراتژی ۲).
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
GOLDEN_HOURS = [19, 20, 21, 22, 23]

def walk_forward_proba(X, Y, idx, n, min_train=MIN_TRAIN, nfolds=N_FOLDS):
    """احتمال out-of-sample برای هر نمونه با walk-forward."""
    proba = np.full(n, np.nan)
    N = len(X)
    fold = (N - min_train) // nfolds
    for k in range(nfolds):
        tr_end = min_train + k*fold
        te_end = tr_end + fold if k < nfolds-1 else N
        m = lgb.LGBMClassifier(n_estimators=600, learning_rate=0.02, num_leaves=40,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=120,
            reg_lambda=1.5, random_state=42, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        p = m.predict_proba(X[tr_end:te_end])[:, 1]
        proba[idx[tr_end:te_end]] = p
    return proba

def main():
    df = load_data()
    df['hour'] = df['dt'].dt.hour
    atr = ind.atr(df, 14); atr_arr = atr.values
    feats = build_features(df); feat_cols = list(feats.columns)
    hours = df['hour'].values
    golden = np.isin(hours, GOLDEN_HOURS)
    n = len(df)

    print("استراتژی ۶: Session-ML LONG (walk-forward)")
    print(f"{'RR':>7}{'BE%':>7}{'thr':>6}{'trades':>8}{'WR%':>8}{'exp$':>9}{'pnl$':>10}")
    print("-"*60)

    best = None
    for hz, tp_m, sl_m in [(24, 1.0, 1.0), (32, 1.5, 1.5), (24, 1.5, 1.0),
                           (32, 1.0, 1.0), (24, 1.2, 1.0)]:
        # هدف روی کل داده ساخته می‌شود (بدون look-ahead: از make_target امن)
        y = make_target(df, hz, tp_m, sl_m, atr, 'long')
        data = feats.copy(); data['y'] = y; data['golden'] = golden
        valid = data.dropna(subset=feat_cols+['y'])
        X = valid[feat_cols].values
        Y = valid['y'].values.astype(int)
        idx = valid.index.values
        proba = walk_forward_proba(X, Y, idx, n)

        be = sl_m/(tp_m+sl_m)*100
        for thr in [0.55, 0.60, 0.65, 0.70]:
            entries = golden & (proba >= thr) & (~np.isnan(proba))
            s, t = run_backtest(df, entries, None, None, 'long', spread=0.20,
                                max_hold=hz, sl_series=sl_m*atr_arr, tp_series=tp_m*atr_arr,
                                allow_overlap=False)
            if s['n_trades'] < 100:
                continue
            flag = ""
            if s['win_rate'] > 70 and s['expectancy'] > 0:
                flag = " <== TARGET MET"
                if best is None or s['expectancy'] > best['exp']:
                    best = {'hz':hz,'tp':tp_m,'sl':sl_m,'thr':thr,
                            'wr':s['win_rate'],'exp':s['expectancy'],
                            'n':s['n_trades'],'pnl':s['total_pnl']}
            print(f"1:{sl_m/tp_m:>4.2f}{be:>7.1f}{thr:>6.2f}{s['n_trades']:>8}"
                  f"{s['win_rate']:>8.2f}{s['expectancy']:>9.3f}{s['total_pnl']:>10.1f}{flag}")
        print()

    if best:
        print("=== بهترین ترکیب با WR>70% و exp>0 ===")
        print(best)
    else:
        print("هیچ ترکیبی به WR>70% + exp>0 نرسید.")

if __name__ == '__main__':
    main()
