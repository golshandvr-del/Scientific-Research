"""
S54b — پرتفویِ واقعیِ چند-دارایی (نکتهٔ اولِ User Note، در ادامهٔ L29)
================================================================================
ایده: به‌جای استفاده از ارزها فقط به‌عنوان «گیتِ تأیید» طلا (S47/S48)، همان
pipelineِ روند-پیروِ ML را روی هر دارایی به‌طور مستقل اجرا می‌کنیم و سیگنال‌ها را
در یک «سبد» ادغام می‌کنیم. فرضیه (که S54a تأیید کرد): جریان‌های ارزها ناهمبستهٔ
زمانی‌اند؛ وقتی طلا بی‌روند است (نیمهٔ اول، L29)، ارزِ دیگری روند دارد. پس سبد باید:
  (۱) فرکانس را بالا ببرد (مجموعِ اکشن‌ها)
  (۲) پایداریِ دو-نیمه را بهبود دهد (رفعِ L27/L29)

روش (سبک و سریع، همان قواعدِ اثبات‌شدهٔ S49):
  - کاندید: EMA50/EMA200 روند-پیرو (long و short)
  - target: TP=1R, SL=1.5R (R=1.5*ATR)  با HZ=48
  - مدل: LightGBM، walk-forward 5-fold، آموزش روی min 45% اولیه
  - خروج: ثابت TP/SL (نه چند-پله؛ برای مقایسهٔ منصفانهٔ edgeِ خام بینِ دارایی‌ها)
  - سنجه‌ها بر حسبِ R (مقیاس‌ناپذیر بینِ دارایی‌ها) + اسپردِ نسبت‌به‌ATR
  - آزمونِ دو-نیمه روی سبدِ ادغام‌شده (معیارِ اصلی)

هیچ look-ahead: مدل فقط از گذشتهٔ همان دارایی آموزش می‌بیند؛ foldها زمانی‌اند.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data
import indicators as ind
from features import build_features, make_target
import warnings; warnings.filterwarnings('ignore')

HZ = 48; TP_M = 1.0; SL_M = 1.5
N_FOLDS = 5; MIN_TRAIN = 0.45
SEEDS = [42, 7]
THRESH = 0.62           # آستانهٔ probaِ ورود (یکسان برای مقایسهٔ منصفانه)
SPREAD_ATR = 0.06       # اسپرد ≈ ۶٪ ATR (محافظه‌کارانه، مشترک بینِ دارایی‌ها)
ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']

LGB_PARAMS = dict(objective='binary', n_estimators=200, learning_rate=0.05,
                  num_leaves=31, max_depth=6, min_child_samples=80,
                  subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0,
                  verbose=-1, n_jobs=2)


def wf_proba(feats, cols, cand, y, seed):
    """walk-forward proba برای یک دارایی/جهت."""
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
        if tr_end >= N:
            break
        m = lgb.LGBMClassifier(random_state=seed, **LGB_PARAMS)
        m.fit(X[:tr_end], Y[:tr_end])
        p = m.predict_proba(X[tr_end:te_end])[:, 1]
        proba[idx[tr_end:te_end]] = p
    return proba


def sim_trades(df, cand, proba, direction, thresh):
    """خروجِ ثابت TP/SL؛ خروجی معاملات با pnl بر حسبِ R و زمانِ ورود."""
    c = df['close'].values; h = df['high'].values; l = df['low'].values
    atr = ind.atr(df, 14).values
    n = len(df)
    entries = np.where(cand & (proba >= thresh))[0]
    trades = []
    busy_until = -1
    for i in entries:
        if i <= busy_until or i + 1 >= n or np.isnan(atr[i]):
            continue
        entry = c[i]
        risk = SL_M * atr[i]
        sp = SPREAD_ATR * atr[i]
        if direction == 'long':
            tp = entry + TP_M * atr[i]; sl = entry - risk
        else:
            tp = entry - TP_M * atr[i]; sl = entry + risk
        outcome = None; exit_bar = min(i + HZ, n - 1)
        for j in range(i + 1, min(i + HZ + 1, n)):
            if direction == 'long':
                if l[j] <= sl: outcome = -risk - sp; exit_bar = j; break
                if h[j] >= tp: outcome = TP_M * atr[i] - sp; exit_bar = j; break
            else:
                if h[j] >= sl: outcome = -risk - sp; exit_bar = j; break
                if l[j] <= tp: outcome = TP_M * atr[i] - sp; exit_bar = j; break
        if outcome is None:
            # خروجِ زمانی
            px = c[exit_bar]
            outcome = ((px - entry) if direction == 'long' else (entry - px)) - sp
        pnl_R = outcome / risk          # نرمال‌سازی به واحدِ R
        trades.append((i, exit_bar, pnl_R, direction))
        busy_until = exit_bar
    return trades


def build_asset(asset):
    df = load_data(f'data/{asset}_M15.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    c = df['close'].values
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50).values
    ema200 = ind.ema(df['close'], 200).values
    cand_long = (c > ema50) & (ema50 > ema200) & ~np.isnan(atr.values)
    cand_short = (c < ema50) & (ema50 < ema200) & ~np.isnan(atr.values)
    feats = build_features(df); cols = list(feats.columns)
    all_tr = []
    for direction, cand in [('long', cand_long), ('short', cand_short)]:
        y = make_target(df, HZ, TP_M, SL_M, atr, direction)
        # میانگینِ probaِ چند-seed
        ps = [wf_proba(feats, cols, cand, y, s) for s in SEEDS]
        proba = np.nanmean(np.vstack(ps), axis=0)
        tr = sim_trades(df, cand, proba, direction, THRESH)
        for (i, ex, pnl, d) in tr:
            all_tr.append({'asset': asset, 'dt': df['dt'].iloc[i],
                           'pnl_R': pnl, 'dir': d})
    return pd.DataFrame(all_tr), df['dt'].iloc[0], df['dt'].iloc[-1]


def report(tr, name):
    if len(tr) == 0:
        print(f"  {name}: بدونِ معامله"); return None
    wins = (tr['pnl_R'] > 0).sum(); n = len(tr)
    wr = wins / n * 100
    gp = tr.loc[tr['pnl_R'] > 0, 'pnl_R'].sum()
    gl = -tr.loc[tr['pnl_R'] < 0, 'pnl_R'].sum()
    pf = gp / gl if gl > 0 else np.inf
    exp = tr['pnl_R'].mean()
    days = tr['dt'].dt.date.nunique()
    per_day = n / days if days else 0
    print(f"  {name}: n={n} WR={wr:.1f}% PF={pf:.3f} exp={exp:+.3f}R "
          f"معامله/روز={per_day:.2f} totalR={tr['pnl_R'].sum():+.1f}")
    return dict(n=n, wr=wr, pf=pf, exp=exp, per_day=per_day)


print("ساخت پرتفوی چند-دارایی (ممکن است چند دقیقه طول بکشد) ...", flush=True)
all_frames = []
ranges = {}
for a in ASSETS:
    print(f"  → پردازشِ {a} ...", flush=True)
    tr, t0, t1 = build_asset(a)
    all_frames.append(tr)
    ranges[a] = (t0, t1)
    report(tr, f"{a} تک")

port = pd.concat(all_frames, ignore_index=True).sort_values('dt').reset_index(drop=True)
# نقطهٔ میانیِ زمانیِ مشترک (بر اساسِ کلِ بازهٔ سبد)
tmid = port['dt'].min() + (port['dt'].max() - port['dt'].min()) / 2

print("\n=== سبدِ ادغام‌شده (همهٔ دارایی‌ها، معیارِ اصلی) ===")
report(port, "کل دوره")
s1 = report(port[port['dt'] < tmid], "نیمهٔ اول")
s2 = report(port[port['dt'] >= tmid], "نیمهٔ دوم")

print("\n=== مقایسه: فقط طلا در برابر سبد (نیمهٔ اول = آزمونِ کلیدیِ L29) ===")
xau = port[port['asset'] == 'XAUUSD']
report(xau[xau['dt'] < tmid], "فقط طلا نیمه۱")
report(port[port['dt'] < tmid], "سبدِ کامل نیمه۱")

if s1 and s2:
    stable = (s1['pf'] > 1.3 and s2['pf'] > 1.3 and
              s1['exp'] > 0 and s2['exp'] > 0 and
              s1['wr'] > 60 and s2['wr'] > 60)
    print(f"\n→ هر دو نیمه PF>1.3 و WR>60 و exp>0؟ {'✅ بله' if stable else '❌ خیر'}")

print("\nتمام.", flush=True)
