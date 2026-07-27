# -*- coding: utf-8 -*-
"""
S331 — احیای RQS+ لایهٔ سوختهٔ S132 (Bollinger Squeeze → Breakout)
================================================================================
هدف (طبق User Note این نشست): لایه‌ای با «معاملاتِ زیاد و سودِ زیاد» را برای احیا
انتخاب کن. انتخابِ علمی: **S132 Squeeze→Breakout** روی XAUUSD M15.

  • S132 اصلی: سودِ خالص +$20,435، هر ۴ پنجرهٔ WF مثبت (G4 از پیش پاس!)، اما WR~۴۰٪
    ⇒ با معیارِ قدیمِ WR≥۴۰ ساخته شد و هرگز با RQS+ کامل ممیزی نشد. مانعِ اصلیِ RQS+
    گیتِ G0 (WR≥۶۰٪) است.
  • S225 قبلاً squeeze را با TP کوچک/SL بزرگ (WR بالا) احیا کرد، اما با فدا کردنِ سود
    (net فقط +$401 M15) و افتِ شدیدِ معاملات (n=196). این مسیر با User Note («سودِ زیاد
    + معاملاتِ زیاد») در تضاد است ⇒ ما مسیرِ متفاوتی می‌رویم.

مبنای ریاضی: volatility clustering / اثرِ ARCH (Engle 1982) — دوره‌های کم‌نوسان
سیستماتیک به دوره‌های پرنوسان ختم می‌شوند. BandWidth بولینگر = ۴σ/mid سنجهٔ مستقیمِ
نوسان است؛ کفِ صدکیِ آن = «فنرِ فشرده».

این ماژول: تولیدِ سیگنال squeeze → اجرا با موتورِ رسمیِ scalp_engine.simulate_trades
(forward-safe واقعی) → ارزیابی با engine.rqs.compute_rqs (شش گیتِ رسمی RQS+).
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs


# ------------------------------------------------------------------------------
# اندیکاتورهای پایه (بدونِ look-ahead — همه از داده‌های تا کندلِ i)
# ------------------------------------------------------------------------------
def ema(x, period):
    x = np.asarray(x, dtype=np.float64)
    alpha = 2.0 / (period + 1.0)
    out = np.full(len(x), np.nan)
    if len(x) == 0:
        return out
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = alpha * x[i] + (1 - alpha) * out[i - 1]
    return out


def rsi(x, period=14):
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    delta = np.diff(x)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    for i in range(period, n):
        g = gain[i - 1]
        l = loss[i - 1]
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else np.inf
        out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def atr(df, period=14):
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)
    tr = np.full(n, np.nan)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(n, np.nan)
    if n >= period:
        out[period - 1] = np.nanmean(tr[:period])
        for i in range(period, n):
            out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def adx(df, period=14):
    """ADX + (+DI, -DI) استاندارد Wilder."""
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr = np.zeros(n)
    for i in range(1, n):
        up = h[i] - h[i - 1]
        dn = l[i - 1] - l[i]
        plus_dm[i] = up if (up > dn and up > 0) else 0.0
        minus_dm[i] = dn if (dn > up and dn > 0) else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr_ = np.full(n, np.nan)
    pdi = np.full(n, np.nan)
    mdi = np.full(n, np.nan)
    adx_ = np.full(n, np.nan)
    if n <= period:
        return adx_, pdi, mdi
    atr_[period] = tr[1:period + 1].sum()
    sp = plus_dm[1:period + 1].sum()
    sm = minus_dm[1:period + 1].sum()
    dx_list = []
    for i in range(period + 1, n):
        atr_[i] = atr_[i - 1] - atr_[i - 1] / period + tr[i]
        sp = sp - sp / period + plus_dm[i]
        sm = sm - sm / period + minus_dm[i]
        pdi[i] = 100.0 * sp / atr_[i] if atr_[i] > 0 else 0.0
        mdi[i] = 100.0 * sm / atr_[i] if atr_[i] > 0 else 0.0
        denom = pdi[i] + mdi[i]
        dx = 100.0 * abs(pdi[i] - mdi[i]) / denom if denom > 0 else 0.0
        dx_list.append(dx)
        if len(dx_list) == period:
            adx_[i] = np.mean(dx_list)
        elif len(dx_list) > period:
            adx_[i] = (adx_[i - 1] * (period - 1) + dx) / period
    return adx_, pdi, mdi


def bollinger_bandwidth(c, period=20, k=2.0):
    n = len(c)
    bw = np.full(n, np.nan)
    for i in range(period - 1, n):
        window = c[i - period + 1:i + 1]
        m = window.mean()
        s = window.std(ddof=0)
        bw[i] = (2.0 * k * s) / m if m != 0 else np.nan
    return bw


def rolling_min_percentile(x, lookback):
    n = len(x)
    pct = np.full(n, np.nan)
    for i in range(lookback, n):
        window = x[i - lookback:i + 1]
        w = window[~np.isnan(window)]
        if len(w) < 5 or np.isnan(x[i]):
            continue
        pct[i] = (w <= x[i]).mean()
    return pct


# ------------------------------------------------------------------------------
# سیگنالِ squeeze → breakout (منطقِ S132، بردارِ بولین هم‌طولِ df)
# ------------------------------------------------------------------------------
def build_squeeze_signal(df, bb_period=20, bb_k=2.0, sqz_lookback=100,
                         sqz_pct=0.15, breakout_lookback=10, trend_gate=True,
                         ema_fast=50, ema_slow=200):
    """برمی‌گرداند: long_sig (بولین هم‌طولِ df). فقط long (بایاسِ صعودیِ طلا)."""
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    e_fast = ema(c, ema_fast)
    e_slow = ema(c, ema_slow)
    bw = bollinger_bandwidth(c, bb_period, bb_k)
    bw_pct = rolling_min_percentile(bw, sqz_lookback)
    n = len(df)
    long_sig = np.zeros(n, dtype=bool)
    start = max(bb_period + sqz_lookback, ema_slow, breakout_lookback) + 1
    for i in range(start, n - 1):
        if np.isnan(bw_pct[i - 1]) or bw_pct[i - 1] > sqz_pct:
            continue
        prior_high = h[i - breakout_lookback:i].max()
        if not (c[i] > prior_high):
            continue
        if trend_gate and not (e_fast[i] > e_slow[i]):
            continue
        long_sig[i] = True
    return long_sig


# ------------------------------------------------------------------------------
# ارزیابیِ کامل با RQS+ رسمی
# ------------------------------------------------------------------------------
def evaluate(df, asset, long_sig, sl_pip, tp_pip, max_hold,
             be_trigger_pip=None, trail_pip=None, filt=None):
    """
    filt : بردارِ بولینِ اختیاریِ هم‌طولِ df — فیلترِ بهبود (فقط سیگنال‌هایی که filt=True).
    خروجی: dict نتیجهٔ RQS+.
    """
    ls = long_sig.copy()
    if filt is not None:
        ls = ls & filt
    short_sig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, ls, short_sig, sl_pip, tp_pip, asset,
                                max_hold=max_hold, allow_overlap=False,
                                be_trigger_pip=be_trigger_pip, trail_pip=trail_pip)
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip if np.isscalar(sl_pip) else None,
                        tp_pip=tp_pip if np.isscalar(tp_pip) else None)
    return r, trades


TF_FILES = {
    'M5':  'data/{sym}_M5.csv',
    'M15': 'data/{sym}_M15.csv',
    'M30': 'data/{sym}_M30.csv',
    'H1':  'data/{sym}_H1.csv',
    'H4':  'data/{sym}_H4.csv',
}


def load_tf(sym, tf):
    path = TF_FILES[tf].format(sym=sym)
    if not os.path.exists(path):
        return None
    return se.load_data(path)


if __name__ == '__main__':
    # بازتولیدِ baseline: S132 روی XAUUSD M15 با TP بزرگ (پارامترِ رکورد)، بدون بهبود
    df = load_tf('XAUUSD', 'M15')
    sig = build_squeeze_signal(df, sqz_pct=0.25, breakout_lookback=6)
    print('signals:', int(sig.sum()))
    # پارامترِ رکوردِ S132: TP=300pip, SL=90pip, max_hold=96
    r, tr = evaluate(df, 'XAUUSD', sig, sl_pip=90, tp_pip=300, max_hold=96)
    print(rqs.format_report('S132-baseline M15', r))
    print('gates:', r['gates'])
    print('metrics:', r['metrics'])
