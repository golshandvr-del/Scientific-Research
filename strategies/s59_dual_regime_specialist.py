"""
S59 — پرتفویِ دو-متخصصِ رژیم-مکملِ ناهمبسته در زمان (حمله به ریشهٔ L29/L33)
================================================================================
ریشهٔ همهٔ شکست‌ها (L29→L33): نیمهٔ اول (۲۰۲۱–۲۰۲۲) کم‌روند بود (ER≈۰.۰۰۴)؛ هر
سیستمِ روند-پیرو در آن دوره PF<1.3 می‌دهد. راه‌حلِ S57/S58 «حذفِ» آن دوره بود که
فرکانس را کشت (L32/L33). راه‌حلِ نو در S59:

  به‌جای «حذفِ» رژیمِ رنج، یک **متخصصِ mean-reversion با فیلترِ ML** بساز که فقط در
  رژیمِ رنج فعال شود و نیمهٔ اول را **از درون** سودآور کند. سپس آن را با متخصصِ
  روند (S55) ترکیب کن. چون دو رژیم در زمان **ناهمبسته**‌اند (رنج ≠ روند)، معاملات
  هم‌پوشانی ندارند ⇒ فرکانس‌ها جمع می‌شوند بدونِ رقیق‌شدنِ WR (برخلافِ L30).

چرا این بار MR کار می‌کند در حالی که S53 (MR خام) شکست خورد؟
  S53 نشان داد MR **خام** روی طلا edge ندارد (P(fav)≈۵۳٪, PF<1). اما S31 ثابت کرد
  short خام هم ضررده بود ولی short+ML به PF=۱.۴۹ رسید. **درسِ کلیدی: ML یک سیگنالِ
  خامِ لب‌مرزی را به edgeِ سودآور تبدیل می‌کند.** اینجا همان دستور را روی MR اعمال
  می‌کنیم: کاندیدِ MR در رنج → برچسب TP-قبل-از-SL → فیلترِ LightGBM.

معماری:
  جریان A (Trend): probaِ S55 (cache) روی کاندیدِ روند (EMA چیده‌شده) — همان همیشه.
  جریان B (Range-MR-ML): مدلِ تازه؛ کاندید = رنج (ER پایین) + BB-touch + RSI اکسترمم؛
                          برچسب = MR-win؛ فیلترِ ML؛ خروجِ چند-پله‌ای.
  ادغام: اتحادِ زمانیِ دو جریان (بدونِ dedup چون رژیم‌ها ناهمبسته‌اند) + آزمونِ دو-نیمه.
"""
import sys, os, gc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import lightgbm as lgb
from backtest import load_data
import indicators as ind
from features import build_features
from dynamic_backtest import run_multistep_backtest
import warnings; warnings.filterwarnings('ignore')

ASSETS = ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']
CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s55_proba_cache.npz')
SPREAD_ATR = 0.06
ER_N = 96
# رژیمِ روند برای جریان A (بالاتر از این ER = روندی) و رنج برای B (پایین‌تر = رنج)
TREND_THRESH = 0.62          # آستانهٔ probaِ trend (مثلِ S55)
RANGE_ER_MAX = 0.10          # رنج = ER پایین (کم‌روند)
MR_HZ = 24                   # افقِ کوتاه‌تر برای MR (برگشتِ سریع)
MR_TP = 1.0; MR_SL = 1.2     # MR: TP نزدیک، SL کمی دورتر
MR_THRESH = 0.58             # آستانهٔ فیلترِ ML روی MR
N_FOLDS = 5; MIN_TRAIN = 0.45
SEEDS = [42, 7]

LGB = dict(objective='binary', n_estimators=200, learning_rate=0.05,
           num_leaves=31, max_depth=6, min_child_samples=60,
           subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=1)

Z = np.load(CACHE, allow_pickle=True)
probas = {k: Z[k] for k in Z.files}


def efficiency_ratio(close, n):
    s = pd.Series(close)
    change = (s - s.shift(n)).abs()
    vol = s.diff().abs().rolling(n).sum()
    return (change / (vol + 1e-12)).shift(1).values


def mr_target(df, horizon, tp_mult, sl_mult, atr, direction):
    """برچسبِ MR: آیا TP (بازگشت به میانگین) قبل از SL خورد؟ بردار، بدون look-ahead در فیچر."""
    high = df['high'].values; low = df['low'].values; close = df['close'].values
    av = atr.values; n = len(df)
    y = np.full(n, np.nan)
    is_long = direction == 'long'
    for i in range(n):
        if np.isnan(av[i]): continue
        entry = close[i]; a = av[i]
        if is_long:
            tp = entry + tp_mult * a; sl = entry - sl_mult * a
        else:
            tp = entry - tp_mult * a; sl = entry + sl_mult * a
        end = min(i + horizon + 1, n)
        res = np.nan
        for j in range(i + 1, end):
            if is_long:
                if low[j] <= sl: res = 0; break
                if high[j] >= tp: res = 1; break
            else:
                if high[j] >= sl: res = 0; break
                if low[j] <= tp: res = 1; break
        y[i] = res
    return y


