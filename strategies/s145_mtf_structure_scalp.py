# -*- coding: utf-8 -*-
"""
s145_mtf_structure_scalp.py — MTF Structure-Gated Scalp (پاسخِ User Note)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR).**
> WR صرفاً یک عددِ گزارشی است؛ تعدادِ معامله در روز و Profit Factor هم هدف نیستند.
> **ما دنبالِ پول هستیم، نه آمارِ زیبا.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**
================================================================================

انگیزهٔ این نشست (User Note):
  «چرا روی موتورِ اسکالپِ M1/M5 کار نمی‌کنیم؟ چرا همبستگیِ بینِ تایم‌فریم‌ها را
   استفاده نمی‌کنیم؟ روند و سطوحِ حمایت/مقاومت را روی 15m تشخیص بده و طبقِ آن روی
   M1/M5 معامله باز کن!»

شکافِ پژوهشی (تأییدشده از مرورِ کلِ ریپو):
  • M1 هرگز در هیچ استراتژیِ ثبت‌شده‌ای استفاده نشده است.
  • هیچ استراتژی‌ای «سطوحِ S/R + جهتِ روندِ HTF (M15) را استخراج و اجرای ورود را روی
    LTF (M5) انجام دهد» تست نکرده. MTF قبلی فقط MTF-as-feature یا MTF-as-stream بود
    (S33/S34/S35) — نه MTF-as-EXECUTION (تصمیم روی HTF، ماشه روی LTF).

هستهٔ ریاضی/منطقی:
  ۱) روی M15: روند = EMA50 vs EMA200 (فیلترِ جهت).
  ۲) روی M15: سطوحِ حمایت/مقاومتِ افقی از pivotها (بدون look-ahead، engine/structure).
  ۳) نگاشتِ زمانیِ سخت‌گیرانه: هر کندلِ M5 فقط به آخرین کندلِ M15ِ **بسته‌شده پیش از
     شروعِ خودش** وصل می‌شود (M15 که closed_time <= m5_open_time). هیچ نشتِ آینده‌ای.
  ۴) ماشهٔ ورود روی M5:
       - LONG: روندِ M15 صعودی ∧ قیمتِ M5 به حمایتِ M15 «pullback» کرده
         (low نزدیکِ سطحِ حمایت در بازهٔ tol) ∧ کندلِ M5 تأییدِ بازگشت (close>open).
       - SHORT: روندِ M15 نزولی ∧ قیمتِ M5 به مقاومتِ M15 رسیده ∧ close<open.
  ۵) خروجِ «هدفِ پنهان» با TP/SL بر حسبِ ATR(M5) — کاربر عددِ آن را نمی‌بیند.

واقع‌گرایی (هم‌راستا با s91/S144 و حسابِ واقعیِ کاربر):
  • طلا: pip=0.10$، ۱ لات=۱۰۰ اونس، اسپردِ کل=۴ pip (۰.۴۰$)، کمیسیون صفر،
    اسلیپیجِ ۰.۵ pip هر طرف.
  • ورود در open کندلِ بعد از سیگنال (forward-safe).
  • ریسکِ درصدیِ ۱٪ روی ۱۰٬۰۰۰$ (capital_engine).
================================================================================
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine.structure import pivots, sr_levels
from engine.capital_engine import run_capital_backtest

# ---------- مشخصاتِ واقعیِ طلا ----------
PIP = 0.10
CONTRACT = 100.0
SPREAD_PIP = 4.0
SLIP_PIP = 0.5
COST_PRICE = (SPREAD_PIP + 2.0 * SLIP_PIP) * PIP   # هزینهٔ رفت‌وبرگشت بر حسبِ قیمت ($)
INITIAL_CAPITAL = 10000.0
RISK_PCT = 1.0


def load(symbol, tf):
    path = os.path.join(ROOT, 'data', f'{symbol}_{tf}.csv')
    df = pd.read_csv(path)
    df['time'] = pd.to_numeric(df['time'])
    df = df.sort_values('time').reset_index(drop=True)
    return df


def ema_np(x, period):
    x = np.asarray(x, dtype=np.float64)
    out = np.full_like(x, np.nan)
    k = 2.0 / (period + 1.0)
    acc = x[0]
    out[0] = acc
    for i in range(1, len(x)):
        acc = x[i] * k + acc * (1 - k)
        out[i] = acc
    return out


def atr_np(df, period=14):
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(n, np.nan)
    k = 1.0 / period
    acc = tr[:period].mean() if n >= period else tr[0]
    if n >= period:
        out[period - 1] = acc
        for i in range(period, n):
            acc = tr[i] * k + acc * (1 - k)
            out[i] = acc
    return out


def build_m15_context(m15, tf_minutes=15, ema_fast=50, ema_slow=200,
                      piv_left=5, piv_right=5, sr_tol=0.0008, sr_expiry=1500):
    """محاسبهٔ روند + سطوحِ S/R روی M15، همه بدون look-ahead.
    خروجی شامل زمانِ «بسته‌شدنِ» هر کندلِ M15 است تا نگاشتِ forward-safe ممکن شود."""
    m15 = m15.copy().reset_index(drop=True)
    ef = ema_np(m15['close'].values, ema_fast)
    es = ema_np(m15['close'].values, ema_slow)
    trend = np.zeros(len(m15), dtype=np.int8)
    trend[ef > es] = 1
    trend[ef < es] = -1
    m15['trend'] = trend
    piv = pivots(m15, left=piv_left, right=piv_right)
    sr = sr_levels(m15, piv, tol=sr_tol, expiry=sr_expiry)
    m15['support'] = sr['support'].values
    m15['resistance'] = sr['resistance'].values
    # زمانِ بسته‌شدنِ کندل M15 = time (open) + مدتِ کندل
    m15['close_time'] = m15['time'] + tf_minutes * 60
    return m15


def map_m15_to_m5(m5, m15ctx):
    """برای هر کندلِ M5، آخرین کندلِ M15 که close_time <= m5.open_time (سخت‌گیرانه:
    فقط اطلاعاتِ M15ِ کاملاً بسته‌شده پیش از باز شدنِ کندلِ M5)."""
    m5 = m5.copy().reset_index(drop=True)
    ct = m15ctx['close_time'].values
    m5_open = m5['time'].values
    # searchsorted: بزرگترین ایندکسی که close_time <= m5_open
    idx = np.searchsorted(ct, m5_open, side='right') - 1
    valid = idx >= 0
    out = pd.DataFrame(index=m5.index)
    for col in ['trend', 'support', 'resistance']:
        arr = np.full(len(m5), np.nan)
        arr[valid] = m15ctx[col].values[idx[valid]]
        out['m15_' + col] = arr
    return out


def generate_signals(m5, ctx, near_tol=0.0010, confirm=True):
    """تولیدِ سیگنالِ ورود روی M5 با گیتِ ساختارِ M15."""
    n = len(m5)
    close = m5['close'].values
    openv = m5['open'].values
    low = m5['low'].values
    high = m5['high'].values
    trend = ctx['m15_trend'].values
    sup = ctx['m15_support'].values
    res = ctx['m15_resistance'].values

    sig = np.zeros(n, dtype=np.int8)  # +1 long, -1 short
    for i in range(1, n):
        t = trend[i]
        if np.isnan(t):
            continue
        # LONG: روند صعودی + pullback به حمایتِ M15 + کندلِ تأیید صعودی
        if t == 1 and not np.isnan(sup[i]):
            near = abs(low[i] - sup[i]) / sup[i] < near_tol and low[i] <= sup[i] * (1 + near_tol)
            conf = (close[i] > openv[i]) if confirm else True
            if near and conf:
                sig[i] = 1
        # SHORT: روند نزولی + قیمت به مقاومتِ M15 رسیده + کندلِ تأیید نزولی
        elif t == -1 and not np.isnan(res[i]):
            near = abs(high[i] - res[i]) / res[i] < near_tol and high[i] >= res[i] * (1 - near_tol)
            conf = (close[i] < openv[i]) if confirm else True
            if near and conf:
                sig[i] = -1
    return sig


def backtest(m5, sig, atr_arr, tp_mult, sl_mult, max_hold=48):
    """paper broker با خروجِ TP/SL پنهان بر حسبِ ATR. forward-safe.
    ورود در open کندلِ بعد از سیگنال؛ خروج intrabar وقتی TP یا SL لمس شود."""
    openv = m5['open'].values
    high = m5['high'].values
    low = m5['low'].values
    n = len(m5)
    trades = []
    sl_dists = []
    i = 1
    while i < n - 1:
        s = sig[i]
        if s == 0 or np.isnan(atr_arr[i]) or atr_arr[i] <= 0:
            i += 1
            continue
        entry_bar = i + 1
        entry = openv[entry_bar]
        a = atr_arr[i]
        if s == 1:
            tp = entry + tp_mult * a
            sl = entry - sl_mult * a
        else:
            tp = entry - tp_mult * a
            sl = entry + sl_mult * a
        sl_dist = abs(entry - sl)
        exit_price = None
        outcome = None
        exit_bar = None
        for j in range(entry_bar, min(entry_bar + max_hold, n)):
            hi, lo = high[j], low[j]
            if s == 1:
                hit_sl = lo <= sl
                hit_tp = hi >= tp
            else:
                hit_sl = hi >= sl
                hit_tp = lo <= tp
            # محافظه‌کارانه: اگر هر دو در یک کندل، SL اول فرض می‌شود
            if hit_sl:
                exit_price = sl; outcome = 'loss'; exit_bar = j; break
            if hit_tp:
                exit_price = tp; outcome = 'win'; exit_bar = j; break
        if exit_price is None:
            exit_bar = min(entry_bar + max_hold - 1, n - 1)
            exit_price = m5['close'].values[exit_bar]
            outcome = 'win' if ((exit_price - entry) * s) > 0 else 'loss'
        # pnl خام روی ۱ اونس (به دلار) با کسرِ هزینهٔ رفت‌وبرگشت
        raw = (exit_price - entry) * s - COST_PRICE
        trades.append({'pnl': raw, 'signal_bar': i, 'exit_bar': exit_bar, 'outcome': outcome})
        sl_dists.append(sl_dist)
        i = exit_bar + 1   # بدونِ همپوشانی
    tr = pd.DataFrame(trades)
    return tr, np.array(sl_dists)


def run_capital(tr, sl_dists):
    if len(tr) == 0:
        return {'net_profit': 0.0, 'n_trades': 0, 'win_rate': 0.0,
                'profit_factor': 0.0, 'max_dd_pct': 0.0, 'sharpe': 0.0}, np.array([INITIAL_CAPITAL])
    stats, eq = run_capital_backtest(tr, sl_dists, initial_capital=INITIAL_CAPITAL,
                                     risk_pct=RISK_PCT, commission_per_lot=0.0,
                                     compounding=True, contract_size=CONTRACT)
    return stats, eq


if __name__ == '__main__':
    print("Loading XAUUSD M5 + M15 ...")
    m5 = load('XAUUSD', 'M5')
    m15 = load('XAUUSD', 'M15')
    print(f"M5 bars: {len(m5)}, M15 bars: {len(m15)}")
    print(f"M5 range: {pd.to_datetime(m5['time'].iloc[0], unit='s')} -> {pd.to_datetime(m5['time'].iloc[-1], unit='s')}")

    ctx15 = build_m15_context(m15)
    ctx = map_m15_to_m5(m5, ctx15)
    atr_arr = atr_np(m5, 14)

    # جاروِ اولیهٔ پارامترها (روی کلِ داده — فقط برای دیدِ کلی)
    sig = generate_signals(m5, ctx, near_tol=0.0010, confirm=True)
    print(f"raw signals: {int((sig!=0).sum())} (long={int((sig==1).sum())}, short={int((sig==-1).sum())})")

    tr, sld = backtest(m5, sig, atr_arr, tp_mult=2.0, sl_mult=1.5, max_hold=48)
    stats, eq = run_capital(tr, sld)
    print(f"\nBASELINE (tp2.0/sl1.5): netP={stats['net_profit']:+.0f}$ n={stats['n_trades']} "
          f"WR={stats['win_rate']:.1f}% PF={stats.get('profit_factor',0):.2f} "
          f"maxDD={stats.get('max_dd_pct',0):.1f}%")
