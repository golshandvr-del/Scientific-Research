"""
explore_moving_hurst_fast.py — Moving-Hurst برداری و آزمونِ قدرتِ پیش‌بینیِ رژیم
================================================================================
نسخهٔ سریعِ (vectorized) محاسبهٔ Moving-Hurst. آزمون: آیا در پنجره‌هایی که
Moving-Hurst بالاست، استراتژیِ «ادامهٔ روند» بازدهِ مثبت/معنادار دارد و در
پنجره‌های H پایین، «بازگشت به میانگین» بهتر است؟ (فرضیهٔ رژیم‌سوییچِ Serban/Kroha)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from backtest import load_data
import warnings; warnings.filterwarnings('ignore')


def moving_hurst_vectorized(logp, win=100, lags=(2, 4, 8, 16)):
    """
    Moving-Hurst سریع با روشِ lag-variance.
    برای هر lag، std(diff) روی پنجرهٔ متحرک با rolling محاسبه می‌شود.
    H = slope(log(std_tau) vs log(lag)) * 2
    """
    s = pd.Series(logp)
    n = len(s)
    log_lags = np.log(np.array(lags))
    # جمعِ برداریِ برای رگرسیونِ خطی: نیاز به std(diff_lag) روی پنجره
    tau_stack = np.full((len(lags), n), np.nan)
    for li, lag in enumerate(lags):
        diff = s.diff(lag)
        # std روی پنجرهٔ win (rolling)
        stdv = diff.rolling(win).std().values
        tau_stack[li] = np.sqrt(np.where(stdv > 0, stdv, np.nan))
    # رگرسیونِ خطی برداری برای هر ستون (زمان): slope = cov(x,y)/var(x)
    x = log_lags
    xm = x.mean()
    xvar = ((x - xm) ** 2).sum()
    H = np.full(n, np.nan)
    logtau = np.log(tau_stack)  # (Lags, n)
    ym = np.nanmean(logtau, axis=0)  # میانگینِ y برای هر زمان
    # cov: sum((x-xm)*(y-ym))
    cov = np.nansum(((x[:, None] - xm) * (logtau - ym[None, :])), axis=0)
    slope = cov / xvar
    H = slope * 2.0
    return H


def analyze(csv, name, win=100):
    df = load_data(csv)
    close = df['close'].values
    logp = np.log(close)
    n = len(df)
    mh = moving_hurst_vectorized(logp, win=win)
    valid_mh = mh[~np.isnan(mh)]
    print(f"\n{'='*72}\n  {name}  (n={n})  Moving-Hurst پنجره={win}\n{'='*72}")
    print(f"  توزیعِ Moving-Hurst: میانگین={np.nanmean(mh):.3f}  "
          f"چارک‌ها=[{np.nanpercentile(valid_mh,25):.3f}, "
          f"{np.nanpercentile(valid_mh,50):.3f}, {np.nanpercentile(valid_mh,75):.3f}]  "
          f"%(H>0.55)={100*np.mean(valid_mh>0.55):.1f}%  %(H<0.45)={100*np.mean(valid_mh<0.45):.1f}%")

    for k in [4, 8, 16, 32]:
        recent = np.full(n, np.nan); recent[k:] = np.sign(logp[k:] - logp[:-k])
        f = np.full(n, np.nan); f[:n-k] = (close[k:]/close[:n-k]-1)*1e4
        trend_follow = recent * f       # بازدهِ «ادامهٔ روند»
        mean_revert = -recent * f       # بازدهِ «بازگشت» (خلافِ روند)
        base = np.abs(f)                 # مبنا
        v = ~np.isnan(mh) & ~np.isnan(trend_follow) & ~np.isnan(recent)
        hi = v & (mh > 0.55)
        lo = v & (mh < 0.45)
        mid = v & (mh >= 0.45) & (mh <= 0.55)
        def st(x):
            x = x[~np.isnan(x)]
            if len(x) < 30: return (len(x), np.nan, np.nan)
            return (len(x), x.mean(), x.mean()/(x.std(ddof=1)/np.sqrt(len(x))))
        # در رژیمِ روند: trend_follow ؛ در رژیمِ بازگشت: mean_revert
        n_hi, m_hi, t_hi = st(trend_follow[hi])
        n_lo, m_lo, t_lo = st(mean_revert[lo])
        n_mid, m_mid, t_mid = st(trend_follow[mid])
        print(f"  k={k:<3}| روندگیری@H>0.55: n={n_hi:<6} {m_hi:+.2f}bps t={t_hi:+.2f}"
              f" | بازگشت@H<0.45: n={n_lo:<6} {m_lo:+.2f}bps t={t_lo:+.2f}"
              f" | روندگیری@mid: {m_mid:+.2f}bps t={t_mid:+.2f}")


if __name__ == '__main__':
    for csv, name in [('data/XAUUSD_M15.csv', 'XAUUSD M15'),
                      ('data/XAUUSD_H1.csv', 'XAUUSD H1'),
                      ('data/EURUSD_M15.csv', 'EURUSD M15')]:
        if os.path.exists(csv):
            for win in [50, 100, 200]:
                analyze(csv, name, win=win)
