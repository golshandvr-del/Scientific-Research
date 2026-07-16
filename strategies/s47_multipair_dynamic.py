"""
استراتژی ۴۷ — تأییدِ چند-جفت‌ارزی + خروجِ پویا، با هدفِ «سود خالصِ روزانه»
=========================================================================
پاسخِ مستقیم به User Note جدید:
  (۱) بازتعریفِ «برد» از WR شمارشی به **سود خالصِ روزانه (daily net PnL)**.
  (۲) مدیریتِ پویای معامله: scale-out نیمی در TP1 + انتقالِ SL به بریک‌ایون +
      تریلینگ‌استاپ ATR برای نیمهٔ باقی‌مانده (طرح P26).
  (۳) تحلیلِ موازیِ چند جفت‌ارز (DXY/EURUSD/AUDUSD/USDCHF) به‌عنوان **گیتِ تأییدِ
      هم‌جهت** برای سیگنالِ طلا (نه پیش‌بین — چون تحلیل نشان داد lead ضعیف است).

مبنا: همان مدلِ برندهٔ S25 (uptrend long + weekly-reversion context, ensemble
۳-seed, Purged Walk-Forward, ورود open بعدی، اسپرد ۰.۲$). فقط دو محورِ جدید
اضافه می‌شود و یک آزمونِ ۲×۲ منصفانه اجرا می‌گردد:

        | خروج ثابت (S25)      | خروج پویا (P26)
  ------+----------------------+--------------------
  بی‌گیت | A0 (خطِ پایهٔ S25)   | A1
  +گیت   | B0                   | B1

معیارِ داوری: علاوه بر WR/PF/exp شمارشی، **سنجه‌های روزانه**: نرخ روزهای سودده،
میانگین سود خالصِ روزانه، Sharpe روزانه، PF روزانه، و معامله/روز تقویمی.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
from features import build_features, make_target
from dynamic_backtest import run_dynamic_backtest, daily_pnl_stats
from multipair import build_multipair_features
import warnings; warnings.filterwarnings('ignore')

N_FOLDS = 6; MIN_TRAIN_FRAC = 0.40
HZ = 48; TP_M = 1.0; SL_M = 1.5; THRESH = 0.68; SPREAD = 0.20
SEEDS = [42, 7, 123]

print("بارگذاری داده و ساخت feature ...")
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

cand = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
print(f"کاندید پایه (uptrend long): {int(cand.sum())}")

# --- گیتِ چند-جفت‌ارزی ---
print("ساخت featureهای تأییدِ چند-جفت‌ارزی (merge_asof، بدون look-ahead) ...")
mp = build_multipair_features(df)
mp_cov = mp['mp_basket_ret_8'].notna().mean() * 100 if 'mp_basket_ret_8' in mp else 0
print(f"پوشش گیتِ چند-جفت‌ارزی: {mp_cov:.1f}%")
align_long = mp['mp_align_long'].fillna(0).values.astype(bool) if 'mp_align_long' in mp else np.zeros(n, bool)


def walk_forward(seed=42):
    y = make_target(df, HZ, TP_M, SL_M, atr, 'long')
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


print("\nآموزش ensemble ۳-seed (S25) ...")
probas = [walk_forward(s) for s in SEEDS]
ens = np.nanmean(np.vstack(probas), axis=0)

base_entries = cand & ~np.isnan(ens) & (ens >= THRESH)
gated_entries = base_entries & align_long
print(f"سیگنال‌های خام مدل (thr={THRESH}): {int(base_entries.sum())}")
print(f"سیگنال‌های پس از گیتِ چند-جفت‌ارزی: {int(gated_entries.sum())} "
      f"({gated_entries.sum()/max(base_entries.sum(),1)*100:.1f}% حفظ شد)")

span_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days


def eval_fixed(entries, label):
    s, tr = run_backtest(df, entries, None, None, 'long', SPREAD, HZ,
                         sl_series=SL_M * atr.values, tp_series=TP_M * atr.values,
                         allow_overlap=False)
    if s['n_trades'] == 0:
        print(f"  {label}: no trades"); return
    tr = tr.copy(); tr['dt'] = df['dt'].values[tr['entry_bar'].values]
    d = daily_pnl_stats(tr)
    tpd = s['n_trades'] / span_days * 7 / 5
    wins = tr[tr['pnl'] > 0]['pnl'].sum(); loss = -tr[tr['pnl'] <= 0]['pnl'].sum()
    pf = wins / loss if loss > 1e-9 else float('inf')
    print(f"  {label}: n={s['n_trades']} WR={s['win_rate']:.2f}% exp={s['expectancy']:+.3f}$ "
          f"PF={pf:.3f} pnl={s['total_pnl']:+.0f}$ | tpd={tpd:.2f}")
    print(f"         روزانه: win_days={d['daily_win_rate']:.1f}% avg={d['avg_daily_pnl']:+.2f}$ "
          f"sharpe={d['daily_sharpe']:.3f} dPF={d['daily_profit_factor']:.2f} "
          f"tpd_cal={d['trades_per_calendar_day']:.2f}")
    return s, d


def eval_dynamic(entries, label, scale_frac=0.5, trail_mult=1.5):
    s, tr = run_dynamic_backtest(df, entries, 'long', atr,
        sl_mult=SL_M, tp1_mult=TP_M, scale_frac=scale_frac, trail_mult=trail_mult,
        be_offset=0.15, spread=SPREAD, max_hold=HZ * 4, allow_overlap=False)
    if s['n_trades'] == 0:
        print(f"  {label}: no trades"); return
    d = daily_pnl_stats(tr)
    tpd = s['n_trades'] / span_days * 7 / 5
    print(f"  {label}: n={s['n_trades']} WR={s['win_rate']:.2f}% exp={s['expectancy']:+.3f}$ "
          f"PF={s['profit_factor']:.3f} pnl={s['total_pnl']:+.0f}$ avgR={s['avg_r']:+.3f} | tpd={tpd:.2f}")
    print(f"         روزانه: win_days={d['daily_win_rate']:.1f}% avg={d['avg_daily_pnl']:+.2f}$ "
          f"sharpe={d['daily_sharpe']:.3f} dPF={d['daily_profit_factor']:.2f} "
          f"tpd_cal={d['trades_per_calendar_day']:.2f}")
    return s, d


print("\n================ آزمونِ ۲×۲ ================")
print("\n--- خروجِ ثابت (S25 استاندارد) ---")
eval_fixed(base_entries,  "A0 بی‌گیت ثابت ")
eval_fixed(gated_entries, "B0 +گیت   ثابت ")

print("\n--- خروجِ پویا (scale-out 50% + BE + ATR trail) ---")
eval_dynamic(base_entries,  "A1 بی‌گیت پویا ")
eval_dynamic(gated_entries, "B1 +گیت   پویا ")

print("\n--- جاروبِ پارامترهای خروجِ پویا (روی سیگنالِ گیت‌دار B) ---")
for sf in [0.3, 0.5, 0.7]:
    for tm in [1.0, 1.5, 2.5]:
        s, tr = run_dynamic_backtest(df, gated_entries, 'long', atr,
            sl_mult=SL_M, tp1_mult=TP_M, scale_frac=sf, trail_mult=tm,
            be_offset=0.15, spread=SPREAD, max_hold=HZ * 4, allow_overlap=False)
        if s['n_trades'] == 0: continue
        d = daily_pnl_stats(tr)
        print(f"  scale={sf} trail={tm}: WR={s['win_rate']:.1f}% PF={s['profit_factor']:.3f} "
              f"exp={s['expectancy']:+.3f}$ dPF={d['daily_profit_factor']:.2f} "
              f"avg_daily={d['avg_daily_pnl']:+.2f}$ win_days={d['daily_win_rate']:.1f}%")

print("\nتمام.")
