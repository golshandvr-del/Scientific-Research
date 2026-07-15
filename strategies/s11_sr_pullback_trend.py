"""
استراتژی ۱۱: S/R Pullback در روند صعودی + پنجره طلایی (Price Action ساختاری)
============================================================================
ترکیب اکشن قیمت (retest/pullback به حمایت) با contextهای اثبات‌شده‌ی پروژه:
- روند صعودی ساختاری: close > EMA50 > EMA200
- پنجره طلایی: ساعت ۱۹–۲۳ UTC (edge ساعتی اثبات‌شده در استراتژی‌های ۶–۹)
- ورود price-action: قیمت به یک سطح حمایت فعال pullback کرده (فاصله < 0.5×ATR)
- فیلتر «فضای رشد»: فاصله تا نزدیک‌ترین مقاومت بالای قیمت > room_min×ATR

منطق: در روند صعودی، وقتی قیمت در ساعات پرنوسان به یک حمایت واقعی برمی‌گردد و
فضای کافی تا مقاومت بعدی دارد، احتمال ادامه‌ی حرکت صعودی (لمس TP قبل از SL) بالاست.

اعتبارسنجی: بک‌تست کامل + تقسیم زمانی (نیمه اول/دوم) برای بررسی پایداری.
همه‌ی سیگنال‌ها بدون look-ahead (سطوح از pivot تأییدشده، contextها از داده گذشته).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scipy import stats as sps
from backtest import load_data, run_backtest
import indicators as ind
import structure as st


def build(df, left=6, right=6, tol=0.0008, expiry=1500):
    piv = st.pivots(df, left=left, right=right)
    sr = st.sr_levels(df, piv, tol=tol, expiry=expiry)
    atr = ind.atr(df, 14)
    ema50 = ind.ema(df['close'], 50)
    ema200 = ind.ema(df['close'], 200)
    rsi = ind.rsi(df['close'], 14)
    return sr, atr, ema50, ema200, rsi


def signals(df, sr, atr, ema50, ema200, rsi,
            near_max=0.5, room_min=2.0, rsi_max=100, h_lo=19, h_hi=23):
    close = df['close'].values
    hour = df['dt'].dt.hour.values
    sup = sr['support'].values
    res = sr['resistance'].values
    a = atr.values
    dist_sup = (close - sup) / a
    room = (res - close) / a
    near_sup = (dist_sup > 0) & (dist_sup < near_max)
    uptrend = (close > ema50.values) & (ema50.values > ema200.values)
    golden = (hour >= h_lo) & (hour <= h_hi)
    room_ok = room > room_min
    rsi_ok = rsi.values < rsi_max
    sig = near_sup & uptrend & golden & room_ok & rsi_ok
    sig[:300] = False
    return sig


def bt(df, sig, atr, tp_mult, sl_mult, spread=0.20, max_hold=96):
    atr_v = atr.values
    stats, tr = run_backtest(
        df, sig, sl_points=None, tp_points=None, direction='long',
        spread=spread, max_hold=max_hold, allow_overlap=False,
        sl_series=atr_v*sl_mult, tp_series=atr_v*tp_mult)
    return stats, tr


def pval_wr(n_win, n, be):
    """آزمون دوجمله‌ای یک‌طرفه: P(WR > breakeven) شانسی نیست."""
    if n == 0:
        return 1.0
    return sps.binomtest(n_win, n, be, alternative='greater').pvalue


if __name__ == '__main__':
    df = load_data()
    sr, atr, ema50, ema200, rsi = build(df)
    print(f"داده: {len(df)} کندل\n")

    print("=== جاروب پارامترها (LONG, TP1.0/SL2.0, BE=66.7%) ===")
    configs = []
    for near in [0.5, 0.7, 1.0]:
        for room in [1.5, 2.0, 3.0]:
            for rmax in [100, 55, 45]:
                sig = signals(df, sr, atr, ema50, ema200, rsi,
                              near_max=near, room_min=room, rsi_max=rmax)
                s, tr = bt(df, sig, atr, 1.0, 2.0)
                if s['n_trades'] >= 60:
                    be = 2.0/3.0
                    nwin = int(round(s['win_rate']/100*s['n_trades']))
                    p = pval_wr(nwin, s['n_trades'], be)
                    configs.append((near, room, rmax, s, p))

    configs.sort(key=lambda x: -x[3]['win_rate'])
    print(f"{'near':>5}{'room':>6}{'rsi':>5}{'n':>6}{'WR%':>8}{'exp$':>8}{'PnL$':>8}{'pval':>8}")
    for near, room, rmax, s, p in configs:
        print(f"{near:>5}{room:>6}{rmax:>5}{s['n_trades']:>6}"
              f"{s['win_rate']:>8.2f}{s['expectancy']:>8.3f}"
              f"{s['total_pnl']:>8.0f}{p:>8.3f}")
