# -*- coding: utf-8 -*-
"""
S351 — «شکستِ ساختارِ لگ-متناسب» (Leg-Proportional Structure Break · LPSB)
================================================================================
منبعِ ایده: `Telegram-Resource/telegram_source_1/Market_Structure_Break_and_Order_Block_v3/
             Market_Structure_Break_and_Order_Block_v3@free_fx_pro.mq4`  (GNU GPL)

--------------------------------------------------------------------------------
۰. چه چیزی از سورس استخراج شد (و چه چیزی عمداً کنار گذاشته شد)
--------------------------------------------------------------------------------
کدِ اصلی ۵٬۳۷۹ خط است ولی هستهٔ منطقش **یک خط** است (خطِ ۴۸۰۰ سورس):

    market = (l0==last_l0 || h0==last_h0) ? market
           : (market==+1 && l0<l1 && l0 < l1 − |h0−l1|·f) ? −1
           : (market==−1 && h0>h1 && h0 > h1 + |h1−l0|·f) ? +1 : market

با `ZigZag Length = 9` و `Fib Factor = 0.33`. یعنی:

  ⭐ **ساختارِ بازار فقط وقتی شکسته اعلام می‌شود که سوئینگِ نو، سوئینگِ قبلی را
     به اندازهٔ کسری از دامنهٔ لگِ ساختاریِ قبلی رد کند.**

و این‌جا نکتهٔ ریاضیِ ظریفی هست که ارزشِ تحقیقاتیِ این منبع را می‌سازد:
آستانهٔ شکست به **دامنهٔ خودِ لگِ ساختاری** نرمال می‌شود، **نه به ATR**. یعنی
یک سنجهٔ **خود-متشابهِ (self-similar) فراکتالی**، در برابرِ نرمال‌سازیِ
**آماریِ** نوسان که کلِ خانوادهٔ `S346` پروژه رویش بنا شده بود. نرمال‌کنندهٔ
متفاوت ⇒ امکانِ لبهٔ واقعاً نو (نه فقط همپوشانی). این را باید **اندازه گرفت**،
نه ادعا کرد — و همین کارِ این ماژول است.

⛔ **چه چیزی کنار گذاشته شد و چرا:** نسخهٔ MT4 صریحاً **repaint** دارد؛ پیوت‌ها
از `pos + zigzag_len` خوانده می‌شوند (`HighestHighStream`/`LowestLowStream` روی
پنجرهٔ متقارن) که **نگاه به آینده** است. پس پورتِ verbatim ممنوع است. بازسازیِ
این ماژول **علّی (causal)** است: پیوت در کندلِ `j` تنها در کندلِ `j+L` تأیید
می‌شود، و ماشهٔ ورود فقط از پیوت‌های **از پیش تأییدشده** ساخته می‌شود.

--------------------------------------------------------------------------------
۱. قانونِ علّیِ لایه (بدونِ هیچ look-ahead)
--------------------------------------------------------------------------------
پیوتِ فراکتالِ متقارنِ نیم‌پنجره `L`:
    سوئینگ‌بالا در j  ⇐  high[j] == max(high[j−L .. j+L])   → **در j+L تأیید می‌شود**
    سوئینگ‌پایین در j ⇐  low[j]  == min(low[j−L .. j+L])    → **در j+L تأیید می‌شود**

در هر کندلِ `i` تنها از پیوت‌هایی استفاده می‌شود که `تأیید ≤ i` دارند:
    H_ref = آخرین سوئینگ‌بالای تأییدشده  ،  L_ref = آخرین سوئینگ‌پایینِ تأییدشده
    leg   = H_ref − L_ref                (> 0 اجباری)

    سطحِ شکستِ صعودی :  up_lvl   = H_ref + f · leg
    سطحِ شکستِ نزولی :  down_lvl = L_ref − f · leg

    ماشهٔ لانگ  در i ⇐ close[i] > up_lvl   و  close[i−1] ≤ up_lvl     (گذارِ تازه)
    ماشهٔ شورت  در i ⇐ close[i] < down_lvl و  close[i−1] ≥ down_lvl

ورود در `open` کندلِ `i+1` (همان قاعدهٔ موتورِ پروژه). شرطِ «گذارِ تازه» معادلِ
سپرِ `last_l0==l0 || last_h0==h0`ِ سورس است: از شمارشِ چندبارهٔ یک شکستِ واحد
جلوگیری می‌کند.

--------------------------------------------------------------------------------
۲. خانوادهٔ **پیش‌ثبت‌شده** — راهِ مشروعِ عبور از H5
--------------------------------------------------------------------------------
طبق §۲.۵ سندِ `RQS2_SPEC.md`: جریمهٔ چندگانگی بهایِ **انتخابِ** بهترینِ N است؛
اگر هیچ عضوی انتخاب نشود، `N = 1`. پس آمارهٔ آزمون = **میانگینِ همهٔ اعضا**.

    L ∈ {5, 8, 13}          ← ۸ همسایهٔ فیبوناچیِ عددِ ۹ سازنده (و ۵/۱۳ دو طرفش)
    f ∈ {0.236, 0.33, 0.5}  ← ۰.۳۳ سازنده + دو ترازِ فیبوناچیِ ۲۳.۶٪ و ۵۰٪
    ⇒ ۹ عضو، هیچ‌کدام گزینش نمی‌شوند.

هندسه **منجمد و یکسان برای همهٔ اعضا** است تا این آزمایش «مهارتِ سیگنال» را
بسنجد نه هندسه را — چون `S350` اندازه گرفت که هندسه `z_obs` را تکان نمی‌دهد،
پس گشتن در هندسه اتلافِ درجهٔ آزادی و بهایِ چندگانگیِ بی‌فایده است.

--------------------------------------------------------------------------------
۳. هندسهٔ منجمد و **سازگار با قانونِ قفلِ سه‌گانه**
--------------------------------------------------------------------------------
`docs/FINDING_BARRIER_REACHABILITY_LAW.md`:   hold ≥ (k_sl · rr)²
انتخاب:   `k_sl = 1.618`  ،  `rr = 1.618`  ⇒  k_tp = 2.618
          hold_نظری = 2.618² = 6.854
اما §۳.۱ همان سند اندازه گرفت که نسبتِ تجربی/نظری در `k=2.618` عددِ **۱.۷۵**
است (بازار در مقیاسِ نزدیک **کم‌پخشی** است). پس:
          hold = ceil(6.854 × 1.75) = **12**   ← مشتق‌شده از قانون، جست‌وجو نشده

⛔ سپرِ اشتباهِ #۸: `rr = 1.618 > 1` ⇒ `TP > SL` ساختاراً تضمین است.

--------------------------------------------------------------------------------
۴. پوشش (قانونِ MTF) — هر ۱۵ کارت
--------------------------------------------------------------------------------
۷ کارتِ XAUUSD (M5..W1) + ۸ کارتِ EURUSD (M1..W1). طلا روی M1 داده ندارد ⇒
نقطهٔ شروعِ طلا M5 است. برای هر کارت نتیجه **جداگانه** ذخیره و چک‌پوینت می‌شود.
"""

