"""
explore_eurusd_short_design.py — طراحیِ لبهٔ Short سشنیِ EURUSD (ساعت‌های ۲۲/۱۳ UTC)
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است. تعریف = XAUUSD + EURUSD.

کشفِ اکتشاف: ساعت‌های ۲۲ و ۱۳ UTC یک drift نزولیِ پایدار (هر ۴ چارَک منفی) دارند.
این مستقل از S73 (Long ساعتِ ۰) است. اینجا با موتورِ واقعی (هزینهٔ واقعیِ EURUSD:
spread=1.5pip, comm=0) بهترین طراحیِ SL/TP/hold و فیلترها را جارو می‌کنیم.

هدف: پیدا کردنِ یک همسایگیِ پایدار (نه یک نقطهٔ تنها) که هر دو نیمه مثبت باشد.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

# هزینهٔ واقعیِ EURUSD طبقِ README به‌روزرسانی‌شده: spread=1.5pip, comm=0
SE.ASSETS['EURUSD'] = dict(file='data/EURUSD_M15.csv', pip=0.0001, contract=100_000.0,
                           pip_value=10.0, spread_pip=1.5, comm=0.0, slip_pip=0.3)
ASSET = 'EURUSD'

df = SE.load_data(SE.ASSETS[ASSET]['file'])
df['hour'] = df['dt'].dt.hour
n = len(df)
hour = df['hour'].values

def build_short(hours, pullup_filter=False, pullup_bars=4):
    """Short در ساعت‌های داده‌شده. اختیاری: فیلترِ 'sell-the-rally' (۴ کندلِ قبل صعودی)."""
    c = df['close'].values
    short_sig = np.isin(hour, hours)
    if pullup_filter:
        move = np.zeros(n)
        for i in range(pullup_bars, n):
            move[i] = c[i] - c[i - pullup_bars]
        short_sig = short_sig & (move > 0)  # فقط اگر قبلش بالا رفته (فروش در اوج)
    long_sig = np.zeros(n, bool)
    return long_sig, short_sig

def evaluate(hours, sl, tp, hold, pullup=False):
    ls, ss = build_short(hours, pullup_filter=pullup)
    tr = SE.simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=hold)
    if len(tr) == 0:
        return None
    s, _ = SE.run_capital(tr, ASSET, compounding=False)
    half = n // 2
    tr1 = tr[tr['entry_bar'] < half]; tr2 = tr[tr['entry_bar'] >= half]
    s1, _ = SE.run_capital(tr1, ASSET, compounding=False)
    s2, _ = SE.run_capital(tr2, ASSET, compounding=False)
    return s, s1, s2

print("=" * 100)
print("  EURUSD Short سشنی — جاروی طراحی (هزینهٔ واقعی: spread=1.5pip, comm=0)")
print("=" * 100)

print("\n--- گامِ ۱: کدام ترکیبِ ساعت؟ (SL=12, TP=12, hold=6) ---")
for hours in [[22], [13], [22, 13], [22, 13, 12], [22, 13, 12, 18]]:
    res = evaluate(hours, 12, 12, 6)
    if res:
        s, s1, s2 = res
        bh = "✅هردونیمه+" if s1['net_profit'] > 0 and s2['net_profit'] > 0 else "⚠️"
        print(f"  ساعت‌ها={str(hours):18} net={s['net_profit']:+7.0f}$  n={s['n_trades']:4d}  "
              f"WR={s['win_rate']:4.1f}%  PF={s['profit_factor']:.2f}  H1={s1['net_profit']:+.0f} H2={s2['net_profit']:+.0f} {bh}")

print("\n--- گامِ ۲: فیلترِ sell-the-rally (ساعت‌ها=[22,13]) ---")
for pu in [False, True]:
    res = evaluate([22, 13], 12, 12, 6, pullup=pu)
    if res:
        s, s1, s2 = res
        bh = "✅هردونیمه+" if s1['net_profit'] > 0 and s2['net_profit'] > 0 else "⚠️"
        print(f"  pullup={pu}: net={s['net_profit']:+7.0f}$  n={s['n_trades']:4d}  WR={s['win_rate']:4.1f}%  "
              f"PF={s['profit_factor']:.2f}  H1={s1['net_profit']:+.0f} H2={s2['net_profit']:+.0f} {bh}")

print("\n--- گامِ ۳: جاروی SL/TP/hold (ساعت‌ها=[22,13], بدون فیلتر) ---")
best = None
for sl in [10, 12, 14, 16]:
    for tp in [8, 10, 12, 14, 16, 20]:
        for hold in [4, 6, 8, 10]:
            res = evaluate([22, 13], sl, tp, hold)
            if res is None: continue
            s, s1, s2 = res
            both = s1['net_profit'] > 0 and s2['net_profit'] > 0
            if best is None or (s['net_profit'] > best[0]['net_profit']):
                best = (s, s1, s2, sl, tp, hold)
            if both and s['net_profit'] > 3000:
                print(f"  SL={sl:2d} TP={tp:2d} hold={hold:2d}: net={s['net_profit']:+7.0f}$  "
                      f"n={s['n_trades']:4d}  WR={s['win_rate']:4.1f}%  PF={s['profit_factor']:.2f}  "
                      f"H1={s1['net_profit']:+.0f} H2={s2['net_profit']:+.0f} ✅")

if best:
    s, s1, s2, sl, tp, hold = best
    print(f"\n  ★ بهترین (بیشترین net): SL={sl} TP={tp} hold={hold} → net={s['net_profit']:+.0f}$ "
          f"n={s['n_trades']} WR={s['win_rate']:.1f}% PF={s['profit_factor']:.2f} "
          f"H1={s1['net_profit']:+.0f} H2={s2['net_profit']:+.0f}")
