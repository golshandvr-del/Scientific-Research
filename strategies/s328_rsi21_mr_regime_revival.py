# -*- coding: utf-8 -*-
"""
S328 — احیای S167 (RSI-21 Mean-Reversion) با فیلترِ رژیمِ رنج + قانونِ شناوری
================================================================================
منشأ: S167 (کتابِ Subarkah 2009) — RSI-21 cross-back mean-reversion.
      در S167 روی XAUUSD M15 با WR=53.1٪ لبه داشت اما به‌دلیلِ ناپایداریِ walk-forward
      (پنجرهٔ W3 منفی، PF=0.73) رد شد. هرگز مولتی‌تایم‌فریمِ کامل + فیلترِ رژیم آزموده نشد.

فرضیهٔ علمیِ نشست (تفکرِ غیرخطی):
  mean-reversion فقط در بازارِ RANGE کار می‌کند؛ در بازارِ TREND قوی، RSI در اشباع
  «می‌ماند» و ورودِ خلافِ‌روند ذبح می‌شود (این دقیقاً چیزی است که W3 را در S167 منفی کرد).
  ⇒ راهِ احیا = فیلترِ رژیمِ رنج (ADX پایین + Efficiency-Ratio پایین) که MR را فقط
  در محیطِ طبیعی‌اش (رنج) فعال کند، به‌علاوهٔ قانونِ شناوریِ TP/SL مخصوصِ هر TF.

معیار: RQS+ (۶ گیت، docs/RQS_ROBUST_QUALITY_SCORE.md). موتور: engine/scalp_engine + engine/rqs.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs
from engine import indicators as ind


def efficiency_ratio(close, period):
    """Kaufman Efficiency Ratio: |net change| / sum(|bar change|). نزدیک ۰ = رنج، نزدیک ۱ = روند."""
    change = close.diff(period).abs()
    vol = close.diff().abs().rolling(period).sum()
    return (change / vol.replace(0, np.nan)).fillna(0.0)


def build_signals(df, rsi_period, lo, hi, adx_max=None, er_max=None, adx_period=14, er_period=10):
    """
    RSI-21 cross-back mean-reversion + فیلترِ رژیمِ رنج (همه causal / shift-safe).
      Long : RSI از زیرِ lo به بالا برگردد (rsi_prev<lo و rsi>=lo)
      Short: RSI از بالای hi به پایین برگردد (rsi_prev>hi و rsi<=hi)
      فیلترِ رنج: فقط اگر ADX<=adx_max و ER<=er_max (اگر داده شوند).
    خروجی: long_sig, short_sig (بولین، هم‌طولِ df).
    """
    close = df['close']
    r = ind.rsi(close, rsi_period)
    r_prev = r.shift(1)

    long_raw = (r_prev < lo) & (r >= lo)
    short_raw = (r_prev > hi) & (r <= hi)

    mask = pd.Series(True, index=df.index)
    if adx_max is not None:
        adx_v, _, _ = ind.adx(df, adx_period)
        mask &= (adx_v.shift(1) <= adx_max)   # shift ⇒ رژیمِ کندلِ قبل، بدونِ look-ahead
    if er_max is not None:
        er = efficiency_ratio(close, er_period)
        mask &= (er.shift(1) <= er_max)

    long_sig = (long_raw & mask).fillna(False).values
    short_sig = (short_raw & mask).fillna(False).values
    return long_sig, short_sig


def evaluate(asset, tf_file, rsi_period, lo, hi, sl_pip, tp_pip, max_hold,
             side='long', adx_max=None, er_max=None):
    df = se.load_data(tf_file)
    long_sig, short_sig = build_signals(df, rsi_period, lo, hi, adx_max, er_max)
    if side == 'long':
        short_sig = np.zeros(len(df), dtype=bool)
    elif side == 'short':
        long_sig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, asset,
                                max_hold=max_hold, allow_overlap=False)
    if trades is None or len(trades) == 0:
        return None, trades, df
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip, tp_pip=tp_pip)
    return r, trades, df


# پیکربندیِ TF ها (طلا و یورو)
TFS = {
    'XAUUSD': {
        'M5':  'data/XAUUSD_M5.csv',
        'M15': 'data/XAUUSD_M15.csv',
        'M30': 'data/XAUUSD_M30.csv',
        'H1':  'data/XAUUSD_H1.csv',
        'H4':  'data/XAUUSD_H4.csv',
    },
    'EURUSD': {
        'M5':  'data/EURUSD_M5.csv',
        'M15': 'data/EURUSD_M15.csv',
        'M30': 'data/EURUSD_M30.csv',
    },
}


def baseline_scan():
    """گامِ ۱: بازتولیدِ S167 خام (بدونِ فیلترِ رژیم) روی همهٔ TF — نقطهٔ شروع."""
    print("=" * 100)
    print("BASELINE — S167 RSI-21 MR خام (بدونِ فیلترِ رژیم) — cross-back، long فقط")
    print("=" * 100)
    # TP/SL نزدیکِ S167 (LO25/HI75, SL150/TP225 روی M15). برای TF های دیگر مقیاس ATR بعداً.
    for asset in ['XAUUSD', 'EURUSD']:
        for tf, f in TFS[asset].items():
            if not os.path.exists(f):
                continue
            r, tr, df = evaluate(asset, f, 21, 25, 75, 150, 225, 16, side='long')
            if r is None:
                print(f"{asset}-{tf:4s}: no trades")
                continue
            print(f"{asset}-{tf:4s} | " + rqs.format_report('RSI21-MR-raw', r))


if __name__ == '__main__':
    baseline_scan()
