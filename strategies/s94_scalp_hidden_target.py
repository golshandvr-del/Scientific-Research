# -*- coding: utf-8 -*-
"""
s94_scalp_hidden_target.py — منطقِ خروجِ «هدفِ پنهان» (بهترین سود، بدونِ نمایشِ TP/SL)
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است، نه WR.
> سودِ خالص = XAUUSD + EURUSD.
================================================================================

کشفِ s93: از نظرِ «سودِ خالص»، خروجِ TP/SL ثابت (TP=120/SL=50) بهتر از خروجِ
سیگنال-محورِ زودهنگام (E4/E5) بود (+$331 در برابرِ +$133).

اما User Note می‌گوید کاربر نباید TP/SL ببیند — سایت باید فقط **لحظه‌ای** بگوید
«سودمونو گرفتیم، ببند» یا «اشتباه بود، ببند».

راهِ حل که هم User Note را برآورده می‌کند و هم بیشترین سود را می‌دهد:
  **هدفِ پنهان (hidden target).** سایت داخلی همان منطقِ برندهٔ TP/SL را دارد، اما
  به‌جای نمایشِ عدد، فقط پیامِ خروج می‌دهد. یعنی خروج هنوز سیگنال-محور (لحظه‌ای)
  است، ولی «سیگنالِ سود» = رسیدنِ حرکتِ مطلوب به آستانهٔ پنهانِ سود، و «سیگنالِ
  اشتباه» = رسیدنِ حرکتِ نامطلوب به آستانهٔ پنهانِ ضرر یا شکستِ روند.

این فایل آستانه‌های پنهانِ سود/ضرر را جارو (sweep) می‌کند تا بهترین جفت را برای
سودِ خالص (با قیدِ both-halves مثبت) پیدا کند. این آستانه‌ها **هرگز** به کاربر
نمایش داده نمی‌شوند؛ فقط تصمیمِ خروجِ سایت را می‌سازند.

نکته: برای «لحظه‌ای بودن»، آستانه‌ها روی close هر کندل سنجیده می‌شوند (نه intrabar
high/low) — چون سایت هر ~۲ ثانیه قیمتِ close/live را می‌بیند، نه wickِ intrabar.
این محافظه‌کارانه‌تر از baselineِ intrabarِ s93 است و به واقعیتِ سایت نزدیک‌تر.
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strategies.s91_scalp_signal_exit import (
    paper_broker, stats, print_stats, DATA,
)
from strategies.s92_scalp_exit_variants import build_entries_long_pullback


def make_hidden_exit(tp_pip, sl_pip, use_trend_break=True):
    """منطقِ خروجِ «هدفِ پنهان» روی close (لحظه‌ای، شبیهِ واقعیتِ سایت).

    - وقتی favor_pip_gross ≥ tp_pip → «سودمونو گرفتیم، ببند» (win).
    - وقتی favor_pip_gross ≤ -sl_pip → «اشتباه بود، ببند» (loss).
    - (اختیاری) وقتی روندِ صعودی شکست و در ضرریم → «اشتباه بود، ببند».
    """
    def _exit(ctx):
        g = ctx['favor_pip_gross']
        if g >= tp_pip:
            return ('win', 'hidden_target_hit')
        if g <= -sl_pip:
            return ('loss', 'hidden_stop_hit')
        if use_trend_break and ctx['ema_f'] < ctx['ema_s'] and g <= 0:
            return ('loss', 'trend_broke')
        return None
    return _exit


def halves(df, entries, exit_fn, cat_sl=500.0):
    n = len(df); half = n // 2
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288)
    s_all = stats(tr)
    e1 = [(i, s) for (i, s) in entries if i < half - 1]
    df1 = df.iloc[:half].reset_index(drop=True)
    s1 = stats(paper_broker(df1, e1, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288))
    e2 = [(i - half, s) for (i, s) in entries if i >= half]
    df2 = df.iloc[half:].reset_index(drop=True)
    s2 = stats(paper_broker(df2, e2, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288))
    return s_all, s1, s2, tr


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    entries = build_entries_long_pullback(df)
    print("=" * 84)
    print("s94 — جارویِ آستانه‌های «هدفِ پنهان» برای بیشترین سودِ خالص (both-halves مثبت)")
    print("=" * 84)
    print(f"داده: {len(df)} کندل   ورودها: {len(entries)}   (خروج روی close = لحظه‌ایِ واقعیِ سایت)\n")

    tp_grid = [100, 120, 150, 180]
    sl_grid = [50, 60, 80]
    results = []
    print(f"{'TP':>4} {'SL':>4} {'trendbrk':>8} | {'net_all':>9} {'PF':>5} {'WR':>5} {'n':>4} | "
          f"{'net½1':>8} {'net½2':>8} both")
    print("-" * 84)
    for tb in [True, False]:
        for tp in tp_grid:
            for sl in sl_grid:
                fn = make_hidden_exit(tp, sl, use_trend_break=tb)
                s_all, s1, s2, tr = halves(df, entries, fn)
                both = s1['net_usd'] > 0 and s2['net_usd'] > 0
                results.append((tp, sl, tb, s_all, s1, s2, both))
                flag = '✅' if both else '  '
                print(f"{tp:>4} {sl:>4} {str(tb):>8} | ${s_all['net_usd']:>+8.2f} "
                      f"{s_all['pf']:>5.2f} {s_all['wr']:>4.1f}% {s_all['n']:>4} | "
                      f"${s1['net_usd']:>+7.2f} ${s2['net_usd']:>+7.2f} {flag}")

    # بهترین: both-halves مثبت + بیشترین net کل
    valid = [r for r in results if r[6]]
    valid.sort(key=lambda r: r[3]['net_usd'], reverse=True)
    print("\n" + "=" * 84)
    if valid:
        best = valid[0]
        tp, sl, tb, s_all, s1, s2, _ = best
        print(f"🏆 بهترین هدفِ پنهان: TP={tp}pip  SL={sl}pip  trend_break={tb}")
        print(f"   net کل = ${s_all['net_usd']:+.2f}  (PF {s_all['pf']:.2f}, WR {s_all['wr']:.1f}%, n={s_all['n']})")
        print(f"   نیمهٔ۱ = ${s1['net_usd']:+.2f}   نیمهٔ۲ = ${s2['net_usd']:+.2f}   (هر دو مثبت ✅)")
        print(f"\n   → این آستانه‌ها فقط داخلِ منطقِ سایت‌اند و به کاربر نمایش داده نمی‌شوند.")
        print(f"   → کاربر فقط می‌بیند: BUY، سپس «سودمونو گرفتیم/اشتباه بود، ببند».")
    else:
        print("هیچ ترکیبی both-halves مثبت نشد!")
    print("=" * 84)


if __name__ == '__main__':
    main()
