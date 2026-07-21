"""
explore_gold_dow_hour.py — اکتشافِ بُعدِ «روزِ هفته × ساعت» روی طلا M15
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (User Note این نشست: «نبوغ‌آمیز فکر کن!»):
  رکوردِ قبلی (Overnight Drift, S139) با کشفِ یک بُعدِ اطلاعاتیِ *متعامد* — «ساعتِ روز» —
  به دست آمد، نه یک ماشهٔ قیمتیِ نو. درسِ پارادایمی: «لبهٔ ناهمبسته لزوماً ماشهٔ قیمتی
  نیست؛ یک بُعدِ اطلاعاتیِ متفاوت می‌تواند از همهٔ لایه‌های قیمت مستقل باشد.»

  ایدهٔ نبوغ‌آمیزِ این نشست: بُعدِ Overnight فقط از *یک* محور (ساعت) استفاده کرد. اما
  ادبیاتِ آکادمیک یک بُعدِ **دوم و متعامد** می‌شناسد: «اثرِ روزِ هفته» (Cross 1973،
  French 1980؛ برای طلا: Ball–Torous–Tschoegl 1982). مهم‌تر: اثرِ *تعاملیِ* روز×ساعت
  (مثلاً «دوشنبهٔ صبحِ آسیا» یا «جمعهٔ پیش از بسته‌شدنِ هفته») یک ساختارِ زمانیِ کاملاً
  نو است که **هرگز آزموده نشده**.

هدفِ این اسکریپت (فقط کشف، بدونِ ادعا):
  ۱) میانگینِ بازدهِ آیندهٔ چند-کندلی را برای هر سلولِ (day_of_week, hour) بسنجد.
  ۲) t-stat هر سلول را حساب کند تا سلول‌های قوی و *پایدار* را بیابد.
  ۳) مهم: سلول‌هایی که با پنجرهٔ Overnight (ساعتِ ۲۲/۲۳) هم‌پوشانی *ندارند* را برجسته
     کند — تا کاندیدِ جریانِ غیرِهم‌بسته باشند.
  ۴) پایداریِ نیمه‌اول/نیمه‌دومِ داده را برای سلول‌های قوی چک کند (ضدِ overfit مقدماتی).
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
PIP = 0.1   # طلا: pip=0.1$ (طبقِ engine/scalp_engine ASSETS['XAUUSD'])

DOW_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s')
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek   # 0=Mon .. 6=Sun
    return df


def forward_return_pip(df, horizon):
    """بازدهِ آیندهٔ `horizon` کندل بر حسبِ pip (long): close[t+h]-close[t]، forward-safe."""
    c = df['close'].values.astype(np.float64)
    n = len(c)
    fr = np.full(n, np.nan)
    fr[:n-horizon] = (c[horizon:] - c[:n-horizon]) / PIP
    return fr


def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 30:
        return 0.0, len(x), 0.0
    m = x.mean()
    s = x.std(ddof=1)
    if s == 0:
        return 0.0, len(x), m
    return m / (s / np.sqrt(len(x))), len(x), m


def main():
    df = load()
    n = len(df)
    print(f"داده: {n} کندلِ M15 XAUUSD")
    print(f"بازه: {pd.to_datetime(df['time'].iloc[0],unit='s')} → {pd.to_datetime(df['time'].iloc[-1],unit='s')}")
    half = n // 2

    # افقِ هولد را مطابقِ Overnight (چند ساعت) می‌گیریم؛ 24 کندل = 6 ساعت
    for horizon in [8, 16, 24, 48]:
        fr = forward_return_pip(df, horizon)
        print(f"\n{'='*78}\nافقِ هولد = {horizon} کندل ({horizon*15} دقیقه)\n{'='*78}")
        print(f"{'DOW×Hour':<14}{'t-stat':>9}{'mean_pip':>10}{'N':>7}{'h1_mean':>9}{'h2_mean':>9}  note")

        cells = []
        for dow in range(7):
            for hour in range(24):
                mask = (df['dow'].values == dow) & (df['hour'].values == hour)
                x = fr[mask]
                t, cnt, m = tstat(x)
                if cnt < 50:
                    continue
                # پایداری نیمه‌ها
                idx = np.where(mask)[0]
                h1 = fr[idx[idx < half]]
                h2 = fr[idx[idx >= half]]
                _, _, m1 = tstat(h1)
                _, _, m2 = tstat(h2)
                cells.append((t, dow, hour, m, cnt, m1, m2))

        # مرتب بر اساسِ |t| نزولی، ۲۵ سلولِ قوی
        cells.sort(key=lambda r: -abs(r[0]))
        for t, dow, hour, m, cnt, m1, m2 in cells[:25]:
            overnight = "OVERLAP-Overnight" if hour in (22, 23) else ""
            stable = "✓both" if (np.sign(m1) == np.sign(m2) and abs(m1) > 0 and abs(m2) > 0) else ""
            tag = f"{overnight} {stable}".strip()
            print(f"{DOW_NAMES[dow]+' '+str(hour):<14}{t:>9.2f}{m:>10.2f}{cnt:>7}{m1:>9.2f}{m2:>9.2f}  {tag}")

    # --- خلاصهٔ محورِ روزِ هفته (تجمیعِ همه ساعات) ---
    print(f"\n{'='*78}\nخلاصه: اثرِ خالصِ روزِ هفته (افق=24، تجمیعِ همه ساعات)\n{'='*78}")
    fr = forward_return_pip(df, 24)
    for dow in range(7):
        mask = df['dow'].values == dow
        t, cnt, m = tstat(fr[mask])
        print(f"{DOW_NAMES[dow]:<6} t={t:>7.2f}  mean={m:>7.2f}pip  N={cnt}")


if __name__ == '__main__':
    main()
