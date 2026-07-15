"""
ماژول ساخت feature برای مدل‌های یادگیری ماشین.
تمام featureها فقط از اطلاعات گذشته/جاری استفاده می‌کنند (no look-ahead).
"""
import numpy as np
import pandas as pd
import indicators as ind
from numba import njit


def build_features(df):
    """دیتافریم feature هم‌طول df برمی‌گرداند (NaN در ابتدای سری)."""
    f = pd.DataFrame(index=df.index)
    close, high, low, o = df['close'], df['high'], df['low'], df['open']
    vol = df['volume']

    # --- بازده‌ها در افق‌های مختلف ---
    for p in [1, 2, 3, 5, 8, 13, 21]:
        f[f'ret_{p}'] = close.pct_change(p)

    # --- RSI چند دوره ---
    for p in [7, 14, 21]:
        f[f'rsi_{p}'] = ind.rsi(close, p)

    # --- MACD ---
    macd_line, sig_line, hist = ind.macd(close)
    f['macd'] = macd_line
    f['macd_sig'] = sig_line
    f['macd_hist'] = hist

    # --- ATR و نوسان ---
    atr = ind.atr(df, 14)
    f['atr'] = atr
    f['atr_pct'] = atr / close
    atr_ma = atr.rolling(50).mean()
    f['atr_ratio'] = atr / atr_ma  # فشردگی/انبساط نوسان
    f['range_pct'] = (high - low) / close
    f['body_pct'] = (close - o).abs() / close

    # --- ADX / DI ---
    adx, pdi, mdi = ind.adx(df, 14)
    f['adx'] = adx
    f['di_diff'] = pdi - mdi

    # --- موقعیت در Bollinger ---
    lo_b, mid_b, up_b = ind.bollinger(close, 20, 2.0)
    width = (up_b - lo_b).replace(0, np.nan)
    f['bb_pos'] = (close - lo_b) / width       # 0=پایین, 1=بالا
    f['bb_width'] = width / close

    # --- Stochastic ---
    k, d = ind.stoch(df, 14, 3)
    f['stoch_k'] = k
    f['stoch_d'] = d

    # --- فاصله از میانگین‌های متحرک ---
    for p in [20, 50, 100]:
        e = ind.ema(close, p)
        f[f'dist_ema{p}'] = (close - e) / e

    # --- شیب روند ---
    f['slope_20'] = ind.rolling_slope(close, 20) / close
    f['slope_50'] = ind.rolling_slope(close, 50) / close

    # --- z-score قیمت ---
    f['zscore_20'] = ind.zscore(close, 20)
    f['zscore_50'] = ind.zscore(close, 50)

    # --- حجم ---
    f['vol_ratio'] = vol / vol.rolling(20).mean()

    # --- ساختار کندل ---
    f['upper_wick'] = (high - np.maximum(o, close)) / (high - low).replace(0, np.nan)
    f['lower_wick'] = (np.minimum(o, close) - low) / (high - low).replace(0, np.nan)

    # --- تعداد کندل هم‌جهت اخیر (streak) ---
    sign = np.sign(close.diff())
    f['streak'] = sign.groupby((sign != sign.shift()).cumsum()).cumcount() + 1
    f['streak'] = f['streak'] * sign  # علامت‌دار

    # --- ویژگی‌های زمانی ---
    hour = df['dt'].dt.hour
    dow = df['dt'].dt.dayofweek
    f['hour_sin'] = np.sin(2*np.pi*hour/24)
    f['hour_cos'] = np.cos(2*np.pi*hour/24)
    f['dow'] = dow
    f['hour'] = hour

    # --- فاصله از open روزانه ---
    date = df['dt'].dt.date
    daily_open = df.groupby(date)['open'].transform('first')
    f['dist_daily_open'] = (close - daily_open) / daily_open

    # --- ویژگی‌های چند-تایم‌فریمی (روند بزرگ‌تر) ---
    # M15 -> H1 (۴ کندل)، H4 (۱۶ کندل)، D1 (۹۶ کندل)
    for htf, name in [(4, 'h1'), (16, 'h4'), (96, 'd1')]:
        ema_htf = ind.ema(close, htf*3)
        f[f'trend_{name}'] = (close - ema_htf) / ema_htf
        f[f'slope_{name}'] = ind.rolling_slope(close, htf) / close
        # RSI روی close نمونه‌برداری‌شده تقریبی
        f[f'ret_{name}'] = close.pct_change(htf)

    # --- روند بلندمدت EMA200 (فیلتر رژیم) ---
    ema200 = ind.ema(close, 200)
    f['above_ema200'] = (close > ema200).astype(float)
    f['dist_ema200'] = (close - ema200) / ema200

    return f


@njit(cache=True)
def _target_loop(high, low, close, atr_v, horizon, tp_mult, sl_mult, is_long):
    n = len(close)
    y = np.full(n, np.nan)
    for i in range(n - horizon - 1):
        entry = close[i]
        a = atr_v[i]
        if np.isnan(a):
            continue
        if is_long:
            tp = entry + tp_mult * a
            sl = entry - sl_mult * a
        else:
            tp = entry - tp_mult * a
            sl = entry + sl_mult * a
        res = 0.0
        for j in range(i+1, i+1+horizon):
            hi = high[j]; lo = low[j]
            if is_long:
                hit_tp = hi >= tp; hit_sl = lo <= sl
            else:
                hit_tp = lo <= tp; hit_sl = hi >= sl
            if hit_sl and hit_tp:
                res = 0.0; break
            if hit_tp:
                res = 1.0; break
            if hit_sl:
                res = 0.0; break
        y[i] = res
    return y


def make_target(df, horizon, tp_mult, sl_mult, atr, direction):
    """
    برچسب دودویی: آیا در «horizon» کندل آینده، TP قبل از SL لمس می‌شود؟
    ورود فرضی در close کندل جاری. (پیاده‌سازی numba برای سرعت)
    """
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    close = df['close'].values.astype(np.float64)
    atr_v = atr.values.astype(np.float64)
    is_long = (direction == 'long')
    return _target_loop(high, low, close, atr_v, horizon, tp_mult, sl_mult, is_long)
