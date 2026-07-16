"""
استراتژی ۳۴ (طرح P39b + P40): «MTF کم‌شمار» و «گیت هم‌راستایی چند-تایم‌فریمی».

--------------------------------------------------------------------------------
درس S33: پرتاب هر ۹۹ feature MTF واقعی به مدل، WR/PF را بهبود نداد (حتی در نقطهٔ
PF کمی بدتر کرد) — با اینکه مدل ۱۸/۲۰ feature برتر را از MTF انتخاب کرد. یعنی
اطلاعات MTF واقعی «جذاب ولی زائد/نویزی» بود و باعث overfit در walk-forward شد.
--------------------------------------------------------------------------------

این استراتژی دو فرضیهٔ ظریف‌تر را آزمون می‌کند:

بخش A — «MTF کم‌شمار» (Parsimony): شاید مشکل کمیت بود نه کیفیت. به‌جای ۹۹ feature،
فقط چند feature MTF با انتخاب مبتنی بر دانش دامنه (context روند H4/D1 + alignment)
اضافه می‌کنیم. تحلیل تکنیکال تاپ-داون دقیقاً همین چند چیز را ادعا می‌کند.
مجموعه‌های آزمون:
   SET1 (روند بزرگ):  h4_dist_ema200, d1_dist_ema200, w1_dist_ema200
   SET2 (+alignment): SET1 + mtf_align_sum, mtf_align_strength, mtf_stack_sum
   SET3 (+قدرت):      SET2 + h4_adx, d1_adx

بخش B — «گیت هم‌راستایی» (P40، حملهٔ مستقیم به قید فرکانس): مدل baseline را ثابت
نگه می‌داریم، thr را *پایین* می‌آوریم تا فرکانس بالا رود (tpd→بالا)، سپس فقط
سیگنال‌هایی را نگه می‌داریم که ≥K تایم‌فریم صعودی هم‌راستا دارند (mtf_n_bull≥K).
فرضیه: گیت MTF واقعی، WR را در thr پایین (فرکانس بالا) بالا نگه می‌دارد ⇒ شاید
هم‌زمان tpd≥5 و WR>60 حاصل شود (قید باقی‌ماندهٔ P01).

اعتبار: Purged Walk-Forward (embargo=50) + open-next + spread 0.2$. float32 برای RAM.
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

N_FOLDS = 6; MIN_TRAIN_FRAC = 0.40; EMBARGO = 50; HZ = 48; SPREAD = 0.20
SEEDS = [42, 7, 123]

print("بارگذاری + feature ...", flush=True)
df = load_data(); n = len(df)
c = df['close'].values
atr = ind.atr(df, 14); atr_v = atr.values.astype(np.float64)
ema50 = ind.ema(df['close'], 50).values; ema200 = ind.ema(df['close'], 200).values

feats = build_features(df).astype(np.float32)
BASE_COLS = list(feats.columns)
mtf_full = add_alignment_features(build_mtf_features(df, tfs=('M30','H1','H4','D1','W1'))).astype(np.float32)

cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr_v)
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
print(f"کاندید: {int(cand.sum())} از {n}", flush=True)

BASE_MAT = feats.values
LABELS = {(1.0,1.5): make_target(df, HZ, 1.0, 1.5, atr, 'long'),
          (1.4,1.7): make_target(df, HZ, 1.4, 1.7, atr, 'long')}


def wf_proba(extra_cols, label_key, seed):
    """WF با baseline + ستون‌های اضافه (extra_cols از mtf_full)."""
    y = LABELS[label_key]
    base_ok = ~np.isnan(BASE_MAT).any(axis=1)
    if extra_cols:
        EX = mtf_full[extra_cols].values
        base_ok = base_ok & ~np.isnan(EX).any(axis=1)
    valid = cand & base_ok & ~np.isnan(y)
    idx = np.where(valid)[0]
    if extra_cols:
        X = np.hstack([BASE_MAT[idx], mtf_full[extra_cols].values[idx]]).astype(np.float32)
    else:
        X = BASE_MAT[idx].astype(np.float32)
    Y = y[idx].astype(np.int8)
    N = len(X); mt = int(N*MIN_TRAIN_FRAC); fold = (N-mt)//N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k*fold; te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS-1 else N
        if te_start >= te_end: continue
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.04, num_leaves=32,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1, n_jobs=2)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:,1]
        del m; gc.collect()
    del X, Y; gc.collect()
    return proba


def ens(extra_cols, label_key):
    acc=np.zeros(n); cnt=np.zeros(n)
    for s in SEEDS:
        p = wf_proba(extra_cols, label_key, s); ok=~np.isnan(p)
        acc[ok]+=p[ok]; cnt[ok]+=1; del p; gc.collect()
    out=np.full(n,np.nan); nz=cnt>0; out[nz]=acc[nz]/cnt[nz]; return out


def evalp(proba, thr, tp, sl, extra_gate=None):
    ent = cand & ~np.isnan(proba) & (proba>=thr)
    if extra_gate is not None:
        ent = ent & extra_gate
    s, tr = run_backtest(df, ent, None, None, 'long', SPREAD, HZ,
                         sl_series=sl*atr_v, tp_series=tp*atr_v, allow_overlap=False)
    nt=s['n_trades']
    if nt<30: return None
    wr=s['win_rate']
    gw=tr[tr['outcome']=='win']['pnl'].sum(); gl=-tr[tr['outcome']=='loss']['pnl'].sum()
    pf=gw/gl if gl>1e-9 else np.inf
    tpd=nt/span_days*7/5; be=sl/(tp+sl)*100
    wins=int(round(wr/100*nt)); pv=binomtest(wins,nt,be/100,alternative='greater').pvalue
    return dict(n=nt,wr=wr,pf=pf,exp=s['expectancy'],pnl=s['total_pnl'],tpd=tpd,be=be,pv=pv)


def show(lbl,r):
    if r is None: print(f"  {lbl}: <30",flush=True); return
    print(f"  {lbl:22s}: n={r['n']:4d} WR={r['wr']:.2f}% PF={r['pf']:.3f} "
          f"exp={r['exp']:+.3f}$ tpd={r['tpd']:.2f} p={r['pv']:.4f}",flush=True)

# ============================================================
# بخش A: MTF کم‌شمار (نقطهٔ PF که مهم‌ترین است)
# ============================================================
SETS = {
    'BASELINE (0 MTF)': [],
    'SET1 trend(3)': ['h4_dist_ema200','d1_dist_ema200','w1_dist_ema200'],
    'SET2 +align(6)': ['h4_dist_ema200','d1_dist_ema200','w1_dist_ema200',
                       'mtf_align_sum','mtf_align_strength','mtf_stack_sum'],
    'SET3 +adx(8)': ['h4_dist_ema200','d1_dist_ema200','w1_dist_ema200',
                     'mtf_align_sum','mtf_align_strength','mtf_stack_sum',
                     'h4_adx','d1_adx'],
}
print("\n"+"="*74,flush=True)
print("بخش A — MTF کم‌شمار در نقطهٔ PF (TP1.4/SL1.7/thr0.65)",flush=True)
print("="*74,flush=True)
for name, cols in SETS.items():
    r = evalp(ens(cols,(1.4,1.7)), 0.65, 1.4, 1.7); show(name, r)

print("\n"+"="*74,flush=True)
print("بخش A — MTF کم‌شمار در نقطهٔ WR (TP1.0/SL1.5/thr0.62)",flush=True)
print("="*74,flush=True)
for name, cols in SETS.items():
    r = evalp(ens(cols,(1.0,1.5)), 0.62, 1.0, 1.5); show(name, r)

# ============================================================
# بخش B: گیت هم‌راستایی MTF برای حل فرکانس (P40)
# مدل baseline ثابت؛ thr پایین برای فرکانس بالا؛ گیت mtf_n_bull>=K
# ============================================================
print("\n"+"="*74,flush=True)
print("بخش B — گیت هم‌راستایی MTF (P40): آیا فرکانس بالا + WR>60 هم‌زمان ممکن است؟",flush=True)
print("="*74,flush=True)
proba_base = ens([], (1.0,1.5))  # baseline در نقطهٔ WR
n_bull = mtf_full['mtf_n_bull'].values  # 0..5
print("مرجع بدون گیت در thr های مختلف:",flush=True)
for thr in [0.50, 0.54, 0.58, 0.62]:
    r = evalp(proba_base, thr, 1.0, 1.5); show(f'no-gate thr={thr}', r)
print("\nبا گیت mtf_n_bull>=K (thr پایین 0.54 برای فرکانس بالا):",flush=True)
for K in [3, 4, 5]:
    gate = (n_bull >= K)
    r = evalp(proba_base, 0.54, 1.0, 1.5, extra_gate=gate); show(f'gate K>={K} thr=0.54', r)
print("\nبا گیت mtf_n_bull>=K (thr 0.58):",flush=True)
for K in [3, 4, 5]:
    gate = (n_bull >= K)
    r = evalp(proba_base, 0.58, 1.0, 1.5, extra_gate=gate); show(f'gate K>={K} thr=0.58', r)

print("\nتمام.",flush=True)
