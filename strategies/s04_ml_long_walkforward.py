"""
استراتژی ۴: مدل LightGBM جهت LONG با اعتبارسنجی Walk-Forward

بینش کلیدی: طلا در بازه داده یک روند صعودی بلندمدت قوی دارد (۱۶۲۰ -> ۴۱۷۰ دلار).
این «بایاس صعودی ساختاری» به معاملات long کمک می‌کند. مدل ML الگوهای ورود
long با احتمال موفقیت بالا را یاد می‌گیرد.

طراحی:
- فقط LONG.
- TP = 1.0×ATR، SL = 3.0×ATR، افق ۲۴ کندل. (base rate بالا ~۷۱٪)
- نقطه سربه‌سر تئوریک = 3.0/4.0 = ۷۵٪ WR. هدف: عبور از آن.
- Walk-Forward: داده به چند بازه متوالی تقسیم می‌شود؛ مدل روی گذشته train
  و روی بازه بعدی (کاملاً out-of-sample) تست می‌شود. این مقاوم‌ترین آزمون است.
- فقط سیگنال‌های با احتمال >= آستانه معامله می‌شوند.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

DIRECTION = 'long'
HORIZON = 24
TP_MULT = 1.0
SL_MULT = 3.0
THRESHOLD = 0.75
N_FOLDS = 5          # تعداد بازه‌های walk-forward
MIN_TRAIN = 40000    # حداقل داده اولیه برای train

def main():
    df = load_data()
    atr = ind.atr(df, 14)
    feats = build_features(df)
    feat_cols = list(feats.columns)
    y = make_target(df, HORIZON, TP_MULT, SL_MULT, atr, DIRECTION)
    data = feats.copy(); data['y'] = y
    valid = data.dropna()
    X = valid[feat_cols].values
    Y = valid['y'].values.astype(int)
    idx = valid.index.values
    N = len(X)
    atr_arr = atr.values

    # مرزهای walk-forward
    test_start = MIN_TRAIN
    fold_size = (N - test_start) // N_FOLDS
    all_entries = np.zeros(len(df), dtype=bool)
    fold_stats = []

    for k in range(N_FOLDS):
        tr_end = test_start + k*fold_size
        te_end = tr_end + fold_size if k < N_FOLDS-1 else N
        Xtr, Ytr = X[:tr_end], Y[:tr_end]
        Xte = X[tr_end:te_end]
        idx_te = idx[tr_end:te_end]
        m = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.03, num_leaves=31,
            max_depth=6, subsample=0.8, colsample_bytree=0.8, min_child_samples=150,
            reg_lambda=1.0, random_state=42, verbose=-1)
        m.fit(Xtr, Ytr)
        proba = m.predict_proba(Xte)[:, 1]
        sel = idx_te[proba >= THRESHOLD]
        all_entries[sel] = True
        # آمار این fold به‌تنهایی
        e_fold = np.zeros(len(df), bool); e_fold[sel] = True
        s, t = run_backtest(df, e_fold, None, None, DIRECTION, spread=0.20,
                            max_hold=HORIZON, sl_series=SL_MULT*atr_arr, tp_series=TP_MULT*atr_arr)
        fold_stats.append(s)
        print(f"Fold {k+1}: train={tr_end} test=[{tr_end}:{te_end}] "
              f"trades={s['n_trades']} WR={s['win_rate']:.2f}% exp={s['expectancy']:.3f}$ pnl={s['total_pnl']:.1f}$")

    # آمار تجمیعی روی همه foldها (کل دوره out-of-sample)
    s_all, t_all = run_backtest(df, all_entries, None, None, DIRECTION, spread=0.20,
                                max_hold=HORIZON, sl_series=SL_MULT*atr_arr, tp_series=TP_MULT*atr_arr)
    be = SL_MULT/(TP_MULT+SL_MULT)*100
    print(f"\n=== AGGREGATE (all OOS folds) ===")
    print(f"trades={s_all['n_trades']} WR={s_all['win_rate']:.2f}% (breakeven~{be:.1f}%) "
          f"exp={s_all['expectancy']:.3f}$ total_pnl={s_all['total_pnl']:.1f}$ "
          f"avg_win={s_all['avg_win']:.2f}$ avg_loss={s_all['avg_loss']:.2f}$")
    return s_all, t_all

if __name__ == '__main__':
    main()
