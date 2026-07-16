"""
S55 — پرتفویِ چند-دارایی + خروجِ پویا چند-پله‌ای (ترکیبِ L30 با موتورِ برندهٔ S49)
================================================================================
L30 نشان داد: تنوعِ چند-دارایی فرکانس را ۳.۳ برابر می‌کند ولی با خروجِ ثابت،
edge صاف می‌ماند (PF≈۱.۰). اما استراتژیِ برندهٔ طلا (S49/S51) با **خروجِ پویا
چند-پله‌ای** توانست PF را از ~۱.۰ به ~۱.۴ ببرد. فرضیهٔ S55:

  «خروجِ پویا (BE + تریلینگ + scale-out) لبهٔ نازکِ هر دارایی را تقویت می‌کند؛
   ترکیبِ چند داراییِ سالم، هم فرکانس (نکتهٔ User Note) هم پایداریِ دو-نیمه را می‌سازد.»

روش:
  - proba walk-forward برای هر دارایی/جهت (مثلِ S54b) → cache در npz
  - خروج: run_multistep_backtest (موتورِ استانداردِ پروژه) روی هر دارایی
  - اسپردِ نسبت‌به‌ATR (۶٪) به دلار تبدیل می‌شود
  - ادغامِ سبد بر حسبِ R + آزمونِ دو-نیمه (معیارِ اصلی)
  - همچنین «اکشن/روز» شمرده می‌شود (هر معامله = ۱ ورود + بستن‌های جزئی)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data
import indicators as ind
from features import build_features, make_target
from dynamic_backtest import run_multistep_backtest
import warnings; warnings.filterwarnings('ignore')

HZ = 48; TP_M = 1.0; SL_M = 1.5
N_FOLDS = 5; MIN_TRAIN = 0.45
SEEDS = [42, 7]
THRESH = 0.62
SPREAD_ATR = 0.06
ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s55_proba_cache.npz')

LGB = dict(objective='binary', n_estimators=200, learning_rate=0.05,
           num_leaves=31, max_depth=6, min_child_samples=80,
           subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=2)


def wf_proba(feats, cols, cand, y, seed):
    n = len(feats)
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=cols + ['y']); valid = valid[valid['cand']]
    if len(valid) < 500:
        return np.full(n, np.nan)
    X = valid[cols].values; Y = valid['y'].values.astype(int); idx = valid.index.values
    N = len(X); mt = int(N * MIN_TRAIN); fold = max(1, (N - mt) // N_FOLDS)
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if tr_end >= N: break
        m = lgb.LGBMClassifier(random_state=seed, **LGB)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1]
    return proba


def get_asset_probas():
    """proba(long/short) هر دارایی؛ با cache."""
    if os.path.exists(CACHE):
        print("بارگذاری probaها از cache ...", flush=True)
        z = np.load(CACHE, allow_pickle=True)
        return {k: z[k] for k in z.files}
    out = {}
    for a in ASSETS:
        print(f"  آموزشِ {a} ...", flush=True)
        df = load_data(f'data/{a}_M15.csv')
        c = df['close'].values
        atr = ind.atr(df, 14)
        ema50 = ind.ema(df['close'], 50).values
        ema200 = ind.ema(df['close'], 200).values
        cL = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
        cS = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
        feats = build_features(df); cols = list(feats.columns)
        for d, cand in [('long', cL), ('short', cS)]:
            y = make_target(df, HZ, TP_M, SL_M, atr, d)
            ps = [wf_proba(feats, cols, cand, y, s) for s in SEEDS]
            out[f'{a}_{d}'] = np.nanmean(np.vstack(ps), axis=0)
    np.savez_compressed(CACHE, **out)
    return out


def run_asset(a, probas):
    """خروجِ پویا روی سیگنال‌های هر دارایی؛ خروجی: DataFrame معاملات با pnl_R."""
    df = load_data(f'data/{a}_M15.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    cL = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
    cS = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
    atr_mean = np.nanmean(atr.values)
    spread = SPREAD_ATR * atr_mean       # اسپردِ دلاری هم‌مقیاسِ ATR
    frames = []
    for d, cand in [('long', cL), ('short', cS)]:
        p = probas[f'{a}_{d}']
        entries = np.where(cand & (p >= THRESH))[0]
        if len(entries) == 0: continue
        _stats, tr = run_multistep_backtest(df, entries, d, atr,
                                    sl_mult=SL_M, tp_mults=(0.8, 1.5, 2.5),
                                    tp_fracs=(0.34, 0.33, 0.33), trail_mult=1.5,
                                    be_offset=0.15, spread=spread, max_hold=200,
                                    allow_overlap=False)
        if len(tr) == 0: continue
        tr = tr.copy()
        # نرمال‌سازی pnl به R (R = SL_M*ATR_mean بر حسبِ دلار)
        R = SL_M * atr_mean
        tr['pnl_R'] = tr['pnl'] / R
        tr['asset'] = a; tr['dir'] = d
        tr['dt'] = df['dt'].iloc[tr['entry_bar'].values].values
        frames.append(tr[['asset', 'dir', 'dt', 'pnl_R', 'n_actions']]
                      if 'n_actions' in tr.columns else
                      tr[['asset', 'dir', 'dt', 'pnl_R']])
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def report(tr, name):
    if tr is None or len(tr) == 0:
        print(f"  {name}: بدونِ معامله"); return None
    n = len(tr); wins = (tr['pnl_R'] > 0).sum(); wr = wins / n * 100
    gp = tr.loc[tr['pnl_R'] > 0, 'pnl_R'].sum()
    gl = -tr.loc[tr['pnl_R'] < 0, 'pnl_R'].sum()
    pf = gp / gl if gl > 0 else np.inf
    exp = tr['pnl_R'].mean()
    days = tr['dt'].dt.date.nunique()
    per_day = n / days if days else 0
    # اکشن/روز اگر ستون داشت
    act = ''
    if 'n_actions' in tr.columns:
        apd = tr['n_actions'].sum() / days if days else 0
        act = f" اکشن/روز={apd:.1f}"
    print(f"  {name}: n={n} WR={wr:.1f}% PF={pf:.3f} exp={exp:+.3f}R "
          f"معامله/روز={per_day:.2f}{act} totalR={tr['pnl_R'].sum():+.1f}")
    return dict(n=n, wr=wr, pf=pf, exp=exp, per_day=per_day)


print("=== S55: پرتفویِ چند-دارایی + خروجِ پویا ===", flush=True)
probas = get_asset_probas()
frames = []
for a in ASSETS:
    tr = run_asset(a, probas)
    report(tr, f"{a} تک (پویا)")
    if len(tr): frames.append(tr)

port = pd.concat(frames, ignore_index=True).sort_values('dt').reset_index(drop=True)
tmid = port['dt'].min() + (port['dt'].max() - port['dt'].min()) / 2

print("\n=== سبدِ ادغام‌شده (خروجِ پویا) ===")
report(port, "کل دوره")
s1 = report(port[port['dt'] < tmid], "نیمهٔ اول")
s2 = report(port[port['dt'] >= tmid], "نیمهٔ دوم")

print("\n=== زیرمجموعه‌های منتخب ===")
sub = port[port['asset'].isin(['XAUUSD', 'USDCHF'])]
report(sub, "XAU+CHF کل")
report(sub[sub['dt'] < tmid], "XAU+CHF نیمه۱")
report(sub[sub['dt'] >= tmid], "XAU+CHF نیمه۲")

if s1 and s2:
    stable = (s1['pf'] > 1.3 and s2['pf'] > 1.3 and s1['exp'] > 0 and
              s2['exp'] > 0 and s1['wr'] > 60 and s2['wr'] > 60)
    print(f"\n→ سبدِ کامل هر دو نیمه PF>1.3 & WR>60 & exp>0؟ {'✅ بله' if stable else '❌ خیر'}")

print("\nتمام.", flush=True)
