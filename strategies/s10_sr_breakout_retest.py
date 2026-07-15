"""
استراتژی ۱۰: Support/Resistance Breakout-Retest (Price Action خالص)
====================================================================
این اولین استراتژی پروژه بر پایه‌ی «اکشن قیمت» کلاسیک است — دقیقاً همان کاری که
تریدرهای واقعی می‌کنند (و در User Note کاربر مطرح شد): کشیدن سطوح حمایت/مقاومت،
انتظار برای شکست (breakout)، و ورود در بازگشت به سطح (retest).

منطق ورود LONG (نمونه؛ short قرینه):
1. یک سطح مقاومت فعال R وجود دارد (از pivot-high تأییدشده).
2. قیمت آن را می‌شکند: close یک کندل > R به‌اندازه‌ی حداقل `break_buf` (بر حسب ATR).
3. سپس قیمت به سطح شکسته‌شده بازمی‌گردد (retest): low یک کندل بعدی به R نزدیک
   می‌شود (فاصله < `retest_tol`×ATR) و کندل صعودی بسته می‌شود (close>open) →
   نشانه‌ی حمایت‌گرفتن از سطح شکسته‌شده.
4. ورود LONG در open کندل بعد. SL زیر سطح، TP بر اساس RR.

تمام تشخیص‌ها فقط با داده‌ی تا کندل جاری انجام می‌شود (no look-ahead)؛ سطوح هم
با pivotهای تأییدشده (right کندل تأخیر) ساخته شده‌اند.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from numba import njit
from backtest import load_data, run_backtest, summary_line
import indicators as ind
import structure as st


@njit(cache=True)
def _signals(open_, high, low, close, atr_v,
             res, sup, break_buf, retest_tol, wait_max):
    """
    تولید سیگنال breakout-retest.
    خروجی: long_sig, short_sig  (بولین هم‌طول)
    منطق state-machine برای هر سطح:
      - وقتی close از مقاومت با بافر عبور کرد -> وارد حالت "منتظر retest صعودی"
      - در پنجره wait_max کندل، اگر low به سطح شکسته‌شده نزدیک شد و کندل صعودی بست
        -> سیگنال long
    قرینه برای short با شکست حمایت.
    """
    n = len(close)
    long_sig = np.zeros(n, dtype=np.bool_)
    short_sig = np.zeros(n, dtype=np.bool_)

    # حالت انتظار برای long
    waiting_long = False
    broken_res = 0.0
    wait_since_l = 0
    # حالت انتظار برای short
    waiting_short = False
    broken_sup = 0.0
    wait_since_s = 0

    for i in range(1, n):
        a = atr_v[i]
        if np.isnan(a) or a <= 0:
            continue

        # --- تشخیص شکست مقاومت (شروع انتظار long) ---
        r = res[i-1]  # مقاومت فعال تا کندل قبل
        if not np.isnan(r):
            if close[i] > r + break_buf * a and close[i-1] <= r + break_buf * a:
                waiting_long = True
                broken_res = r
                wait_since_l = 0
                # شکست مقاومت، حالت short را باطل می‌کند
                waiting_short = False

        # --- تشخیص شکست حمایت (شروع انتظار short) ---
        s = sup[i-1]
        if not np.isnan(s):
            if close[i] < s - break_buf * a and close[i-1] >= s - break_buf * a:
                waiting_short = True
                broken_sup = s
                wait_since_s = 0
                waiting_long = False

        # --- بررسی retest برای long ---
        if waiting_long:
            wait_since_l += 1
            # قیمت باید هنوز بالای سطح باشد (شکست معتبر بماند)
            if close[i] < broken_res - break_buf * a:
                waiting_long = False  # شکست کاذب (fakeout)
            else:
                # retest: low به سطح شکسته‌شده نزدیک شود + کندل صعودی
                near = low[i] <= broken_res + retest_tol * a
                bullish = close[i] > open_[i]
                if near and bullish and close[i] > broken_res:
                    long_sig[i] = True
                    waiting_long = False
            if wait_since_l > wait_max:
                waiting_long = False

        # --- بررسی retest برای short ---
        if waiting_short:
            wait_since_s += 1
            if close[i] > broken_sup + break_buf * a:
                waiting_short = False
            else:
                near = high[i] >= broken_sup - retest_tol * a
                bearish = close[i] < open_[i]
                if near and bearish and close[i] < broken_sup:
                    short_sig[i] = True
                    waiting_short = False
            if wait_since_s > wait_max:
                waiting_short = False

    return long_sig, short_sig


def build_signals(df, left=6, right=6, tol=0.0008, expiry=1500,
                  break_buf=0.25, retest_tol=0.5, wait_max=20):
    piv = st.pivots(df, left=left, right=right)
    sr = st.sr_levels(df, piv, tol=tol, expiry=expiry)
    atr = ind.atr(df, 14)
    ls, ss = _signals(
        df['open'].values.astype(np.float64),
        df['high'].values.astype(np.float64),
        df['low'].values.astype(np.float64),
        df['close'].values.astype(np.float64),
        atr.values.astype(np.float64),
        sr['resistance'].values.astype(np.float64),
        sr['support'].values.astype(np.float64),
        break_buf, retest_tol, wait_max)
    return ls, ss, atr


def evaluate(df, ls, ss, atr, tp_mult, sl_mult, spread=0.20, max_hold=96):
    atr_v = atr.values
    res = {}
    for name, sig, direction in [('LONG', ls, 'long'), ('SHORT', ss, 'short')]:
        stats, tr = run_backtest(
            df, sig, sl_points=None, tp_points=None, direction=direction,
            spread=spread, max_hold=max_hold, allow_overlap=False,
            sl_series=atr_v * sl_mult, tp_series=atr_v * tp_mult)
        res[name] = (stats, tr)
    return res


if __name__ == '__main__':
    df = load_data()
    print(f"داده: {len(df)} کندل\n")

    # نسخه پایه: RR متعادل تا edge خام را ببینیم
    print("=== S10 Breakout-Retest — جاروب اولیه پارامترها (RR=1:1.5) ===")
    for (l, r, bb, rt, wm) in [(6,6,0.25,0.5,20), (8,8,0.3,0.6,24), (5,5,0.2,0.5,16)]:
        ls, ss, atr = build_signals(df, left=l, right=r, break_buf=bb,
                                    retest_tol=rt, wait_max=wm)
        print(f"\n[left={l} right={r} buf={bb} retest_tol={rt} wait={wm}]  "
              f"long_sig={ls.sum()} short_sig={ss.sum()}")
        for tp, sl in [(1.5, 1.0), (1.0, 1.0), (1.5, 1.5)]:
            res = evaluate(df, ls, ss, atr, tp, sl)
            for name in ['LONG', 'SHORT']:
                s = res[name][0]
                if s['n_trades'] > 0:
                    be = sl/(tp+sl)*100
                    print(f"  TP{tp}/SL{sl} (BE={be:.0f}%) {name}: "
                          f"n={s['n_trades']}, WR={s['win_rate']:.2f}%, "
                          f"exp={s['expectancy']:.3f}$, PnL={s['total_pnl']:.0f}$")
