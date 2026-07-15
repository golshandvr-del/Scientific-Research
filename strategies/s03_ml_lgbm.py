"""
استراتژی ۳: مدل یادگیری ماشین (LightGBM) با فیلتر اطمینان بالا

منطق علمی:
- به جای قانون ساده، مدل gradient boosting الگوهای غیرخطی چندبعدی را یاد می‌گیرد.
- Target: آیا TP قبل از SL در افق مشخص لمس می‌شود؟
- فقط روی پیش‌بینی‌های با احتمال بالا (> آستانه) معامله می‌کنیم -> WR بالا.
- Train/Test split زمانی (out-of-sample واقعی) برای جلوگیری از overfit.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target

HORIZON = 16      # افق آینده (16 کندل = 4 ساعت)
TP_MULT = 2.0     # TP = 2*ATR
SL_MULT = 2.0     # SL = 2*ATR  (RR متعادل 1:1)
THRESHOLD = 0.60  # آستانه اطمینان برای معامله

def main():
    df = load_data()
    atr = ind.atr(df, 14)
    feats = build_features(df)
    feat_cols = list(feats.columns)

    results = {}
    for direction in ['long', 'short']:
        y = make_target(df, HORIZON, TP_MULT, SL_MULT, atr, direction)
        data = feats.copy()
        data['y'] = y
        data['atr'] = atr.values
        valid = data.dropna()
        X = valid[feat_cols].values
        Y = valid['y'].values.astype(int)
        idx = valid.index.values

        # split زمانی 70/30
        split = int(len(X) * 0.70)
        Xtr, Xte = X[:split], X[split:]
        Ytr, Yte = Y[:split], Y[split:]
        idx_te = idx[split:]

        model = lgb.LGBMClassifier(
            n_estimators=400, learning_rate=0.03, num_leaves=31,
            max_depth=6, subsample=0.8, colsample_bytree=0.8,
            min_child_samples=100, reg_lambda=1.0, random_state=42, verbose=-1)
        model.fit(Xtr, Ytr)

        proba = model.predict_proba(Xte)[:, 1]
        base_rate = Yte.mean()
        # سیگنال روی کندل‌های تست با احتمال بالا
        entries = np.zeros(len(df), dtype=bool)
        signal_bars = idx_te[proba >= THRESHOLD]
        entries[signal_bars] = True

        atr_arr = atr.values
        s, t = run_backtest(df, entries, None, None, direction,
                            spread=0.20, max_hold=HORIZON,
                            sl_series=SL_MULT*atr_arr, tp_series=TP_MULT*atr_arr)
        results[direction] = (s, base_rate, (proba>=THRESHOLD).sum())
        print(f"[{direction}] base_rate(TP hit)={base_rate:.3f} | "
              f"signals={ (proba>=THRESHOLD).sum() } | "
              f"trades={s['n_trades']} WR={s['win_rate']:.2f}% "
              f"exp={s['expectancy']:.3f}$ pnl={s['total_pnl']:.1f}$")

    return results

if __name__ == '__main__':
    main()
