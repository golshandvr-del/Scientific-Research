# -*- coding: utf-8 -*-
"""
S185c — همپوشانیِ *کاملِ* 123PatternsV6 با کلِ اجتماعِ پرتفویِ XAUUSD
=====================================================================
درسِ S182: سهمِ مستقل باید نسبت به «Union-All» سنجیده شود، نه فقط زیرمجموعه‌ای از
لایه‌ها. این‌جا اجتماع = پنجره‌های زمان-محور ∪ ساختارِ Brooks High-2/Low-2 (بار-به-بار).
هر معاملهٔ 123Patterns که واردِ اجتماع نشود «سهمِ مستقلِ اصیل» است.

خروجی: درصدِ همپوشانی + net/WR/گیتِ walk-forward روی سهمِ مستقلِ نهایی.
"""
import sys
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.ea_tracer import (load_candles, generate_signals,
                             trace_trades, summarize)
from strategies.s168_brooks_high2_low2 import count_high2_low2


def main():
    sym, tf, pt = "XAUUSD", "M15", 0.01
    cd = load_candles(sym, tf)
    sig, zz = generate_signals(cd, point=pt)
    trades = trace_trades(cd, sig, sym, target=1)
    n_bars = len(cd["time"])

    # --- دیتافریم برای تقویم + High-2/Low-2 ---
    df = pd.DataFrame({
        "time": cd["time"], "open": cd["open"], "high": cd["high"],
        "low": cd["low"], "close": cd["close"], "volume": cd["volume"],
    })
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["hour"] = df["dt"].dt.hour
    df["dow"] = df["dt"].dt.dayofweek
    df["dom"] = df["dt"].dt.day
    df["ym"] = df["dt"].dt.year * 100 + df["dt"].dt.month
    days = df[["dt", "ym"]].copy()
    days["date"] = df["dt"].dt.normalize()
    dd = days.drop_duplicates("date").reset_index(drop=True)
    dd["rank"] = dd.groupby("ym").cumcount() + 1
    dd["cnt"] = dd.groupby("ym")["date"].transform("count")
    dd["from_end"] = dd["rank"] - dd["cnt"] - 1
    m = dict(zip(dd["date"], dd["from_end"]))
    df["from_end"] = df["dt"].dt.normalize().map(m)

    # --- ماسکِ اجتماعِ زمان-محور (بار-به-بار) ---
    time_mask = (
        df["hour"].isin([22, 23]) |
        (df["dom"] <= 3) |
        df["dom"].between(13, 17) |
        df["from_end"].between(-8, -6) |
        (df["dow"] == 0)
    ).to_numpy()

    # --- ساختارِ Brooks High-2 (long) و Low-2 (short) روی EMA20/50 ---
    long_evt, short_evt = count_high2_low2(df, 20, 50)
    brooks_mask = np.asarray(long_evt, dtype=bool) | np.asarray(short_evt, dtype=bool)

    union_mask = time_mask | brooks_mask

    total = len(trades)
    covered_time = 0
    covered_brooks = 0
    covered_union = 0
    indep = []
    for t in trades:
        i = t["entry_shift"]
        ct = bool(time_mask[i])
        cb = bool(brooks_mask[i])
        cu = bool(union_mask[i])
        covered_time += ct
        covered_brooks += cb
        covered_union += cu
        if not cu:
            indep.append(t)

    print("=" * 78)
    print("S185c — همپوشانیِ کاملِ 123Patterns با Union-All طلا (زمان ∪ Brooks High/Low-2)")
    print("=" * 78)
    print(f"کلِ معاملات: {total}")
    print(f"  همپوشانی با زمان-محورها : {covered_time} ({covered_time/total*100:.1f}%)")
    print(f"  همپوشانی با Brooks H2/L2 : {covered_brooks} ({covered_brooks/total*100:.1f}%)")
    print(f"  همپوشانی با Union-All    : {covered_union} ({covered_union/total*100:.1f}%)")
    print(f"  سهمِ مستقلِ اصیل         : {len(indep)} ({len(indep)/total*100:.1f}%)")

    s_all = summarize(trades)
    s_ind = summarize(indep)
    print(f"\n  کل    : net={s_all['net']:+,.2f} WR={s_all['wr']}% n={s_all['n']}")
    print(f"  مستقل : net={s_ind['net']:+,.2f} WR={s_ind['wr']}% n={s_ind['n']} PF={s_ind['pf']}")

    tr = sorted(indep, key=lambda t: t["entry_shift"])
    mid = len(tr) // 2
    h1 = sum(t["pnl"] for t in tr[:mid]); h2 = sum(t["pnl"] for t in tr[mid:])
    q = len(tr) // 4
    wf = [round(sum(t["pnl"] for t in tr[i*q:(i+1)*q])) for i in range(4)]
    print(f"  مستقل halves: h1={h1:+.0f} h2={h2:+.0f} | WF={wf}")
    passes = (s_ind["net"] > 0 and s_ind["wr"] >= 40 and h1 > 0 and h2 > 0
              and all(w > 0 for w in wf) and s_ind["n"] >= 30)
    print(f"\n  سهمِ مستقلِ نهایی گیتِ سخت را: "
          f"{'✅ پاس می‌کند ⇒ ثبتِ لبهٔ مستقل' if passes else '❌ رد می‌کند'}")
    print(f"  ➜ سودِ خالصِ قابلِ ثبت (سهمِ مستقلِ محافظه‌کارانه): "
          f"{s_ind['net'] if passes else 0:+,.2f}$")


if __name__ == "__main__":
    main()
