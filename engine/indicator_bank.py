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


# ثبتِ دسته‌ها در انتهای فایل انجام می‌شود (پس از تعریفِ همهٔ سازنده‌ها).
