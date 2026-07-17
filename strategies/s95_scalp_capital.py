# -*- coding: utf-8 -*-
"""
s95_scalp_capital.py — گرهِ سرمایه: سودِ خالصِ سرمایه‌محورِ منطقِ اسکالپِ نو در برابرِ S79
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر» است، نه WR.
> سودِ خالص = XAUUSD + EURUSD.
================================================================================

تصمیمِ نهاییِ بخشِ اسکالپ (User Note) را با «مدلِ سرمایه‌محور» (همان عینکِ L41/S67)
می‌سنجیم تا با رکوردِ پروژه هم‌مقیاس شود:

  A) S79 فعلیِ سایت: خروجِ TP=120/SL=50 ثابت (intrabar) — رکوردِ ثبت‌شده +۴٬۲۵۶$.
  B) منطقِ نوِ «هدفِ پنهان» (کشفِ s94): خروج روی close با آستانهٔ پنهانِ
     TP=120pip / SL=80pip — بدونِ نمایشِ TP/SL به کاربر.

هر دو روی همان ورودهای S79 (trend-pullback long) و همان موتورِ paper broker،
سپس run_capital (ریسکِ ۱٪ روی ۱۰k$، کامپاند). چون sl پنهانِ B بزرگ‌تر است
(۸۰ در برابرِ ۵۰)، لاتِ B کوچک‌تر می‌شود؛ باید ببینیم آیا سودِ pipِ بیشترِ B این
را جبران می‌کند یا نه — این تنها معیارِ تصمیم است (سودِ خالص).
"""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from strategies.s91_scalp_signal_exit import paper_broker, stats, DATA
from strategies.s92_scalp_exit_variants import build_entries_long_pullback
from strategies.s94_scalp_hidden_target import make_hidden_exit


def add_sl_pip(trades, sl_pip):
    """افزودنِ ستونِ sl_pip (ثابت) که run_capital برای تعیینِ لات لازم دارد."""
    trades = trades.copy()
    trades['sl_pip'] = float(sl_pip)
    return trades


def cap_report(df, entries, exit_fn, sl_pip_for_sizing, label, cat_sl=500.0):
    tr = paper_broker(df, entries, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288)
    tr = add_sl_pip(tr, sl_pip_for_sizing)
    st, eq = se.run_capital(tr, 'XAUUSD', initial_capital=10000.0,
                            risk_pct=1.0, compounding=True)
    print(f"\n── {label} ──")
    print(f"   n={st['n_trades']}  net_profit=${st['net_profit']:+,.2f}  "
          f"return={st['return_pct']:+.1f}%  PF={st['profit_factor']:.2f}")
    print(f"   WR={st['win_rate']:.1f}%  MaxDD={st['max_dd_pct']:.1f}%  "
          f"Sharpe={st['sharpe']:.2f}  avg_lot={st['avg_lot']:.3f}  ruined={st['ruined']}")
    return st


def cap_halves(df, entries, exit_fn, sl_pip, label, cat_sl=500.0):
    n = len(df); half = n // 2
    e1 = [(i, s) for (i, s) in entries if i < half - 1]
    df1 = df.iloc[:half].reset_index(drop=True)
    e2 = [(i - half, s) for (i, s) in entries if i >= half]
    df2 = df.iloc[half:].reset_index(drop=True)
    tr1 = add_sl_pip(paper_broker(df1, e1, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288), sl_pip)
    tr2 = add_sl_pip(paper_broker(df2, e2, exit_fn, catastrophic_sl_pip=cat_sl, max_hold=288), sl_pip)
    s1, _ = se.run_capital(tr1, 'XAUUSD', initial_capital=10000.0, risk_pct=1.0, compounding=True)
    s2, _ = se.run_capital(tr2, 'XAUUSD', initial_capital=10000.0, risk_pct=1.0, compounding=True)
    print(f"   [both-halves] نیمهٔ۱ net=${s1['net_profit']:+,.2f} | "
          f"نیمهٔ۲ net=${s2['net_profit']:+,.2f} | "
          f"هر دو مثبت: {'✅' if s1['net_profit']>0 and s2['net_profit']>0 else '❌'}")
    return s1, s2


def main():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    entries = build_entries_long_pullback(df)

    print("=" * 80)
    print("s95 — سودِ خالصِ سرمایه‌محورِ اسکالپ (ریسکِ ۱٪ روی ۱۰٬۰۰۰$، کامپاند)")
    print("=" * 80)
    print(f"داده: {len(df)} کندلِ M5   ورودهای S79: {len(entries)}")

    # A) S79 فعلی: TP=120/SL=50 (خروج روی close برای هم‌سنجی با سایت)
    exit_A = make_hidden_exit(120, 50, use_trend_break=False)
    stA = cap_report(df, entries, exit_A, 50, "A) S79 فعلی — TP=120/SL=50")
    cap_halves(df, entries, exit_A, 50, "A")

    # B) منطقِ نو: هدفِ پنهان TP=120/SL=80
    exit_B = make_hidden_exit(120, 80, use_trend_break=False)
    stB = cap_report(df, entries, exit_B, 80, "B) هدفِ پنهانِ نو — TP=120/SL=80 (بدونِ نمایش)")
    cap_halves(df, entries, exit_B, 80, "B")

    print("\n" + "=" * 80)
    delta = stB['net_profit'] - stA['net_profit']
    print(f"اختلافِ سودِ خالصِ لایهٔ اسکالپ: ${delta:+,.2f}  "
          f"({'B بهتر ✅' if delta > 0 else 'A بهتر'})")
    print(f"  A (فعلی): ${stA['net_profit']:+,.2f}")
    print(f"  B (نو)  : ${stB['net_profit']:+,.2f}")
    print("=" * 80)
    print("یادداشت: این عدد لایهٔ M5 است. رکوردِ کلِ پروژه = XAUUSD(M15+M5+M30) + EURUSD.")
    print("اگر B > A، لایهٔ اسکالپِ سایت به منطقِ B ارتقا می‌یابد و سودِ خالصِ کل بالا می‌رود.")


if __name__ == '__main__':
    main()
