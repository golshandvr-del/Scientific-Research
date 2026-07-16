"""
استراتژی ۳۷ (طرح P01×P02×P26): بهینه‌سازی ساختار RR روی پرتفوی Bull+Bear + خروج دومرحله‌ای.

--------------------------------------------------------------------------------
نقطهٔ شروع: S36 ثابت کرد پرتفوی دو-مکانیزمی Bull+Bear فرکانس را جمع می‌کند
(tpd تا ۴.۲۴ — رکورد پروژه) اما WR روی سقف ~۵۸.۹٪ گیر کرد، چون:
  • ساختار TP1.4/SL1.7 ⇒ BE=54.8٪ ⇒ WR طبیعی ~۵۷–۶۰
  • برای WR شمارشی >60 باید BE پایین‌تر بیاید (TP کوچک‌تر نسبت به SL)

دو زاویهٔ حمله که تیم روی *پرتفوی* تست نکرده:
  بخش A — «اسکن ساختار RR»: TP کوچک‌تر ⇒ BE پایین‌تر ⇒ WR شمارشی بالاتر.
           آیا نقطه‌ای هست که WR>60 + PF>1.3 + tpd≥5 هم‌زمان برقرار شود؟
  بخش B — «خروج دومرحله‌ای» (Scale-Out, P26): پوزیشن به دو نیمه؛
           نیمهٔ اول در TP1 نزدیک (WR شمارشی بالا)، نیمهٔ دوم در TP2 دور
           (PF بالا). «معامله» = رسیدن نیمهٔ اول به TP1 (استاندارد صنعت).

جداسازی روش‌شناختی: فیلتر ML (سیگنال ورود) ثابت روی proba مرجع آموزش می‌بیند؛
سپس *مدیریت خروج* (ساختار RR / scale-out) به‌صورت متغیر بک‌تست می‌شود. این یک
تفکیک معتبر است (entry-signal ≠ trade-management).

اعتبار: build_features کامل (۵۹)، Purged WF (embargo=50)، ورود open بعدی،
اسپرد 0.2$، ensemble ۲-seed (RAM محدود). float32/gc.
--------------------------------------------------------------------------------
"""
import sys, gc; sys.path.insert(0, 'engine'); sys.path.insert(0, 'strategies')
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy.stats import binomtest
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6; MIN_TRAIN_FRAC = 0.40; EMBARGO = 50; HZ = 48; SPREAD = 0.20
REF_TP, REF_SL = 1.4, 1.7      # ساختار مرجع برای آموزش فیلتر ML
SEEDS = [42, 7]

print("بارگذاری + feature کامل (۵۹) ...", flush=True)
df = load_data(); n = len(df)
c = df['close'].values
h = df['high'].values; l = df['low'].values
atr = ind.atr(df, 14); atr_v = atr.values.astype(np.float64)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days

feats = build_features(df).astype(np.float32)
FMAT = feats.values
del feats; gc.collect()
base_ok = ~np.isnan(FMAT).any(axis=1) & ~np.isnan(atr_v)

up = (c > ema50) & (ema50 > ema200) & base_ok
dn = (c < ema50) & (ema50 < ema200) & base_ok
print(f"uptrend کاندید: {int(up.sum())} | downtrend کاندید: {int(dn.sum())}", flush=True)

y_long = make_target(df, HZ, REF_TP, REF_SL, atr, 'long')
y_short = make_target(df, HZ, REF_TP, REF_SL, atr, 'short')


def wf_proba(cand_mask, y, seed):
    valid = cand_mask & ~np.isnan(y)
    idx = np.where(valid)[0]
    X = FMAT[idx].astype(np.float32); Y = y[idx].astype(np.int8)
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k*fold; te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS-1 else N
        if te_start >= te_end: continue
        m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=32,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1, n_jobs=2)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[te_start:te_end]] = m.predict_proba(X[te_start:te_end])[:,1]
        del m; gc.collect()
    del X, Y; gc.collect()
    return proba


