"""
استراتژی ۵: کشف «مرز کارایی» بازار XAUUSD M15

این اسکریپت به‌صورت سیستماتیک رابطه بین Win Rate و نسبت Risk:Reward را
با مدل LightGBM (walk-forward) بررسی می‌کند تا سقف قابلیت پیش‌بینی بازار را
مشخص کند.

نتیجه: مدل می‌تواند WR را حداکثر ~۳-۴٪ بالای baseline (=base rate) ببرد،
اما نمی‌تواند از نقطه سربه‌سر (که با RR تعیین می‌شود) به‌طور پایدار عبور کند.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, lightgbm as lgb
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

def wf_proba(df, atr, Xall, direction, hz, tp, sl, nfolds=6, min_train=50000):
    y = make_target(df, hz, tp, sl, atr, direction)
    mask = ~np.isnan(y) & ~np.isnan(Xall).any(axis=1)
    idx = np.where(mask)[0]
    X = Xall[idx]; Y = y[idx].astype(int)
    N = len(X); fold = (N-min_train)//nfolds
    proba = np.full(len(df), np.nan)
    base = Y.mean()
    for k in range(nfolds):
        tr_end = min_train + k*fold
        te_end = tr_end + fold if k < nfolds-1 else N
        m = lgb.LGBMClassifier(n_estimators=800, learning_rate=0.015, num_leaves=48,
            max_depth=7, subsample=0.8, colsample_bytree=0.7, min_child_samples=150,
            reg_lambda=2.0, random_state=42, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1]
    return proba, base


def main():
    df = load_data(); atr = ind.atr(df, 14); atr_arr = atr.values
    feats = build_features(df); Xall = feats.values

    # ماتریس RR مختلف؛ برای هر کدام بهترین WR در آستانه بالا
    configs = [
        (16, 1.0, 2.0),   # BE 66.7%
        (20, 1.0, 2.5),   # BE 71.4%
        (24, 1.0, 3.0),   # BE 75.0%
    ]
    print("Efficiency frontier of XAUUSD M15 (LONG, walk-forward):")
    print(f"{'RR':>8}{'BE%':>7}{'base%':>8}{'bestWR%':>9}{'exp$':>9}{'trades':>8}")
    for hz, tp, sl in configs:
        proba, base = wf_proba(df, atr, Xall, 'long', hz, tp, sl)
        be = sl/(tp+sl)*100
        best = None
        for th in [0.70, 0.72, 0.75, 0.78, 0.80, 0.82]:
            e = (proba >= th) & (~np.isnan(proba))
            s, t = run_backtest(df, e, None, None, 'long', spread=0.20, max_hold=hz,
                                sl_series=sl*atr_arr, tp_series=tp*atr_arr)
            if s['n_trades'] > 300 and (best is None or s['win_rate'] > best[0]):
                best = (s['win_rate'], s['expectancy'], s['n_trades'])
        print(f"1:{sl/tp:>5.1f}{be:>7.1f}{base*100:>8.1f}"
              f"{best[0]:>9.2f}{best[1]:>9.3f}{best[2]:>8}")


if __name__ == '__main__':
    main()
