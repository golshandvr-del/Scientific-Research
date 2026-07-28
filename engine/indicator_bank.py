# -*- coding: utf-8 -*-
"""
indicator_bank.py — بانکِ ۴۰۱ اندیکاتورِ پروژه، نسخهٔ پایتون برای بک‌تست
================================================================================
این ماژول **معادلِ پایتونیِ** بانکِ TypeScript در `web_tool/src/indicators/bank/`
است. هدف: AIِ استراتژی‌ساز/احیاکن بتواند در `strategies/*.py` دقیقاً همان ۴۰۱
اندیکاتوری را صدا بزند که موتورِ سایت استفاده می‌کند — تا آنچه در بک‌تست ساخته
می‌شود بی‌کم‌وکاست قابلِ پورت به سایت باشد.

قراردادها (هم‌راستا با `engine/indicators.py`):
  • ورودی: DataFrame با ستون‌های ['open','high','low','close','volume'] (index مرتب).
  • خروجی: pd.Series هم‌طولِ df (NaN در ابتدای پنجره).
  • **بدونِ look-ahead**: هر مقدار فقط از داده‌های تا همان کندل استفاده می‌کند
    (rolling/ewm/shift(+)/cumulative). هیچ‌جا shift(-k) یا center=True نیست.
  • الگوهای کندلی: +100 صعودی / −100 نزولی / 0 بدونِ الگو.

استفاده:
    from engine import indicator_bank as ib
    s   = ib.compute('r2_fib_55', df)     # با نام (شاملِ variantها)
    s2  = ib.hurst(df, 64)                # مستقیم
    names = ib.list_indicators()          # همهٔ ۴۰۱ نام
    feats = ib.compute_many(['r2_20','hurst_64','ssf_10'], df)  # DataFrame

نکتهٔ عددهای غیررند (اشتباه رایج #۷): دنباله‌های فیبوناچی/لوکاس از پیش تعریف شده‌اند
تا از اعدادِ رندِ over-fit پرهیز شود.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# دنباله‌های دورهٔ غیررند (منطبق با kit.ts)
# ---------------------------------------------------------------------------
FIB_PERIODS = [3, 5, 8, 13, 21, 34, 55, 89, 144, 233]
LUCAS_PERIODS = [4, 7, 11, 18, 29, 47, 76, 123, 199]

# رجیستریِ سراسری: name -> callable(df) -> pd.Series
_REGISTRY: dict[str, callable] = {}


def _reg(name: str, fn) -> None:
    """ثبتِ یک اندیکاتور در رجیستری (نامِ تکراری خطا می‌دهد)."""
    if name in _REGISTRY:
        raise ValueError(f"indicator '{name}' already registered")
    _REGISTRY[name] = fn


# ===========================================================================
# بخش ۰ — توابعِ کمکیِ برداری (vectorized helpers) — بدونِ look-ahead
# ===========================================================================
def _c(df: pd.DataFrame) -> pd.Series:
    return df['close'].astype('float64')


def _tr(df: pd.DataFrame) -> pd.Series:
    """True Range."""
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    return pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)


def sma_s(s: pd.Series, p: int) -> pd.Series:
    return s.rolling(p).mean()


def ema_s(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()


def rma_s(s: pd.Series, p: int) -> pd.Series:
    """Wilder RMA (== ewm alpha=1/p)."""
    return s.ewm(alpha=1.0 / p, adjust=False).mean()


def wma_s(s: pd.Series, p: int) -> pd.Series:
    w = np.arange(1, p + 1, dtype='float64')
    wsum = w.sum()
    return s.rolling(p).apply(lambda x: np.dot(x, w) / wsum, raw=True)


def std_s(s: pd.Series, p: int) -> pd.Series:
    # انحرافِ معیارِ جمعیتی (ddof=0) — منطبق با stdArr در kit.ts
    return s.rolling(p).std(ddof=0)


def highest_s(s: pd.Series, p: int) -> pd.Series:
    return s.rolling(p).max()


def lowest_s(s: pd.Series, p: int) -> pd.Series:
    return s.rolling(p).min()


def rsi_s(s: pd.Series, p: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    ag = gain.ewm(alpha=1.0 / p, adjust=False).mean()
    al = loss.ewm(alpha=1.0 / p, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr_s(df: pd.DataFrame, p: int = 14) -> pd.Series:
    return rma_s(_tr(df), p)


# ===========================================================================
# رجیستری/محاسبه — API عمومی
# ===========================================================================
def list_indicators() -> list[str]:
    """فهرستِ همهٔ نام‌های ثبت‌شده (باید ۴۰۱ باشد)."""
    return sorted(_REGISTRY.keys())


def has_indicator(name: str) -> bool:
    return name in _REGISTRY


def registry_size() -> int:
    return len(_REGISTRY)


def compute(name: str, df: pd.DataFrame) -> pd.Series:
    """محاسبهٔ یک اندیکاتور با نام؛ خروجی pd.Series هم‌طولِ df."""
    if name not in _REGISTRY:
        raise KeyError(f"unknown indicator '{name}'. use list_indicators().")
    out = _REGISTRY[name](df)
    return pd.Series(out, index=df.index, name=name).astype('float64')


def compute_many(names: list[str], df: pd.DataFrame) -> pd.DataFrame:
    """محاسبهٔ چند اندیکاتور و بازگشتِ یک DataFrame (ستون‌ها = نام‌ها)."""
    return pd.DataFrame({n: compute(n, df) for n in names}, index=df.index)


# ===========================================================================
# بخش ۱ — TREND (روند / میانگین‌های پیشرفته) — ۱۶ پایه (نام‌ها ۱:۱ با trend.ts)
# نام‌ها: dema tema zlema hma rma wma trima t3 kama vidya mcgd alma fwma sinwma dma bbi
# ===========================================================================
def dema(df, p=20):
    e1 = ema_s(_c(df), p); e2 = ema_s(e1, p)
    return 2 * e1 - e2


def tema(df, p=20):
    e1 = ema_s(_c(df), p); e2 = ema_s(e1, p); e3 = ema_s(e2, p)
    return 3 * e1 - 3 * e2 + e3


def zlema(df, p=20):
    x = _c(df); lag = (p - 1) // 2
    return ema_s(x + (x - x.shift(lag)), p)


def hma(df, p=20):
    x = _c(df)
    half = wma_s(x, max(1, p // 2)); full = wma_s(x, p)
    return wma_s(2 * half - full, max(1, int(np.sqrt(p))))


def rma_ind(df, p=14):
    return rma_s(_c(df), p)


def wma_ind(df, p=20):
    return wma_s(_c(df), p)


def trima(df, p=20):
    # TRIMA = SMA(SMA) با نیم‌پنجره‌ها — منطبق با trend.ts (h=ceil((p+1)/2))
    h = (p + 1 + 1) // 2  # ceil((p+1)/2)
    return sma_s(sma_s(_c(df), h), p // 2 + 1)


def t3(df, p=10, v=0.7):
    x = _c(df)
    e1 = ema_s(x, p); e2 = ema_s(e1, p); e3 = ema_s(e2, p)
    e4 = ema_s(e3, p); e5 = ema_s(e4, p); e6 = ema_s(e5, p)
    c1 = -v ** 3; c2 = 3 * v ** 2 + 3 * v ** 3
    c3 = -6 * v ** 2 - 3 * v - 3 * v ** 3; c4 = 1 + 3 * v + v ** 3 + 3 * v ** 2
    return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3


def kama(df, p=10, fast=2, slow=30):
    x = _c(df); n = len(x); xv = x.values
    change = np.abs(xv - np.concatenate([np.full(p, np.nan), xv[:-p]]))
    vol = pd.Series(np.abs(np.diff(xv, prepend=xv[0]))).rolling(p).sum().values
    er = np.where(vol != 0, change / vol, 0.0)
    fsc = 2.0 / (fast + 1); ssc = 2.0 / (slow + 1)
    sc = (er * (fsc - ssc) + ssc) ** 2
    out = np.full(n, np.nan)
    prev = xv[0]
    for i in range(n):
        if np.isnan(sc[i]):
            out[i] = xv[i]; prev = xv[i]; continue
        prev = prev + sc[i] * (xv[i] - prev); out[i] = prev
    return pd.Series(out, index=x.index)


def vidya(df, p=14, cmo_p=9):
    x = _c(df); n = len(x); xv = x.values
    d = np.diff(xv, prepend=xv[0])
    up = pd.Series(np.where(d > 0, d, 0.0)).rolling(cmo_p).sum().values
    dn = pd.Series(np.where(d < 0, -d, 0.0)).rolling(cmo_p).sum().values
    cmo_v = np.where((up + dn) != 0, np.abs((up - dn) / (up + dn)), 0.0)
    alpha = 2.0 / (p + 1)
    out = np.full(n, np.nan); prev = xv[0]
    for i in range(n):
        k = alpha * cmo_v[i] if not np.isnan(cmo_v[i]) else 0.0
        prev = prev + k * (xv[i] - prev); out[i] = prev
    return pd.Series(out, index=x.index)


def mcgd(df, p=14):
    x = _c(df); n = len(x); xv = x.values
    out = np.full(n, np.nan); prev = xv[0]
    for i in range(n):
        if prev and not np.isnan(prev):
            prev = prev + (xv[i] - prev) / (p * (xv[i] / prev) ** 4)
        else:
            prev = xv[i]
        out[i] = prev
    return pd.Series(out, index=x.index)


def alma(df, p=21, offset=0.85, sigma=6.0):
    x = _c(df)
    m = offset * (p - 1); s = p / sigma
    w = np.exp(-((np.arange(p) - m) ** 2) / (2 * s * s)); w /= w.sum()
    return x.rolling(p).apply(lambda a: np.dot(a, w), raw=True)


def fwma(df, p=10):
    # میانگینِ وزنیِ فیبوناچی (وزن‌ها = دنباله‌ی فیبوناچیِ p جمله)
    fib = [1, 1]
    for k in range(2, p):
        fib.append(fib[k - 1] + fib[k - 2])
    fib = np.array(fib[:p], dtype='float64'); wsum = fib.sum()
    return _c(df).rolling(p).apply(lambda a: np.dot(a, fib) / wsum, raw=True)


def sinwma(df, p=14):
    # میانگینِ وزنیِ سینوسی (وزن‌ها = sin(kπ/(p+1)))
    w = np.array([np.sin(k * np.pi / (p + 1)) for k in range(1, p + 1)], dtype='float64')
    wsum = w.sum()
    return _c(df).rolling(p).apply(lambda a: np.dot(a, w) / wsum, raw=True)


def dma_ind(df, fast=10, slow=50):
    # 平均差 — تفاضلِ دو SMA
    x = _c(df)
    return sma_s(x, fast) - sma_s(x, slow)


def bbi(df, p1=3, p2=6, p3=12, p4=24):
    # 多空均线 — میانگینِ چهار SMA
    x = _c(df)
    return (sma_s(x, p1) + sma_s(x, p2) + sma_s(x, p3) + sma_s(x, p4)) / 4


_reg('dema', dema); _reg('tema', tema); _reg('zlema', zlema); _reg('hma', hma)
_reg('rma', rma_ind); _reg('wma', wma_ind); _reg('trima', trima); _reg('t3', t3)
_reg('kama', kama); _reg('vidya', vidya); _reg('mcgd', mcgd); _reg('alma', alma)
_reg('fwma', fwma); _reg('sinwma', sinwma); _reg('dma', dma_ind); _reg('bbi', bbi)


# ===========================================================================
# بخش ۲ — MOMENTUM (مومنتوم / اسیلاتورها) — ۲۵ پایه (نام‌ها ۱:۱ با momentum.ts)
# نام‌ها: ao ac apo ppo cmo tsi roc mom bop cfo pgo fisher ifish_rsi rvgi kdj_j
#         bias wr_cn psy br ar cr trix dpo mtm adtm
# ===========================================================================
def ao(df):
    mid = (df['high'] + df['low']) / 2
    return sma_s(mid, 5) - sma_s(mid, 34)


def ac(df):
    mid = (df['high'] + df['low']) / 2
    aos = sma_s(mid, 5) - sma_s(mid, 34)
    return aos - sma_s(aos, 5)


def apo(df, fast=12, slow=26):
    x = _c(df)
    return ema_s(x, fast) - ema_s(x, slow)


def ppo(df, fast=12, slow=26):
    ef = ema_s(_c(df), fast); es = ema_s(_c(df), slow)
    return 100 * (ef - es) / es.replace(0, np.nan)


def cmo(df, p=14):
    d = _c(df).diff()
    up = d.clip(lower=0).rolling(p).sum(); dn = (-d.clip(upper=0)).rolling(p).sum()
    return 100 * (up - dn) / (up + dn).replace(0, np.nan)


def tsi(df, long=25, short=13):
    m = _c(df).diff()
    r = ema_s(ema_s(m, long), short); a = ema_s(ema_s(m.abs(), long), short)
    return 100 * r / a.replace(0, np.nan)


def roc(df, p=10):
    x = _c(df)
    return 100 * (x - x.shift(p)) / x.shift(p).replace(0, np.nan)


def mom(df, p=10):
    return _c(df).diff(p)


def bop(df, smooth=14):
    rng = (df['high'] - df['low']).replace(0, np.nan)
    raw = ((df['close'] - df['open']) / rng).fillna(0)
    return sma_s(raw, smooth)


def cfo(df, p=14):
    # Chande Forecast Oscillator — انحراف از خطِ رگرسیونِ خطیِ p جمله
    x = _c(df); n = len(x); xv = x.values; out = np.full(n, np.nan)
    kk = np.arange(p, dtype='float64'); sx = kk.sum(); sxx = (kk * kk).sum()
    denom = p * sxx - sx * sx
    for i in range(p - 1, n):
        y = xv[i - p + 1:i + 1]
        sy = y.sum(); sxy = (kk * y).sum()
        b = (p * sxy - sx * sy) / denom
        a = (sy - b * sx) / p
        forecast = a + b * (p - 1)
        out[i] = 100 * (xv[i] - forecast) / xv[i] if xv[i] else np.nan
    return pd.Series(out, index=x.index)


def pgo(df, p=14):
    # Pretty Good Oscillator — (close − SMA)/EMA(TR)
    x = _c(df); sma = sma_s(x, p)
    eatr = ema_s(_tr(df), p)
    return (x - sma) / eatr.replace(0, np.nan)


def fisher(df, p=9):
    # تبدیلِ فیشرِ اِهلرز — منطبق با momentum.ts (0.66/0.67 روی median نرمال‌شده)
    med = ((df['high'] + df['low']) / 2)
    n = len(med); mv = med.values
    hh = med.rolling(p).max().values; ll = med.rolling(p).min().values
    out = np.full(n, np.nan); v = 0.0; prev_f = 0.0
    for i in range(p - 1, n):
        rng = (hh[i] - ll[i]) or 1e-10
        v = 0.66 * (2 * (mv[i] - ll[i]) / rng - 1) + 0.67 * v
        vv = min(0.999, max(-0.999, v))
        f = 0.5 * np.log((1 + vv) / (1 - vv)) + 0.5 * prev_f
        out[i] = f; prev_f = f
    return pd.Series(out, index=med.index)


def ifish_rsi(df, p=14):
    # Inverse Fisher of RSI
    r = rsi_s(_c(df), p)
    v = 0.1 * (r - 50)
    return (np.exp(2 * v) - 1) / (np.exp(2 * v) + 1)


def rvgi(df, p=10):
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    co = c - o; hl = h - l
    num = (co + 2 * co.shift(1) + 2 * co.shift(2) + co.shift(3)) / 6
    den = (hl + 2 * hl.shift(1) + 2 * hl.shift(2) + hl.shift(3)) / 6
    return sma_s(num, p) / sma_s(den, p).replace(0, np.nan)


def kdj_j(df, p=9, k_s=3, d_s=3):
    ll = lowest_s(df['low'], p); hh = highest_s(df['high'], p)
    rsv = 100 * (df['close'] - ll) / (hh - ll).replace(0, np.nan)
    k = rsv.ewm(alpha=1.0 / k_s, adjust=False).mean()
    d = k.ewm(alpha=1.0 / d_s, adjust=False).mean()
    return 3 * k - 2 * d


def bias(df, p=6):
    x = _c(df); s = sma_s(x, p)
    return 100 * (x - s) / s.replace(0, np.nan)


def wr_cn(df, p=14):
    # ویلیامز %R چینی: (hh−close)/(hh−ll)*100  (بازه‌ی 0..100، معکوسِ %R غربی)
    hh = highest_s(df['high'], p); ll = lowest_s(df['low'], p)
    return 100 * (hh - df['close']) / (hh - ll).replace(0, np.nan)


def psy(df, p=12):
    up = (_c(df).diff() > 0).astype('float64')
    return 100 * up.rolling(p).sum() / p


def br(df, p=26):
    # 情绪指标 BR
    h, l, pc = df['high'], df['low'], df['close'].shift(1)
    up = (h - pc).clip(lower=0).rolling(p).sum()
    dn = (pc - l).clip(lower=0).rolling(p).sum()
    return 100 * up / dn.replace(0, np.nan)


def ar(df, p=26):
    o, h, l = df['open'], df['high'], df['low']
    up = (h - o).rolling(p).sum(); dn = (o - l).rolling(p).sum()
    return 100 * up / dn.replace(0, np.nan)


def cr(df, p=26):
    mid = (df['high'] + df['low'] + df['close']) / 3
    pm = mid.shift(1)
    up = (df['high'] - pm).clip(lower=0).rolling(p).sum()
    dn = (pm - df['low']).clip(lower=0).rolling(p).sum()
    return 100 * up / dn.replace(0, np.nan)


def trix(df, p=15):
    e = ema_s(ema_s(ema_s(_c(df), p), p), p)
    return 100 * e.diff() / e.shift(1).replace(0, np.nan)


def dpo(df, p=20):
    x = _c(df); sh = p // 2 + 1
    return x - sma_s(x, p).shift(sh)


def mtm(df, p=12, smooth=6):
    raw = _c(df).diff(p)
    return sma_s(raw, smooth)


def adtm(df, p=23, smooth=8):
    o, h, l = df['open'], df['high'], df['low']
    po = o.shift(1)
    dtm = np.where(o <= po, 0.0,
                   np.maximum((h - o).values, (o - po).values))
    dbm = np.where(o >= po, 0.0,
                   np.maximum((o - l).values, (o - po).values))
    dtm = pd.Series(dtm, index=o.index); dbm = pd.Series(dbm, index=o.index)
    sd = dtm.rolling(p).sum(); sb = dbm.rolling(p).sum()
    stm = pd.concat([sd, sb], axis=1).max(axis=1)
    out = ((sd - sb) / stm.replace(0, np.nan)).fillna(0)
    return sma_s(out, smooth)


_reg('ao', ao); _reg('ac', ac); _reg('apo', apo); _reg('ppo', ppo)
_reg('cmo', cmo); _reg('tsi', tsi); _reg('roc', roc); _reg('mom', mom)
_reg('bop', bop); _reg('cfo', cfo); _reg('pgo', pgo); _reg('fisher', fisher)
_reg('ifish_rsi', ifish_rsi); _reg('rvgi', rvgi); _reg('kdj_j', kdj_j); _reg('bias', bias)
_reg('wr_cn', wr_cn); _reg('psy', psy); _reg('br', br); _reg('ar', ar)
_reg('cr', cr); _reg('trix', trix); _reg('dpo', dpo); _reg('mtm', mtm); _reg('adtm', adtm)


# ثبتِ دسته‌ها در انتهای فایل انجام می‌شود (پس از تعریفِ همهٔ سازنده‌ها).
