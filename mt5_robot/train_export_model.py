"""
آموزش مدل نهایی استراتژی ۱۴ (نسخه‌ی ساده‌شده MQL5-friendly) و صادرات به ONNX.
============================================================================
هدف: مدلی با زیرمجموعه‌ای از fe[atureهای «قابل‌محاسبه‌ی بدون‌ابهام در MQL5»
آموزش دهیم که WR>60٪ استراتژی ۱۴ را حفظ کند، سپس آن را به ONNX صادر کنیم تا
Expert Advisor در MetaTrader 5 مستقیماً همان مدل را اجرا کند.

feature‌های انتخابی (همه تک‌تایم‌فریم M15، بدون VWAP لنگرشده و بدون MTF پیچیده
که در MQL5 مستعد خطای همگام‌سازی‌اند):
  RSI(14), MACD(12,26,9) + hist, ATR%, ADX(14), DI-diff, BollingerPos, BB-width,
  Stoch K/D, فاصله از EMA20/50/200 (نرمال‌شده با ATR)، شیب EMA، بازده‌های اخیر،
  اندازه بدنه/سایه، ساعت (sin/cos)، وضعیت روند EMA.

اعتبارسنجی: همان Walk-Forward استراتژی ۱۴ برای تأیید WR>60٪ روی این زیرمجموعه.
"""
import sys, os
ENGINE = os.path.join(os.path.dirname(__file__), '..', 'engine')
sys.path.insert(0, ENGINE)
import numpy as np
import pandas as pd
import lightgbm as lgb
from scipy import stats
import indicators as ind
from backtest import load_data, run_backtest
import warnings; warnings.filterwarnings('ignore')

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')

# پارامترهای برنده‌ی استراتژی ۱۴
HZ, TP_M, SL_M, THR = 48, 1.0, 1.5, 0.62
BE = SL_M / (TP_M + SL_M) * 100
SEEDS = [42, 7, 123]
N_FOLDS = 6
MIN_TRAIN_FRAC = 0.40

# ترتیب دقیق feature (باید در EA MQL5 دقیقاً همین ترتیب باشد)
FEATURE_ORDER = [
    'ret_1', 'ret_2', 'ret_3', 'ret_5', 'ret_8',
    'rsi_14', 'macd', 'macd_hist',
    'atr_pct', 'adx', 'di_diff',
    'bb_pos', 'bb_width', 'stoch_k', 'stoch_d',
    'dist_ema20_atr', 'dist_ema50_atr', 'dist_ema200_atr',
    'slope_20', 'body_pct', 'upper_wick', 'lower_wick',
    'hour_sin', 'hour_cos',
]


def build_simple_features(df):
    """featureهای ساده‌ی MQL5-friendly (فقط M15، بدون VWAP/MTF)."""
    c = df['close']; h = df['high']; l = df['low']; o = df['open']
    f = pd.DataFrame(index=df.index)
    for k in (1, 2, 3, 5, 8):
        f[f'ret_{k}'] = c.pct_change(k)
    f['rsi_14'] = ind.rsi(c, 14)
    macd, macd_sig, macd_hist = ind.macd(c)
    f['macd'] = macd
    f['macd_hist'] = macd_hist
    atr = ind.atr(df, 14)
    f['atr_pct'] = atr / c
    adx_, plus_di, minus_di = ind.adx(df, 14)
    f['adx'] = adx_
    f['di_diff'] = plus_di - minus_di
    lo_b, mid_b, up_b = ind.bollinger(c, 20, 2.0)
    f['bb_pos'] = (c - lo_b) / (up_b - lo_b)
    f['bb_width'] = (up_b - lo_b) / c
    stoch_k, stoch_d = ind.stoch(df, 14, 3)
    f['stoch_k'] = stoch_k
    f['stoch_d'] = stoch_d
    ema20 = ind.ema(c, 20); ema50 = ind.ema(c, 50); ema200 = ind.ema(c, 200)
    f['dist_ema20_atr'] = (c - ema20) / atr
    f['dist_ema50_atr'] = (c - ema50) / atr
    f['dist_ema200_atr'] = (c - ema200) / atr
    f['slope_20'] = ind.rolling_slope(c, 20) / atr
    rng = (h - l).replace(0, np.nan)
    f['body_pct'] = (c - o).abs() / rng
    f['upper_wick'] = (h - np.maximum(c, o)) / rng
    f['lower_wick'] = (np.minimum(c, o) - l) / rng
    hour = df['dt'].dt.hour
    f['hour_sin'] = np.sin(2 * np.pi * hour / 24)
    f['hour_cos'] = np.cos(2 * np.pi * hour / 24)
    return f, ema50, ema200, atr


