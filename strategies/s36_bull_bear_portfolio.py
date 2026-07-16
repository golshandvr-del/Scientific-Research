"""
استراتژی ۳۶ (طرح P02 راستین): «پرتفوی دو-مکانیزمی Bull+Bear» — جریان‌های زمانی ناهمبسته.

--------------------------------------------------------------------------------
درس S35: پرتفوی چند-تایم‌فریمیِ *هم‌مکانیزم* شکست خورد، چون جریان‌ها در زمان همبسته
بودند (همه trend-pullback روی همان روند) و در dedup حذف شدند (L12).

راه‌حل P02 راستین: تنوع باید در **مکانیزم/رژیم** باشد، نه تایم‌فریم. دو جریانِ
اثبات‌شدهٔ پروژه که در زمان **کاملاً ناهمبسته**‌اند (چون رژیم‌هایشان هرگز هم‌زمان
نیستند):
   جریان LONG  = مغز صعودی (S25): کاندید close>EMA50>EMA200، جهت long
   جریان SHORT = مغز نزولی (S31): کاندید close<EMA50<EMA200، جهت short
uptrend و downtrend هرگز هم‌زمان رخ نمی‌دهند ⇒ فرکانس‌ها بدون dedup **جمع** می‌شوند.
--------------------------------------------------------------------------------

فرضیهٔ مرکزی:
  هر جریان در نقطهٔ کاری PF (TP1.4/SL1.7) به‌تنهایی WR~۵۷–۶۰ و PF>1.3 می‌دهد اما
  فقط ~۰.۶–۱ معامله/روز. چون در زمان ناهمبسته‌اند، پرتفویِ آن‌ها:
    - WR وزنی ≈ میانگین وزنی WRها (اگر هر دو نزدیک ۵۸–۶۰ ⇒ پرتفوی ~۵۸–۶۰)
    - PF وزنی ≈ ترکیب (هر دو >1.3 ⇒ پرتفوی >1.3)
    - tpd = مجموع (بدون dedup چون رژیم‌ها ناسازگارند) ⇒ شاید به هدف نزدیک شود
  سپس thr هر دو جریان را *پایین* می‌آوریم تا فرکانس بالا رود و منحنی
  WR/PF/tpd(thr) را استخراج می‌کنیم — آیا نقطه‌ای با tpd≥5 + WR>60 + PF>1.3 هست؟

اعتبار: build_features کامل (۵۹ feature، همان S25/S31)، Purged Walk-Forward
(embargo=50)، ورود open بعدی، اسپرد 0.2$، ensemble ۲-seed (RAM محدود). float32/gc.
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
TP_M, SL_M = 1.4, 1.7
SEEDS = [42, 7]

print("بارگذاری + feature کامل (۵۹) ...", flush=True)
df = load_data(); n = len(df)
c = df['close'].values
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

y_long = make_target(df, HZ, TP_M, SL_M, atr, 'long')
y_short = make_target(df, HZ, TP_M, SL_M, atr, 'short')


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

BE = SL_M/(TP_M+SL_M)*100  # ≈54.8


def backtest_side(entries, direction):
    s, tr = run_backtest(df, entries, None, None, direction, SPREAD, HZ,
                         sl_series=SL_M*atr_v, tp_series=TP_M*atr_v, allow_overlap=False)
    return s, tr


def combine_and_eval(thr_long, thr_short, label):
    """دو جریان را جدا بک‌تست و معاملات را ادغام می‌کند (رژیم‌ها ناسازگارند ⇒ بدون تداخل)."""
    ent_l = up & ~np.isnan(proba_long) & (proba_long >= thr_long)
    ent_s = dn & ~np.isnan(proba_short) & (proba_short >= thr_short)
    sl, trl = backtest_side(ent_l, 'long')
    ss, trs = backtest_side(ent_s, 'short')
    frames = [t for t in [trl, trs] if len(t) > 0]
    if not frames:
        print(f"  {label}: no trades", flush=True); return None
    tr = pd.concat(frames, ignore_index=True).sort_values('entry_bar').reset_index(drop=True)
    nt = len(tr); wins = (tr['outcome']=='win').sum()
    wr = wins/nt*100
    gw = tr[tr['outcome']=='win']['pnl'].sum(); gl = -tr[tr['outcome']=='loss']['pnl'].sum()
    pf = gw/gl if gl>1e-9 else np.inf
    exp = tr['pnl'].mean(); pnl = tr['pnl'].sum()
    tpd = nt/span_days*7/5
    pv = binomtest(int(wins), nt, BE/100, alternative='greater').pvalue
    pv60 = binomtest(int(wins), nt, 0.60, alternative='greater').pvalue
    nl = len(trl); ns = len(trs)
    print(f"  {label:24s}: n={nt:4d}(L{nl}/S{ns}) WR={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ "
          f"pnl={pnl:+.0f}$ tpd={tpd:.2f} p(WR>{BE:.0f})={pv:.4f} p(WR>60)={pv60:.3f}", flush=True)
    return dict(n=nt, wr=wr, pf=pf, exp=exp, pnl=pnl, tpd=tpd, pv=pv, pv60=pv60, tr=tr,
                ent_l=ent_l, ent_s=ent_s)


print("\n" + "="*90, flush=True)
print(f"پرتفوی Bull+Bear در نقطهٔ PF (TP{TP_M}/SL{SL_M}, BE≈{BE:.1f}%) — جاروب thr", flush=True)
print("="*90, flush=True)

# جاروب متقارن thr برای هر دو جریان (از سختگیر تا شل برای دیدن منحنی فرکانس)
for thr in [0.66, 0.62, 0.58, 0.55, 0.52, 0.50]:
    combine_and_eval(thr, thr, f'thr={thr}')

# جاروب نامتقارن: long سختگیرتر (WR بالاتر)، short شل‌تر (فرکانس)
print("\nترکیب‌های نامتقارن (long-thr / short-thr):", flush=True)
for tl, ts in [(0.62,0.58),(0.60,0.55),(0.58,0.55),(0.56,0.54),(0.55,0.52)]:
    combine_and_eval(tl, ts, f'L{tl}/S{ts}')

print("\nتمام.", flush=True)
