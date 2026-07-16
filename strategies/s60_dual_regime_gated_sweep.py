"""
S60 — جاروبِ گیتِ کیفیت روی پرتفویِ دو-رژیمِ S59 (Trend-ML + Range-MR-ML)
================================================================================
S59 نشان داد افزودنِ جریانِ Range-MR-ML (با فیلترِ ML) فرکانس را به ۲۶ ورود/روز
رساند و WR را ۶۳٪ نگه داشت — اما با threshold پایین (۰.۶۲/۰.۵۸) PF≈۱.۰ (L30).
حالا چون فرکانسِ خام بسیار بالاست، فضای زیادی برای **گیتِ کیفیتِ سخت‌تر** داریم
بدونِ افتِ فرکانس زیرِ حدِ نصاب.

فرضیه: با بالا بردنِ threshold هر دو جریان به‌طورِ هم‌زمان، ممکن است نقطه‌ای پیدا
شود که هر دو نیمه PF>1.3 و WR>60 بدهند و فرکانس (ورود یا اکشن) ≥۵ بماند — چون
تنوعِ دو-رژیمی (ناهمبسته در زمان) شعاعِ مثلثِ ناممکن را بزرگ‌تر می‌کند.

این نسخه probaها را **یک‌بار** می‌سازد و cache می‌کند، سپس گیت را ارزان جارو می‌کند.
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
TREND_CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s55_proba_cache.npz')
MR_CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s60_mr_cache.npz')
SPREAD_ATR = 0.06; ER_N = 96; RANGE_ER_MAX = 0.10
MR_HZ = 24; MR_TP = 1.0; MR_SL = 1.2
N_FOLDS = 5; MIN_TRAIN = 0.45; SEEDS = [42, 7]

LGB = dict(objective='binary', n_estimators=200, learning_rate=0.05,
           num_leaves=31, max_depth=6, min_child_samples=60,
           subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1, n_jobs=1)

trend_probas = {k: np.load(TREND_CACHE, allow_pickle=True)[k]
                for k in np.load(TREND_CACHE, allow_pickle=True).files}


def efficiency_ratio(close, n):
    s = pd.Series(close)
    change = (s - s.shift(n)).abs()
    vol = s.diff().abs().rolling(n).sum()
    return (change / (vol + 1e-12)).shift(1).values


def mr_target(df, horizon, tp_mult, sl_mult, atr, is_long):
    high = df['high'].values; low = df['low'].values; close = df['close'].values
    av = atr.values; n = len(df); y = np.full(n, np.nan)
    for i in range(n):
        if np.isnan(av[i]): continue
        entry = close[i]; a = av[i]
        if is_long: tp = entry + tp_mult*a; sl = entry - sl_mult*a
        else:       tp = entry - tp_mult*a; sl = entry + sl_mult*a
        end = min(i + horizon + 1, n); res = np.nan
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
    valid = cols_ok & cand & ~np.isnan(y)
    idx = np.where(valid)[0]
    if len(idx) < 400: return np.full(n, np.nan, dtype=np.float32)
    X = X_all[idx]; Y = y[idx].astype(np.int8)
    N = len(X); mt = int(N*MIN_TRAIN); fold = max(1, (N-mt)//N_FOLDS)
    proba = np.full(n, np.nan, dtype=np.float32)
    for k in range(N_FOLDS):
        tr_end = mt + k*fold; te_end = tr_end+fold if k < N_FOLDS-1 else N
        if tr_end >= N: break
        m = lgb.LGBMClassifier(random_state=seed, **LGB)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:,1].astype(np.float32)
        del m; gc.collect()
    return proba


# ---------- ساخت/بارگذاریِ کشِ MR ----------
def build_mr_cache():
    if os.path.exists(MR_CACHE):
        print("بارگذاریِ کشِ MR ...", flush=True)
        z = np.load(MR_CACHE, allow_pickle=True)
        return {k: z[k] for k in z.files}
    out = {}
    for a in ASSETS:
        print(f"  MR-ML آموزشِ {a} ...", flush=True)
        df = load_data(f'data/{a}_M15.csv')
        c = df['close'].values; atr = ind.atr(df, 14)
        er = efficiency_ratio(c, ER_N); rsi = ind.rsi(df['close'], 14).values
        bb_l, _, bb_u = ind.bollinger(df['close'], 20, 2.0)
        rng = er <= RANGE_ER_MAX
        candL = rng & (c <= bb_l.values) & (rsi < 38) & ~np.isnan(atr.values)
        candS = rng & (c >= bb_u.values) & (rsi > 62) & ~np.isnan(atr.values)
        feats = build_features(df); X_all = feats.values.astype(np.float32)
        cols_ok = ~np.isnan(X_all).any(axis=1); del feats; gc.collect()
        for d, cand, is_long in [('long', candL, True), ('short', candS, False)]:
            if cand.sum() < 400:
                out[f'{a}_{d}'] = np.full(len(df), np.nan, dtype=np.float32); continue
            y = mr_target(df, MR_HZ, MR_TP, MR_SL, atr, is_long)
            ps = [wf_proba(X_all, cols_ok, cand, y, s, len(df)) for s in SEEDS]
            out[f'{a}_{d}'] = np.nanmean(np.vstack(ps), axis=0).astype(np.float32)
            del y, ps; gc.collect()
        del df, X_all, cols_ok; gc.collect()
    np.savez_compressed(MR_CACHE, **out)
    print("✅ کشِ MR ذخیره شد.", flush=True)
    return out

mr_probas = build_mr_cache()


# ---------- ساختِ معاملات با گیتِ threshold ----------
def all_trades(trend_thr, mr_thr):
    frames = []
    for a in ASSETS:
        df = load_data(f'data/{a}_M15.csv')
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        c = df['close'].values; atr = ind.atr(df, 14)
        e50 = ind.ema(df['close'], 50).values; e200 = ind.ema(df['close'], 200).values
        er = efficiency_ratio(c, ER_N); rsi = ind.rsi(df['close'], 14).values
        bb_l, _, bb_u = ind.bollinger(df['close'], 20, 2.0)
        am = np.nanmean(atr.values); spread = SPREAD_ATR*am; be = 0.10*am
        rng = er <= RANGE_ER_MAX
        # جریان A: trend
        cL = (c > e50) & (e50 > e200) & ~np.isnan(atr.values)
        cS = (c < e50) & (e50 < e200) & ~np.isnan(atr.values)
        for direction, cand in [('long', cL), ('short', cS)]:
            p = trend_probas[f'{a}_{direction}']
            ent = cand & (p >= trend_thr) & ~np.isnan(p)
            if ent.sum() == 0: continue
            _s, tr = run_multistep_backtest(df, ent, direction, atr, sl_mult=1.5,
                                tp_mults=(0.8,1.5,2.5), tp_fracs=(0.34,0.33,0.33),
                                trail_mult=1.5, be_offset=be, spread=spread,
                                max_hold=200, allow_overlap=False)
            if len(tr) == 0: continue
            tr = tr.copy(); tr['pnl_R']=tr['r_mult']; tr['stream']='trend'
            tr['dt']=df['dt'].iloc[tr['entry_bar'].values].values
            frames.append(tr[['stream','dt','pnl_R','n_actions']])
        # جریان B: range-MR
        candL = rng & (c <= bb_l.values) & (rsi < 38) & ~np.isnan(atr.values)
        candS = rng & (c >= bb_u.values) & (rsi > 62) & ~np.isnan(atr.values)
        for direction, cand in [('long', candL), ('short', candS)]:
            p = mr_probas[f'{a}_{direction}']
            ent = cand & (p >= mr_thr) & ~np.isnan(p)
            if ent.sum() == 0: continue
            _s, tr = run_multistep_backtest(df, ent, direction, atr, sl_mult=MR_SL,
                                tp_mults=(0.7,1.0,1.4), tp_fracs=(0.4,0.35,0.25),
                                trail_mult=1.2, be_offset=be, spread=spread,
                                max_hold=MR_HZ*2, allow_overlap=False)
            if len(tr) == 0: continue
            tr = tr.copy(); tr['pnl_R']=tr['r_mult']; tr['stream']='mr'
            tr['dt']=df['dt'].iloc[tr['entry_bar'].values].values
            frames.append(tr[['stream','dt','pnl_R','n_actions']])
        del df, c, atr, e50, e200, er, rsi; gc.collect()
    return pd.concat(frames, ignore_index=True).sort_values('dt').reset_index(drop=True) if frames else pd.DataFrame()


def metrics(tr, span):
    if tr is None or len(tr)==0: return None
    n=len(tr); wr=(tr['pnl_R']>0).mean()*100
    gp=tr.loc[tr['pnl_R']>0,'pnl_R'].sum(); gl=-tr.loc[tr['pnl_R']<0,'pnl_R'].sum()
    pf=gp/gl if gl>1e-9 else np.inf
    epd=n/tr['dt'].dt.date.nunique(); apd=tr['n_actions'].sum()/span if span else 0
    return dict(n=n,wr=wr,pf=pf,exp=tr['pnl_R'].mean(),epd=epd,apd=apd)


print("\n=== S60: جاروبِ گیتِ کیفیت روی پرتفویِ دو-رژیم ===", flush=True)
print(f"{'trend':>5} {'mr':>5} | {'n':>6} {'WR':>5} {'PF':>6} {'ورود/د':>6} {'اکشن/د':>7} | "
      f"{'ن۱PF':>6} {'ن۱WR':>5} {'ن۱ورود':>6} | {'ن۲PF':>6} {'ن۲WR':>5} {'ن۲ورود':>6} | قید")
print("-"*115)

GRID = [(0.62,0.58),(0.66,0.60),(0.68,0.62),(0.70,0.64),(0.72,0.66),(0.72,0.68),(0.74,0.68)]
winner = None
for tthr, mthr in GRID:
    port = all_trades(tthr, mthr)
    if len(port)==0: continue
    t0,t1 = port['dt'].min(), port['dt'].max(); tmid = t0+(t1-t0)/2
    sa=max(1,(t1-t0).days); s1=max(1,(tmid-t0).days); s2=max(1,(t1-tmid).days)
    mA=metrics(port,sa); m1=metrics(port[port['dt']<tmid],s1); m2=metrics(port[port['dt']>=tmid],s2)
    if not(m1 and m2): continue
    ok = (m1['pf']>1.3 and m2['pf']>1.3 and m1['wr']>60 and m2['wr']>60
          and m1['exp']>0 and m2['exp']>0 and m1['epd']>=5 and m2['epd']>=5)
    flag='✅' if ok else '❌'
    print(f"{tthr:>5.2f} {mthr:>5.2f} | {mA['n']:>6} {mA['wr']:>4.1f}% {mA['pf']:>6.3f} "
          f"{mA['epd']:>6.2f} {mA['apd']:>7.2f} | {m1['pf']:>6.3f} {m1['wr']:>4.1f}% {m1['epd']:>6.2f} | "
          f"{m2['pf']:>6.3f} {m2['wr']:>4.1f}% {m2['epd']:>6.2f} | {flag}")
    if ok and (winner is None or min(m1['pf'],m2['pf']) > winner[0]):
        winner = (min(m1['pf'],m2['pf']), tthr, mthr, mA, m1, m2)

print()
if winner:
    _, tthr, mthr, mA, m1, m2 = winner
    print("🎯🎯🎯 برنده! همهٔ قیودِ دو-نیمه برآورده شد.")
    print(f"   trend_thr={tthr}, mr_thr={mthr}")
    print(f"   کل: WR={mA['wr']:.1f}% PF={mA['pf']:.3f} ورود/روز={mA['epd']:.2f}")
else:
    print("در این گرید هیچ نقطه‌ای همهٔ قیودِ دو-نیمه را برآورده نکرد.")
print("\nتمام.", flush=True)
