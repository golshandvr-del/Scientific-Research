"""
جاروب پارامتری استراتژی ۲۰ (TTM Squeeze + Chandelier).
هدف: یافتن ناحیه‌ای که WR>60% و expectancy مثبت هم‌زمان برقرار باشد.

نکته کلیدی: Chandelier خالص → WR پایین (trend-following). برای بالا بردن WR
گزینه «TP سقف» (cap) را اضافه می‌کنیم که سود را زودتر قفل می‌کند؛ ولی طبق درس
پروژه مراقب «WinRate Trap» هستیم: WR و expectancy را با هم گزارش می‌کنیم و
فقط ترکیبی را قبول می‌کنیم که هر دو خوب باشند.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, atr, bollinger
from engine.backtest import load_data
from strategies.s20_squeeze_chandelier import build_signals


def backtest_chandelier_cap(df, entries, direction_series, atr_series,
                            ch_mult=3.0, init_sl_mult=1.5, tp_cap_mult=None,
                            be_trigger_mult=None, spread=0.20,
                            max_hold=400, allow_overlap=False):
    """
    مانند نسخه اصلی، اما با دو افزودنی اختیاری:
      tp_cap_mult    : اگر داده شود، یک TP سقف در فاصله tp_cap_mult*ATR گذاشته می‌شود
                       (قفل سود زودهنگام → WR بالاتر).
      be_trigger_mult: اگر داده شود، پس از رسیدن سود به این مضرب ATR، استاپ به
                       break-even (fill) منتقل می‌شود (کاهش ضرر → WR بالاتر).
    """
    o = df['open'].values; h = df['high'].values
    l = df['low'].values;  c = df['close'].values
    n = len(df)
    entries = np.asarray(entries, dtype=bool)
    dir_arr = np.asarray(direction_series)
    atr_arr = np.asarray(atr_series)

    trades = []
    busy_until = -1
    for si in np.where(entries)[0]:
        entry_bar = si + 1
        if entry_bar >= n: continue
        if not allow_overlap and entry_bar <= busy_until: continue
        d = dir_arr[si]; a = atr_arr[si]
        if not np.isfinite(a) or a <= 0: continue

        if d > 0:
            fill = o[entry_bar] + spread
            stop = fill - init_sl_mult * a
            extreme = h[entry_bar]
            tp = fill + tp_cap_mult * a if tp_cap_mult else None
        else:
            fill = o[entry_bar] - spread
            stop = fill + init_sl_mult * a
            extreme = l[entry_bar]
            tp = fill - tp_cap_mult * a if tp_cap_mult else None

        chand_dist = ch_mult * a
        be_done = False
        exit_bar = exit_price = None
        for j in range(entry_bar, min(entry_bar + max_hold, n)):
            hi, lo = h[j], l[j]
            if d > 0:
                if lo <= stop:
                    exit_bar = j; exit_price = stop; break
                if tp is not None and hi >= tp:
                    exit_bar = j; exit_price = tp; break
                if be_trigger_mult and not be_done and hi >= fill + be_trigger_mult*a:
                    stop = max(stop, fill); be_done = True
                if hi > extreme:
                    extreme = hi
                    ns = extreme - chand_dist
                    if ns > stop: stop = ns
            else:
                if hi >= stop:
                    exit_bar = j; exit_price = stop; break
                if tp is not None and lo <= tp:
                    exit_bar = j; exit_price = tp; break
                if be_trigger_mult and not be_done and lo <= fill - be_trigger_mult*a:
                    stop = min(stop, fill); be_done = True
                if lo < extreme:
                    extreme = lo
                    ns = extreme + chand_dist
                    if ns < stop: stop = ns
        if exit_bar is None:
            exit_bar = min(entry_bar + max_hold, n) - 1
            exit_price = c[exit_bar]

        pnl = (exit_price - fill) if d > 0 else (fill - exit_price)
        busy_until = exit_bar
        trades.append({'outcome': 'win' if pnl > 0 else 'loss', 'pnl': pnl,
                       'bars_held': exit_bar - entry_bar})

    tr = pd.DataFrame(trades)
    if len(tr) == 0:
        return {'n_trades':0,'win_rate':0,'expectancy':0,'total_pnl':0,'avg_bars_held':0}, tr
    wins = tr[tr['outcome']=='win']
    return {'n_trades':len(tr),'win_rate':len(wins)/len(tr)*100,
            'expectancy':tr['pnl'].mean(),'total_pnl':tr['pnl'].sum(),
            'avg_bars_held':tr['bars_held'].mean()}, tr


def main():
    df = load_data()
    n_days = (df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    a = atr(df, 14).values

    # سیگنال ثابت (baseline squeeze fire)، فقط مکانیزم خروج را جاروب می‌کنیم
    fire, direction = build_signals(df, min_squeeze_len=3)
    print(f"تعداد سیگنال fire: {fire.sum()}  (~{fire.sum()/n_days:.2f}/روز)\n")

    print("=== جاروب مکانیزم خروج (سیگنال ثابت) ===")
    print(f"{'exit-config':<45}{'n':>6}{'WR%':>8}{'exp$':>9}{'PnL$':>9}{'tpd':>7}")
    configs = [
        ("Chandelier x3.0 (خالص)", dict(ch_mult=3.0, init_sl_mult=1.5)),
        ("Chandelier x2.0", dict(ch_mult=2.0, init_sl_mult=1.5)),
        ("Chandelier x1.5", dict(ch_mult=1.5, init_sl_mult=1.5)),
        ("Chandelier x1.0 (تنگ)", dict(ch_mult=1.0, init_sl_mult=1.5)),
        ("Chand x3 + TPcap 1.0", dict(ch_mult=3.0, init_sl_mult=1.5, tp_cap_mult=1.0)),
        ("Chand x3 + TPcap 1.5", dict(ch_mult=3.0, init_sl_mult=1.5, tp_cap_mult=1.5)),
        ("Chand x3 + TPcap 2.0", dict(ch_mult=3.0, init_sl_mult=1.5, tp_cap_mult=2.0)),
        ("Chand x3 + BE@1.0", dict(ch_mult=3.0, init_sl_mult=1.5, be_trigger_mult=1.0)),
        ("Chand x3 + BE@0.5", dict(ch_mult=3.0, init_sl_mult=1.5, be_trigger_mult=0.5)),
        ("Chand x2 + TPcap1.0 + BE0.5", dict(ch_mult=2.0, init_sl_mult=1.5, tp_cap_mult=1.0, be_trigger_mult=0.5)),
        ("TPcap0.8 + SL2.0 (WR-max test)", dict(ch_mult=5.0, init_sl_mult=2.0, tp_cap_mult=0.8)),
        ("TPcap0.5 + SL2.5 (extreme WR)", dict(ch_mult=5.0, init_sl_mult=2.5, tp_cap_mult=0.5)),
    ]
    for name, kw in configs:
        st, _ = backtest_chandelier_cap(df, fire, direction, a, **kw)
        tpd = st['n_trades']/n_days
        print(f"{name:<45}{st['n_trades']:>6}{st['win_rate']:>8.2f}"
              f"{st['expectancy']:>9.3f}{st['total_pnl']:>9.1f}{tpd:>7.2f}")


if __name__ == '__main__':
    main()
