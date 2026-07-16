"""
استراتژی ۳۸ (طرح گروه-F: افزایش edge خام): «گیت متا رژیم-نوسان» (Meta Volatility-Regime Gate).

--------------------------------------------------------------------------------
انگیزه از L15 (کشف S37): روی OHLCV، WR و PF دو نمایِ یک edge خام‌اند؛ بازآراییِ
خروج/آستانه نمی‌تواند هر دو را هم‌زمان بالا ببرد. تنها راه، **بالا بردن خودِ
edge خام** است — یعنی معامله فقط جایی که مدل واقعاً پیش‌بینی‌پذیری بالا دارد.

فرضیهٔ علمی (پشتوانه: market-regime volatility filtering literature):
  کیفیت پیش‌بینیِ مدل ML به **رژیم نوسان** وابسته است. در رژیم نوسانِ «مناسب»،
  الگوهای trend-pullback پایدارترند ⇒ edge بالاتر ⇒ WR و PF *هم‌زمان* بالا.
  در رژیم پرنوسان/نویزی، سیگنال‌ها کاذب‌ترند ⇒ باید سکوت کرد.

روش: متغیر رژیم = vol_ratio تحقق‌یافته = ATR(14) / ATR(100) (نرمال، بدون واحد).
  سطل‌بندی به Low / Mid / High (بر اساس چندک‌های *گذشته-محورِ* غلتان، بدون نشت).
  سپس ماتریسِ (رژیم × آستانهٔ proba) را برای پرتفوی Bull+Bear اسکن می‌کنیم و
  دنبال سلولی می‌گردیم که WR>60 + PF>1.3 + exp>0 + tpd≥5 هم‌زمان بزند.

اعتبار: build_features کامل (۵۹)، Purged WF (embargo=50)، ورود open بعدی،
اسپرد 0.2$، ensemble ۲-seed، float32/gc. رژیم فقط از گذشته محاسبه می‌شود.
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
c = df['close'].values; h = df['high'].values; l = df['low'].values
atr = ind.atr(df, 14); atr_v = atr.values.astype(np.float64)
atr_long = ind.atr(df, 100).values.astype(np.float64)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days

# ---- متغیر رژیم نوسان: نسبت ATR کوتاه/بلند (نرمال، بدون نشت آینده) ----
vol_ratio = atr_v / (atr_long + 1e-9)
# چندک‌های *گذشته-محور* غلتان (rolling، بدون look-ahead): از پنجرهٔ گذشته
vr_ser = pd.Series(vol_ratio)
q33 = vr_ser.rolling(2000, min_periods=500).quantile(0.33).values
q66 = vr_ser.rolling(2000, min_periods=500).quantile(0.66).values
regime = np.full(n, -1, dtype=np.int8)  # -1=unknown, 0=Low,1=Mid,2=High
valid_r = ~np.isnan(q33) & ~np.isnan(q66) & ~np.isnan(vol_ratio)
regime[valid_r & (vol_ratio <= q33)] = 0
regime[valid_r & (vol_ratio > q33) & (vol_ratio <= q66)] = 1
regime[valid_r & (vol_ratio > q66)] = 2

feats = build_features(df).astype(np.float32)
FMAT = feats.values
del feats; gc.collect()
base_ok = ~np.isnan(FMAT).any(axis=1) & ~np.isnan(atr_v)

up = (c > ema50) & (ema50 > ema200) & base_ok
dn = (c < ema50) & (ema50 < ema200) & base_ok
print(f"uptrend={int(up.sum())} downtrend={int(dn.sum())} | "
      f"regime counts L/M/H = {int((regime==0).sum())}/{int((regime==1).sum())}/{int((regime==2).sum())}",
      flush=True)

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
BE = SL_M/(TP_M+SL_M)*100


def portfolio_trades(thr_l, thr_s, regime_allow):
    """regime_allow: مجموعهٔ رژیم‌های مجاز (مثلاً {0,1}). فیلتر رژیم روی سیگنال ورود."""
    rmask = np.isin(regime, list(regime_allow))
    ent_l = up & rmask & ~np.isnan(proba_long) & (proba_long >= thr_l)
    ent_s = dn & rmask & ~np.isnan(proba_short) & (proba_short >= thr_s)
    _, trl = run_backtest(df, ent_l, None, None, 'long', SPREAD, HZ,
                          sl_series=SL_M*atr_v, tp_series=TP_M*atr_v, allow_overlap=False)
    _, trs = run_backtest(df, ent_s, None, None, 'short', SPREAD, HZ,
                          sl_series=SL_M*atr_v, tp_series=TP_M*atr_v, allow_overlap=False)
    frames = [t for t in [trl, trs] if len(t) > 0]
    if not frames: return None
    return pd.concat(frames, ignore_index=True)


def report(tr, label):
    if tr is None or len(tr)==0:
        print(f"  {label}: no trades", flush=True); return None
    nt=len(tr); wins=int((tr['outcome']=='win').sum()); wr=wins/nt*100
    gw=tr[tr['outcome']=='win']['pnl'].sum(); gl=-tr[tr['outcome']=='loss']['pnl'].sum()
    pf=gw/gl if gl>1e-9 else np.inf
    exp=tr['pnl'].mean(); pnl=tr['pnl'].sum(); tpd=nt/span_days*7/5
    pv60=binomtest(wins,nt,0.60,alternative='greater').pvalue
    ok=(wr>60 and pf>1.3 and exp>0 and tpd>=5)
    flag="  <<< هدف!" if ok else ("  * WR&PF ok" if (wr>60 and pf>1.3) else "")
    print(f"  {label:34s}: n={nt:4d} WR={wr:.2f}% PF={pf:.3f} exp={exp:+.3f}$ "
          f"pnl={pnl:+.0f}$ tpd={tpd:.2f} p(WR>60)={pv60:.3f}{flag}", flush=True)
    return dict(wr=wr,pf=pf,exp=exp,tpd=tpd,ok=ok)


print("\n" + "="*94, flush=True)
print("گام ۱ — تشخیص رژیمِ پُر-edge: بک‌تست پرتفوی به‌تفکیک هر رژیم (thr=0.58)", flush=True)
print("="*94, flush=True)
for rg, nm in [(0,'Low-vol'),(1,'Mid-vol'),(2,'High-vol')]:
    report(portfolio_trades(0.58, 0.58, {rg}), f'regime={nm}')

print("\n" + "="*94, flush=True)
print("گام ۲ — ترکیب رژیم‌های مجاز × جاروب thr (دنبال WR>60 & PF>1.3 & tpd>=5)", flush=True)
print("="*94, flush=True)
best=None
for allow, nm in [({0},'L'),({1},'M'),({0,1},'L+M'),({1,2},'M+H'),({0,1,2},'ALL')]:
    print(f"\n--- رژیم‌های مجاز: {nm} ---", flush=True)
    for thr in [0.60,0.57,0.55,0.53,0.51,0.50]:
        r=report(portfolio_trades(thr,thr,allow), f'{nm} thr={thr}')
        if r and r['ok'] and (best is None or r['pf']>best['pf']):
            best=dict(r, allow=nm, thr=thr)

if best:
    print(f"\n*** S38 هدف را زد: رژیم={best['allow']} thr={best['thr']} "
          f"WR={best['wr']:.2f} PF={best['pf']:.3f} tpd={best['tpd']:.2f} ***", flush=True)
else:
    print("\nS38: هیچ ترکیب رژیم/thr هر ۴ قید را هم‌زمان نزد.", flush=True)

print("\nتمام.", flush=True)
