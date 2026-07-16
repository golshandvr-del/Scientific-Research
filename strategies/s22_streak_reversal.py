"""
استراتژی ۲۲: Streak-Reversal (بازگشت پس از کندل‌های متوالی هم‌جهت)
================================================================================
مسیری متمایز از ۲۱ استراتژی قبلی: بهره‌برداری مستقیم از **serial dependence**
(هم‌بستگی خودکار جهت) که در کاوش داده کشف شد.

  کشف کاوشی (روی ۱۵۰k کندل):
  ---------------------------
  - جهت کندلِ بعدی پس از یک کندل قوی، تمایل خفیف به «برگشت» دارد (P(ادامه)≈۴۴–۴۹٪).
  - پس از N کندل نزولی متوالی، احتمال برگشت صعودی کندل بعد ≈ ۵۳–۵۴٪ (بالای ۵۰٪).
    → یک سوگیری برگشتی (mean-reversion) خام اما جهت‌دار و واقعی (نه تله‌ی RR).

  منطق استراتژی:
  --------------
  - سیگنال: پس از N کندل *نزولی* متوالی (close<open)، ورود LONG (شرط بر برگشت صعودی).
  - فیلترها: RSI اشباع فروش (RSI<35 یا <30) و/یا روند بلندمدت (close>EMA200).
  - TP/SL: ضریبی از ATR (خودتطبیق با نوسان).

  تمایز از استراتژی‌های قبلی:
  ---------------------------
  هیچ استراتژی قبلی مستقیماً از «طول رگه‌ی (streak) کندل‌های متوالی هم‌جهت» به‌عنوان
  تریگر استفاده نکرده بود. (s01 mean-reversion با BB/RSI بود، نه streak؛ s13 range-BB
  بود.) این یک الگوی شمارشی/ترتیبی خالص است.

ارزیابی با موتور مشترک engine/backtest.py (بدون look-ahead، اسپرد ۰.۲۰$).
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.backtest import load_data, run_backtest
from engine.indicators import atr as atr_ind, rsi, ema


def build_signal(df, N, filt):
    d = np.sign(df['close'].values - df['open'].values)
    c = df['close'].values
    n = len(df)
    r = rsi(df['close'], 14).values
    e200 = ema(df['close'], 200).values

    run_dn = np.zeros(n, bool)
    for i in range(N, n):
        if np.all(d[i - N + 1:i + 1] == -1):
            run_dn[i] = True

    if filt == 'none':
        extra = np.ones(n, bool)
    elif filt == 'rsi<35':
        extra = r < 35
    elif filt == 'rsi<30':
        extra = r < 30
    elif filt == 'above_ema200':
        extra = c > e200
    else:
        extra = np.ones(n, bool)
    return run_dn & extra


def main():
    df = load_data()
    a = atr_ind(df, 14).values
    nd = df['dt'].dt.date.nunique()
    print(f"داده: {len(df)} کندل، {nd} روز")
    print(f"{'N':>3}{'filt':>16}{'TP':>5}{'SL':>5}{'n':>6}{'WR':>8}{'exp':>9}{'tpd':>7}")
    print("=" * 62)

    rows = []
    for N in [4, 5, 6]:
        for filt in ['none', 'rsi<35', 'rsi<30', 'above_ema200']:
            sig = build_signal(df, N, filt)
            if sig.sum() < 50:
                continue
            for tp, sl in [(1.0, 1.0), (1.0, 1.5), (0.75, 1.0), (1.5, 1.5)]:
                stats, tr = run_backtest(df, sig, None, None, 'long', spread=0.20,
                                         max_hold=48, sl_series=sl * a, tp_series=tp * a)
                if stats['n_trades'] < 50:
                    continue
                tpd = stats['n_trades'] / nd
                rows.append((N, filt, tp, sl, stats['n_trades'],
                             stats['win_rate'], stats['expectancy'], tpd))

    for r in sorted(rows, key=lambda x: -x[5]):
        print(f"{r[0]:>3}{r[1]:>16}{r[2]:>5}{r[3]:>5}{r[4]:>6}{r[5]:>8.2f}{r[6]:>9.3f}{r[7]:>7.2f}")

    print("\n" + "=" * 62)
    good = [r for r in rows if r[5] > 60 and r[6] > 0 and r[7] >= 3]
    print("نقاط با WR>60 + exp>0 + tpd>=3:", good if good else "هیچ‌کدام")


if __name__ == '__main__':
    main()
