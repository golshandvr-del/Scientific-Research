# -*- coding: utf-8 -*-
"""
s337_tf_ladder.py — نردبانِ تایم‌فریم: آیا WRِ ذاتی با بالا رفتنِ TF بالا می‌رود؟
====================================================================================
تزِ مرکزیِ این نشست (پاسخ به «چرا به نتیجه نمی‌رسیم؟»):

  قیدِ ریاضیِ G1:  WR_breakeven = SL / (SL + TP)
  با TP/SL متوازن روی M5 → WR ذاتی حولِ ۵۰٪ قفل می‌شود (S336/S337 اثبات کرد).
  فرضیه: علتش «نویز و تقارنِ افقِ کوتاه» است، نه نبودِ edge. پس روی TFهای بلندتر،
  همان منطقِ trend-continuation باید WRِ ذاتیِ بالاتری بدهد چون edge/noise بزرگ‌تر است.

این اسکریپت *یک* منطقِ ثابت (buy-the-dip در روندِ تمیزِ صعودی + sell-the-rip در نزولیِ تمیز)
را روی نردبانِ TF اجرا می‌کند و WR/PF را برحسبِ TF گزارش می‌دهد. صرفاً تشخیصی — نه لایهٔ نهایی.
هدف: دیدنِ *شیبِ* WR نسبت به TF. اگر صعودی بود، مسیرِ نشست روشن می‌شود.

هیچ اعدادِ رند: TP/SL بر حسبِ ATR (شناور per-TF) تعریف می‌شوند (رفعِ اشتباه ۶ و ۷).
همه اندیکاتورها shift(1) → بدون look-ahead.
"""
import numpy as np
import pandas as pd
from engine import scalp_engine as se, rqs
from engine import indicator_bank as ib

TF_BARS_PER_DAY = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24, 'H4': 6, 'D1': 1}
TFS = ['M5', 'M15', 'M30', 'H1', 'H4']


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def wr_pf(trades):
    if trades is None or len(trades) == 0:
        return 0, 0.0, 0.0
    wr = (trades['outcome'] == 'win').mean() * 100
    wins = trades.loc[trades.pnl_pip > 0, 'pnl_pip'].sum()
    loss = -trades.loc[trades.pnl_pip <= 0, 'pnl_pip'].sum()
    pf = wins / loss if loss > 0 else 9.99
    return len(trades), wr, pf


def atr_pips(df, asset, period=14):
    """ATR بر حسبِ pip (برای XAU: 1 pip = 0.1$؛ ATR در $ تقسیم بر 0.1)."""
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().values
    pip = 0.1 if 'XAU' in asset else 0.0001
    return atr / pip


def run_tf(asset, tf, r2_min=0.55, hurst_min=0.5, sl_mult=1.5, tp_mult=1.5):
    """یک منطقِ ثابت روی یک TF. TP/SL بر حسبِ ضریبِ ATRِ میانه (شناور per-TF)."""
    df = load(asset, tf)
    n = len(df)
    if n < 500:
        return None
    days = n / TF_BARS_PER_DAY[tf]

    close = df['close'].values
    hurst = ib.compute('hurst', df).shift(1).values
    r2 = ib.compute('r2_fib_55', df).shift(1).values
    ema_dist = ib.compute('ema_dist_atr', df).shift(1).values      # کششِ نرمال‌شده به ATR
    hma = ib.compute('hma_fib_34', df)
    slope = (hma - hma.shift(3)).shift(1).values                   # جهتِ روند

    atrp = atr_pips(df, asset)
    sl = float(np.nanmedian(atrp)) * sl_mult
    tp = float(np.nanmedian(atrp)) * tp_mult
    if not np.isfinite(sl) or sl < 1:
        return None

    trend_up = (hurst > hurst_min) & (r2 > r2_min) & (slope > 0)
    trend_dn = (hurst > hurst_min) & (r2 > r2_min) & (slope < 0)

    # buy-the-dip: روندِ صعودیِ تمیز + پول‌بکِ کوچک (کشش کمی منفی)
    long_sig = trend_up & (ema_dist < -0.2) & (ema_dist > -1.2)
    # sell-the-rip: روندِ نزولیِ تمیز + جهشِ کوچک
    short_sig = trend_dn & (ema_dist > 0.2) & (ema_dist < 1.2)

    long_sig = pd.Series(np.nan_to_num(long_sig, nan=0).astype(bool))
    short_sig = pd.Series(np.nan_to_num(short_sig, nan=0).astype(bool))

    mh = 24  # حداکثر نگه‌داری
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset, mh, False)
    if tr is None or len(tr) == 0:
        return dict(tf=tf, days=days, n=0, wr=0, pf=0, sl=sl, tp=tp, perday=0)
    tr = tr.copy(); tr['tp_pip'] = float(tp)
    ntr, wr, pf = wr_pf(tr)
    return dict(tf=tf, days=days, n=ntr, wr=wr, pf=pf, sl=sl, tp=tp,
                perday=ntr / days if days else 0, trades=tr)


