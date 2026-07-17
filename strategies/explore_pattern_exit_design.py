"""
explore_pattern_exit_design.py — طراحیِ خروجِ بهینه برای لبه‌های الگوییِ کشف‌شده
================================================================================
قانونِ #۱: فقط سودِ خالص. سودِ خالص = XAUUSD + EURUSD.

هدف: نسخهٔ اولِ S74 با TP/SL بزرگِ ATR ruin شد چون لبهٔ الگوها کوچک است (~1-4 bps)
و در افقِ بزرگ (k=16-32) ظاهر می‌شود، نه در نوسانِ فوریِ TP/SL. اینجا برای هر لبهٔ
اثبات‌شده، طراحیِ خروج را با موتورِ سرمایه‌محور اسکن می‌کنیم تا ببینیم کدام ترکیبِ
(hold, TP-mult, SL-mult) سودِ خالصِ مثبت و پایدار (both-halves) می‌دهد.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')


def ctx(df):
    df = df.copy()
    df['atr'] = ind.atr(df, 14)
    a, _, _ = ind.adx(df, 14); df['adx'] = a
    df['ema50'] = ind.ema(df['close'], 50)
    return df


def confirmed_pivots(df, left=4, right=4):
    h = df['high'].values; l = df['low'].values; n = len(df)
    ph, pl = [], []
    for i in range(left, n - right):
        wh = h[i-left:i+right+1]; wl = l[i-left:i+right+1]
        if h[i] == wh.max() and (wh == h[i]).sum() == 1:
            ph.append((i, h[i], i + right))
        if l[i] == wl.min() and (wl == l[i]).sum() == 1:
            pl.append((i, l[i], i + right))
    return ph, pl


def double_top_signals(df, ph, atr):
    n = len(df); e = np.zeros(n, dtype=bool)
    for a in range(len(ph) - 1):
        i1, p1, _ = ph[a]; i2, p2, cb2 = ph[a+1]
        if not (8 <= i2 - i1 <= 60) or cb2 >= n:
            continue
        if abs(p1 - p2) <= 0.5 * atr[i2]:
            e[cb2] = True
    return e


def higher_high_signals(df, ph, close, ema50):
    n = len(df); e = np.zeros(n, dtype=bool)
    for a in range(1, len(ph)):
        ip, pp, _ = ph[a-1]; ic, pc, cb = ph[a]
        if cb >= n:
            continue
        if pc > pp and (ic - ip) <= 60 and not np.isnan(ema50[cb]) and close[cb] > ema50[cb]:
            e[cb] = True
    return e


def test_exit(df, entries, direction, tp_mult, sl_mult, hold):
    atr = df['atr'].values
    stats, tr = run_backtest(df, entries, None, None, direction, spread=0.20,
                             max_hold=hold, allow_overlap=False,
                             sl_series=sl_mult*atr, tp_series=tp_mult*atr)
    if len(tr) < 30:
        return None
    sl_dist = sl_mult * atr[tr['signal_bar'].values]
    cap, _ = run_capital_backtest(tr, sl_dist, initial_capital=10_000.0,
                                  risk_pct=1.0, commission_per_lot=7.0, compounding=False)
    # دو-نیمه
    mid = len(df)//2
    halves = []
    for m in [(tr['signal_bar']<mid), (tr['signal_bar']>=mid)]:
        h = tr[m]
        if len(h):
            sd = sl_mult*atr[h['signal_bar'].values]
            hc,_ = run_capital_backtest(h.reset_index(drop=True), sd, initial_capital=10_000.0,
                                        risk_pct=1.0, commission_per_lot=7.0, compounding=False)
            halves.append(hc['net_profit'])
        else:
            halves.append(0)
    return cap, halves


def scan(df, entries, direction, name):
    print(f"\n  ===== {name} (n_sig={entries.sum()}, جهت {direction}) =====")
    print(f"  {'tp':>4}{'sl':>5}{'hold':>6}{'netP':>9}{'WR%':>7}{'PF':>6}{'DD%':>7}{'H1':>8}{'H2':>8}")
    best = None
    for tp_mult in [0.5, 0.8, 1.0, 1.5, 2.0, 3.0]:
        for sl_mult in [1.0, 1.5, 2.0]:
            for hold in [8, 16, 32, 48]:
                r = test_exit(df, entries, direction, tp_mult, sl_mult, hold)
                if r is None:
                    continue
                cap, halves = r
                both = '✓' if halves[0] > 0 and halves[1] > 0 else ' '
                if abs(cap['net_profit']) < 1e7:  # فیلترِ ruin عددی
                    line = (f"  {tp_mult:>4}{sl_mult:>5}{hold:>6}{cap['net_profit']:>+9.0f}"
                            f"{cap['win_rate']:>7.1f}{cap['profit_factor']:>6.2f}"
                            f"{cap['max_dd_pct']:>7.1f}{halves[0]:>+8.0f}{halves[1]:>+8.0f} {both}")
                    # فقط ترکیب‌های both-halves-positive و سودده را چاپ کن
                    if halves[0] > 0 and halves[1] > 0 and cap['net_profit'] > 0:
                        print(line)
                        if best is None or cap['net_profit'] > best[0]['net_profit']:
                            best = (cap, tp_mult, sl_mult, hold, halves)
    if best:
        cap, tp, sl, hold, halves = best
        print(f"  ★ بهترین both-halves: tp={tp} sl={sl} hold={hold} "
              f"netP={cap['net_profit']:+.0f}$ WR={cap['win_rate']:.1f}% PF={cap['profit_factor']:.2f}")
    else:
        print("  هیچ ترکیبِ both-halves-positive سوددهی یافت نشد.")
    return best


def main():
    df = load_data('data/XAUUSD_M15.csv'); df = ctx(df)
    ph, pl = confirmed_pivots(df)
    atr = df['atr'].values; close = df['close'].values; ema50 = df['ema50'].values
    dt = double_top_signals(df, ph, atr)
    hh = higher_high_signals(df, ph, close, ema50)
    print("=" * 78)
    print("  طراحیِ خروجِ بهینه برای لبه‌های الگویی (XAUUSD M15)")
    print("=" * 78)
    scan(df, dt, 'short', 'Double-Top SHORT')
    scan(df, hh, 'long', 'Higher-High LONG')


if __name__ == '__main__':
    main()
