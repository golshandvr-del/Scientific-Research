"""
استراتژی ۲۰: Volatility-Squeeze Breakout با خروج پویا (Chandelier Trailing Exit)
================================================================================
پاسخ به User Note. ترکیبی که هیچ‌کدام از ۱۹ استراتژی قبلی امتحان نکرده‌اند:

  سیگنال ورود : TTM Squeeze  (Bollinger Bands داخل Keltner Channel = فشردگی نوسان)
                که «آزاد می‌شود» (squeeze off) + جهت شکست بر پایه مومنتوم.
  خروج پویا   : Chandelier Exit — ATR trailing stop
                long : stop = highest_high(since entry) - mult*ATR
                short: stop = lowest_low(since entry)  + mult*ATR
                (به‌جای TP ثابت؛ سود را «می‌دواند» تا وقتی trailing لمس شود)

تفاوت با استراتژی‌های قبلی:
  - هیچ استراتژی قبلی TTM-Squeeze به‌عنوان تریگر نداشت (s10/s19 breakout بر پایه
    عبور از سقف N کندل بود، نه فشردگی نوسان BB-in-Keltner).
  - هیچ استراتژی قبلی خروج trailing نداشت؛ همه TP/SL ثابت داشتند. موتور مشترک
    engine/backtest.py هم فقط TP/SL ثابت را پشتیبانی می‌کند، لذا اینجا یک موتور
    بک‌تست اختصاصی با Chandelier trailing پیاده شده است (بدون look-ahead).

ارزیابی: WR (بردها = خروج با سود مثبت پس از هزینه)، expectancy، فرکانس (trades/day).
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, atr, bollinger
from engine.backtest import load_data


# ---------------------------------------------------------------------------
# اندیکاتورهای اختصاصی این استراتژی
# ---------------------------------------------------------------------------
def keltner(df, period=20, mult=1.5):
    """Keltner Channel: EMA(close) ± mult*ATR."""
    mid = ema(df['close'], period)
    a = atr(df, period)
    return mid - mult * a, mid, mid + mult * a


def ttm_squeeze(df, bb_period=20, bb_mult=2.0, kc_period=20, kc_mult=1.5):
    """
    Squeeze روشن (on) وقتی BB کاملاً داخل Keltner است:
        BB_upper < KC_upper  و  BB_lower > KC_lower
    خروجی: سری بولین squeeze_on.
    """
    bb_l, _, bb_u = bollinger(df['close'], bb_period, bb_mult)
    kc_l, _, kc_u = keltner(df, kc_period, kc_mult)
    squeeze_on = (bb_u < kc_u) & (bb_l > kc_l)
    return squeeze_on.fillna(False)


def ttm_momentum(df, period=20):
    """
    مومنتوم به سبک TTM: رگرسیون خطی close حول میانگینِ (میانه دان‌چیان + SMA).
    ما نسخه ساده و رایج آن را استفاده می‌کنیم:
        base = ((highest_high + lowest_low)/2 + SMA(close)) / 2
        mom  = خطی‌سازی (close - base) روی پنجره
    علامت mom جهت شکست را می‌دهد.
    """
    hh = df['high'].rolling(period).max()
    ll = df['low'].rolling(period).min()
    sma_c = df['close'].rolling(period).mean()
    base = ((hh + ll) / 2 + sma_c) / 2
    diff = df['close'] - base
    # صاف‌سازی با رگرسیون خطی روی پنجره (شیب‌محور مومنتوم)
    x = np.arange(period)
    xm = x.mean()
    denom = ((x - xm) ** 2).sum()
    def _lin(y):
        # مقدار برازش‌شده انتهای پنجره منهای میانگین ≈ مومنتوم TTM
        b = ((x - xm) * (y - y.mean())).sum() / denom
        a = y.mean() - b * xm
        return a + b * (period - 1) - y.mean()
    mom = diff.rolling(period).apply(_lin, raw=True)
    return mom


# ---------------------------------------------------------------------------
# موتور بک‌تست با Chandelier Trailing Exit (بدون look-ahead)
# ---------------------------------------------------------------------------
def backtest_chandelier(df, entries, direction_series, atr_series,
                        ch_mult=3.0, init_sl_mult=1.5, spread=0.20,
                        max_hold=400, allow_overlap=False):
    """
    entries          : بولین هم‌طول df؛ True = سیگنال روی این کندل (ورود در open بعدی)
    direction_series : +1 برای long، -1 برای short (هم‌طول df)
    atr_series       : مقدار ATR هر کندل (برای فاصله chandelier و SL اولیه)
    ch_mult          : ضریب ATR برای فاصله trailing stop
    init_sl_mult     : ضریب ATR برای استاپ اولیه (قبل از حرکت سود)
    منطق trailing (long):
        chand_stop = max(highest_high_since_entry) - ch_mult*ATR_entry
        stop نهایی = max(init_stop, chand_stop)   (فقط بالا می‌رود، هرگز پایین نمی‌آید)
    خروج فقط با لمس trailing stop یا پایان max_hold.
    """
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    n = len(df)
    entries = np.asarray(entries, dtype=bool)
    dir_arr = np.asarray(direction_series)
    atr_arr = np.asarray(atr_series)

    trades = []
    busy_until = -1
    for si in np.where(entries)[0]:
        entry_bar = si + 1
        if entry_bar >= n:
            continue
        if not allow_overlap and entry_bar <= busy_until:
            continue
        d = dir_arr[si]
        a = atr_arr[si]
        if not np.isfinite(a) or a <= 0:
            continue

        if d > 0:  # long
            fill = o[entry_bar] + spread
            stop = fill - init_sl_mult * a
            extreme = h[entry_bar]
        else:      # short
            fill = o[entry_bar] - spread
            stop = fill + init_sl_mult * a
            extreme = l[entry_bar]

        chand_dist = ch_mult * a
        exit_bar = None
        exit_price = None
        for j in range(entry_bar, min(entry_bar + max_hold, n)):
            hi, lo = h[j], l[j]
            if d > 0:
                # ابتدا بررسی لمس stop با low کندل جاری
                if lo <= stop:
                    exit_bar = j; exit_price = stop; break
                # به‌روزرسانی trailing با high کندل جاری
                if hi > extreme:
                    extreme = hi
                    new_stop = extreme - chand_dist
                    if new_stop > stop:
                        stop = new_stop
            else:
                if hi >= stop:
                    exit_bar = j; exit_price = stop; break
                if lo < extreme:
                    extreme = lo
                    new_stop = extreme + chand_dist
                    if new_stop < stop:
                        stop = new_stop
        if exit_bar is None:
            exit_bar = min(entry_bar + max_hold, n) - 1
            exit_price = c[exit_bar]

        pnl = (exit_price - fill) if d > 0 else (fill - exit_price)
        busy_until = exit_bar
        trades.append({
            'signal_bar': si, 'entry_bar': entry_bar, 'exit_bar': exit_bar,
            'entry_price': fill, 'exit_price': exit_price,
            'direction': 'long' if d > 0 else 'short',
            'outcome': 'win' if pnl > 0 else 'loss',
            'pnl': pnl, 'bars_held': exit_bar - entry_bar,
        })

    tr = pd.DataFrame(trades)
    if len(tr) == 0:
        return {'n_trades': 0, 'win_rate': 0, 'total_pnl': 0,
                'expectancy': 0, 'avg_win': 0, 'avg_loss': 0,
                'avg_bars_held': 0}, tr
    wins = tr[tr['outcome'] == 'win']
    losses = tr[tr['outcome'] == 'loss']
    stats = {
        'n_trades': len(tr),
        'win_rate': len(wins) / len(tr) * 100,
        'total_pnl': tr['pnl'].sum(),
        'expectancy': tr['pnl'].mean(),
        'avg_win': wins['pnl'].mean() if len(wins) else 0,
        'avg_loss': losses['pnl'].mean() if len(losses) else 0,
        'avg_bars_held': tr['bars_held'].mean(),
    }
    return stats, tr


# ---------------------------------------------------------------------------
# ساخت سیگنال استراتژی ۲۰
# ---------------------------------------------------------------------------
def build_signals(df, bb_period=20, bb_mult=2.0, kc_period=20, kc_mult=1.5,
                  mom_period=20, min_squeeze_len=3):
    """
    سیگنال ورود = لحظه‌ی 'آزادشدن squeeze' (fire):
        squeeze_on در کندل قبلی True بود و در این کندل False شد،
        و طول squeeze اخیر >= min_squeeze_len (فشردگی معنادار).
    جهت = علامت مومنتوم TTM در لحظه آزادشدن.
    """
    sq = ttm_squeeze(df, bb_period, bb_mult, kc_period, kc_mult).values
    mom = ttm_momentum(df, mom_period).values

    # طول squeeze پیوسته تا کندل قبل
    run = np.zeros(len(df), dtype=int)
    for i in range(1, len(df)):
        run[i] = run[i-1] + 1 if sq[i] else 0

    fire = np.zeros(len(df), dtype=bool)
    direction = np.zeros(len(df), dtype=int)
    for i in range(1, len(df)):
        if sq[i-1] and (not sq[i]):           # squeeze just fired
            if run[i-1] >= min_squeeze_len and np.isfinite(mom[i]):
                fire[i] = True
                direction[i] = 1 if mom[i] > 0 else -1
    return fire, direction


def evaluate(df, params, spread=0.20, label=""):
    a = atr(df, params.get('atr_period', 14))
    fire, direction = build_signals(
        df,
        bb_period=params.get('bb_period', 20),
        bb_mult=params.get('bb_mult', 2.0),
        kc_period=params.get('kc_period', 20),
        kc_mult=params.get('kc_mult', 1.5),
        mom_period=params.get('mom_period', 20),
        min_squeeze_len=params.get('min_squeeze_len', 3),
    )
    stats, tr = backtest_chandelier(
        df, fire, direction, a.values,
        ch_mult=params.get('ch_mult', 3.0),
        init_sl_mult=params.get('init_sl_mult', 1.5),
        spread=spread,
        max_hold=params.get('max_hold', 400),
        allow_overlap=False,
    )
    return stats, tr


if __name__ == '__main__':
    df = load_data()
    n_days = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days
    print(f"داده: {len(df)} کندل، ~{n_days} روز\n")

    base = dict(bb_period=20, bb_mult=2.0, kc_period=20, kc_mult=1.5,
                mom_period=20, min_squeeze_len=3, atr_period=14,
                ch_mult=3.0, init_sl_mult=1.5, max_hold=400)
    stats, tr = evaluate(df, base, label="baseline")
    tpd = stats['n_trades'] / n_days if n_days else 0
    print("=== Baseline (TTM Squeeze + Chandelier x3.0) ===")
    print(f"trades={stats['n_trades']}  WR={stats['win_rate']:.2f}%  "
          f"exp={stats['expectancy']:.3f}$  PnL={stats['total_pnl']:.1f}$  "
          f"tpd={tpd:.2f}  avg_hold={stats['avg_bars_held']:.0f} bars")
    if len(tr):
        print(f"avg_win={stats['avg_win']:.2f}$  avg_loss={stats['avg_loss']:.2f}$")
