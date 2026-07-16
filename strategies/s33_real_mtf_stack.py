"""
استراتژی ۳۳ (طرح P39 از strategy_plans.md): «هرم تاپ-داون واقعی» —
افزودن featureهای مولتی‌تایم‌فریمِ *واقعی* (از کندل‌های اصیل M30/H1/H4/D1/W1)
به مدل برندهٔ S25 و آزمون A/B دقیق.

--------------------------------------------------------------------------------
انگیزهٔ علمی (قانون L1: اطلاعات > معماری):
--------------------------------------------------------------------------------
featureهای MTF فعلیِ مدل (در engine/features.py خطوط ۹۴–۱۰۱) جعلی‌اند: روند
«H1/H4/D1» صرفاً EMA بلندتر روی همان سری M15 است و کندل واقعی تایم‌فریم بالا را
نمی‌بیند. حالا که دادهٔ هر ۷ تایم‌فریم موجود است، featureهای MTF را از کندل‌های
اصیل هر تایم‌فریم می‌سازیم (ماژول engine/mtf.py با هم‌ترازسازی as-of بدون look-ahead).

فرضیه: اگر «دیدن طلا از چشم رزولوشن‌های واقعی بالاتر» اطلاعات تازه‌ای اضافه کند،
باید WR و/یا PF مدل را بهبود دهد.

روش: A/B دقیق — BASELINE (۵۹ feature فعلی) در برابر AUGMENTED (+۹۹ MTF واقعی)،
همان کاندید، همان Purged Walk-Forward (embargo=50)، همان seedها، همان نقاط اجرا.
ورود open کندل بعدی + اسپرد ۰.۲$. دو نقطهٔ کار: WR (TP1.0/SL1.5/thr0.62) و
PF برندهٔ P01 (TP1.4/SL1.7/thr0.65).

نکتهٔ مهندسی: به‌خاطر محدودیت RAM (~۱GB)، تمام featureها float32 و فقط ماتریس
کاندیدها در حافظه نگه داشته می‌شود؛ کپی‌ها با del/gc آزاد می‌شوند.

اعتبار: Purged Walk-Forward (embargo=50) + open-next + spread 0.2$ + p-value binomial.
"""
import sys, gc; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from mtf import build_mtf_features, add_alignment_features
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40
EMBARGO = 50
HZ = 48
SPREAD = 0.20
SEEDS = [42, 7, 123]

print("بارگذاری داده M15 ...", flush=True)
df = load_data()
n = len(df)
c = df['close'].values
atr = ind.atr(df, 14)
atr_v = atr.values.astype(np.float64)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values

print("ساخت feature های پایه (S25، شامل MTF جعلی) ...", flush=True)
feats = build_features(df).astype(np.float32)
BASE_COLS = list(feats.columns)
print(f"  feature پایه: {len(BASE_COLS)}", flush=True)

print("ساخت feature های MTF واقعی (as-of بدون look-ahead) ...", flush=True)
mtf = add_alignment_features(build_mtf_features(df, tfs=('M30', 'H1', 'H4', 'D1', 'W1')))
mtf = mtf.astype(np.float32)
MTF_COLS = list(mtf.columns)
print(f"  feature MTF واقعی: {len(MTF_COLS)}", flush=True)

cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr_v)
print(f"کاندید پایه (uptrend long): {int(cand.sum())} از {n}", flush=True)
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days

# پیش‌محاسبهٔ ماتریس‌های feature به‌صورت numpy float32 (بدون نگه‌داشتن کپی‌های DataFrame)
BASE_MAT = feats.values  # (n, 59) float32
MTF_MAT = mtf.values     # (n, 99) float32
del mtf; gc.collect()

# برچسب‌ها را برای دو نقطهٔ کار پیش‌محاسبه می‌کنیم (label = همان RR اجرا، نکتهٔ P01)
LABELS = {}
for tp, sl in [(1.0, 1.5), (1.4, 1.7)]:
    LABELS[(tp, sl)] = make_target(df, HZ, tp, sl, atr, 'long')


def build_valid_index(fcols_mask_cols, label_key):
    """اندیس نمونه‌های معتبر (کاندید + بدون NaN در feature/label) را برمی‌گرداند."""
    y = LABELS[label_key]
    # NaN در ماتریس‌های انتخاب‌شده
    return y


def wf_proba(use_mtf, label_key, seed):
    """
    Purged Walk-Forward. use_mtf=False → فقط BASE_MAT، True → concat BASE+MTF.
    حافظه‌بهینه: ماتریس X فقط روی نمونه‌های معتبر ساخته می‌شود.
    """
    tp, sl = label_key
    y = LABELS[label_key]
    # ماسک معتبر: کاندید + y غیر NaN + هیچ NaN در feature ها
    base_ok = ~np.isnan(BASE_MAT).any(axis=1)
    if use_mtf:
        feat_ok = base_ok & ~np.isnan(MTF_MAT).any(axis=1)
    else:
        feat_ok = base_ok
    valid = cand & feat_ok & ~np.isnan(y)
    idx = np.where(valid)[0]
    if use_mtf:
        X = np.hstack([BASE_MAT[idx], MTF_MAT[idx]]).astype(np.float32)
    else:
        X = BASE_MAT[idx].astype(np.float32)
    Y = y[idx].astype(np.int8)
    N = len(X)
    mt = int(N * MIN_TRAIN_FRAC)
    fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan, dtype=np.float64)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if te_start >= te_end:
            continue
        m = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.04, num_leaves=32, max_depth=6,
            subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1, n_jobs=2)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
        del m; gc.collect()
    del X, Y; gc.collect()
    return proba


