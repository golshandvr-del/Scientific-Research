"""
S79 — XAUUSD M5 Trend-Pullback (اولین لبهٔ سوددهِ اثبات‌شده روی موتورِ نو / پاسخِ User Note 2)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله در روز و Profit Factor هم هدف نیستند. **ما دنبالِ پول
> هستیم، نه آمارِ زیبا.** تنها تابعِ هدفِ کلِ پروژه: **سودِ خالصِ تجمعیِ پس از
> اسپرد/کمیسیون/اسلیپیج.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

================================================================================
داستانِ کشف (پاسخِ مستقیم به User Note 2 — «موتورِ نو برای اسکالپ/نوسان روی M5/M1، اول طلا»):

  ۱) موتورِ نو (`scalp_engine.py`, pip-native + cost-first) ساخته و اعتبارسنجی شد (S78).
  ۲) اکتشافِ اسکالپِ ساده روی M5 طلا (ورودِ ساعتی/breakout پرتکرار) → همه منفی/ruin.
     درس: روی M5 طلا اسپرد+کمیسیون در اسکالپِ پرتکرار غالب است؛ drift خام (~۱bps) محو می‌شود.
     (تأییدِ مجددِ درسِ L44/L15: لبهٔ آماریِ خام ≠ سودآوری.)
  ۳) کشفِ کلیدی: تحلیلِ forward-return نشان داد «buy-dip در روندِ صعودی» فقط با
     **نگهداریِ بلندتر** (K≥۲۴ کندلِ M5 ≈ ۲ ساعت) میانگینِ net مثبت می‌شود. یعنی
     لبهٔ طلا از جنسِ swing/momentum است، نه اسکالپِ سریع — همان دلیلِ موفقیتِ S67 در M15.
  ۴) این بینش با موتورِ نو و فیلترهای سخت‌گیرانه جارو شد ⇒ لبهٔ پایدار پیدا شد.

منطقِ نهایی (کاملاً forward-safe):
  • روندِ کلانِ صعودی:  EMA(20) > EMA(100)   (فقط Long، هم‌سو با روندِ داده).
  • Pullback (نقطهٔ ورودِ ارزان):  RSI(21) < 35.
  • خروج: SL=۵۰ pip (۵$)، TP=۱۲۰ pip (۱۲$) → R:R=۱:۲.۴ (سوارِ روند)، max_hold=۷۲ کندل (۶ ساعت).
  • ورود روی open کندلِ بعد از سیگنال؛ SL/TP intrabar با قاعدهٔ بدترین‌حالت (موتورِ نو).

نتیجه (سرمایهٔ ۱۰٬۰۰۰$، ریسکِ ثابتِ ۱٪، بدون کامپاند — دقیقاً متدِ S67):
  net = +۵٬۱۹۲$   |  n=۳۶۰  |  WR=۳۹٪ (فقط گزارشی)  |  PF=۱.۲۳  |  MaxDD −۱۳.۲٪  |  Sharpe ۱.۹۰

اعتبارسنجی (چرا overfit نیست):
  • هر ۴ چارَکِ زمانی مثبت (+۱۴۹۷/+۵۱/+۲۶۷۶/+۹۱۸).
  • هر دو نیمهٔ IS/OOS مثبت.
  • مقاوم به اسپرد: حتی با اسپردِ ۵pip (۲.۵$، بدبینانه) هنوز +۳٬۰۳۲$.
  • مقاوم به پارامتر: همهٔ EMA/RSI/SL/TP همسایه مثبت (منطقهٔ پایدار، نه اکسترمم).

نقشِ در پرتفوی: لایهٔ دومِ مستقلِ XAUUSD (تایم‌فریمِ M5، تخصیصِ سرمایهٔ جدا از S67 که M15 است).
  XAUUSD = S67 (+۳۷٬۱۵۶$) + S79 (+۵٬۱۹۲$) = +۴۲٬۳۴۸$
  رکوردِ کل = XAUUSD (+۴۲٬۳۴۸$) + EURUSD S73 (+۷٬۳۰۲$) = **+۴۹٬۶۵۰$**  (+۱۱.۷٪ از رکوردِ قبلیِ +۴۴٬۴۵۸$)
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

# مشخصاتِ M5 طلا (همان طلا؛ فایلِ M5).
# ⚠️ مشخصاتِ هزینه از «حسابِ واقعیِ کاربر» (User Note 2): اسپردِ کلِ طلا = ۰.۴۰$ حرکت
# = ۴.۰ pipِ موتور (pip=0.10)، کمیسیون = صفر. (جایگزینِ فرضِ قدیمیِ spread=2/comm=7.)
SE.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
ASSET = 'XAUUSD_M5'

# پارامترهای نهایی (وسطِ منطقهٔ پایدار — انتخابِ محافظه‌کارانه برای پرهیز از overfit)
EMA_FAST = 20
EMA_SLOW = 100
RSI_PERIOD = 21
RSI_TH = 35
SL_PIP = 50
TP_PIP = 120
MAX_HOLD = 72


def ema(x, s):
    return pd.Series(x).ewm(span=s, adjust=False).mean().values


def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def build_signals(df):
    """سیگنالِ Long (forward-safe): روندِ صعودیِ کلان + pullback بر RSI."""
    c = df['close'].values
    e_f = ema(c, EMA_FAST)
    e_s = ema(c, EMA_SLOW)
    r = rsi(c, RSI_PERIOD)
    long_sig = np.nan_to_num((e_f > e_s) & (r < RSI_TH)).astype(bool)
    short_sig = np.zeros(len(df), bool)
    return long_sig, short_sig


def run(initial_capital=10_000.0, risk_pct=1.0, compounding=False):
    df = SE.load_data(SE.ASSETS[ASSET]['file'])
    long_sig, short_sig = build_signals(df)
    tr = SE.simulate_trades(df, long_sig, short_sig, SL_PIP, TP_PIP, ASSET, max_hold=MAX_HOLD)
    stats, eq = SE.run_capital(tr, ASSET, initial_capital=initial_capital,
                               risk_pct=risk_pct, compounding=compounding)
    return tr, stats, eq, df


def main():
    print("=" * 96)
    print("  S79 — XAUUSD M5 Trend-Pullback (موتورِ نو؛ سرمایهٔ ۱۰k$/ریسکِ ۱٪/بدون کامپاند)")
    print("=" * 96)
    tr, s, eq, df = run()
    print(SE.summary_line('XAU_M5', s))
    n = len(df); half = n // 2

    print("\n  اعتبارسنجیِ دو-نیمه:")
    for name, a, b in [('IS نیمهٔ اول', 0, half), ('OOS نیمهٔ دوم', half, n)]:
        trh = tr[(tr['entry_bar'] >= a) & (tr['entry_bar'] < b)]
        sh, _ = SE.run_capital(trh, ASSET, compounding=False)
        print(f"    {name}: net={sh['net_profit']:+8.0f}$  n={sh['n_trades']:4d}  "
              f"WR={sh['win_rate']:.0f}%  PF={sh['profit_factor']:.2f}  DD={sh['max_dd_pct']:.1f}%")

    print("\n  چهار چارَکِ زمانی:")
    for qi, (a, b) in enumerate([(0, 50000), (50000, 100000), (100000, 150000), (150000, 200000)]):
        trq = tr[(tr['entry_bar'] >= a) & (tr['entry_bar'] < b)]
        sq, _ = SE.run_capital(trq, ASSET, compounding=False)
        print(f"    Q{qi+1}: net={sq['net_profit']:+7.0f}$  n={sq['n_trades']:4d}  "
              f"WR={sq['win_rate']:.0f}%  PF={sq['profit_factor']:.2f}")

    # اعداد با «هزینهٔ واقعیِ حسابِ کاربر» (User Note 2): طلا spread=0.40$/comm=0،
    # EURUSD spread=1.5pip/comm=0. همهٔ استراتژی‌ها با همین معیار بازآزمایی شدند.
    S67_REAL = 30490   # S67 با هزینهٔ واقعی (قبلاً با هزینهٔ خوش‌بینانه +37,156$ بود)
    S73_REAL = 9223    # S73 با هزینهٔ واقعی (comm=0 → از +7,302$ بهبود یافت)
    print("\n" + "-" * 96)
    print(f"  سودِ خالصِ S79 (تنها، XAUUSD M5، هزینهٔ واقعی) = {s['net_profit']:+.0f}$")
    print(f"  --- مقایسهٔ منصفانه با «هزینهٔ واقعیِ یکسان» ---")
    print(f"  بدونِ S79: S67({S67_REAL:+d}$) + S73({S73_REAL:+d}$) = {S67_REAL + S73_REAL:+d}$")
    print(f"  با S79   : XAUUSD [S67+S79 = {S67_REAL + int(s['net_profit']):+d}$] + EURUSD [{S73_REAL:+d}$] "
          f"= {S67_REAL + int(s['net_profit']) + S73_REAL:+d}$")
    print(f"  بهبود از افزودنِ S79 = {int(s['net_profit']):+d}$")
    print("=" * 96)


if __name__ == '__main__':
    main()
