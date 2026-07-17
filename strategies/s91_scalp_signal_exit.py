# -*- coding: utf-8 -*-
"""
s91_scalp_signal_exit.py — بازنگریِ بخشِ اسکالپ (پاسخِ User Note)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله در روز و Profit Factor هم هدف نیستند. **ما دنبالِ پول
> هستیم، نه آمارِ زیبا.** تنها تابعِ هدفِ کلِ پروژه: **سودِ خالصِ تجمعیِ پس از
> اسپرد/کمیسیون/اسلیپیج.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**
================================================================================

انگیزه (پاسخِ مستقیم به User Note این چرخه):
  کاربر می‌خواهد بخشِ اسکالپِ سایت **بدونِ TP/SL و بدونِ حجم** کار کند:
    ۱) سایت مستقیماً می‌گوید BUY یا SELL (طبقِ تشخیصِ خودش).
    ۲) کاربر با یک دکمه تأیید می‌کند که معاملهٔ دمو را باز کرده.
    ۳) سایت وارد حالتِ «مدیریت» می‌شود و فقط **لحظه‌ای** می‌گوید:
       «ما سودمونو گرفتیم، سریع معامله رو ببند» یا
       «متاسفم تشخیصم اشتباه بود، سریع معامله رو ببند».
    ۴) یک دکمه که کاربر بزند «بستم».

  این یعنی خروج دیگر یک قیمتِ ثابت (TP/SL) نیست؛ خروج یک **تصمیمِ لحظه‌ایِ
  سیگنال-محور** است که هر کندل، با اندیکاتورهای زنده، تصمیم می‌گیرد ببندد یا نه.

  چون خروجْ سیگنال-محور است (نه TP/SL)، موتورِ قدیمیِ scalp_engine.simulate_trades
  (که فقط TP/SL را intrabar می‌سنجد) کافی نیست. این فایل یک **paper broker** با
  خروجِ per-bar می‌سازد و چند منطقِ خروجِ سیگنال-محور را روی دادهٔ واقعیِ M5 تست
  می‌کند تا مطمئن شویم منطقِ سایت واقعاً سودده است — دقیقاً همان‌طور که کاربر
  خواست «حتماً با تست paper broker تست کنیم».

مدلِ واقع‌گرایی (هم‌راستا با scalp_engine و مشخصاتِ حسابِ واقعیِ کاربر):
  • طلا: pip=0.10$، ۱ لات=۱۰۰ اونس، اسپردِ کل=۴ pip (۰.۴۰$)، کمیسیون صفر،
    اسلیپیجِ ۰.۵ pip هر طرف.
  • ورود در open کندلِ بعد از سیگنال (forward-safe).
  • خروج در open کندلِ بعد از تصمیمِ خروج (forward-safe — تصمیم روی close کندلِ t
    گرفته می‌شود، اجرا در open کندلِ t+1).
  • هزینهٔ رفت‌وبرگشت + اسلیپیجِ دو طرف روی هر معامله اعمال می‌شود.
  • یک SLِ فاجعه‌ایِ پنهان (catastrophic stop) برای واقع‌گرایی: کاربر آن را نمی‌بیند،
    اما اگر بازار ناگهان بترکد و منطقِ خروج فرصتِ واکنش نداشته باشد، معامله بسته
    می‌شود (شبیه‌سازیِ اینکه کاربر بی‌نهایت ضرر نمی‌کند). این عدد بزرگ است تا
    خروجِ سیگنال-محور نقشِ اصلی را بازی کند، نه SLِ ثابت.
================================================================================
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M5.csv')

# ------------------------------------------------------------------------------
# مشخصاتِ واقعیِ طلا (هم‌راستا با engine/scalp_engine.py و حسابِ واقعیِ کاربر)
# ------------------------------------------------------------------------------
PIP = 0.10            # اندازهٔ یک pip بر حسبِ قیمت
CONTRACT = 100.0      # اونس در ۱ لات
PIP_VALUE = CONTRACT * PIP   # ارزشِ دلاریِ ۱ pip برای ۱ لات = 10$
SPREAD_PIP = 4.0      # اسپردِ رفت‌وبرگشت (۰.۴۰$)
SLIP_PIP = 0.5        # اسلیپیج هر طرف
COMM_PER_LOT = 0.0    # کمیسیون رفت‌وبرگشت به‌ازای ۱ لات

COST_PIP = SPREAD_PIP + 2.0 * SLIP_PIP   # هزینهٔ ثابتِ رفت‌وبرگشت بر حسبِ pip

# سرمایه/ریسک (فقط برای گزارشِ سرمایه‌محور؛ چون کاربر حجم نمی‌بیند، حجمِ ثابتِ
# محافظه‌کارانهٔ ۰.۰۱ لات فرض می‌شود تا مقایسه‌ی سودِ خالص واقع‌بینانه بماند و
# به مدلِ ریسکِ درصدی که کاربر دیگر نمی‌بیند وابسته نباشد).
FIXED_LOT = 0.01
INITIAL_CAPITAL = 10000.0


# ------------------------------------------------------------------------------
# اندیکاتورها (بازتولیدِ دقیقِ همان فرمول‌هایی که در indicators.ts سایت هست)
# ------------------------------------------------------------------------------
def ema(x, period):
    x = np.asarray(x, dtype=np.float64)
    out = np.full_like(x, np.nan)
    k = 2.0 / (period + 1.0)
    acc = x[0]
    out[0] = acc
    for i in range(1, len(x)):
        acc = x[i] * k + acc * (1 - k)
        out[i] = acc
    return out


def rsi(x, period=14):
    x = np.asarray(x, dtype=np.float64)
    n = len(x)
    out = np.full(n, np.nan)
    if n < period + 1:
        return out
    delta = np.diff(x)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag = gain[:period].mean()
    al = loss[:period].mean()
    out[period] = 100.0 - 100.0 / (1.0 + (ag / al if al > 0 else np.inf))
    for i in range(period + 1, n):
        ag = (ag * (period - 1) + gain[i - 1]) / period
        al = (al * (period - 1) + loss[i - 1]) / period
        rs = ag / al if al > 0 else np.inf
        out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def atr(df, period=14):
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    out = np.full(n, np.nan)
    if n < period:
        return out
    acc = tr[:period].mean()
    out[period - 1] = acc
    for i in range(period, n):
        acc = (acc * (period - 1) + tr[i]) / period
        out[i] = acc
    return out


# ==============================================================================
# PAPER BROKER — شبیه‌سازِ خروجِ سیگنال-محور (per-bar exit)
# ==============================================================================
def paper_broker(df, entries, exit_fn, catastrophic_sl_pip=200.0, max_hold=288):
    """
    شبیه‌سازیِ paper broker با خروجِ per-bar.

    df                : دیتافریمِ OHLC (طلا M5).
    entries           : لیست از tuple (bar_index, 'long'|'short') — سیگنالِ ورود.
                        ورود در open کندلِ bar_index+1 اجرا می‌شود (forward-safe).
    exit_fn(ctx)      : تابعِ تصمیمِ خروج. ورودی dict شاملِ:
                          side, entry_fill, i (کندلِ جاری), price(=close[i]),
                          bars_held, favor_pip (سود/زیانِ فعلی بر حسبِ pip، خالص از
                          هزینه), rsi, ema_f, ema_s, atr, macd_hist, peak_favor_pip.
                        باید یکی از این‌ها را برگرداند:
                          None            → نگه‌دار
                          ('win', reason)  → «سودمونو گرفتیم، ببند»
                          ('loss', reason) → «تشخیص اشتباه بود، ببند»
    catastrophic_sl_pip: SLِ فاجعه‌ایِ پنهان (کاربر نمی‌بیند) — فقط واقع‌گرایی.
    max_hold          : حداکثر کندلِ نگهداری (۲۸۸ کندلِ M5 = ۲۴ ساعت).

    خروج در open کندلِ بعد از تصمیم اجرا می‌شود (forward-safe).
    برمی‌گرداند: DataFrame معاملات با pnl_pip (خالص از هزینه) + net_usd.
    """
    o = df['open'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    n = len(df)

    emaF = ema(c, 20)
    emaS = ema(c, 100)
    rsiArr = rsi(c, 21)
    atrArr = atr(df, 14)
    # MACD hist (12,26,9)
    macd_line = ema(c, 12) - ema(c, 26)
    macd_sig = ema(macd_line, 9)
    macd_hist = macd_line - macd_sig

    trades = []
    busy_until = -1

    for (si, side) in entries:
        entry_bar = si + 1
        if entry_bar >= n:
            continue
        if entry_bar <= busy_until:
            continue

        raw_entry = o[entry_bar]
        # اسلیپیجِ ورود (بدتر برای کاربر)
        if side == 'long':
            entry_fill = raw_entry + SLIP_PIP * PIP
        else:
            entry_fill = raw_entry - SLIP_PIP * PIP

        exit_bar = None
        exit_price = None
        outcome = None
        reason = ''
        peak_favor_pip = 0.0
        pending_exit = None   # تصمیمِ خروج که کندلِ بعد اجرا می‌شود

        end = min(entry_bar + max_hold, n)
        for j in range(entry_bar, end):
            # اگر تصمیمِ خروج در کندلِ قبل گرفته شده، همین‌جا (open کندلِ j) اجرا کن
            if pending_exit is not None:
                outcome, reason = pending_exit
                exit_bar = j
                exit_price = o[j]  # اجرا در open (forward-safe)
                break

            # سود/زیانِ جاری بر حسبِ قیمت (تا close این کندل)
            price = c[j]
            if side == 'long':
                favor = price - entry_fill
                # SLِ فاجعه‌ای intrabar (پنهان)
                cat_hit = l[j] <= entry_fill - catastrophic_sl_pip * PIP
            else:
                favor = entry_fill - price
                cat_hit = h[j] >= entry_fill + catastrophic_sl_pip * PIP

            favor_pip_gross = favor / PIP
            if favor_pip_gross > peak_favor_pip:
                peak_favor_pip = favor_pip_gross

            if cat_hit:
                # فاجعه: بستن intrabar روی SL فاجعه‌ای
                outcome = 'loss'; reason = 'catastrophic_stop'
                exit_bar = j
                exit_price = (entry_fill - catastrophic_sl_pip * PIP) if side == 'long' \
                    else (entry_fill + catastrophic_sl_pip * PIP)
                break

            ctx = {
                'side': side, 'entry_fill': entry_fill, 'i': j, 'price': price,
                'bars_held': j - entry_bar,
                'favor_pip': favor_pip_gross - COST_PIP,   # خالص از هزینه (تخمین لحظه‌ای)
                'favor_pip_gross': favor_pip_gross,
                'peak_favor_pip': peak_favor_pip,
                'rsi': rsiArr[j], 'ema_f': emaF[j], 'ema_s': emaS[j],
                'atr': atrArr[j], 'macd_hist': macd_hist[j],
            }
            decision = exit_fn(ctx)
            if decision is not None:
                pending_exit = decision   # اجرا در open کندلِ بعد

        # اگر تا max_hold باز ماند، در close آخرین کندل ببند
        if exit_bar is None:
            exit_bar = end - 1
            exit_price = c[exit_bar]
            outcome = 'timeout'
            reason = 'max_hold'

        # اسلیپیجِ خروج (بدتر برای کاربر)
        if side == 'long':
            exit_fill = exit_price - SLIP_PIP * PIP
            gross_price = exit_fill - entry_fill
        else:
            exit_fill = exit_price + SLIP_PIP * PIP
            gross_price = entry_fill - exit_fill

        # pnl بر حسبِ pip، خالص از اسپرد (اسلیپیج قبلاً در fill لحاظ شد)
        pnl_pip = gross_price / PIP - SPREAD_PIP
        net_usd = pnl_pip * PIP_VALUE * FIXED_LOT * (CONTRACT / CONTRACT) \
            - COMM_PER_LOT * FIXED_LOT
        # net_usd = pnl_pip * (ارزشِ pip برای FIXED_LOT)
        net_usd = pnl_pip * (PIP_VALUE * FIXED_LOT) - COMM_PER_LOT * FIXED_LOT

        trades.append({
            'entry_bar': entry_bar, 'exit_bar': exit_bar, 'side': side,
            'entry': entry_fill, 'exit': exit_fill, 'pnl_pip': pnl_pip,
            'net_usd': net_usd, 'bars_held': exit_bar - entry_bar,
            'outcome': outcome, 'reason': reason,
        })
        busy_until = exit_bar

    return pd.DataFrame(trades)


def stats(trades, label=''):
    if len(trades) == 0:
        return {'label': label, 'n': 0, 'net_usd': 0.0, 'net_pip': 0.0,
                'wr': 0.0, 'pf': 0.0, 'avg_hold': 0.0}
    net_usd = trades['net_usd'].sum()
    net_pip = trades['pnl_pip'].sum()
    wins = trades[trades['pnl_pip'] > 0]
    losses = trades[trades['pnl_pip'] <= 0]
    gross_win = wins['pnl_pip'].sum()
    gross_loss = abs(losses['pnl_pip'].sum())
    pf = gross_win / gross_loss if gross_loss > 0 else np.inf
    wr = len(wins) / len(trades) * 100
    return {
        'label': label, 'n': len(trades), 'net_usd': net_usd, 'net_pip': net_pip,
        'wr': wr, 'pf': pf, 'avg_hold': trades['bars_held'].mean(),
        'avg_pip': net_pip / len(trades),
    }


def print_stats(s):
    print(f"  [{s['label']}]  n={s['n']:5d}  net=${s['net_usd']:+9.2f}  "
          f"net_pip={s['net_pip']:+9.1f}  WR={s['wr']:5.1f}%  PF={s['pf']:.2f}  "
          f"avg_pip={s.get('avg_pip', 0):+.2f}  hold={s['avg_hold']:.1f}")


if __name__ == '__main__':
    print("=" * 78)
    print("s91 — بازنگریِ بخشِ اسکالپ با paper broker + خروجِ سیگنال-محور (بدون TP/SL)")
    print("=" * 78)
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    print(f"داده: {len(df)} کندلِ M5 طلا  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    print(f"هزینهٔ رفت‌وبرگشت: {COST_PIP} pip (اسپرد {SPREAD_PIP} + اسلیپیج {2*SLIP_PIP})")
    print()
    print("این اسکریپت فقط زیرساخت است؛ استراتژی‌ها در فایل‌های s91_* بعدی اجرا می‌شوند.")
