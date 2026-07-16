"""
ماژول دادهٔ برون‌زا (Exogenous data) — گروه G.

هدف: بارگذاری DXY (شاخص دلار) و ساخت featureهای برون‌زای جهت‌دار برای XAUUSD،
با هم‌ترازسازی دقیق و **بدون نشت آینده** (no look-ahead).

پایهٔ علمی (مطالعهٔ ادبیات + نتایج قبلی پروژه):
  • طلا و DXY همبستگی معکوس قوی دارند (معمولاً زیر −0.80). پس بازده/وضعیت DXY
    یک سیگنال جهت‌دارِ *برون‌زا* برای طلاست — چیزی که از خودِ OHLCV طلا درنمی‌آید.
  • «شکست قاعدهٔ معکوس» (divergence) خودش یک سیگنال رژیم است.
  • همبستگی و بتای غلتان، شدت و پایداری این رابطه را کمی می‌کنند.

قاعدهٔ طلایی هم‌ترازسازی (L5/L6 پروژه):
  برای هر کندل XAU در زمان t، فقط از کندل DXY استفاده می‌کنیم که close آن
  **پیش از یا هم‌زمان با t بسته شده باشد**. چون هر دو سری M15 و هم‌مرز (بستن هر
  کندل M15 در همان لحظه) هستند، از merge_asof(direction='backward') روی زمانِ
  بستهٔ کندل استفاده می‌کنیم. featureهای DXY فقط از close/بازدهِ کندل‌های
  *بسته‌شده* ساخته می‌شوند (هیچ high/low آینده‌ای دخالت ندارد).
"""
import numpy as np
import pandas as pd
import indicators as ind


def load_dxy(path='data/DXY_M15.csv'):
    """دیتافریم DXY با ستون dt (زمان بستهٔ کندل = time + 15min نیست؛ time = زمان باز کندل)."""
    d = pd.read_csv(path)
    d['dt'] = pd.to_datetime(d['time'], unit='s')
    d = d.sort_values('dt').reset_index(drop=True)
    return d


def _dxy_self_features(d):
    """featureهای درون‌سری DXY (فقط از close/بازدهِ خودِ DXY، بدون نگاه به طلا)."""
    c = d['close']
    f = pd.DataFrame(index=d.index)
    f['dxy_dt'] = d['dt']
    # بازده DXY در افق‌های مختلف — سیگنال جهت‌دار (معکوسِ طلا انتظار می‌رود)
    for p in [1, 4, 16, 96]:            # ~M15, H1, H4, D1
        f[f'dxy_ret_{p}'] = c.pct_change(p)
    # RSI و z-score وضعیت DXY
    f['dxy_rsi_14'] = ind.rsi(c, 14)
    f['dxy_zscore_50'] = ind.zscore(c, 50)
    # فاصله از EMA50 (کشش/روند DXY)
    ema50 = ind.ema(c, 50)
    f['dxy_dist_ema50'] = (c - ema50) / ema50
    # شیب کوتاه‌مدت DXY
    f['dxy_slope_20'] = ind.rolling_slope(c, 20) / c
    # موقعیت نسبت به EMA200 (رژیم بلندمدت دلار)
    ema200 = ind.ema(c, 200)
    f['dxy_above_ema200'] = (c > ema200).astype(float)
    return f


def build_exogenous_features(xau_df):
    """
    برای دیتافریم XAU (باید ستون dt داشته باشد) featureهای برون‌زای DXY را
    هم‌تراز و بدون look-ahead برمی‌گرداند (هم‌طول xau_df، NaN در ابتدا/شکاف‌ها).

    خروجی شامل:
      - featureهای درون‌سری DXY (dxy_ret_*, dxy_rsi_14, ...)
      - featureهای رابطه‌ای طلا↔DXY که پس از هم‌ترازسازی ساخته می‌شوند:
          gold_dxy_corr_N  : همبستگی غلتان بازده طلا و DXY (سنجهٔ رژیم رابطه)
          gold_dxy_beta_N  : بتای غلتان (شیب رگرسیون بازده طلا بر DXY)
          dxy_gold_divergence : آیا هر دو هم‌جهت حرکت کرده‌اند (نقض قاعدهٔ معکوس)
    """
    d = load_dxy()
    dxy_self = _dxy_self_features(d)

    left = xau_df[['dt']].copy()
    left['_row'] = np.arange(len(left))
    left = left.sort_values('dt')

    # merge_asof backward: برای هر کندل XAU، آخرین کندل DXY با dt <= dt_xau
    merged = pd.merge_asof(
        left, dxy_self.sort_values('dxy_dt'),
        left_on='dt', right_on='dxy_dt', direction='backward',
        tolerance=pd.Timedelta('2h')   # اگر DXY بیش از ۲ ساعت قدیمی بود → NaN (شکاف)
    )
    merged = merged.sort_values('_row').reset_index(drop=True)

    # ---- featureهای رابطه‌ای (نیازمند هم‌ترازیِ بازدهِ هر دو سری) ----
    # بازدهِ M15 طلا و بازدهِ هم‌تراز DXY (هر دو از کندل‌های بسته‌شده)
    gold_ret1 = xau_df['close'].pct_change().values
    dxy_ret1 = merged['dxy_ret_1'].values

    gr = pd.Series(gold_ret1)
    dr = pd.Series(dxy_ret1)
    # نکته: rolling.cov اگر هر NaN در پنجره باشد NaN می‌دهد. با min_periods
    # اجازه می‌دهیم پنجره‌های با چند نقطهٔ معتبر هم مقدار بدهند (شکاف‌های کوچک DXY
    # نباید کل feature رابطه‌ای را نابود کنند). هم‌ترازیِ زمانی از merge_asof تضمین شده.
    for N in [48, 96]:                 # ~نیم‌روز و یک‌روز کندلی
        mp = N // 2
        cov = gr.rolling(N, min_periods=mp).cov(dr)
        var_d = dr.rolling(N, min_periods=mp).var()
        var_g = gr.rolling(N, min_periods=mp).var()
        corr = cov / (np.sqrt(var_d * var_g) + 1e-12)
        beta = cov / (var_d + 1e-12)   # حساسیت بازده طلا به بازده دلار
        merged[f'gold_dxy_corr_{N}'] = corr.values
        merged[f'gold_dxy_beta_{N}'] = beta.values

    # divergence: در رابطهٔ سالمِ معکوس، sign(gold)!=sign(dxy).
    # اگر هم‌جهت شدند (نقض قاعده) → 1 (سیگنال رژیمِ ویژه/شکست همبستگی).
    # روی ردیف‌های بدون DXY، NaN می‌گذاریم (نه 0 کاذب).
    same_dir = (np.sign(gold_ret1) == np.sign(dxy_ret1)) & (gold_ret1 != 0) & (dxy_ret1 != 0)
    div = same_dir.astype(float)
    div[np.isnan(dxy_ret1) | np.isnan(gold_ret1)] = np.nan
    merged['dxy_gold_divergence'] = div

    # ستون‌های کمکی را دور می‌ریزیم
    out = merged.drop(columns=['dt', '_row', 'dxy_dt'])
    out.index = xau_df.index
    return out


def dxy_coverage_report(xau_df):
    """گزارش پوشش DXY نسبت به XAU (برای اطمینان از کیفیت هم‌ترازسازی)."""
    ex = build_exogenous_features(xau_df)
    n = len(ex)
    have = ex['dxy_ret_1'].notna().sum()
    return dict(total=n, aligned=int(have), coverage_pct=round(100 * have / n, 2))
