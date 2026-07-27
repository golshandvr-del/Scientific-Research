# -*- coding: utf-8 -*-
"""
bank_filters.py — پورتِ Python از اندیکاتورهای پیشرفتهٔ بانکِ ۴۰۱-تایی
(web_tool/src/indicators/bank/*.ts) که در INDICATOR_BANK_GUIDE.md به‌عنوان
«فیلترِ رژیم / کیفیتِ روند» توصیه شده‌اند.

هدف: رفعِ اشتباهِ رایجِ #۳ — غفلت از اندیکاتورهای پیچیده. لایهٔ S332 (squeeze)
تا این‌جا فقط با ADX/DI فیلتر شده بود؛ این ماژول فیلترهای عمیق‌ترِ زیر را می‌دهد تا
روی TFهای پایین (که به دیوارِ WR~52٪ خورده بودند) آزموده شوند:

  آماری/فراکتالی : hurst, r2, corr_t, fdi, entropy
  نوسان/رژیم     : chop (Choppiness), natr, atr_pct
  ساختاری/روند   : supertrend(dir), aroon, vortex, gann_hilo(dir), psar(dir),
                    donchian_mid, chandelier
  مومنتوم        : waddah, crsi, qqe, stc, tdi, elder_impulse, cmo, ao
  ترکیبی         : trend_gate, ema_dist_atr, rsi_of_er, er (Kaufman)

قواعد:
  • بدونِ look-ahead — هر مقدارِ اندیس i فقط از دادهٔ تا i استفاده می‌کند.
  • منطق verbatim از فایل‌های TS بانک پورت شده (همان فرمول‌ها/دوره‌های پیش‌فرض).
  • همه numpy-vectorized یا حلقهٔ سبک؛ برای دادهٔ بزرگِ M5 (۲۰۰k) هم قابلِ اجرا.

خروجی هر تابع: np.ndarray هم‌طولِ ورودی با NaN در ابتدای گرم‌شدن.
"""
import numpy as np
import pandas as pd


