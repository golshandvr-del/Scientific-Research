"""
ماژول «ریبونِ چند-MA» (Multi-MA Ribbon) — پاسخ به User Note دومِ کاربر.
================================================================================
ایدهٔ کاربر (نقلِ مستقیم):
> «بعضی تریدرها از ۳ یا بیشتر MA استفاده می‌کنند... تنظیماتِ درستِ هر خط را پیدا
>  می‌کنند و از آن‌ها به‌عنوانِ خطوطِ روند، حمایت، مقاومت، و نمایشِ قدرتِ روندِ فعلی
>  بر اساسِ همگرایی یا واگراییِ خطوط استفاده می‌کنند. تکنیکِ کشفِ S/R و روند در
>  تایم‌فریمِ بالا و استفاده در تایم‌فریمِ پایین.»

این ماژول این تکنیکِ کیفی را به کمّیت‌های عددیِ **بدونِ look-ahead** تبدیل می‌کند و
طبقِ L2 پروژه (اثرِ خام → feature در ML، نه قانونِ خام) به‌صورتِ feature ارائه می‌دهد.

--------------------------------------------------------------------------------
هندسهٔ ریبون — چه چیزی را کمّی می‌کنیم؟
--------------------------------------------------------------------------------
یک «ریبون» = مجموعه‌ای از N عدد EMA با دوره‌های صعودی (مثلاً 8,13,21,34,55,89,144).
از هندسهٔ لحظه‌ایِ این خطوط سه مفهومِ گفته‌شدهٔ کاربر استخراج می‌شود:

۱. **قدرتِ روند از واگرایی/همگرایی:**
   - `ribbon_spread`  = (max(EMAها) − min(EMAها)) / price   ← واگرایی زیاد = روند قوی
   - `ribbon_width_z` = z-scoreِ spread نسبت به تاریخِ خودش  ← فشردگی (همگرایی) در برابر انبساط
۲. **جهت و «ترتیبِ صحیح» (fan / stack):**
   - `ribbon_order`   = +1 اگر EMAها کاملاً صعودی مرتب (کوتاه بالای بلند)،
                        −1 اگر کاملاً نزولی مرتب، بینِ آن‌ها کسری.
   - `ribbon_slope`   = میانگینِ شیبِ نرمال‌شدهٔ خطوط (جهتِ کلیِ ریبون)
۳. **S/R دینامیک (خطوطِ ریبون به‌مثابهٔ حمایت/مقاومت):**
   - `dist_to_ribbon_top/bottom_atr` = فاصلهٔ قیمت تا لبه‌های ریبون بر حسبِ ATR
   - `price_vs_ribbon` = موقعیتِ قیمت نسبت به ریبون (بالای همه / داخل / زیرِ همه)

روی تایم‌فریمِ بالا (H1/H4) محاسبه و با merge_asof(backward) روی زمانِ بسته‌شدن به
M15 نگاشت می‌شود (همان قاعدهٔ طلاییِ engine/mtf.py).
"""
import numpy as np
import pandas as pd
import indicators as ind

TF_SECONDS = {'M15': 15*60, 'M30': 30*60, 'H1': 60*60, 'H4': 4*3600, 'D1': 24*3600}

# دوره‌های ریبون (فیبوناچی — پرکاربردترین در بینِ تریدرها)
RIBBON_PERIODS = [8, 13, 21, 34, 55, 89, 144]


def _load_tf(tf, data_dir='data'):
    df = pd.read_csv(f'{data_dir}/XAUUSD_{tf}.csv')
    df = df.sort_values('time').drop_duplicates('time').reset_index(drop=True)
    df['open_time'] = df['time'].astype(np.int64)
    df['close_time'] = df['open_time'] + TF_SECONDS[tf]
    return df


