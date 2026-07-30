# -*- coding: utf-8 -*-
"""
S346 — «کانالِ ATR تطبیقی» (mladen 2018) → لایه‌ی fade/breakout روی XAUUSD و EURUSD
================================================================================
منبعِ ایده: `Telegram-Resource/telegram_source_1/Adaptive ATR channel.mq5`
(سورسِ بازِ MT5، mladen 2018). تحلیلِ منبع در فایلِ md همان پوشه.

هدفِ این نشست (User Note): لایه‌ای با **N بالا / تعدادِ معاملهٔ زیاد** که با این‌حال
هر ۶ دروازهٔ RQS+ را پاس کند.

--------------------------------------------------------------------------------
منطقِ ریاضیِ منبع (verbatim از سورسِ mq5 — بدونِ look-ahead)
--------------------------------------------------------------------------------
۱) Efficiency Ratio (Kaufman):
      signal = |price[i] − price[i−p]|
      noise  = Σ_{k=0..p−1} |price[i−k] − price[i−k−1]|
      ER     = signal / noise            (۰ = رنجِ پرنویز ، ۱ = روندِ خالص)
۲) دورهٔ هموارسازیِ تطبیقی:
      fastEnd = p/2 ، slowEnd = p*5
      avgPeriod = ER·(slowEnd − fastEnd) + fastEnd
      α = 2/(1 + avgPeriod)
۳) خطِ میانی و کانال — **هر دو با همان α نفس می‌کشند** (نکتهٔ کلیدیِ منبع):
      val[i] = val[i−1] + α·(price[i] − val[i−1])          (EMA تطبیقی ≈ KAMA)
      atr[i] = atr[i−1] + α·((high[i] − low[i]) − atr[i−1]) (ATR تطبیقی)
      chanUp = val + mult·atr   ،   chanDn = val − mult·atr

⚠️ تفاوتِ ماهویِ این ابزار با Bollinger/Keltner: در Bollinger پهنای کانال با یک دورهٔ
*ثابت* حساب می‌شود؛ اینجا **سرعتِ به‌روزرسانیِ خودِ پهنا** تابعِ کیفیتِ روند (ER) است.
در رنج (ER→۰) کانال «فراموش‌کارِ کند» و پهن می‌شود، در روند (ER→۱) چابک و باریک.

--------------------------------------------------------------------------------
دو ترجمهٔ بک‌تست‌پذیر (هر دو آزموده می‌شوند — رفعِ اشتباهِ رایج #۱/#۲)
--------------------------------------------------------------------------------
FADE      : بستنِ کندل بیرونِ کانال در **رژیمِ رنج** (ER پایین) ⇒ بازگشت به میانه.
            (close ≤ chanDn ⇒ LONG   ،  close ≥ chanUp ⇒ SHORT)
BREAKOUT  : بستنِ کندل بیرونِ کانال در **رژیمِ روندی** (ER بالا) ⇒ ادامهٔ حرکت.
            (close ≥ chanUp ⇒ LONG   ،  close ≤ chanDn ⇒ SHORT)

قانونِ «همه‌چیز شناور است»: SL/TP **ثابت نیستند**؛ ضریبی از همان `atr_adaptive`
کندلِ سیگنال‌اند ⇒ در هر TF و هر رژیمِ نوسان خودشان را تنظیم می‌کنند.

هیچ look-ahead: تصمیمِ کندلِ i فقط از داده‌ی تا i؛ ورود در open کندلِ i+1
(اجرای ورود توسطِ `scalp_engine.simulate_trades`).
"""
import numpy as np
import pandas as pd


# ------------------------------------------------------------------------------
# ۱. هستهٔ ریاضی — کانالِ ATR تطبیقی (پورتِ وفادارِ سورسِ mq5)
# ------------------------------------------------------------------------------
def typical_price(df):
    return (df['high'].values + df['low'].values + df['close'].values) / 3.0


def efficiency_ratio(price, p):
    """ER کافمن — برداری و causal (O(n))."""
    price = np.asarray(price, dtype=np.float64)
    n = len(price)
    d = np.abs(np.diff(price, prepend=price[0]))          # |Δ| گام‌به‌گام
    csum = np.cumsum(d)
    noise = np.full(n, np.nan)
    noise[p:] = csum[p:] - csum[:-p]
    sig = np.full(n, np.nan)
    sig[p:] = np.abs(price[p:] - price[:-p])
    with np.errstate(divide='ignore', invalid='ignore'):
        er = np.where((noise > 0) & np.isfinite(noise), sig / noise, 0.0)
    er[:p] = np.nan
    return er


