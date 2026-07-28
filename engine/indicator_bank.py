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


# ===========================================================================
# بخش ۳ — VOLATILITY (۶) + VOLUME (۸) — نام‌ها ۱:۱ با volatility.ts
# نام‌ها: natr rvi_vol ulcer chop mass atr_pct | obv ad adosc efi mfi wvad vpt emv
# ===========================================================================
def natr(df, p=14):
    x = _c(df); a = rma_s(_tr(df), p)
    return 100 * a / x.replace(0, np.nan)


def rvi_vol(df, p=14):
    x = _c(df); sd = std_s(x, p)
    up = sd.where(x > x.shift(1), 0.0)
    dn = sd.where(x <= x.shift(1), 0.0)
    eu = ema_s(up, p); ed = ema_s(dn, p)
    return 100 * eu / (eu + ed).replace(0, np.nan)


def ulcer(df, p=14):
    x = _c(df); n = len(x); xv = x.values; out = np.full(n, np.nan)
    hh = x.rolling(p).max().values
    for i in range(p - 1, n):
        h = hh[i]
        if not h:
            continue
        window = xv[i - p + 1:i + 1]
        dd = 100 * (window - h) / h
        out[i] = np.sqrt(np.mean(dd * dd))
    return pd.Series(out, index=x.index)


def chop(df, p=14):
    tr = _tr(df)
    sum_tr = tr.rolling(p).sum()
    hh = df['high'].rolling(p).max(); ll = df['low'].rolling(p).min()
    rng = (hh - ll).replace(0, np.nan)
    return 100 * np.log10(sum_tr / rng) / np.log10(p)


def mass(df, ema=9, summ=25):
    rng = (df['high'] - df['low'])
    e1 = ema_s(rng, ema); e2 = ema_s(e1, ema)
    ratio = e1 / e2.replace(0, np.nan)
    return ratio.rolling(summ).sum()


def atr_pct(df, p=14, lookback=100):
    a = rma_s(_tr(df), p)
    # صدکِ درصدیِ ATR جاری در پنجره‌ی گذشته (شاملِ خودش) — بدونِ look-ahead
    return a.rolling(lookback + 1).apply(
        lambda w: 100.0 * (w <= w[-1]).sum() / len(w), raw=True)


def obv(df):
    x = _c(df); v = df['volume']
    sign = np.sign(x.diff().fillna(0))
    return (sign * v).cumsum()


def _adl(df):
    rng = (df['high'] - df['low'])
    mfm = (((df['close'] - df['low']) - (df['high'] - df['close'])) / rng.replace(0, np.nan)).fillna(0)
    return (mfm * df['volume']).cumsum()


def ad(df):
    return _adl(df)


def adosc(df, fast=3, slow=10):
    adl = _adl(df)
    return ema_s(adl, fast) - ema_s(adl, slow)


def efi(df, p=13):
    raw = _c(df).diff() * df['volume']
    return ema_s(raw, p)


def mfi(df, p=14):
    tp = (df['high'] + df['low'] + df['close']) / 3
    mf = tp * df['volume']
    up = mf.where(tp > tp.shift(1), 0.0).rolling(p).sum()
    dn = mf.where(tp < tp.shift(1), 0.0).rolling(p).sum()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def wvad(df, p=24):
    rng = (df['high'] - df['low'])
    raw = (((df['close'] - df['open']) / rng.replace(0, np.nan)) * df['volume']).fillna(0)
    return sma_s(raw, p)


def vpt(df):
    x = _c(df); v = df['volume']
    raw = (v * (x.diff() / x.shift(1).replace(0, np.nan))).fillna(0)
    return raw.cumsum()


def emv(df, p=14):
    mid = ((df['high'] + df['low']) / 2).diff()
    rng = (df['high'] - df['low'])
    box = (df['volume'] / 1e6) / rng.replace(0, np.nan)
    raw = (mid / box.replace(0, np.nan)).fillna(0)
    return sma_s(raw, p)


_reg('natr', natr); _reg('rvi_vol', rvi_vol); _reg('ulcer', ulcer); _reg('chop', chop)
_reg('mass', mass); _reg('atr_pct', atr_pct)
_reg('obv', obv); _reg('ad', ad); _reg('adosc', adosc); _reg('efi', efi)
_reg('mfi', mfi); _reg('wvad', wvad); _reg('vpt', vpt); _reg('emv', emv)


