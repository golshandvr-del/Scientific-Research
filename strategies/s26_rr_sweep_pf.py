"""
استراتژی ۲۶ (طرح P01 از strategy_plans.md): «جابه‌جایی نقطهٔ کار» — جاروب سطح RR
روی مدل S25 موجود با تابع هدف = Profit Factor (نه Win Rate).

ایدهٔ مرکزی (strategy_plans.md بخش ۱):
  PF = [WR × r] / [1 − WR]  با  r = avgWin/avgLoss
  شرط PF>1.3 ⇒ WR > 1.3 / (1.3 + r).
  در TP1.0/SL1.5 (r≈0.70 پس از اسپرد) برای PF=1.3 به WR≥۶۵٪ نیاز است (سقف پروژه).
  اما با انتقال نقطهٔ کار به RR متقارن‌تر (TP≈1.3–1.5×ATR)، آستانهٔ PF=1.3 به
  WR≈۵۸–۶۰٪ سقوط می‌کند — دقیقاً ناحیه‌ای که مدل ما در آن زندگی می‌کند.

روش (تکرار مو‌به‌مو دستور پخت Recipe-S25):
  1) مدل S25 (long-only در uptrend، ۵۹ feature شامل early_atr/weekly_rev) ثابت است.
  2) نکتهٔ ظریف P01: proba مدل به «ساختار برچسب» (TP/SL هدف در آموزش) وابسته است.
     پس برای هر ساختار برچسب یک‌بار Purged Walk-Forward (embargo=50) اجرا می‌شود.
  3) سپس روی شبکهٔ (TP_exec, SL_exec, thr) بک‌تست open-next + spread=0.2$ انجام و
     برای هر نقطه WR/PF/exp/tpd/p-value گزارش می‌شود.
  4) خروجی اصلی: منحنی تجربی WR(TP) و PF(TP) که تمام طرح‌های بعدی به آن ارجاع می‌دهند.

معیار موفقیت: WR>60 (p<0.05) + PF>1.3 + exp>0 + tpd≥5 هم‌زمان روی OOS.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

# ---------- پارامترهای ثابت مدل (همان S25) ----------
N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40
EMBARGO = 50          # purge/embargo بین train و test هر fold (L6)
HZ = 48              # افق برچسب و max_hold اجرا
SPREAD = 0.20
SEEDS = [42, 7]       # ensemble 2-seed (سرعت؛ 3-seed در تأیید نهایی)

print("بارگذاری داده ...")
df = load_data()
n = len(df)
c = df['close'].values
atr = ind.atr(df, 14)
atr_v = atr.values
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values

print("ساخت feature ها (شامل early_atr / weekly_rev) ...")
feats = build_features(df)
FCOLS = list(feats.columns)   # همان ۵۹ feature کامل مدل برنده

# کاندید پایه S25: روند صعودی، long-only
cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr_v)
print(f"کاندید پایه (uptrend long): {int(cand.sum())}  از  {n}")

span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days


def walk_forward_proba(label_tp, label_sl, seed):
    """
    Purged Walk-Forward با برچسبی که با (label_tp, label_sl) ساخته می‌شود.
    embargo=EMBARGO ردیف بین انتهای train و شروع test پاک می‌شود تا نشت افق برچسب
    (HZ کندلی) و همبستگی سریالی حذف شود.
    خروجی: آرایهٔ proba هم‌طول df (NaN جز روی نمونه‌های test).
    """
    y = make_target(df, HZ, label_tp, label_sl, atr, 'long')
    data = feats.copy()
    data['y'] = y
    data['cand'] = cand
    valid = data.dropna(subset=FCOLS + ['y'])
    valid = valid[valid['cand']]
    X = valid[FCOLS].values
    Y = valid['y'].values.astype(int)
    idx = valid.index.values
    N = len(X)
    mt = int(N * MIN_TRAIN_FRAC)
    fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_start = tr_end + EMBARGO           # embargo بعد از train
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


def ens_proba(label_tp, label_sl):
    probas = [walk_forward_proba(label_tp, label_sl, s) for s in SEEDS]
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
    avg_win = s['avg_win']; avg_loss = s['avg_loss']
    gross_win = tr[tr['outcome'] == 'win']['pnl'].sum()
    gross_loss = -tr[tr['outcome'] == 'loss']['pnl'].sum()
    pf = gross_win / gross_loss if gross_loss > 1e-9 else np.inf
    tpd = nt / span_days * 7 / 5
    be = sl_exec / (tp_exec + sl_exec) * 100
    wins = int(round(wr / 100 * nt))
    pv = binomtest(wins, nt, be / 100, alternative='greater').pvalue
    return dict(n=nt, wr=wr, pf=pf, exp=s['expectancy'], pnl=s['total_pnl'],
                tpd=tpd, be=be, pv=pv, avg_win=avg_win, avg_loss=avg_loss)


# =================================================================
# مرحله ۱: منحنی WR(TP) و PF(TP) — برچسب هم‌ساختار با اجرا (بازآموزی برچسب)
# =================================================================
print("\n" + "=" * 70)
print("مرحله ۱: منحنی WR(TP)/PF(TP) — برچسب بازتولیدشده برای هر RR (thr=0.62 ثابت)")
print("=" * 70)
SL_FIX = 1.5
TP_GRID = [1.0, 1.2, 1.3, 1.4, 1.5, 1.8]
THR_FIX = 0.62
proba_cache = {}
curve = []
for tp in TP_GRID:
    key = (tp, SL_FIX)
    proba_cache[key] = ens_proba(tp, SL_FIX)     # برچسب = همان RR اجرا
    proba = proba_cache[key]
    r = eval_point(proba, THR_FIX, tp, SL_FIX)
    if r is None:
        print(f"TP={tp:.1f} SL={SL_FIX}: <30 trade"); continue
    print(f"TP={tp:.1f} SL={SL_FIX} | n={r['n']:4d} WR={r['wr']:.2f}% "
          f"PF={r['pf']:.3f} exp={r['exp']:+.3f}$ tpd={r['tpd']:.2f} "
          f"BE={r['be']:.1f}% p={r['pv']:.3f}")
    curve.append((tp, r))

# =================================================================
# مرحله ۲: جاروب کامل (TP, SL, thr) با هدف PF — برچسب هم‌ساختار
# =================================================================
print("\n" + "=" * 70)
print("مرحله ۲: جاروب (TP,SL,thr) با هدف PF>1.3 و WR>60 و tpd≥5")
print("=" * 70)
# SL=1.5 ثابت (فرضیهٔ اصلی P01: افزایش TP). چند SL جایگزین هم برای کامل‌بودن.
TP_S = [1.2, 1.3, 1.4, 1.5]
SL_S = [1.5, 1.7]
THR_S = [0.55, 0.58, 0.60, 0.62, 0.65, 0.68]
results = []
for tp in TP_S:
    for sl in SL_S:
        key = (tp, sl)
        if key not in proba_cache:
            proba_cache[key] = ens_proba(tp, sl)
        proba = proba_cache[key]
        for thr in THR_S:
            r = eval_point(proba, thr, tp, sl)
            if r is None:
                continue
            r.update(tp=tp, sl=sl, thr=thr)
            results.append(r)

# مرتب‌سازی: ابتدا نقاطی که همهٔ قیود را برآورده می‌کنند
def meets(r):
    return (r['wr'] > 60 and r['pf'] > 1.3 and r['exp'] > 0
            and r['tpd'] >= 5 and r['pv'] < 0.05)

results.sort(key=lambda r: (meets(r), r['pf'], r['wr']), reverse=True)
print("\nTop 15 نقطه بر اساس PF (که WR>60 و exp>0 دارند):")
print(f"{'TP':>4} {'SL':>4} {'thr':>5} {'n':>5} {'WR%':>6} {'PF':>6} "
      f"{'exp$':>7} {'tpd':>5} {'BE%':>5} {'p':>6} {'OK':>3}")
shown = 0
for r in results:
    if r['wr'] < 55:
        continue
    print(f"{r['tp']:>4.1f} {r['sl']:>4.1f} {r['thr']:>5.2f} {r['n']:>5d} "
          f"{r['wr']:>6.2f} {r['pf']:>6.3f} {r['exp']:>+7.3f} {r['tpd']:>5.2f} "
          f"{r['be']:>5.1f} {r['pv']:>6.3f} {'YES' if meets(r) else '-':>3}")
    shown += 1
    if shown >= 15:
        break

winners = [r for r in results if meets(r)]
print("\n" + "=" * 70)
if winners:
    b = winners[0]
    print(f"✅✅ نقطهٔ برنده یافت شد: TP={b['tp']} SL={b['sl']} thr={b['thr']}")
    print(f"   WR={b['wr']:.2f}% PF={b['pf']:.3f} exp={b['exp']:+.3f}$ "
          f"tpd={b['tpd']:.2f} p={b['pv']:.3f}")
else:
    print("❌ هیچ نقطه‌ای هم‌زمان WR>60 + PF>1.3 + exp>0 + tpd≥5 + p<0.05 نداشت.")
    # بهترین PF با WR>60
    best_wr60 = [r for r in results if r['wr'] > 60 and r['exp'] > 0]
    best_wr60.sort(key=lambda r: r['pf'], reverse=True)
    if best_wr60:
        b = best_wr60[0]
        print(f"   نزدیک‌ترین (WR>60, exp>0, بیشترین PF): TP={b['tp']} SL={b['sl']} "
              f"thr={b['thr']} WR={b['wr']:.2f}% PF={b['pf']:.3f} tpd={b['tpd']:.2f}")
print("=" * 70)