def ens_proba(use_mtf, label_key):
    acc = np.zeros(n); cnt = np.zeros(n)
    for s in SEEDS:
        p = wf_proba(use_mtf, label_key, s)
        ok = ~np.isnan(p)
        acc[ok] += p[ok]; cnt[ok] += 1
        del p; gc.collect()
    out = np.full(n, np.nan)
    nz = cnt > 0
    out[nz] = acc[nz] / cnt[nz]
    return out


def eval_point(proba, thr, tp_exec, sl_exec):
    ent = cand & ~np.isnan(proba) & (proba >= thr)
    s, tr = run_backtest(df, ent, None, None, 'long', SPREAD, HZ,
                         sl_series=sl_exec * atr_v, tp_series=tp_exec * atr_v,
                         allow_overlap=False)
    nt = s['n_trades']
    if nt < 30:
        return None
    wr = s['win_rate']
    gross_win = tr[tr['outcome'] == 'win']['pnl'].sum()
    gross_loss = -tr[tr['outcome'] == 'loss']['pnl'].sum()
    pf = gross_win / gross_loss if gross_loss > 1e-9 else np.inf
    tpd = nt / span_days * 7 / 5
    be = sl_exec / (tp_exec + sl_exec) * 100
    wins = int(round(wr / 100 * nt))
    pv = binomtest(wins, nt, be / 100, alternative='greater').pvalue
    return dict(n=nt, wr=wr, pf=pf, exp=s['expectancy'], pnl=s['total_pnl'],
                tpd=tpd, be=be, pv=pv)


def show(label, r):
    if r is None:
        print(f"  {label}: <30 trade", flush=True); return
    print(f"  {label:12s}: n={r['n']:4d}  WR={r['wr']:.2f}%  PF={r['pf']:.3f}  "
          f"exp={r['exp']:+.3f}$  pnl={r['pnl']:+.0f}$  tpd={r['tpd']:.2f}  "
          f"p(WR>{r['be']:.0f})={r['pv']:.4f}", flush=True)


POINTS = [
    ('نقطهٔ WR (TP1.0/SL1.5/thr0.62)', 1.0, 1.5, 0.62),
    ('نقطهٔ PF (TP1.4/SL1.7/thr0.65)', 1.4, 1.7, 0.65),
]

for pname, tp, sl, thr in POINTS:
    print("\n" + "=" * 74, flush=True)
    print(f"A/B در {pname}", flush=True)
    print("=" * 74, flush=True)
    pb = ens_proba(False, (tp, sl))
    rb = eval_point(pb, thr, tp, sl); show('BASELINE', rb)
    del pb; gc.collect()
    pa = ens_proba(True, (tp, sl))
    ra = eval_point(pa, thr, tp, sl); show('AUG +MTF', ra)
    del pa; gc.collect()
    if rb and ra:
        print(f"  Δ (AUG-BASE): ΔWR={ra['wr']-rb['wr']:+.2f}پ.پ.  "
              f"ΔPF={ra['pf']-rb['pf']:+.3f}  Δexp={ra['exp']-rb['exp']:+.3f}$  "
              f"Δpnl={ra['pnl']-rb['pnl']:+.0f}$", flush=True)

# اهمیت feature: آیا مدل واقعاً MTF واقعی را استفاده می‌کند؟
print("\n" + "=" * 74, flush=True)
print("اهمیت feature در مدل AUG (نقطهٔ WR) — رتبهٔ MTF واقعی (★)", flush=True)
print("=" * 74, flush=True)
y = LABELS[(1.0, 1.5)]
base_ok = ~np.isnan(BASE_MAT).any(axis=1) & ~np.isnan(MTF_MAT).any(axis=1)
valid = cand & base_ok & ~np.isnan(y)
idx = np.where(valid)[0]
X = np.hstack([BASE_MAT[idx], MTF_MAT[idx]]).astype(np.float32)
Y = y[idx].astype(np.int8)
mt = int(len(X) * 0.7)
m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.04, num_leaves=32,
                       max_depth=6, subsample=0.8, colsample_bytree=0.75,
                       min_child_samples=80, reg_lambda=2.0, random_state=42,
                       verbose=-1, n_jobs=2)
m.fit(X[:mt], Y[:mt])
allcols = BASE_COLS + MTF_COLS
imp = pd.Series(m.feature_importances_, index=allcols).sort_values(ascending=False)
mtf_set = set(MTF_COLS)
print("Top 20 feature (★=MTF واقعی):", flush=True)
for rank, (name, val) in enumerate(imp.head(20).items(), 1):
    star = '★' if name in mtf_set else ' '
    print(f"  {rank:2d}. {star} {name:26s} {val}", flush=True)
print(f"\nحضور MTF واقعی: {sum(1 for x in imp.head(20).index if x in mtf_set)}/20 top20، "
      f"{sum(1 for x in imp.head(40).index if x in mtf_set)}/40 top40", flush=True)
print("\nتمام.", flush=True)