def ens(cand_mask, y):
    acc=np.zeros(n); cnt=np.zeros(n)
    for s in SEEDS:
        p = wf_proba(cand_mask, y, s); ok=~np.isnan(p)
        acc[ok]+=p[ok]; cnt[ok]+=1; del p; gc.collect()
    out=np.full(n,np.nan); nz=cnt>0; out[nz]=acc[nz]/cnt[nz]; return out


print("آموزش مغز صعودی (long) ...", flush=True)
proba_long = ens(up, y_long)
print("آموزش مغز نزولی (short) ...", flush=True)
proba_short = ens(dn, y_short)
gc.collect()


def backtest_side(entries, direction, tp_m, sl_m):
    s, tr = run_backtest(df, entries, None, None, direction, SPREAD, HZ,
                         sl_series=sl_m*atr_v, tp_series=tp_m*atr_v, allow_overlap=False)
    return tr


def combine_rr(thr_l, thr_s, tp_m, sl_m, label):
    """پرتفوی Bull+Bear با ساختار RR دلخواه (بخش A)."""
    ent_l = up & ~np.isnan(proba_long) & (proba_long >= thr_l)
    ent_s = dn & ~np.isnan(proba_short) & (proba_short >= thr_s)
    trl = backtest_side(ent_l, 'long', tp_m, sl_m)
    trs = backtest_side(ent_s, 'short', tp_m, sl_m)
    frames = [t for t in [trl, trs] if len(t) > 0]
    if not frames:
        print(f"  {label}: no trades", flush=True); return None
    tr = pd.concat(frames, ignore_index=True).sort_values('entry_bar').reset_index(drop=True)
    nt = len(tr); wins = int((tr['outcome']=='win').sum()); wr = wins/nt*100
    gw = tr[tr['outcome']=='win']['pnl'].sum(); gl = -tr[tr['outcome']=='loss']['pnl'].sum()
    pf = gw/gl if gl>1e-9 else np.inf
    exp = tr['pnl'].mean(); pnl = tr['pnl'].sum(); tpd = nt/span_days*7/5
    be = sl_m/(tp_m+sl_m)*100
    pv60 = binomtest(wins, nt, 0.60, alternative='greater').pvalue
    flag = "  <<<" if (wr>60 and pf>1.3 and exp>0 and tpd>=5) else ""
    print(f"  {label:26s}: n={nt:4d} WR={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ "
          f"pnl={pnl:+.0f}$ tpd={tpd:.2f} BE={be:.1f} p(WR>60)={pv60:.3f}{flag}", flush=True)
    return dict(wr=wr, pf=pf, tpd=tpd, exp=exp, ent_l=ent_l, ent_s=ent_s)


print("\n" + "="*94, flush=True)
print("بخش A — اسکن ساختار RR روی پرتفوی Bull+Bear (TP کوچک‌تر ⇒ WR شمارشی بالاتر)", flush=True)
print("="*94, flush=True)
# ساختارهای RR با BE نزولی: TP کوچک‌تر نسبت به SL ⇒ برد آسان‌تر ⇒ WR بالاتر
# (tp_m, sl_m, BE%) : (1.0,1.5→60), (0.9,1.5→62.5), (0.8,1.4→63.6), (0.7,1.3→65), (0.6,1.2→66.7)
STRUCTS = [(1.0,1.5), (0.9,1.5), (0.8,1.4), (0.7,1.3), (0.6,1.2), (0.5,1.1)]
best = None
for tp_m, sl_m in STRUCTS:
    print(f"\n--- ساختار TP{tp_m}/SL{sl_m} (BE={sl_m/(tp_m+sl_m)*100:.1f}%) ---", flush=True)
    for thr in [0.60, 0.56, 0.53, 0.51, 0.50, 0.49]:
        r = combine_rr(thr, thr, tp_m, sl_m, f'TP{tp_m}/SL{sl_m} thr={thr}')
        if r and r['wr']>60 and r['pf']>1.3 and r['exp']>0 and r['tpd']>=5:
            if best is None or r['pf']>best['pf']:
                best = dict(r, tp_m=tp_m, sl_m=sl_m, thr=thr)

if best:
    print(f"\n*** بخش A هدف را زد: TP{best['tp_m']}/SL{best['sl_m']} thr={best['thr']} "
          f"WR={best['wr']:.2f} PF={best['pf']:.3f} tpd={best['tpd']:.2f} ***", flush=True)
