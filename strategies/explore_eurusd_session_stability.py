"""
explore_eurusd_session_stability.py — آزمونِ پایداریِ out-of-sample ساعت‌های کاندید
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است. تعریف = XAUUSD + EURUSD.

ساعت‌های کاندید از explore_eurusd_all_sessions:
  Long : ۲۳ (drift صعودی، t تا +15)
  Short: ۲۲، ۱۳، ۱۲ (drift نزولی پایدار)
هدف: فقط ساعتی که در «هر ۴ چارَکِ زمانی» جهتش پایدار بماند ارزشِ ساخت دارد
(معیارِ ضدِ-overfit که S73 هم استفاده کرد).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

df = pd.read_csv('data/EURUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s')
df['hour'] = df['dt'].dt.hour
c = df['close'].values
o = df['open'].values
n = len(df)
PIP = 0.0001

def fwd_ret_pip(h):
    r = np.full(n, np.nan)
    for i in range(n - h - 1):
        r[i] = (c[i + h] - o[i + 1]) / PIP
    return r

quarters = [(0, 50000), (50000, 100000), (100000, 150000), (150000, 200000)]

print("=" * 100)
print("  آزمونِ پایداریِ چارَکیِ ساعت‌های کاندید EURUSD (h=6) — فقط پایدارها ارزش دارند")
print("=" * 100)

r6 = fwd_ret_pip(6)
cand = [0, 23, 22, 13, 12, 18, 17]
idx = np.arange(n)
for hr in cand:
    print(f"\n--- ساعتِ {hr} UTC ---")
    all_pos = True; all_neg = True
    for qi, (a, b) in enumerate(quarters):
        mask = (df['hour'].values == hr) & (idx >= a) & (idx < b) & ~np.isnan(r6)
        vals = r6[mask]
        if len(vals) < 20:
            print(f"    Q{qi+1}: کم‌نمونه"); continue
        mean = vals.mean()
        t = mean / (vals.std() / np.sqrt(len(vals))) if vals.std() > 0 else 0
        if mean <= 0: all_pos = False
        if mean >= 0: all_neg = False
        print(f"    Q{qi+1}: mean={mean:+.3f}pip  t={t:+.2f}  n={len(vals)}")
    verdict = "✅ پایدارِ صعودی (Long)" if all_pos else ("✅ پایدارِ نزولی (Short)" if all_neg else "❌ ناپایدار (جهت عوض می‌شود)")
    print(f"    → {verdict}")
