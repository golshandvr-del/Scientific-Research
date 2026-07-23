# -*- coding: utf-8 -*-
"""s212_diag_parity.py — تشخیصِ علامتِ asym: همان دادهٔ مصنوعیِ تستِ TS را به تابعِ
پایتون می‌دهد تا مطمئن شویم علامت/جهتِ asym در TS و پایتون یکی است، و بفهمیم rounding
واقعاً asym مثبت می‌دهد یا منفی (اصلاحِ docstring)."""
import numpy as np, pandas as pd, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import s212_brooks_inverse_view as M

N = 20
def series(pref):
    close = list(pref); high = [p + 0.3 for p in pref]; low = [p - 0.3 for p in pref]
    return pd.DataFrame({'close': close, 'high': high, 'low': low})

# سناریو ۱: اصلاحِ تندِ خطی
linear = []
for i in range(7): linear.append(100 + i * 1.0)
for i in range(1, 12): linear.append(106 - i * 1.0)
while len(linear) < N: linear.append(95)
d1 = series(linear[:N])
a1 = M.inverse_view_asym(d1, 12)
print("سناریو ۱ خطی: asym[last]=", a1[-1], " asym[N-1]=", a1[N-1] if len(a1) >= N else None)

# سناریو ۲: اصلاحِ محدب/rounding
convex = []
for i in range(7): convex.append(100 + i * 1.0)
convex += [104.8, 103.6, 102.4, 101.2, 100.0]        # نیمهٔ اول تند
convex += [99.9, 99.85, 99.82, 99.8, 99.8, 99.8]     # نیمهٔ دوم تخت (rounding)
while len(convex) < N: convex.append(99.8)
d2 = series(convex[:N])
a2 = M.inverse_view_asym(d2, 12)
print("سناریو ۲ محدب: asym[last]=", a2[-1])

# نمایشِ جزئیاتِ محاسبه برای سناریوی محدب (i=N-1، مثلِ TS)
i = N - 1
lb = 12
w_h = d2['high'].to_numpy()[i - lb:i]
w_l = d2['low'].to_numpy()[i - lb:i]
w_c = d2['close'].to_numpy()[i - lb:i]
pk = int(np.argmax(w_h)); seg_l = w_l[pk:]; tr = int(np.argmin(seg_l)) + pk
leg = w_c[pk:tr + 1]; m = len(leg); half = m // 2
s1 = np.polyfit(np.arange(half), leg[:half], 1)[0]
s2 = np.polyfit(np.arange(m - half), leg[half:], 1)[0]
print(f"  pk={pk} tr={tr} m={m} half={half} s1(نیمه۱)={s1:.4f} s2(نیمه۲)={s2:.4f} s1-s2={s1-s2:.4f}")
print("  نتیجه: rounding-bottom در این تعریف asym", "مثبت" if (s1 - s2) > 0 else "منفی", "می‌دهد.")