def adaptive_channel(df, p=21, mult=1.618):
    """
    خروجی: dict با کلیدهای val, atr_a, up, dn, er, avg_period — همه هم‌طولِ df و causal.
    """
    price = typical_price(df)
    hi = df['high'].values.astype(np.float64)
    lo = df['low'].values.astype(np.float64)
    n = len(price)

    er = efficiency_ratio(price, p)
    fast_end = p / 2.0
    slow_end = p * 5.0
    avg_period = np.where(np.isfinite(er), er * (slow_end - fast_end) + fast_end, slow_end)
    alpha = 2.0 / (1.0 + avg_period)

    val = np.full(n, np.nan)
    atr_a = np.full(n, np.nan)
    # مقدارِ اولیه = همان کندل (مثلِ سورس که val[i]=price هنگام نبودِ prev)
    val[0] = price[0]
    atr_a[0] = hi[0] - lo[0]
    for i in range(1, n):
        a = alpha[i]
        if not np.isfinite(a):
            a = 2.0 / (1.0 + slow_end)
        val[i] = val[i - 1] + a * (price[i] - val[i - 1])
        atr_a[i] = atr_a[i - 1] + a * ((hi[i] - lo[i]) - atr_a[i - 1])

    up = val + mult * atr_a
    dn = val - mult * atr_a
    return dict(val=val, atr_a=atr_a, up=up, dn=dn, er=er, avg_period=avg_period)


# ------------------------------------------------------------------------------
# ۲. ساختِ سیگنال
# ------------------------------------------------------------------------------
def build_signals(df, mode='fade', p=21, mult=1.618, er_thr=0.236,
                  sl_k=1.618, tp_k=2.058, min_sl_pip=None, pip=0.10,
                  require_reentry=False, extra_gate=None, warmup=None):
    """
    mode='fade'     : close بیرونِ کانال + ER < er_thr  ⇒ معاملهٔ بازگشتی به میانه
    mode='breakout' : close بیرونِ کانال + ER > er_thr  ⇒ معاملهٔ ادامهٔ روند

    require_reentry : اگر True، یک کندل تأخیر برای تأییدِ برگشت به داخلِ کانال
                      (کندلِ i−1 بیرون بود و کندلِ i برگشته داخل) — نسخهٔ محتاط‌ترِ fade.
    extra_gate      : آرایهٔ بولینِ هم‌طولِ df (فیلترِ بهبود) یا None.
    خروجی: long_sig, short_sig, sl_pip[], tp_pip[], ch (dict کانال)
    """
    ch = adaptive_channel(df, p=p, mult=mult)
    c = df['close'].values.astype(np.float64)
    n = len(c)
    up, dn, er, atr_a = ch['up'], ch['dn'], ch['er'], ch['atr_a']

    out_up = c >= up          # بستن بیرونِ سقفِ کانال
    out_dn = c <= dn          # بستن بیرونِ کفِ کانال

    if require_reentry:
        prev_up = np.roll(out_up, 1); prev_up[0] = False
        prev_dn = np.roll(out_dn, 1); prev_dn[0] = False
        trig_up = prev_up & (~out_up)      # بیرونِ سقف بود، برگشت داخل
        trig_dn = prev_dn & (~out_dn)
    else:
        trig_up, trig_dn = out_up, out_dn

    if mode == 'fade':
        regime = er < er_thr
        long_sig = trig_dn & regime
        short_sig = trig_up & regime
    elif mode == 'breakout':
        regime = er > er_thr
        long_sig = trig_up & regime
        short_sig = trig_dn & regime
    else:
        raise ValueError('mode must be fade|breakout')

    valid = np.isfinite(er) & np.isfinite(atr_a) & (atr_a > 0)
    if warmup is None:
        warmup = max(5 * p, 200)
    valid[:warmup] = False
    long_sig = long_sig & valid
    short_sig = short_sig & valid

    if extra_gate is not None:
        g = np.asarray(extra_gate, dtype=bool)
        long_sig = long_sig & g
        short_sig = short_sig & g

    # SL/TP شناور = ضریبی از ATRِ تطبیقیِ همان کندل (بر حسبِ pip)
    with np.errstate(invalid='ignore'):
        sl_pip = sl_k * atr_a / pip
        tp_pip = tp_k * atr_a / pip
    sl_pip = np.nan_to_num(sl_pip, nan=0.0)
    tp_pip = np.nan_to_num(tp_pip, nan=0.0)
    if min_sl_pip is not None:
        sl_pip = np.maximum(sl_pip, min_sl_pip)
        tp_pip = np.maximum(tp_pip, min_sl_pip * (tp_k / sl_k))

    return long_sig, short_sig, sl_pip, tp_pip, ch