import os
import sys
import json
import math
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from strategies.s346_fast import (barrier_outcomes,                # noqa: E402
                                  select_non_overlap, stats)

OUT = 'results/_scan_S351'

# ------------------------------ کارت‌ها (قانونِ MTF) ------------------------------
CARDS = {
    'XAUUSD-M5':  ('XAUUSD', 'data/XAUUSD_M5.csv'),
    'XAUUSD-M15': ('XAUUSD', 'data/XAUUSD_M15.csv'),
    'XAUUSD-M30': ('XAUUSD', 'data/XAUUSD_M30.csv'),
    'XAUUSD-H1':  ('XAUUSD', 'data/XAUUSD_H1.csv'),
    'XAUUSD-H4':  ('XAUUSD', 'data/XAUUSD_H4.csv'),
    'XAUUSD-D1':  ('XAUUSD', 'data/XAUUSD_D1.csv'),
    'XAUUSD-W1':  ('XAUUSD', 'data/XAUUSD_W1.csv'),
    'EURUSD-M1':  ('EURUSD', 'data/EURUSD_M1.csv'),
    'EURUSD-M5':  ('EURUSD', 'data/EURUSD_M5.csv'),
    'EURUSD-M15': ('EURUSD', 'data/EURUSD_M15.csv'),
    'EURUSD-M30': ('EURUSD', 'data/EURUSD_M30.csv'),
    'EURUSD-H1':  ('EURUSD', 'data/EURUSD_H1.csv'),
    'EURUSD-H4':  ('EURUSD', 'data/EURUSD_H4.csv'),
    'EURUSD-D1':  ('EURUSD', 'data/EURUSD_D1.csv'),
    'EURUSD-W1':  ('EURUSD', 'data/EURUSD_W1.csv'),
}

