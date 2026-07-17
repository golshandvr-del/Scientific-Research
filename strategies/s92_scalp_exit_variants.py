# -*- coding: utf-8 -*-
"""
s92_scalp_exit_variants.py — اسکنِ منطق‌های خروجِ سیگنال-محور برای بخشِ اسکالپ
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است، نه WR.
> سودِ خالص = XAUUSD + EURUSD.
================================================================================

هدف: با استفاده از paper broker (s91)، چند منطقِ خروجِ لحظه‌ای را روی همان لبهٔ
ورودِ اثبات‌شدهٔ S79 (trend-pullback، فقط Long) بسنجیم و ببینیم کدام «خروجِ
سیگنال-محور» (بدون TP/SL ثابت) سودِ خالصِ بیشتری از خروجِ TP/SL ثابتِ S79 می‌دهد.

ورودِ پایه (همان S79 — لبهٔ اثبات‌شده):
    EMA(20) > EMA(100)  و  RSI(21) < 35   → BUY (پولبک در روندِ صعودی)

منطق‌های خروجِ کاندید (هرکدام «سودمونو گرفتیم» یا «اشتباه بود» را تعریف می‌کند):
  E1  RSI-target       : ببند وقتی RSI ≥ 55 (سود گرفته شد) یا EMA20<EMA100 (روند شکست).
  E2  MACD-flip        : ببند وقتی MACD-hist از مثبت به منفی رفت (مومنتوم تمام شد).
  E3  RSI+time         : E1 + سقفِ زمانی نگهداری.
  E4  peak-giveback    : ببند وقتی سود از اوجِ خود ۴۰٪ پس داد (trailing سیگنالی).
  E5  ema-cross-exit   : ببند فقط وقتی EMA20 دوباره زیر EMA100 رفت (خروجِ روندی خالص).
همه در برابرِ baselineِ S79 (TP=120pip/SL=50pip ثابت) روی همان ورودها مقایسه می‌شوند.

both-halves: هر منطق روی نیمهٔ اول و دومِ داده جداگانه گزارش می‌شود (ضدِ overfit).
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strategies.s91_scalp_signal_exit import (
    paper_broker, stats, print_stats, ema, rsi, atr,
    PIP, COST_PIP, DATA,
)

EMA_FAST, EMA_SLOW = 20, 100
RSI_PERIOD = 21
RSI_ENTRY = 35


def build_entries_long_pullback(df):
    """ورودِ S79: روندِ صعودی + پولبک (RSI<35). فقط Long."""
    c = df['close'].values.astype(np.float64)
    emaF = ema(c, EMA_FAST)
    emaS = ema(c, EMA_SLOW)
    rsiArr = rsi(c, RSI_PERIOD)
    entries = []
    n = len(df)
    for i in range(EMA_SLOW + 2, n - 1):
        if emaF[i] > emaS[i] and rsiArr[i] < RSI_ENTRY:
            entries.append((i, 'long'))
    return entries


# ---------------- منطق‌های خروج ----------------
def exit_E1_rsi_target(ctx):
    # سود گرفته شد: RSI به ناحیهٔ اشباع خرید رسید
    if ctx['side'] == 'long' and ctx['rsi'] >= 55:
        return ('win', 'rsi_overbought')
    # اشتباه بود: روندِ صعودی شکست (EMA20 زیرِ EMA100)
    if ctx['ema_f'] < ctx['ema_s']:
        return ('loss', 'trend_broke')
    return None


def exit_E2_macd_flip(ctx):
    if ctx['side'] == 'long':
        if ctx['macd_hist'] < 0 and ctx['favor_pip'] > 0:
            return ('win', 'macd_flip_in_profit')
        if ctx['macd_hist'] < 0 and ctx['bars_held'] >= 6:
            return ('loss', 'macd_flip_no_profit')
    if ctx['ema_f'] < ctx['ema_s']:
        return ('loss', 'trend_broke')
    return None


def exit_E3_rsi_time(ctx):
    r = exit_E1_rsi_target(ctx)
    if r is not None:
        return r
    if ctx['bars_held'] >= 72:   # ۶ ساعت M5
        return ('win' if ctx['favor_pip'] > 0 else 'loss', 'time_cap')
    return None


def exit_E4_peak_giveback(ctx):
    peak = ctx['peak_favor_pip']
    # فقط وقتی سودِ معناداری داشته‌ایم trailing سیگنالی فعال می‌شود
    if peak >= 60 and ctx['favor_pip_gross'] <= 0.6 * peak:
        return ('win', 'peak_giveback')
    if ctx['ema_f'] < ctx['ema_s'] and ctx['favor_pip'] <= 0:
        return ('loss', 'trend_broke')
    if ctx['bars_held'] >= 96:
        return ('win' if ctx['favor_pip'] > 0 else 'loss', 'time_cap')
    return None


def exit_E5_ema_cross(ctx):
    # خروجِ روندی خالص: فقط وقتی EMA20 دوباره زیرِ EMA100 رفت.
    if ctx['ema_f'] < ctx['ema_s']:
        return ('win' if ctx['favor_pip'] > 0 else 'loss', 'ema_cross')
    if ctx['bars_held'] >= 144:
        return ('win' if ctx['favor_pip'] > 0 else 'loss', 'time_cap')
    return None


EXITS = [
    ('E1_rsi_target', exit_E1_rsi_target),
    ('E2_macd_flip', exit_E2_macd_flip),
    ('E3_rsi_time', exit_E3_rsi_time),
    ('E4_peak_giveback', exit_E4_peak_giveback),
    ('E5_ema_cross', exit_E5_ema_cross),
]


def run_on(df, entries, tag):
    print(f"\n── {tag}  (ورودها: {len(entries)}) ──")
    results = {}
    for name, fn in EXITS:
        tr = paper_broker(df, entries, fn, catastrophic_sl_pip=200.0, max_hold=288)
        # bar های ورود در subset را باید به اندیس واقعیِ df نگاشت — اینجا df همان است
        s = stats(tr, name)
        print_stats(s)
        results[name] = (s, tr)
    return results


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    n = len(df)
    print("=" * 78)
    print("s92 — اسکنِ خروجِ سیگنال-محورِ اسکالپ روی دادهٔ واقعیِ M5 طلا")
    print("=" * 78)
    print(f"داده: {n} کندل  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")

    entries_all = build_entries_long_pullback(df)
    print(f"سیگنال‌های ورودِ S79 (long pullback): {len(entries_all)}")

    # کل داده
    run_on(df, entries_all, "کلِ داده (۲۰۰k کندل)")

    # نیمهٔ اول / دوم (both-halves — ضدِ overfit)
    half = n // 2
    e1 = [(i, s) for (i, s) in entries_all if i < half - 1]
    df1 = df.iloc[:half].reset_index(drop=True)
    run_on(df1, e1, "نیمهٔ اول")

    e2_raw = [(i, s) for (i, s) in entries_all if i >= half]
    df2 = df.iloc[half:].reset_index(drop=True)
    e2 = [(i - half, s) for (i, s) in e2_raw]
    run_on(df2, e2, "نیمهٔ دوم")

    print("\n" + "=" * 78)
    print("نتیجه‌گیری: منطقی که در «کل + هر دو نیمه» بیشترین net مثبت را بدهد،")
    print("منطقِ خروجِ بخشِ اسکالپِ سایت می‌شود (بدون هیچ TP/SL نمایشی برای کاربر).")
    print("=" * 78)


if __name__ == '__main__':
    main()
