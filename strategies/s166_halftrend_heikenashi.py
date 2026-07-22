# -*- coding: utf-8 -*-
"""
S166 — HalfTrend flip + Heiken Ashi filter (اقتباس از سیستمِ Agimat FX 2020 Pro)

قانونِ پروژه: تابعِ هدف = بیشینه‌سازیِ سودِ خالصِ XAUUSD+EURUSD؛ WR هدف نیست اما
هر لایهٔ فعال باید WR≥۴۰٪ داشته باشد.

منبع: `Telegram-Resource/telegram_source_1/+++AgimatPro 2020 (2)/`
اجزای بازسازی‌شده (سورسِ Agimat بسته بود؛ این‌ها اجزای عمومیِ شناخته‌شده‌اند):
  - HalfTrend: اندیکاتورِ روندِ کم‌تأخیر مبتنی بر کانالِ high/low + ATR.
  - Heiken Ashi: کندلِ صاف‌شده به‌عنوانِ فیلترِ تأییدِ جهت.

قاعدهٔ آزمون:
  Long  = flipِ HalfTrend به صعودی  AND  کندلِ HA صعودی (haClose>haOpen)
  Short = flipِ HalfTrend به نزولی  AND  کندلِ HA نزولی
  خروج: SL/TP بر حسبِ pip؛ ورود روی open کندلِ بعد (forward-safe در موتور).

HalfTrend کاملاً causal است (فقط از گذشته استفاده می‌کند) ⇒ بدونِ look-ahead.
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

OUT = os.path.join(ROOT, "results", "_s166_halftrend_heikenashi.json")
CAPITAL = 10_000.0
RISK_PCT = 1.0
WR_FLOOR = 40.0


def load(asset):
    cfg = se.ASSETS[asset]
    df = pd.read_csv(os.path.join(ROOT, cfg["file"]))
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def heiken_ashi(df):
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)
    ha_close = (o + h + l + c) / 4.0
    ha_open = np.empty(n)
    ha_open[0] = (o[0] + c[0]) / 2.0
    for i in range(1, n):
        ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2.0
    return ha_open, ha_close


def half_trend(df, amplitude=2, atr_period=100):
    """بازسازیِ استانداردِ HalfTrend (Everget/Alex Orekhov). trend: 0=up, 1=down.
    خروجی: آرایهٔ trend و آرایهٔ flip (نقطهٔ تغییرِ روند)."""
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)

    # ATR/2
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr2 = pd.Series(tr).rolling(atr_period, min_periods=1).mean().to_numpy() / 2.0

    high_ma = pd.Series(h).rolling(amplitude, min_periods=1).mean().to_numpy()
    low_ma = pd.Series(l).rolling(amplitude, min_periods=1).mean().to_numpy()
    # highest high / lowest low over amplitude
    hh = pd.Series(h).rolling(amplitude, min_periods=1).max().to_numpy()
    ll = pd.Series(l).rolling(amplitude, min_periods=1).min().to_numpy()

    # پیاده‌سازیِ ساده و پایدارِ HalfTrend (causal — فقط از گذشته):
    #   در روندِ صعودی، اگر میانگینِ کفِ اخیر زیرِ (بیشترین سقفِ اخیر − ATR) برود ⇒ flip به نزول.
    #   در روندِ نزولی، اگر میانگینِ سقفِ اخیر بالای (کمترین کفِ اخیر + ATR) برود ⇒ flip به صعود.
    trend = np.zeros(n, dtype=int)
    atr_arr = pd.Series(tr).rolling(atr_period, min_periods=1).mean().to_numpy()
    for i in range(1, n):
        t = trend[i - 1]
        if t == 0:  # currently up
            if low_ma[i] < (hh[i] - atr_arr[i]):
                t = 1
        else:  # currently down
            if high_ma[i] > (ll[i] + atr_arr[i]):
                t = 0
        trend[i] = t
    flip_up = (trend == 0) & (np.concatenate([[1], trend[:-1]]) == 1)
    flip_dn = (trend == 1) & (np.concatenate([[0], trend[:-1]]) == 0)
    return trend, flip_up, flip_dn


def signals(df, amplitude, atr_period, use_ha):
    trend, flip_up, flip_dn = half_trend(df, amplitude, atr_period)
    long_sig = flip_up.copy()
    short_sig = flip_dn.copy()
    if use_ha:
        ha_o, ha_c = heiken_ashi(df)
        ha_bull = ha_c > ha_o
        ha_bear = ha_c < ha_o
        long_sig = long_sig & ha_bull
        short_sig = short_sig & ha_bear
    return long_sig, short_sig


def run(df, asset, side, amplitude=2, atr_period=100, use_ha=True, sl=30, tp=45, max_hold=24):
    long_sig, short_sig = signals(df, amplitude, atr_period, use_ha)
    z = np.zeros(len(df), dtype=bool)
    if side == "long":
        ls, ss = long_sig, z
    elif side == "short":
        ls, ss = z, short_sig
    else:
        ls, ss = long_sig, short_sig
    trades = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=max_hold, allow_overlap=False)
    if trades is None or len(trades) == 0:
        return None
    trades = trades.copy()
    trades["sl_pip"] = float(sl)
    stats, _, per_trade = se.run_capital_pertrade(
        trades, asset, initial_capital=CAPITAL, risk_pct=RISK_PCT, compounding=True
    )
    net = per_trade["net_usd"].to_numpy()
    return {
        "net": float(stats["net_profit"]),
        "wr": float((net > 0).mean() * 100.0) if len(net) else 0.0,
        "n": int(len(net)),
        "pf": float(stats["profit_factor"]),
        "max_dd_pct": float(stats["max_dd_pct"]),
    }


def evaluate(df, asset, side, **kw):
    full = run(df, asset, side, **kw)
    if full is None:
        return {"full": None, "accepted": False, "gates": {}}
    half = len(df) // 2
    halves = [run(df.iloc[:half].reset_index(drop=True), asset, side, **kw),
              run(df.iloc[half:].reset_index(drop=True), asset, side, **kw)]
    windows = [run(df.iloc[idx].reset_index(drop=True), asset, side, **kw)
               for idx in np.array_split(np.arange(len(df)), 4)]

    def ok(x):
        return x is not None and x["net"] > 0 and x["wr"] >= WR_FLOOR

    gates = {
        "full_net_positive": full["net"] > 0,
        "full_wr_at_least_40": full["wr"] >= WR_FLOOR,
        "both_halves_ok": all(ok(x) for x in halves),
        "all_walk_forward_ok": all(ok(x) for x in windows),
    }
    return {"full": full, "halves": halves, "walk_forward": windows,
            "gates": gates, "accepted": all(gates.values())}


def main():
    results = {}
    for asset in ("XAUUSD", "EURUSD"):
        df = load(asset)
        results[asset] = {"rows": len(df), "variants": []}
        for side in ("long", "short", "both"):
            for amplitude in (2, 3):
                for use_ha in (True, False):
                    for sl, tp in ((30, 45), (40, 60), (50, 100)):
                        ev = evaluate(df, asset, side, amplitude=amplitude, atr_period=100,
                                      use_ha=use_ha, sl=sl, tp=tp, max_hold=24)
                        if ev["full"] is not None and ev["full"]["n"] >= 20:
                            results[asset]["variants"].append({
                                "side": side, "amplitude": amplitude, "use_ha": use_ha,
                                "sl": sl, "tp": tp, **ev["full"],
                                "accepted": ev["accepted"], "gates": ev["gates"],
                            })
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    for asset, r in results.items():
        print(f"\n===== {asset} ({r['rows']} rows) =====")
        vs = sorted(r["variants"], key=lambda x: x["net"], reverse=True)
        print(f"  {len(vs)} variants n>=20; accepted={sum(v['accepted'] for v in vs)}")
        for v in vs[:8]:
            flag = "✅ACCEPTED" if v["accepted"] else "  rejected"
            print(f"  {flag} {v['side']:5s} amp{v['amplitude']} ha={int(v['use_ha'])} "
                  f"SL{v['sl']}/TP{v['tp']}  net=${v['net']:>10.0f}  WR={v['wr']:5.1f}%  n={v['n']:4d}  PF={v['pf']:.2f}")
    return results


if __name__ == "__main__":
    main()
