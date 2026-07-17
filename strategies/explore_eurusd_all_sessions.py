"""
explore_eurusd_all_sessions.py — اکتشافِ عمیقِ ساختارِ سشنیِ EURUSD روی همهٔ ساعت‌ها
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است — نه WR.
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

انگیزه:
  S73 فقط ساعتِ ۰ UTC (باز شدنِ اروپا) را به‌عنوانِ drift صعودی استخراج کرد.
  اما DNA اولیه (فایلِ S73) نشان داد ساعت‌های دیگر هم t-stat بالا دارند (نزولی):
  ساعت ۲۲ (t=-5.98)، ۱۳ (-4.61)، ۲۳ (-3.77)، ۱۸ (-3.66)، ۶ (-3.60).
  فرضیه: EURUSD یک «ساختارِ چند-سشنیِ» غنی دارد؛ S73 فقط یک تکه‌اش را برداشت.
  اگر ساعت‌های نزولیِ پایدار (Short) یا صعودیِ دیگر (Long) هم لبهٔ سودده بدهند،
  می‌توان یک لایهٔ مستقلِ جدید (S80) به پرتفوی افزود — دقیقاً روشِ S79.

این اسکریپت فقط «کشفِ ساختار» است (بدونِ ادعای سود). هر ساعت را:
  • میانگین/انحراف/t-stat حرکتِ h کندلِ آینده (h=1,4,6)
  • پایداری در ۴ چارَکِ زمانی (out-of-sample)
می‌سنجد تا کاندیدهای پایدار را برای طراحیِ استراتژی پیدا کند.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

df = pd.read_csv('data/EURUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s')
df['hour'] = df['dt'].dt.hour
df['dow'] = df['dt'].dt.dayofweek
c = df['close'].values
o = df['open'].values
n = len(df)
PIP = 0.0001

print("=" * 100)
print(f"  EURUSD M15 — اکتشافِ ساختارِ سشنی روی همهٔ ساعت‌ها  (n={n})")
print("=" * 100)

# forward return بر حسبِ pip برای افق‌های مختلف (از open کندلِ بعد از سیگنال تا h کندل بعد)
def fwd_ret_pip(h):
    # ورود در open[i+1]، خروج در close[i+h]
    r = np.full(n, np.nan)
    for i in range(n - h - 1):
        r[i] = (c[i + h] - o[i + 1]) / PIP
    return r

for h in [4, 6, 8]:
    print(f"\n--- افقِ نگهداری h={h} کندل (~{h*15}min) — میانگینِ forward-return به pip، به تفکیکِ ساعتِ UTC ---")
    r = fwd_ret_pip(h)
    rows = []
    for hr in range(24):
        mask = (df['hour'].values == hr) & ~np.isnan(r)
        vals = r[mask]
        if len(vals) < 50:
            continue
        mean = vals.mean()
        t = mean / (vals.std() / np.sqrt(len(vals))) if vals.std() > 0 else 0
        rows.append((hr, len(vals), mean, t))
    rows.sort(key=lambda x: -abs(x[3]))
    print(f"  {'ساعت':>4} {'n':>6} {'میانگین(pip)':>13} {'t-stat':>8}")
    for hr, cnt, mean, t in rows[:12]:
        flag = '  ⭐' if abs(t) > 4 else ('  •' if abs(t) > 2.5 else '')
        print(f"  {hr:>4} {cnt:>6} {mean:>13.3f} {t:>8.2f}{flag}")
