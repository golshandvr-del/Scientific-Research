"""
ماژول مولتی‌تایم‌فریم (MTF) — هستهٔ معماری تاپ-داون واقعی.

هدف: برای هر کندل M15 در زمان t، featureهای تایم‌فریم‌های بالاتر (M30/H1/H4/D1/W1)
را طوری بچسبانیم که **هیچ نشت آینده (look-ahead)** رخ ندهد.

--------------------------------------------------------------------------------
قاعدهٔ طلایی (بسیار مهم):
--------------------------------------------------------------------------------
ستون `time` در همهٔ CSVها زمان *باز شدن* کندل است (unix seconds).
پس زمان *بسته‌شدن* یک کندل HTF = time_open + duration(TF).

برای کندل M15 در زمان باز شدن t، فقط از کندل‌های HTF استفاده می‌کنیم که
**کاملاً پیش از t بسته شده‌اند**، یعنی:  close_time_HTF <= t.

پیاده‌سازی: اندیکاتورها را روی HTF محاسبه می‌کنیم (که ذاتاً فقط از گذشتهٔ خودِ HTF
استفاده می‌کنند)، سپس هر ردیف HTF را به «زمان بسته‌شدنش» مُهر می‌زنیم و با
merge_asof(direction='backward') روی زمان باز شدن کندل M15 نگاشت می‌کنیم.
merge_asof تضمین می‌کند نزدیک‌ترین کندل HTF که close_time <= t است انتخاب شود.

این دقیقاً کاری است که یک تریدر واقعی در زمان واقعی می‌بیند: در ساعت ۱۰:۱۵،
آخرین کندل D1 «بسته‌شده» کندل دیروز است، نه کندل امروز که هنوز باز است.
"""
import numpy as np
import pandas as pd
import indicators as ind


# مدت هر تایم‌فریم بر حسب ثانیه (برای محاسبهٔ زمان بسته‌شدن)
TF_SECONDS = {
    'M5':   5 * 60,
    'M15':  15 * 60,
    'M30':  30 * 60,
    'H1':   60 * 60,
    'H4':   4 * 60 * 60,
    'D1':   24 * 60 * 60,
    'W1':   7 * 24 * 60 * 60,
}


def load_tf(tf, data_dir='data'):
    """یک تایم‌فریم را می‌خواند و ستون‌های زمان باز/بسته را اضافه می‌کند."""
    df = pd.read_csv(f'{data_dir}/XAUUSD_{tf}.csv')
    df = df.sort_values('time').reset_index(drop=True)
    df['open_time'] = df['time'].astype(np.int64)
    df['close_time'] = df['open_time'] + TF_SECONDS[tf]
    return df


def _htf_indicator_frame(htf, tf_name):
    """
    روی داده‌های خام یک تایم‌فریم بالا، مجموعه‌ای از اندیکاتورهای واقعی می‌سازد.
    همهٔ اندیکاتورها فقط از گذشتهٔ همان تایم‌فریم استفاده می‌کنند (no look-ahead).
    خروجی: DataFrame با ستون close_time + featureهای پیشونددار با tf_name.
    """
    c, h, l, o = htf['close'], htf['high'], htf['low'], htf['open']
    out = pd.DataFrame()
    out['close_time'] = htf['close_time'].values

    p = tf_name  # پیشوند، مثلاً 'h1'

    # --- روند: فاصله از EMAها (نرمال‌شده) ---
    ema20 = ind.ema(c, 20)
    ema50 = ind.ema(c, 50)
    ema200 = ind.ema(c, 200)
    out[f'{p}_dist_ema20'] = ((c - ema20) / ema20).values
    out[f'{p}_dist_ema50'] = ((c - ema50) / ema50).values
    out[f'{p}_dist_ema200'] = ((c - ema200) / ema200).values
    out[f'{p}_ema_stack'] = ((ema20 > ema50) & (ema50 > ema200)).astype(float).values  # چیدمان صعودی
    out[f'{p}_above_ema200'] = (c > ema200).astype(float).values

    # --- شیب (جهت روند HTF) ---
    out[f'{p}_slope20'] = (ind.rolling_slope(c, 20) / c).values

    # --- مومنتوم ---
    out[f'{p}_rsi14'] = ind.rsi(c, 14).values
    for k in [1, 3, 6]:
        out[f'{p}_ret{k}'] = c.pct_change(k).values

    # --- قدرت روند (ADX) و جهت DI ---
    adx_, pdi, mdi = ind.adx(htf, 14)
    out[f'{p}_adx'] = adx_.values
    out[f'{p}_di_diff'] = (pdi - mdi).values

    # --- نوسان تایم‌فریم بالا ---
    atr_h = ind.atr(htf, 14)
    out[f'{p}_atr_pct'] = (atr_h / c).values
    atr_ma = atr_h.rolling(50).mean()
    out[f'{p}_atr_ratio'] = (atr_h / atr_ma).values  # فشردگی/انبساط در HTF

    # --- موقعیت close در رنج آخرین کندل HTF بسته‌شده (بستن قوی/ضعیف) ---
    rng = (h - l).replace(0, np.nan)
    out[f'{p}_close_pos'] = ((c - l) / rng).values
    out[f'{p}_body_dir'] = np.sign((c - o).values)  # جهت بدنهٔ کندل HTF

    # --- بولینگر HTF (موقعیت نسبی) ---
    lo_b, mid_b, up_b = ind.bollinger(c, 20, 2.0)
    width = (up_b - lo_b).replace(0, np.nan)
    out[f'{p}_bb_pos'] = ((c - lo_b) / width).values

    # --- فاصله از high/low اخیر HTF بر حسب ATR (سطوح کلیدی HTF) ---
    hh = h.rolling(20).max()
    ll = l.rolling(20).min()
    out[f'{p}_dist_hi20_atr'] = ((hh - c) / atr_h).values   # فاصله تا سقف ۲۰-کندلی HTF
    out[f'{p}_dist_lo20_atr'] = ((c - ll) / atr_h).values   # فاصله تا کف ۲۰-کندلی HTF

    return out