# --------------------- خانوادهٔ پیش‌ثبت‌شده (هیچ گزینشی نیست) ---------------------
L_LIST = (5, 8, 13)                 # نیم‌پنجرهٔ پیوت — فیبوناچی، حولِ ۹ سازنده
F_LIST = (0.236, 0.33, 0.5)         # فاکتورِ فیبِ تأییدِ شکست — ۰.۳۳ سازنده

# ---------------------- هندسهٔ منجمد (مشتق، جست‌وجو نشده) ----------------------
GEO_SL_K = 1.618
GEO_RR = 1.618
GEO_HOLD = 12                       # = ceil((1.618·1.618)² × 1.75) طبقِ قانونِ قفلِ سه‌گانه
ATR_P = 21                          # پنجرهٔ ATR — فیبوناچی، غیررند

SPLIT_FRAC = 0.60                   # ۶۰٪ اکتشاف / ۴۰٪ holdout (دست‌نخورده)
SEED = 351


# ==============================================================================
#                          اندیکاتورهای پایه (بدونِ look-ahead)
# ==============================================================================
def atr_series(df, p=ATR_P):
    """ATR وایلدر (RMA) — کاملاً علّی."""
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    out = np.full(len(tr), np.nan)
    if len(tr) <= p:
        return out
    acc = tr[:p].mean()
    out[p - 1] = acc
    a = 1.0 / p
    for i in range(p, len(tr)):
        acc = acc + a * (tr[i] - acc)
        out[i] = acc
    return out


def confirmed_pivots(df, L):
    """
    ⭐ هستهٔ ضدِ repaint.

    پیوتِ فراکتالِ متقارنِ نیم‌پنجرهٔ L:
        سوئینگ‌بالا در j  ⇐ high[j] == max(high[j−L .. j+L])
        سوئینگ‌پایین در j ⇐ low[j]  == min(low[j−L .. j+L])

    خروجی برای **هر کندلِ i** فقط از پیوت‌هایی ساخته می‌شود که در `j+L ≤ i`
    تأیید شده‌اند. یعنی `h_ref[i]`/`l_ref[i]` در لحظهٔ i **قابلِ دانستن** بودند.

    این دقیقاً همان چیزی است که نسخهٔ MT4 نقض می‌کرد: آن‌جا `pos+zigzag_len`
    خوانده می‌شد ⇒ پیوت پیش از تأیید در دسترس بود ⇒ repaint.
    """
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    n = len(h)
    h_ref = np.full(n, np.nan)
    l_ref = np.full(n, np.nan)
    h_bar = np.full(n, -1, dtype=np.int64)
    l_bar = np.full(n, -1, dtype=np.int64)

    # پیوت‌بودن را برداری تشخیص بده (پنجرهٔ متقارنِ 2L+1)
    w = 2 * L + 1
    if n < w + 2:
        return h_ref, l_ref, h_bar, l_bar
    # rolling max/min با stride tricks
    hs = np.lib.stride_tricks.sliding_window_view(h, w)      # shape (n-w+1, w)
    ls = np.lib.stride_tricks.sliding_window_view(l, w)
    is_ph = np.zeros(n, dtype=bool)
    is_pl = np.zeros(n, dtype=bool)
    centers = np.arange(L, n - L)
    is_ph[centers] = h[centers] >= hs.max(axis=1)
    is_pl[centers] = l[centers] <= ls.min(axis=1)

    # forward-fill با تأخیرِ تأیید: پیوتِ j در j+L در دسترس می‌آید
    cur_h, cur_hb = np.nan, -1
    cur_l, cur_lb = np.nan, -1
    for i in range(n):
        j = i - L                      # کندلی که تأییدش همین حالا کامل شد
        if j >= 0:
            if is_ph[j]:
                cur_h, cur_hb = h[j], j
            if is_pl[j]:
                cur_l, cur_lb = l[j], j
        h_ref[i], h_bar[i] = cur_h, cur_hb
        l_ref[i], l_bar[i] = cur_l, cur_lb
    return h_ref, l_ref, h_bar, l_bar


