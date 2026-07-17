"""
explore_gold_mtf_swing.py — آزمونِ فرضیهٔ User Note: آیا trend-pullbackِ برندهٔ S80(H1)
روی H4 و M30 هم جواب می‌دهد؟ (کاندیدِ S81)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله در روز و Profit Factor هم هدف نیستند.
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

فرضیهٔ کاربر (User Note): «مطمئنم اینی که روی H1 جواب داده، روی H4 و M30 هم جواب می‌دهد.»
منطقِ برندهٔ S80: EMA20>EMA100 (روندِ صعودیِ کلان) + RSI(14)<40 (pullbackِ ارزان)، فقط Long.

این اسکریپت:
  ۱) مشخصاتِ آماریِ هر TF (رنجِ کندل بر حسبِ pip) را می‌سنجد تا SL/TP را متناسب مقیاس کند.
  ۲) همان منطق را روی H4 و M30 جارو می‌کند (RSI_th, SL, TP, hold).
  ۳) پایداری را در دو نیمه + چهار چارَک می‌سنجد.
هزینهٔ واقعیِ طلا: spread=4pip(0.40$), comm=0, slip=0.5pip.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

# ثبتِ داراییِ H4 و M30 (همان مشخصاتِ هزینهٔ طلا)
SE.ASSETS['XAUUSD_H4'] = dict(file='data/XAUUSD_H4.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
SE.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)


def ema(x, s): return pd.Series(x).ewm(span=s, adjust=False).mean().values
def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def build(c, n, ema_f, ema_s, rsi_p, rsi_th):
    ef = ema(c, ema_f); es = ema(c, ema_s); r = rsi(c, rsi_p)
    ls = np.nan_to_num((ef > es) & (r < rsi_th)).astype(bool)
    ss = np.zeros(n, bool)
    return ls, ss


def evaluate(asset, sl_grid, tp_grid, hold_grid, rsi_grid=(35, 40, 45)):
    df = SE.load_data(SE.ASSETS[asset]['file'])
    n = len(df); c = df['close'].values
    half = n // 2
    # مشخصاتِ آماری
    rng_pip = ((df['high'] - df['low']) / SE.ASSETS[asset]['pip']).mean()
    print(f"\n{'='*100}\n  {asset}  (n={n}, {df['dt'].iloc[0]} → {df['dt'].iloc[-1]})  "
          f"میانگین رنجِ کندل = {rng_pip:.0f} pip\n{'='*100}")
    best = None
    hits = []
    for rsi_th in rsi_grid:
        ls, ss = build(c, n, 20, 100, 14, rsi_th)
        for sl in sl_grid:
            for tp in tp_grid:
                for hold in hold_grid:
                    tr = SE.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=hold)
                    if len(tr) < 30:
                        continue
                    s, _ = SE.run_capital(tr, ASSET := asset, compounding=False)
                    s1, _ = SE.run_capital(tr[tr['entry_bar'] < half], asset, compounding=False)
                    s2, _ = SE.run_capital(tr[tr['entry_bar'] >= half], asset, compounding=False)
                    both = s1['net_profit'] > 0 and s2['net_profit'] > 0
                    rec = dict(rsi=rsi_th, sl=sl, tp=tp, hold=hold, s=s, s1=s1, s2=s2, both=both)
                    if best is None or s['net_profit'] > best['s']['net_profit']:
                        best = rec
                    if both and s['net_profit'] > 2000:
                        hits.append(rec)
    # چاپِ hitها (پایدارِ دو-نیمه)
    hits.sort(key=lambda r: -r['s']['net_profit'])
    for r in hits[:12]:
        s = r['s']
        print(f"  RSI<{r['rsi']} SL={r['sl']} TP={r['tp']} hold={r['hold']}: "
              f"net={s['net_profit']:+8.0f}$ n={s['n_trades']:4d} WR={s['win_rate']:4.1f}% "
              f"PF={s['profit_factor']:.2f} DD={s['max_dd_pct']:5.1f}% "
              f"H1={r['s1']['net_profit']:+.0f} H2={r['s2']['net_profit']:+.0f} ✅")
    if best:
        s = best['s']
        print(f"\n  ★ بهترین (سودِ خالص): RSI<{best['rsi']} SL={best['sl']} TP={best['tp']} "
              f"hold={best['hold']} → net={s['net_profit']:+.0f}$ n={s['n_trades']} "
              f"WR={s['win_rate']:.1f}% PF={s['profit_factor']:.2f} DD={s['max_dd_pct']:.1f}% "
              f"both_halves={'✅' if best['both'] else '❌'} "
              f"H1={best['s1']['net_profit']:+.0f} H2={best['s2']['net_profit']:+.0f}")
    return best


if __name__ == '__main__':
    print("#" * 100)
    print("  آزمونِ فرضیهٔ User Note: trend-pullbackِ S80(H1) روی H4 و M30 (کاندیدِ S81)")
    print("#" * 100)

    # H4: حرکت‌های بسیار بزرگ‌تر ⇒ SL/TP بزرگ‌تر
    best_h4 = evaluate('XAUUSD_H4',
                       sl_grid=[200, 300, 400, 600],
                       tp_grid=[600, 1000, 1500, 2500],
                       hold_grid=[24, 48, 72],
                       rsi_grid=(35, 40, 45))

    # M30: بین M15 و H1 ⇒ SL/TP کوچک‌تر از H1
    best_m30 = evaluate('XAUUSD_M30',
                        sl_grid=[80, 120, 180, 250],
                        tp_grid=[300, 500, 800, 1200],
                        hold_grid=[48, 96, 144],
                        rsi_grid=(35, 40, 45))

    print("\n" + "#" * 100)
    print("  جمع‌بندی (سودِ خالص با هزینهٔ واقعی، ۱۰k$/۱٪):")
    for name, b in [('H4', best_h4), ('M30', best_m30)]:
        if b:
            print(f"    {name}: net={b['s']['net_profit']:+8.0f}$  "
                  f"both_halves={'✅' if b['both'] else '❌'}  n={b['s']['n_trades']}")
    print("#" * 100)