def build_mtf_features(base_df, tfs=('M30', 'H1', 'H4', 'D1', 'W1'), data_dir='data'):
    """
    برای دیتافریم پایه (M15) featureهای MTF واقعی و بدون look-ahead می‌سازد.

    base_df باید ستون 'time' (open_time بر حسب unix seconds) داشته باشد.
    خروجی: DataFrame هم‌طول و هم‌ایندکس base_df، فقط شامل ستون‌های MTF.

    منطق no-look-ahead:
      - featureهای HTF به close_time کندل HTF مُهر می‌شوند.
      - merge_asof(base.time, htf.close_time, direction='backward')
        ⇒ برای هر کندل M15 که در زمان t باز می‌شود، آخرین کندل HTF که
        close_time <= t دارد انتخاب می‌شود (کندل کاملاً بسته‌شده).
    """
    base = base_df[['time']].copy().reset_index(drop=True)
    base['time'] = base['time'].astype(np.int64)
    base['_row'] = np.arange(len(base))
    # merge_asof نیازمند مرتب‌سازی کلید است
    base_sorted = base.sort_values('time').reset_index(drop=True)

    name_map = {'M30': 'm30', 'H1': 'h1', 'H4': 'h4', 'D1': 'd1', 'W1': 'w1', 'M5': 'm5'}

    merged = base_sorted[['time', '_row']].copy()
    for tf in tfs:
        htf = load_tf(tf, data_dir)
        feat = _htf_indicator_frame(htf, name_map[tf])
        feat = feat.sort_values('close_time').reset_index(drop=True)
        merged = pd.merge_asof(
            merged, feat,
            left_on='time', right_on='close_time',
            direction='backward'
        )
        if 'close_time' in merged.columns:
            merged = merged.drop(columns=['close_time'])

    # بازگرداندن به ترتیب اصلی base_df
    merged = merged.sort_values('_row').reset_index(drop=True)
    merged = merged.drop(columns=['time', '_row'])
    merged.index = base_df.index
    return merged


def add_alignment_features(mtf_df, tfs=('m30', 'h1', 'h4', 'd1', 'w1')):
    """
    featureهای «هم‌راستایی چند-تایم‌فریمی» را از روی ستون‌های MTF موجود می‌سازد.
    این‌ها مستقیماً هندسهٔ همزمانی روند را کمی می‌کنند (برای P40 — گیت فرکانس).

    خروجی: همان mtf_df به‌علاوهٔ چند ستون alignment.
    """
    out = mtf_df.copy()

    # علامت روند هر TF: بالای EMA200 = +1، پایین = -1 (از dist_ema200)
    signs = []
    for p in tfs:
        col = f'{p}_dist_ema200'
        if col in out.columns:
            signs.append(np.sign(out[col].values))
    if signs:
        S = np.vstack(signs)  # (n_tf, n_rows)
        # مجموع علامت‌دار: چند تایم‌فریم صعودی منهای نزولی
        out['mtf_align_sum'] = np.nansum(S, axis=0)
        # نسبت هم‌جهت بودن (قدر مطلق میانگین): 1 = کاملاً هم‌راستا، 0 = پراکنده
        out['mtf_align_strength'] = np.abs(np.nanmean(S, axis=0))
        # شمار تایم‌فریم‌های صعودی (برای گیت K)
        out['mtf_n_bull'] = np.nansum(S > 0, axis=0)

    # هم‌راستایی چیدمان EMA (ema_stack) در تایم‌فریم‌ها
    stacks = []
    for p in tfs:
        col = f'{p}_ema_stack'
        if col in out.columns:
            stacks.append(out[col].values)
    if stacks:
        out['mtf_stack_sum'] = np.nansum(np.vstack(stacks), axis=0)

    return out


if __name__ == '__main__':
    # تست سریع: ساخت featureها روی M15 و بررسی عدم نشت
    import sys
    sys.path.insert(0, 'engine')
    base = pd.read_csv('data/XAUUSD_M15.csv').sort_values('time').reset_index(drop=True)
    mtf = build_mtf_features(base)
    mtf = add_alignment_features(mtf)
    print(f"M15 rows: {len(base)}, MTF feature cols: {mtf.shape[1]}")
    print("ستون‌ها:", list(mtf.columns))
    # درصد NaN در ابتدای سری (به‌خاطر warmup اندیکاتورهای HTF)
    print("NaN در ردیف اول:", int(mtf.iloc[0].isna().sum()), "/", mtf.shape[1])
    print("NaN در ردیف آخر:", int(mtf.iloc[-1].isna().sum()), "/", mtf.shape[1])
