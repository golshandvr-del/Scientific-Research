"""
explore_eurusd_short_mfe.py — تحلیلِ MFE/MAE ساعت‌های Short برای فهمِ «آیا اصلاً قابلِ معامله است؟»
================================================================================
جاروی طراحی نشان داد drift نزولیِ ساعت ۲۲/۱۳ (~0.6pip) با هزینهٔ 2.1pip ruin می‌شود.
اینجا MFE (بیشترین حرکتِ مطلوب) و MAE (بیشترین حرکتِ نامطلوب) را می‌سنجیم تا ببینیم
آیا با TP کوچک/SL بزرگ لبه‌ای قابلِ استخراج هست یا این ساعت‌ها اساساً برای معامله بی‌فایده‌اند.
همچنین «آیا drift کافی برای پوششِ هزینه هست؟» را کمّی می‌کنیم.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

df = pd.read_csv('data/EURUSD_M15.csv')
df['dt'] = pd.to_datetime(df['time'], unit='s')
df['hour'] = df['dt'].dt.hour
o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
n = len(df); PIP = 0.0001
hour = df['hour'].values
COST = 1.5 + 2 * 0.3  # اسپرد + اسلیپیجِ دو طرف = 2.1 pip

print("=" * 100)
print("  تحلیلِ MFE/MAE ساعت‌های Short کاندید EURUSD (هزینهٔ رفت‌وبرگشت = 2.1pip)")
print("=" * 100)

def analyze_short(hr, hold):
    """برای Short: MFE = چقدر پایین رفت (سود)، MAE = چقدر بالا رفت (ضرر)."""
    sig = np.where(hour == hr)[0]
    mfe, mae, netclose = [], [], []
    for i in sig:
        eb = i + 1
        if eb + hold >= n: continue
        entry = o[eb]
        window_l = l[eb:eb + hold]; window_h = h[eb:eb + hold]
        favor = (entry - window_l.min()) / PIP   # سودِ Short = افت
        adverse = (window_h.max() - entry) / PIP  # ضررِ Short = صعود
        nc = (entry - c[eb + hold - 1]) / PIP
        mfe.append(favor); mae.append(adverse); netclose.append(nc)
    return np.array(mfe), np.array(mae), np.array(netclose)

for hr in [22, 13, 12]:
    print(f"\n--- ساعتِ {hr} UTC ---")
    for hold in [4, 6, 8]:
        mfe, mae, nc = analyze_short(hr, hold)
        # سودِ خالصِ نگهداری تا close منهای هزینه:
        net_after_cost = nc.mean() - COST
        print(f"  hold={hold:2d}: MFE_med={np.median(mfe):5.2f}  MAE_med={np.median(mae):5.2f}  "
              f"close_drift={nc.mean():+5.2f}pip  net_after_cost={net_after_cost:+5.2f}pip  "
              f"{'✅ مثبت' if net_after_cost > 0 else '❌ منفی'}")
    # چند درصد از معاملات MFE > هزینه دارند؟ (سقفِ نظریِ TP-scalp)
    mfe6, _, _ = analyze_short(hr, 6)
    for tp in [2, 3, 4, 5]:
        pct = (mfe6 >= tp + COST).mean() * 100
        print(f"    اگر TP={tp}pip: {pct:.0f}% از معاملات به TP می‌رسند (نیازمندِ MFE≥{tp+COST:.1f})")
