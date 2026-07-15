"""گزارش نهایی config برنده‌ی استراتژی ۱۷ (good4 [9,15,20,21], TP1.0/SL1.5, thr0.55)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from scipy import stats
import lightgbm as lgb
import indicators as ind
from backtest import load_data, run_backtest
import features as feat

df = load_data(os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv'))
atr = ind.atr(df, 14); X = feat.build_features(df)
close = df['close']; ema50 = ind.ema(close, 50); ema200 = ind.ema(close, 200); rsi = ind.rsi(close, 14)
hr = df['dt'].dt.hour
uptrend = (close > ema50) & (ema50 > ema200)
n_days = df['dt'].dt.normalize().nunique()
hours = [9, 15, 20, 21]
pull = (rsi < 55) & (rsi > rsi.shift(1))
prim = (uptrend & pull & hr.isin(hours)).fillna(False).values
sig_idx = np.array([i for i in np.where(prim)[0] if i < len(df) - 60
                    and not X.iloc[i].isna().any() and not np.isnan(atr.values[i])])
tp, sl, hz, thr = 1.0, 1.5, 48, 0.55; be = sl / (tp + sl)
high = df['high'].values; low = df['low'].values; c = df['close'].values; av = atr.values; n = len(df); L = {}
for i in sig_idx:
    a = av[i]
    if np.isnan(a) or a <= 0: continue
    e = c[i]; TP = e + tp * a; SL = e - sl * a; lab = 0
    for j in range(i + 1, min(i + 1 + hz, n)):
        if low[j] <= SL and high[j] >= TP: lab = 0; break
        if high[j] >= TP: lab = 1; break
        if low[j] <= SL: lab = 0; break
    L[i] = lab
keys = np.array(sorted(L.keys())); sig = keys; y = np.array([L[i] for i in sig]); Xv = X.iloc[sig].values
bnd = np.linspace(int(n * 0.4), n, 7).astype(int); ap = np.zeros(n, bool)
for k in range(6):
    lo, hi = bnd[k], bnd[k + 1]; tm = (sig >= lo) & (sig < hi); trm = sig < (lo - hz - 50)
    if trm.sum() < 200 or tm.sum() == 0: continue
    ytr = y[trm]
    if len(np.unique(ytr)) < 2: continue
    pr = np.zeros(tm.sum())
    for sd in (42, 7, 123):
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=31, max_depth=6,
                               subsample=0.8, colsample_bytree=0.8, min_child_samples=30,
                               reg_lambda=1.0, random_state=sd, n_jobs=-1, verbose=-1)
        m.fit(Xv[trm], ytr); pr += m.predict_proba(Xv[tm])[:, 1]
    pr /= 3; ap[sig[tm][pr >= thr]] = True
e = np.zeros(n, bool); e[ap] = True
st, tr = run_backtest(df, e, None, None, 'long', 0.20, hz, False, sl_series=av * sl, tp_series=av * tp)
def pv(k, nn, p0): return 1 - stats.norm.cdf((k / nn - p0) / np.sqrt(p0 * (1 - p0) / nn)) if nn else 1
nt, wr = st['n_trades'], st['win_rate']
print(f"FINAL n={nt} WR={wr:.2f}% exp={st['expectancy']:+.3f} PnL={st['total_pnl']:+.0f} "
      f"avgW={st['avg_win']:+.2f} avgL={st['avg_loss']:+.2f} p={pv(round(wr/100*nt),nt,be):.4f}")
d = df['dt'].dt.normalize().values[tr['entry_bar'].values]; pdd = pd.Series(d).value_counts()
print(f"tpd_cal={nt/n_days:.2f} tpd_active_mean={pdd.mean():.2f} median={pdd.median():.0f} max={pdd.max()}")
tr = tr.reset_index(drop=True); bl = np.array_split(tr, 5)
print("STABILITY:")
for bi, b in enumerate(bl):
    w = (b['outcome'] == 'win').mean() * 100
    print(f"  block{bi+1}: n={len(b)} WR={w:.2f}% exp={b['pnl'].mean():+.3f}")
