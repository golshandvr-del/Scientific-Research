# -*- coding: utf-8 -*-
"""
S168 — آزمونِ لبهٔ مستقل: آیا High-2 روی سیگنال‌های *خارج از* پنجره‌های زمان-محورِ
موجود هم به‌تنهایی سودده است؟

منطق: بهترین واریانتِ accepted طلا (long, ema20/50, SL300/TP450, mh32) را برمی‌داریم
و سیگنال‌هایش را به دو گروه می‌شکنیم:
  • IN  = سیگنال‌هایی که در پنجره‌های زمان-محورِ موجود می‌افتند (Overnight/ToM/Mid/EoM/Monday)
  • OUT = سیگنال‌های خارج از همهٔ آن پنجره‌ها (۴۳.۸٪ مستقل طبقِ overlap_check)
هر گروه را جداگانه بک‌تست می‌کنیم.

حکم:
  اگر گروهِ OUT به‌تنهایی net>0 و WR≥۴۰٪ ⇒ لبهٔ ساختاریِ High-2 واقعاً مستقل است و
  صرفاً بازتولیدِ لایه‌های زمان-محور نیست ⇒ ارزشِ افزودن دارد.
  اگر گروهِ OUT ضررده باشد ⇒ سودِ لایه عمدتاً از همپوشانی با لایه‌های موجود می‌آید ⇒
  لبهٔ مستقل نیست.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from engine import scalp_engine as se
from s168_brooks_high2_low2 import count_high2_low2, load_data

DATA = os.path.join(ROOT, "data", "XAUUSD_M15.csv")
CAPITAL = 10_000.0
RISK_PCT = 1.0

# بهترین واریانتِ accepted
EMA_FAST, EMA_SLOW = 20, 50
SL, TP, MH = 300, 450, 32


def build_time_windows(df):
    """ماسکِ بولی: True اگر کندل در یکی از پنجره‌های زمان-محورِ موجود باشد."""
    dt = df["dt"]
    hour = dt.dt.hour
    dow = dt.dt.dayofweek
    dom = dt.dt.day
    ym = dt.dt.year * 100 + dt.dt.month
    tdays = pd.DataFrame({"dt": dt, "ym": ym})
    tdays["date"] = dt.dt.normalize()
    days = tdays.drop_duplicates("date").reset_index(drop=True)
    days["rank"] = days.groupby("ym").cumcount() + 1
    days["cnt"] = days.groupby("ym")["date"].transform("count")
    days["from_end"] = days["rank"] - days["cnt"] - 1
    m = dict(zip(days["date"], days["from_end"]))
    from_end = dt.dt.normalize().map(m)

    in_win = (
        hour.isin([22, 23])
        | (dom <= 3)
        | (dom.between(13, 17))
        | (from_end.between(-8, -6))
        | (dow == 0)
    )
    return in_win.to_numpy()


def run_group(df, long_sig, asset="XAUUSD"):
    short_sig = np.zeros_like(long_sig, dtype=bool)
    trades = se.simulate_trades(
        df, long_sig, short_sig, SL, TP, asset,
        max_hold=MH, allow_overlap=False,
    )
    if trades is None or len(trades) < 10:
        return None
    stats, _, per_trade = se.run_capital_pertrade(
        trades, asset, df=df, initial_capital=CAPITAL, risk_pct=RISK_PCT,
        compounding=False,
    )
    return {
        "net": float(stats["net_profit"]),
        "wr": float(stats["win_rate"]),
        "pf": float(stats["profit_factor"]) if stats["profit_factor"] != float("inf") else 999.0,
        "n": int(len(per_trade)),
    }


def main():
    df = load_data(DATA)
    long_evt, _ = count_high2_low2(df, EMA_FAST, EMA_SLOW)
    in_win = build_time_windows(df)

    # سیگنالِ خام روی کندلِ رویداد؛ سپس تقسیم به IN/OUT بر اساسِ همان کندل
    long_all = pd.Series(long_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    # ماسکِ پنجره را هم یک کندل shift می‌کنیم تا با سیگنالِ ورودی هم‌تراز شود
    in_win_sh = pd.Series(in_win).shift(1).fillna(False).infer_objects(copy=False).to_numpy()

    long_in = long_all & in_win_sh
    long_out = long_all & (~in_win_sh)

    print("=" * 62)
    print("S168 — آزمونِ لبهٔ مستقل (High-2 long, ema20/50, SL300/TP450, mh32)")
    print("=" * 62)
    print(f"کلِ سیگنال‌های ورودی: {int(long_all.sum())}")
    print(f"  IN  (داخلِ پنجره‌های زمان-محور): {int(long_in.sum())}")
    print(f"  OUT (مستقل، خارج از پنجره‌ها):   {int(long_out.sum())}")
    print("-" * 62)

    r_all = run_group(df, long_all)
    r_in = run_group(df, long_in)
    r_out = run_group(df, long_out)

    def show(tag, r):
        if r is None:
            print(f"  {tag:5s}: n<10 — نامعتبر")
            return
        print(f"  {tag:5s}: net=${r['net']:8.0f}  WR={r['wr']:5.1f}%  "
              f"n={r['n']:5d}  PF={r['pf']:.2f}")

    show("ALL", r_all)
    show("IN", r_in)
    show("OUT", r_out)
    print("-" * 62)

    # حکم
    if r_out and r_out["net"] > 0 and r_out["wr"] >= 40.0:
        print("✅ حکم: گروهِ OUT به‌تنهایی net>0 و WR≥۴۰٪ ⇒ لبهٔ ساختاریِ High-2 مستقل")
        print("   است و صرفاً بازتولیدِ لایه‌های زمان-محور نیست ⇒ ارزشِ افزودن دارد.")
    else:
        onet = r_out["net"] if r_out else 0.0
        owr = r_out["wr"] if r_out else 0.0
        print(f"⛔ حکم: گروهِ OUT مستقلاً لبه ندارد (net=${onet:.0f}, WR={owr:.1f}%)")
        print("   ⇒ سودِ لایه عمدتاً از همپوشانی می‌آید؛ لبهٔ مستقلِ کافی نیست.")


if __name__ == "__main__":
    main()
