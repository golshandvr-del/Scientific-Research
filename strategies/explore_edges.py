"""
تحلیل اکتشافی عمیق برای یافتن edge شرطی واقعی در XAUUSD M15.
هدف: پیدا کردن شرایطی که در آن احتمال حرکت جهت‌دار به‌طور معنادار از baseline بیشتر است.
تمرکز روی مفاهیمی که قبلاً بررسی نشده: liquidity sweep، gap، الگوی سشن دقیق‌تر.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data()
c = df['close'].values; o = df['open'].values
h = df['high'].values; l = df['low'].values
n = len(df)
df['hour'] = df['dt'].dt.hour
df['dow'] = df['dt'].dt.dayofweek

# بازده آینده (forward return) در افق‌های مختلف بر حسب دلار و درصد
ret_fwd = {}
for hz in [4, 8, 16, 24]:
    fut = np.full(n, np.nan)
    fut[:-hz] = c[hz:] - c[:-hz]
    ret_fwd[hz] = fut

print("="*70)
print("baseline: میانگین بازده آینده (دلار) و احتمال صعود")
for hz in [4, 8, 16, 24]:
    r = ret_fwd[hz]
    valid = ~np.isnan(r)
    print(f"  hz={hz:2d}: mean={np.nanmean(r):+.4f}$  P(up)={np.mean(r[valid]>0)*100:.2f}%")

# ============ 1) اثر ساعتی دقیق ============
print("\n" + "="*70)
print("اثر ساعتی: میانگین بازده ۱۶ کندل آینده به تفکیک ساعت UTC")
r16 = ret_fwd[16]
for hr in range(24):
    m = (df['hour'].values == hr) & ~np.isnan(r16)
    if m.sum() > 100:
        rr = r16[m]
        print(f"  ساعت {hr:2d}: mean={rr.mean():+.4f}$  P(up)={np.mean(rr>0)*100:.1f}%  n={m.sum()}")

# ============ 2) Liquidity Sweep: شکست کف/سقف N کندل قبل و برگشت ============
print("\n" + "="*70)
print("Liquidity Sweep (شکار استاپ): قیمت کف/سقف اخیر را می‌شکند سپس برمی‌گردد")
LB = 20  # lookback
for direction in ['bull_sweep', 'bear_sweep']:
    # bull_sweep: low قیمت زیر min(low[-LB:]) رفته ولی close بالای آن بسته شده -> برگشت صعودی محتمل
    prior_low = pd.Series(l).rolling(LB).min().shift(1).values
    prior_high = pd.Series(h).rolling(LB).max().shift(1).values
    if direction == 'bull_sweep':
        sig = (l < prior_low) & (c > prior_low)
        r = ret_fwd[16]
    else:
        sig = (h > prior_high) & (c < prior_high)
        r = -ret_fwd[16]  # برای short، بازده معکوس
    m = sig & ~np.isnan(r)
    if m.sum() > 50:
        rr = r[m]
        print(f"  {direction}: n={m.sum()}  mean_fav_ret={rr.mean():+.4f}$  P(favorable)={np.mean(rr>0)*100:.1f}%")

# ============ 3) رژیم روند (ADX) × جهت DI ============
print("\n" + "="*70)
print("رژیم روند: ADX بالا + جهت DI -> ادامه روند؟")
adx, pdi, mdi = ind.adx(df, 14)
adx = adx.values; pdi = pdi.values; mdi = mdi.values
r16 = ret_fwd[16]
for adx_th in [20, 25, 30]:
    # روند صعودی قوی
    m_up = (adx > adx_th) & (pdi > mdi) & ~np.isnan(r16)
    m_dn = (adx > adx_th) & (mdi > pdi) & ~np.isnan(r16)
    print(f"  ADX>{adx_th} & +DI>-DI (روند صعودی): n={m_up.sum()} mean={np.nanmean(r16[m_up]):+.4f}$ P(up)={np.mean(r16[m_up]>0)*100:.1f}%")
    print(f"  ADX>{adx_th} & -DI>+DI (روند نزولی): n={m_dn.sum()} mean={np.nanmean(r16[m_dn]):+.4f}$ P(dn)={np.mean(r16[m_dn]<0)*100:.1f}%")

# ============ 4) شکست باند + مومنتوم (breakout continuation) ============
print("\n" + "="*70)
print("Breakout: close بالای سقف N کندل با مومنتوم -> ادامه؟")
for LB in [20, 50]:
    prior_high = pd.Series(h).rolling(LB).max().shift(1).values
    prior_low = pd.Series(l).rolling(LB).min().shift(1).values
    r8 = ret_fwd[8]
    m_bo_up = (c > prior_high) & ~np.isnan(r8)
    m_bo_dn = (c < prior_low) & ~np.isnan(r8)
    print(f"  LB={LB} breakout بالا: n={m_bo_up.sum()} mean={np.nanmean(r8[m_bo_up]):+.4f}$ P(up)={np.mean(r8[m_bo_up]>0)*100:.1f}%")
    print(f"  LB={LB} breakdown پایین: n={m_bo_dn.sum()} mean={np.nanmean(r8[m_bo_dn]):+.4f}$ P(dn)={np.mean(r8[m_bo_dn]<0)*100:.1f}%")
