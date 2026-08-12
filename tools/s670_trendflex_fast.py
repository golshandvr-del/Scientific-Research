# -*- coding: utf-8 -*-
"""S670 — TrendFlex برداری‌شده (پورتِ سریعِ engine/indicator_bank.trendflex).

چرا این فایل وجود دارد: نسخه‌ی بانک حلقه‌ی خالص پایتونی O(n·period) دارد و
روی M1 با ۵ میلیون سطر و period≈21 یعنی ~۱۰۰ میلیون تکرارِ پایتونی — ساعت‌ها.
این پورت همان ریاضیات را با scipy.signal.lfilter + cumsum انجام می‌دهد.

اثبات هم‌ارزی (باید با parity_check تست شود، نه فرض):
  1) SSF اِهلرز: out[i] = c1·(x[i]+x[i−1])/2 + c2·out[i−1] + c3·out[i−2]
     ⇔ فیلتر IIR با b=[c1/2, c1/2], a=[1, −c2, −c3] به‌علاوه‌ی شرط اولیه‌ی
     out[0]=x[0], out[1]=x[1] که با zi و بازنویسی دو نمونه‌ی اول اعمال می‌شود.
  2) s[i] = (1/p)·Σ_{k=1..p}(ssf[i]−ssf[i−k]) = ssf[i] − mean(ssf[i−p..i−1])
  3) ms[i] = 0.04·s²[i] + 0.96·ms[i−1] ⇔ lfilter(b=[0.04], a=[1,−0.96], s²)
  4) out[i] = s[i]/√ms[i] اگر ms≠0 وگرنه 0؛ و برای i<period مقدار 0
     (در نسخه‌ی بانک حلقه از i=period شروع می‌شود).
"""
import numpy as np
from scipy.signal import lfilter


def ssf_fast(xv: np.ndarray, period: float) -> np.ndarray:
    """Ehlers Super Smoother — هم‌ارزِ بیت‌به‌بیتِ _ssf_arr بانک."""
    xv = np.asarray(xv, dtype=np.float64)
    n = len(xv)
    a = np.exp(-1.414 * np.pi / period)
    b = 2 * a * np.cos(1.414 * np.pi / period)
    c2 = b; c3 = -a * a; c1 = 1 - c2 - c3
    if n < 3:
        return xv.copy()
    out = np.empty(n)
    out[0] = xv[0]; out[1] = xv[1]
    # فیلتر از i=2 شروع می‌شود؛ حالت اولیه‌ی lfilter را طوری می‌سازیم که
    # دقیقاً همان بازگشتِ بانک را ادامه دهد. برای فرم مستقیم II ترانهاده:
    #   y[i] = b0·x[i] + z0[i−1]
    #   z0[i] = b1·x[i] − a1·y[i] + z1[i−1]
    #   z1[i] = −a2·y[i]
    # با y[1]=out[1], x[1]=xv[1], y[0]=out[0]:
    b_c = np.array([c1 / 2, c1 / 2])
    a_c = np.array([1.0, -c2, -c3])
    z0 = b_c[1] * xv[1] + c2 * out[1] + c3 * out[0]
    z1 = c3 * out[1]
    out[2:], _ = lfilter(b_c, a_c, xv[2:], zi=np.array([z0, z1]))
    return out


def trendflex_fast(close: np.ndarray, period: int = 20) -> np.ndarray:
    """هم‌ارزِ engine.indicator_bank.trendflex ولی برداری."""
    xv = np.asarray(close, dtype=np.float64)
    n = len(xv)
    ssf = ssf_fast(xv, period / 2)
    # s[i] = ssf[i] − mean(ssf[i−period .. i−1])  فقط برای i ≥ period
    cs = np.concatenate(([0.0], np.cumsum(ssf)))
    s = np.zeros(n)
    idx = np.arange(period, n)
    s[idx] = ssf[idx] - (cs[idx] - cs[idx - period]) / period
    # ms[i] = 0.04·s² + 0.96·ms[i−1] — برای i<period، s=0 پس ms هم 0 می‌ماند
    ms = lfilter([0.04], [1.0, -0.96], s * s)
    out = np.zeros(n)
    nz = ms > 0
    out[nz] = s[nz] / np.sqrt(ms[nz])
    return out


def parity_check(n: int = 30000, period: int = 20, seed: int = 42) -> dict:
    """مقایسه با نسخه‌ی مرجعِ بانک روی داده‌ی تصادفی + گزارش بیشینه‌ی خطا."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import pandas as pd
    from engine import indicator_bank as ib
    rng = np.random.default_rng(seed)
    px = 2000 + np.cumsum(rng.normal(0, 1, n))
    df = pd.DataFrame({'open': px, 'high': px + 0.5, 'low': px - 0.5,
                       'close': px, 'volume': np.ones(n)})
    ref = ib.trendflex(df, period=period).values
    fast = trendflex_fast(px, period=period)
    err = np.max(np.abs(ref - fast))
    rel = err / max(np.max(np.abs(ref)), 1e-12)
    return {'max_abs_err': float(err), 'max_rel_err': float(rel),
            'ok': bool(rel < 1e-9)}


if __name__ == '__main__':
    for p in (13, 20, 21, 34):
        r = parity_check(period=p)
        print(f'period={p:3d}  max_abs_err={r["max_abs_err"]:.3e}  '
              f'rel={r["max_rel_err"]:.3e}  ok={r["ok"]}')
