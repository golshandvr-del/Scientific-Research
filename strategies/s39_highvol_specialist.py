"""
استراتژی ۳۹ (توسعهٔ L17): «متخصص رژیم پرنوسان» (High-Vol Specialist).

--------------------------------------------------------------------------------
S38/L17 نشان داد edgeِ trend-pullback طلا در رژیم High-vol ~۷× قوی‌تر است، اما
مدل آن‌جا یک مدلِ *عمومی* بود که صرفاً در High-vol فیلتر می‌شد. فرضیهٔ جدید:
اگر مدل را **فقط روی نمونه‌های High-vol آموزش دهیم** (تخصص‌گرایی رژیمی)، الگوهای
مختصِ آن رژیم را بهتر می‌آموزد ⇒ شاید WR در آن زیرمجموعه از ۶۰ عبور کند.

تفاوت روش‌شناختیِ کلیدی با S38:
   S38: train روی همه رژیم‌ها  →  predict  →  فیلترِ رژیم روی خروجی.
   S39: train **فقط** روی High(+Mid)-vol  →  predict فقط همان‌جا (مدل متخصص).

هم‌چنین آستانهٔ proba را per-side کالیبره می‌کنیم و RR را حول نقطهٔ PF می‌چرخانیم.

اعتبار: build_features کامل (۵۹)، Purged WF (embargo=50) اما فقط روی اندیسِ
High-vol، ورود open بعدی، اسپرد 0.2$، ensemble ۲-seed، float32/gc. رژیم فقط
از گذشته (بدون نشت).
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
TP_M, SL_M = 1.4, 1.7
SEEDS = [42, 7]

print("بارگذاری + feature کامل (۵۹) ...", flush=True)
df = load_data(); n = len(df)
c = df['close'].values
atr = ind.atr(df, 14); atr_v = atr.values.astype(np.float64)
atr_long = ind.atr(df, 100).values.astype(np.float64)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days

vol_ratio = atr_v / (atr_long + 1e-9)
vr_ser = pd.Series(vol_ratio)
q50 = vr_ser.rolling(2000, min_periods=500).quantile(0.50).values  # آستانهٔ High = بالای میانه
q66 = vr_ser.rolling(2000, min_periods=500).quantile(0.66).values
valid_r = ~np.isnan(q50) & ~np.isnan(vol_ratio)
# دو تعریف رژیم پُر-edge برای مقایسه: High(>q66) و Mid+High(>q50)
high_only = valid_r & (vol_ratio > q66)
midhigh   = valid_r & (vol_ratio > q50)

feats = build_features(df).astype(np.float32)
FMAT = feats.values
del feats; gc.collect()
base_ok = ~np.isnan(FMAT).any(axis=1) & ~np.isnan(atr_v)

up = (c > ema50) & (ema50 > ema200) & base_ok
dn = (c < ema50) & (ema50 < ema200) & base_ok

y_long = make_target(df, HZ, TP_M, SL_M, atr, 'long')
y_short = make_target(df, HZ, TP_M, SL_M, atr, 'short')


def wf_proba(cand_mask, y, seed):
    """آموزش/پیش‌بینی فقط روی زیرمجموعهٔ cand_mask (که شامل فیلتر رژیم است)."""
    valid = cand_mask & ~np.isnan(y)
    idx = np.where(valid)[0]
    if len(idx) < 500: return np.full(n, np.nan)
    X = FMAT[idx].astype(np.float32); Y = y[idx].astype(np.int8)
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k*fold; te_start = tr_end + EMBARGO
        te_end = tr_end + fold if k < N_FOLDS-1 else N
        if te_start >= te_end: continue
        m = lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=32,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=60,
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


def run_specialist(regime_mask, tag):
    up_r = up & regime_mask
    dn_r = dn & regime_mask
    print(f"\n### متخصص {tag}: uptrend∩R={int(up_r.sum())} downtrend∩R={int(dn_r.sum())}", flush=True)
    pl = ens(up_r, y_long)
    ps = ens(dn_r, y_short)
    def trades(thr):
        el = up_r & ~np.isnan(pl) & (pl>=thr)
        es = dn_r & ~np.isnan(ps) & (ps>=thr)
        _, tl = run_backtest(df, el, None, None, 'long', SPREAD, HZ,
                             sl_series=SL_M*atr_v, tp_series=TP_M*atr_v, allow_overlap=False)
        _, ts = run_backtest(df, es, None, None, 'short', SPREAD, HZ,
                             sl_series=SL_M*atr_v, tp_series=TP_M*atr_v, allow_overlap=False)
        fr=[t for t in [tl,ts] if len(t)>0]
        return pd.concat(fr, ignore_index=True) if fr else None
    for thr in [0.60,0.58,0.56,0.54,0.52,0.50]:
        tr = trades(thr)
        if tr is None or len(tr)==0:
            print(f"  thr={thr}: no trades", flush=True); continue
        nt=len(tr); w=int((tr['outcome']=='win').sum()); wr=w/nt*100
        gw=tr[tr['outcome']=='win']['pnl'].sum(); gl=-tr[tr['outcome']=='loss']['pnl'].sum()
        pf=gw/gl if gl>1e-9 else np.inf
        exp=tr['pnl'].mean(); pnl=tr['pnl'].sum(); tpd=nt/span_days*7/5
        pv60=binomtest(w,nt,0.60,alternative='greater').pvalue
        ok=(wr>60 and pf>1.3 and exp>0 and tpd>=5)
        flag="  <<< هدف!" if ok else ("  * WR&PF ok" if (wr>60 and pf>1.3) else "")
        print(f"  thr={thr}: n={nt:4d} WR={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ "
              f"pnl={pnl:+.0f}$ tpd={tpd:.2f} p(WR>60)={pv60:.3f}{flag}", flush=True)
    del pl, ps; gc.collect()


print("="*94, flush=True)
print("متخصص رژیم — مدل فقط روی نمونه‌های پُر-نوسان آموزش می‌بیند (تخصص‌گرایی)", flush=True)
print("="*94, flush=True)
run_specialist(midhigh, 'Mid+High (>میانه)')
run_specialist(high_only, 'High (>q66)')

print("\nتمام.", flush=True)