def lpsb_signals(df, L, f, warmup=None):
    """
    ماشهٔ «شکستِ ساختارِ لگ-متناسب».

    برمی‌گرداند (long_sig, short_sig, state) که `state` وضعیتِ ساختارِ بازار
    (+1 صعودی / −1 نزولی / 0 نامعلوم) در هر کندل است — این خودش یک **فیلترِ
    جهتیِ مستقل** است که در `s351_filter.py` روی لایه‌های سوخته آزموده می‌شود.
    """
    c = df['close'].values.astype(np.float64)
    n = len(c)
    h_ref, l_ref, _, _ = confirmed_pivots(df, L)
    leg = h_ref - l_ref
    ok = np.isfinite(leg) & (leg > 0)

    up_lvl = np.where(ok, h_ref + f * leg, np.nan)
    dn_lvl = np.where(ok, l_ref - f * leg, np.nan)

    cross_up = np.zeros(n, dtype=bool)
    cross_dn = np.zeros(n, dtype=bool)
    cross_up[1:] = ok[1:] & (c[1:] > up_lvl[1:]) & ~(c[:-1] > up_lvl[1:])
    cross_dn[1:] = ok[1:] & (c[1:] < dn_lvl[1:]) & ~(c[:-1] < dn_lvl[1:])

    # وضعیتِ ساختار: آخرین شکست حاکم است (ماشینِ حالت، مثلِ `market` سورس)
    state = np.zeros(n, dtype=np.int8)
    cur = 0
    for i in range(n):
        if cross_up[i]:
            cur = 1
        elif cross_dn[i]:
            cur = -1
        state[i] = cur

    if warmup is None:
        warmup = max(4 * (2 * L + 1), 250)
    cross_up[:warmup] = False
    cross_dn[:warmup] = False
    return cross_up, cross_dn, state


# ==============================================================================
#                                اجرای یک عضو
# ==============================================================================
def member_stats(df, atr, asset, L, f, hold=GEO_HOLD, sl_k=GEO_SL_K, rr=GEO_RR,
                 lo=None, hi=None):
    """
    یک عضوِ خانواده را اجرا کن.  `lo/hi` پنجرهٔ کندلیِ مجاز (اکتشاف یا holdout).
    خروجی: dict آمار + اندیس‌های سیگنالِ خالص برای مصرفِ بعدی.
    """
    cfg = se.ASSETS[asset]
    pip = float(cfg['pip'])
    spread = float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))

    ls, ss, _ = lpsb_signals(df, L, f)
    sel = ls | ss
    if lo is not None:
        sel[:lo] = False
    if hi is not None:
        sel[hi:] = False
    sig = np.where(sel & np.isfinite(atr) & (atr > 0))[0]
    if len(sig) == 0:
        return dict(n=0, wr=0.0, exp=0.0, pf=0.0, n_sig=0), sig, np.zeros(0, bool)

    is_long = ls[sig]
    sl_dist = sl_k * atr[sig]
    tp_dist = np.maximum(rr * sl_dist, sl_dist)       # سپرِ #۸: TP ≥ SL
    fo = barrier_outcomes(df, sig, is_long, sl_dist, tp_dist, hold,
                          pip, spread, slip)
    keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
    st = stats(fo['pnl_pip'][keep], fo['win'][keep], spread + 2 * slip)
    st['n_sig'] = int(len(sig))
    return st, sig, is_long


def members():
    return [dict(L=L, f=f) for L in L_LIST for f in F_LIST]
