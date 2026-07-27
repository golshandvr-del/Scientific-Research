# -*- coding: utf-8 -*-
"""
S79 Revival under RQS+ — احیای «XAUUSD M5 Trend-Pullback» با معیارِ RQS+
================================================================================
لایهٔ سوختهٔ هدف: S79 (results/S79_Gold_M5_TrendPullback_NetProfit_4256.md)
منطقِ اصلی:  EMA(20)>EMA(100)  AND  RSI(21)<35  → Long فقط ، SL=50 TP=120 ، max_hold=72

با معیارِ قدیمِ «سودِ خالص» موفق بود (+4256$) اما با RQS+ قطعاً رد می‌شود:
   WR≈39%(<60 → G0✗) · PF≈1.18(<1.3 → G2✗) · MaxDD≈15.5%(>8 → G3✗)

این اسکریپت:
  گام ۰) baselineِ اصلی را بازتولید و ردشدنِ RQS+ را تأیید می‌کند (اثباتِ سوخته‌بودن).
  گام‌های بعد در همین فایل (به‌صورت افزایشی) بهبودها را می‌آزماید.

اجرا:  python strategies/explore_s79_revival_rqs.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicators as ind


def load(asset_key, tf):
    """بارگذاریِ داده برای یک دارایی/تایم‌فریم مشخص."""
    path = f"data/{asset_key}_{tf}.csv"
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def s79_baseline_signals(df):
    """منطقِ دقیقِ S79 اصلی."""
    close = df['close']
    ema20 = ind.ema(close, 20)
    ema100 = ind.ema(close, 100)
    rsi21 = ind.rsi(close, 21)
    long_sig = (ema20 > ema100) & (rsi21 < 35)
    short_sig = pd.Series(False, index=df.index)
    return long_sig.fillna(False).values, short_sig.values


def evaluate(name, df, long_sig, short_sig, sl_pip, tp_pip, asset,
             max_hold=72, be=None, trail=None, verbose=True):
    """شبیه‌سازی + RQS+ و چاپِ گزارشِ تک‌خطی."""
    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, asset,
                                max_hold=max_hold, be_trigger_pip=be, trail_pip=trail)
    # sl/tp مؤثر برای گیتِ G1 (اگر آرایه بود، میانه)
    sl_eff = float(np.median(sl_pip)) if not np.isscalar(sl_pip) else float(sl_pip)
    tp_eff = float(np.median(tp_pip)) if not np.isscalar(tp_pip) else float(tp_pip)
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_eff, tp_pip=tp_eff)
    if verbose:
        print(rqs.format_report(name, r))
    return r, trades


if __name__ == '__main__':
    print("=" * 110)
    print("گام ۰ — بازتولیدِ baselineِ S79 اصلی و تأییدِ ردشدن با RQS+  (XAUUSD M5)")
    print("=" * 110)

    df5 = load('XAUUSD', 'M5')
    print(f"داده: XAUUSD M5 — {len(df5):,} کندل  ({df5['dt'].iloc[0]} تا {df5['dt'].iloc[-1]})")

    lsig, ssig = s79_baseline_signals(df5)
    print(f"تعدادِ سیگنالِ خام (long): {int(lsig.sum()):,}")

    r0, tr0 = evaluate("S79-baseline (EMA20>100 & RSI21<35, SL50/TP120, hold72)",
                       df5, lsig, ssig, 50.0, 120.0, 'XAUUSD', max_hold=72)

    print("\nجزئیاتِ گیت‌ها:")
    for g, ok in r0['gates'].items():
        print(f"   {g}: {'✓ پاس' if ok else '✗ رد'}")
    print(f"\nحکم: {r0['verdict']}  |  RQS={r0['rqs_score']}")
    print(f"متریک‌ها: {r0['metrics']}")

    # ========================================================================
    print("\n" + "=" * 110)
    print("گام ۱ — تشخیصِ ریشه‌ای: G1/G4/G5 پاس ⇒ لبهٔ واقعی هست؛ مشکل شکلِ توزیع است.")
    print("        فرضیه: معکوس‌کردنِ R:R (TP کوچک، SL بزرگ‌تر) + max_holdِ کوتاه‌تر")
    print("        WR را بالای ۶۰٪ می‌برد (mean-reversion: بازگشتِ کوچک محتمل‌تر است).")
    print("=" * 110)

    # اسکنِ محورِ R:R معکوس روی همان سیگنالِ خام S79 (بدون فیلترِ اضافه هنوز)
    # هدف: ببینیم صرفِ تغییرِ TP/SL چقدر WR/PF را جابجا می‌کند.
    print(f"\n{'SL/TP/hold':28s} | verdict  RQS  |  n    WR    PF    DD    MCL   p")
    print("-" * 95)
    grid = []
    for sl in [40, 60, 80, 100]:
        for tp in [12, 18, 24, 30, 40]:
            for hold in [12, 24, 48]:
                r, _ = evaluate(f"SL{sl}/TP{tp}/h{hold}", df5, lsig, ssig,
                                float(sl), float(tp), 'XAUUSD', max_hold=hold, verbose=False)
                m = r['metrics']
                grid.append((r['rqs_score'], sl, tp, hold, r, m))
    # مرتب‌سازی بر اساسِ WR سپس RQS
    grid.sort(key=lambda x: (x[5].get('win_rate', 0), x[0]), reverse=True)
    for score, sl, tp, hold, r, m in grid[:15]:
        print(f"SL{sl:3d}/TP{tp:3d}/h{hold:2d}{'':13s} | {r['verdict']:6s} {score:5.1f} | "
              f"{m['n_trades']:4d} {m['win_rate']:5.1f} {m['profit_factor']:5.2f} "
              f"{m['max_dd_pct']:5.1f} {m['max_consec_losses']:3d}  {m['p_value']:.3f}")

    best = max(grid, key=lambda x: x[0])
    print(f"\nبهترین RQS در این اسکن: {best[0]}  (SL{best[1]}/TP{best[2]}/hold{best[3]})")
    print("درسِ گام ۱: معکوسِ افراطیِ R:R ⇒ WR بالا ولی p≈۱ و PF<۱ (تلهٔ WR). RQS+ آن را می‌گیرد.")
    print("⇒ باید R:R را نزدیکِ متعادل نگه داشت و WR را با «فیلترِ کیفیتِ ورود» بالا برد، نه با R:R.")

    # ========================================================================
    print("\n" + "=" * 110)
    print("گام ۲ — فیلترهای کیفیتِ ورود (بانکِ اندیکاتور) + R:R متعادل.")
    print("        منطقِ پایه S79 حفظ می‌شود؛ فقط بهترین pullbackها با فیلتر انتخاب می‌شوند.")
    print("=" * 110)

    close = df5['close']
    ema20 = ind.ema(close, 20); ema100 = ind.ema(close, 100)
    rsi21 = ind.rsi(close, 21)
    atr14 = ind.atr(df5, 14)
    adx14, pdi, mdi = ind.adx(df5, 14)
    # فاصلهٔ نرمال‌شدهٔ قیمت تا EMA100 بر حسبِ ATR (عمقِ pullback)
    dist_atr = (ema100 - close) / atr14
    # شیبِ EMA100 بر حسبِ ATR (قدرتِ روند)
    slope100 = (ema100 - ema100.shift(20)) / atr14
    base = (ema20 > ema100) & (rsi21 < 35)

    def apply_filter(mask):
        s = (base & mask).fillna(False).values
        return s, pd.Series(False, index=df5.index).values

    print("\nفیلترها (هرکدام روی base S79، با SL60/TP72 ⇒ R:R=1:1.2 متعادل، hold48):")
    print(f"{'filter':42s} | verdict RQS |  n    WR    PF    DD   MCL   p")
    print("-" * 100)

    SL, TP, HOLD = 60.0, 72.0, 48
    filters = {
        'بدون فیلتر (فقط R:R متعادل)': pd.Series(True, index=df5.index),
        'ADX>25 (روندِ قوی)': adx14 > 25,
        'ADX>30': adx14 > 30,
        'slope100>1.0 (روندِ صعودیِ محکم)': slope100 > 1.0,
        'slope100>1.5': slope100 > 1.5,
        'dist_atr>0.5 (pullbackِ عمیق)': dist_atr > 0.5,
        'dist_atr در [0.3,1.5] (متعادل)': (dist_atr > 0.3) & (dist_atr < 1.5),
        'ADX>25 & slope100>1.0': (adx14 > 25) & (slope100 > 1.0),
        'ADX>25 & dist_atr>0.3': (adx14 > 25) & (dist_atr > 0.3),
    }
    for fname, mask in filters.items():
        s, ss = apply_filter(mask)
        r, _ = evaluate(fname, df5, s, ss, SL, TP, 'XAUUSD', max_hold=HOLD, verbose=False)
        m = r['metrics']
        print(f"{fname:42s} | {r['verdict']:6s} {r['rqs_score']:4.0f} | "
              f"{m['n_trades']:4d} {m['win_rate']:5.1f} {m['profit_factor']:5.2f} "
              f"{m['max_dd_pct']:5.1f} {m['max_consec_losses']:3d}  {m['p_value']:.3f}")

    print("\nدرسِ گام ۲: فیلترِ «قدرتِ روند» (slope100/ATR) قوی‌ترین اهرم است:")
    print("   slope>1.0 ⇒ WR58 PF1.82 DD3.1 (نزدیکِ پاس)؛ slope>1.5 ⇒ WR87 اما n=8 (کم‌نمونه).")
    print("   ⇒ نقطهٔ شیرین بینِ این دو + تنظیمِ دقیقِ R:R (اعدادِ غیررند). → گام ۳")

    # ========================================================================
    print("\n" + "=" * 110)
    print("گام ۳ — تنظیمِ دقیق: آستانهٔ slope غیررند + R:R، برای پاسِ همزمانِ هر ۶ گیت.")
    print("        قید: n≥30 (G0) ، WR≥60 ، PF≥1.3 ، DD≤8 ، MCL≤8 ، p<0.05.")
    print("=" * 110)

    print(f"\n{'slope>  SL/TP  hold':30s} | verdict RQS |  n    WR    PF    DD   MCL   p     G0123 45")
    print("-" * 105)
    results3 = []
    for sl_th in [1.05, 1.15, 1.25, 1.35]:
        mask = slope100 > sl_th
        for sl in [45, 55, 65]:
            for rr in [1.0, 1.2, 1.4]:
                tp = round(sl * rr)
                for hold in [36, 60]:
                    s, ss = apply_filter(mask)
                    r, _ = evaluate(f"s{sl_th}", df5, s, ss, float(sl), float(tp),
                                    'XAUUSD', max_hold=hold, verbose=False)
                    m = r['metrics']
                    results3.append((r['rqs_score'], sl_th, sl, tp, hold, r, m))
    results3.sort(key=lambda x: x[0], reverse=True)
    for score, sl_th, sl, tp, hold, r, m in results3[:18]:
        g = r['gates']
        gstr = ''.join('1' if g[f'G{i}'] else '0' for i in range(6))
        print(f"slope>{sl_th} SL{sl}/TP{tp} h{hold:2d}{'':6s} | {r['verdict']:6s} {score:4.0f} | "
              f"{m['n_trades']:4d} {m['win_rate']:5.1f} {m['profit_factor']:5.2f} "
              f"{m['max_dd_pct']:5.1f} {m['max_consec_losses']:3d}  {m['p_value']:.3f}  {gstr}")

    passed3 = [x for x in results3 if x[5]['passed']]
    print(f"\nتعدادِ ترکیب‌هایی که هر ۶ گیت را پاس کردند: {len(passed3)}")
    if passed3:
        b = max(passed3, key=lambda x: x[0])
        print(f"بهترین پاس‌شده: slope>{b[1]} SL{b[2]}/TP{b[3]} hold{b[4]} → RQS={b[0]}")

    # ========================================================================
    print("\n" + "=" * 110)
    print("گام ۴ — نگرانیِ علمی: n=37 نزدیکِ کفِ ۳۰ است. تلاش برای n بیشتر + تحلیلِ حساسیت.")
    print("        هدف: پیکربندیِ مقاوم با n راحت بالای ۳۰ و RQS بالا، نه یک نقطهٔ شکننده.")
    print("=" * 110)

    print(f"\n{'slope>  SL/TP  hold':30s} | verdict RQS |  n    WR    PF    DD   MCL   p     gates")
    print("-" * 105)
    results4 = []
    for sl_th in [0.75, 0.85, 0.95, 1.05]:
        mask = slope100 > sl_th
        for sl in [55, 65, 75]:
            for tp in [55, 65, 78, 91]:
                for hold in [48, 60, 72]:
                    s, ss = apply_filter(mask)
                    r, _ = evaluate(f"s{sl_th}", df5, s, ss, float(sl), float(tp),
                                    'XAUUSD', max_hold=hold, verbose=False)
                    m = r['metrics']
                    results4.append((r['rqs_score'], sl_th, sl, tp, hold, r, m))
    # مرتب‌سازی: اول پاس‌شده‌ها با n بالا، سپس RQS
    passed4 = [x for x in results4 if x[5]['passed']]
    passed4.sort(key=lambda x: (x[6]['n_trades'], x[0]), reverse=True)
    print("— پاس‌شده‌ها با بیشترین n (مقاوم‌ترین): —")
    for score, sl_th, sl, tp, hold, r, m in passed4[:12]:
        g = r['gates']; gstr = ''.join('1' if g[f'G{i}'] else '0' for i in range(6))
        print(f"slope>{sl_th} SL{sl}/TP{tp} h{hold:2d}{'':6s} | {r['verdict']:6s} {score:4.0f} | "
              f"{m['n_trades']:4d} {m['win_rate']:5.1f} {m['profit_factor']:5.2f} "
              f"{m['max_dd_pct']:5.1f} {m['max_consec_losses']:3d}  {m['p_value']:.3f}  {gstr}")

    print(f"\nمجموعِ پاس‌شده در گام ۴: {len(passed4)}")
    if passed4:
        # انتخابِ نهایی: بیشترین n میانِ آن‌هایی که RQS≥85 (تعادلِ مقاومت و کیفیت)
        robust = [x for x in passed4 if x[0] >= 85]
        pick = max(robust, key=lambda x: x[6]['n_trades']) if robust else passed4[0]
        print(f"\n🎯 انتخابِ نهاییِ مقاوم: slope>{pick[1]} SL{pick[2]}/TP{pick[3]} hold{pick[4]}")
        print(f"   n={pick[6]['n_trades']} WR={pick[6]['win_rate']} PF={pick[6]['profit_factor']} "
              f"DD={pick[6]['max_dd_pct']} MCL={pick[6]['max_consec_losses']} RQS={pick[0]}")