# ===========================================================================
# بخش ۴ — STATISTICAL / FRACTAL (۸) — نام‌ها ۱:۱ با statistical.ts
# نام‌ها: skew kurt corr_t r2 hurst entropy frama fdi
# ⚑ r2 و hurst کلیدِ احیای S332 بودند — دقتِ ریاضی حیاتی است.
# ===========================================================================
def skew(df, p=20):
    x = _c(df)
    def _s(w):
        m = w.mean(); d = w - m
        sd = np.sqrt((d * d).mean())
        return (d ** 3).mean() / (sd ** 3) if sd else 0.0
    return x.rolling(p).apply(_s, raw=True)


def kurt(df, p=20):
    x = _c(df)
    def _k(w):
        m = w.mean(); d = w - m
        v = (d * d).mean()
        return (d ** 4).mean() / (v * v) - 3 if v else 0.0
    return x.rolling(p).apply(_k, raw=True)


def corr_t(df, p=20):
    x = _c(df); t = np.arange(p, dtype='float64')
    st = t.sum(); stt = (t * t).sum()
    def _c_fn(w):
        sy = w.sum(); sxy = (t * w).sum(); syy = (w * w).sum()
        num = p * sxy - st * sy
        den = np.sqrt((p * stt - st * st) * (p * syy - sy * sy))
        return num / den if den else 0.0
    return x.rolling(p).apply(_c_fn, raw=True)


def r2(df, p=20):
    x = _c(df); t = np.arange(p, dtype='float64')
    st = t.sum(); stt = (t * t).sum()
    def _r2(w):
        sy = w.sum(); sxy = (t * w).sum(); syy = (w * w).sum()
        num = p * sxy - st * sy
        den = (p * stt - st * st) * (p * syy - sy * sy)
        r = num / np.sqrt(den) if den > 0 else 0.0
        return r * r
    return x.rolling(p).apply(_r2, raw=True)


def hurst(df, p=64):
    # نمای هرست به روشِ Rescaled Range روی log-returns (منطبق با statistical.ts)
    x = _c(df); n = len(x); xv = x.values
    ret = np.zeros(n)
    with np.errstate(divide='ignore', invalid='ignore'):
        ret[1:] = np.where(xv[:-1] != 0, np.log(xv[1:] / xv[:-1]), 0.0)
    ret = np.nan_to_num(ret)
    out = np.full(n, np.nan)
    logp = np.log(p)
    for i in range(p, n):
        w = ret[i - p + 1:i + 1]
        m = w.mean(); dev = w - m
        cum = np.cumsum(dev)
        R = cum.max() - cum.min()
        sd = np.sqrt((dev * dev).mean())
        out[i] = np.log(R / sd) / logp if (sd and R > 0) else 0.5
    return pd.Series(out, index=x.index)


def entropy(df, p=20, bins=8):
    x = _c(df); n = len(x); xv = x.values
    ret = np.zeros(n)
    ret[1:] = np.where(xv[:-1] != 0, (xv[1:] - xv[:-1]) / xv[:-1], 0.0)
    out = np.full(n, np.nan)
    for i in range(p, n):
        w = ret[i - p + 1:i + 1]
        mn, mx = w.min(), w.max(); rng = (mx - mn) or 1e-10
        idx = np.minimum(bins - 1, ((w - mn) / rng * bins).astype(int))
        hist = np.bincount(idx, minlength=bins)
        pr = hist[hist > 0] / p
        out[i] = -(pr * np.log2(pr)).sum()
    return pd.Series(out, index=x.index)


def frama(df, p=16):
    # Fractal Adaptive MA (اِهلرز) — برچسبِ trend ولی منطقِ فراکتالی
    h = df['high'].values; l = df['low'].values; xv = _c(df).values
    n = len(xv); out = np.full(n, np.nan)
    per = p if p % 2 == 0 else p + 1
    half = per // 2
    prev = np.nan
    for i in range(n):
        if i < per:
            out[i] = xv[i]; prev = xv[i]; continue
        n1 = (h[i - half:i].max() - l[i - half:i].min()) / half
        n2 = (h[i - half + 1:i + 1].max() - l[i - half + 1:i + 1].min()) / half
        n3 = (h[i - per + 1:i + 1].max() - l[i - per + 1:i + 1].min()) / per
        D = 1.0
        if n1 > 0 and n2 > 0 and n3 > 0:
            D = (np.log(n1 + n2) - np.log(n3)) / np.log(2)
        alpha = float(np.clip(np.exp(-4.6 * (D - 1)), 0.01, 1.0))
        prev = alpha * xv[i] + (1 - alpha) * prev if np.isfinite(prev) else xv[i]
        out[i] = prev
    return pd.Series(out, index=df.index)