def make_target(df, hz, tp_m, sl_m, atr):
    high = df['high'].values; low = df['low'].values; close = df['close'].values
    av = atr.values; n = len(df); y = np.full(n, np.nan)
    for i in range(n):
        a = av[i]
        if np.isnan(a) or a <= 0 or i >= n - 1:
            continue
        entry = close[i]; TP = entry + tp_m * a; SL = entry - sl_m * a
        lab = 0
        for j in range(i + 1, min(i + 1 + hz, n)):
            if low[j] <= SL and high[j] >= TP:
                lab = 0; break
            if high[j] >= TP:
                lab = 1; break
            if low[j] <= SL:
                lab = 0; break
        y[i] = lab
    return y


def wf_proba(feats, fc, cand, y, n, seed):
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=fc + ['y']); valid = valid[valid['cand']]
    X = valid[fc].values; Y = valid['y'].values.astype(int); idx = valid.index.values
    N = len(X); mt = int(N * MIN_TRAIN_FRAC); fold = (N - mt) // N_FOLDS
    proba = np.full(n, np.nan)
    for k in range(N_FOLDS):
        tr_end = mt + k * fold; te_end = tr_end + fold if k < N_FOLDS - 1 else N
        m = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.025, num_leaves=32,
                               max_depth=6, subsample=0.8, colsample_bytree=0.75,
                               min_child_samples=80, reg_lambda=2.0,
                               random_state=seed, verbose=-1)
        m.fit(X[:tr_end], Y[:tr_end])
        proba[idx[tr_end:te_end]] = m.predict_proba(X[tr_end:te_end])[:, 1]
    return proba


def main():
    print("بارگذاری داده و ساخت featureهای ساده...")
    df = load_data(DATA)
    feats, ema50, ema200, atr = build_simple_features(df)
    fc = FEATURE_ORDER
    feats = feats[fc]
    c = df['close'].values
    cand = (c > ema50.values) & (ema50.values > ema200.values)
    y = make_target(df, HZ, TP_M, SL_M, atr)
    n = len(df)

    print("Walk-Forward برای تأیید WR>60٪ روی featureهای ساده...")
    proba = np.nanmean(np.vstack([wf_proba(feats, fc, cand, y, n, sd) for sd in SEEDS]), axis=0)
    oos = ~np.isnan(proba)
    entries = cand & (proba >= THR) & oos
    atr_arr = atr.values
    s, tr = run_backtest(df, entries, None, None, 'long', spread=0.20, max_hold=HZ,
                         sl_series=SL_M * atr_arr, tp_series=TP_M * atr_arr,
                         allow_overlap=False)
    nt = s['n_trades']; wins = int(round(s['win_rate'] / 100 * nt))
    pval = stats.binomtest(wins, nt, BE / 100, alternative='greater').pvalue
    span_days = (df['dt'].max() - df['dt'].min()).days
    trading_days = span_days * 5 / 7
    tpd = (nt / trading_days) / (oos.sum() / n)
    print("=" * 60)
    print(f"مدل ساده‌شده (thr={THR}): n={nt} WR={s['win_rate']:.2f}% "
          f"exp={s['expectancy']:+.3f}$ PnL={s['total_pnl']:+.0f}$ "
          f"tpd={tpd:.2f} p={pval:.4f}")
    print("=" * 60)

    # آموزش مدل نهایی روی کل داده و صادرات ONNX (ensemble → میانگین با یک مدل واحد
    # روی همه‌ی داده؛ برای production از seed=42 استفاده می‌کنیم)
    print("\nآموزش مدل نهایی روی کل داده برای صادرات ONNX...")
    data = feats.copy(); data['y'] = y; data['cand'] = cand
    valid = data.dropna(subset=fc + ['y']); valid = valid[valid['cand']]
    X = valid[fc].values.astype(np.float32); Y = valid['y'].values.astype(int)
    final = lgb.LGBMClassifier(n_estimators=500, learning_rate=0.025, num_leaves=32,
                               max_depth=6, subsample=0.8, colsample_bytree=0.75,
                               min_child_samples=80, reg_lambda=2.0,
                               random_state=42, verbose=-1)
    final.fit(X, Y)

    # صادرات به ONNX
    from onnxmltools.convert import convert_lightgbm
    from onnxconverter_common.data_types import FloatTensorType
    initial_type = [('input', FloatTensorType([None, len(fc)]))]
    onx = convert_lightgbm(final, initial_types=initial_type, zipmap=False,
                           target_opset=12)
    out_path = os.path.join(os.path.dirname(__file__), 'xauusd_s14_model.onnx')
    with open(out_path, 'wb') as fp:
        fp.write(onx.SerializeToString())
    print(f"مدل ONNX ذخیره شد: {out_path} ({os.path.getsize(out_path)} bytes)")

    # ذخیره‌ی متادیتا (ترتیب feature + پارامترها) برای EA
    meta_path = os.path.join(os.path.dirname(__file__), 'model_meta.txt')
    with open(meta_path, 'w') as fp:
        fp.write(f"THR={THR}\nHZ={HZ}\nTP_M={TP_M}\nSL_M={SL_M}\nBE={BE}\n")
        fp.write("FEATURES=" + ",".join(fc) + "\n")
    print(f"متادیتا ذخیره شد: {meta_path}")


if __name__ == '__main__':
    main()
