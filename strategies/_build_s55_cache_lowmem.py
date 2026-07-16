"""
ساختِ کشِ probaِ S55 با مدیریتِ حافظهٔ سخت‌گیرانه (محیطِ ۱GB RAM).
هر دارایی مستقل پردازش، بلافاصله آزاد (del + gc). feature ها float32.
خروجی: results/_s55_proba_cache.npz  (کلیدها: {asset}_{long|short})
"""
import sys, os, gc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

HZ = 48; TP_M = 1.0; SL_M = 1.5
N_FOLDS = 5; MIN_TRAIN = 0.45
SEEDS = [42, 7]
ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s55_proba_cache.npz')

# n_jobs=1 برای کنترلِ حافظه؛ n_estimators کمی کمتر
LGB = dict(objective='binary', n_estimators=200, learning_rate=0.05,
           num_leaves=31, max_depth=6, min_child_samples=80,
           subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=1)


def wf_proba(X_all, cols_ok, cand, y, seed, n):
    """walk-forward؛ X_all از قبل float32 numpy است."""
    valid_mask = cols_ok & cand & ~np.isnan(y)
    idx = np.where(valid_mask)[0]
    if len(idx) < 500:
        return np.full(n, np.nan, dtype=np.float32)
    X = X_all[idx]; Y = y[idx].astype(np.int8)
    N = len(X); mt = int(N * MIN_TRAIN); fold = max(1, (N - mt) // N_FOLDS)
    proba = np.full(n, np.nan, dtype=np.float32)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if tr_end >= N:
            break
        m = lgb.LGBMClassifier(random_state=seed, **LGB)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1].astype(np.float32)
        del m; gc.collect()
    return proba


out = {}
for a in ASSETS:
    print(f"  آموزشِ {a} ...", flush=True)
    df = load_data(f'data/{a}_M15.csv')
    n = len(df)
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    atrv = atr.values
    cL = (c > ema50) & (ema50 > ema200) & ~np.isnan(atrv)
    cS = (c < ema50) & (ema50 < ema200) & ~np.isnan(atrv)

    feats = build_features(df)
    cols = list(feats.columns)
    X_all = feats.values.astype(np.float32)
    cols_ok = ~np.isnan(X_all).any(axis=1)
    del feats; gc.collect()

    for d, cand in [('long', cL), ('short', cS)]:
        y = make_target(df, HZ, TP_M, SL_M, atr, d).astype(np.float32)
        ps = [wf_proba(X_all, cols_ok, cand, y, s, n) for s in SEEDS]
        out[f'{a}_{d}'] = np.nanmean(np.vstack(ps), axis=0).astype(np.float32)
        del y, ps; gc.collect()
        print(f"    {a}_{d}: signals={np.sum(~np.isnan(out[f'{a}_{d}']))}", flush=True)

    del df, X_all, cols_ok, cL, cS, atr, atrv, c, ema50, ema200; gc.collect()

np.savez_compressed(CACHE, **out)
print(f"\n✅ کش ذخیره شد: {CACHE}", flush=True)
print("کلیدها:", list(out.keys()), flush=True)