def ladder(asset='XAUUSD'):
    print(f"\n=== TF LADDER {asset} === تزِ نشست: آیا WRِ ذاتی با TF بالا می‌رود؟")
    print(f"منطقِ ثابت: buy-dip/sell-rip در روندِ تمیز (hurst>0.5 & r2>0.55). TP=SL=1.5×ATR(median) شناورِ per-TF.\n")
    print(f"{'TF':>4} {'days':>6} {'n':>6} {'/day':>6} {'WR%':>6} {'PF':>6} {'SLpip':>7} {'TPpip':>7} {'RQS':>6} {'gate':>6}")
    print("-" * 70)
    for tf in TFS:
        try:
            r = run_tf(asset, tf)
        except Exception as e:
            print(f"{tf:>4}  ERR {e}")
            continue
        if r is None:
            print(f"{tf:>4}  (داده ناکافی)")
            continue
        rq = 0.0; gate = '------'
        if r['n'] >= 20:
            res = rqs.compute_rqs(r['trades'], asset, r['sl'], r['tp'])
            rq = res.get('rqs_plus', res.get('rqs', 0)) if isinstance(res, dict) else 0
            g = res.get('gates', {}) if isinstance(res, dict) else {}
            gate = ''.join('1' if g.get(k) else '0' for k in sorted(g)) if g else '------'
        print(f"{r['tf']:>4} {r['days']:>6.0f} {r['n']:>6} {r['perday']:>6.2f} "
              f"{r['wr']:>6.1f} {r['pf']:>6.2f} {r['sl']:>7.1f} {r['tp']:>7.1f} {rq:>6.1f} {gate:>6}")


if __name__ == '__main__':
    import sys
    a = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    ladder(a)


def run_tf_v2(asset, tf, mode, r2_min=0.55, hurst_th=0.5, sl_mult=1.5, tp_mult=1.5, mh=24):
    """چند منطق را روی یک TF می‌سنجد. mode:
       'fade_trend'  = معکوسِ v1 (fade پول‌بک؛ یعنی در روندِ صعودی SHORT بزن روی جهش)
       'mr_extreme'  = mean-reversion در رژیمِ ضدروند (hurst<th) روی کششِ افراطی
       'breakout'    = شکستِ کانال در روندِ تمیز (follow با تریگرِ مومنتوم)
    """
    df = load(asset, tf); n = len(df)
    if n < 500: return None
    days = n / TF_BARS_PER_DAY[tf]
    hurst = ib.compute('hurst', df).shift(1).values
    r2 = ib.compute('r2_fib_55', df).shift(1).values
    ema_dist = ib.compute('ema_dist_atr', df).shift(1).values
    hma = ib.compute('hma_fib_34', df)
    slope = (hma - hma.shift(3)).shift(1).values
    atrp = atr_pips(df, asset)
    sl = float(np.nanmedian(atrp)) * sl_mult
    tp = float(np.nanmedian(atrp)) * tp_mult
    if not np.isfinite(sl) or sl < 1: return None

    if mode == 'fade_trend':
        up = (hurst > hurst_th) & (r2 > r2_min) & (slope > 0)
        dn = (hurst > hurst_th) & (r2 > r2_min) & (slope < 0)
        short_sig = up & (ema_dist < -0.2) & (ema_dist > -1.2)   # معکوسِ v1
        long_sig  = dn & (ema_dist > 0.2) & (ema_dist < 1.2)
    elif mode == 'mr_extreme':
        # رژیمِ بازگشتی (hurst پایین) + کششِ افراطی → fade
        long_sig  = (hurst < hurst_th) & (ema_dist < -2.0)       # افتِ شدید → LONG
        short_sig = (hurst < hurst_th) & (ema_dist > 2.0)        # جهشِ شدید → SHORT
    elif mode == 'breakout':
        up = (hurst > hurst_th) & (r2 > r2_min) & (slope > 0)
        dn = (hurst > hurst_th) & (r2 > r2_min) & (slope < 0)
        long_sig  = up & (ema_dist > 0.5)                         # follow با مومنتوم
        short_sig = dn & (ema_dist < -0.5)
    else:
        return None

    long_sig = pd.Series(np.nan_to_num(long_sig, nan=0).astype(bool))
    short_sig = pd.Series(np.nan_to_num(short_sig, nan=0).astype(bool))
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset, mh, False)
    if tr is None or len(tr) == 0:
        return dict(tf=tf, days=days, n=0, wr=0, pf=0, sl=sl, tp=tp, perday=0, mode=mode)
    tr = tr.copy(); tr['tp_pip'] = float(tp)
    ntr, wr, pf = wr_pf(tr)
    return dict(tf=tf, days=days, n=ntr, wr=wr, pf=pf, sl=sl, tp=tp,
                perday=ntr/days if days else 0, mode=mode, trades=tr)


def ladder_v2(asset='XAUUSD'):
    print(f"\n=== TF LADDER v2 {asset} === سه منطقِ متفاوت روی نردبانِ TF")
    print(f"{'mode':>12} {'TF':>4} {'n':>6} {'/day':>6} {'WR%':>6} {'PF':>6} {'RQS':>6}")
    print("-" * 52)
    for mode in ['fade_trend', 'mr_extreme', 'breakout']:
        for tf in TFS:
            try:
                r = run_tf_v2(asset, tf, mode)
            except Exception as e:
                print(f"{mode:>12} {tf:>4}  ERR {str(e)[:30]}"); continue
            if r is None: continue
            rq = 0.0
            if r['n'] >= 20:
                res = rqs.compute_rqs(r['trades'], asset, r['sl'], r['tp'])
                rq = res.get('rqs_plus', res.get('rqs', 0)) if isinstance(res, dict) else 0
            print(f"{r['mode']:>12} {r['tf']:>4} {r['n']:>6} {r['perday']:>6.2f} "
                  f"{r['wr']:>6.1f} {r['pf']:>6.2f} {rq:>6.1f}")
        print()


if __name__ == '__main__' and len(__import__('sys').argv) > 2 and __import__('sys').argv[2] == 'v2':
    ladder_v2(__import__('sys').argv[1])
