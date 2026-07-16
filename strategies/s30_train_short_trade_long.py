"""
استراتژی ۳۰ (طرح P31 از strategy_plans.md، گروه F): Train-Short, Trade-Long

ایده (سند P31):
  مدل روی «هر دو جهت» آموزش ببیند (نمونه‌های short هم با برچسب short-win تولید شوند)
  اما در اجرا فقط long معامله شود. فرضیه: یادگیری ساختار دوطرفهٔ بازار (multi-task /
  data-augmentation) بازنمایی داخلی مدل را غنی‌تر می‌کند و دقت *همان سیگنال‌های long*
  را بالا می‌برد. هزینهٔ آزمایش تقریباً صفر است.

پیاده‌سازی multi-task با «data-augmentation جهت‌آگاه»:
  - هر ردیف کاندید یک بار به‌صورت long و (در صورت واجد شرط) یک بار به‌صورت short وارد
    مجموعهٔ آموزش می‌شود.
  - برای اینکه مدل «جهت» را بفهمد، feature ها *قرینه‌سازیِ جهتی* می‌شوند: featureهای
    جهت‌دار (بازده‌ها، شیب، فاصله‌ها، MACD، di_diff، ...) در نمونهٔ short در -1 ضرب
    می‌شوند و featureهای بی‌جهت (ATR، عرض BB، حجم، RSI-محور نوسان) دست‌نخورده می‌مانند.
    برچسب = «آیا در آن جهت TP قبل از SL خورد؟». یک ستون direction هم اضافه می‌شود.
  - در استنتاج، فقط ردیف‌های long (direction=+1، feature اصلی) امتیازدهی می‌شوند.
  A/B: baseline (فقط long، مثل S25) در برابر augmented (long+short mirrored در آموزش).

⚠️ چون آینهٔ short «همان کندل long با feature قرینه» است، هیچ نشت زمانی جدید نداریم؛
اما purged walk-forward روی محور زمان همچنان رعایت می‌شود.
"""
import sys; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np, pandas as pd
import lightgbm as lgb
import _base_s25 as B
from features import make_target
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

print("="*70)
print("P31 — Train-Short, Trade-Long (multi-task data augmentation)")
print("="*70)

base = B.load_base()
df, atr, cand = base['df'], base['atr'], base['cand']
feats, cols, n = base['feats'], base['cols'], base['n']
c = base['c']; ema50 = base['ema50']; ema200 = base['ema200']

# برچسب long (نقطهٔ کار پایه) و short (قرینه)
y_long = make_target(df, B.HZ, B.TP_M, B.SL_M, atr, 'long')
y_short = make_target(df, B.HZ, B.TP_M, B.SL_M, atr, 'short')

# کاندید short = زیررژیم نزولی (برای augmentation معنادار؛ L8)
cand_short = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)

# --- تعیین featureهای جهت‌دار که باید در نمونهٔ short قرینه شوند ---
DIRECTIONAL = []
for col in cols:
    if any(col.startswith(p) for p in ['ret_', 'slope_', 'dist_ema', 'macd',
                                        'di_diff', 'zscore_', 'trend_', 'vwap_dist',
                                        'ema50_dist', 'dist_daily_open', 'weekly_rev',
                                        'early_atr', 'streak']):
        DIRECTIONAL.append(col)
# featureهایی مثل bb_pos, stoch, rsi, close_pos_in_range حول ۰.۵/۵۰ متقارن‌اند →
# قرینهٔ درست = «آینه حول مرکز». آنها را جدا مدیریت می‌کنیم:
CENTERED = {'bb_pos': 1.0, 'close_pos_in_range': 1.0, 'stoch_k': 100.0,
            'stoch_d': 100.0, 'rsi_7': 100.0, 'rsi_14': 100.0, 'rsi_21': 100.0}
print(f"featureهای جهت‌دار (×-1 در short): {len(DIRECTIONAL)}")
print(f"featureهای مرکزی (آینه حول مرکز): {list(CENTERED.keys())}")