def fdi(df, p=30):
    x = _c(df); n = len(x); xv = x.values; out = np.full(n, np.nan)
    for i in range(p - 1, n):
        w = xv[i - p + 1:i + 1]
        rng = (w.max() - w.min()) or 1e-10
        d1 = np.diff(w) / rng
        L = np.sqrt(d1 * d1 + 1.0 / (p * p)).sum()
        out[i] = 1 + (np.log(L) + np.log(2)) / np.log(2 * p)
    return pd.Series(out, index=x.index)


_reg('skew', skew); _reg('kurt', kurt); _reg('corr_t', corr_t); _reg('r2', r2)
_reg('hurst', hurst); _reg('entropy', entropy); _reg('frama', frama); _reg('fdi', fdi)


# ===========================================================================
# بخش ۵ — CYCLE / EHLERS / DSP (۹) — نام‌ها ۱:۱ با cycle.ts
# نام‌ها: ssf ehp roof laguerre laguerre_rsi reflex trendflex cg dsma
# فیلترهای بازگشتی (stateful) — پورتِ حلقه‌به‌حلقه، بدونِ look-ahead.
# ===========================================================================
def _ssf_arr(xv, period):
    n = len(xv); out = np.empty(n)
    a = np.exp(-1.414 * np.pi / period)
    b = 2 * a * np.cos(1.414 * np.pi / period)
    c2 = b; c3 = -a * a; c1 = 1 - c2 - c3
    for i in range(n):
        if i < 2:
            out[i] = xv[i]
        else:
            out[i] = c1 * (xv[i] + xv[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2]
    return out


def ssf(df, period=10):
    return pd.Series(_ssf_arr(_c(df).values, period), index=df.index)


def ehp(df, period=48):
    xv = _c(df).values; n = len(xv); out = np.zeros(n)
    a = (np.cos(2 * np.pi / period) + np.sin(2 * np.pi / period) - 1) / np.cos(2 * np.pi / period)
    for i in range(1, n):
        out[i] = (1 - a / 2) * (xv[i] - xv[i - 1]) + (1 - a) * out[i - 1]
    return pd.Series(out, index=df.index)


def roof(df, hp=48, ss=10):
    xv = _c(df).values; n = len(xv); hpf = np.zeros(n)
    a = (np.cos(2 * np.pi / hp) + np.sin(2 * np.pi / hp) - 1) / np.cos(2 * np.pi / hp)
    for i in range(2, n):
        hpf[i] = ((1 - a / 2) ** 2) * (xv[i] - 2 * xv[i - 1] + xv[i - 2]) \
                 + 2 * (1 - a) * hpf[i - 1] - ((1 - a) ** 2) * hpf[i - 2]
    out = np.empty(n)
    aa = np.exp(-1.414 * np.pi / ss); bb = 2 * aa * np.cos(1.414 * np.pi / ss)
    c2 = bb; c3 = -aa * aa; c1 = 1 - c2 - c3
    for i in range(n):
        if i < 2:
            out[i] = hpf[i]
        else:
            out[i] = c1 * (hpf[i] + hpf[i - 1]) / 2 + c2 * out[i - 1] + c3 * out[i - 2]
    return pd.Series(out, index=df.index)


def _laguerre_levels(xv, g):
    n = len(xv)
    L0s = np.empty(n); L1s = np.empty(n); L2s = np.empty(n); L3s = np.empty(n)
    L0 = L1 = L2 = L3 = 0.0
    for i in range(n):
        pL0, pL1, pL2 = L0, L1, L2
        L0 = (1 - g) * xv[i] + g * L0
        L1 = -g * L0 + pL0 + g * L1
        L2 = -g * L1 + pL1 + g * L2
        L3 = -g * L2 + pL2 + g * L3
        L0s[i], L1s[i], L2s[i], L3s[i] = L0, L1, L2, L3
    return L0s, L1s, L2s, L3s


def laguerre(df, gamma=0.8):
    L0, L1, L2, L3 = _laguerre_levels(_c(df).values, gamma)
    return pd.Series((L0 + 2 * L1 + 2 * L2 + L3) / 6, index=df.index)


def laguerre_rsi(df, gamma=0.5):
    L0, L1, L2, L3 = _laguerre_levels(_c(df).values, gamma)
    cu = np.zeros_like(L0); cd = np.zeros_like(L0)
    for a, b in ((L0, L1), (L1, L2), (L2, L3)):
        up = a >= b
        cu += np.where(up, a - b, 0.0)
        cd += np.where(~up, b - a, 0.0)
    tot = cu + cd
    return pd.Series(np.where(tot != 0, 100 * cu / tot, 50.0), index=df.index)


def _flex(df, period, trend):
    xv = _c(df).values; n = len(xv)
    ssf = _ssf_arr(xv, period / 2)
    out = np.zeros(n); ms = 0.0
    for i in range(period, n):
        if trend:
            s = sum(ssf[i] - ssf[i - k] for k in range(1, period + 1)) / period
        else:
            slope = (ssf[i - period] - ssf[i]) / period
            s = sum(ssf[i] + k * slope - ssf[i - k] for k in range(1, period + 1)) / period
        ms = 0.04 * s * s + 0.96 * ms
        out[i] = s / np.sqrt(ms) if ms else 0.0
    return pd.Series(out, index=df.index)


def reflex(df, period=20):
    return _flex(df, period, trend=False)


def trendflex(df, period=20):
    return _flex(df, period, trend=True)


def cg(df, period=10):
    x = _c(df); k = np.arange(1, period + 1, dtype='float64')
    def _cg(w):
        wr = w[::-1]  # w[-1] جدیدترین → معادلِ x[i-k] با k=0..
        num = (k * wr).sum(); den = wr.sum()
        return -num / den + (period + 1) / 2 if den else 0.0
    return x.rolling(period).apply(_cg, raw=True)


def dsma(df, period=20):
    xv = _c(df).values; n = len(xv)
    out = np.empty(n); zeros = np.zeros(n); filt = np.zeros(n)
    a = np.exp(-1.414 * np.pi / (period / 2)); b = 2 * a * np.cos(1.414 * np.pi / (period / 2))
    c2 = b; c3 = -a * a; c1 = 1 - c2 - c3
    prev = np.nan
    for i in range(n):
        zeros[i] = xv[i] - xv[i - 2] if i >= 2 else 0.0
        if i < 2:
            filt[i] = 0.0; out[i] = xv[i]; prev = xv[i]; continue
        filt[i] = c1 * (zeros[i] + zeros[i - 1]) / 2 + c2 * filt[i - 1] + c3 * filt[i - 2]
        w = min(period, i + 1)
        rms = np.sqrt((filt[i - w + 1:i + 1] ** 2).mean())
        sc = abs(filt[i] / rms) if rms else 0.0
        alpha = float(np.clip((5 * sc) / period, 0.01, 1.0))
        prev = alpha * xv[i] + (1 - alpha) * prev
        out[i] = prev
    return pd.Series(out, index=df.index)


_reg('ssf', ssf); _reg('ehp', ehp); _reg('roof', roof); _reg('laguerre', laguerre)
_reg('laguerre_rsi', laguerre_rsi); _reg('reflex', reflex); _reg('trendflex', trendflex)
_reg('cg', cg); _reg('dsma', dsma)


# ===========================================================================
# بخش ۶ — STRUCTURE / TREND-FOLLOWING (۱۳) — نام‌ها ۱:۱ با structure.ts
# نام‌ها: supertrend psar aroon vortex donchian_mid qqe stc crsi waddah
#         elder_impulse chandelier gann_hilo tdi
# ===========================================================================
def supertrend(df, period=10, mult=3.0):
    h = df['high'].values; l = df['low'].values; cl = df['close'].values
    atr = rma_s(_tr(df), period).values
    n = len(cl); out = np.full(n, np.nan)
    final_up = final_dn = np.nan; direction = 1; started = False
    for i in range(n):
        if not np.isfinite(atr[i]):
            continue
        mid = (h[i] + l[i]) / 2
        basic_up = mid - mult * atr[i]; basic_dn = mid + mult * atr[i]
        if not started:
            final_up, final_dn, direction = basic_up, basic_dn, 1
            out[i] = final_up; started = True; continue
        final_up = basic_up if (basic_up > final_up or cl[i - 1] < final_up) else final_up
        final_dn = basic_dn if (basic_dn < final_dn or cl[i - 1] > final_dn) else final_dn
        if direction == 1 and cl[i] < final_up:
            direction = -1
        elif direction == -1 and cl[i] > final_dn:
            direction = 1
        out[i] = final_up if direction == 1 else final_dn
    return pd.Series(out, index=df.index)


def psar(df, step=0.02, mx=0.2):
    h = df['high'].values; l = df['low'].values; cl = df['close'].values
    n = len(cl); out = np.full(n, np.nan)
    if n < 2:
        return pd.Series(out, index=df.index)
    bull = cl[1] >= cl[0]
    af = step; ep = h[0] if bull else l[0]; sar = l[0] if bull else h[0]
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
        out[i] = sar
    return pd.Series(out, index=df.index)


def aroon(df, period=25):
    h = df['high']; l = df['low']
    # فاصله تا بیشینه/کمینه در پنجره‌ی period+1 (argmax روی پنجره) — بدونِ look-ahead
    def _up(w): return 100 * (period - (len(w) - 1 - int(np.argmax(w)))) / period
    def _dn(w): return 100 * (period - (len(w) - 1 - int(np.argmin(w)))) / period
    up = h.rolling(period + 1).apply(_up, raw=True)
    dn = l.rolling(period + 1).apply(_dn, raw=True)
    return up - dn


def vortex(df, period=14):
    h = df['high']; l = df['low']
    vmp = (h - l.shift(1)).abs(); vmn = (l - h.shift(1)).abs()
    tr = _tr(df)
    sp = vmp.rolling(period).sum(); sn = vmn.rolling(period).sum(); st = tr.rolling(period).sum()
    return (sp - sn) / st.replace(0, np.nan)


def donchian_mid(df, period=20):
    return (df['high'].rolling(period).max() + df['low'].rolling(period).min()) / 2


def qqe(df, rsiP=14, sf=5):
    return ema_s(rsi_s(_c(df), rsiP), sf)


def stc(df, fast=23, slow=50, cycle=10):
    x = _c(df)
    macd = ema_s(x, fast) - ema_s(x, slow)
    hh1 = macd.rolling(cycle).max(); ll1 = macd.rolling(cycle).min()
    st1 = (100 * (macd - ll1) / (hh1 - ll1).replace(0, np.nan)).fillna(50)
    d1 = ema_s(st1, max(2, cycle // 2))
    hh2 = d1.rolling(cycle).max(); ll2 = d1.rolling(cycle).min()
    st2 = (100 * (d1 - ll2) / (hh2 - ll2).replace(0, np.nan)).fillna(50)
    return ema_s(st2, max(2, cycle // 2))


def crsi(df, rsiP=3, streakP=2, rankP=100):
    x = _c(df); n = len(x); xv = x.values
    r = rsi_s(x, rsiP)
    streak = np.zeros(n); s = 0
    for i in range(1, n):
        if xv[i] > xv[i - 1]:
            s = s + 1 if s >= 0 else 1
        elif xv[i] < xv[i - 1]:
            s = s - 1 if s <= 0 else -1
        else:
            s = 0
        streak[i] = s
    streak_rsi = rsi_s(pd.Series(streak, index=x.index), streakP)
    ret = pd.Series(np.zeros(n), index=x.index)
    ret.iloc[1:] = np.where(xv[:-1] != 0, (xv[1:] - xv[:-1]) / xv[:-1], 0.0)
    rv = ret.values; rank = np.full(n, np.nan)
    for i in range(rankP, n):
        below = (rv[i - rankP:i] < rv[i]).sum()
        rank[i] = 100 * below / rankP
    rank = pd.Series(rank, index=x.index)
    return (r + streak_rsi + rank) / 3


def waddah(df, fast=20, slow=40, bbP=20, bbM=2.0):
    x = _c(df)
    macd = ema_s(x, fast) - ema_s(x, slow)
    return (macd - macd.shift(1)) * 150


def elder_impulse(df, emaP=13, macdF=12, macdS=26, macdSig=9):
    x = _c(df)
    e = ema_s(x, emaP)
    macd = ema_s(x, macdF) - ema_s(x, macdS)
    sig = ema_s(macd, macdSig)
    hist = macd - sig
    es = np.sign(e.diff()); hs = np.sign(hist.diff())
    out = np.where((es > 0) & (hs > 0), 1.0, np.where((es < 0) & (hs < 0), -1.0, 0.0))
    res = pd.Series(out, index=df.index); res.iloc[0] = np.nan
    return res


def chandelier(df, period=22, mult=3.0):
    atr = rma_s(_tr(df), period)
    return df['high'].rolling(period).max() - mult * atr


def gann_hilo(df, period=10):
    h = df['high']; l = df['low']; cl = df['close'].values
    sh = sma_s(h, period).values; sl = sma_s(l, period).values
    n = len(cl); out = np.full(n, np.nan); direction = 1
    for i in range(period, n):
        if cl[i] > sh[i - 1]:
            direction = 1
        elif cl[i] < sl[i - 1]:
            direction = -1
        out[i] = sl[i] if direction == 1 else sh[i]
    return pd.Series(out, index=df.index)


def tdi(df, rsiP=13, sig=7):
    return sma_s(rsi_s(_c(df), rsiP), sig)


_reg('supertrend', supertrend); _reg('psar', psar); _reg('aroon', aroon); _reg('vortex', vortex)
_reg('donchian_mid', donchian_mid); _reg('qqe', qqe); _reg('stc', stc); _reg('crsi', crsi)
_reg('waddah', waddah); _reg('elder_impulse', elder_impulse); _reg('chandelier', chandelier)
_reg('gann_hilo', gann_hilo); _reg('tdi', tdi)


# ===========================================================================
# بخش ۷ — COMPOSITE / OVERLAP (۵ تبدیلِ قیمت + ۳ ترکیبیِ رژیم‌محور = ۸)
# نام‌ها ۱:۱ با composite.ts:
#   hl2 hlc3 ohlc4 wcp midpoint | ema_dist_atr rsi_of_er trend_gate
# ===========================================================================
def hl2(df):
    return (df['high'] + df['low']) / 2


def hlc3(df):
    return (df['high'] + df['low'] + df['close']) / 3


def ohlc4(df):
    return (df['open'] + df['high'] + df['low'] + df['close']) / 4


def wcp(df):
    return (df['high'] + df['low'] + 2 * df['close']) / 4


def midpoint(df, period=14):
    x = _c(df)
    return (x.rolling(period).max() + x.rolling(period).min()) / 2


def ema_dist_atr(df, emaP=50, atrP=14):
    x = _c(df); e = ema_s(x, emaP); a = rma_s(_tr(df), atrP)
    return (x - e) / a.replace(0, np.nan)


def rsi_of_er(df, erP=10, rsiP=14):
    x = _c(df); n = len(x); xv = x.values
    er = np.zeros(n)
    absdiff = np.abs(np.diff(xv, prepend=xv[0]))
    vol = pd.Series(absdiff).rolling(erP).sum().values
    change = np.abs(xv - np.concatenate([np.full(erP, np.nan), xv[:-erP]]))
    with np.errstate(invalid='ignore'):
        er = np.where((vol != 0) & np.isfinite(change), change / vol, 0.0)
    er = np.nan_to_num(er)
    return rsi_s(pd.Series(er * 100, index=x.index), rsiP)


def trend_gate(df, chopP=14, emaP=50, thr=38.2):
    x = _c(df); e = ema_s(x, emaP)
    tr = _tr(df)
    sum_tr = tr.rolling(chopP).sum()
    rng = (df['high'].rolling(chopP).max() - df['low'].rolling(chopP).min())
    chop_v = 100 * np.log10(sum_tr / rng.replace(0, np.nan)) / np.log10(chopP)
    slope = np.sign(e.diff())
    out = np.where(chop_v < thr, slope, 0.0)
    return pd.Series(out, index=df.index)


_reg('hl2', hl2); _reg('hlc3', hlc3); _reg('ohlc4', ohlc4); _reg('wcp', wcp)
_reg('midpoint', midpoint); _reg('ema_dist_atr', ema_dist_atr)
_reg('rsi_of_er', rsi_of_er); _reg('trend_gate', trend_gate)


# ===========================================================================
# بخش ۸ — CANDLESTICK PATTERNS (۳۱) — نام‌ها ۱:۱ با pattern.ts
# خروجی: +100 صعودی / −100 نزولی / 0 بدونِ الگو. بدونِ look-ahead
# (هر کندل فقط به i, i-1, i-2 نگاه می‌کند). vectorized با shift(+k).
# ===========================================================================
def _cndl(df):
    o, h, l, c = df['open'], df['high'], df['low'], df['close']
    body = (c - o).abs(); rng = (h - l)
    up_sh = h - pd.concat([o, c], axis=1).max(axis=1)
    dn_sh = pd.concat([o, c], axis=1).min(axis=1) - l
    is_bull = c >= o; is_bear = c < o
    return o, h, l, c, body, rng, up_sh, dn_sh, is_bull, is_bear


def cdl_doji(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    return np.where((rng > 0) & (body <= 0.1 * rng), 100.0, 0.0)


def cdl_dragonfly(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    return np.where((rng > 0) & (body <= 0.1 * rng) & (ds >= 0.6 * rng), 100.0, 0.0)


def cdl_gravestone(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    return np.where((rng > 0) & (body <= 0.1 * rng) & (us >= 0.6 * rng), -100.0, 0.0)


def cdl_hammer(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (ds >= 2 * body) & (us <= 0.15 * rng) & (c.shift(1) < c.shift(2))
    return np.where(cond, 100.0, 0.0)


def cdl_invhammer(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (us >= 2 * body) & (ds <= 0.15 * rng) & (c.shift(1) < c.shift(2))
    return np.where(cond, 100.0, 0.0)


def cdl_hangingman(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (ds >= 2 * body) & (us <= 0.15 * rng) & (c.shift(1) > c.shift(2))
    return np.where(cond, -100.0, 0.0)


def cdl_shootingstar(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (us >= 2 * body) & (ds <= 0.15 * rng) & (c.shift(1) > c.shift(2))
    return np.where(cond, -100.0, 0.0)


def cdl_marubozu(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (body >= 0.95 * rng)
    return np.where(cond, np.where(bu, 100.0, -100.0), 0.0)


def cdl_spinningtop(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (body <= 0.3 * rng) & (us >= 0.3 * rng) & (ds >= 0.3 * rng)
    return np.where(cond, 100.0, 0.0)


def cdl_engulf_bull(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = be.shift(1, fill_value=False) & bu & (c >= o.shift(1)) & (o <= c.shift(1))
    return np.where(cond, 100.0, 0.0)


def cdl_engulf_bear(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = bu.shift(1, fill_value=False) & be & (o >= c.shift(1)) & (c <= o.shift(1))
    return np.where(cond, -100.0, 0.0)


def cdl_harami_bull(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    mx = pd.concat([o, c], axis=1).max(axis=1); mn = pd.concat([o, c], axis=1).min(axis=1)
    cond = be.shift(1, fill_value=False) & (body.shift(1) > 0) & (mx < o.shift(1)) & (mn > c.shift(1))
    return np.where(cond, 100.0, 0.0)


def cdl_harami_bear(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    mx = pd.concat([o, c], axis=1).max(axis=1); mn = pd.concat([o, c], axis=1).min(axis=1)
    cond = bu.shift(1, fill_value=False) & (body.shift(1) > 0) & (mx < c.shift(1)) & (mn > o.shift(1))
    return np.where(cond, -100.0, 0.0)


def cdl_piercing(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    mid = (o.shift(1) + c.shift(1)) / 2
    cond = be.shift(1, fill_value=False) & bu & (o < l.shift(1)) & (c > mid) & (c < o.shift(1))
    return np.where(cond, 100.0, 0.0)


def cdl_darkcloud(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    mid = (o.shift(1) + c.shift(1)) / 2
    cond = bu.shift(1, fill_value=False) & be & (o > h.shift(1)) & (c < mid) & (c > o.shift(1))
    return np.where(cond, -100.0, 0.0)


def cdl_morningstar(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    rng1 = (h.shift(1) - l.shift(1)).replace(0, np.nan)
    mid2 = (o.shift(2) + c.shift(2)) / 2
    cond = be.shift(2, fill_value=False) & (body.shift(1) <= 0.3 * rng1) & bu & (c > mid2)
    return np.where(cond.fillna(False), 100.0, 0.0)


def cdl_eveningstar(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    rng1 = (h.shift(1) - l.shift(1)).replace(0, np.nan)
    mid2 = (o.shift(2) + c.shift(2)) / 2
    cond = bu.shift(2, fill_value=False) & (body.shift(1) <= 0.3 * rng1) & be & (c < mid2)
    return np.where(cond.fillna(False), -100.0, 0.0)


def cdl_3whitesoldiers(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (bu & bu.shift(1, fill_value=False) & bu.shift(2, fill_value=False) &
            (c > c.shift(1)) & (c.shift(1) > c.shift(2)) &
            (o > o.shift(1)) & (o.shift(1) > o.shift(2)))
    return np.where(cond, 100.0, 0.0)


def cdl_3blackcrows(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (be & be.shift(1, fill_value=False) & be.shift(2, fill_value=False) &
            (c < c.shift(1)) & (c.shift(1) < c.shift(2)) &
            (o < o.shift(1)) & (o.shift(1) < o.shift(2)))
    return np.where(cond, -100.0, 0.0)


def cdl_beltuphold_bull(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = bu & (o == l) & (body >= 0.7 * rng) & (rng > 0)
    return np.where(cond, 100.0, 0.0)


def cdl_beltuphold_bear(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = be & (o == h) & (body >= 0.7 * rng) & (rng > 0)
    return np.where(cond, -100.0, 0.0)


def cdl_longleg_doji(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (body <= 0.1 * rng) & (us >= 0.35 * rng) & (ds >= 0.35 * rng)
    return np.where(cond, 100.0, 0.0)


def cdl_highwave(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    cond = (rng > 0) & (body <= 0.2 * rng) & ((us >= 0.4 * rng) | (ds >= 0.4 * rng))
    return np.where(cond, 100.0, 0.0)


def cdl_3inside_up(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    mx1 = pd.concat([o.shift(1), c.shift(1)], axis=1).max(axis=1)
    mn1 = pd.concat([o.shift(1), c.shift(1)], axis=1).min(axis=1)
    cond = be.shift(2, fill_value=False) & (mx1 < o.shift(2)) & (mn1 > c.shift(2)) & bu & (c > o.shift(2))
    return np.where(cond.fillna(False), 100.0, 0.0)


def cdl_3inside_dn(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    mx1 = pd.concat([o.shift(1), c.shift(1)], axis=1).max(axis=1)
    mn1 = pd.concat([o.shift(1), c.shift(1)], axis=1).min(axis=1)
    cond = bu.shift(2, fill_value=False) & (mx1 < c.shift(2)) & (mn1 > o.shift(2)) & be & (c < o.shift(2))
    return np.where(cond.fillna(False), -100.0, 0.0)


def cdl_tweezerbottom(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    tol = 0.05 * rng.replace(0, 1)
    cond = ((l - l.shift(1)).abs() <= tol) & be.shift(1, fill_value=False) & bu
    return np.where(cond, 100.0, 0.0)


def cdl_tweezertop(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    tol = 0.05 * rng.replace(0, 1)
    cond = ((h - h.shift(1)).abs() <= tol) & bu.shift(1, fill_value=False) & be
    return np.where(cond, -100.0, 0.0)


def cdl_kicking_bull(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    rng1 = (h.shift(1) - l.shift(1))
    cond = (be.shift(1, fill_value=False) & (body.shift(1) >= 0.9 * rng1) &
            bu & (body >= 0.9 * rng) & (o > o.shift(1)))
    return np.where(cond.fillna(False), 100.0, 0.0)


def cdl_kicking_bear(df):
    o, h, l, c, body, rng, us, ds, bu, be = _cndl(df)
    rng1 = (h.shift(1) - l.shift(1))
    cond = (bu.shift(1, fill_value=False) & (body.shift(1) >= 0.9 * rng1) &
            be & (body >= 0.9 * rng) & (o < o.shift(1)))
    return np.where(cond.fillna(False), -100.0, 0.0)


def cdl_gap_up(df):
    return np.where(df['low'] > df['high'].shift(1), 100.0, 0.0)


def cdl_gap_dn(df):
    return np.where(df['high'] < df['low'].shift(1), -100.0, 0.0)


for _nm, _fn in [
    ('cdl_doji', cdl_doji), ('cdl_dragonfly', cdl_dragonfly), ('cdl_gravestone', cdl_gravestone),
    ('cdl_hammer', cdl_hammer), ('cdl_invhammer', cdl_invhammer), ('cdl_hangingman', cdl_hangingman),
    ('cdl_shootingstar', cdl_shootingstar), ('cdl_marubozu', cdl_marubozu), ('cdl_spinningtop', cdl_spinningtop),
    ('cdl_engulf_bull', cdl_engulf_bull), ('cdl_engulf_bear', cdl_engulf_bear),
    ('cdl_harami_bull', cdl_harami_bull), ('cdl_harami_bear', cdl_harami_bear),
    ('cdl_piercing', cdl_piercing), ('cdl_darkcloud', cdl_darkcloud),
    ('cdl_morningstar', cdl_morningstar), ('cdl_eveningstar', cdl_eveningstar),
    ('cdl_3whitesoldiers', cdl_3whitesoldiers), ('cdl_3blackcrows', cdl_3blackcrows),
    ('cdl_beltuphold_bull', cdl_beltuphold_bull), ('cdl_beltuphold_bear', cdl_beltuphold_bear),
    ('cdl_longleg_doji', cdl_longleg_doji), ('cdl_highwave', cdl_highwave),
    ('cdl_3inside_up', cdl_3inside_up), ('cdl_3inside_dn', cdl_3inside_dn),
    ('cdl_tweezerbottom', cdl_tweezerbottom), ('cdl_tweezertop', cdl_tweezertop),
    ('cdl_kicking_bull', cdl_kicking_bull), ('cdl_kicking_bear', cdl_kicking_bear),
    ('cdl_gap_up', cdl_gap_up), ('cdl_gap_dn', cdl_gap_dn),
]:
    _reg(_nm, _fn)


# ثبتِ دسته‌ها در انتهای فایل انجام می‌شود (پس از تعریفِ همهٔ سازنده‌ها).
