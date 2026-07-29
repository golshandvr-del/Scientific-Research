# -*- coding: utf-8 -*-
"""
S341 — Al Brooks «Horizontal Lines: Swing Points and Other Key Price Levels»
(فصلِ ۱۷ کتابِ Trading Price Action: Trends)
================================================================================
پارادایم: RQS+ ≥ ۸۰ (نه net-profit قدیمی). سند: docs/RQS_ROBUST_QUALITY_SCORE.md

تز (نقلِ مکانیکیِ Brooks، فصل ۱۷):
- بیشترِ روزها رنج‌اند؛ خطوطِ افقی روی swing high/low قبلی مانع می‌شوند ⇒ failed breakout ⇒ reversal.
- swing-high breakout معمولاً fail می‌شود ⇒ higher-high reversal ⇒ SHORT (fade).
  swing-low  breakout معمولاً fail می‌شود ⇒ lower-low  reversal ⇒ LONG  (fade).
- «سیگنالِ دوم بهترین است»: دومین failed higher-high / lower-low اکستریم‌تر و مطمئن‌تر است.
- «میانهٔ روز مغناطیس است» ⇒ TP هدفِ بازگشت به میانه (نه یک روند بزرگ).
- ⚠️ «Don't fade strong trends»: فقط در رژیمِ رنج fade کن. در روند، fade ممنوع.

منطقِ مکانیکی (causal، بدونِ look-ahead؛ سیگنال روی کندلِ i، ورود در open کندلِ i+1):
  SHORT (failed breakout بالای swing high):
    - یک swing high در گذشته وجود دارد: پیوتِ فراکتالیِ سطح `lvl` (نیم‌پنجرهٔ w، کاملاً در گذشته).
    - کندلِ i بالای آن سطح رفته: high[i] > lvl  (breakout)
    - اما زیرِ آن سطح بسته: close[i] < lvl        (failed breakout / تله)
    - رژیمِ رنج فعال است (chop بالا / r2 پایین / er پایین)  ← قلبِ فصل
    - (اختیاری) سیگنالِ دوم: این دومین failed-breakout بالای همان ناحیهٔ سطح است.
  LONG قرینهٔ کامل (failed breakout زیرِ swing low).

هدفِ اصلیِ RQS+: چون این fade است (خطرِ تلهٔ اسپردِ S325)، رژیمِ رنج + سیگنالِ دوم +
TP/SL غیررندِ per-TF کلیدِ عبور از گیت‌هاست.
"""
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicator_bank as ib


# ---------------------------------------------------------------------------
def _fractal_levels(h, l, w):
    """آخرین swing-high و swing-low سطح که *کاملاً در گذشته* تأیید شده (بدونِ look-ahead).

    یک پیوتِ high در اندیس p وقتی تأیید می‌شود که h[p] اکیداً بزرگ‌تر از w کندلِ چپ و w کندلِ
    راست باشد؛ این پیوت فقط از اندیسِ p+w به بعد «شناخته‌شده» است (چون کندل‌های راستش لازم‌اند).
    خروجی: دو آرایهٔ هم‌طول last_sh[i]، last_sl[i] = آخرین سطحِ سوئینگِ شناخته‌شده تا کندلِ i.
    """
    n = len(h)
    last_sh = np.full(n, np.nan)
    last_sl = np.full(n, np.nan)
    cur_sh = np.nan
    cur_sl = np.nan
    for i in range(n):
        # پیوتی که مرکزش p = i - w است، همین حالا (با کندلِ i به‌عنوان آخرین کندلِ راست) تأیید می‌شود
        p = i - w
        if p - w >= 0:
            hp = h[p]
            if hp > h[p - w:p].max() and hp > h[p + 1:p + w + 1].max():
                cur_sh = hp
            lp = l[p]
            if lp < l[p - w:p].min() and lp < l[p + 1:p + w + 1].min():
                cur_sl = lp
        last_sh[i] = cur_sh
        last_sl[i] = cur_sl
    return last_sh, last_sl


