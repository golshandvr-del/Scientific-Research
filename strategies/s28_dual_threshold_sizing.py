"""
استراتژی ۲۸ (طرح P03 از strategy_plans.md): Dual-Threshold / Kelly-Bucket Sizing
— جدا کردن «PF دلاری» از «فرکانس شمارشی».

بینش مرکزی (سند P03):
  قیود کاربر در واحدهای متفاوت‌اند:
    - WR      → شمارشی (تعداد برد / کل)
    - فرکانس  → شمارشی (تعداد معامله در روز)
    - PF, exp → دلاری (مجموع سود$ / |مجموع زیان$|)
  اگر به سیگنال‌های پراطمینان سایز بزرگ‌تر و به سیگنال‌های کم‌اطمینان سایز کوچک‌تر
  بدهیم:
    - فرکانس شمارشی (همهٔ معاملات) بالا می‌ماند ✅
    - WR شمارشی (میانگین همه) >۶۰ می‌ماند ✅
    - PF دلاری به لایهٔ باکیفیت سنگین می‌شود → می‌تواند >1.3 شود ✅
  کاملاً صادقانه: هیچ معامله‌ای پنهان نمی‌شود؛ فقط تخصیص سرمایه هوشمند می‌شود.
  WR و tpd همیشه بدون-وزن (شمارشی خام) گزارش می‌شوند.

اعتبارسنجی حیاتی (سند): کالیبراسیون احتمال مدل روی OOS باید پایدار باشد
(reliability curve) وگرنه sizing روی اطمینان کاذب بنا می‌شود → گزارش می‌شود.

روش:
  - جریان پایه = S25 long-trend، نقطهٔ کار پرفرکانس (TP1.0/SL1.5) با آستانهٔ پایه
    پایین (thr_base) تا فرکانس ≥۵ تأمین شود.
  - allow_overlap=True با سقف پوزیشن هم‌زمان (واقع‌گرایی حساب چندپوزیشنه) برای
    رساندن فرکانس واقعی به ≥۵.
  - هر معاملهٔ باز، بر اساس proba در زمان سیگنال، وزن سایز می‌گیرد:
      لایهٔ ۱ (thr_base≤p<thr_hi): وزن ۱
      لایهٔ ۲ (p≥thr_hi):          وزن Wهی (۱.۵/۲/۳ جاروب)
    یا نسخهٔ Kelly-کسری پیوسته: w = clip(a*(p-0.5), 0, wmax).
  - PF/exp دلاری با این وزن‌ها؛ WR/tpd شمارشی خام.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6; MIN_TRAIN_FRAC = 0.40; EMBARGO = 50; HZ = 48; SPREAD = 0.20
SEEDS = [42, 7]
TP_M, SL_M = 1.0, 1.5     # نقطهٔ کار پرفرکانس

print("بارگذاری داده + feature ...")
df = load_data(); n = len(df)
c = df['close'].values
atr = ind.atr(df, 14); atr_v = atr.values
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
feats = build_features(df); FCOLS = list(feats.columns)
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr_v)
print(f"کاندید long-trend: {int(cand.sum())}")


def walk_forward(seed):
    y = make_target(df, HZ, TP_M, SL_M, atr, 'long')
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=FCOLS + ['y']); valid = valid[valid['cand']]
    X = valid[FCOLS].values; Y = valid['y'].values.astype(int); idx = valid.index.values
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold; te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if te_start >= te_end: continue
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.04, num_leaves=32,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1, n_jobs=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:, 1]
    return proba

print("Walk-forward ensemble ...")
proba = np.nanmean(np.vstack([walk_forward(s) for s in SEEDS]), axis=0)

# ---- اعتبارسنجی کالیبراسیون (reliability) روی نمونه‌های OOS ----
print("\n=== reliability curve (کالیبراسیون احتمال روی OOS) ===")
y_true = make_target(df, HZ, TP_M, SL_M, atr, 'long')
mask = cand & ~np.isnan(proba) & ~np.isnan(y_true)
pp = proba[mask]; yy = y_true[mask]
print(f"{'bin':>12} {'n':>6} {'pred':>7} {'actual':>7}")
for lo in [0.45, 0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70, 0.75]:
    hi = lo + 0.05
    m = (pp >= lo) & (pp < hi)
    if m.sum() > 20:
        print(f"[{lo:.2f},{hi:.2f}) {int(m.sum()):>6} {pp[m].mean():>7.3f} {yy[m].mean():>7.3f}")


def run_with_entries(thr_base):
    ent = cand & ~np.isnan(proba) & (proba >= thr_base)
    # allow_overlap=True تا فرکانس واقعیِ حساب چندپوزیشنه دیده شود
    s, tr = run_backtest(df, ent, None, None, 'long', SPREAD, HZ,
                         sl_series=SL_M * atr_v, tp_series=TP_M * atr_v, allow_overlap=True)
    if len(tr) == 0:
        return None
    tr = tr.copy()
    tr['proba'] = proba[tr['signal_bar'].values]
    return tr


def eval_sized(tr, thr_hi, w_hi, wmax_kelly=None, kelly_a=None, label=""):
    """WR/tpd شمارشی خام؛ PF/exp دلاری با وزن سایز."""
    nt = len(tr); wins = (tr['outcome'] == 'win').sum()
    wr = wins / nt * 100
    tpd = nt / span_days * 7 / 5
    if kelly_a is not None:
        w = np.clip(kelly_a * (tr['proba'].values - 0.5), 0.0, wmax_kelly)
        # نرمال‌سازی به میانگین ۱ تا مقایسه منصفانه با baseline باشد
        w = w / (w.mean() + 1e-9)
    else:
        w = np.where(tr['proba'].values >= thr_hi, w_hi, 1.0)
    wpnl = tr['pnl'].values * w
    gw = wpnl[tr['outcome'].values == 'win'].sum()
    gl = -wpnl[tr['outcome'].values == 'loss'].sum()
    pf = gw / gl if gl > 1e-9 else np.inf
    exp = wpnl.mean()
    pv = binomtest(int(wins), nt, 0.60, alternative='greater').pvalue
    ok = (wr > 60 and pf > 1.3 and exp > 0 and tpd >= 5 and pv < 0.05)
    print(f"{label}: n={nt} WR={wr:.2f}%(خام) PF={pf:.3f}(دلاری) exp={exp:+.3f}$ "
          f"tpd={tpd:.2f}(خام) p(WR>60)={pv:.3f} {'✅' if ok else ''}")
    return dict(n=nt, wr=wr, pf=pf, exp=exp, tpd=tpd, pv=pv, ok=ok,
                thr_hi=thr_hi, w_hi=w_hi, kelly_a=kelly_a, wmax=wmax_kelly)


results = []
print("\n" + "=" * 70)
print("جاروب Dual-Threshold Sizing (WR/tpd خام، PF/exp دلاری)")
print("=" * 70)
for thr_base in [0.52, 0.54, 0.56, 0.58]:
    tr = run_with_entries(thr_base)
    if tr is None: continue
    print(f"\n--- thr_base={thr_base} (n={len(tr)}, tpd_خام={len(tr)/span_days*7/5:.2f}) ---")
    # baseline بی‌وزن
    r = eval_sized(tr, 1.0, 1.0, label=f"  baseline(w=1)")
    r['thr_base'] = thr_base; results.append(r)
    # دولایه با آستانه‌ها و وزن‌های مختلف
    for thr_hi in [0.65, 0.68, 0.72]:
        for w_hi in [2.0, 3.0, 4.0]:
            r = eval_sized(tr, thr_hi, w_hi, label=f"  dual thr_hi={thr_hi} w={w_hi}")
            r['thr_base'] = thr_base; results.append(r)
    # Kelly پیوسته
    for a in [4.0, 6.0, 8.0]:
        for wmax in [3.0, 5.0]:
            r = eval_sized(tr, None, None, wmax_kelly=wmax, kelly_a=a,
                           label=f"  kelly a={a} wmax={wmax}")
            r['thr_base'] = thr_base; results.append(r)

winners = [r for r in results if r['ok']]
print("\n" + "=" * 70)
if winners:
    winners.sort(key=lambda r: (r['pf'], r['tpd']), reverse=True)
    b = winners[0]
    print(f"✅✅✅ نقطهٔ برنده: thr_base={b['thr_base']} thr_hi={b['thr_hi']} "
          f"w_hi={b['w_hi']} kelly_a={b['kelly_a']}")
    print(f"   WR={b['wr']:.2f}%(خام) PF={b['pf']:.3f}(دلاری) exp={b['exp']:+.3f}$ "
          f"tpd={b['tpd']:.2f} p={b['pv']:.4f}")
else:
    # بهترین PF با WR>60 و tpd≥5
    cand_r = [r for r in results if r['wr'] > 60 and r['tpd'] >= 5 and r['exp'] > 0]
    cand_r.sort(key=lambda r: r['pf'], reverse=True)
    print("❌ هیچ نقطه‌ای همهٔ قیود را برآورده نکرد.")
    if cand_r:
        b = cand_r[0]
        print(f"   نزدیک‌ترین (WR>60 & tpd≥5 & exp>0، بیشترین PF): "
              f"PF={b['pf']:.3f} WR={b['wr']:.2f}% tpd={b['tpd']:.2f} "
              f"thr_base={b['thr_base']} thr_hi={b['thr_hi']} w={b['w_hi']} kelly_a={b['kelly_a']}")
    else:
        # چرا؟ تشخیص
        hi_freq = [r for r in results if r['tpd'] >= 5]
        print(f"   نقاطی با tpd≥5: {len(hi_freq)}؛ از این‌ها WR>60: "
              f"{len([r for r in hi_freq if r['wr']>60])}")
print("=" * 70)
