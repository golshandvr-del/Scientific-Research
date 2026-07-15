"""
استراتژی ۱۸: Multi-Signal Ensemble + Fractional Differentiation
==================================================================
هدف: عبور هم‌زمان از (الف) WR>60٪ و (ب) ≥۳ معامله/روز فعال، با سودآوری.

تمایز نسبت به کارهای قبلی (s01..s17):
  - همه‌ی کارهای قبلی از یک نوع ورود واحد (فقط pullback یا فقط breakout یا
    فقط golden-window) استفاده می‌کردند → فرکانس محدود بود.
  - اینجا دو نوع ورود مکمل و مستقل ترکیب می‌شوند تا نرخ سیگنال ~۲–۳ برابر شود:
      A) Pullback-Reversal در روند صعودی (RSI اصلاح + چرخش به بالا)
      B) Trend-Continuation Breakout (شکست سقف کوتاه در روند قوی با ADX)
    هر ورود در «ساعات پرقدرت» (لندن/نیویورک) که در s17 کشف شد فیلتر می‌شود.
  - افزودن feature تازه: Fractional Differentiation لگاریتم قیمت
    (López de Prado, AFML ch.5) — یک سری ایستا که «حافظه»ی بلندمدت روند را
    حفظ می‌کند؛ هیچ‌کدام از featureهای قبلی این خاصیت را نداشتند.
  - یک مدل ML واحد روی مجموعه‌ی هر دو نوع ورود آموزش می‌بیند و کیفیت هر
    سیگنال را جدا امتیاز می‌دهد → precision (=WR) بالا با فرکانس بالا.

اعتبارسنجی: Purged Walk-Forward با embargo (بدون look-ahead).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scipy import stats
import lightgbm as lgb
import indicators as ind
import features as feat
from backtest import load_data, run_backtest

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')

# ساعات پرقدرت کشف‌شده در s17 (سشن لندن ~۹ و نیویورک ~۱۵ + بعدازظهر US)
POWER_HOURS = [8, 9, 10, 13, 14, 15, 20, 21]


# ----------------------- Fractional Differentiation -----------------------
def _frac_weights(d, size):
    w = [1.0]
    for k in range(1, size):
        w.append(-w[-1] * (d - k + 1) / k)
    return np.array(w[::-1])


def fracdiff_fixed(series, d=0.4, thres=1e-3):
    """تفاضل کسری با پنجره‌ی ثابت (López de Prado). سری ایستا با حافظه‌ی بلند."""
    w = _frac_weights(d, 500)
    w_ = w[np.abs(w) > thres]
    width = len(w_)
    vals = series.values.astype(float)
    out = np.full(len(vals), np.nan)
    for i in range(width - 1, len(vals)):
        out[i] = np.dot(w_, vals[i - width + 1:i + 1])
    return out


# ----------------------- سیگنال‌های اولیه‌ی مکمل -----------------------
def primary_signals(df):
    """
    دو نوع ورود مکمل برمی‌گرداند (هر دو long، در ساعات پرقدرت):
      A) pullback-reversal   B) trend-continuation breakout
    خروجی: (sig_bool, sig_type)  که sig_type: 0=pullback، 1=breakout
    """
    close = df['close']; high = df['high']
    ema50 = ind.ema(close, 50); ema200 = ind.ema(close, 200)
    rsi = ind.rsi(close, 14)
    adx = ind.adx(df, 14) if hasattr(ind, 'adx') else None
    hour = df['dt'].dt.hour
    powh = hour.isin(POWER_HOURS)

    uptrend = (close > ema50) & (ema50 > ema200)

    # A) Pullback-Reversal: اصلاح RSI و چرخش به بالا در روند
    pullback = uptrend & (rsi < 55) & (rsi > rsi.shift(1))

    # B) Trend-Continuation: شکست سقف ۱۰ کندل قبلی در روند قوی
    donch10 = high.rolling(10).max().shift(1)
    strong = uptrend
    if adx is not None:
        strong = strong & (adx > 20)
    breakout = strong & (close > donch10) & (close.shift(1) <= donch10)

    sigA = (pullback & powh).fillna(False)
    sigB = (breakout & powh).fillna(False)

    sig = (sigA | sigB)
    stype = np.where(sigB.values, 1, 0)  # اگر هر دو، breakout غالب
    return sig.values, stype


# ----------------------- Triple-Barrier labeling -----------------------
def triple_barrier(df, sig_idx, atr, hz, tp_mult, sl_mult):
    high = df['high'].values; low = df['low'].values; close = df['close'].values
    av = atr.values; n = len(df); labels = {}
    for i in sig_idx:
        a = av[i]
        if np.isnan(a) or a <= 0:
            continue
        entry = close[i]; TP = entry + tp_mult * a; SL = entry - sl_mult * a
        lab = 0
        for j in range(i + 1, min(i + 1 + hz, n)):
            if low[j] <= SL and high[j] >= TP:
                lab = 0; break            # هر دو در یک کندل → بدبینانه SL
            if high[j] >= TP:
                lab = 1; break
            if low[j] <= SL:
                lab = 0; break
        labels[i] = lab
    return labels


# ----------------------- Purged Walk-Forward -----------------------
def purged_wf(df, X, sig_idx, labels, hz, thr, n_folds=6, min_train_frac=0.4, embargo=50):
    n = len(df)
    sig = np.array(sorted(sig_idx))
    y = np.array([labels[i] for i in sig])
    Xv = X.iloc[sig].values
    bounds = np.linspace(int(n * min_train_frac), n, n_folds + 1).astype(int)
    approved = np.zeros(n, dtype=bool)
    for k in range(n_folds):
        lo, hi = bounds[k], bounds[k + 1]
        test_mask = (sig >= lo) & (sig < hi)
        train_mask = sig < (lo - hz - embargo)
        if train_mask.sum() < 200 or test_mask.sum() == 0:
            continue
        ytr = y[train_mask]
        if len(np.unique(ytr)) < 2:
            continue
        proba = np.zeros(test_mask.sum())
        for sd in (42, 7, 123):
            m = lgb.LGBMClassifier(
                n_estimators=300, learning_rate=0.03, num_leaves=31, max_depth=6,
                subsample=0.8, colsample_bytree=0.8, min_child_samples=30,
                reg_lambda=1.0, random_state=sd, n_jobs=-1, verbose=-1)
            m.fit(Xv[train_mask], ytr)
            proba += m.predict_proba(Xv[test_mask])[:, 1]
        proba /= 3
        approved[sig[test_mask][proba >= thr]] = True
    return approved


def pvalue(wins, n, p0):
    if n == 0:
        return 1.0
    return float(1 - stats.norm.cdf((wins / n - p0) / np.sqrt(p0 * (1 - p0) / n)))


def main():
    print("در حال بارگذاری داده...")
    df = load_data(DATA)
    n_days = df['dt'].dt.normalize().nunique()
    atr = ind.atr(df, 14)

    print("ساخت featureها + fracdiff...")
    X = feat.build_features(df)
    # افزودن featureهای تازه
    logp = np.log(df['close'].values)
    X = X.copy()
    X['fracdiff_04'] = fracdiff_fixed(pd.Series(logp), d=0.4, thres=1e-3)
    X['fracdiff_03'] = fracdiff_fixed(pd.Series(logp), d=0.3, thres=1e-3)

    sig, stype = primary_signals(df)
    X['sig_type'] = 0
    X.loc[sig, 'sig_type'] = stype[sig]

    # کاندیدهای معتبر (بدون NaN، دور از انتهای داده)
    sig_idx = [i for i in np.where(sig)[0]
               if i < len(df) - 60 and not np.isnan(atr.values[i])
               and not X.iloc[i].isna().any()]
    sig_idx = np.array(sig_idx)
    n_break = int(stype[sig_idx].sum()); n_pull = len(sig_idx) - n_break
    print(f"کاندید اولیه: {len(sig_idx)} (pullback={n_pull}, breakout={n_break}) "
          f"| tpd_cal={len(sig_idx)/n_days:.2f}")

    configs = [
        # (tp, sl, hz, thr)
        (1.0, 1.5, 48, 0.50),
        (1.0, 1.5, 48, 0.55),
        (1.0, 1.5, 48, 0.58),
        (1.2, 1.5, 48, 0.55),
        (1.0, 1.3, 40, 0.55),
    ]

    print("\n=== نتایج Purged Walk-Forward ===")
    for tp, sl, hz, thr in configs:
        be = sl / (tp + sl)
        labels = triple_barrier(df, sig_idx, atr, hz, tp, sl)
        keys = np.array(sorted(labels.keys()))
        approved = purged_wf(df, X, keys, labels, hz, thr)
        entries = np.zeros(len(df), dtype=bool); entries[approved] = True
        st, tr = run_backtest(df, entries, None, None, 'long', 0.20, hz, False,
                              sl_series=atr.values * sl, tp_series=atr.values * tp)
        nt, wr = st['n_trades'], st['win_rate']
        p = pvalue(round(wr / 100 * nt), nt, be)
        # فرکانس فعال
        if nt > 0:
            d = df['dt'].dt.normalize().values[tr['entry_bar'].values]
            perday = pd.Series(d).value_counts()
            act_mean, act_med = perday.mean(), perday.median()
        else:
            act_mean = act_med = 0
        print(f"TP{tp}/SL{sl} hz{hz} thr{thr} BE{be*100:.0f}% | "
              f"n={nt} WR={wr:.2f}% exp={st['expectancy']:+.3f}$ PnL={st['total_pnl']:+.0f}$ "
              f"tpd_cal={nt/n_days:.2f} tpd_active={act_mean:.2f}(med{act_med:.0f}) p={p:.3f}")


if __name__ == '__main__':
    main()
