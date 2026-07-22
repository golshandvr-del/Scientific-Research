# -*- coding: utf-8 -*-
"""
S169-MM — Walk-forward ۴-پنجره روی سهمِ مستقلِ measured-move (XAUUSD long).

هدف: تأییدِ پایداریِ زمانیِ لبهٔ مستقل پیش از پذیرش. گیت: هر ۴ پنجره net>0 و WR≥40٪.
دو کاندیدِ برترِ پایدار از فایلِ measured-move آزموده می‌شوند.
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
from strategies.s169_brooks_spike_channel import load_data, ASSET_FILES
from strategies.s169_spike_channel_measured_move import detect_with_spike_height
from strategies.s169_spike_channel_validate import in_time_layers

CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0
OUT = os.path.join(ROOT, "results", "_s169_mm_walkforward.json")

BASE = dict(ema_fast=10, ema_slow=30, spike_len=3, spike_atr_mult=1.5, channel_window=20)
CANDIDATES = [
    dict(BASE, sl_frac=1.0, tp_frac=1.0, max_hold=48),   # WR 47.2%
    dict(BASE, sl_frac=1.0, tp_frac=1.5, max_hold=48),   # WR 44.6%
    dict(BASE, sl_frac=0.5, tp_frac=2.0, max_hold=32),   # net بالا، WR 42.3%
]


def build_independent_signals(df, cfg):
    asset = "XAUUSD"
    long_evt, spike_h = detect_with_spike_height(
        df, cfg["ema_fast"], cfg["ema_slow"], cfg["spike_len"],
        cfg["spike_atr_mult"], cfg["channel_window"],
    )
    n = len(df)
    pip = se.ASSETS[asset]["pip"]
    sl_arr = np.full(n, np.nan); tp_arr = np.full(n, np.nan)
    valid = ~np.isnan(spike_h)
    hpip = np.where(valid, spike_h / pip, 0.0)
    sl_arr[valid] = np.clip(hpip[valid] * cfg["sl_frac"], 80, 500)
    tp_arr[valid] = np.clip(hpip[valid] * cfg["tp_frac"], 120, 900)

    long_sig = pd.Series(long_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    sl_shift = pd.Series(sl_arr).shift(1).to_numpy()
    tp_shift = pd.Series(tp_arr).shift(1).to_numpy()

    time_mask = in_time_layers(df["dt"])
    for si in np.where(long_sig)[0]:
        if si < n and time_mask[si]:
            long_sig[si] = False

    sl_final = np.where(np.isnan(sl_shift), 100.0, sl_shift)
    tp_final = np.where(np.isnan(tp_shift), 150.0, tp_shift)
    return long_sig, sl_final, tp_final


def run(df, long_sig, sl, tp, mh):
    n = len(df)
    trades = se.simulate_trades(df, long_sig, np.zeros(n, dtype=bool), sl, tp,
                                "XAUUSD", max_hold=mh, allow_overlap=False)
    if trades is None or len(trades) < 10:
        return None
    stats, _, per_trade = se.run_capital_pertrade(
        trades, "XAUUSD", df=df, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=False)
    return {"net": float(stats["net_profit"]), "wr": float(stats["win_rate"]),
            "pf": float(stats["profit_factor"]) if stats["profit_factor"] != float("inf") else 999.0,
            "n": int(len(per_trade))}


def main():
    df = load_data(ASSET_FILES["XAUUSD"])
    n = len(df)
    edges = [int(n * k / 4) for k in range(5)]
    all_res = []

    for cfg in CANDIDATES:
        label = f"slF{cfg['sl_frac']} tpF{cfg['tp_frac']} mh{cfg['max_hold']}"
        long_sig, sl, tp = build_independent_signals(df, cfg)
        full = run(df, long_sig, sl, tp, cfg["max_hold"])
        print(f"\n=== {label} ===")
        print(f"  FULL: net=${full['net']:.0f}  WR={full['wr']:.1f}%  PF={full['pf']:.2f}  n={full['n']}")
        wf = []; all_ok = True
        for w in range(4):
            a, b = edges[w], edges[w + 1]
            sub = df.iloc[a:b].reset_index(drop=True)
            ls, s, t = build_independent_signals(sub, cfg)
            r = run(sub, ls, s, t, cfg["max_hold"])
            ok = r is not None and r["net"] > 0 and r["wr"] >= WR_FLOOR
            all_ok = all_ok and ok
            wf.append(r)
            if r:
                print(f"    W{w+1} [{'OK ' if ok else 'BAD'}] net=${r['net']:7.0f}  "
                      f"WR={r['wr']:5.1f}%  PF={r['pf']:.2f}  n={r['n']}")
            else:
                print(f"    W{w+1} [BAD] insufficient")
        print(f"  ⇒ walk-forward all positive & WR≥40: {all_ok}")
        all_res.append({"config": cfg, "full": full, "walkforward": wf, "wf_all_ok": bool(all_ok)})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(all_res, f, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