def _range_regime(df, chop_min, r2_max, er_max, chop_p, r2_p, er_name):
    """ماسکِ بولینِ رژیمِ رنج (بدونِ look-ahead). هرچه شرط بیشتر پاس شود، رنجی‌تر."""
    ch = ib.chop(df, p=chop_p).to_numpy()
    r2 = ib.r2(df, p=r2_p).to_numpy()
    er = ib.compute(er_name, df).to_numpy()
    mask = np.ones(len(df), dtype=bool)
    if chop_min is not None:
        mask &= (ch >= chop_min)
    if r2_max is not None:
        mask &= (r2 <= r2_max)
    if er_max is not None:
        mask &= (np.abs(er) <= er_max)
    mask &= np.isfinite(ch) & np.isfinite(r2) & np.isfinite(er)
    return mask


def swing_fade_signals(df, side, w=5, buf_frac=0.0,
                       chop_min=None, r2_max=None, er_max=None,
                       chop_p=14, r2_p=20, er_name='er_lucas_11',
                       require_second=False, second_lookback=40):
    """
    خروجی: آرایهٔ بولین هم‌طولِ df؛ True = سیگنالِ ورود روی این کندل (ورود در i+1).

    side='short' ⇒ failed breakout بالای swing high (fade پایین)
    side='long'  ⇒ failed breakout زیرِ swing low   (fade بالا)
    buf_frac      ⇒ بافرِ کوچک نسبت به ATR برای «واقعاً بالای سطح رفته» (کاهشِ نویز).
    require_second⇒ فقط دومین failed-breakout در پنجرهٔ second_lookback را بگیر.
    """
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)

    last_sh, last_sl = _fractal_levels(h, l, w)
    atr = ib.atr_s(df, p=14).to_numpy()
    reg = _range_regime(df, chop_min, r2_max, er_max, chop_p, r2_p, er_name)

    sig = np.zeros(n, dtype=bool)
    # برای سیگنالِ دوم: شمارِ failed-breakoutهای اخیرِ هم‌جهت
    recent = []  # اندیس‌های failed-breakout

    for i in range(w + 2, n):
        if not reg[i]:
            continue
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        buf = buf_frac * a

        if side == 'short':
            lvl = last_sh[i]
            if not np.isfinite(lvl):
                continue
            # breakout بالای سطح + بسته‌شدن زیرِ سطح (failed)
            broke = h[i] > (lvl + buf)
            failed = c[i] < lvl
            trig = broke and failed
        else:
            lvl = last_sl[i]
            if not np.isfinite(lvl):
                continue
            broke = l[i] < (lvl - buf)
            failed = c[i] > lvl
            trig = broke and failed

        if not trig:
            continue

        if require_second:
            # پاک‌سازیِ قدیمی‌ها
            recent = [x for x in recent if x >= i - second_lookback]
            recent.append(i)
            if len(recent) < 2:
                continue  # این اولین است ⇒ منتظرِ دوم بمان

        sig[i] = True

    return sig


# ---------------------------------------------------------------------------
def load_tf(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


if __name__ == '__main__':
    from engine import rqs
    # تستِ دود روی XAUUSD M5 (شروعِ اجباری از M پایین)
    df = load_tf('XAUUSD', 'M5')
    for side in ('short', 'long'):
        s = swing_fade_signals(df, side, w=5, buf_frac=0.1,
                               chop_min=55, r2_max=0.35, er_max=0.25,
                               require_second=False)
        long_sig = s if side == 'long' else np.zeros(len(df), bool)
        short_sig = s if side == 'short' else np.zeros(len(df), bool)
        tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=250, tp_pip=250,
                                asset='XAUUSD', max_hold=24, allow_overlap=False)
        r = rqs.compute_rqs(tr, 'XAUUSD', sl_pip=250, tp_pip=250)
        print(rqs.format_report(f'S341_XAU_M5_{side}', r))
