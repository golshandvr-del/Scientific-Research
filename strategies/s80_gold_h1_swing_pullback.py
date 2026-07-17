"""
S80 — XAUUSD H1 Swing Trend-Pullback (لایهٔ سومِ مستقلِ طلا؛ رکوردِ جدیدِ سودِ خالص)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR از این پس صرفاً
> یک عددِ گزارشی است، نه هدف و نه قید. تعدادِ معامله در روز و Profit Factor هم هدف
> نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.** تنها تابعِ هدفِ کلِ پروژه:
> **سودِ خالصِ تجمعیِ پس از اسپرد/کمیسیون/اسلیپیج.**
>
> **تعریفِ رسمیِ سودِ خالص در این پروژه = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

================================================================================
انگیزهٔ نظری (مستقیماً از تحقیقِ فراکتال/Hurst در research/DeepResearch_...):
  • «خود-تشابهیِ Mandelbrot»: روند در همهٔ TFها هست اما با شدتِ متفاوت.
  • «کشفِ Hurst»: حافظهٔ روند (H) در افقِ بلندتر بزرگ‌تر است (DAX: H=0.54 روزانه →
    H=0.82 در ۵۰ روز). ⇒ لبهٔ روند روی H1 باید تمیزتر از M15/M5 باشد و هزینهٔ نسبیِ
    اسپرد (۴pip روی حرکت‌های صدها-pipیِ H1) ناچیز شود.
  • S67 روی M15 و S79 روی M5 است. H1 یک تایم‌فریمِ کاملاً مستقل است.

داستانِ کشف:
  ۱) explore_eurusd_all_sessions/short_design: تلاش برای گسترشِ EURUSD به Short سشنی
     (ساعت ۲۲/۱۳ UTC) — درفتِ نزولی واقعی بود اما (~0.6pip) زیرِ آستانهٔ هزینهٔ 2.1pip
     ⇒ ruin. تأییدِ پنجمِ «لبهٔ خام ≠ سود» (فایلِ EURUSD_MultiSession_Short_Fail).
  ۲) explore_gold_h1_swing: منطقِ برندهٔ trend-pullbackِ S79 روی H1 جارو شد و یک
     لبهٔ سوددهِ پایدار پیدا شد (net=+10,064$، هر دو نیمه مثبت).
  ۳) explore corr: همبستگیِ pnl روزانهٔ S80(H1) با S79(M5) = −0.01 (تقریباً صفر)
     ⇒ S80 یک جریانِ سودِ کاملاً مستقل است، نه تکرارِ S79. ⇒ افزودنیِ واقعیِ پرتفوی.

منطقِ نهایی (کاملاً forward-safe، همان قالبِ S79):
  • روندِ کلانِ صعودی:  EMA(20) > EMA(100).
  • Pullback (نقطهٔ ورودِ ارزان):  RSI(14) < 40.
  • خروج: SL=۱۵۰ pip (۱۵$)، TP=۷۰۰ pip (۷۰$) → R:R≈۱:۴.۷ (سوارِ روندِ بزرگِ H1)،
    max_hold=۷۲ کندلِ H1 (۳ روز).
  • ورود روی open کندلِ بعد از سیگنال؛ SL/TP intrabar با قاعدهٔ بدترین‌حالت (موتورِ نو).
  • فقط Long (دادهٔ طلا در کل روندیِ صعودی است؛ Short در این رژیم لبه نداشت).

نتیجه (سرمایهٔ ۱۰٬۰۰۰$، ریسکِ ثابتِ ۱٪، بدون کامپاند — دقیقاً متدِ S67/S79):
  net = +۱۰٬۰۶۴$  |  n=۷۴۸  |  WR=۳۸.۰٪ (فقط گزارشی)  |  PF=۱.۲۲  |  MaxDD −۱۰.۳٪  |  Sharpe ۲.۰۷

اعتبارسنجی (چرا overfit نیست):
  • هر ۴ چارَکِ زمانی مثبت (+۷۹/+۸۹۲/+۵۹۵/+۸۴۹۸).
  • هر دو نیمهٔ IS/OOS مثبت (+۹۷۱ / +۹٬۰۹۳).
  • مقاوم به هزینه: حتی با اسپردِ ۸pip (دو برابرِ واقعی) هنوز +۷٬۹۶۹$.
  • مقاوم به پارامتر: RSI∈{35..45}, SL∈{100..250}, TP∈{400..1200}, EMA همسایه‌ها همه مثبت.
  • همبستگیِ ~صفر با S79 ⇒ استقلالِ آماری.

نقشِ در پرتفوی: لایهٔ **سومِ مستقلِ XAUUSD** روی تایم‌فریمِ **H1** (تخصیصِ سرمایهٔ جدا).
  XAUUSD = S67 (+۳۰٬۴۹۰$، M15) + S79 (+۴٬۲۵۶$، M5) + S80 (+۱۰٬۰۶۴$، H1) = +۴۴٬۸۱۰$
  رکوردِ کل = XAUUSD (+۴۴٬۸۱۰$) + EURUSD S73 (+۹٬۲۲۳$) = **+۵۴٬۰۳۳$**
  (+۱۰٬۰۶۵$ / +۲۲.۹٪ از رکوردِ قبلیِ +۴۳٬۹۶۸$)
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

# مشخصاتِ H1 طلا؛ هزینهٔ واقعیِ حسابِ کاربر: اسپرد=۴pip(۰.۴۰$)، کمیسیون=صفر.
SE.ASSETS['XAUUSD_H1'] = dict(file='data/XAUUSD_H1.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
ASSET = 'XAUUSD_H1'

# پارامترهای نهایی (وسطِ منطقهٔ پایدار — انتخابِ محافظه‌کارانه برای پرهیز از overfit)
EMA_FAST = 20
EMA_SLOW = 100
RSI_PERIOD = 14
RSI_TH = 40
SL_PIP = 150
TP_PIP = 700
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
    long_sig = np.nan_to_num((ema(c, EMA_FAST) > ema(c, EMA_SLOW)) & (rsi(c, RSI_PERIOD) < RSI_TH)).astype(bool)
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
    print("  S80 — XAUUSD H1 Swing Trend-Pullback (موتورِ نو؛ ۱۰k$/ریسکِ ۱٪/بدون کامپاند)")
    print("=" * 96)
    tr, s, eq, df = run()
    print(SE.summary_line('XAU_H1', s))
    n = len(df); half = n // 2

    print("\n  اعتبارسنجیِ دو-نیمه:")
    for name, a, b in [('IS نیمهٔ اول', 0, half), ('OOS نیمهٔ دوم', half, n)]:
        trh = tr[(tr['entry_bar'] >= a) & (tr['entry_bar'] < b)]
        sh, _ = SE.run_capital(trh, ASSET, compounding=False)
        print(f"    {name}: net={sh['net_profit']:+8.0f}$  n={sh['n_trades']:4d}  "
              f"WR={sh['win_rate']:.0f}%  PF={sh['profit_factor']:.2f}  DD={sh['max_dd_pct']:.1f}%")

    print("\n  چهار چارَکِ زمانی:")
    q = n // 4
    for qi in range(4):
        a, b = qi * q, (qi + 1) * q if qi < 3 else n
        trq = tr[(tr['entry_bar'] >= a) & (tr['entry_bar'] < b)]
        sq, _ = SE.run_capital(trq, ASSET, compounding=False)
        print(f"    Q{qi+1}: net={sq['net_profit']:+7.0f}$  n={sq['n_trades']:4d}  "
              f"WR={sq['win_rate']:.0f}%  PF={sq['profit_factor']:.2f}")

    # اعداد با «هزینهٔ واقعیِ حسابِ کاربر» (طلا spread=0.40$/comm=0، EURUSD spread=1.5pip/comm=0)
    S67_REAL = 30490
    S79_REAL = 4256
    S73_REAL = 9223
    prev_record = S67_REAL + S79_REAL + S73_REAL  # +43,968$
    new_xau = S67_REAL + S79_REAL + int(s['net_profit'])
    new_total = new_xau + S73_REAL
    print("\n" + "-" * 96)
    print(f"  سودِ خالصِ S80 (تنها، XAUUSD H1، هزینهٔ واقعی) = {s['net_profit']:+.0f}$")
    print(f"  --- پرتفویِ چهار-لایه با «هزینهٔ واقعیِ یکسان» ---")
    print(f"  رکوردِ قبلی (S67+S79+S73)         = {prev_record:+d}$")
    print(f"  XAUUSD [S67+S79+S80 = {new_xau:+d}$] + EURUSD [S73 {S73_REAL:+d}$] = {new_total:+d}$")
    print(f"  بهبود از افزودنِ S80 = {int(s['net_profit']):+d}$  ({s['net_profit']/prev_record*100:+.1f}%)")
    print("=" * 96)


if __name__ == '__main__':
    main()
