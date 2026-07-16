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

فرضیه: اگر «دیدن طلا از چشم رزولوشن‌های واقعی بالاتر» اطلاعات تازه‌ای اضافه کند
(نه صرفاً هموارسازی دیگری از M15)، باید WR و/یا PF مدل را بهبود دهد.

--------------------------------------------------------------------------------
روش (تکرار مو‌به‌مو Recipe-S25 + پروتکل A/B):
--------------------------------------------------------------------------------
  BASELINE : مدل S25 با featureهای فعلی (شامل MTF جعلی).
  AUGMENTED: BASELINE + ۹۹ feature MTF واقعی (from engine/mtf.py).
  - همان کاندید پایه (uptrend long: close>ema50>ema200).
  - همان Purged Walk-Forward (embargo=50)، همان seedها، همان نقاط اجرا.
  - ورود open کندل بعدی + اسپرد ۰.۲$.
  - دو نقطهٔ کار ارزیابی می‌شود:
      (A) نقطهٔ WR: TP1.0/SL1.5/thr0.62  (هدف WR>60 + فرکانس)
      (B) نقطهٔ PF (برندهٔ P01): TP1.4/SL1.7/thr0.65 (هدف PF>1.3)
  - معیار پذیرش L1: بهبود هم‌زمانِ (یا دست‌کم بدون افت) WR و PF نسبت به baseline.

اعتبار: Purged Walk-Forward (embargo=50) + open-next + spread 0.2$ + گزارش p-value.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from mtf import build_mtf_features, add_alignment_features
import warnings; warnings.filterwarnings('ignore')

# ---------- پارامترهای ثابت (همان S25/S26) ----------
N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40
EMBARGO = 50
HZ = 48
SPREAD = 0.20
SEEDS = [42, 7, 123]

print("بارگذاری داده M15 ...")
df = load_data()
n = len(df)
c = df['close'].values
atr = ind.atr(df, 14)
atr_v = atr.values
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values

print("ساخت feature های پایه (S25، شامل MTF جعلی) ...")
feats = build_features(df)
BASE_COLS = list(feats.columns)
print(f"  تعداد feature پایه: {len(BASE_COLS)}")

print("ساخت feature های MTF واقعی (M30/H1/H4/D1/W1) با as-of بدون look-ahead ...")
mtf = build_mtf_features(df, tfs=('M30', 'H1', 'H4', 'D1', 'W1'))
mtf = add_alignment_features(mtf)
MTF_COLS = list(mtf.columns)
print(f"  تعداد feature MTF واقعی: {len(MTF_COLS)}")

# دیتافریم افزوده
feats_aug = pd.concat([feats, mtf], axis=1)
AUG_COLS = BASE_COLS + MTF_COLS

# کاندید پایه S25: روند صعودی long-only
cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr_v)
print(f"کاندید پایه (uptrend long): {int(cand.sum())} از {n}")
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days


def walk_forward_proba(feature_df, fcols, label_tp, label_sl, seed):
    """Purged Walk-Forward با embargo. خروجی proba هم‌طول df."""
    y = make_target(df, HZ, label_tp, label_sl, atr, 'long')
    data = feature_df.copy()
    data['y'] = y
    data['cand'] = cand
    valid = data.dropna(subset=fcols + ['y'])
    valid = valid[valid['cand']]
    X = valid[fcols].values
    Y = valid['y'].values.astype(int)
    idx = valid.index.values
    N = len(X)
    mt = int(N * MIN_TRAIN_FRAC)
    fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if te_start >= te_end:
            continue
        m = lgb.LGBMClassifier(
            n_estimators=300, learning_rate=0.04, num_leaves=32, max_depth=6,
            subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1, n_jobs=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
    return proba


def ens_proba(feature_df, fcols, label_tp, label_sl):
    probas = [walk_forward_proba(feature_df, fcols, label_tp, label_sl, s) for s in SEEDS]
    return np.nanmean(np.vstack(probas), axis=0)


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
        print(f"  {label}: <30 trade"); return
    print(f"  {label:12s}: n={r['n']:4d}  WR={r['wr']:.2f}%  PF={r['pf']:.3f}  "
          f"exp={r['exp']:+.3f}$  pnl={r['pnl']:+.0f}$  tpd={r['tpd']:.2f}  "
          f"p(WR>{r['be']:.0f})={r['pv']:.4f}")


# =================================================================
# A/B روی دو نقطهٔ کار کلیدی
# =================================================================
POINTS = [
    ('نقطهٔ WR  (TP1.0/SL1.5/thr0.62)', 1.0, 1.5, 0.62),
    ('نقطهٔ PF  (TP1.4/SL1.7/thr0.65)', 1.4, 1.7, 0.65),
]

summary = {}
for pname, tp, sl, thr in POINTS:
    print("\n" + "=" * 74)
    print(f"A/B در {pname}")
    print("=" * 74)
    # baseline
    pb = ens_proba(feats, BASE_COLS, tp, sl)
    rb = eval_point(pb, thr, tp, sl)
    show('BASELINE', rb)
    # augmented (+MTF واقعی)
    pa = ens_proba(feats_aug, AUG_COLS, tp, sl)
    ra = eval_point(pa, thr, tp, sl)
    show('AUG +MTF', ra)
    if rb and ra:
        dwr = ra['wr'] - rb['wr']
        dpf = ra['pf'] - rb['pf']
        print(f"  Δ (AUG-BASE): ΔWR={dwr:+.2f}پ.پ.  ΔPF={dpf:+.3f}  "
              f"Δexp={ra['exp']-rb['exp']:+.3f}$")
    summary[pname] = (rb, ra)

# =================================================================
# اهمیت feature های MTF (آیا مدل واقعاً از آن‌ها استفاده می‌کند؟)
# =================================================================
print("\n" + "=" * 74)
print("اهمیت feature ها در مدل AUGMENTED (نقطهٔ WR) — رتبهٔ MTF واقعی")
print("=" * 74)
y = make_target(df, 1.0, 1.5, atr, 'long') if False else make_target(df, HZ, 1.0, 1.5, atr, 'long')
data = feats_aug.copy(); data['y'] = y; data['cand'] = cand
valid = data.dropna(subset=AUG_COLS + ['y']); valid = valid[valid['cand']]
X = valid[AUG_COLS].values; Y = valid['y'].values.astype(int)
mt = int(len(X) * 0.7)
m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.04, num_leaves=32,
                       max_depth=6, subsample=0.8, colsample_bytree=0.75,
                       min_child_samples=80, reg_lambda=2.0, random_state=42,
                       verbose=-1, n_jobs=-1)
m.fit(X[:mt], Y[:mt])
imp = pd.Series(m.feature_importances_, index=AUG_COLS).sort_values(ascending=False)
mtf_set = set(MTF_COLS)
print("Top 20 feature کل مدل (★ = MTF واقعی):")
for rank, (name, val) in enumerate(imp.head(20).items(), 1):
    star = '★' if name in mtf_set else ' '
    print(f"  {rank:2d}. {star} {name:24s} {val}")
n_mtf_top20 = sum(1 for name in imp.head(20).index if name in mtf_set)
n_mtf_top40 = sum(1 for name in imp.head(40).index if name in mtf_set)
print(f"\nحضور MTF واقعی: {n_mtf_top20}/20 در top20 ، {n_mtf_top40}/40 در top40")

print("\nتمام. (نتیجه در results/ ثبت می‌شود)")
