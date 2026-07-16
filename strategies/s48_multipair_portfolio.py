"""
استراتژی ۴۸ — پرتفویِ موازیِ چند-جریانی با خروجِ پویا (حمله به قیدِ فرکانس)
=========================================================================
ادامهٔ مستقیمِ S47. در S47 ثابت شد که «گیتِ چند-جفت‌ارزی + خروجِ پویا» روی جریانِ
long طلا به PF=1.55 و WR=62٪ می‌رسد، اما فرکانس ~۰.۷۶ معامله/روز است (خیلی کمتر
از قیدِ ۵/روز). این استراتژی طبقِ ایدهٔ User Note («تحلیلِ موازیِ چند جفت‌ارز:
وقتی در یکی LONG، در دیگری SHORT») و طبقِ درسِ L24/S45 (جمعِ جریان‌های ناهمبستهٔ
زمانی)، چند جریانِ سالمِ ناهمبسته را موازی اجرا و ادغام می‌کند:

  L   = long طلا  (uptrend  + گیتِ دلاریِ صعودی + خروجِ پویا)  ← همان B1 اثبات‌شدهٔ S47
  S   = short طلا (downtrend + گیتِ دلاریِ نزولی + خروجِ پویا)
  Lf  = long طلا با آستانهٔ پایین‌تر (رژیمِ یکسان، فرکانسِ بیشتر)

پرسشِ علمی: آیا ادغامِ این جریان‌ها فرکانس را به ≥۵/روز می‌رساند، در حالی که
سنجه‌های سود خالصِ روزانه (dPF>1.3, WR>60٪) سالم می‌مانند؟

معیارِ داوری = همان سنجه‌های روزانهٔ User Note (سود خالصِ روزانه محور).
هر جریان: ensemble ۳-seed، Purged Walk-Forward، ورودِ open بعدی، اسپرد ۰.۲$.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data
import indicators as ind
from features import build_features, make_target
from dynamic_backtest import run_dynamic_backtest, daily_pnl_stats
from multipair import build_multipair_features
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6; MIN_TRAIN_FRAC = 0.40
HZ = 48; TP_M = 1.0; SL_M = 1.5; SPREAD = 0.20
SEEDS = [42, 7, 123]
THRESH_L = 0.68      # آستانهٔ جریانِ long (مثل S47)
THRESH_Lf = 0.60     # آستانهٔ پایین‌ترِ long برای فرکانسِ بیشتر
THRESH_S = 0.66      # آستانهٔ جریانِ short

print("بارگذاری داده و ساخت feature ...", flush=True)
df = load_data()
n = len(df)
c = df['close'].values
atr = ind.atr(df, 14)
ema50 = ind.ema(df['close'], 50).values
ema200 = ind.ema(df['close'], 200).values

# --- feature زمانی S25 (weekly reversion) ---
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
print(f"کاندید long (uptrend): {int(cand_long.sum())}  |  کاندید short (downtrend): {int(cand_short.sum())}", flush=True)

# --- گیتِ چند-جفت‌ارزی ---
print("ساخت featureهای تأییدِ چند-جفت‌ارزی ...", flush=True)
mp = build_multipair_features(df)
align_long = mp['mp_align_long'].fillna(0).values.astype(bool) if 'mp_align_long' in mp else np.zeros(n, bool)
align_short = mp['mp_align_short'].fillna(0).values.astype(bool) if 'mp_align_short' in mp else np.zeros(n, bool)

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


def ens_proba(cand, direction):
    ps = [walk_forward(cand, direction, s) for s in SEEDS]
    return np.nanmean(np.vstack(ps), axis=0)


print("\nآموزش ensemble ۳-seed برای جریانِ LONG ...", flush=True)
ens_long = ens_proba(cand_long, 'long')
print("آموزش ensemble ۳-seed برای جریانِ SHORT ...", flush=True)
ens_short = ens_proba(cand_short, 'short')

# --- تعریفِ سه جریان (با گیتِ دلاری) ---
entries_L  = cand_long  & ~np.isnan(ens_long)  & (ens_long  >= THRESH_L)  & align_long
entries_Lf = cand_long  & ~np.isnan(ens_long)  & (ens_long  >= THRESH_Lf) & align_long
entries_S  = cand_short & ~np.isnan(ens_short) & (ens_short >= THRESH_S)  & align_short

print(f"\nسیگنال‌ها: L={int(entries_L.sum())}  Lf={int(entries_Lf.sum())}  S={int(entries_S.sum())}", flush=True)


def run_stream(entries, direction, scale_frac=0.5, trail_mult=1.5):
    s, tr = run_dynamic_backtest(df, entries, direction, atr,
        sl_mult=SL_M, tp1_mult=TP_M, scale_frac=scale_frac, trail_mult=trail_mult,
        be_offset=0.15, spread=SPREAD, max_hold=HZ * 4, allow_overlap=False)
    return s, tr


def merge_dedup(tr_list):
    """ادغامِ چند جریان؛ حذفِ معاملاتِ هم‌پوشان بر اساس زمانِ ورود (اولویت با ترتیبِ لیست)."""
    frames = [t for t in tr_list if t is not None and len(t) > 0]
    if not frames: return None
    allt = pd.concat(frames, ignore_index=True).sort_values('entry_bar').reset_index(drop=True)
    # حذفِ ورودهای دقیقاً هم‌کندل (یک معامله در هر کندل)
    allt = allt.drop_duplicates(subset='entry_bar', keep='first').reset_index(drop=True)
    return allt


def report(tr, label):
    if tr is None or len(tr) == 0:
        print(f"  {label}: no trades"); return
    n_tr = len(tr)
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else float('inf')
    wr = (tr['pnl'] > 0).mean() * 100
    exp = tr['pnl'].mean()
    d = daily_pnl_stats(tr)
    tpd = n_tr / span_days * 7 / 5
    print(f"  {label}: n={n_tr} WR={wr:.2f}% exp={exp:+.3f}$ PF={pf:.3f} "
          f"pnl={tr['pnl'].sum():+.0f}$ | tpd={tpd:.2f}")
    print(f"         روزانه: win_days={d['daily_win_rate']:.1f}% avg={d['avg_daily_pnl']:+.2f}$ "
          f"sharpe={d['daily_sharpe']:.3f} dPF={d['daily_profit_factor']:.2f} "
          f"tpd_cal={d['trades_per_calendar_day']:.2f}")
    return d


print("\n================ جریان‌های منفرد (خروجِ پویا) ================", flush=True)
sL, trL   = run_stream(entries_L,  'long')
sLf, trLf = run_stream(entries_Lf, 'long')
sS, trS   = run_stream(entries_S,  'short')
report(trL,  "L  (long thr0.68) ")
report(trLf, "Lf (long thr0.60) ")
report(trS,  "S  (short thr0.66)")

print("\n================ پرتفویِ ادغام‌شده ================", flush=True)
report(merge_dedup([trL, trS]),        "L+S       (long+short)   ")
report(merge_dedup([trLf, trS]),       "Lf+S      (long_freq+short)")
report(merge_dedup([trLf]),            "Lf        (فقط long_freq)  ")

print("\nتمام.", flush=True)
