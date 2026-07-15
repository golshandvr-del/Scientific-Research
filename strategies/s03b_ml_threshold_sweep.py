"""
استراتژی ۳ب: جاروب آستانه اطمینان مدل LightGBM

هدف: یافتن ترکیب (TP/SL, threshold) که هم WR>70% بدهد هم expectancy مثبت.
منحنی trade-off بین آستانه اطمینان، Win Rate و سودآوری را بررسی می‌کند.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target

def evaluate(df, atr, feats, feat_cols, direction, horizon, tp_mult, sl_mult, thresholds):
    y = make_target(df, horizon, tp_mult, sl_mult, atr, direction)
    data = feats.copy(); data['y'] = y
    valid = data.dropna()
    X = valid[feat_cols].values
    Y = valid['y'].values.astype(int)
    idx = valid.index.values
    split = int(len(X)*0.70)
    model = lgb.LGBMClassifier(
        n_estimators=400, learning_rate=0.03, num_leaves=31, max_depth=6,
        subsample=0.8, colsample_bytree=0.8, min_child_samples=100,
        reg_lambda=1.0, random_state=42, verbose=-1)
    model.fit(X[:split], Y[:split])
    proba = model.predict_proba(X[split:])[:,1]
    idx_te = idx[split:]
    atr_arr = atr.values
    out = []
    for th in thresholds:
        entries = np.zeros(len(df), dtype=bool)
        entries[idx_te[proba>=th]] = True
        s,t = run_backtest(df, entries, None, None, direction, spread=0.20,
                           max_hold=horizon, sl_series=sl_mult*atr_arr, tp_series=tp_mult*atr_arr)
        out.append((th, s['n_trades'], s['win_rate'], s['expectancy'], s['total_pnl']))
    return out

def main():
    df = load_data()
    atr = ind.atr(df,14)
    feats = build_features(df)
    feat_cols = list(feats.columns)
    ths = [0.55,0.60,0.65,0.70,0.75,0.80,0.85]

    configs = [
        ('long', 16, 1.5, 2.5),
        ('short',16, 1.5, 2.5),
        ('long', 16, 1.0, 2.0),
        ('short',16, 1.0, 2.0),
    ]
    for direction, hz, tp, sl in configs:
        print(f"\n=== {direction} H={hz} TP={tp}xATR SL={sl}xATR ===")
        print(f"{'th':>5}{'trades':>8}{'WR%':>8}{'exp$':>9}{'pnl$':>10}")
        for th,n,wr,exp,pnl in evaluate(df,atr,feats,feat_cols,direction,hz,tp,sl,ths):
            print(f"{th:>5}{n:>8}{wr:>8.2f}{exp:>9.3f}{pnl:>10.1f}")

if __name__=='__main__':
    main()
