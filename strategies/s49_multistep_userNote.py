"""
استراتژی ۴۹ — پیاده‌سازیِ کاملِ «مدلِ مدیریتِ معاملهٔ User Note» + بازتعریفِ فرکانس
================================================================================
این استراتژی مستقیماً سناریوی دقیقی را که User Note توصیف کرد پیاده می‌کند:

  «سایت به کاربر می‌گوید کجا وارد شو، TP/SL چقدر باشد. با افزایشِ سود، SL به
   بریک‌ایون و سپس تریلینگ می‌رود. با نزدیک‌شدنِ برگشتِ روند، به کاربر می‌گوید
   n% از معامله را ببند (scale-out چندمرحله‌ای). در انتها می‌گوید کلِ معامله را
   ببند. و در روز ۴–۵ بار این اتفاق می‌افتد.»

نوآوریِ کلیدی نسبت به S47/S48: **بازتعریفِ «۵ معامله در روز»**.
در S47/S48 فرکانس بر اساسِ «تعدادِ ورودهای مستقل» شمرده می‌شد و به دیوارِ L21
می‌خورد. اما در مدلِ User Note، هر ورود به چند **رویدادِ اجرایی** تبدیل می‌شود که
کاربر در سایت اجرا می‌کند: ورود + چند بستنِ جزئی + خروجِ نهایی. پس معیارِ درستِ
«۵ اکشن/روز» را باید روی این رویدادها سنجید — دقیقاً همان چیزی که کاربر تجربه می‌کند.

مبنا: پرتفوی L+S اثبات‌شدهٔ S48 (long uptrend + short downtrend، هر دو با گیتِ
چند-جفت‌ارزی). خروج: موتورِ چند-پله‌ای (۳ سطحِ TP + BE + تریلینگ).

سنجه‌ها:
  - WR شمارشی، PF، expectancy (سازگاری با معیارِ سنتی)
  - سنجه‌های روزانه (User Note): سود خالصِ روزانه، dPF، Sharpe روزانه
  - **اکشن/روز** (بازتعریفِ فرکانس): actions_per_calendar_day و per_active_day
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data
import indicators as ind
from features import build_features, make_target
from dynamic_backtest import run_multistep_backtest, daily_pnl_stats
from multipair import build_multipair_features
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6; MIN_TRAIN_FRAC = 0.40
HZ = 48; TP_M = 1.0; SL_M = 1.5; SPREAD = 0.20
SEEDS = [42, 7, 123]
THRESH_L = 0.68; THRESH_S = 0.66
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s49_proba_cache.npz')

print("بارگذاری داده و ساخت feature ...", flush=True)
df = load_data()
n = len(df)
c = df['close'].values
atr = ind.atr(df, 14)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values

df['dow'] = df['dt'].dt.dayofweek; df['date'] = df['dt'].dt.date
df['dt_d'] = pd.to_datetime(df['date'])
df['iso_year'] = df['dt_d'].dt.isocalendar().year.values
df['iso_week'] = df['dt_d'].dt.isocalendar().week.values
daily = df.groupby('date').agg(dow=('dow', 'first'), d_open=('open', 'first'),
                               d_close=('close', 'last'), iso_year=('iso_year', 'first'),
                               iso_week=('iso_week', 'first')).reset_index()
em = {}
for (yr, wk), g in daily.groupby(['iso_year', 'iso_week']):
    g = g.sort_values('date'); e = g[g['dow'].isin([0, 1, 2])]
    if len(e) == 0: continue
    em[(yr, wk)] = e['d_close'].iloc[-1] - e['d_open'].iloc[0]
df['early'] = df.apply(lambda r: em.get((r['iso_year'], r['iso_week']), np.nan), axis=1)
atr_daily = atr.rolling(96).mean().values
early_atr = df['early'].values / (atr_daily + 1e-9)
day_w = df['dow'].map({0: 0.2, 1: 0.3, 2: 0.5, 3: 1.0, 4: 0.9, 5: 0, 6: 0}).values
weekly_rev = -np.sign(df['early'].values) * np.clip(np.abs(early_atr), 0, 3) * day_w

feats = build_features(df)
feats['weekly_rev'] = weekly_rev
feats['early_atr'] = early_atr
cols = list(feats.columns)

cand_long = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
cand_short = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)

print("ساخت featureهای گیتِ چند-جفت‌ارزی ...", flush=True)
mp = build_multipair_features(df)
align_long = mp['mp_align_long'].fillna(0).values.astype(bool)
align_short = mp['mp_align_short'].fillna(0).values.astype(bool)
span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days


def walk_forward(cand, direction, seed=42):
    y = make_target(df, HZ, TP_M, SL_M, atr, direction)
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=cols + ['y']); valid = valid[valid['cand']]
    X = valid[cols].values; Y = valid['y'].values.astype(int); idx = valid.index.values
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold; te_end = tr_end + fold if k < N_FOLDS - 1 else N
        m = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.025, num_leaves=32,
            max_depth=6, subsample=0.8, colsample_bytree=0.75, min_child_samples=80,
            reg_lambda=2.0, random_state=seed, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1]
    return proba


def ens(cand, direction):
    return np.nanmean(np.vstack([walk_forward(cand, direction, s) for s in SEEDS]), axis=0)


if os.path.exists(CACHE):
    print("بارگذاریِ probaها از cache ...", flush=True)
    z = np.load(CACHE)
    ens_long = z['ens_long']; ens_short = z['ens_short']
else:
    print("آموزش ensemble ۳-seed برای LONG ...", flush=True)
    ens_long = ens(cand_long, 'long')
    print("آموزش ensemble ۳-seed برای SHORT ...", flush=True)
    ens_short = ens(cand_short, 'short')
    np.savez(CACHE, ens_long=ens_long, ens_short=ens_short)
    print("cache ذخیره شد.", flush=True)

entries_L = cand_long & ~np.isnan(ens_long) & (ens_long >= THRESH_L) & align_long
entries_S = cand_short & ~np.isnan(ens_short) & (ens_short >= THRESH_S) & align_short
print(f"سیگنال‌ها: L={int(entries_L.sum())}  S={int(entries_S.sum())}", flush=True)


def run_ms(entries, direction, tp_mults, tp_fracs, trail=1.5):
    return run_multistep_backtest(df, entries, direction, atr, sl_mult=SL_M,
        tp_mults=tp_mults, tp_fracs=tp_fracs, trail_mult=trail, be_offset=0.15,
        spread=SPREAD, max_hold=HZ * 4, allow_overlap=False)


def merge_dedup(frames):
    fs = [t for t in frames if t is not None and len(t) > 0]
    if not fs: return None
    allt = pd.concat(fs, ignore_index=True).sort_values('entry_bar')
    return allt.drop_duplicates(subset='entry_bar', keep='first').reset_index(drop=True)


def report(tr, label):
    if tr is None or len(tr) == 0:
        print(f"  {label}: no trades"); return None
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else float('inf')
    wr = (tr['pnl'] > 0).mean() * 100; exp = tr['pnl'].mean()
    d = daily_pnl_stats(tr)
    apd_cal = d.get('actions_per_calendar_day', 0)
    apd_act = d.get('actions_per_active_day', 0)
    print(f"  {label}: n_entries={len(tr)} WR={wr:.2f}% exp={exp:+.3f}$ PF={pf:.3f} "
          f"pnl={tr['pnl'].sum():+.0f}$")
    print(f"         روزانه: win_days={d['daily_win_rate']:.1f}% avg={d['avg_daily_pnl']:+.2f}$ "
          f"dPF={d['daily_profit_factor']:.2f} sharpe={d['daily_sharpe']:.3f}")
    print(f"         فرکانس: ورود/روز={d['trades_per_calendar_day']:.2f}  "
          f"**اکشن/روزِ تقویمی={apd_cal:.2f}**  اکشن/روزِ فعال={apd_act:.2f}")
    return d


# پیکربندی‌های خروجِ چند-پله‌ای (سطوح TP و کسرها)
CONFIGS = [
    ("۳سطح متعادل   ", (0.8, 1.5, 2.5), (0.34, 0.33, 0.33)),
    ("۳سطح جلوبار   ", (0.6, 1.2, 2.2), (0.5, 0.25, 0.25)),
    ("۴سطح ریز      ", (0.6, 1.1, 1.8, 2.8), (0.3, 0.25, 0.25, 0.2)),
]

print("\n================ پرتفوی L+S با خروجِ چند-پله‌ای ================", flush=True)
for name, tpm, tpf in CONFIGS:
    trL = run_ms(entries_L, 'long', tpm, tpf)[1]
    trS = run_ms(entries_S, 'short', tpm, tpf)[1]
    report(merge_dedup([trL, trS]), f"L+S [{name}]")

print("\nتمام.", flush=True)
