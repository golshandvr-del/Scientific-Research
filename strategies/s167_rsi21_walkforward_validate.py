# -*- coding: utf-8 -*-
"""
S167 — آزمونِ پایداریِ walk-forward برای بهترین لایهٔ RSI-21 روی XAUUSD.

هدف: تعیینِ اینکه لبهٔ +$1,337 (long, LO25/HI75, SL150/TP225, mh16) واقعی و پایدار
است یا artifactِ یک بازهٔ خاص. معیارِ پذیرشِ سخت‌گیرانهٔ پروژه:
  - net کل > 0 ✅ (از S167 مشخص است)
  - net در **هر ۴ پنجرهٔ زمانیِ مساوی** > 0  ← آزمونِ اصلیِ اینجا
  - WR هر پنجره ≥ 40٪
اگر حتی یک پنجره منفی شود، لبه ناپایدار است و رد می‌شود (درسِ L: کالیبراسیون فقط
لبه‌های ذاتاً پایدار را نجات می‌دهد، نه مرزی‌ها).
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind

DATA = os.path.join(ROOT, "data", "XAUUSD_M15.csv")
ASSET = "XAUUSD"
CAPITAL = 10_000.0
RISK_PCT = 1.0
RSI_PERIOD = 21
LO, HI = 25, 75
SL_PIP, TP_PIP, MAX_HOLD = 150, 225, 16


def load_data():
    df = pd.read_csv(DATA)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def build_signals(df):
    rsi = ind.rsi(df["close"], RSI_PERIOD)
    rsi_prev = rsi.shift(1)
    long_raw = (rsi_prev < LO) & (rsi >= LO)
    long_sig = long_raw.shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    short_sig = np.zeros(len(df), dtype=bool)
    return long_sig, short_sig


def run_window(df):
    long_sig, short_sig = build_signals(df)
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
        "n": len(per_trade),
        "net": float(stats["net_profit"]),
        "wr": float(stats["win_rate"]),
        "pf": float(stats["profit_factor"]),
    }


def main():
    df = load_data()
    n = len(df)
    print(f"XAUUSD RSI-21 MR long — walk-forward پایداری (کلِ {n} کندل)")
    print(f"لایه: long LO{LO}/HI{HI} SL{SL_PIP}/TP{TP_PIP} mh{MAX_HOLD}\n")

    # کل
    full = run_window(df)
    print(f"[FULL]  net=${full['net']:8.0f}  WR={full['wr']:5.1f}%  n={full['n']:4d}  PF={full['pf']:.2f}")

    # ۴ پنجرهٔ زمانیِ مساوی
    edges = np.linspace(0, n, 5, dtype=int)
    all_pos = True
    all_wr_ok = True
    print("\nپنجره‌های زمانیِ مساوی (walk-forward):")
    for i in range(4):
        seg = df.iloc[edges[i]:edges[i + 1]].reset_index(drop=True)
        r = run_window(seg)
        if r is None:
            print(f"  W{i+1}: معاملهٔ کافی نیست")
            all_pos = False
            continue
        flag = "OK " if r["net"] > 0 else "NEG"
        wrflag = "" if r["wr"] >= 40 else "  ⚠WR<40"
        print(f"  W{i+1} [{flag}] net=${r['net']:8.0f}  WR={r['wr']:5.1f}%  n={r['n']:4d}  PF={r['pf']:.2f}{wrflag}")
        if r["net"] <= 0:
            all_pos = False
        if r["wr"] < 40:
            all_wr_ok = False

    print("\n=== حکمِ پایداری ===")
    if all_pos and all_wr_ok:
        print("✅ پایدار: net در هر ۴ پنجره مثبت و WR≥40 ⇒ لبه پذیرفته می‌شود.")
    else:
        print("⛔ ناپایدار: دستِ‌کم یک پنجره منفی/WR<40 ⇒ لبه رد می‌شود (artifact احتمالی).")


if __name__ == "__main__":
    main()
