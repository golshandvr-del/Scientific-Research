# ============================================================================
# استراتژی ۸۶ — «تشخیصِ جهتِ رفتارِ چارت و سنجشِ سودِ خالص» (پاسخِ اصلیِ User Note)
# ----------------------------------------------------------------------------
# قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدف **فقط و فقط «سودِ خالصِ بیشتر»** است —
# نه Win-Rate. تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD. WR گزارشی است.
#
# پیش‌زمینه (کشفِ S85):
#   پیش‌بینیِ «جهتِ هر کندلِ منفرد» شکست خورد (همهٔ اندیکاتورها و ML زیرِ baselineِ
#   drift ماندند؛ ML حتی UP-share=۰.۴۶ داشت ⇒ کورکورانه short می‌داد = دقیقاً بیماریِ
#   سایت). درسِ علمی: بازار در این تایم‌فریم نیمه‌قوی است؛ لبهٔ واقعی نه در «هر کندل»
#   بلکه در **جهتِ رژیم/drift** است.
#
# این اسکریپت آن درس را به سودِ خالص تبدیل می‌کند. سه مدلِ رفتاری را روی بازهٔ
# یک‌سالِ اخیرِ طلا (M15) با موتورِ سرمایه‌محورِ واقعی (scalp_engine، هزینهٔ واقعیِ
# کاربر) می‌سنجد:
#
#   MODE-1  SYMMETRIC   : هر جا اندیکاتور سیگنال داد long/short (رفتارِ غلطِ سایت).
#   MODE-2  SHORT-ONLY  : فقط short (اثباتِ اینکه در بازارِ صعودی زیان‌ده است).
#   MODE-3  REGIME-LONG : فقط هم‌سو با رژیمِ روندِ صعودی (فیلترِ جهتِ درست).
#
# فرضیهٔ کاربر: «سایت در روندِ صعودی short می‌داد و ضرر می‌کرد.» انتظار: MODE-2 و
# نیمهٔ shortِ MODE-1 زیان‌ده، و MODE-3 (هم‌سو با رفتارِ واقعیِ چارت) سودده باشد.
#
# تعریفِ «رفتارِ چارت» به‌صورتِ عملیاتی و forward-safe:
#   رژیم = وضعیتِ EMAهای بلند (ema50 vs ema200) + شیبِ ema50. این «حالتِ رفتاری»
#   است که تنها از گذشته محاسبه می‌شود. ورود = پول‌بکِ کوتاه (RSI پایین) در جهتِ رژیم.
# ============================================================================
import sys, os
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, rsi, atr, macd, adx
from engine import scalp_engine as SE

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data', 'XAUUSD_M15.csv')
ASSET = 'XAUUSD'


def load_last_year():
    df = pd.read_csv(DATA)
    df.columns = [c.strip().lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    cutoff = df['dt'].max() - pd.Timedelta(days=365)
    d = df[df['dt'] >= cutoff].reset_index(drop=True)
    d['dt2'] = pd.to_datetime(d['time'], unit='s')  # برای موتور (بدون tz)
    return d


def add_ind(d):
    c = d['close']
    d['ema20'] = ema(c, 20)
    d['ema50'] = ema(c, 50)
    d['ema100'] = ema(c, 100)
    d['ema200'] = ema(c, 200)
    d['rsi14'] = rsi(c, 14)
    d['rsi21'] = rsi(c, 21)
    d['atr14'] = atr(d, 14)
    _, _, hist = macd(c)
    d['macd_hist'] = hist
    a, pdi, mdi = adx(d, 14)
    d['adx'] = a; d['plus_di'] = pdi; d['minus_di'] = mdi
    d['ema50_slope'] = d['ema50'].diff(5)
    return d


def report(name, stats):
    print('%-22s | net=%+9.1f$  ret=%+7.1f%%  trades=%4d  WR=%.1f%%  PF=%.2f  DD=%.1f%%'
          % (name, stats['net_profit'], stats['return_pct'], stats['n_trades'],
             stats['win_rate'], stats['profit_factor'], stats['max_dd_pct']))


def run_mode(d, long_sig, short_sig, sl_pip, tp_pip, name, max_hold=48):
    dd = d.rename(columns={'dt2': 'dt'}) if 'dt2' in d.columns else d
    trades = SE.simulate_trades(dd, long_sig, short_sig, sl_pip, tp_pip, ASSET,
                                max_hold=max_hold, allow_overlap=False)
    stats, _ = SE.run_capital(trades, ASSET, initial_capital=10_000.0, risk_pct=1.0)
    report(name, stats)
    return stats


def main():
    d = load_last_year()
    d = add_ind(d)
    print('=' * 92)
    move = (d['close'].iloc[-1] / d['close'].iloc[0] - 1) * 100
    print('بازهٔ یک‌سالِ اخیرِ طلا M15 | کندل‌ها=%d | حرکتِ قیمت=%.1f%% (روندِ صعودیِ قوی)'
          % (len(d), move))
    print('=' * 92)

    # --- تعریفِ رژیمِ رفتاری (فقط گذشته → forward-safe) ---
    uptrend = (d['ema50'] > d['ema200']) & (d['ema50_slope'] > 0)
    downtrend = (d['ema50'] < d['ema200']) & (d['ema50_slope'] < 0)
    print('سهمِ کندل‌ها در رژیمِ صعودی: %.1f%% | نزولی: %.1f%% | خنثی: %.1f%%'
          % (uptrend.mean()*100, downtrend.mean()*100,
             (1-uptrend.mean()-downtrend.mean())*100))
    print('-' * 92)

    # سیگنالِ پایه: پول‌بکِ RSI (ورود پس از اصلاحِ کوتاه)
    pullback_long = (d['rsi14'] < 40)
    pullback_short = (d['rsi14'] > 60)

    SL, TP = 120.0, 240.0   # pip (R:R = 1:2)، هم‌راستا با لایه‌های swingِ طلا

    # MODE-1: SYMMETRIC (رفتارِ غلطِ سایت — long و short بی‌توجه به رژیم)
    run_mode(d, pullback_long.values, pullback_short.values, SL, TP,
             'MODE-1 SYMMETRIC')

    # MODE-2: SHORT-ONLY (اثباتِ زیان‌دهی در بازارِ صعودی)
    run_mode(d, np.zeros(len(d), bool), pullback_short.values, SL, TP,
             'MODE-2 SHORT-ONLY')

    # MODE-2b: LONG-ONLY (بی‌فیلتر)
    run_mode(d, pullback_long.values, np.zeros(len(d), bool), SL, TP,
             'MODE-2b LONG-ONLY')

    # MODE-3: REGIME-LONG (فقط هم‌سو با رژیمِ صعودی)
    rl = (pullback_long & uptrend).values
    run_mode(d, rl, np.zeros(len(d), bool), SL, TP,
             'MODE-3 REGIME-LONG')

    # MODE-3b: REGIME دو-طرفه (long در صعودی، short در نزولی) — «رفتارِ درست»
    rl2 = (pullback_long & uptrend).values
    rs2 = (pullback_short & downtrend).values
    run_mode(d, rl2, rs2, SL, TP,
             'MODE-3b REGIME-BOTH')

    print('=' * 92)
    print('نتیجهٔ کلیدی: مقایسهٔ MODE-1/2 (متقارن/short) با MODE-3 (فیلترِ رژیمِ جهت).')
    print('این عددها ورودیِ فایلِ MD و تصمیمِ به‌روزرسانیِ منطقِ سایت‌اند.')


if __name__ == '__main__':
    main()
