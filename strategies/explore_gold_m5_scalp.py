"""
explore_gold_m5_scalp.py — اکتشافِ لبه‌های اسکالپ روی XAUUSD M5 با موتورِ نو (User Note 2)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً گزارشی.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

انگیزه (User Note 2): «موتور محاسباتیِ نو برای اسکالپینگ روی M5/M1 بسازیم و اول
روی طلا نتیجه بگیریم، بعد یورو.» موتورِ نو (scalp_engine) ساخته و اعتبارسنجی شد
(S78). این اسکریپت اولین اکتشافِ سیستماتیکِ لبه روی دادهٔ M5 طلاست.

روش (کاملاً forward-safe، بدونِ look-ahead):
  • دادهٔ M5 طلا (۲۰۰k کندل، بازهٔ ۲۰۲۳-۰۹ تا ۲۰۲۶-۰۷ — اخیر/روندی).
  • فرضیه: در M5 بازده خام تقریباً random-walk است (autocorr≈۰)، اما مثل EURUSD
    ممکن است drift ساعتیِ ساختاری وجود داشته باشد (اکتشافِ اولیه: h=01,03,23 صعودی).
  • برای هر ساعتِ UTC، یک لبهٔ ساده تست می‌کنیم:
      - Long-at-hour: در آن ساعت وارد شو (drift-following).
      - Short-at-hour: برعکس.
  • تقسیمِ IS (نیمهٔ اول) / OOS (نیمهٔ دوم) → فقط لبه‌هایی که در هر دو مثبت‌اند.
  • همه چیز با scalp_engine (pip-native, اسپرد+کمیسیون+اسلیپیج) سنجیده می‌شود.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

# مشخصاتِ M5 طلا = همان طلا (pip=0.10$, contract=100). اسپردِ اسکالپِ M5 کمی بیشتر
# در نظر می‌گیریم (واقع‌گرایی: اسکالپِ سریع اسپردِ مؤثرِ بالاتری می‌خورد).
SE.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=2.0, comm=7.0, slip_pip=0.5)

ASSET = 'XAUUSD_M5'
SL_PIP = 30.0   # 3.0$  (≈ میانگین رنجِ ~۱ کندلِ M5 است؛ برای اسکالپ متعارف)
TP_PIP = 30.0
MAX_HOLD = 12   # ۶۰ دقیقه


def main():
    df = SE.load_data(SE.ASSETS[ASSET]['file'])
    df['h'] = df['dt'].dt.hour
    n = len(df)
    half = n // 2
    print("=" * 92)
    print("  اکتشافِ لبه‌های اسکالپ روی XAUUSD M5 — موتورِ نو (IS نیمهٔ اول / OOS نیمهٔ دوم)")
    print(f"  کندل‌ها={n}  SL=TP={SL_PIP}pip  max_hold={MAX_HOLD}  اسپرد={SE.ASSETS[ASSET]['spread_pip']}pip")
    print("=" * 92)

    hours = np.arange(24)
    rows = []
    for h in hours:
        at_h = (df['h'].values == h)
        for direction in ('long', 'short'):
            long_sig = at_h if direction == 'long' else np.zeros(n, bool)
            short_sig = at_h if direction == 'short' else np.zeros(n, bool)

            # IS
            tr = SE.simulate_trades(df, long_sig, short_sig, SL_PIP, TP_PIP, ASSET, max_hold=MAX_HOLD)
            if len(tr) == 0:
                continue
            tr_is = tr[tr['entry_bar'] < half]
            tr_oos = tr[tr['entry_bar'] >= half]
            if len(tr_is) < 100 or len(tr_oos) < 100:
                continue
            s_is, _ = SE.run_capital(tr_is, ASSET)
            s_oos, _ = SE.run_capital(tr_oos, ASSET)
            rows.append((h, direction, s_is['net_profit'], s_oos['net_profit'],
                         s_oos['win_rate'], s_is['n_trades'], s_oos['n_trades'],
                         s_oos['profit_factor']))

    # لبه‌هایی که هر دو نیمه مثبت‌اند
    winners = [r for r in rows if r[2] > 0 and r[3] > 0]
    winners.sort(key=lambda r: r[2] + r[3], reverse=True)
    print("\n  === لبه‌های دو-نیمه-مثبت (پایدار) ===")
    if not winners:
        print("   هیچ لبهٔ دو-نیمه-مثبتی یافت نشد.")
    for h, d, is_p, oos_p, wr, nis, noos, pf in winners:
        print(f"   h={h:02d} {d:5s} | IS={is_p:+8.0f}$ (n={nis}) | "
              f"OOS={oos_p:+8.0f}$ (n={noos}, WR={wr:.0f}%, PF={pf:.2f}) | جمع={is_p+oos_p:+8.0f}$")

    print("\n  === همهٔ ساعت‌ها (مرتب بر جمعِ IS+OOS) ===")
    rows.sort(key=lambda r: r[2] + r[3], reverse=True)
    for h, d, is_p, oos_p, wr, nis, noos, pf in rows[:12]:
        flag = "✅" if (is_p > 0 and oos_p > 0) else "  "
        print(f"  {flag} h={h:02d} {d:5s} | IS={is_p:+8.0f}$ | OOS={oos_p:+8.0f}$ | جمع={is_p+oos_p:+8.0f}$")
    print("=" * 92)


if __name__ == '__main__':
    main()