def mirror_features(Fdf):
    """نسخهٔ short-mirrored از یک دیتافریم feature."""
    M = Fdf.copy()
    for col in DIRECTIONAL:
        if col in M.columns:
            M[col] = -M[col]
    for col, ctr in CENTERED.items():
        if col in M.columns:
            M[col] = ctr - M[col]
    return M

# =====================================================================
# ساخت مجموعه‌های آموزش
# =====================================================================
# long rows
long_data = feats.copy(); long_data['y'] = y_long; long_data['cand'] = cand
long_valid = long_data.dropna(subset=cols + ['y']); long_valid = long_valid[long_valid['cand']]

# short rows (mirrored features)
short_feats = mirror_features(feats)
short_data = short_feats.copy(); short_data['y'] = y_short; short_data['cand'] = cand_short
short_valid = short_data.dropna(subset=cols + ['y']); short_valid = short_valid[short_valid['cand']]

print(f"\nنمونه‌های long valid: {len(long_valid)}, نمونه‌های short valid: {len(short_valid)}")

# محور زمان برای walk-forward: از اندیس long استفاده می‌کنیم (اجرا فقط long است)
idx_long = long_valid.index.values
X_long = long_valid[cols].values
Y_long = long_valid['y'].values.astype(int)

# short، با direction=-1 و long با direction=+1 (feature اضافه)
Xl = np.column_stack([X_long, np.ones(len(X_long))])
Yl = Y_long
idx_l = idx_long

X_short = short_valid[cols].values
Y_short = short_valid['y'].values.astype(int)
idx_short = short_valid.index.values
Xs = np.column_stack([X_short, -np.ones(len(X_short))])

def wf_baseline(seed):
    """فقط long (مثل S25) با feature direction ثابت +1."""
    N = len(Xl); mt = int(N * B.MIN_TRAIN_FRAC); fold = (N - mt)//B.N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(B.N_FOLDS):
        tr_end = mt + k*fold; te_start = tr_end + B.EMBARGO
        te_end = tr_end + fold if k < B.N_FOLDS-1 else N
        if te_start >= te_end: continue
        m = B._lgbm(seed); m.fit(Xl[:tr_end], Yl[:tr_end])
        proba[idx_l[te_start:te_end]] = m.predict_proba(Xl[te_start:te_end])[:,1]
    return proba

def wf_augmented(seed):
    """آموزش روی long+short(mirrored)؛ استنتاج فقط روی long (direction=+1).
    برای جلوگیری از نشت: در هر fold، فقط نمونه‌های short با زمان < مرز train استفاده شوند."""
    N = len(Xl); mt = int(N*B.MIN_TRAIN_FRAC); fold=(N-mt)//B.N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(B.N_FOLDS):
        tr_end = mt + k*fold; te_start = tr_end + B.EMBARGO
        te_end = tr_end + fold if k < B.N_FOLDS-1 else N
        if te_start >= te_end: continue
        # زمان مرزی = اندیس کندل در انتهای train long
        time_cut = idx_l[tr_end-1]
        s_mask = idx_short < time_cut     # فقط short های قبل از مرز زمانی
        X_tr = np.vstack([Xl[:tr_end], Xs[s_mask]])
        Y_tr = np.concatenate([Yl[:tr_end], Y_short[s_mask]])
        m = B._lgbm(seed); m.fit(X_tr, Y_tr)
        proba[idx_l[te_start:te_end]] = m.predict_proba(Xl[te_start:te_end])[:,1]
    return proba

print("\n=== A/B (ensemble 3-seed، purged walk-forward) ===")
pb = np.nanmean(np.vstack([wf_baseline(s) for s in B.SEEDS]), axis=0)
pa = np.nanmean(np.vstack([wf_augmented(s) for s in B.SEEDS]), axis=0)

for label, proba in [('BASELINE (long-only train)', pb),
                     ('AUGMENTED (train long+short)', pa)]:
    print(f"\n--- {label} ---")
    for thr in [0.62, 0.65, 0.68, 0.70]:
        ent = cand & ~np.isnan(proba) & (proba >= thr)
        B.eval_entries(df, atr, ent, label=f'  thr={thr}')

print("\nتمام P31.")
