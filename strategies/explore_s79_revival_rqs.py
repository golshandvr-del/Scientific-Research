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
    print("نتیجه‌گیریِ گام ۱: آیا صرفِ R:R کافی است یا فیلترِ کیفیت هم لازم است؟ → گام ۲")
