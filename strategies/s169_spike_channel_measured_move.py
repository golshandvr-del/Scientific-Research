# -*- coding: utf-8 -*-
"""
S169-MM — واریانتِ measured-move از Spike-and-Channel (هستهٔ واقعیِ روشِ Brooks).

انگیزه: در آزمونِ اول، لبهٔ مستقلِ Spike-and-Channel (خارج از پنجره‌های زمان-محور)
فقط +$198 با PF=1.01 بود (تقریباً بی‌لبه). Brooks تأکید می‌کند TP باید بر اساسِ
**measured move = ارتفاعِ spike** باشد، نه TP ثابت. این فایل همان قاعده را با
TP/SL نسبت به ارتفاعِ spike (پویا) و **فقط روی سهمِ مستقل** می‌آزماید تا ببینیم
آیا measured-move لبهٔ مستقلِ واقعی می‌سازد.

تابعِ هدف: سودِ خالص؛ کفِ WR≥40٪.
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
from strategies.s169_brooks_spike_channel import load_data, ASSET_FILES
from strategies.s169_spike_channel_validate import in_time_layers

CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0
OUT = os.path.join(ROOT, "results", "_s169_spike_channel_measured_move.json")


def detect_with_spike_height(df, ema_fast, ema_slow, spike_len, spike_atr_mult,
                             channel_window):
    """مثلِ نسخهٔ اصلی اما برای هر سیگنالِ long، ارتفاعِ spikeِ فعال (spike_top-
    spike_bot) را هم ذخیره می‌کند تا TP/SL نسبت به آن پویا شود."""
    o = df["open"].to_numpy(dtype=np.float64)
    h = df["high"].to_numpy(dtype=np.float64)
    l = df["low"].to_numpy(dtype=np.float64)
    c = df["close"].to_numpy(dtype=np.float64)
    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()
    atr = ind.atr(df, 14).to_numpy()
    n = len(df)

    long_evt = np.zeros(n, dtype=bool)
    spike_h = np.full(n, np.nan)  # ارتفاعِ spikeِ فعال روی کندلِ سیگنال

    bull_body = c > o
    hh = np.zeros(n, dtype=bool); hh[1:] = h[1:] > h[:-1]
    hl = np.zeros(n, dtype=bool); hl[1:] = l[1:] > l[:-1]

    def rolling_all(arr):
        out = arr.copy()
        for k in range(1, spike_len):
            sh = np.zeros(n, dtype=bool); sh[k:] = arr[:n - k]
            out &= sh
        out[:spike_len - 1] = False
        return out

    mask = rolling_all(bull_body) & rolling_all(hh) & rolling_all(hl)
    move_up = np.full(n, -np.inf); move_up[spike_len:] = c[spike_len:] - c[:n - spike_len]
    bull_spike = mask & (~np.isnan(atr)) & (move_up >= spike_atr_mult * np.nan_to_num(atr))

    bull_channel_left = 0
    spike_top = np.nan
    spike_bot = np.nan
    for i in range(spike_len + 1, n):
        bull = ef[i] > es[i]
        if bull and bull_spike[i]:
            bull_channel_left = channel_window
            spike_top = h[i]
            spike_bot = l[i - spike_len + 1]
        if bull_channel_left > 0:
            if not bull:
                bull_channel_left = 0
            else:
                if l[i] < l[i - 1] and c[i] < spike_top:
                    long_evt[i] = True
                    spike_h[i] = spike_top - spike_bot
                bull_channel_left -= 1
    return long_evt, spike_h


def evaluate(df, asset, cfg, independent_only=True):
    long_evt, spike_h = detect_with_spike_height(
        df, cfg["ema_fast"], cfg["ema_slow"], cfg["spike_len"],
        cfg["spike_atr_mult"], cfg["channel_window"],
    )
    n = len(df)
    pip = se.ASSETS[asset]["pip"]

    # TP/SL پویا بر حسبِ ارتفاعِ spike (بر حسبِ pip)، با کف/سقف امن
    sl_pip_arr = np.full(n, np.nan)
    tp_pip_arr = np.full(n, np.nan)
    valid = ~np.isnan(spike_h)
    height_pip = np.where(valid, spike_h / pip, 0.0)
    sl_pip_arr[valid] = np.clip(height_pip[valid] * cfg["sl_frac"], 80, 500)
    tp_pip_arr[valid] = np.clip(height_pip[valid] * cfg["tp_frac"], 120, 900)

    long_sig = pd.Series(long_evt).shift(1).fillna(False).infer_objects(copy=False).to_numpy()
    # shift کردنِ TP/SL هم‌راه با سیگنال
    sl_shift = pd.Series(sl_pip_arr).shift(1).to_numpy()
    tp_shift = pd.Series(tp_pip_arr).shift(1).to_numpy()

    if independent_only:
        time_mask = in_time_layers(df["dt"])
        # حذفِ سیگنال‌هایی که ورودشان داخلِ لایه‌های زمانی است
        for si in np.where(long_sig)[0]:
            if si < n and time_mask[si]:
                long_sig[si] = False

    # جایگزینیِ NaN در TP/SL جاهایی که سیگنال نیست با مقدارِ بی‌اثر
    sl_final = np.where(np.isnan(sl_shift), 100.0, sl_shift)
    tp_final = np.where(np.isnan(tp_shift), 150.0, tp_shift)

    trades = se.simulate_trades(
        df, long_sig, np.zeros(n, dtype=bool), sl_final, tp_final, asset,
        max_hold=cfg["max_hold"], allow_overlap=False,
    )
    if trades is None or len(trades) < 30:
        return None
    stats, _, per_trade = se.run_capital_pertrade(
        trades, asset, df=df, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=False,
    )
    m = len(per_trade)
    if m < 30:
        return None
    half = m // 2
    pnl = per_trade["net_usd"]
    return {
        "sl_frac": cfg["sl_frac"], "tp_frac": cfg["tp_frac"], "max_hold": cfg["max_hold"],
        "net": float(stats["net_profit"]), "wr": float(stats["win_rate"]),
        "pf": float(stats["profit_factor"]) if stats["profit_factor"] != float("inf") else 999.0,
        "n": int(m),
        "net_h1": float(pnl.iloc[:half].sum()), "net_h2": float(pnl.iloc[half:].sum()),
    }


def main():
    asset = "XAUUSD"
    df = load_data(ASSET_FILES[asset])
    base = dict(ema_fast=10, ema_slow=30, spike_len=3, spike_atr_mult=1.5,
                channel_window=20)
    grid = []
    for sl_frac in (0.5, 0.75, 1.0):
        for tp_frac in (1.0, 1.5, 2.0):
            for mh in (32, 48):
                grid.append(dict(base, sl_frac=sl_frac, tp_frac=tp_frac, max_hold=mh))

    print(f"===== {asset} measured-move (INDEPENDENT sub-edge only) =====")
    rows = []
    for cfg in grid:
        r = evaluate(df, asset, cfg, independent_only=True)
        if r:
            rows.append(r)
    rows.sort(key=lambda x: x["net"], reverse=True)
    for r in rows[:12]:
        stable = r["net"] > 0 and r["net_h1"] > 0 and r["net_h2"] > 0 and r["wr"] >= WR_FLOOR
        tag = "OK " if stable else "wk "
        print(f"  [{tag}] slF{r['sl_frac']} tpF{r['tp_frac']} mh{r['max_hold']}  "
              f"net=${r['net']:8.0f}  WR={r['wr']:5.1f}%  PF={r['pf']:.2f}  n={r['n']}  "
              f"h1=${r['net_h1']:.0f} h2=${r['net_h2']:.0f}")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"asset": asset, "rows": rows}, f, ensure_ascii=False, indent=2)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
