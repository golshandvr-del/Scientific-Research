# -*- coding: utf-8 -*-
"""
ماژولِ Ichimoku Kinko Hyo (ابرِ ایچیموکو) — پیاده‌سازیِ forward-safe و بدونِ look-ahead.
================================================================================
مرجع علمی: Goichi Hosoda (一目均衡表), 1969. سیستمِ کاملِ «تعادلِ یک-نگاهی».

مؤلفه‌ها:
  Tenkan-sen  (خطِ تبدیل)  = (HH(9)  + LL(9))  / 2
  Kijun-sen   (خطِ پایه)   = (HH(26) + LL(26)) / 2
  Senkou A    (لبهٔ ۱ ابر) = (Tenkan + Kijun)/2 ، شیفتِ +26 به جلو
  Senkou B    (لبهٔ ۲ ابر) = (HH(52) + LL(52))/2 ، شیفتِ +26 به جلو
  Kumo (ابر)  = ناحیهٔ بینِ Senkou A و Senkou B
  Chikou      = close ، شیفتِ −26 به عقب  (برای سیگنال استفاده نمی‌شود؛ look-behind دارد)

⚠️ نکتهٔ forward-safe:
  ابرِ قابل‌مشاهده در کندلِ i (Senkou A/B که به i شیفت شده‌اند) از دادهٔ کندلِ i-26 ساخته شده.
  پس هیچ look-ahead ندارد؛ در کندلِ i مجاز به استفاده است.
  Senkou "future" (لبهٔ ابری که ۲۶ کندل جلوترِ i کشیده می‌شود) از دادهٔ i ساخته می‌شود
  ⇒ برای «رنگِ آیندهٔ ابر» می‌توان از مقایسهٔ span_a_raw[i] و span_b_raw[i] استفاده کرد (بدونِ شیفت)،
  که کاملاً forward-safe است (فقط دادهٔ تا i را می‌بیند).
"""
import numpy as np
import pandas as pd


def ichimoku(df, tenkan=9, kijun=26, senkou_b=52, shift=26):
    """
    خروجی: dict از آرایه‌های numpy هم‌طول با df، همه forward-safe (بدون look-ahead).
      tenkan, kijun                 : خطوطِ جاری
      span_a, span_b                : لبه‌های ابرِ *قابل‌مشاهده در i* (شیفت‌شده از i-shift) — مجاز
      span_a_fut, span_b_fut        : لبه‌های خام (بدون شیفت) = ابری که برای i+shift کشیده می‌شود
                                       ⇒ فقط از دادهٔ تا i ساخته شده، پس مجاز برای «رنگِ آیندهٔ ابر»
      cloud_top, cloud_bot          : سقف/کفِ ابرِ قابل‌مشاهده در i
    """
    high = df['high'].values.astype(np.float64)
    low  = df['low'].values.astype(np.float64)
    n = len(df)

    def hh(period):
        return pd.Series(high).rolling(period).max().values

    def ll(period):
        return pd.Series(low).rolling(period).min().values

    tenkan_line = (hh(tenkan) + ll(tenkan)) / 2.0
    kijun_line  = (hh(kijun)  + ll(kijun))  / 2.0

    # لبه‌های خامِ ابر (بدون شیفت) — ساخته‌شده از دادهٔ تا i:
    span_a_raw = (tenkan_line + kijun_line) / 2.0
    span_b_raw = (hh(senkou_b) + ll(senkou_b)) / 2.0

    # ابرِ *قابل‌مشاهده در i* = لبه‌های خامِ i-shift (شیفت به جلو):
    span_a = np.full(n, np.nan)
    span_b = np.full(n, np.nan)
    span_a[shift:] = span_a_raw[:n - shift]
    span_b[shift:] = span_b_raw[:n - shift]

    cloud_top = np.nanmax(np.column_stack([span_a, span_b]), axis=1)
    cloud_bot = np.nanmin(np.column_stack([span_a, span_b]), axis=1)

    return dict(
        tenkan=tenkan_line,
        kijun=kijun_line,
        span_a=span_a,          # لبهٔ ابرِ جاری (forward-safe)
        span_b=span_b,
        span_a_fut=span_a_raw,  # رنگِ آیندهٔ ابر (forward-safe: فقط دادهٔ تا i)
        span_b_fut=span_b_raw,
        cloud_top=cloud_top,
        cloud_bot=cloud_bot,
    )


def cloud_signals(df, close_col='close', **kw):
    """
    نشانه‌های خامِ Ichimoku (همه forward-safe):
      above_cloud  : close بالای سقفِ ابر (روندِ صعودی تأییدشده)
      below_cloud  : close زیرِ کفِ ابر  (روندِ نزولی تأییدشده)
      in_cloud     : close داخلِ ابر (بی‌روند / ناحیهٔ تعادل)
      tk_bull/bear : تقاطعِ Tenkan/Kijun (مومنتومِ کوتاه‌مدت)
      cloud_bull_fut/bear_fut : رنگِ ابرِ آینده (span_a_fut vs span_b_fut)
      cloud_thick_atr : ضخامتِ ابر بر حسبِ ATR (شدتِ حمایت/مقاومت)
    """
    ich = ichimoku(df, **kw)
    close = df[close_col].values.astype(np.float64)
    ct, cb = ich['cloud_top'], ich['cloud_bot']

    above = close > ct
    below = close < cb
    inside = (~above) & (~below) & np.isfinite(ct)

    tk_diff = ich['tenkan'] - ich['kijun']
    tk_bull = (tk_diff > 0)
    tk_bear = (tk_diff < 0)

    cloud_bull_fut = ich['span_a_fut'] > ich['span_b_fut']
    cloud_bear_fut = ich['span_a_fut'] < ich['span_b_fut']

    thickness = np.abs(ich['span_a'] - ich['span_b'])

    return dict(
        above_cloud=above, below_cloud=below, in_cloud=inside,
        tk_bull=tk_bull, tk_bear=tk_bear,
        cloud_bull_fut=cloud_bull_fut, cloud_bear_fut=cloud_bear_fut,
        cloud_thickness=thickness,
        tenkan=ich['tenkan'], kijun=ich['kijun'],
        cloud_top=ct, cloud_bot=cb,
    )
