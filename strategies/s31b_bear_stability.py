"""
S31b — اعتبارسنجی پایداری مغز نزولی در نقطهٔ کار PF-محور (TP1.4/SL1.7, thr=0.66)
که در S31 بهترین نتیجهٔ معنادار را داد (WR=58.4%, PF=1.49, exp=+1.71$, p=0.015).

هدف: پایداری ۵-بلوکه + مقایسه با نقطهٔ کار BE60. اثبات اینکه edge نزولی آرتیفکت
یک بازهٔ خاص نیست بلکه در طول زمان تکرار می‌شود.
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS, MIN_TRAIN_FRAC, EMBARGO, SPREAD = 6, 0.40, 50, 0.20
SEEDS = [42, 7, 123]


def _lgbm(seed):
    return lgb.LGBMClassifier(n_estimators=500, learning_rate=0.025, num_leaves=32,
        max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
        reg_lambda=2.0, random_state=seed, verbose=-1)


def purged_wf(X, Y, idx, n, seed):
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold; te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if te_start >= te_end: continue
        m = _lgbm(seed); m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
    return proba


df = load_data(); n = len(df)
c = df['close'].values
atr = ind.atr(df, 14)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
print("ساخت feature ها ...")
feats = build_features(df); cols = list(feats.columns)
cand_bear = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)

HZ, TP_M, SL_M, THR = 48, 1.4, 1.7, 0.66
y = make_target(df, HZ, TP_M, SL_M, atr, 'short')
data = feats.copy(); data['y'] = y; data['cand'] = cand_bear
valid = data.dropna(subset=cols + ['y']); valid = valid[valid['cand']]
X = valid[cols].values; Y = valid['y'].values.astype(int); idx = valid.index.values
proba = np.nanmean(np.vstack([purged_wf(X, Y, idx, n, s) for s in SEEDS]), axis=0)

ent = cand_bear & ~np.isnan(proba) & (proba >= THR)
s, tr = run_backtest(df, ent, None, None, 'short', SPREAD, HZ,
                     sl_series=SL_M*atr.values, tp_series=TP_M*atr.values, allow_overlap=False)
be = SL_M/(TP_M+SL_M)*100
nt = len(tr); wins = int((tr['outcome']=='win').sum())
pv = binomtest(wins, nt, be/100, alternative='greater').pvalue
gw = tr[tr['outcome']=='win']['pnl'].sum(); gl = abs(tr[tr['outcome']=='loss']['pnl'].sum())
pf = gw/gl
span = (df['dt'].iloc[-1]-df['dt'].iloc[0]).days
print("="*72)
print(f"مغز نزولی @ PF-point (TP{TP_M}/SL{SL_M}, thr={THR})")
print("="*72)
print(f"کل: n={nt} WR={s['win_rate']:.2f}% PF={pf:.3f} exp={s['expectancy']:+.3f}$ "
      f"pnl={s['total_pnl']:+.1f}$ tpd={nt/span*7/5:.2f} p(WR>{be:.0f})={pv:.4f}")

# پایداری ۵-بلوکه
print("\nپایداری ۵-بلوکه (بر اساس زمان ورود):")
edges = np.linspace(0, len(df), 6).astype(int)
allpos = 0
for b in range(5):
    m = (tr['entry_bar']>=edges[b]) & (tr['entry_bar']<edges[b+1]); sub = tr[m]
    if len(sub)==0: print(f"  بلوک {b+1}: بدون معامله"); continue
    wr = (sub['outcome']=='win').mean()*100; ex = sub['pnl'].mean()
    d0 = df['dt'].iloc[edges[b]].date(); d1 = df['dt'].iloc[edges[b+1]-1].date()
    pos = "✅" if ex>0 else "❌"
    if ex>0: allpos += 1
    print(f"  بلوک {b+1} [{d0}..{d1}]: n={len(sub)} WR={wr:.1f}% exp={ex:+.3f}$ PnL={sub['pnl'].sum():+.1f}$ {pos}")
print(f"\nبلوک‌های سودآور: {allpos}/5")

# آمار توصیفی معاملات
print(f"\nمیانگین برد: {tr[tr['outcome']=='win']['pnl'].mean():+.2f}$  "
      f"میانگین باخت: {tr[tr['outcome']=='loss']['pnl'].mean():+.2f}$  "
      f"نسبت r=avgWin/|avgLoss|: {tr[tr['outcome']=='win']['pnl'].mean()/abs(tr[tr['outcome']=='loss']['pnl'].mean()):.3f}")

# مقایسه: همین کاندید نزولی بدون مدل (خام short در هر کندل نزولی)
raw = cand_bear & ~np.isnan(atr.values)
sr, trr = run_backtest(df, raw, None, None, 'short', SPREAD, HZ,
                       sl_series=SL_M*atr.values, tp_series=TP_M*atr.values, allow_overlap=False)
print(f"\nمرجع: short خام در هر کندل نزولی (بدون مدل): "
      f"n={len(trr)} WR={sr['win_rate']:.2f}% exp={sr['expectancy']:+.3f}$ "
      f"pnl={sr['total_pnl']:+.1f}$  → مدل چقدر بهتر است؟")

# feature importance مغز نزولی (روی کل داده برای تفسیر)
m = _lgbm(42); m.fit(X, Y)
imp = pd.Series(m.feature_importances_, index=cols).sort_values(ascending=False)
print("\n۱۲ feature مهم مغز نزولی:")
for name, v in imp.head(12).items():
    print(f"  {name}: {v}")
