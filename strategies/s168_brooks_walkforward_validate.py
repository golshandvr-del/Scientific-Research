# -*- coding: utf-8 -*-
"""
S168 — آزمونِ پایداریِ walk-forward برای تنها لایهٔ accepted:
XAUUSD long، High-2 bar-counting، EMA20/50، SL300/TP450، max_hold=32.

معیار: net>0 در هر ۴ پنجرهٔ زمانیِ مساوی و WR≥۴۰٪. اگر حتی یک پنجره منفی ⇒ رد.
هشدارِ پیشینی: در بک‌تستِ کامل h1=+$293 و h2=+$3,844 (تمرکزِ سود در نیمهٔ دوم).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from s168_brooks_high2_low2 import count_high2_low2  # استفادهٔ مجدد از همان شمارنده

DATA = os.path.join(ROOT, "data", "XAUUSD_M15.csv")
ASSET = "XAUUSD"
CAPITAL = 10_000.0
RISK_PCT = 1.0
EMA_FAST, EMA_SLOW = 20, 50
SL_PIP, TP_PIP, MAX_HOLD = 300, 450, 32


def load_data():
    df = pd.read_csv(DATA)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def run_window(df):
    long_evt, _ = count_high2_low2(df, EMA_FAST, EMA_SLOW)
    long_sig = pd.Series(long_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    short_sig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(
        df, long_sig, short_sig, SL_PIP, TP_PIP, ASSET,
        max_hold=MAX_HOLD, allow_overlap=False,
    )
    if trades is None or len(trades) < 10:
        return None
    stats, _, per_trade = se.run_capital_pertrade(
        trades, ASSET, df=df, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=False,
    )
    return {
        "n": len(per_trade), "net": float(stats["net_profit"]),
        "wr": float(stats["win_rate"]), "pf": float(stats["profit_factor"]),
    }


def main():
    df = load_data()
    n = len(df)
    print(f"XAUUSD Brooks High-2 long — walk-forward پایداری (کلِ {n} کندل)")
    print(f"لایه: long ema{EMA_FAST}/{EMA_SLOW} SL{SL_PIP}/TP{TP_PIP} mh{MAX_HOLD}\n")

    full = run_window(df)
    print(f"[FULL]  net=${full['net']:8.0f}  WR={full['wr']:5.1f}%  n={full['n']:5d}  PF={full['pf']:.2f}")

    edges = np.linspace(0, n, 5, dtype=int)
    all_pos = True; all_wr_ok = True
    print("\nپنجره‌های زمانیِ مساوی:")
    for i in range(4):
        seg = df.iloc[edges[i]:edges[i + 1]].reset_index(drop=True)
        r = run_window(seg)
        if r is None:
            print(f"  W{i+1}: معاملهٔ کافی نیست"); all_pos = False; continue
        flag = "OK " if r["net"] > 0 else "NEG"
        wrflag = "" if r["wr"] >= 40 else "  ⚠WR<40"
        print(f"  W{i+1} [{flag}] net=${r['net']:8.0f}  WR={r['wr']:5.1f}%  n={r['n']:4d}  PF={r['pf']:.2f}{wrflag}")
        if r["net"] <= 0: all_pos = False
        if r["wr"] < 40: all_wr_ok = False

    print("\n=== حکمِ پایداری ===")
    if all_pos and all_wr_ok:
        print("✅ پایدار: net در هر ۴ پنجره مثبت و WR≥40 ⇒ لبه پذیرفته می‌شود.")
    else:
        print("⛔ ناپایدار: دستِ‌کم یک پنجره منفی/WR<40 ⇒ لبه رد می‌شود.")


if __name__ == "__main__":
    main()
