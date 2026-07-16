"""
S53b — تحلیلِ عمیقِ تفاوتِ دو نیمهٔ بازار (چرا نیمهٔ اول edge روندی ندارد؟)
================================================================================
S53 نشان داد رژیمِ رنج در هر دو نیمه یکسان (~۱۶٪) است و MR خام edge ندارد. پس چرا
جریان‌های روندی در نیمهٔ اول فقط بریک‌ایون‌اند؟ این اسکریپت ویژگی‌های خامِ آماریِ
دو نیمه را مقایسه می‌کند تا ماهیتِ واقعیِ تفاوت را بفهمیم — پایهٔ تصمیمِ بعدی.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data(); n = len(df); c = df['close'].values
atr = ind.atr(df, 14).values
ema200 = ind.ema(df['close'], 200).values
adx_, pdi, mdi = ind.adx(df, 14); adxv = adx_.values
ret = pd.Series(c).pct_change().values
mid = n // 2

print(f"بازهٔ کل: {df['dt'].iloc[0]} → {df['dt'].iloc[-1]}")
print(f"نقطهٔ میانی (mid): {df['dt'].iloc[mid]}\n")


def desc(name, s, e):
    seg_c = c[s:e]; seg_ret = ret[s:e]; seg_atr = atr[s:e]; seg_adx = adxv[s:e]
    # روندِ خالص: نسبتِ تغییرِ کل به مجموعِ حرکت (efficiency ratio)
    net = abs(seg_c[-1] - seg_c[0])
    path = np.nansum(np.abs(np.diff(seg_c)))
    eff = net / path if path > 0 else 0
    # درصدِ زمان بالای EMA200 (سوگیریِ جهت)
    above = np.nanmean(c[s:e] > ema200[s:e]) * 100
    ann_vol = np.nanstd(seg_ret) * np.sqrt(96 * 252) * 100
    print(f"{name}:")
    print(f"  قیمت: {seg_c[0]:.0f} → {seg_c[-1]:.0f}  (تغییرِ خالص {100*(seg_c[-1]/seg_c[0]-1):+.1f}%)")
    print(f"  efficiency ratio (روندی‌بودنِ کل): {eff:.4f}")
    print(f"  زمان بالای EMA200: {above:.1f}%")
    print(f"  ADX میانگین: {np.nanmean(seg_adx):.1f}")
    print(f"  نوسانِ سالانه: {ann_vol:.1f}%")
    print(f"  میانگین |بازده روزانه|: {100*np.nanmean(np.abs(seg_ret)):.4f}%\n")


desc("نیمهٔ اول (~۲۰۲۰–۲۰۲۳)", 0, mid)
desc("نیمهٔ دوم (~۲۰۲۳–۲۰۲۶)", mid, n)

# تفکیکِ سالانه برای دیدِ ریزتر
print("=== efficiency ratio و روند به تفکیکِ سال ===")
df['year'] = df['dt'].dt.year
for yr, g in df.groupby('year'):
    ci = g['close'].values
    if len(ci) < 100: continue
    net = abs(ci[-1] - ci[0]); path = np.nansum(np.abs(np.diff(ci)))
    eff = net / path if path > 0 else 0
    print(f"  {yr}: {ci[0]:.0f}→{ci[-1]:.0f} ({100*(ci[-1]/ci[0]-1):+.1f}%)  eff={eff:.4f}")

print("\nتمام.")
