# -*- coding: utf-8 -*-
# ============================================================================
# numba.py — «shim»/جایگزینِ بی‌اثرِ numba برای اجرا در Pyodide (WebView/APK)
# ----------------------------------------------------------------------------
# چرا؟ موتورِ واقعیِ پروژه (engine/dynamic_backtest.py, features.py, structure.py)
# از `from numba import njit` و دکوراتورِ `@njit(cache=True)` برای شتابِ عددی
# استفاده می‌کند. Pyodide (CPython کامپایل‌شده به WASM) بستهٔ numba را ندارد.
#
# راهِ نبوغانه (بدونِ تغییرِ حتی یک خط از موتورِ واقعی): این فایل را در مسیرِ
# جست‌وجوی ماژول‌ها قرار می‌دهیم تا `import numba` این نسخهٔ ساختگی را بیابد.
# `njit` این‌جا یک دکوراتورِ pass-through است: تابعِ پایتونِ خالصِ زیرش را عیناً
# و بدونِ کامپایلِ JIT اجرا می‌کند. نتیجه ۱۰۰٪ یکسان است، فقط کندتر — که برای
# اجرای یک‌بارهٔ بک‌تست/سیگنالِ زنده روی موبایل کاملاً قابل‌قبول است.
#
# این کار تضمین می‌کند فایل‌های واقعیِ برندهٔ پروژه «بدونِ بازنویسی» در APK اجرا شوند.
# ============================================================================


def njit(*args, **kwargs):
    """
    جایگزینِ بی‌اثرِ numba.njit. از هر دو شکلِ فراخوانی پشتیبانی می‌کند:
        @njit
        def f(...): ...
    و
        @njit(cache=True, parallel=True, ...)
        def f(...): ...
    در هر دو حالت، تابعِ اصلی را دست‌نخورده برمی‌گرداند.
    """
    # حالتِ «@njit» بدونِ پرانتز: args[0] خودِ تابع است.
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]

    # حالتِ «@njit(cache=True, ...)»: باید یک دکوراتور برگردانیم.
    def _decorator(func):
        return func
    return _decorator


def jit(*args, **kwargs):
    """مترادفِ njit برای پوششِ کاملِ کدهایی که از numba.jit استفاده می‌کنند."""
    return njit(*args, **kwargs)


def prange(*args, **kwargs):
    """
    جایگزینِ numba.prange با range معمولی (اجرای ترتیبی به‌جای موازی).
    خروجی از نظرِ محاسباتی کاملاً یکسان است.
    """
    return range(*args, **kwargs)


# برخی کدها ممکن است این ثابت‌ها/انواع را وارد کنند؛ برای ایمنی تعریف می‌کنیم.
int32 = int
int64 = int
float32 = float
float64 = float
boolean = bool


class _TypesNamespace:
    """پوششِ numba.types در صورتِ import شدن."""
    int32 = int
    int64 = int
    float32 = float
    float64 = float
    boolean = bool


types = _TypesNamespace()

__version__ = "0.0.0-pyodide-shim"
