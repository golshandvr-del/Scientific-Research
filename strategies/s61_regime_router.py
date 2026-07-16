"""
S61 — Regime-Router با نسبت‌دهیِ «سودِ خالص» (PARADIGM v2: محلِ درستِ استفاده)
================================================================================
فرضیهٔ محوریِ User Note 2:
  «مشکل، خودِ استراتژی‌ها نیست؛ محلِ درستِ استفاده از آن‌هاست.»
  اگر رژیمِ درستِ هر استراتژی را بشناسیم و هرکدام را فقط در محلِ خودش فعال کنیم،
  «سودِ خالص» بالا می‌رود.

معیارِ موفقیت: فقط «سودِ خالصِ تجمعی» (total_pnl پس از اسپرد). نه WR، نه فرکانس.

روش:
  ۱) دو جریانِ متخصص روی XAUUSD:
       - Bull-ML  (long، فقط در رژیمِ صعودی، افق ۴۸، TP1.0/SL1.5×ATR)
       - Bear-ML  (short، فقط در رژیمِ نزولی، افق ۴۸، TP1.4/SL1.7×ATR)
     probaها با walk-forward (بدون look-ahead) و ensembleِ ۲-seed ساخته می‌شوند.
  ۲) رژیمِ زندهٔ هر کندل با دو محور کمی‌سازی می‌شود (همه با shift → بدون آینده):
       محورِ جهت    : up / down / range  (EMA50 vs EMA200 و قیمت)
       محورِ کارایی : Efficiency-Ratio کافمن (روندی‌بودن) → سطلِ trend/chop
  ۳) «سودِ خالصِ» هر جریان در هر سطلِ رژیم اندازه‌گیری می‌شود.
  ۴) Router: در هر سطل، همان جریانی فعال می‌شود که سودِ خالصِ مثبت و بیشتر دارد
     (یادگیریِ Router روی نیمهٔ اولِ IS، ارزیابی روی نیمهٔ دومِ OOS → بدون نشتِ آینده).
  ۵) سودِ خالصِ Router با baselineها (bull-تنها، bear-تنها، هر دو بدون گیت) مقایسه می‌شود.
"""
import sys, os, gc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

HZ = 48
N_FOLDS = 5; MIN_TRAIN = 0.45
SEEDS = [42, 7]
SPREAD = 0.20
ER_WIN = 32                     # پنجرهٔ Efficiency-Ratio (کافمن)
ER_TREND_THR = 0.30             # ER بالاتر = بازارِ روندی

LGB = dict(objective='binary', n_estimators=200, learning_rate=0.05,
           num_leaves=31, max_depth=6, min_child_samples=80,
           subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=1)


def wf_proba(X_all, cols_ok, cand, y, seed, n):
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


def efficiency_ratio(close, win):
    """ER کافمن: |تغییرِ خالص| / مجموعِ |تغییرات|. shift(1) برای بدونِ آینده."""
    close = pd.Series(close)
    change = close.diff(win).abs()
    vol = close.diff().abs().rolling(win).sum()
    er = (change / vol).replace([np.inf, -np.inf], np.nan)
    return er.shift(1).values   # فقط اطلاعاتِ تا کندلِ قبل


print("=== S61: Regime-Router (معیار: سودِ خالص) — XAUUSD ===\n", flush=True)

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
c = df['close'].values
atr = ind.atr(df, 14)
atrv = atr.values
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values

# رژیمِ جهت (بدون آینده: EMA/قیمتِ همین کندل که از گذشته ساخته شده‌اند)
up_reg = (c > ema50) & (ema50 > ema200)
down_reg = (c < ema50) & (ema50 < ema200)
# محورِ کارایی
er = efficiency_ratio(c, ER_WIN)
trendy = er >= ER_TREND_THR     # روندی

# کاندیدهای هر جریان
cL = up_reg & ~np.isnan(atrv)
cS = down_reg & ~np.isnan(atrv)

print(f"کندل‌ها: {n} | رژیمِ صعودی: {cL.sum()} | رژیمِ نزولی: {cS.sum()} | روندی(ER): {np.nansum(trendy)}", flush=True)

# probaها
feats = build_features(df)
X_all = feats.values.astype(np.float32)
cols_ok = ~np.isnan(X_all).any(axis=1)
del feats; gc.collect()

