"""
explore_hurst_regime.py — آزمونِ فرضیهٔ مرکزیِ تحقیق (فراکتال/Hurst روی طلا)
================================================================================
User note 2 خواست پیش از هرچیز فراکتال‌ها را عمیق بررسی کنیم. تحقیق (فایلِ
DeepResearch...md) نشان داد:
  • Hurst روی TFِ کوتاه ≈ 0.5 (random walk)، روی TFِ بلند > 0.5 (trend).
  • Moving Hurst می‌تواند رژیم (روند/رنج/بازگشت) را لحظه‌ای تشخیص دهد.

این اسکریپت فقط «اکتشاف» است (نه استراتژی). می‌سنجد:
 1) نمای هرستِ کلیِ طلا روی افق‌های مختلف (پاسخ به «چه تایم‌فریمی؟»).
 2) آیا وقتی Moving-Hurst بالاست، بازدهِ آتیِ روند-پیرو واقعاً بیشتر است؟
    (آیا Hurst یک فیلترِ رژیمِ واقعی است یا خیر)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from backtest import load_data
import warnings; warnings.filterwarnings('ignore')


def hurst_rs(ts):
    """نمای هرست به روشِ lag-variance (Longmore/Quantstart). ts: آرایهٔ log-price."""
    ts = np.asarray(ts, dtype=float)
    n = len(ts)
    if n < 20:
        return np.nan
    lags = range(2, min(20, n // 2))
    tau = []
    for lag in lags:
        diff = ts[lag:] - ts[:-lag]
        tau.append(np.sqrt(np.std(diff)))
    lags = np.array(list(lags))
    tau = np.array(tau)
    good = tau > 0
    if good.sum() < 3:
        return np.nan
    # شیبِ log(tau) بر log(lag) ؛ H = 2*slope (چون tau ~ std نه var)
    poly = np.polyfit(np.log(lags[good]), np.log(tau[good]), 1)
    return poly[0] * 2.0


def global_hurst_by_horizon(csv, name):
    """نمای هرستِ کلی روی بازده‌های k-کندلیِ مختلف — پاسخ به «چه تایم‌فریمی؟»"""
    df = load_data(csv)
    logp = np.log(df['close'].values)
    print(f"\n{'='*70}\n  {name}  (n={len(df)})  — نمای هرستِ کلی روی افق‌های مختلف\n{'='*70}")
    print(f"  {'افق (k کندل)':<18}{'Hurst':>10}   رژیم")
    for k in [1, 2, 4, 8, 16, 32, 64, 128]:
        # سری log-price نمونه‌برداری‌شده هر k کندل
        sub = logp[::k]
        h = hurst_rs(sub)
        reg = 'روند (persistent)' if h > 0.55 else ('بازگشت (mean-rev)' if h < 0.45 else 'تصادفی (random walk)')
        print(f"  {k:<18}{h:>10.3f}   {reg}")


def moving_hurst_predictive(csv, name, win=100):
    """آیا Moving-Hurst پیش‌بینی‌کنندهٔ کیفیتِ روند است؟"""
    df = load_data(csv)
    close = df['close'].values
    logp = np.log(close)
    n = len(df)
    # Moving Hurst روی پنجرهٔ win
    mh = np.full(n, np.nan)
    for i in range(win, n):
        mh[i] = hurst_rs(logp[i - win:i])
    # بازدهِ آتیِ «روند-پیرو» با افقِ k: علامتِ حرکتِ اخیر × بازدهِ آتی
    print(f"\n{'='*70}\n  {name}  — قدرتِ پیش‌بینیِ Moving-Hurst (پنجره={win})\n{'='*70}")
    for k in [4, 8, 16, 32]:
        mom = np.zeros(n)  # علامتِ روندِ اخیر (بازدهِ k کندلِ گذشته)
        fut = np.full(n, np.nan)
        mom[k:] = np.sign(close[k:] - close[:-k])[:len(mom)-k] if False else 0
        # جهتِ روندِ اخیر
        recent = np.full(n, np.nan); recent[k:] = np.sign(logp[k:] - logp[:-k])
        # بازدهِ آتیِ روند-پیرو (bps): جهتِ اخیر × بازدهِ k کندلِ بعد
        f = np.full(n, np.nan); f[:n-k] = (close[k:]/close[:n-k]-1)*1e4
        tf = recent * f  # بازدهِ استراتژیِ «ادامهٔ روند»
        valid = ~np.isnan(mh) & ~np.isnan(tf) & ~np.isnan(recent)
        hi = valid & (mh > 0.55)   # رژیمِ روند
        lo = valid & (mh < 0.45)   # رژیمِ بازگشت
        def stat(m):
            x = tf[m]
            if len(x) < 30: return (len(x), np.nan, np.nan)
            t = x.mean()/(x.std(ddof=1)/np.sqrt(len(x)))
            return (len(x), x.mean(), t)
        n_hi, m_hi, t_hi = stat(hi)
        n_lo, m_lo, t_lo = stat(lo)
        print(f"  k={k:<3} روند-پیرو | H>0.55: n={n_hi:<6} mean={m_hi:+.2f}bps t={t_hi:+.2f}"
              f"  || H<0.45: n={n_lo:<6} mean={m_lo:+.2f}bps t={t_lo:+.2f}")
    print("  تفسیر: اگر در H>0.55 بازدهِ روند-پیرو مثبت‌تر/معنادارتر باشد، Hurst فیلترِ رژیمِ واقعی است.")


if __name__ == '__main__':
    print("########## آزمونِ فرضیهٔ فراکتال/Hurst روی دادهٔ واقعی ##########")
    for csv, name in [('data/XAUUSD_M15.csv', 'XAUUSD M15'),
                      ('data/XAUUSD_H1.csv', 'XAUUSD H1'),
                      ('data/XAUUSD_H4.csv', 'XAUUSD H4')]:
        if os.path.exists(csv):
            global_hurst_by_horizon(csv, name)
    for csv, name in [('data/XAUUSD_M15.csv', 'XAUUSD M15'),
                      ('data/XAUUSD_H1.csv', 'XAUUSD H1')]:
        if os.path.exists(csv):
            moving_hurst_predictive(csv, name, win=100)
