"""
جاروب فیلترهای کیفیت سیگنال برای استراتژی ۲۰ (TTM Squeeze fire).
هدف: بالا بردن WR بدون خراب‌کردن expectancy — با انتخابِ فقط شکست‌های باکیفیت.

فیلترها:
  - قدرت مومنتوم (|mom| بالای صدک X)  → شکست قوی‌تر
  - هم‌راستایی با روند EMA200          → ادامه‌دار بودن
  - ADX (قدرت روند)
  - ساعت معاملاتی پرقدرت (لندن/نیویورک)
  - طول squeeze (فشردگی طولانی‌تر = انفجار بزرگ‌تر)
هر فیلتر با خروج متوازن (Chandelier x3 + TP cap تطبیقی) سنجیده می‌شود؛ WR و exp
هر دو گزارش می‌شوند تا از WinRate-Trap پرهیز شود.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import ema, atr, bollinger, adx
from engine.backtest import load_data
from strategies.s20_squeeze_chandelier import ttm_squeeze, ttm_momentum
from strategies.s20b_sweep import backtest_chandelier_cap


def build_signals_filtered(df, min_squeeze_len=3, mom_period=20,
                           mom_pct=None, trend_align=False, adx_min=None,
                           hours=None):
    sq = ttm_squeeze(df).values
    mom = ttm_momentum(df, mom_period).values
    n = len(df)

    run = np.zeros(n, dtype=int)
    for i in range(1, n):
        run[i] = run[i-1]+1 if sq[i] else 0

    ema200 = ema(df['close'], 200).values
    close = df['close'].values
    adx_v = adx(df, 14)[0].values if adx_min is not None else None
    hour = df['dt'].dt.hour.values if hours is not None else None
    # آستانه صدک قدرت مومنتوم روی مقادیر متناهی
    mom_abs = np.abs(mom)
    thr = np.nanpercentile(mom_abs[np.isfinite(mom_abs)], mom_pct) if mom_pct else None

    fire = np.zeros(n, dtype=bool)
    direction = np.zeros(n, dtype=int)
    for i in range(1, n):
        if not (sq[i-1] and not sq[i]):
            continue
        if run[i-1] < min_squeeze_len:
            continue
        m = mom[i]
        if not np.isfinite(m):
            continue
        d = 1 if m > 0 else -1
        if thr is not None and abs(m) < thr:
            continue
        if trend_align:
            if d > 0 and not (close[i] > ema200[i]): continue
            if d < 0 and not (close[i] < ema200[i]): continue
        if adx_min is not None and not (np.isfinite(adx_v[i]) and adx_v[i] >= adx_min):
            continue
        if hours is not None and hour[i] not in hours:
            continue
        fire[i] = True
        direction[i] = d
    return fire, direction


def run(df, a, n_days, name, sig_kw, exit_kw):
    fire, direction = build_signals_filtered(df, **sig_kw)
    st, _ = backtest_chandelier_cap(df, fire, direction, a, **exit_kw)
    tpd = st['n_trades']/n_days
    print(f"{name:<48}{st['n_trades']:>6}{st['win_rate']:>8.2f}"
          f"{st['expectancy']:>9.3f}{st['total_pnl']:>9.1f}{tpd:>7.2f}")
    return st


def main():
    df = load_data()
    n_days = (df['dt'].iloc[-1]-df['dt'].iloc[0]).days
    a = atr(df, 14).values
    LONDON_NY = set(range(7,17))  # UTC؛ لندن+نیویورک

    exit_bal = dict(ch_mult=3.0, init_sl_mult=1.5)                 # سودآور خالص
    exit_wr  = dict(ch_mult=3.0, init_sl_mult=1.2, tp_cap_mult=1.2, be_trigger_mult=0.6)

    print(f"{'config':<48}{'n':>6}{'WR%':>8}{'exp$':>9}{'PnL$':>9}{'tpd':>7}")
    print("--- گروه A: خروج سودآور خالص (Chandelier x3) + فیلترها ---")
    run(df, a, n_days, "A0 بدون فیلتر", {}, exit_bal)
    run(df, a, n_days, "A1 mom>صدک70", dict(mom_pct=70), exit_bal)
    run(df, a, n_days, "A2 mom>صدک85", dict(mom_pct=85), exit_bal)
    run(df, a, n_days, "A3 trend-align (EMA200)", dict(trend_align=True), exit_bal)
    run(df, a, n_days, "A4 ADX>20", dict(adx_min=20), exit_bal)
    run(df, a, n_days, "A5 ساعت لندن+NY", dict(hours=LONDON_NY), exit_bal)
    run(df, a, n_days, "A6 mom85+trend+ADX20+ساعت", dict(mom_pct=85, trend_align=True, adx_min=20, hours=LONDON_NY), exit_bal)
    run(df, a, n_days, "A7 squeeze_len>=8 + trend", dict(min_squeeze_len=8, trend_align=True), exit_bal)

    print("--- گروه B: خروج WR-محور (TPcap1.2+BE0.6) + فیلترها ---")
    run(df, a, n_days, "B0 بدون فیلتر", {}, exit_wr)
    run(df, a, n_days, "B1 trend-align", dict(trend_align=True), exit_wr)
    run(df, a, n_days, "B2 mom85+trend", dict(mom_pct=85, trend_align=True), exit_wr)
    run(df, a, n_days, "B3 mom85+trend+ADX20+ساعت", dict(mom_pct=85, trend_align=True, adx_min=20, hours=LONDON_NY), exit_wr)


if __name__ == '__main__':
    main()
