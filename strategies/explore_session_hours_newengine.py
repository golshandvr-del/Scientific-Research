"""
explore_session_hours_newengine.py — اکتشافِ ساعتِ سشن روی موتورِ نو (۴ ارز)
================================================================================
> قانونِ شمارهٔ ۱: معیار فقط «سودِ خالصِ کلِ چهار ارز» است، نه WR.

پرسشِ اکتشافی (نه استراتژیِ نهایی): با موتورِ نو (هزینهٔ واقعی) کدام ساعتِ ورود
(open آن ساعت UTC) در کدام ارز، برای long و برای short، لبهٔ سودده دارد؟
  • این فقط نقشه‌برداری است تا استراتژیِ نهایی روی لبه‌های واقعی ساخته شود.
  • forward-safe: سیگنال روی کندلِ قبل، ورود در open کندلِ ساعتِ هدف.
  • نیمهٔ اول داده = کشف (IS)، نیمهٔ دوم = تأیید (OOS) تا از overfit ساعت جلوگیری شود.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
from scalp_engine import load_data, simulate_trades, run_capital, ASSETS
import warnings; warnings.filterwarnings('ignore')

EVAL_START = 24000
SL_TP = 12.0
MAX_HOLD = 16


def hour_signal(df, target_hour):
    """سیگنال روی کندلی که کندلِ بعدش ساعتِ target_hour است (ورود در open آن ساعت)."""
    n = len(df)
    hour = pd.to_datetime(df['time'], unit='s').dt.hour.values
    eval_mask = np.zeros(n, dtype=bool); eval_mask[EVAL_START:] = True
    sig = np.zeros(n, dtype=bool)
    sig[:-1] = (hour[1:] == target_hour) & (hour[:-1] != target_hour)
    return sig & eval_mask


def net_for(df, asset, sig, direction, mask):
    n = len(df)
    longS = sig & mask if direction == 'long' else np.zeros(n, bool)
    shortS = sig & mask if direction == 'short' else np.zeros(n, bool)
    tr = simulate_trades(df, longS, shortS, SL_TP, SL_TP, asset,
                         max_hold=MAX_HOLD, allow_overlap=False)
    if len(tr) == 0:
        return 0.0, 0, 0.0
    st, _ = run_capital(tr, asset, compounding=False)
    return st['net_profit'], st['n_trades'], st['win_rate']


def main():
    print("=" * 92)
    print("  اکتشافِ ساعتِ سشن روی موتورِ نو — لبه‌های سودده (IS نیمهٔ اول / OOS نیمهٔ دوم)")
    print("=" * 92)
    for asset in ['XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF']:
        df = load_data(ASSETS[asset]['file'])
        n = len(df)
        mid = (EVAL_START + n) // 2
        is_mask = np.zeros(n, bool); is_mask[EVAL_START:mid] = True
        oos_mask = np.zeros(n, bool); oos_mask[mid:] = True
        print(f"\n--- {asset} ---")
        rows = []
        for hh in range(24):
            sig = hour_signal(df, hh)
            for d in ('long', 'short'):
                is_net, is_n, is_wr = net_for(df, asset, sig, d, is_mask)
                if is_n < 40:  # نیاز به نمونهٔ کافی
                    continue
                oos_net, oos_n, oos_wr = net_for(df, asset, sig, d, oos_mask)
                # فقط لبه‌هایی که در هر دو نیمه مثبت‌اند (پایداری)
                if is_net > 0 and oos_net > 0:
                    rows.append((hh, d, is_net, oos_net, is_n, oos_n, oos_wr))
        rows.sort(key=lambda r: -(r[2] + r[3]))
        if not rows:
            print("   هیچ لبهٔ دو-نیمه-مثبتی یافت نشد.")
        for hh, d, isn, oosn, isc, oosc, wr in rows[:6]:
            print(f"   h={hh:02d} {d:5s} | IS={isn:+7.0f}$ (n={isc}) | OOS={oosn:+7.0f}$ "
                  f"(n={oosc}, WR={wr:.0f}%) | جمع={isn+oosn:+7.0f}$")
    print("\n" + "=" * 92)


if __name__ == '__main__':
    main()
