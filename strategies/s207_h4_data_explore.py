"""
s207_h4_data_explore.py — تحلیلِ اکتشافیِ XAUUSD H4 «بگذار داده حرف بزند»
================================================================================
> قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD + EURUSD). WR≥40٪ فقط کفِ پذیرش.
> پاسخ به User Note جدید: «تایم‌فریمِ هدف = H4. اول داده را بررسی کن و بگذار
> حرف بزند.» (نشستِ قبل H1 را کامل بست: S196–S206؛ رکورد +$252,471.)

خروجی: آمارِ خامِ اکتشافی (بدونِ معامله) تا تصمیم بگیریم کدام لایه‌ها را روی H4
بیاوریم و با چه تنظیمِ TP/SL/max_hold. مقایسه با H1/M15 برای بازتنظیم.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

RESULTS = os.path.join(ROOT, 'results')
DATA_H4 = os.path.join(ROOT, 'data', 'XAUUSD_H4.csv')
DATA_H1 = os.path.join(ROOT, 'data', 'XAUUSD_H1.csv')
DATA_M15 = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
PIP = 0.10


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek
    df['dom'] = df['dt'].dt.day
    df['dim'] = df['dt'].dt.days_in_month
    df['ret_pip'] = (df['close'] - df['open']) / PIP  # بازدهِ هر کندل بر حسب pip
    return df.reset_index(drop=True)


def atr_median(df, n=14):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = pd.Series(tr).rolling(n).mean().values / PIP
    rng = (h - l) / PIP
    return np.nanmedian(rng), np.nanmedian(atr)


def hour_drift(df):
    """میانگین و t-stat بازدهِ هر کندل بر حسبِ ساعتِ باز-شدنِ کندل (UTC)."""
    out = []
    for hr in sorted(df['hour'].unique()):
        x = df.loc[df['hour'] == hr, 'ret_pip'].values
        if len(x) < 30:
            continue
        m = x.mean(); s = x.std(ddof=1)
        t = m / (s / np.sqrt(len(x))) if s > 0 else 0.0
        out.append((int(hr), float(m), float(t), int(len(x))))
    return sorted(out, key=lambda r: -r[2])


def dow_drift(df):
    names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    out = []
    for d in sorted(df['dow'].unique()):
        x = df.loc[df['dow'] == d, 'ret_pip'].values
        if len(x) < 30:
            continue
        m = x.mean(); s = x.std(ddof=1)
        t = m / (s / np.sqrt(len(x))) if s > 0 else 0.0
        out.append((names[d], float(m), float(t), int(len(x))))
    return sorted(out, key=lambda r: -r[2])


def dom_bucket_drift(df):
    """drift روزِ تقویمیِ ماه در سه خوشه: ابتدا/میانه/انتها."""
    buckets = {
        'TurnOfMonth(dom1-3)': df['dom'].isin([1, 2, 3]),
        'MidMonth(dom10-14)': df['dom'].isin([10, 11, 12, 13, 14]),
        'MidMonth20(dom18-22)': df['dom'].isin([18, 19, 20, 21, 22]),
        'EndOfMonth(rel-6..-3)': (df['dom'] >= (df['dim'] - 6)) & (df['dom'] <= (df['dim'] - 3)),
    }
    out = []
    for name, mask in buckets.items():
        x = df.loc[mask.values, 'ret_pip'].values
        if len(x) < 30:
            continue
        m = x.mean(); s = x.std(ddof=1)
        t = m / (s / np.sqrt(len(x))) if s > 0 else 0.0
        out.append((name, float(m), float(t), int(len(x))))
    return sorted(out, key=lambda r: -r[2])


def autocorr(df, lag=1):
    x = df['ret_pip'].values
    x = x[~np.isnan(x)]
    if len(x) < lag + 5:
        return 0.0
    return float(np.corrcoef(x[:-lag], x[lag:])[0, 1])


def main():
    print("=" * 92)
    print("s207 — تحلیلِ اکتشافیِ XAUUSD H4 «بگذار داده حرف بزند» (پاسخِ User Note: TF=H4)")
    print("=" * 92, flush=True)

    df = load(DATA_H4)
    print(f"\n[۱] پوششِ داده: {len(df):,} کندلِ H4  "
          f"({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})")
    print(f"    بازهٔ قیمت: {df['low'].min():,.0f} – {df['high'].max():,.0f} $")
    # ساعاتِ باز-شدنِ کندلِ H4 (معمولاً 0,4,8,12,16,20 UTC)
    print(f"    ساعاتِ باز-شدنِ کندلِ H4 (UTC): {sorted(df['hour'].unique().tolist())}")

    print("\n[۲] مقایسهٔ ATR (برای بازتنظیمِ TP/SL و max_hold):")
    for name, path in [('H4', DATA_H4), ('H1', DATA_H1), ('M15', DATA_M15)]:
        d = load(path)
        rng, atr = atr_median(d)
        print(f"    {name:4s}: میانهٔ range={rng:6.1f} pip   میانهٔ ATR14={atr:6.1f} pip   (n={len(d):,})")
    rng4, atr4 = atr_median(df)
    _, atr1 = atr_median(load(DATA_H1))
    print(f"    ⇒ نسبتِ ATR(H4/H1) ≈ {atr4/atr1:.2f}×  ⇒ TP/SL روی H4 باید بزرگ‌تر باشد،")
    print(f"      و max_hold(H4) ≈ max_hold(H1)/4 (هر H4 = 4×H1 = 16×M15).")

    print("\n[۳] ⭐ Drift ساعتی (میانگینِ بازدهِ کندلِ H4 بر ساعتِ باز-شدن، UTC):")
    print(f"    {'hour':>5}{'mean(pip)':>12}{'t-stat':>9}{'n':>8}")
    for hr, m, t, n in hour_drift(df):
        star = ' ⭐' if abs(t) >= 2.0 else ''
        print(f"    {hr:>5}{m:>+12.2f}{t:>+9.2f}{n:>8}{star}")

    print("\n[۴] Drift روزِ هفته:")
    print(f"    {'dow':>5}{'mean(pip)':>12}{'t-stat':>9}{'n':>8}")
    for d, m, t, n in dow_drift(df):
        star = ' ⭐' if abs(t) >= 2.0 else ''
        print(f"    {d:>5}{m:>+12.2f}{t:>+9.2f}{n:>8}{star}")

    print("\n[۵] Drift روزِ تقویمیِ ماه (خوشه‌ای):")
    print(f"    {'bucket':>24}{'mean(pip)':>12}{'t-stat':>9}{'n':>8}")
    for name, m, t, n in dom_bucket_drift(df):
        star = ' ⭐' if abs(t) >= 2.0 else ''
        print(f"    {name:>24}{m:>+12.2f}{t:>+9.2f}{n:>8}{star}")

    ac1 = autocorr(df, 1)
    ac2 = autocorr(df, 2)
    mean_all = float(df['ret_pip'].mean())
    print("\n[۶] بایاسِ کلی و ساختار:")
    print(f"    میانگینِ بازدهِ هر کندلِ H4 = {mean_all:+.3f} pip  (بایاسِ صعودیِ ساختاریِ طلا)")
    print(f"    اتوکورلیشن lag-1 = {ac1:+.3f}   lag-2 = {ac2:+.3f}")
    print(f"    ⇒ {'مومنتوم/روند-ادامه شانس دارد' if ac1 > 0.03 else 'اتوکورلیشن خنثی ⇒ زمان-محور/ساختاری شانسِ بیشتری دارد'}")

    out = dict(
        data='XAUUSD_H4', n_candles=len(df),
        date_range=[str(df['dt'].iloc[0].date()), str(df['dt'].iloc[-1].date())],
        h4_open_hours=sorted(df['hour'].unique().tolist()),
        atr_h4=atr4, atr_h1=atr1, ratio_h4_h1=atr4 / atr1,
        hour_drift=hour_drift(df), dow_drift=dow_drift(df),
        dom_bucket=dom_bucket_drift(df),
        autocorr_lag1=ac1, autocorr_lag2=ac2, mean_ret_pip=mean_all,
    )
    with open(os.path.join(RESULTS, '_s207_h4_explore.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s207_h4_explore.json")


if __name__ == '__main__':
    main()
