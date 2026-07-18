"""
موتور بک‌تست استاندارد و مشترک برای تمام استراتژی‌ها.

منطق:
- سیگنال‌ها روی کندل i تولید می‌شوند (فقط با اطلاعات بسته‌شدن کندل i و قبل‌تر).
- ورود به معامله در قیمت OPEN کندل i+1 (بدون look-ahead).
- هر معامله SL و TP دارد. برای هر کندل بعد از ورود، بررسی می‌شود که آیا
  TP یا SL لمس شده. اگر هر دو در یک کندل لمس شوند (کندل ابهام)، بدترین حالت
  (SL) در نظر گرفته می‌شود -> محافظه‌کارانه و واقع‌بینانه.
- اسپرد و کمیسیون لحاظ می‌شود.

Win Rate = تعداد معاملاتی که به TP رسیدند / کل معاملات بسته‌شده.
"""
import numpy as np
import pandas as pd


def load_data(path='data/XAUUSD_M15.csv'):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df = df.reset_index(drop=True)
    return df


def run_backtest(df, entries, sl_points, tp_points, direction,
                 spread=0.20, max_hold=200, allow_overlap=False,
                 sl_series=None, tp_series=None):
    """
    df          : دیتافریم با ستون‌های open/high/low/close
    entries     : آرایه بولین هم‌طول df؛ True یعنی سیگنال ورود روی این کندل
                  (ورود در open کندل بعدی انجام می‌شود)
    sl_points   : فاصله ثابت استاپ‌لاس بر حسب دلار (یا None اگر sl_series داده شود)
    tp_points   : فاصله ثابت تیک‌پروفیت بر حسب دلار (یا None اگر tp_series داده شود)
    direction   : 'long' یا 'short'
    spread      : اسپرد بر حسب دلار (هزینه ورود)
    max_hold    : حداکثر تعداد کندل نگهداری؛ بعد از آن معامله با قیمت close بسته می‌شود
    allow_overlap: اگر False، تا بسته‌شدن معامله فعلی وارد معامله جدید نمی‌شویم
    sl_series/tp_series: در صورت نیاز به SL/TP متغیر (مثلا مبتنی بر ATR) - آرایه هم‌طول df

    خروجی: دیکشنری آمار + دیتافریم معاملات
    """
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    n = len(df)
    entries = np.asarray(entries, dtype=bool)

    trades = []
    i = 0
    busy_until = -1  # اندیس کندلی که تا آن معامله فعلی باز است

    signal_idx = np.where(entries)[0]
    for si in signal_idx:
        entry_bar = si + 1  # ورود در کندل بعد
        if entry_bar >= n:
            continue
        if not allow_overlap and entry_bar <= busy_until:
            continue

        entry_price = o[entry_bar]
        # اعمال اسپرد: خرید در ask (open+spread)، فروش در bid (open-spread)
        if direction == 'long':
            fill = entry_price + spread
            sl_d = sl_series[si] if sl_series is not None else sl_points
            tp_d = tp_series[si] if tp_series is not None else tp_points
            sl_price = fill - sl_d
            tp_price = fill + tp_d
        else:
            fill = entry_price - spread
            sl_d = sl_series[si] if sl_series is not None else sl_points
            tp_d = tp_series[si] if tp_series is not None else tp_points
            sl_price = fill + sl_d
            tp_price = fill - tp_d

        outcome = None
        exit_bar = None
        exit_price = None
        for j in range(entry_bar, min(entry_bar + max_hold, n)):
            hi, lo = h[j], l[j]
            if direction == 'long':
                hit_sl = lo <= sl_price
                hit_tp = hi >= tp_price
            else:
                hit_sl = hi >= sl_price
                hit_tp = lo <= tp_price
            if hit_sl and hit_tp:
                # ابهام: بدترین حالت = SL
                outcome = 'loss'; exit_bar = j; exit_price = sl_price; break
            elif hit_tp:
                outcome = 'win'; exit_bar = j; exit_price = tp_price; break
            elif hit_sl:
                outcome = 'loss'; exit_bar = j; exit_price = sl_price; break
        if outcome is None:
            # پایان بازه نگهداری -> بستن با close
            exit_bar = min(entry_bar + max_hold, n) - 1
            exit_price = c[exit_bar]
            if direction == 'long':
                pnl = exit_price - fill
            else:
                pnl = fill - exit_price
            outcome = 'win' if pnl > 0 else 'loss'
        else:
            if direction == 'long':
                pnl = exit_price - fill
            else:
                pnl = fill - exit_price

        busy_until = exit_bar
        trades.append({
            'signal_bar': si,
            'entry_bar': entry_bar,
            'exit_bar': exit_bar,
            'entry_price': fill,
            'exit_price': exit_price,
            'direction': direction,
            'outcome': outcome,
            'pnl': pnl,
            'bars_held': exit_bar - entry_bar,
        })

    tr = pd.DataFrame(trades)
    if len(tr) == 0:
        return {'n_trades': 0, 'win_rate': 0.0, 'total_pnl': 0.0,
                'avg_win': 0, 'avg_loss': 0, 'expectancy': 0}, tr

    wins = tr[tr['outcome'] == 'win']
    losses = tr[tr['outcome'] == 'loss']
    stats = {
        'n_trades': len(tr),
        'win_rate': len(wins) / len(tr) * 100,
        'total_pnl': tr['pnl'].sum(),
        'avg_win': wins['pnl'].mean() if len(wins) else 0,
        'avg_loss': losses['pnl'].mean() if len(losses) else 0,
        'expectancy': tr['pnl'].mean(),
        'avg_bars_held': tr['bars_held'].mean(),
    }
    return stats, tr


def summary_line(name, stats):
    return (f"{name}: trades={stats['n_trades']}, "
            f"win_rate={stats['win_rate']:.2f}%, "
            f"expectancy={stats['expectancy']:.3f}$, "
            f"total_pnl={stats['total_pnl']:.1f}$")
