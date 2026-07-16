"""
استراتژی ۲۱: Session Opening-Range Breakout (ORB) + فیلتر فشردگی (Coiled-Spring)
================================================================================
مسیری که هیچ‌کدام از ۲۰ استراتژی قبلی امتحان نکرده‌اند:

  ایده ریاضی/رفتاری:
  ------------------
  در آغاز هر سشن بزرگ (لندن ~07:00 UTC، نیویورک ~13:00 UTC) نقدینگی و جهت‌گیری
  روزانه شکل می‌گیرد. «بازه افتتاحیه» (Opening Range) = high/low چند کندل ابتدای
  سشن. فرضیه‌ی کلاسیک ORB: عبور قیمت از سقف/کف این بازه، جهت غالب سشن را نشان
  می‌دهد و اغلب با ادامه‌ی حرکت همراه است.

  نوآوری متمایزکننده از استراتژی ۲۰ (TTM-Squeeze/Chandelier):
  ----------------------------------------------------------
  - تریگر اینجا «بازه‌ی زمانی افتتاحیه‌ی سشن» است، نه فشردگی BB-in-Keltner و نه
    عبور از سقف N کندلِ غلتان. این مفهوم زمان‌محور (time-anchored) کاملاً تازه است.
  - ورود «دوطرفه» با stop-order بالای high و زیر low بازه؛ جهت را خودِ بازار
    (اولین لمس) تعیین می‌کند — نه یک مدل جهت‌بین. این «bracket/OCO» را هیچ
    استراتژی قبلی نداشت.
  - فیلتر Coiled-Spring: فقط روزهایی که بازه‌ی افتتاحیه نسبت به ATR اخیر «باریک»
    است (فشردگی) معامله می‌شود — احتمال شکست انفجاری بالاتر.
  - TP/SL «خودتطبیق» بر پایه‌ی اندازه‌ی خودِ بازه (range) هستند، نه ATR مطلق.

  اجرای بدون look-ahead:
  ----------------------
  - بازه‌ی افتتاحیه فقط از کندل‌های داخل پنجره‌ی افتتاحیه ساخته می‌شود و معامله
    فقط از کندلِ *بعد از* پایان پنجره تا انتهای همان روز فعال است.
  - stop-order فقط وقتی فعال می‌شود که high/low کندل به سطح تریگر برسد؛ ورود در
    خودِ سطح تریگر (breakout price) انجام می‌شود (واقع‌بینانه، با اسپرد).
  - اگر هر دو طرف در یک کندل لمس شوند، بدترین حالت (ابتدا لمس مخالف سپس SL) لحاظ
    می‌شود؛ برای ورود دوطرفه، جهت اولین تریگر بر اساس نزدیکی open کندل تعیین می‌شود.

ارزیابی: Win Rate = درصد معاملاتی که به TP رسیدند قبل از SL. + expectancy + trades/day.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import atr as atr_ind
from engine.backtest import load_data


def run_orb(df, session_start_h, or_bars, atr_ratio_max, tp_mult, sl_mult,
            spread=0.20, max_hold_bars=48, day_end_h=None):
    """
    df              : دیتافریم M15 با ستون‌های open/high/low/close و dt
    session_start_h : ساعت UTC شروع سشن (مثلا 7 یا 13)
    or_bars         : تعداد کندل M15 برای ساخت بازه افتتاحیه (مثلا 4 = یک ساعت)
    atr_ratio_max   : حداکثر نسبت (range/ATR) برای فیلتر فشردگی؛ range باریک‌تر
                      از این نسبت اجازه معامله دارد (coiled spring). None = بدون فیلتر
    tp_mult, sl_mult: TP و SL به‌صورت ضریبی از اندازه‌ی range
    max_hold_bars   : حداکثر کندل نگهداری پس از ورود
    day_end_h       : اگر داده شود، معامله در این ساعت (UTC) بسته می‌شود (بستن روزانه)
    """
    df = df.copy()
    df['hour'] = df['dt'].dt.hour
    df['minute'] = df['dt'].dt.minute
    df['date'] = df['dt'].dt.date

    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    hour = df['hour'].values
    date = df['date'].values
    n = len(df)

    atr14 = atr_ind(df, 14).values

    trades = []

    # گروه‌بندی بر اساس روز
    unique_days = pd.unique(df['date'])
    # نگاشت date->اندیس‌های آن روز
    day_to_idx = {}
    for i in range(n):
        day_to_idx.setdefault(date[i], []).append(i)

    for d in unique_days:
        idxs = day_to_idx[d]
        # کندل‌های پنجره افتتاحیه: از ساعت session_start_h با or_bars کندل متوالی
        or_idx = [i for i in idxs if hour[i] == session_start_h]
        # or_bars کندل اول پنجره (M15 → 4 کندل = یک ساعت)
        or_idx = sorted(or_idx)[:or_bars]
        if len(or_idx) < or_bars:
            continue
        last_or = or_idx[-1]
        or_high = h[or_idx].max()
        or_low = l[or_idx].min()
        rng = or_high - or_low
        if rng <= 0:
            continue

        # فیلتر فشردگی: range نسبت به ATR اخیر
        a = atr14[last_or]
        if a is None or np.isnan(a) or a <= 0:
            continue
        if atr_ratio_max is not None and (rng / a) > atr_ratio_max:
            continue

        # کندل‌های فعال برای شکست: بعد از پایان پنجره افتتاحیه تا انتهای روز
        active = [i for i in idxs if i > last_or]
        if day_end_h is not None:
            active = [i for i in active if hour[i] <= day_end_h]
        if not active:
            continue
        active = sorted(active)

        long_trig = or_high
        short_trig = or_low

        # پیدا کردن اولین کندلی که یک طرف را تریگر می‌کند
        entered = False
        for k, j in enumerate(active):
            if k > max_hold_bars:
                break
            hit_long = h[j] >= long_trig
            hit_short = l[j] <= short_trig
            if not hit_long and not hit_short:
                continue
            # تعیین جهت: اگر هر دو در یک کندل، بر اساس اینکه open به کدام نزدیک‌تر است
            if hit_long and hit_short:
                direction = 'long' if abs(o[j] - long_trig) <= abs(o[j] - short_trig) else 'short'
            elif hit_long:
                direction = 'long'
            else:
                direction = 'short'

            if direction == 'long':
                fill = long_trig + spread
                tp_price = fill + tp_mult * rng
                sl_price = fill - sl_mult * rng
            else:
                fill = short_trig - spread
                tp_price = fill - tp_mult * rng
                sl_price = fill + sl_mult * rng

            # مدیریت معامله از همین کندل j (ورود در سطح تریگر، سپس بررسی TP/SL)
            outcome = None; exit_price = None; exit_bar = None
            for m_i, jj in enumerate(active[k:]):
                if m_i > max_hold_bars:
                    break
                hi, lo = h[jj], l[jj]
                if direction == 'long':
                    hit_sl = lo <= sl_price
                    hit_tp = hi >= tp_price
                else:
                    hit_sl = hi >= sl_price
                    hit_tp = lo <= tp_price
                if hit_sl and hit_tp:
                    outcome = 'loss'; exit_price = sl_price; exit_bar = jj; break
                elif hit_tp:
                    outcome = 'win'; exit_price = tp_price; exit_bar = jj; break
                elif hit_sl:
                    outcome = 'loss'; exit_price = sl_price; exit_bar = jj; break
            if outcome is None:
                exit_bar = active[min(k + max_hold_bars, len(active) - 1)]
                exit_price = c[exit_bar]
                pnl = (exit_price - fill) if direction == 'long' else (fill - exit_price)
                outcome = 'win' if pnl > 0 else 'loss'
            else:
                pnl = (exit_price - fill) if direction == 'long' else (fill - exit_price)

            trades.append({
                'date': str(d), 'session_h': session_start_h, 'direction': direction,
                'entry_bar': j, 'exit_bar': exit_bar, 'entry_price': fill,
                'exit_price': exit_price, 'outcome': outcome, 'pnl': pnl,
                'range': rng, 'atr': a, 'range_atr': rng / a,
            })
            entered = True
            break  # فقط یک معامله در هر سشن هر روز

    tr = pd.DataFrame(trades)
    if len(tr) == 0:
        return {'n_trades': 0, 'win_rate': 0.0, 'expectancy': 0.0, 'total_pnl': 0.0,
                'trades_per_day': 0.0}, tr

    wins = tr[tr['outcome'] == 'win']
    n_days = df['date'].nunique()
    stats = {
        'n_trades': len(tr),
        'win_rate': len(wins) / len(tr) * 100,
        'expectancy': tr['pnl'].mean(),
        'total_pnl': tr['pnl'].sum(),
        'trades_per_day': len(tr) / n_days,
        'avg_range_atr': tr['range_atr'].mean(),
    }
    return stats, tr


def main():
    df = load_data()
    print(f"داده: {len(df)} کندل، {df['dt'].dt.date.nunique()} روز")
    print("=" * 100)

    # جاروب اولیه روی سشن‌ها و پارامترها
    sessions = [7, 13]          # لندن، نیویورک (UTC)
    or_bars_list = [4]          # 4 کندل M15 = یک ساعت افتتاحیه
    atr_ratios = [None, 1.5, 1.2, 1.0, 0.8]   # فیلتر فشردگی
    tp_mults = [1.0, 1.5, 2.0]
    sl_mults = [0.5, 1.0]

    rows = []
    for sess in sessions:
        for orb in or_bars_list:
            for ar in atr_ratios:
                for tp in tp_mults:
                    for sl in sl_mults:
                        stats, tr = run_orb(df, sess, orb, ar, tp, sl,
                                            spread=0.20, max_hold_bars=48, day_end_h=21)
                        if stats['n_trades'] < 30:
                            continue
                        rows.append({
                            'sess': sess, 'or_bars': orb, 'atr_max': ar,
                            'tp': tp, 'sl': sl, **stats,
                        })

    res = pd.DataFrame(rows)
    res = res.sort_values(['win_rate'], ascending=False)
    pd.set_option('display.width', 200)
    pd.set_option('display.max_columns', 20)
    print(res.to_string(index=False))

    # بهترین بر اساس WR با فرکانس معقول
    print("\n" + "=" * 100)
    print("بهترین‌ها با WR>55 و trades_per_day>=0.5:")
    good = res[(res['win_rate'] > 55) & (res['trades_per_day'] >= 0.5)]
    print(good.to_string(index=False) if len(good) else "هیچ‌کدام")


if __name__ == '__main__':
    main()