print("ساختِ probaِ Bull-ML ...", flush=True)
yL = make_target(df, HZ, 1.0, 1.5, atr, 'long').astype(np.float32)
pL = np.nanmean(np.vstack([wf_proba(X_all, cols_ok, cL, yL, s, n) for s in SEEDS]), axis=0)
print("ساختِ probaِ Bear-ML ...", flush=True)
yS = make_target(df, HZ, 1.4, 1.7, atr, 'short').astype(np.float32)
pS = np.nanmean(np.vstack([wf_proba(X_all, cols_ok, cS, yS, s, n) for s in SEEDS]), axis=0)
del X_all, cols_ok; gc.collect()

# آستانهٔ ورودِ هر جریان (کیفیت). چون معیار سودِ خالص است، آستانه را متعادل می‌گیریم.
THR_L, THR_S = 0.60, 0.60

# سیگنال‌های خام هر جریان
sigL = cL & (pL >= THR_L)
sigS = cS & (pS >= THR_S)

# بک‌تستِ هر جریان به‌تنهایی (کلِ داده) — برای دیدِ کلی
slL = 1.5 * atrv; tpL = 1.0 * atrv
slS = 1.7 * atrv; tpS = 1.4 * atrv
stL, _ = run_backtest(df, sigL, None, None, 'long', spread=SPREAD, max_hold=HZ, sl_series=slL, tp_series=tpL)
stS, _ = run_backtest(df, sigS, None, None, 'short', spread=SPREAD, max_hold=HZ, sl_series=slS, tp_series=tpS)
print(f"\n[کلِ داده] Bull-ML:  n={stL['n_trades']:5d}  WR={stL['win_rate']:.1f}%  سودِ خالص={stL['total_pnl']:8.1f}$  اکسپکتنسی={stL['expectancy']:.3f}$", flush=True)
print(f"[کلِ داده] Bear-ML:  n={stS['n_trades']:5d}  WR={stS['win_rate']:.1f}%  سودِ خالص={stS['total_pnl']:8.1f}$  اکسپکتنسی={stS['expectancy']:.3f}$", flush=True)

# ---------------------------------------------------------------------------
# تحلیلِ سودِ خالص به‌تفکیکِ سطلِ رژیم (محورِ کارایی: trend/chop)
# هر سیگنال به سطلی که در آن رخ داده نسبت داده می‌شود.
# ---------------------------------------------------------------------------
def pnl_by_bucket(df, sig, direction, sl_s, tp_s, bucket_mask):
    """سودِ خالصِ سیگنال‌هایی که در bucket_mask هستند."""
    s = sig & bucket_mask
    st, _ = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st

print("\n--- سودِ خالص به‌تفکیکِ سطلِ کارایی (Efficiency-Ratio) ---", flush=True)
print(f"{'جریان':10s} {'سطل':8s} {'n':>6s} {'WR%':>6s} {'سودِخالص$':>12s} {'اکسپکتنسی$':>12s}", flush=True)
buckets = {'روندی': trendy == True, 'رنج': (trendy == False)}
for name, sig, d, sl_s, tp_s in [('Bull-ML', sigL, 'long', slL, tpL),
                                  ('Bear-ML', sigS, 'short', slS, tpS)]:
    for bname, bmask in buckets.items():
        st = pnl_by_bucket(df, sig, d, sl_s, tp_s, np.nan_to_num(bmask, nan=False).astype(bool))
        print(f"{name:10s} {bname:8s} {st['n_trades']:6d} {st['win_rate']:6.1f} {st['total_pnl']:12.1f} {st['expectancy']:12.3f}", flush=True)

print("\nتمام (فازِ ۱: نسبت‌دهیِ سودِ خالص). فازِ ۲ = ساختِ Router از این جدول.", flush=True)

# ذخیرهٔ probaها و رژیم برای فازِ Router (کش سبک)
np.savez_compressed(os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz'),
                    pL=pL.astype(np.float32), pS=pS.astype(np.float32),
                    up_reg=up_reg, down_reg=down_reg, er=er.astype(np.float32),
                    atrv=atrv.astype(np.float32))
print("کش S61 ذخیره شد.", flush=True)