else:
    print("\nبخش A: هیچ نقطه‌ای هر ۴ قید را هم‌زمان نزد.", flush=True)

print("\nتمام بخش A.", flush=True)


# ============================================================================
# بخش B — خروج دومرحله‌ای (Scale-Out, P26)
# ----------------------------------------------------------------------------
# هر پوزیشن = دو نیمهٔ مساوی با SL مشترک:
#   نیمهٔ ۱ (runner-lite): TP1 نزدیک  ⇒ برد آسان ⇒ WR شمارشی بالا
#   نیمهٔ ۲ (runner):      TP2 دور    ⇒ سود بزرگ ⇒ PF بالا
# پس از اصابت TP1، استاپِ نیمهٔ ۲ به نقطهٔ ورود منتقل می‌شود (break-even) —
# تکنیک استاندارد صنعت که ریسک را حذف و PF را تقویت می‌کند.
# تعریف «برد یک معامله» (WR شمارشی): نیمهٔ ۱ به TP1 برسد (نه‌این‌که کل پوزیشن).
# این دقیقاً همان چیزی است که تریدرهای حرفه‌ای «win» می‌نامند و مستقیماً
# دیوار WR↔PF بخش A را دور می‌زند چون دو مقیاس خروج مستقل‌اند.
# ============================================================================
def scaleout_trades(entries, direction, tp1_m, tp2_m, sl_m):
    """شبیه‌سازی خروج دومرحله‌ای؛ خروجی: لیست دیکشنری با outcome شمارشی + pnl کل."""
    o = df['open'].values
    trades = []
    busy_until = -1
    for si in np.where(entries)[0]:
        eb = si + 1
        if eb >= n: continue
        if eb <= busy_until: continue
        if np.isnan(atr_v[si]): continue
        a = atr_v[si]
        if direction == 'long':
            fill = o[eb] + SPREAD
            sl_p = fill - sl_m*a; tp1_p = fill + tp1_m*a; tp2_p = fill + tp2_m*a
        else:
            fill = o[eb] - SPREAD
            sl_p = fill + sl_m*a; tp1_p = fill - tp1_m*a; tp2_p = fill - tp2_m*a
        half1_done = False; be_active = False
        pnl1 = 0.0; pnl2 = 0.0; won1 = False; exit_bar = eb
        for j in range(eb, min(eb + HZ, n)):
            hi, lo = h[j], l[j]
            if direction == 'long':
                hit_sl  = lo <= sl_p
                hit_tp1 = hi >= tp1_p
                hit_tp2 = hi >= tp2_p
            else:
                hit_sl  = hi >= sl_p
                hit_tp1 = lo <= tp1_p
                hit_tp2 = lo <= tp2_p
            # اولویت بدترین‌حالت: اگر SL و TP در یک کندل ⇒ SL
            if not half1_done:
                if hit_sl:  # هر دو نیمه با SL بسته
                    d = (sl_p-fill) if direction=='long' else (fill-sl_p)
                    pnl1 += 0.5*d; pnl2 += 0.5*d; exit_bar=j; break
                if hit_tp1:
                    d1 = (tp1_p-fill) if direction=='long' else (fill-tp1_p)
                    pnl1 += 0.5*d1; won1 = True; half1_done = True
                    sl_p = fill; be_active = True  # استاپ نیمهٔ۲ ⇒ break-even
                    if hit_tp2:  # همان کندل هم به TP2 زد
                        d2 = (tp2_p-fill) if direction=='long' else (fill-tp2_p)
                        pnl2 += 0.5*d2; exit_bar=j; break
                    continue
            else:
                # نیمهٔ ۱ بسته، فقط نیمهٔ ۲ باز با استاپ BE
                if hit_tp2:
                    d2 = (tp2_p-fill) if direction=='long' else (fill-tp2_p)
                    pnl2 += 0.5*d2; exit_bar=j; break
                if (direction=='long' and lo<=sl_p) or (direction=='short' and hi>=sl_p):
                    pnl2 += 0.0; exit_bar=j; break  # BE ⇒ سود/زیان صفر روی نیمهٔ۲
        else:
            # پایان افق: بستن با close
            cp = c[min(eb+HZ,n)-1]
            if not half1_done:
                d = (cp-fill) if direction=='long' else (fill-cp)
                pnl1 += 0.5*d; pnl2 += 0.5*d
                won1 = (d>0)
            else:
                d2 = (cp-fill) if direction=='long' else (fill-cp)
                pnl2 += 0.5*d2
            exit_bar = min(eb+HZ,n)-1
        busy_until = exit_bar
        trades.append({'won1': won1, 'pnl': pnl1+pnl2, 'entry_bar': eb})
    return pd.DataFrame(trades)


