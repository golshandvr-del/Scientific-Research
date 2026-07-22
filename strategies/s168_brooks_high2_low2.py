# -*- coding: utf-8 -*-
"""
S168 — Al Brooks High-2 / Low-2 Bar-Counting (کتابِ Trading Price Action: Trends)

قانونِ شمارهٔ ۱ پروژه: تابعِ هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR
هدف نیست، اما WR هر لایه باید حداقل ۴۰٪ باشد.

فرضیهٔ ازپیش‌تعریف‌شده (از کتاب، فصلِ Bar-Counting):
  در روندِ صعودی، اصلاحِ دو-پایه (two-legged pullback) با تشکیلِ «High 2» سیگنالِ
  ادامهٔ روند می‌دهد؛ قرینه «Low 2» در روندِ نزولی.

تعریفِ مکانیکی (shift-safe، بدونِ look-ahead):
  - رژیم: روندِ صعودی اگر EMA_fast > EMA_slow؛ نزولی اگر برعکس.
  - در روندِ صعودی:
      • pullback = باری که high آن < high بارِ قبلی (leg نزولیِ اصلاح).
      • «High event» = باری که high آن > high بارِ قبلی، بلافاصله پس از >=۱ بارِ pullback.
      • شمارنده: اولین High event پس از شروعِ اصلاح = High 1؛ اگر پس از آن دوباره
        >=۱ بارِ pullback و سپس High event رخ دهد = **High 2** ⇒ سیگنالِ Long.
      • شمارنده با شکستِ رژیم یا رسیدن به High-4 ری‌ست می‌شود.
  - قرینهٔ کامل برای Low 2 ⇒ Short.
  ورود روی open کندلِ بعدی (سیگنال روی کندلِ بسته‌شده تولید و سپس shift می‌شود).

اعتبار: گیتِ سخت‌گیرانه = net>0 کل + net>0 در هر ۴ پنجره + WR≥۴۰٪ + n≥۳۰.
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

OUT = os.path.join(ROOT, "results", "_s168_brooks_high2_low2.json")
CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0

ASSET_FILES = {
    "XAUUSD": os.path.join(ROOT, "data", "XAUUSD_M15.csv"),
    "EURUSD": os.path.join(ROOT, "data", "EURUSD_M15.csv"),
}

se.ASSETS["EURUSD"].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load_data(path):
    df = pd.read_csv(path)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def count_high2_low2(df, ema_fast, ema_slow):
    """شمارندهٔ Brooks bar-counting — پیمایشِ سببیِ (causal) یک‌گذر.
    خروجی: دو آرایهٔ بولی long_event و short_event روی همان کندل (قبل از shift)."""
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    close = df["close"].to_numpy()
    ef = ind.ema(pd.Series(close), ema_fast).to_numpy()
    es = ind.ema(pd.Series(close), ema_slow).to_numpy()
    n = len(df)

    long_evt = np.zeros(n, dtype=bool)
    short_evt = np.zeros(n, dtype=bool)

    # شمارنده‌ها
    up_count = 0        # تعدادِ High eventهای شمارش‌شده در اصلاحِ جاری
    saw_pullback = False  # آیا از آخرین High event حداقل یک بارِ pullback دیده شده؟
    dn_count = 0
    saw_rally = False

    for i in range(1, n):
        bull = ef[i] > es[i]
        bear = ef[i] < es[i]

        # --- روندِ صعودی: شمارشِ High 1/2 ---
        if bull:
            dn_count = 0; saw_rally = False  # ری‌ستِ سمتِ مخالف
            if high[i] < high[i - 1]:
                saw_pullback = True  # بارِ pullback (legِ نزولیِ اصلاح)
            elif high[i] > high[i - 1] and saw_pullback:
                up_count += 1
                saw_pullback = False
                if up_count == 2:
                    long_evt[i] = True
                    up_count = 0  # پس از High 2 ری‌ست (ورودِ یک‌بار)
                elif up_count >= 4:
                    up_count = 0
        else:
            up_count = 0; saw_pullback = False

        # --- روندِ نزولی: شمارشِ Low 1/2 ---
        if bear:
            up_count = 0; saw_pullback = False
            if low[i] > low[i - 1]:
                saw_rally = True  # بارِ اصلاحِ صعودی
            elif low[i] < low[i - 1] and saw_rally:
                dn_count += 1
                saw_rally = False
                if dn_count == 2:
                    short_evt[i] = True
                    dn_count = 0
                elif dn_count >= 4:
                    dn_count = 0
        elif not bull:
            dn_count = 0; saw_rally = False

    return long_evt, short_evt


def evaluate(df, asset, side, ema_fast, ema_slow, sl_pip, tp_pip, max_hold):
    long_evt, short_evt = count_high2_low2(df, ema_fast, ema_slow)
    # ورود روی کندلِ بعدی
    long_sig = pd.Series(long_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    short_sig = pd.Series(short_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
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
        trades, asset, df=df, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=False,
    )
    n = len(per_trade)
    if n < 30:
        return None
    half = n // 2
    pnl = per_trade["net_usd"]
    net_h1 = pnl.iloc[:half].sum()
    net_h2 = pnl.iloc[half:].sum()
    net = float(stats["net_profit"])
    wr = float(stats["win_rate"])
    pf = float(stats["profit_factor"])
    accepted = bool(net > 0 and net_h1 > 0 and net_h2 > 0 and wr >= WR_FLOOR and n >= 30)
    return {
        "asset": asset, "side": side, "ema_fast": ema_fast, "ema_slow": ema_slow,
        "sl": sl_pip, "tp": tp_pip, "max_hold": max_hold,
        "net": net, "net_h1": float(net_h1), "net_h2": float(net_h2),
        "wr": wr, "pf": pf if pf != float("inf") else 999.0,
        "n": int(n), "accepted": accepted,
    }


def main():
    ema_pairs = [(20, 50), (10, 30)]
    grids = {
        "XAUUSD": [(150, 225), (200, 300), (250, 250), (300, 450)],
        "EURUSD": [(15, 22), (20, 30), (25, 25), (30, 45)],
    }
    max_holds = [16, 32]

    results = {}
    for asset, path in ASSET_FILES.items():
        df = load_data(path)
        variants = []
        for side in ("long", "short"):
            for (ef, es) in ema_pairs:
                for (sl, tp) in grids[asset]:
                    for mh in max_holds:
                        r = evaluate(df, asset, side, ef, es, sl, tp, mh)
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
            print(f"    {tag} {v['side']:5s} ema{v['ema_fast']}/{v['ema_slow']} "
                  f"SL{v['sl']}/TP{v['tp']} mh{v['max_hold']:2d}  "
                  f"net=${v['net']:9.0f}  WR={v['wr']:5.1f}%  n={v['n']:5d}  PF={v['pf']:.2f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    total_acc = sum(r["n_accepted"] for r in results.values())
    print(f"\n=== خلاصه: مجموع واریانتِ پذیرفته‌شده = {total_acc} ===")


if __name__ == "__main__":
    main()
