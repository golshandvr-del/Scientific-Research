"""
explore_geometric_patterns.py — اکتشافِ الگوهای هندسی/شکلی (User Note: «دو قله»)
================================================================================
قانونِ شمارهٔ ۱ پروژه: هدف **فقط سودِ خالصِ بیشتر** — نه WR. سودِ خالص = XAUUSD+EURUSD.

انگیزه (User Note): تریدر روی چارت «دو قله» (double top) کشید و ادامهٔ روند را حدس زد.
سوال علمی: آیا الگوهای هندسیِ تکرارشونده (double top/bottom، higher-high/lower-low
sequences) در XAUUSD لبهٔ واقعی دارند؟ کجا؟

روش: از swing pivots (engine/structure.py) استفاده می‌کنیم و بازدهِ آتیِ شرطی را
پس از تشکیلِ هر الگوی هندسی می‌سنجیم. بدونِ نشتِ آینده: pivot فقط با کندل‌های
تأییدشده (right bars گذشته) ساخته می‌شود، و سیگنال روی کندلِ تأیید صادر می‌شود.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

HORIZONS = [4, 8, 16, 32]


def confirmed_pivots(df, left=4, right=4):
    """
    نقاطِ swing high/low که با `right` کندلِ بعد تأیید شده‌اند.
    برای forward-safe بودن: pivot در کندلِ i، تنها در زمانِ i+right «معلوم» می‌شود.
    خروجی: آرایه‌های اندیس و قیمتِ pivotها + آرایهٔ confirm_bar (زمانِ معلوم شدن).
    """
    h = df['high'].values; l = df['low'].values
    n = len(df)
    ph, pl = [], []   # (idx, price, confirm_bar)
    for i in range(left, n - right):
        win_h = h[i-left:i+right+1]
        win_l = l[i-left:i+right+1]
        if h[i] == win_h.max() and (win_h == h[i]).sum() == 1:
            ph.append((i, h[i], i + right))
        if l[i] == win_l.min() and (win_l == l[i]).sum() == 1:
            pl.append((i, l[i], i + right))
    return ph, pl


def eval_signal(df, signal_bars, direction, tag):
    """بازدهِ آتیِ شرطی روی کندلِ سیگنال (confirm_bar)."""
    c = df['close'].values; n = len(df)
    signal_bars = np.array(sorted(set(int(b) for b in signal_bars if b < n - max(HORIZONS))))
    if len(signal_bars) < 30:
        print(f"  {tag}: n={len(signal_bars)} <30 (نادر) — رد")
        return
    print(f"  {tag}: n={len(signal_bars)}  (جهت {'↑' if direction>0 else '↓'})")
    for k in HORIZONS:
        fut = (c[signal_bars + k] / c[signal_bars] - 1.0) * 10000.0 * direction
        base_all = (c[k:] / c[:n-k] - 1.0) * 10000.0 * direction
        mean = fut.mean(); base = base_all.mean()
        t = mean / (fut.std(ddof=1) / np.sqrt(len(fut))) if fut.std() > 0 else 0
        wr = (fut > 0).mean() * 100
        flag = '  <<< لبه' if abs(t) >= 3 and (mean - base) > 0 else ''
        print(f"      k={k:>2}: mean={mean:>7.2f}bps base={base:>7.2f} "
              f"lift={mean-base:>7.2f} t={t:>6.2f} WR={wr:.1f}%{flag}")


def analyze(path, asset):
    print("\n" + "=" * 78)
    print(f"  {asset}  ({path})")
    print("=" * 78)
    df = load_data(path)
    df['atr'] = ind.atr(df, 14)
    adx_val, _, _ = ind.adx(df, 14)
    df['adx'] = adx_val
    ph, pl = confirmed_pivots(df, 4, 4)
    print(f"  pivots: high={len(ph)}  low={len(pl)}")
    atr = df['atr'].values
    c = df['close'].values

    # --------- Double Top: دو قلهٔ هم‌ارتفاع، سیگنال نزولی ---------
    dt_sig = []
    for a in range(len(ph) - 1):
        i1, p1, _ = ph[a]; i2, p2, cb2 = ph[a+1]
        gap = i2 - i1
        if not (8 <= gap <= 60):    # فاصلهٔ منطقیِ دو قله
            continue
        tol = 0.5 * atr[i2] if atr[i2] > 0 else 0
        if abs(p1 - p2) <= tol:      # هم‌ارتفاع (در حدِ نصفِ ATR)
            dt_sig.append(cb2)       # سیگنال روی کندلِ تأییدِ قلهٔ دوم
    eval_signal(df, dt_sig, -1, "Double-Top (نزولی)")

    # --------- Double Bottom: دو کفِ هم‌ارتفاع، سیگنال صعودی ---------
    db_sig = []
    for a in range(len(pl) - 1):
        i1, p1, _ = pl[a]; i2, p2, cb2 = pl[a+1]
        gap = i2 - i1
        if not (8 <= gap <= 60):
            continue
        tol = 0.5 * atr[i2] if atr[i2] > 0 else 0
        if abs(p1 - p2) <= tol:
            db_sig.append(cb2)
    eval_signal(df, db_sig, +1, "Double-Bottom (صعودی)")

    # --------- Higher-High sequence (ادامهٔ روندِ صعودی) ---------
    hh_sig = []
    for a in range(1, len(ph)):
        i_prev, p_prev, _ = ph[a-1]; i_cur, p_cur, cb = ph[a]
        if p_cur > p_prev and (i_cur - i_prev) <= 60:
            hh_sig.append(cb)
    eval_signal(df, hh_sig, +1, "Higher-High seq (ادامهٔ صعود)")

    # --------- Lower-Low sequence (ادامهٔ روندِ نزولی) ---------
    ll_sig = []
    for a in range(1, len(pl)):
        i_prev, p_prev, _ = pl[a-1]; i_cur, p_cur, cb = pl[a]
        if p_cur < p_prev and (i_cur - i_prev) <= 60:
            ll_sig.append(cb)
    eval_signal(df, ll_sig, -1, "Lower-Low seq (ادامهٔ نزول)")


if __name__ == '__main__':
    analyze('data/XAUUSD_M15.csv', 'XAUUSD M15')
    analyze('data/XAUUSD_H1.csv', 'XAUUSD H1')
