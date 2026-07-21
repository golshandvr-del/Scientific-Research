"""
explore_gold_midmonth_days.py — کالبدشکافیِ «روزهای قویِ میانهٔ ماه» (dom 10/13/20)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» = XAUUSD + EURUSD — نه Win-Rate.

منشأ: اسکنِ ابعادِ تقویمی (explore_gold_calendar_dimensions.py) نشان داد قوی‌ترین
  t-statهای کلِ پروژه در روزهای *میانهٔ ماه* هستند — نه ابتدای ماه (که S141 گرفت):
    dom=20 → t=+10.99, mean=+31.32pip, both ✓ (قوی‌ترین کلِ پروژه!)
    dom=10 → t=+9.31,  mean=+19.82pip, both ✓
    dom=13 → t=+7.49,  mean=+16.20pip, both ✓
  این یک بُعدِ تقویمیِ *متفاوت* از S141 (dom=1 = ابتدای ماه) است ⇒ کاندیدِ ناهمبسته.

این اسکریپت (پیش از ساختِ استراتژی):
  ۱) ساعاتِ قویِ هر روز را می‌یابد (برای طراحیِ پنجرهٔ ورود).
  ۲) بررسی می‌کند آیا این روزها با پنجرهٔ ساعتیِ S141 (۷–۱۲) هم‌پوشانیِ ساعتی دارند.
  ۳) خوشهٔ {10,13,20} را در برابرِ بقیهٔ ماه به‌عنوان یک ماشهٔ واحد می‌سنجد.
  ۴) پایداریِ چارک‌به‌چارک (۴ پنجره) را برای اطمینان از عدمِ آرتیفکت می‌سنجد.
================================================================================
"""
import os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
HORIZON = 24


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['dt'] = dt
    df['hour'] = dt.dt.hour
    df['dom'] = dt.dt.day
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def fwd_ret_pip(df, horizon):
    c = df['close'].values; n = len(c)
    fr = np.full(n, np.nan)
    fr[:n - horizon] = (c[horizon:] - c[:n - horizon]) / 0.10
    return fr


def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 30 or x.std() == 0:
        return 0.0, 0.0, len(x)
    return float(x.mean() / (x.std() / np.sqrt(len(x)))), float(x.mean()), len(x)


def main():
    df = load()
    df['fr'] = fwd_ret_pip(df, HORIZON)
    n = len(df)

    print(f"داده: {n} کندلِ M15 XAUUSD | افق={HORIZON} کندل\n")

    # --- ۱) ساعاتِ قویِ هر روزِ کاندید ---
    print(f"{'='*78}\n۱) ساعاتِ قویِ هر روزِ کاندید (t>2.5, N>20)\n{'='*78}")
    for d in [10, 13, 20]:
        sub = df[df['dom'] == d]
        strong = []
        for h in range(24):
            hh = sub[sub['hour'] == h]['fr'].values
            t, m, cnt = tstat(hh)
            if t > 2.5 and cnt > 20:
                strong.append((h, round(t, 1), round(m, 1)))
        print(f"  dom={d}: ساعاتِ قوی = {strong}")

    # --- ۲) خوشهٔ {10,13,20} به‌عنوان یک ماشهٔ واحد در برابرِ بقیهٔ ماه ---
    print(f"\n{'='*78}\n۲) خوشهٔ میانهٔ ماه {{10,13,20}} در برابرِ بقیهٔ ماه\n{'='*78}")
    half = n // 2
    cluster = df['dom'].isin([10, 13, 20])
    for label, mask in [('cluster{10,13,20}', cluster), ('rest', ~cluster)]:
        t, m, cnt = tstat(df[mask]['fr'].values)
        h1 = df[mask & (df.index < half)]['fr'].values
        h2 = df[mask & (df.index >= half)]['fr'].values
        _, m1, _ = tstat(h1); _, m2, _ = tstat(h2)
        print(f"  {label:>18}: t={t:+.2f}  mean={m:+.2f}pip  N={cnt}  h1={m1:+.2f} h2={m2:+.2f}  both={'✓' if m1>0 and m2>0 else '✗'}")

    # --- ۳) پایداریِ چارک‌به‌چارک (۴ پنجره) برای خوشه ---
    print(f"\n{'='*78}\n۳) پایداریِ ۴-چارکیِ خوشهٔ {{10,13,20}} (ضدِ آرتیفکت)\n{'='*78}")
    edges = np.linspace(0, n, 5, dtype=int)
    for k in range(4):
        seg = df.iloc[edges[k]:edges[k+1]]
        sub = seg[seg['dom'].isin([10, 13, 20])]
        t, m, cnt = tstat(sub['fr'].values)
        print(f"  چارکِ {k+1}: t={t:+.2f}  mean={m:+.2f}pip  N={cnt}")

    # --- ۴) هر روز به‌تنهایی، ۴-چارکی (کدام واقعاً پایدار است؟) ---
    print(f"\n{'='*78}\n۴) پایداریِ ۴-چارکیِ هر روز به‌تنهایی\n{'='*78}")
    for d in [10, 13, 20]:
        row = []
        for k in range(4):
            seg = df.iloc[edges[k]:edges[k+1]]
            sub = seg[seg['dom'] == d]
            t, m, cnt = tstat(sub['fr'].values)
            row.append(round(m, 1))
        allpos = all(x > 0 for x in row)
        print(f"  dom={d}: چارک‌ها(mean_pip)={row}  {'✅ هر ۴ مثبت' if allpos else '⚠️'}")


if __name__ == '__main__':
    main()
