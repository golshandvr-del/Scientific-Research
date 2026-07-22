# -*- coding: utf-8 -*-
"""
S169 — اعتبارسنجیِ بهترین واریانتِ Spike-and-Channel روی XAUUSD.

سه آزمون:
  (۱) walk-forward ۴-پنجره (هر پنجره باید net>0 و WR≥40٪).
  (۲) نیمه‌ها (h1/h2) — از قبل در فایلِ اصلی چک شده، اینجا تکرار برای اطمینان.
  (۳) لبهٔ مستقل: سهمِ سیگنال‌هایی که خارج از پنجره‌های زمان-محورِ موجودِ پروژه
      رخ می‌دهند (تا مطمئن شویم بازتولیدِ S139..S144 نیست). دقیقاً مثلِ روشِ S168.

بهترین واریانتِ طلا از خروجیِ فایلِ اصلی:
  long, ema10/30, spike_len=3, spike_atr_mult=1.5, channel_window=20,
  SL=200, TP=300, max_hold=32  ⇒  net=+$4,998, WR=49.4%.
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
from strategies.s169_brooks_spike_channel import (
    detect_spike_channel_events, load_data, ASSET_FILES,
)

CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0
OUT = os.path.join(ROOT, "results", "_s169_spike_channel_validate.json")

BEST = dict(asset="XAUUSD", side="long", ema_fast=10, ema_slow=30,
            spike_len=3, spike_atr_mult=1.5, channel_window=20,
            sl=200, tp=300, max_hold=32)


def build_signals(df, cfg):
    long_evt, short_evt = detect_spike_channel_events(
        df, cfg["ema_fast"], cfg["ema_slow"], cfg["spike_len"],
        cfg["spike_atr_mult"], cfg["channel_window"],
    )
    long_sig = pd.Series(long_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    short_sig = pd.Series(short_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    if cfg["side"] == "long":
        short_sig = np.zeros_like(short_sig, dtype=bool)
    else:
        long_sig = np.zeros_like(long_sig, dtype=bool)
    return long_sig, short_sig


def run_window(df, long_sig, short_sig, cfg):
    trades = se.simulate_trades(
        df, long_sig, short_sig, cfg["sl"], cfg["tp"], cfg["asset"],
        max_hold=cfg["max_hold"], allow_overlap=False,
    )
    if trades is None or len(trades) < 10:
        return None
    stats, _, per_trade = se.run_capital_pertrade(
        trades, cfg["asset"], df=df, initial_capital=CAPITAL,
        risk_pct=RISK_PCT, compounding=False,
    )
    return {
        "net": float(stats["net_profit"]), "wr": float(stats["win_rate"]),
        "pf": float(stats["profit_factor"]) if stats["profit_factor"] != float("inf") else 999.0,
        "n": int(len(per_trade)),
    }


def in_time_layers(dt_series):
    """ماسکِ کندل‌هایی که در پنجره‌های زمان-محورِ موجودِ پروژه (S139..S144) هستند.
    S139 Overnight (22-23 UTC)، S140 Monday، S141 Turn-of-Month (روز 1-3)،
    S142 Mid-Month (روز 10/13/20)، S144 Pre-End (6-8 روز مانده به پایان ماه)."""
    dt = pd.DatetimeIndex(dt_series)
    hour = dt.hour
    dow = dt.dayofweek        # Monday=0
    dom = dt.day
    # روزهای مانده به پایانِ ماه
    days_in_month = dt.days_in_month
    days_to_end = days_in_month - dom
    m = (
        ((hour == 22) | (hour == 23)) |          # S139 Overnight
        (dow == 0) |                              # S140 Monday
        (dom <= 3) |                              # S141 Turn-of-Month
        (np.isin(dom, [10, 13, 20])) |            # S142/143 Mid-Month
        ((days_to_end >= 6) & (days_to_end <= 8)) # S144 Pre-End
    )
    return np.asarray(m)


def main():
    cfg = BEST
    df = load_data(ASSET_FILES[cfg["asset"]])
    long_sig, short_sig = build_signals(df, cfg)
    n = len(df)

    result = {"config": cfg}

    # --- کلّ دوره ---
    full = run_window(df, long_sig, short_sig, cfg)
    result["full"] = full
    print(f"FULL: net=${full['net']:.0f}  WR={full['wr']:.1f}%  PF={full['pf']:.2f}  n={full['n']}")

    # --- walk-forward ۴ پنجره ---
    edges = [int(n * k / 4) for k in range(5)]
    wf = []
    all_pos = True
    for w in range(4):
        a, b = edges[w], edges[w + 1]
        sub = df.iloc[a:b].reset_index(drop=True)
        ls, ss = build_signals(sub, cfg)
        r = run_window(sub, ls, ss, cfg)
        wf.append(r)
        ok = r is not None and r["net"] > 0 and r["wr"] >= WR_FLOOR
        all_pos = all_pos and ok
        tag = "OK " if ok else "BAD"
        if r:
            print(f"  W{w+1} [{tag}] net=${r['net']:8.0f}  WR={r['wr']:5.1f}%  PF={r['pf']:.2f}  n={r['n']}")
        else:
            print(f"  W{w+1} [BAD] insufficient trades")
    result["walkforward"] = wf
    result["wf_all_positive"] = bool(all_pos)

    # --- لبهٔ مستقل (خارج از پنجره‌های زمان-محور) ---
    time_mask = in_time_layers(df["dt"])
    indep_long = long_sig.copy()
    # سیگنال روی کندلِ si؛ ورود روی si+1. زمانِ ورود را برای طبقه‌بندی می‌گیریم.
    entry_time_mask = np.zeros(n, dtype=bool)
    sig_idx = np.where(long_sig)[0]
    for si in sig_idx:
        eb = si + 1
        if eb < n and time_mask[eb]:
            entry_time_mask[si] = True  # این سیگنال داخلِ لایه‌های زمانی است
    indep_long[entry_time_mask] = False  # فقط سیگنال‌های مستقل باقی می‌مانند
    n_total = int(long_sig.sum())
    n_indep = int(indep_long.sum())
    overlap_pct = 100.0 * (n_total - n_indep) / max(n_total, 1)

    indep = run_window(df, indep_long, np.zeros(n, dtype=bool), cfg)
    result["independent"] = {
        "n_total_signals": n_total, "n_independent_signals": n_indep,
        "overlap_pct_with_time_layers": round(overlap_pct, 1),
        "stats": indep,
    }
    if indep:
        indep_ok = indep["net"] > 0 and indep["wr"] >= WR_FLOOR and indep["n"] >= 30
        print(f"\nINDEP edge (outside time-layers): overlap={overlap_pct:.1f}%  "
              f"net=${indep['net']:.0f}  WR={indep['wr']:.1f}%  PF={indep['pf']:.2f}  n={indep['n']}  "
              f"[{'OK' if indep_ok else 'WEAK'}]")
        result["independent_ok"] = bool(indep_ok)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
