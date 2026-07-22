# -*- coding: utf-8 -*-
"""
S167 — RSI-21 Mean-Reversion (اقتباس از کتاب/پایان‌نامهٔ Subarkah 2009)

قانونِ شمارهٔ ۱ پروژه: تابعِ هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR
هدف نیست، اما WR هر لایه باید حداقل ۴۰٪ باشد.

فرضیهٔ ازپیش‌تعریف‌شده (از منبع):
منبع (پایان‌نامهٔ اندونزیایی، منبعِ Telegram `042114161_Full.pdf`) ادعا می‌کند RSI با
دورهٔ ۲۱ (به‌جای ۱۴ استانداردِ Wilder) سیگنالِ کاذبِ کمتری می‌سازد. قاعدهٔ کلاسیک:
  • RSI < LO (اشباعِ فروش) ⇒ آماده برای Long (بازگشت به میانگین).
  • RSI > HI (اشباعِ خرید) ⇒ آماده برای Short.
ما نسخهٔ «cross-back» را می‌آزماییم (کم‌نویزتر و بدونِ look-ahead):
  • Long وقتی RSI از زیرِ LO به بالای LO برگردد (خروج از oversold).
  • Short وقتی RSI از بالای HI به زیرِ HI برگردد (خروج از overbought).
سیگنال پس از بسته‌شدنِ کندل فعال و ورود روی open کندلِ بعدی است (shift-safe).

اعتبار (forward-safe + ضدِ overfit):
  - همهٔ اندیکاتورها فقط از گذشته (shift(1) روی سیگنال).
  - گیتِ پذیرش: net>0 در کلِ دوره + هر دو نیمه (H1,H2) net>0 + WR≥40٪ + n≥30.
  - گریدِ آستانه/SL/TP گزارش می‌شود تا plateau دیده شود (نه بیشینهٔ منفرد).
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind

OUT = os.path.join(ROOT, "results", "_s167_rsi21_mean_reversion.json")
CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0
RSI_PERIOD = 21

ASSET_FILES = {
    "XAUUSD": os.path.join(ROOT, "data", "XAUUSD_M15.csv"),
    "EURUSD": os.path.join(ROOT, "data", "EURUSD_M15.csv"),
}

# مشخصاتِ واقعیِ حساب (User Note): طلا اسپرد 3.3pip/comm0؛ یورو 1pip/comm0.
se.ASSETS["EURUSD"].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load_data(path):
    df = pd.read_csv(path)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def build_signals(df, lo, hi):
    """cross-back RSI-21 mean-reversion، shift-safe."""
    rsi = ind.rsi(df["close"], RSI_PERIOD)
    rsi_prev = rsi.shift(1)
    # خروج از oversold ⇒ long ؛ خروج از overbought ⇒ short (روی کندلِ بسته‌شده)
    long_raw = (rsi_prev < lo) & (rsi >= lo)
    short_raw = (rsi_prev > hi) & (rsi <= hi)
    # ورود روی کندلِ بعدی (shift 1) تا look-ahead نداشته باشیم
    long_sig = long_raw.shift(1).fillna(False).to_numpy()
    short_sig = short_raw.shift(1).fillna(False).to_numpy()
    return long_sig, short_sig


def evaluate(df, asset, side, lo, hi, sl_pip, tp_pip, max_hold):
    long_sig, short_sig = build_signals(df, lo, hi)
    if side == "long":
        short_sig = np.zeros_like(short_sig, dtype=bool)
    else:
        long_sig = np.zeros_like(long_sig, dtype=bool)

    trades = se.simulate_trades(
        df, long_sig, short_sig, sl_pip, tp_pip, asset,
        max_hold=max_hold, allow_overlap=False,
    )
    if trades is None or len(trades) < 30:
        return None
    stats, _, per_trade = se.run_capital_pertrade(
        trades, asset, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=False,
    )
    n = len(per_trade)
    half = n // 2
    net_h1 = per_trade["pnl_dollar"].iloc[:half].sum()
    net_h2 = per_trade["pnl_dollar"].iloc[half:].sum()
    wr = (per_trade["pnl_dollar"] > 0).mean() * 100.0
    gross_win = per_trade.loc[per_trade["pnl_dollar"] > 0, "pnl_dollar"].sum()
    gross_loss = -per_trade.loc[per_trade["pnl_dollar"] < 0, "pnl_dollar"].sum()
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    net = per_trade["pnl_dollar"].sum()
    accepted = bool(net > 0 and net_h1 > 0 and net_h2 > 0 and wr >= WR_FLOOR and n >= 30)
    return {
        "asset": asset, "side": side, "lo": lo, "hi": hi,
        "sl": sl_pip, "tp": tp_pip, "max_hold": max_hold,
        "net": float(net), "net_h1": float(net_h1), "net_h2": float(net_h2),
        "wr": float(wr), "pf": float(pf) if pf != float("inf") else 999.0,
        "n": int(n), "accepted": accepted,
    }


def main():
    thresholds = [(30, 70), (25, 75), (20, 80)]
    # SL/TP بر حسب pip؛ برای طلا 1pip=0.1$/oz. گرید متعارف mean-reversion.
    grids = {
        "XAUUSD": [(150, 150), (150, 225), (200, 200), (250, 375), (300, 300)],
        "EURUSD": [(15, 15), (15, 22), (20, 20), (25, 37), (30, 30)],
    }
    max_holds = [16, 32]

    results = {}
    for asset, path in ASSET_FILES.items():
        df = load_data(path)
        variants = []
        for side in ("long", "short"):
            for (lo, hi) in thresholds:
                for (sl, tp) in grids[asset]:
                    for mh in max_holds:
                        r = evaluate(df, asset, side, lo, hi, sl, tp, mh)
                        if r is not None:
                            variants.append(r)
        acc = [v for v in variants if v["accepted"]]
        pos = [v for v in variants if v["net"] > 0]
        variants.sort(key=lambda x: x["net"], reverse=True)
        results[asset] = {
            "rows": len(df), "variants": variants,
            "n_accepted": len(acc), "n_net_positive": len(pos),
        }
        print(f"\n===== {asset} ({len(df)} rows) =====")
        print(f"  {len(variants)} variants; accepted={len(acc)}; net_positive={len(pos)}")
        for v in variants[:8]:
            tag = "ACCEPT" if v["accepted"] else "reject"
            print(f"    {tag} {v['side']:5s} LO{v['lo']}/HI{v['hi']} "
                  f"SL{v['sl']}/TP{v['tp']} mh{v['max_hold']:2d}  "
                  f"net=${v['net']:9.0f}  WR={v['wr']:5.1f}%  n={v['n']:5d}  PF={v['pf']:.2f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_acc = sum(r["n_accepted"] for r in results.values())
    print(f"\n=== خلاصه: مجموع واریانتِ پذیرفته‌شده = {total_acc} ===")
    if total_acc == 0:
        print("هیچ لایه‌ای گیتِ سخت‌گیرانه را پاس نکرد ⇒ یافتهٔ منفی؛ رکورد بدون تغییر.")


if __name__ == "__main__":
    main()
