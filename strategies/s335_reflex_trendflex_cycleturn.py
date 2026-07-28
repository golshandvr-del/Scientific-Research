# -*- coding: utf-8 -*-
"""
S335 — Reflex-TrendFlex Cycle-Turn (چرخشِ چرخهٔ کم‌تأخیرِ اِهلرز)
================================================================================
> استراتژیِ *جدید* (User Note این نشست: «خودت با ترکیبِ اندیکاتورها یک استراتژیِ
> جدید بساز»). این لایه با هیچ‌کدام از لایه‌های فعلی هم‌منطق نیست: تنها لایه‌ای است
> که هستهٔ سیگنالش از دستهٔ **cycle/DSP اِهلرز** می‌آید (که راهنمای بانک آن را
> «حوزهٔ پیچیده و کم‌استفاده / فرصتِ کشفِ لبه» می‌نامد — رفعِ اشتباه رایج #۲ و #۳).

منبعِ نظری (استنادِ علمی):
  • John F. Ehlers, "Cycle Analytics for Traders" (Wiley, 2013) — فلسفهٔ DSP: قیمت یک
    سیگنالِ فیزیکی است؛ Super Smoother = فیلترِ ۲-قطبیِ Butterworth با کمترین تأخیر.
  • John F. Ehlers, "Reflex and TrendFlex Indicators" (Stocks & Commodities, Feb 2020):
    - TrendFlex : سنجهٔ *جهت/قدرتِ روندِ* کم‌تأخیر (صفرمحور).
    - Reflex    : سنجهٔ *چرخهٔ* کم‌تأخیر (صفرمحور) — انحرافِ قیمت از خطِ روندِ محلی.
    اِهلرز پیشنهاد می‌کند: TrendFlex = «چه جهت»، Reflex = «چه زمان». با هم یک سیستمِ
    کاملِ کِی-و-کجا می‌سازند (docs/indicators/cycle.md بند ۶ و ۷).

منطقِ لایه (LONG، خرید در کفِ چرخه درونِ روندِ صعودی):
  1) گیتِ رژیم/جهت:      trendflex(pTf) > tfMin      → روندِ صعودیِ کم‌تأخیر برقرار است.
  2) تریگرِ چرخش چرخه:   reflex(pRf) از کف (< -rfDip) رو به بالا برمی‌گردد
                          یعنی reflex[i] > reflex[i-1]  و  reflex[i-1] <= -rfDip
                          (پایانِ پول‌بکِ کوتاه‌مدت درونِ روند — «خرید در کفِ چرخه»).
  3) فیلترِ کیفیتِ روند:  hurst(pHu) > huMin  (حافظهٔ روندی؛ ضدِ whipsawِ رنجِ نویزی).

  همهٔ سیگنال‌ها بدونِ look-ahead: تصمیمِ کندلِ i از دادهٔ تا i؛ ورود در open کندلِ i+1
  (توسطِ scalp_engine.simulate_trades). فیلترهای اِهلرز stateful و forward-safe‌اند.

SL/TP:  per-TF و غیررند (از اسکن؛ اشتباه رایج #۶/#۷). TP≥SL نگه داشته می‌شود تا WR از
        دقتِ ورود بیاید نه از هندسهٔ TP<SL (اشتباه رایج #۹).

اجرا:   python3 strategies/s335_reflex_trendflex_cycleturn.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib


# ---------------------------------------------------------------------------
# منطقِ سیگنال — همان توابعِ بانک (reflex/trendflex/hurst) بدونِ look-ahead
# ---------------------------------------------------------------------------
def build_long_signal(df, p_rf, p_tf, rf_dip, tf_min, p_hu, hu_min):
    """آرایهٔ بولینِ هم‌طولِ df؛ True = سیگنالِ خریدِ کندلِ i (ورود در i+1)."""
    reflex = ib.reflex(df, period=p_rf).values.astype(float)
    tflex  = ib.trendflex(df, period=p_tf).values.astype(float)
    hurst  = ib.hurst(df, p=p_hu).values.astype(float)
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    for i in range(1, n):
        # گیتِ رژیم/جهت (روندِ صعودیِ کم‌تأخیر)
        if not (np.isfinite(tflex[i]) and tflex[i] > tf_min):
            continue
        # فیلترِ کیفیتِ روند (حافظهٔ روندی)
        if not (np.isfinite(hurst[i]) and hurst[i] > hu_min):
            continue
        # تریگرِ چرخشِ چرخه: reflex از کف (<= -rf_dip) رو به بالا
        if not (np.isfinite(reflex[i]) and np.isfinite(reflex[i - 1])):
            continue
        if reflex[i - 1] <= -rf_dip and reflex[i] > reflex[i - 1]:
            sig[i] = True
    return sig


def evaluate(asset, tf_file, p_rf, p_tf, rf_dip, tf_min, p_hu, hu_min,
             sl_pip, tp_pip, max_hold, verbose=False):
    df = se.load_data(tf_file)
    long_sig = build_long_signal(df, p_rf, p_tf, rf_dip, tf_min, p_hu, hu_min)
    short_sig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=asset, max_hold=max_hold, allow_overlap=False)
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip, tp_pip=tp_pip)
    return r, trades, df


if __name__ == '__main__':
    # نقطهٔ شروعِ اجباری: XAUUSD M5
    print("=== S335 — Reflex-TrendFlex Cycle-Turn — اسکنِ اولیه روی XAUUSD M5 ===")
    r, tr, df = evaluate('XAUUSD', 'data/XAUUSD_M5.csv',
                         p_rf=20, p_tf=34, rf_dip=1.0, tf_min=0.0, p_hu=55, hu_min=0.50,
                         sl_pip=170, tp_pip=255, max_hold=48)
    print(rqs.format_report('S335_XAUUSD_M5_seed', r))