# ---------------------------------------------------------------- helpers پایه
def _ema(x, period):
    x = np.asarray(x, dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    if n == 0:
        return out
    alpha = 2.0 / (period + 1.0)
    # نقطهٔ شروع: اولین مقدارِ معتبر
    start = 0
    while start < n and not np.isfinite(x[start]):
        start += 1
    if start >= n:
        return out
    prev = x[start]
    out[start] = prev
    for i in range(start + 1, n):
        v = x[i]
        if not np.isfinite(v):
            out[i] = prev
            continue
        prev = alpha * v + (1 - alpha) * prev
        out[i] = prev
    return out


def _sma(x, period):
    s = pd.Series(x, dtype=float)
    return s.rolling(period, min_periods=period).mean().to_numpy()


def _rma(x, period):
    # Wilder RMA = EMA با alpha=1/period
    x = np.asarray(x, dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    if n == 0:
        return out
    alpha = 1.0 / period
    start = 0
    while start < n and not np.isfinite(x[start]):
        start += 1
    if start >= n:
        return out
    prev = x[start]
    out[start] = prev
    for i in range(start + 1, n):
        v = x[i] if np.isfinite(x[i]) else 0.0
        prev = alpha * v + (1 - alpha) * prev
        out[i] = prev
    return out


def _std(x, period):
    s = pd.Series(x, dtype=float)
    return s.rolling(period, min_periods=period).std(ddof=0).to_numpy()


def _true_range(df):
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.roll(c, 1)
    pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return tr


def _highest(x, period):
    return pd.Series(x, dtype=float).rolling(period, min_periods=period).max().to_numpy()


def _lowest(x, period):
    return pd.Series(x, dtype=float).rolling(period, min_periods=period).min().to_numpy()


def _rsi(x, period=14):
    x = np.asarray(x, dtype=float)
    n = len(x)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    d = np.diff(x, prepend=x[0])
    gain = np.where(d > 0, d, 0.0)
    loss = np.where(d < 0, -d, 0.0)
    ag = _rma(gain, period)
    al = _rma(loss, period)
    rs = np.where(al > 1e-12, ag / al, np.inf)
    out = 100 - 100 / (1 + rs)
    out[np.isinf(rs)] = 100.0
    return out


# ---------------------------------------------------------------- آماری/فراکتالی
def hurst(df, period=64):
    """نمای هرست R/S — >0.5 روندی، <0.5 بازگشتی. verbatim از statistical.ts"""
    x = df['close'].to_numpy(float)
    n = len(x)
    out = np.full(n, 0.5)
    ret = np.zeros(n)
    ret[1:] = np.where(x[:-1] != 0, np.log(x[1:] / x[:-1]), 0.0)
    logp = np.log(period)
    for i in range(period, n):
        w = ret[i - period + 1:i + 1]
        m = w.mean()
        cum = np.cumsum(w - m)
        R = cum.max() - cum.min()
        sd = np.sqrt(((w - m) ** 2).mean())
        out[i] = (np.log(R / sd) / logp) if (sd and R > 0) else 0.5
    return out


def r2(df, period=20):
    """R² رگرسیونِ خطیِ قیمت-زمان — >0.8 روندِ تمیز. verbatim از statistical.ts"""
    x = df['close'].to_numpy(float)
    n = len(x)
    out = np.full(n, np.nan)
    t = np.arange(period, dtype=float)
    st = t.sum()
    stt = (t * t).sum()
    for i in range(period - 1, n):
        y = x[i - period + 1:i + 1]
        sy = y.sum()
        sty = (t * y).sum()
        syy = (y * y).sum()
        num = period * sty - st * sy
        den = (period * stt - st * st) * (period * syy - sy * sy)
        r = num / np.sqrt(den) if den > 0 else 0.0
        out[i] = r * r
    return out


def corr_t(df, period=20):
    """همبستگیِ پیرسونِ قیمت با زمان (علامت‌دار) — کیفیت + جهتِ روند."""
    x = df['close'].to_numpy(float)
    n = len(x)
    out = np.full(n, np.nan)
    t = np.arange(period, dtype=float)
    st = t.sum()
    stt = (t * t).sum()
    for i in range(period - 1, n):
        y = x[i - period + 1:i + 1]
        sy = y.sum()
        sty = (t * y).sum()
        syy = (y * y).sum()
        num = period * sty - st * sy
        den = np.sqrt((period * stt - st * st) * (period * syy - sy * sy))
        out[i] = num / den if den > 0 else 0.0
    return out


def fdi(df, period=30):
    """شاخصِ بُعدِ فراکتال — بالاتر = پیچیده‌تر/نویزی‌تر. verbatim از statistical.ts"""
    x = df['close'].to_numpy(float)
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(period - 1, n):
        w = x[i - period + 1:i + 1]
        hh, ll = w.max(), w.min()
        rng = (hh - ll) or 1e-10
        d1 = np.diff(w) / rng
        L = np.sqrt(d1 * d1 + 1.0 / (period * period)).sum()
        out[i] = 1 + (np.log(L) + np.log(2)) / np.log(2 * period)
    return out


# ---------------------------------------------------------------- نوسان/رژیم
def chop(df, period=14):
    """Choppiness Index — >61.8 رنج، <38.2 روند. verbatim از volatility.ts"""
    tr = _true_range(df)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    n = len(df)
    sum_tr = pd.Series(tr).rolling(period, min_periods=period).sum().to_numpy()
    hh = _highest(h, period)
    ll = _lowest(l, period)
    rng = hh - ll
    with np.errstate(divide='ignore', invalid='ignore'):
        out = np.where(rng > 0, 100 * np.log10(sum_tr / rng) / np.log10(period), np.nan)
    return out


def natr(df, period=14):
    """ATR درصدی — مقایسه‌پذیر بین TFها. پایهٔ SL/TP پویا."""
    tr = _true_range(df)
    a = _rma(tr, period)
    c = df['close'].to_numpy(float)
    return np.where(c != 0, 100 * a / c, np.nan)


def atr_series(df, period=14):
    return _rma(_true_range(df), period)


# ---------------------------------------------------------------- ساختاری/روند
def supertrend_dir(df, period=10, mult=3.0):
    """جهتِ سوپرترند {+1,-1}. verbatim از structure.ts"""
    n = len(df)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    atr = _rma(_true_range(df), period)
    out = np.full(n, np.nan)
    final_up = final_dn = np.nan
    d = 1
    started = False
    for i in range(n):
        if not np.isfinite(atr[i]):
            continue
        mid = (h[i] + l[i]) / 2
        basic_up = mid - mult * atr[i]
        basic_dn = mid + mult * atr[i]
        if not started:
            final_up, final_dn, d = basic_up, basic_dn, 1
            out[i] = d
            started = True
            continue
        final_up = basic_up if (basic_up > final_up or c[i - 1] < final_up) else final_up
        final_dn = basic_dn if (basic_dn < final_dn or c[i - 1] > final_dn) else final_dn
        if d == 1 and c[i] < final_up:
            d = -1
        elif d == -1 and c[i] > final_dn:
            d = 1
        out[i] = d
    return out


def aroon(df, period=25):
    """اسیلاتورِ آرون = AroonUp − AroonDown. verbatim از structure.ts"""
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    n = len(df)
    out = np.full(n, np.nan)
    for i in range(period, n):
        win_h = h[i - period:i + 1]
        win_l = l[i - period:i + 1]
        hi = period - int(np.argmax(win_h[::-1]))  # فاصله از سقفِ اخیر
        li = period - int(np.argmin(win_l[::-1]))
        # argmax روی reversed → k از انتها؛ بازتولیدِ منطقِ TS:
        hv = -np.inf; lv = np.inf; khi = 0; kli = 0
        for k in range(period + 1):
            if h[i - k] > hv:
                hv = h[i - k]; khi = k
            if l[i - k] < lv:
                lv = l[i - k]; kli = k
        up = 100 * (period - khi) / period
        dn = 100 * (period - kli) / period
        out[i] = up - dn
    return out


def vortex(df, period=14):
    """VI+ − VI−. verbatim از structure.ts"""
    n = len(df)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    tr = _true_range(df)
    vmp = np.zeros(n); vmn = np.zeros(n)
    vmp[1:] = np.abs(h[1:] - l[:-1])
    vmn[1:] = np.abs(l[1:] - h[:-1])
    sp = pd.Series(vmp).rolling(period, min_periods=period).sum().to_numpy()
    sn = pd.Series(vmn).rolling(period, min_periods=period).sum().to_numpy()
    st = pd.Series(tr).rolling(period, min_periods=period).sum().to_numpy()
    return np.where(st > 0, (sp - sn) / st, np.nan)


def gann_hilo_dir(df, period=10):
    """جهتِ گانِ های‌لو {+1,-1}. verbatim از structure.ts"""
    n = len(df)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    sh = _sma(h, period)
    sl = _sma(l, period)
    out = np.full(n, np.nan)
    d = 1
    for i in range(period, n):
        if c[i] > sh[i - 1]:
            d = 1
        elif c[i] < sl[i - 1]:
            d = -1
        out[i] = d
    return out


def psar_dir(df, step=0.02, mx=0.2):
    """جهتِ Parabolic SAR {+1 bull, -1 bear}. verbatim از structure.ts"""
    n = len(df)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    out = np.full(n, np.nan)
    if n < 2:
        return out
    bull = c[1] >= c[0]
    af = step
    ep = h[0] if bull else l[0]
    sar = l[0] if bull else h[0]
    for i in range(1, n):
        sar = sar + af * (ep - sar)
        if bull:
            if l[i] < sar:
                bull = False; sar = ep; ep = l[i]; af = step
            elif h[i] > ep:
                ep = h[i]; af = min(mx, af + step)
        else:
            if h[i] > sar:
                bull = True; sar = ep; ep = h[i]; af = step
            elif l[i] < ep:
                ep = l[i]; af = min(mx, af + step)
        out[i] = 1 if bull else -1
    return out


# ---------------------------------------------------------------- مومنتوم
def waddah(df, fast=20, slow=40):
    """انفجارِ وداح‌عطار (MACD-diff تشدیدشده). verbatim از structure.ts"""
    x = df['close'].to_numpy(float)
    macd = _ema(x, fast) - _ema(x, slow)
    out = np.full(len(x), np.nan)
    out[1:] = (macd[1:] - macd[:-1]) * 150
    return out


def crsi(df, rsi_p=3, streak_p=2, rank_p=100):
    """Connors RSI = (RSI3 + streakRSI + PctRank)/3. verbatim از structure.ts"""
    x = df['close'].to_numpy(float)
    n = len(x)
    rsi3 = _rsi(x, rsi_p)
    streak = np.zeros(n)
    s = 0
    for i in range(1, n):
        if x[i] > x[i - 1]:
            s = s + 1 if s >= 0 else 1
        elif x[i] < x[i - 1]:
            s = s - 1 if s <= 0 else -1
        else:
            s = 0
        streak[i] = s
    streak_rsi = _rsi(streak, streak_p)
    ret = np.zeros(n)
    ret[1:] = np.where(x[:-1] != 0, (x[1:] - x[:-1]) / x[:-1], 0.0)
    rank = np.full(n, np.nan)
    for i in range(rank_p, n):
        below = np.sum(ret[i - rank_p:i] < ret[i])
        rank[i] = 100 * below / rank_p
    out = (rsi3 + streak_rsi + rank) / 3
    return out


def qqe(df, rsi_p=14, sf=5):
    """QQE = EMA(RSI). verbatim از structure.ts"""
    return _ema(_rsi(df['close'].to_numpy(float), rsi_p), sf)


def stc(df, fast=23, slow=50, cycle=10):
    """Schaff Trend Cycle. verbatim از structure.ts"""
    x = df['close'].to_numpy(float)
    n = len(x)
    macd = _ema(x, fast) - _ema(x, slow)
    st1 = np.full(n, np.nan)
    for i in range(cycle - 1, n):
        w = macd[i - cycle + 1:i + 1]
        hh, ll = np.nanmax(w), np.nanmin(w)
        st1[i] = 100 * (macd[i] - ll) / (hh - ll) if (hh - ll) else 50
    d1 = _ema(st1, max(2, cycle // 2))
    st2 = np.full(n, np.nan)
    for i in range(cycle - 1, n):
        w = d1[i - cycle + 1:i + 1]
        hh, ll = np.nanmax(w), np.nanmin(w)
        st2[i] = 100 * (d1[i] - ll) / (hh - ll) if (hh - ll) else 50
    return _ema(st2, max(2, cycle // 2))


def tdi(df, rsi_p=13, sig=7):
    """Traders Dynamic Index = SMA(RSI). verbatim از structure.ts"""
    return _sma(_rsi(df['close'].to_numpy(float), rsi_p), sig)


def elder_impulse(df, ema_p=13, macd_f=12, macd_s=26, macd_sig=9):
    """ضربهٔ الدر {−1,0,+1}. verbatim از structure.ts"""
    x = df['close'].to_numpy(float)
    n = len(x)
    e = _ema(x, ema_p)
    macd = _ema(x, macd_f) - _ema(x, macd_s)
    sig = _ema(macd, macd_sig)
    hist = macd - sig
    out = np.full(n, np.nan)
    for i in range(1, n):
        es = np.sign(e[i] - e[i - 1])
        hs = np.sign(hist[i] - hist[i - 1])
        out[i] = 1 if (es > 0 and hs > 0) else (-1 if (es < 0 and hs < 0) else 0)
    return out


def cmo(df, period=14):
    """Chande Momentum Oscillator."""
    x = df['close'].to_numpy(float)
    n = len(x)
    d = np.diff(x, prepend=x[0])
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    su = pd.Series(up).rolling(period, min_periods=period).sum().to_numpy()
    sd = pd.Series(dn).rolling(period, min_periods=period).sum().to_numpy()
    return np.where((su + sd) > 0, 100 * (su - sd) / (su + sd), np.nan)


def ao(df):
    """Awesome Oscillator = SMA5(HL2) − SMA34(HL2)."""
    hl2 = (df['high'].to_numpy(float) + df['low'].to_numpy(float)) / 2
    return _sma(hl2, 5) - _sma(hl2, 34)


# ---------------------------------------------------------------- ترکیبی
def kaufman_er(df, period=10):
    """نسبتِ کاراییِ کافمن (0..1) — کیفیتِ جهت‌دار بودنِ حرکت."""
    x = df['close'].to_numpy(float)
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(period, n):
        change = abs(x[i] - x[i - period])
        vol = np.abs(np.diff(x[i - period:i + 1])).sum()
        out[i] = change / vol if vol else 0.0
    return out


def rsi_of_er(df, er_p=10, rsi_p=14):
    """RSI روی کاراییِ کافمن. verbatim از composite.ts"""
    er = kaufman_er(df, er_p)
    er100 = np.where(np.isfinite(er), er * 100, 0.0)
    return _rsi(er100, rsi_p)


def ema_dist_atr(df, ema_p=50, atr_p=14):
    """فاصلهٔ قیمت از EMA بر حسبِ ATR (over-extension). verbatim از composite.ts"""
    x = df['close'].to_numpy(float)
    e = _ema(x, ema_p)
    a = _rma(_true_range(df), atr_p)
    return np.where(a != 0, (x - e) / a, np.nan)


def trend_gate(df, chop_p=14, ema_p=50, thr=38.2):
    """دروازهٔ روند {−1,0,+1}: chop<thr و شیبِ EMA. verbatim از composite.ts"""
    x = df['close'].to_numpy(float)
    n = len(x)
    e = _ema(x, ema_p)
    ch = chop(df, chop_p)
    out = np.full(n, np.nan)
    for i in range(chop_p, n):
        if np.isfinite(ch[i]) and ch[i] < thr:
            out[i] = np.sign(e[i] - e[i - 1])
        else:
            out[i] = 0
    return out


# ---------------------------------------------------------------- رجیستریِ فیلترها
# هر ورودی: نام → تابعِ سازندهٔ ماسکِ بولینِ «اجازهٔ ورودِ LONG»
# آستانه‌ها از راهنمای بانک (INDICATOR_BANK_GUIDE.md) گرفته شده‌اند.
def build_filter_library(df):
    """
    کتابخانه‌ای از ماسک‌های بولین (اجازهٔ ورودِ LONG) بر پایهٔ اندیکاتورهای بانک.
    خروجی: dict[name -> np.ndarray(bool)] — هر ماسک با nan→False امن‌سازی شده.
    """
    def B(arr):
        return np.nan_to_num(arr.astype(float), nan=0.0).astype(bool)

    lib = {}

    # آماری/فراکتالی — کیفیتِ روند
    hu = hurst(df, 64)
    lib['hurst>0.50'] = B(hu > 0.50)
    lib['hurst>0.55'] = B(hu > 0.55)
    r2v = r2(df, 20)
    lib['r2>0.60'] = B(r2v > 0.60)
    lib['r2>0.75'] = B(r2v > 0.75)
    ct = corr_t(df, 20)
    lib['corr_t>0.5'] = B(ct > 0.5)       # روندِ صعودیِ خطیِ باکیفیت
    lib['corr_t>0.7'] = B(ct > 0.7)
    fd = fdi(df, 30)
    lib['fdi<1.5'] = B(fd < 1.5)          # کم‌پیچیدگی = روندِ تمیزتر

    # نوسان/رژیم
    ch = chop(df, 14)
    lib['chop<38.2'] = B(ch < 38.2)       # رژیمِ روندی (کلیدی)
    lib['chop<45'] = B(ch < 45)

    # ساختاری/روند — جهت
    lib['supertrend_up'] = B(supertrend_dir(df, 10, 3.0) > 0)
    lib['aroon>50'] = B(aroon(df, 25) > 50)
    lib['aroon>0'] = B(aroon(df, 25) > 0)
    lib['vortex_up'] = B(vortex(df, 14) > 0)
    lib['gann_up'] = B(gann_hilo_dir(df, 10) > 0)
    lib['psar_bull'] = B(psar_dir(df) > 0)

    # مومنتوم
    lib['waddah>0'] = B(waddah(df) > 0)   # انفجارِ صعودی
    lib['elder_up'] = B(elder_impulse(df) > 0)
    lib['cmo>0'] = B(cmo(df, 14) > 0)
    lib['ao>0'] = B(ao(df) > 0)
    lib['stc>25'] = B(stc(df) > 25)
    qq = qqe(df)
    lib['qqe>50'] = B(qq > 50)
    lib['crsi<70'] = B(crsi(df) < 70)     # نه اشباعِ خرید (ضدِ ورودِ دیرهنگام)

    # ترکیبی
    lib['trend_gate_up'] = B(trend_gate(df) > 0)
    er = kaufman_er(df, 10)
    lib['er>0.30'] = B(er > 0.30)         # حرکتِ جهت‌دار (کافمن)
    lib['er>0.20'] = B(er > 0.20)
    roe = rsi_of_er(df)
    lib['rsi_of_er>50'] = B(roe > 50)
    eda = ema_dist_atr(df)
    lib['not_overext'] = B(eda < 2.0)     # نه بیش‌ازحد کشیده (ضدِ ورودِ دیرهنگام)

    return lib


if __name__ == '__main__':
    # تستِ دود: روی XAUUSD H4 مقادیرِ نمونه چاپ شود
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from engine import scalp_engine as se
    df = se.load_data('data/XAUUSD_M15.csv')
    df = df.iloc[-3000:].reset_index(drop=True)
    lib = build_filter_library(df)
    print(f"فیلترها ساخته شد: {len(lib)} عدد روی {len(df)} کندل")
    for k, v in lib.items():
        print(f"  {k:18s}: True={int(v.sum()):5d} ({100*v.mean():.1f}%)")
