# -*- coding: utf-8 -*-
"""
S343 — Brooks "Trending Trading Range Day" Measured-Move Fade
================================================================================
منبع: کتابِ `1 Trading Price Action - Trends.pdf` — CHAPTER 22 (Trending Trading
Range Days). سندِ استخراج: `Telegram-Resource/telegram_source_1/pdfs/1 Trading
Price Action - Trends.pdf.md` (مرحلهٔ ۲۳).

تزِ مرکزیِ فصل (نقلِ مکانیکیِ Brooks):
  • رِنجِ اولیهٔ روز ≈ ⅓ تا ½ میانگینِ دامنهٔ روزانه است.
  • بعد از breakout، انتظارِ «دو برابر شدنِ دامنه» (measured-move ≈ +۱×initRange) را داشته باش.
  • ⭐ در ناحیهٔ measured-move هدف، «trend-barِ قوی (climax)» را **fade کن** (ورودِ ضدِ روند)
    با انتظارِ بازگشت به breakout-gap. مثالِ عددیِ Brooks: bears ~۴–۶ point (~۴۰–۶۰٪ initR)
    بالای رِنجِ پایینی scale-in short می‌کنند.

ترجمهٔ بک‌تست‌پذیر (بدونِ look-ahead، forward-safe):
  در پنجرهٔ N کندلِ اخیر (به‌عنوانِ «رِنجِ اولیه»):
    initHi = max(high[i-N+1..i]) ,  initLo = min(low[i-N+1..i]) ,  initR = initHi-initLo
  فیلترِ رژیمِ «رِنجِ کوچک»: initR ≤ smallMult × ATR(atrLen)   (کوچک ⇒ کاندیدِ TTR-day)
  هدفِ measured-move بالا:  tgtUp = initHi + k × initR
  هدفِ measured-move پایین: tgtDn = initLo − k × initR
  ⭐ FADE SHORT (کندلِ i): high[i] ≥ tgtUp  AND  کندلِ i یک bull-climax است
        (body = close-open ≥ climaxMult × ATR  و  close صعودی)
  ⭐ FADE LONG  (کندلِ i): low[i]  ≤ tgtDn  AND  کندلِ i یک bear-climax است
  ورود در open کندلِ i+1 (توسطِ موتور). SL آن‌سویِ climax (بیرونِ هدف)، TP بازگشت به رِنج.

قانونِ «همه‌چیز شناور است»: N, k, atrLen, smallMult, climaxMult, SL/TP همه per-TF و غیررند.
"""
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib


# ------------------------------------------------------------------------------
# ابزارهای پایه (verbatim برای پورتِ بی‌دردسر به TS)
# ------------------------------------------------------------------------------
def true_range(df):
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return tr


def atr(df, p):
    tr = true_range(df)
    return pd.Series(tr).rolling(p, min_periods=1).mean().values


def rolling_max(a, N):
    return pd.Series(a).rolling(N, min_periods=N).max().values


def rolling_min(a, N):
    return pd.Series(a).rolling(N, min_periods=N).min().values


def build_signals(df, N, atrLen, smallMult, k, climaxMult,
                  r2min=None, hurstmax=None, side='both'):
    """
    خروجی: long_sig, short_sig (np.bool هم‌طولِ df) — بدونِ look-ahead.
    سیگنالِ کندلِ i فقط از داده‌ی تا i استفاده می‌کند؛ ورود در i+1.
    """
    o = df['open'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    n = len(df)

    a = atr(df, atrLen)
    # رِنجِ اولیه: پنجرهٔ N کندلِ اخیر (شاملِ کندلِ i)
    initHi = rolling_max(h, N)
    initLo = rolling_min(l, N)
    initR = initHi - initLo

    body = c - o                       # بدنهٔ کندل (علامت‌دار)
    abody = np.abs(body)

    # فیلترِ رژیمِ «رِنجِ کوچک» (Brooks: رِنجِ اولیه ≈ ½ دامنهٔ معمول)
    small_ok = initR <= (smallMult * a)

    tgtUp = initHi + k * initR
    tgtDn = initLo - k * initR

    # کندلِ climax (بدنهٔ افراطی نسبت به ATR)
    bull_climax = (body >= climaxMult * a)
    bear_climax = (-body >= climaxMult * a)

    # FADE SHORT: رسیدن به هدفِ بالا + bull-climax  ⇒ ضدِ روند (short)
    short_sig = small_ok & (h >= tgtUp) & bull_climax
    # FADE LONG: رسیدن به هدفِ پایین + bear-climax ⇒ ضدِ روند (long)
    long_sig = small_ok & (l <= tgtDn) & bear_climax

    # فیلترهای رژیمِ اختیاریِ جعبه‌ابزار (r2/hurst) — «قانونِ جعبه‌ابزار»
    if r2min is not None:
        r2s = ib.compute('r2', df).values
        # برای mean-reversion، رِنج‌بودن مطلوب است ⇒ r2 پایین بهتر؛ اما به‌عنوانِ فیلترِ
        # کیفیت اجازه می‌دهیم هر دو جهت آزموده شود (اسکن تصمیم می‌گیرد).
        gate = r2s <= r2min
        long_sig &= gate
        short_sig &= gate
    if hurstmax is not None:
        hus = ib.compute('hurst', df).values
        gate = hus <= hurstmax          # hurst پایین ⇒ mean-reverting ⇒ مطلوبِ fade
        long_sig &= gate
        short_sig &= gate

    # اطمینان از نبودِ NaN در ابتدای سری
    valid = ~(np.isnan(initR) | np.isnan(a))
    long_sig &= valid
    short_sig &= valid

    if side == 'long':
        short_sig[:] = False
    elif side == 'short':
        long_sig[:] = False
    return long_sig, short_sig


def run_one(path, asset, N, atrLen, smallMult, k, climaxMult,
            sl_pip, tp_pip, max_hold, r2min=None, hurstmax=None, side='both',
            label=''):
    df = se.load_data(path)
    ls, ss = build_signals(df, N, atrLen, smallMult, k, climaxMult,
                           r2min=r2min, hurstmax=hurstmax, side=side)
    trades = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=asset, max_hold=max_hold, allow_overlap=False)
    if len(trades):
        trades['tp_pip'] = tp_pip
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip, tp_pip=tp_pip)
    n_long = int(ls.sum()); n_short = int(ss.sum())
    return r, len(trades), n_long, n_short, df


if __name__ == '__main__':
    import sys
    # تستِ سریعِ پیش‌فرض روی XAUUSD M5 (پایین‌ترین TF موجودِ طلا)
    r, nt, nl, ns, df = run_one('data/XAUUSD_M5.csv', 'XAUUSD',
                                N=21, atrLen=21, smallMult=0.6, k=1.0, climaxMult=1.2,
                                sl_pip=200, tp_pip=140, max_hold=48, side='both')
    print(rqs.format_report('S343_XAUUSD_M5_default', r))
    print(f"  raw signals long={nl} short={ns} trades={nt}")