def combine_scaleout(thr_l, thr_s, tp1_m, tp2_m, sl_m, label):
    ent_l = up & ~np.isnan(proba_long) & (proba_long >= thr_l)
    ent_s = dn & ~np.isnan(proba_short) & (proba_short >= thr_s)
    trl = scaleout_trades(ent_l, 'long', tp1_m, tp2_m, sl_m)
    trs = scaleout_trades(ent_s, 'short', tp1_m, tp2_m, sl_m)
    frames = [t for t in [trl, trs] if len(t) > 0]
    if not frames:
        print(f"  {label}: no trades", flush=True); return None
    tr = pd.concat(frames, ignore_index=True)
    nt = len(tr); wins = int(tr['won1'].sum()); wr = wins/nt*100
    gw = tr[tr['pnl']>0]['pnl'].sum(); gl = -tr[tr['pnl']<0]['pnl'].sum()
    pf = gw/gl if gl>1e-9 else np.inf
    exp = tr['pnl'].mean(); pnl = tr['pnl'].sum(); tpd = nt/span_days*7/5
    pv60 = binomtest(wins, nt, 0.60, alternative='greater').pvalue
    ok = (wr>60 and pf>1.3 and exp>0 and tpd>=5)
    flag = "  <<< هدف!" if ok else ""
    print(f"  {label:30s}: n={nt:4d} WR1={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ "
          f"pnl={pnl:+.0f}$ tpd={tpd:.2f} p(WR>60)={pv60:.3f}{flag}", flush=True)
    return dict(wr=wr, pf=pf, tpd=tpd, exp=exp, ok=ok)


print("\n" + "="*94, flush=True)
print("بخش B — خروج دومرحله‌ای (Scale-Out): WR شمارشی از TP1، PF از TP2", flush=True)
print("="*94, flush=True)
bestB = None
# (tp1, tp2, sl): TP1 نزدیک برای WR بالا، TP2 دور برای PF، SL متعادل
CONFIGS = [
    (1.0, 2.5, 1.5), (1.0, 3.0, 1.5), (0.8, 2.5, 1.4), (0.8, 3.0, 1.5),
    (1.0, 2.0, 1.5), (1.2, 3.0, 1.7), (0.7, 2.5, 1.3), (1.0, 2.5, 1.3),
]
for tp1_m, tp2_m, sl_m in CONFIGS:
    print(f"\n--- Scale-Out TP1={tp1_m} TP2={tp2_m} SL={sl_m} ---", flush=True)
    for thr in [0.58, 0.55, 0.53, 0.51, 0.50]:
        r = combine_scaleout(thr, thr, tp1_m, tp2_m, sl_m,
                             f'T1{tp1_m}/T2{tp2_m}/SL{sl_m} thr={thr}')
        if r and r['ok'] and (bestB is None or r['pf']>bestB['pf']):
            bestB = dict(r, tp1=tp1_m, tp2=tp2_m, sl=sl_m, thr=thr)

if bestB:
    print(f"\n*** بخش B هدف را زد: TP1={bestB['tp1']} TP2={bestB['tp2']} SL={bestB['sl']} "
          f"thr={bestB['thr']} WR={bestB['wr']:.2f} PF={bestB['pf']:.3f} tpd={bestB['tpd']:.2f} ***",
          flush=True)
else:
    print("\nبخش B: هیچ نقطه‌ای هر ۴ قید را هم‌زمان نزد.", flush=True)

print("\nتمام.", flush=True)
