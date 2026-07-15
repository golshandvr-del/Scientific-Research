"""
استراتژی ۱۹: Trend-Continuation Breakout + فیلتر ML اختصاصی
=============================================================
انگیزه: در s18 کشف شد که زیرمجموعه‌ی «breakout تداوم‌روند» پس از فیلتر ML به
WR≈۸۸٪ رسید (در حالی که breakout خام فقط ~۵۶٪ است). یعنی ML روی این نوع سیگنال
قدرت تفکیک فوق‌العاده دارد. اینجا این نوع ورود را **جداگانه** مدل و بهینه می‌کنیم
تا ببینیم آیا می‌توان به هدف اصلی (WR>70٪) با فرکانس معقول رسید.

تعریف سیگنال اولیه (فقط breakout):
  - روند صعودی: close>EMA50>EMA200
  - قدرت روند: ADX>20
  - شکست: close از سقف ۱۰ کندل قبلی عبور کند (کندل قبل زیر سقف بوده)
  - ساعات پرقدرت [8,9,10,13,14,15,20,21] UTC

featureها: featureهای استاندارد + fracdiff (مثل s18).
اعتبارسنجی: Purged Walk-Forward، embargo، بدون look-ahead.

تفاوت با s10 (SR-Breakout-Retest که WR=۴۷٪ شد): s10 روی retest بعد از شکست و
بدون فیلتر ML + بدون قید ساعت/ADX/روند-EMA بود؛ اینجا شکستِ در-جهت-روندِ قوی
در ساعات پرقدرت با فیلتر ML اختصاصی است — مفهوم و نتیجه کاملاً متفاوت.
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
POWER_HOURS = [8, 9, 10, 13, 14, 15, 20, 21]


def _frac_weights(d, size):
    w = [1.0]
    for k in range(1, size):
        w.append(-w[-1] * (d - k + 1) / k)
    return np.array(w[::-1])


def fracdiff_fixed(series, d=0.4, thres=1e-3):
    w = _frac_weights(d, 500)
    w_ = w[np.abs(w) > thres]
    width = len(w_)
    vals = series.values.astype(float)
    out = np.full(len(vals), np.nan)
    for i in range(width - 1, len(vals)):
        out[i] = np.dot(w_, vals[i - width + 1:i + 1])
    return out


def breakout_signal(df, donch=10, adx_th=20, hours=POWER_HOURS):
    close = df['close']; high = df['high']
    ema50 = ind.ema(close, 50); ema200 = ind.ema(close, 200)
    adx_, _, _ = ind.adx(df, 14)
    hour = df['dt'].dt.hour
    uptrend = (close > ema50) & (ema50 > ema200)
    strong = uptrend & (adx_ > adx_th)
    dh = high.rolling(donch).max().shift(1)
    brk = strong & (close > dh) & (close.shift(1) <= dh)
    if hours is not None:
        brk = brk & hour.isin(hours)
    return brk.fillna(False).values


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
                lab = 0; break
            if high[j] >= TP:
                lab = 1; break
            if low[j] <= SL:
                lab = 0; break
        labels[i] = lab
    return labels


def purged_wf(df, X, sig_idx, labels, hz, thr, n_folds=6, min_train_frac=0.4, embargo=50):
    n = len(df)
    sig = np.array(sorted(sig_idx))
    y = np.array([labels[i] for i in sig])
    Xv = X.iloc[sig].values
    bounds = np.linspace(int(n * min_train_frac), n, n_folds + 1).astype(int)
    approved = np.zeros(n, dtype=bool)
    proba_all = np.full(n, np.nan)
    for k in range(n_folds):
        lo, hi = bounds[k], bounds[k + 1]
        test_mask = (sig >= lo) & (sig < hi)
        train_mask = sig < (lo - hz - embargo)
        if train_mask.sum() < 150 or test_mask.sum() == 0:
            continue
        ytr = y[train_mask]
        if len(np.unique(ytr)) < 2:
            continue
        proba = np.zeros(test_mask.sum())
        for sd in (42, 7, 123):
            m = lgb.LGBMClassifier(
                n_estimators=300, learning_rate=0.03, num_leaves=31, max_depth=6,
                subsample=0.8, colsample_bytree=0.8, min_child_samples=20,
                reg_lambda=1.0, random_state=sd, n_jobs=-1, verbose=-1)
            m.fit(Xv[train_mask], ytr)
            proba += m.predict_proba(Xv[test_mask])[:, 1]
        proba /= 3
        proba_all[sig[test_mask]] = proba
        approved[sig[test_mask][proba >= thr]] = True
    return approved, proba_all


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
    X = feat.build_features(df).copy()
    logp = np.log(df['close'].values)
    X['fracdiff_04'] = fracdiff_fixed(pd.Series(logp), d=0.4, thres=1e-3)
    X['fracdiff_03'] = fracdiff_fixed(pd.Series(logp), d=0.3, thres=1e-3)

    sig = breakout_signal(df, donch=10, adx_th=20)
    sig_idx = np.array([i for i in np.where(sig)[0]
                        if i < len(df) - 60 and not np.isnan(atr.values[i])
                        and not X.iloc[i].isna().any()])
    print(f"کاندید breakout: {len(sig_idx)} | tpd_cal={len(sig_idx)/n_days:.2f}")

    # جاروب آستانه برای یافتن trade-off بین WR و فرکانس
    configs = [
        (1.0, 1.5, 48, thr) for thr in (0.45, 0.50, 0.55, 0.58, 0.60, 0.62, 0.65)
    ]

    print("\n=== نتایج Purged Walk-Forward (فقط breakout) ===")
    labels = triple_barrier(df, sig_idx, atr, 48, 1.0, 1.5)
    keys = np.array(sorted(labels.keys()))
    for tp, sl, hz, thr in configs:
        be = sl / (tp + sl)
        approved, _ = purged_wf(df, X, keys, labels, hz, thr)
        entries = np.zeros(len(df), dtype=bool); entries[approved] = True
        st, tr = run_backtest(df, entries, None, None, 'long', 0.20, hz, False,
                              sl_series=atr.values * sl, tp_series=atr.values * tp)
        nt, wr = st['n_trades'], st['win_rate']
        p = pvalue(round(wr / 100 * nt), nt, be)
        if nt > 0:
            d = df['dt'].dt.normalize().values[tr['entry_bar'].values]
            perday = pd.Series(d).value_counts()
            am, md = perday.mean(), perday.median()
        else:
            am = md = 0
        print(f"thr{thr} BE{be*100:.0f}% | n={nt} WR={wr:.2f}% exp={st['expectancy']:+.3f}$ "
              f"PnL={st['total_pnl']:+.0f}$ tpd_cal={nt/n_days:.2f} "
              f"tpd_active={am:.2f}(med{md:.0f}) p={p:.4f}")


if __name__ == '__main__':
    main()
