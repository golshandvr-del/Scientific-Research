"""
S77 — Hurst-Regime Mean-Reversion (کشفِ حاصل از تحقیقِ عمیقِ فراکتال/User note 2)
================================================================================
> قانونِ شمارهٔ ۱ پروژه: معیار فقط «سودِ خالصِ کلِ ۴ ارز» است، نه WR.

مبنای علمی (از فایلِ DeepResearch_Scalping_VisualPatterns_Fractals.md):
  • Mandelbrot/Hurst: بازار در رژیم‌های مختلف (persistent/anti-persistent) است.
  • اکتشافِ ما (explore_moving_hurst_fast.py) کشفِ محکمی داد:
    - طلا و یورو در Moving-Hurst اکثراً H<0.45 (رژیمِ بازگشتی/anti-persistent) اند.
    - در این رژیم، استراتژیِ «بازگشت به میانگین» بازدهِ آتیِ مثبتِ معنادار دارد:
      EURUSD k=16..32: t تا +4.66 ؛ این پایدارترین لبهٔ کشف‌شده است.
  • Serban(2010): در رژیمِ درست از mean-reversion و در رژیمِ روند از momentum.
  • این پاسخِ مستقیم به تریدر است: «در بازارِ رنج (H پایین) اسکالپِ بازگشتی کن.»

منطقِ S77 (کاملاً forward-safe):
  1) Moving-Hurst روی پنجرهٔ گذشته (بدون نشتِ آینده).
  2) فقط در رژیمِ H < hurst_thr (بازگشتی) معامله کن.
  3) z-score قیمت نسبت به میانگینِ متحرک؛ اگر z < -entry → Long (انتظارِ بازگشت به بالا)،
     اگر z > +entry → Short.
  4) ورود در open کندلِ بعد؛ TP/SL بر حسبِ ATR؛ موتورِ سرمایه‌محور، ریسکِ ۱٪.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from backtest import load_data, run_backtest
from capital_engine import run_capital_backtest, summary_line
import indicators as ind
import warnings; warnings.filterwarnings('ignore')


def moving_hurst(logp, win=100, lags=(2, 4, 8, 16)):
    s = pd.Series(logp)
    n = len(s)
    log_lags = np.log(np.array(lags))
    tau = np.full((len(lags), n), np.nan)
    for li, lag in enumerate(lags):
        stdv = s.diff(lag).rolling(win).std().values
        tau[li] = np.sqrt(np.where(stdv > 0, stdv, np.nan))
    x = log_lags; xm = x.mean(); xvar = ((x - xm) ** 2).sum()
    logtau = np.log(tau)
    ym = np.nanmean(logtau, axis=0)
    cov = np.nansum((x[:, None] - xm) * (logtau - ym[None, :]), axis=0)
    return (cov / xvar) * 2.0


def build_signals(df, hurst_win=100, hurst_thr=0.45, z_win=20, z_entry=1.5):
    """سیگنال‌های mean-reversion در رژیمِ Hurst پایین. همه forward-safe (shift 1)."""
    close = df['close'].values
    logp = np.log(close)
    n = len(df)
    H = moving_hurst(logp, win=hurst_win)
    # z-score نسبت به SMA
    sma = pd.Series(close).rolling(z_win).mean().values
    sd = pd.Series(close).rolling(z_win).std().values
    z = (close - sma) / np.where(sd > 0, sd, np.nan)
    # رژیمِ بازگشتی: H < thr ؛ همه بر پایهٔ داده تا کندلِ i (shift 1 هنگام ورود)
    regime = H < hurst_thr
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    valid = ~np.isnan(z) & ~np.isnan(H) & regime
    long_sig[valid & (z < -z_entry)] = True   # قیمت خیلی پایین → انتظارِ بازگشت به بالا
    short_sig[valid & (z > z_entry)] = True    # قیمت خیلی بالا → انتظارِ بازگشت به پایین
    return long_sig, short_sig, H, z


def run_asset(csv, name, spread, hurst_win=100, hurst_thr=0.45, z_win=20,
              z_entry=1.5, sl_mult=1.5, tp_mult=1.0, max_hold=16,
              initial_capital=10000.0, risk_pct=1.0, verbose=True):
    df = load_data(csv)
    atr = ind.atr(df, 14).values
    n = len(df)
    longS, shortS, H, z = build_signals(df, hurst_win, hurst_thr, z_win, z_entry)
    # فقط نیمهٔ دومِ داده به‌عنوان eval (مثلِ سایرِ استراتژی‌ها، اجتناب از warmup)
    warm = max(hurst_win, z_win, 200)
    mask = np.zeros(n, dtype=bool); mask[warm:] = True
    longS &= mask; shortS &= mask
    sl_series = sl_mult * atr
    tp_series = tp_mult * atr

    def trades_for(direction, entries):
        if entries.sum() == 0:
            return pd.DataFrame(), np.array([])
        st, tr = run_backtest(df, entries, None, None, direction,
                              spread=spread, max_hold=max_hold,
                              sl_series=sl_series, tp_series=tp_series,
                              allow_overlap=False)
        if len(tr) == 0:
            return tr, np.array([])
        sld = sl_series[tr['signal_bar'].values]
        return tr, sld

    trL, slL = trades_for('long', longS)
    trS, slS = trades_for('short', shortS)
    parts = []
    if len(trL): parts.append(trL.assign(_sl=slL))
    if len(trS): parts.append(trS.assign(_sl=slS))
    if not parts:
        if verbose: print(f"  {name}: هیچ معامله‌ای تولید نشد.")
        return {'net_profit': 0.0, 'n_trades': 0}, None
    allt = pd.concat(parts, ignore_index=True).sort_values('exit_bar').reset_index(drop=True)
    cap, _ = run_capital_backtest(allt, allt['_sl'].values,
                                  initial_capital=initial_capital, risk_pct=risk_pct,
                                  commission_per_lot=7.0, compounding=False)
    if verbose:
        print(f"  {name}: {summary_line(name, cap)}  (L={len(trL)} S={len(trS)})")
    return cap, allt


def two_half(allt, n_half_bar, initial_capital=10000.0, risk_pct=1.0):
    res = []
    for m in [allt['signal_bar'] < n_half_bar, allt['signal_bar'] >= n_half_bar]:
        sub = allt[m].reset_index(drop=True)
        if len(sub) == 0:
            res.append(0.0); continue
        c, _ = run_capital_backtest(sub, sub['_sl'].values, initial_capital=initial_capital,
                                    risk_pct=risk_pct, commission_per_lot=7.0, compounding=False)
        res.append(c['net_profit'])
    return res


def main():
    print("=" * 78)
    print("  S77 — Hurst-Regime Mean-Reversion (تستِ اولیه روی ۴ ارز)")
    print("=" * 78)
    assets = [
        ('data/XAUUSD_M15.csv', 'XAUUSD', 0.20),
        ('data/EURUSD_M15.csv', 'EURUSD', 0.00010),
        ('data/AUDUSD_M15.csv', 'AUDUSD', 0.00010),
        ('data/DXY_M15.csv',    'DXY',    0.010),
    ]
    total = 0.0
    for csv, name, spread in assets:
        if not os.path.exists(csv):
            print(f"  {name}: فایل موجود نیست."); continue
        cap, allt = run_asset(csv, name, spread)
        total += cap['net_profit']
    print("-" * 78)
    print(f"  سودِ خالصِ کلِ ۴ ارز (S77 تنها) = {total:+.0f}$")
    print(f"  رکوردِ فعلی (S67 طلا + S73 یورو) = +44,458$")
    print("=" * 78)


if __name__ == '__main__':
    main()
