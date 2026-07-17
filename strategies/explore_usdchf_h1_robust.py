"""
explore_usdchf_h1_robust.py — آزمونِ استحکامِ لبهٔ USDCHF h=01 UTC Long (موتورِ نو)
================================================================================
> قانونِ شمارهٔ ۱: معیار فقط «سودِ خالصِ کلِ چهار ارز» است، نه WR.

اکتشافِ قبلی یک لبهٔ محکم داد: USDCHF, ورودِ Long در open ساعتِ 01 UTC،
IS=+6181$ / OOS=+8767$ (هر دو نیمه مثبت، WR≈61%). قبل از ساختِ استراتژیِ نهایی
باید استحکامش را از چند زاویه بسنجیم تا مطمئن شویم fluke نیست:
  1) حساسیت به SL/TP (grid) — آیا فقط یک نقطهٔ خوش‌شانس است یا یک ناحیهٔ پایدار؟
  2) حساسیت به max_hold.
  3) پایداری در چهار چارَکِ زمانی (نه فقط دو نیمه).
  4) اثرِ فیلترِ pullback (buy-the-dip) و فیلترِ روند.
همه forward-safe و با هزینهٔ کاملِ موتورِ نو.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scalp_engine import load_data, simulate_trades, run_capital, ASSETS
import warnings; warnings.filterwarnings('ignore')

ASSET = 'USDCHF'
EVAL_START = 24000
TARGET_HOUR = 1


def base_signal(df):
    n = len(df)
    hour = pd.to_datetime(df['time'], unit='s').dt.hour.values
    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True
    sig = np.zeros(n, dtype=bool)
    sig[:-1] = (hour[1:] == TARGET_HOUR) & (hour[:-1] != TARGET_HOUR)
    return sig & eval_mask


def evaluate(df, sig, sl, tp, max_hold, mask=None):
    n = len(df)
    longS = sig.copy()
    if mask is not None:
        longS = longS & mask
    shortS = np.zeros(n, bool)
    tr = simulate_trades(df, longS, shortS, sl, tp, ASSET, max_hold=max_hold,
                         allow_overlap=False)
    if len(tr) == 0:
        return None
    st, _ = run_capital(tr, ASSET, compounding=False)
    return st


def main():
    df = load_data(ASSETS[ASSET]['file'])
    n = len(df)
    sig = base_signal(df)
    print("=" * 90)
    print(f"  استحکامِ لبهٔ {ASSET} h={TARGET_HOUR:02d} UTC Long — موتورِ نو")
    print("=" * 90)

    # 1) grid SL/TP
    print("\n[1] حساسیت به SL/TP (max_hold=16):  netProfit$")
    print("       TP=8    TP=10   TP=12   TP=15   TP=20")
    for sl in (8, 10, 12, 15, 20):
        line = f"  SL={sl:2d} "
        for tp in (8, 10, 12, 15, 20):
            st = evaluate(df, sig, sl, tp, 16)
            line += f"{st['net_profit']:+7.0f} "
        print(line)

    # 2) max_hold
    print("\n[2] حساسیت به max_hold (SL=TP=12):")
    for mh in (8, 12, 16, 24, 32, 48):
        st = evaluate(df, sig, 12, 12, mh)
        print(f"  max_hold={mh:2d}: net={st['net_profit']:+7.0f}$  n={st['n_trades']}  "
              f"WR={st['win_rate']:.1f}%  PF={st['profit_factor']:.2f}  DD={st['max_dd_pct']:.1f}%")

    # 3) چهار چارَک (SL=TP=12, mh=16)
    print("\n[3] پایداری در چهار چارَکِ زمانی (SL=TP=12, mh=16):")
    bounds = np.linspace(EVAL_START, n, 5).astype(int)
    for q in range(4):
        mask = np.zeros(n, bool); mask[bounds[q]:bounds[q+1]] = True
        st = evaluate(df, sig, 12, 12, 16, mask)
        if st:
            print(f"  Q{q+1} [{bounds[q]}:{bounds[q+1]}]: net={st['net_profit']:+7.0f}$  "
                  f"n={st['n_trades']}  WR={st['win_rate']:.1f}%")

    # 4) فیلترِ pullback (buy-the-dip): close < close[k قبل]
    print("\n[4] اثرِ فیلترِ pullback (SL=TP=12, mh=16):")
    c = df['close'].values
    for k in (0, 2, 4, 8):
        if k == 0:
            mask = None; label = "بدون فیلتر"
        else:
            prior = np.zeros(n); prior[k:] = c[k:] - c[:-k]
            mask = prior < 0; label = f"dip {k} کندل"
        st = evaluate(df, sig, 12, 12, 16, mask)
        if st:
            print(f"  {label:14s}: net={st['net_profit']:+7.0f}$  n={st['n_trades']}  "
                  f"WR={st['win_rate']:.1f}%  PF={st['profit_factor']:.2f}")
    print("\n" + "=" * 90)


if __name__ == '__main__':
    main()