def _ribbon_frame(htf, prefix, periods=RIBBON_PERIODS):
    """
    روی داده‌های خامِ یک تایم‌فریم، featureهای هندسهٔ ریبون را می‌سازد.
    همهٔ محاسبات فقط از گذشتهٔ همان تایم‌فریم (no look-ahead).
    خروجی: DataFrame با ستونِ close_time + featureهای پیشونددار.
    """
    c = htf['close']
    atr_h = ind.atr(htf, 14)
    out = pd.DataFrame()
    out['close_time'] = htf['close_time'].values

    emas = [ind.ema(c, p) for p in periods]
    E = np.column_stack([e.values for e in emas])       # (n, N)
    top = np.nanmax(E, axis=1)
    bot = np.nanmin(E, axis=1)
    price = c.values
    atrv = atr_h.values

    p = prefix
    # ۱) واگرایی/همگرایی (قدرتِ روند)
    spread = (top - bot) / np.where(price != 0, price, np.nan)
    out[f'{p}_rib_spread'] = spread
    sp = pd.Series(spread)
    out[f'{p}_rib_width_z'] = ((sp - sp.rolling(100).mean()) /
                               (sp.rolling(100).std() + 1e-12)).values

    # ۲) ترتیبِ صحیح (fan): چه کسری از جفت‌های مجاور به‌ترتیبِ صعودی‌اند؟
    #    EMA کوتاه باید بالای EMA بلند باشد در روندِ صعودی.
    asc = np.zeros(len(htf)); pairs = 0
    for k in range(len(periods) - 1):
        asc += (E[:, k] > E[:, k+1]).astype(float)   # کوتاه‌تر بالای بلندتر = صعودی
        pairs += 1
    frac_asc = asc / pairs                             # 1=کاملاً صعودی، 0=کاملاً نزولی
    out[f'{p}_rib_order'] = 2 * frac_asc - 1           # به [-1,+1]

    # ۳) شیبِ میانگینِ ریبون (جهت)
    slopes = []
    for e in emas:
        slopes.append((ind.rolling_slope(e, 10) / c).values)
    out[f'{p}_rib_slope'] = np.nanmean(np.column_stack(slopes), axis=1)

    # ۴) S/R دینامیک: فاصلهٔ قیمت تا لبه‌های ریبون بر حسبِ ATR
    out[f'{p}_dist_rib_top_atr'] = (top - price) / np.where(atrv != 0, atrv, np.nan)
    out[f'{p}_dist_rib_bot_atr'] = (price - bot) / np.where(atrv != 0, atrv, np.nan)

    # ۵) موقعیتِ قیمت نسبت به ریبون: +1 بالای همه، -1 زیرِ همه، بین = نسبی
    above_all = (price > top).astype(float)
    below_all = (price < bot).astype(float)
    out[f'{p}_price_vs_rib'] = above_all - below_all
    # نسبتِ نفوذِ قیمت در بدنهٔ ریبون [0..1]
    band = (top - bot)
    out[f'{p}_pos_in_rib'] = np.where(band > 1e-9, (price - bot) / band, 0.5)

    # ۶) گیتِ کیفیِ روند: ریبونِ «باز و مرتب» (روندِ سالم) در برابرِ «فشرده/درهم»
    #    روندِ صعودیِ قوی = order>~0.8 و width_z>0 (منبسط)
    order = out[f'{p}_rib_order'].values
    wz = out[f'{p}_rib_width_z'].fillna(0).values
    out[f'{p}_rib_strong_up'] = ((order >= 0.7) & (wz > 0)).astype(float)
    out[f'{p}_rib_strong_dn'] = ((order <= -0.7) & (wz > 0)).astype(float)
    return out


def build_ribbon_features(base_df, tfs=('H1', 'H4'), data_dir='data',
                          periods=RIBBON_PERIODS):
    """
    featureهای ریبونِ چند-تایم‌فریمی را هم‌طولِ base_df (M15) برمی‌گرداند.
    نگاشت با merge_asof(backward) روی close_time (بدونِ look-ahead).
    """
    base = base_df.copy().reset_index(drop=True)
    base['open_time'] = base['time'].astype(np.int64)
    left = base[['open_time']].copy()
    left['_row'] = np.arange(len(left))
    result = pd.DataFrame(index=base_df.index)

    for tf in tfs:
        try:
            htf = _load_tf(tf, data_dir)
        except FileNotFoundError:
            continue
        rf = _ribbon_frame(htf, tf.lower(), periods).sort_values('close_time')
        merged = pd.merge_asof(
            left.sort_values('open_time'), rf,
            left_on='open_time', right_on='close_time',
            direction='backward')
        merged = merged.sort_values('_row').reset_index(drop=True)
        for col in rf.columns:
            if col == 'close_time':
                continue
            result[col] = merged[col].values
    return result


def ribbon_alignment_gate(base_df, tfs=('H1', 'H4'), data_dir='data', mode='up'):
    """
    گیتِ هم‌راستاییِ ریبون در چند تایم‌فریم:
    برمی‌گرداند آرایهٔ بولین که True یعنی همهٔ tfها ریبونِ «قوی و مرتب» در جهتِ mode دارند.
    این پیاده‌سازیِ مستقیمِ توصیفِ کاربر است: «کشفِ روند در تایم‌فریمِ بالا و استفاده
    در تایم‌فریمِ پایین».
    """
    f = build_ribbon_features(base_df, tfs, data_dir)
    key = 'rib_strong_up' if mode == 'up' else 'rib_strong_dn'
    cols = [f'{tf.lower()}_{key}' for tf in tfs if f'{tf.lower()}_{key}' in f.columns]
    if not cols:
        return np.zeros(len(base_df), dtype=bool)
    agree = f[cols].fillna(0).sum(axis=1).values
    return (agree >= len(cols)).astype(bool)   # همهٔ tfها موافق
