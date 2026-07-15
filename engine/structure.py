"""
ماژول ساختار قیمت (Price Action / Market Structure)
====================================================
پیاده‌سازی مفاهیمی که تریدرهای واقعی استفاده می‌کنند:
- Pivot High / Pivot Low (نقاط چرخش سوئینگ)
- سطوح حمایت و مقاومت افقی (Support / Resistance)
- خطوط روند (Trendlines)

نکته حیاتی (بدون look-ahead bias):
یک pivot با پارامتر (left, right) فقط زمانی «تأیید» می‌شود که `right` کندل
بعد از آن گذشته باشد. بنابراین سطحی که در کندل i تشکیل می‌شود، تنها از کندل
i+right به بعد قابل استفاده در تصمیم‌گیری است. تمام توابع این قید را رعایت می‌کنند.
"""
import numpy as np
import pandas as pd
from numba import njit


@njit(cache=True)
def _pivots(high, low, left, right):
    """
    برمی‌گرداند دو آرایه:
      ph_conf_idx[i] = اندیس کندلی که pivot-high در آن *تأیید* شد (یا -1)
      pl_conf_idx[i] = مشابه برای pivot-low
    خروجی دیگر: مقدار قیمت pivot در همان اندیس تأیید.
    یک pivot-high در کندل p یعنی high[p] >= همه‌ی high در [p-left, p+right].
    تأیید در کندل p+right اتفاق می‌افتد (اولین لحظه‌ای که کل پنجره راست دیده شده).
    """
    n = len(high)
    ph_price = np.full(n, np.nan)   # قیمت pivot-high تأییدشده در این کندل
    pl_price = np.full(n, np.nan)
    ph_bar = np.full(n, -1)         # اندیس کندلِ خودِ pivot
    pl_bar = np.full(n, -1)
    for p in range(left, n - right):
        hv = high[p]
        is_ph = True
        for k in range(p - left, p + right + 1):
            if k == p:
                continue
            if high[k] > hv:
                is_ph = False
                break
        if is_ph:
            conf = p + right
            ph_price[conf] = hv
            ph_bar[conf] = p
        lv = low[p]
        is_pl = True
        for k in range(p - left, p + right + 1):
            if k == p:
                continue
            if low[k] < lv:
                is_pl = False
                break
        if is_pl:
            conf = p + right
            pl_price[conf] = lv
            pl_bar[conf] = p
    return ph_price, pl_price, ph_bar, pl_bar


def pivots(df, left=5, right=5):
    """DataFrame با ستون‌های pivot تأییدشده (بدون look-ahead)."""
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    ph_price, pl_price, ph_bar, pl_bar = _pivots(high, low, left, right)
    out = pd.DataFrame(index=df.index)
    out['ph_price'] = ph_price   # مقاومت جدید تأییدشده در این کندل
    out['pl_price'] = pl_price   # حمایت جدید تأییدشده در این کندل
    out['ph_bar'] = ph_bar
    out['pl_bar'] = pl_bar
    return out


@njit(cache=True)
def _active_levels(ph_price, pl_price, close, tol, max_levels, expiry):
    """
    برای هر کندل i، نزدیک‌ترین سطح مقاومت بالای قیمت و نزدیک‌ترین حمایت زیر قیمت
    را از میان سطوح تأییدشده‌ی اخیر برمی‌گرداند.
    tol      : تلورانس ادغام سطوح نزدیک (نسبی، مثلا 0.0008)
    expiry   : یک سطح بعد از این تعداد کندل منقضی می‌شود
    خروجی: res_level[i], sup_level[i], و شمار برخوردها res_touch[i]/sup_touch[i]
    """
    n = len(close)
    res_level = np.full(n, np.nan)
    sup_level = np.full(n, np.nan)
    res_age = np.full(n, np.nan)
    sup_age = np.full(n, np.nan)

    # نگهدارنده‌ی سطوح فعال: قیمت، آخرین کندل، تعداد برخورد
    lv_price = np.zeros(max_levels)
    lv_last = np.zeros(max_levels, dtype=np.int64)
    lv_active = np.zeros(max_levels, dtype=np.int64)  # 1=مقاومت,-1=حمایت,0=خالی
    lv_born = np.zeros(max_levels, dtype=np.int64)

    for i in range(n):
        # افزودن سطح جدید مقاومت
        rp = ph_price[i]
        if not np.isnan(rp):
            # ادغام با سطح مشابه یا افزودن به اولین جای خالی
            merged = False
            for s in range(max_levels):
                if lv_active[s] != 0 and abs(lv_price[s] - rp) / rp < tol:
                    lv_price[s] = rp
                    lv_last[s] = i
                    lv_active[s] = 1
                    merged = True
                    break
            if not merged:
                slot = -1
                for s in range(max_levels):
                    if lv_active[s] == 0:
                        slot = s
                        break
                if slot == -1:
                    # جایگزینی قدیمی‌ترین
                    oldest = 0
                    for s in range(1, max_levels):
                        if lv_last[s] < lv_last[oldest]:
                            oldest = s
                    slot = oldest
                lv_price[slot] = rp
                lv_last[slot] = i
                lv_born[slot] = i
                lv_active[slot] = 1

        lp = pl_price[i]
        if not np.isnan(lp):
            merged = False
            for s in range(max_levels):
                if lv_active[s] != 0 and abs(lv_price[s] - lp) / lp < tol:
                    lv_price[s] = lp
                    lv_last[s] = i
                    lv_active[s] = -1
                    merged = True
                    break
            if not merged:
                slot = -1
                for s in range(max_levels):
                    if lv_active[s] == 0:
                        slot = s
                        break
                if slot == -1:
                    oldest = 0
                    for s in range(1, max_levels):
                        if lv_last[s] < lv_last[oldest]:
                            oldest = s
                    slot = oldest
                lv_price[slot] = lp
                lv_last[slot] = i
                lv_born[slot] = i
                lv_active[slot] = -1

        # منقضی کردن سطوح قدیمی
        for s in range(max_levels):
            if lv_active[s] != 0 and (i - lv_last[s]) > expiry:
                lv_active[s] = 0

        # یافتن نزدیک‌ترین مقاومت بالای close و حمایت زیر close
        cpx = close[i]
        best_res = np.nan
        best_res_age = np.nan
        best_sup = np.nan
        best_sup_age = np.nan
        for s in range(max_levels):
            if lv_active[s] == 0:
                continue
            pxs = lv_price[s]
            if pxs >= cpx:
                if np.isnan(best_res) or pxs < best_res:
                    best_res = pxs
                    best_res_age = i - lv_born[s]
            else:
                if np.isnan(best_sup) or pxs > best_sup:
                    best_sup = pxs
                    best_sup_age = i - lv_born[s]
        res_level[i] = best_res
        sup_level[i] = best_sup
        res_age[i] = best_res_age
        sup_age[i] = best_sup_age
    return res_level, sup_level, res_age, sup_age


def sr_levels(df, piv, tol=0.0008, max_levels=40, expiry=1500):
    """نزدیک‌ترین حمایت/مقاومت فعال برای هر کندل (بدون look-ahead)."""
    close = df['close'].values.astype(np.float64)
    ph = piv['ph_price'].values.astype(np.float64)
    pl = piv['pl_price'].values.astype(np.float64)
    res, sup, res_age, sup_age = _active_levels(ph, pl, close, tol, max_levels, expiry)
    out = pd.DataFrame(index=df.index)
    out['resistance'] = res
    out['support'] = sup
    out['res_age'] = res_age
    out['sup_age'] = sup_age
    return out