def wf_proba(X_all, cols_ok, cand, y, seed, n):
    valid_mask = cols_ok & cand & ~np.isnan(y)
    idx = np.where(valid_mask)[0]
    if len(idx) < 400:
        return np.full(n, np.nan, dtype=np.float32)
    X = X_all[idx]; Y = y[idx].astype(np.int8)
    N = len(X); mt = int(N * MIN_TRAIN); fold = max(1, (N - mt) // N_FOLDS)
    proba = np.full(n, np.nan, dtype=np.float32)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold
        te_end = tr_end + fold if k < N_FOLDS - 1 else N
        if tr_end >= N: break
        m = lgb.LGBMClassifier(random_state=seed, **LGB)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1].astype(np.float32)
        del m; gc.collect()
    return proba


def build_asset(a):
    """داده + اندیکاتورهای مشترک هر دارایی."""
    df = load_data(f'data/{a}_M15.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    c = df['close'].values
    atr = ind.atr(df, 14)
    e50 = ind.ema(df['close'], 50).values
    e200 = ind.ema(df['close'], 200).values
    er = efficiency_ratio(c, ER_N)
    rsi = ind.rsi(df['close'], 14).values
    bb_l, bb_m, bb_u = ind.bollinger(df['close'], 20, 2.0)
    am = np.nanmean(atr.values)
    return dict(df=df, atr=atr, c=c, e50=e50, e200=e200, er=er, rsi=rsi,
                bb_l=bb_l.values, bb_u=bb_u.values, am=am,
                spread=SPREAD_ATR * am, be=0.10 * am)


def trend_trades(a, d):
    """جریان A: روند-ML (probaِ S55) روی کاندیدِ روند در رژیمِ روندی."""
    df = d['df']; atr = d['atr']
    cL = (d['c'] > d['e50']) & (d['e50'] > d['e200']) & ~np.isnan(atr.values)
    cS = (d['c'] < d['e50']) & (d['e50'] < d['e200']) & ~np.isnan(atr.values)
    frames = []
    for direction, cand in [('long', cL), ('short', cS)]:
        p = probas[f'{a}_{direction}']
        entries = cand & (p >= TREND_THRESH) & ~np.isnan(p)
        if entries.sum() == 0: continue
        _s, tr = run_multistep_backtest(df, entries, direction, atr, sl_mult=1.5,
                                        tp_mults=(0.8, 1.5, 2.5), tp_fracs=(0.34, 0.33, 0.33),
                                        trail_mult=1.5, be_offset=d['be'], spread=d['spread'],
                                        max_hold=200, allow_overlap=False)
        if len(tr) == 0: continue
        tr = tr.copy(); tr['pnl_R'] = tr['r_mult']; tr['asset'] = a; tr['stream'] = 'trend'
        tr['dt'] = df['dt'].iloc[tr['entry_bar'].values].values
        frames.append(tr[['asset', 'stream', 'dt', 'pnl_R', 'n_actions']])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def range_mr_trades(a, d, X_all, cols_ok):
    """جریان B: MR-ML روی کاندیدِ رنج (ER پایین + BB-touch + RSI اکسترمم)."""
    df = d['df']; atr = d['atr']
    range_reg = (d['er'] <= RANGE_ER_MAX)
    # کاندیدِ MR-long: لمسِ BB پایین + RSI پایین در رنج
    candL = range_reg & (d['c'] <= d['bb_l']) & (d['rsi'] < 38) & ~np.isnan(atr.values)
    candS = range_reg & (d['c'] >= d['bb_u']) & (d['rsi'] > 62) & ~np.isnan(atr.values)
    frames = []
    for direction, cand in [('long', candL), ('short', candS)]:
        if cand.sum() < 400: continue
        y = mr_target(df, MR_HZ, MR_TP, MR_SL, atr, direction)
        ps = [wf_proba(X_all, cols_ok, cand, y, s, len(df)) for s in SEEDS]
        p = np.nanmean(np.vstack(ps), axis=0)
        entries = cand & (p >= MR_THRESH) & ~np.isnan(p)
        if entries.sum() == 0: continue
        _s, tr = run_multistep_backtest(df, entries, direction, atr, sl_mult=MR_SL,
                                        tp_mults=(0.7, 1.0, 1.4), tp_fracs=(0.4, 0.35, 0.25),
                                        trail_mult=1.2, be_offset=d['be'], spread=d['spread'],
                                        max_hold=MR_HZ * 2, allow_overlap=False)
        if len(tr) == 0: continue
        tr = tr.copy(); tr['pnl_R'] = tr['r_mult']; tr['asset'] = a; tr['stream'] = 'mr'
        tr['dt'] = df['dt'].iloc[tr['entry_bar'].values].values
        frames.append(tr[['asset', 'stream', 'dt', 'pnl_R', 'n_actions']])
        del y, ps; gc.collect()
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def metrics(tr, span_days):
    if tr is None or len(tr) == 0: return None
    n = len(tr); wr = (tr['pnl_R'] > 0).mean() * 100
    gp = tr.loc[tr['pnl_R'] > 0, 'pnl_R'].sum()
    gl = -tr.loc[tr['pnl_R'] < 0, 'pnl_R'].sum()
    pf = gp / gl if gl > 1e-9 else np.inf
    epd = n / tr['dt'].dt.date.nunique()
    apd = tr['n_actions'].sum() / span_days if span_days else 0
    return dict(n=n, wr=wr, pf=pf, exp=tr['pnl_R'].mean(), epd=epd, apd=apd)


def report_block(tr, label):
    t0, t1 = tr['dt'].min(), tr['dt'].max()
    tmid = t0 + (t1 - t0) / 2
    span_all = max(1, (t1 - t0).days)
    span_h1 = max(1, (tmid - t0).days); span_h2 = max(1, (t1 - tmid).days)
    mALL = metrics(tr, span_all)
    m1 = metrics(tr[tr['dt'] < tmid], span_h1)
    m2 = metrics(tr[tr['dt'] >= tmid], span_h2)
    print(f"\n--- {label} ---")
    for nm, m in [('کل', mALL), ('نیمه۱', m1), ('نیمه۲', m2)]:
        if m:
            print(f"  {nm}: n={m['n']} WR={m['wr']:.1f}% PF={m['pf']:.3f} "
                  f"exp={m['exp']:+.3f}R ورود/روز={m['epd']:.2f} اکشن/روز={m['apd']:.2f}")
    return mALL, m1, m2


print("=== S59: پرتفویِ دو-متخصصِ رژیم-مکمل (Trend-ML + Range-MR-ML) ===", flush=True)
trend_all, mr_all = [], []
for a in ASSETS:
    print(f"\n[{a}] ساختِ داده و دو جریان ...", flush=True)
    d = build_asset(a)
    feats = build_features(d['df']); X_all = feats.values.astype(np.float32)
    cols_ok = ~np.isnan(X_all).any(axis=1); del feats; gc.collect()

    tt = trend_trades(a, d)
    mt = range_mr_trades(a, d, X_all, cols_ok)
    if len(tt):
        print(f"  Trend: n={len(tt)} WR={(tt['pnl_R']>0).mean()*100:.1f}%")
        trend_all.append(tt)
    if len(mt):
        print(f"  Range-MR: n={len(mt)} WR={(mt['pnl_R']>0).mean()*100:.1f}%")
        mr_all.append(mt)
    del d, X_all, cols_ok; gc.collect()

trend = pd.concat(trend_all, ignore_index=True) if trend_all else pd.DataFrame()
mr = pd.concat(mr_all, ignore_index=True) if mr_all else pd.DataFrame()

if len(trend): report_block(trend, "جریانِ A: Trend-ML (تنها)")
if len(mr): report_block(mr, "جریانِ B: Range-MR-ML (تنها)")

if len(trend) and len(mr):
    port = pd.concat([trend, mr], ignore_index=True).sort_values('dt').reset_index(drop=True)
    mALL, m1, m2 = report_block(port, "🎯 پرتفویِ ادغام‌شده (A ∪ B)")
    if m1 and m2:
        ok = (m1['pf'] > 1.3 and m2['pf'] > 1.3 and m1['wr'] > 60 and m2['wr'] > 60
              and m1['exp'] > 0 and m2['exp'] > 0 and m1['apd'] >= 5 and m2['apd'] >= 5)
        print(f"\n→ همهٔ قیودِ دو-نیمه (WR>60, PF>1.3, exp>0, اکشن/روز≥5)؟ "
              f"{'✅✅✅ بله!' if ok else '❌ خیر'}")
        # همچنین با معیارِ ورود/روز
        ok2 = (m1['pf'] > 1.3 and m2['pf'] > 1.3 and m1['wr'] > 60 and m2['wr'] > 60
               and m1['exp'] > 0 and m2['exp'] > 0 and m1['epd'] >= 5 and m2['epd'] >= 5)
        print(f"→ با معیارِ «ورود/روز≥5»؟ {'✅ بله' if ok2 else '❌ خیر'}")

print("\nتمام.", flush=True)
