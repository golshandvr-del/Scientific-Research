# -*- coding: utf-8 -*-
"""
S166-GATECHECK — تشخیصِ کاملِ ۱۱ گیتِ RQS2 روی بهترین واریانتِ D1/W1
--------------------------------------------------------------------------------
هدف: D1 و W1 طلا PF>1 دارند (اقتصاداً سودده) ولی REJECT شدند. باید بفهمیم
دقیقاً کدام گیت‌ها رد شدند تا تصمیمِ POWER-LIMITED در برابر DEAD گرفته شود.
اگر فقط گیت‌های توان‌محور (H3/H7/H10) به‌خاطر نمونهٔ کم رد شده‌اند ⇒ POWER-LIMITED.
اگر گیت‌های اقتصادی (H0/H1/H2/H8/H9) رد شده‌اند ⇒ لبهٔ واقعی معیوب است.
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs2
from strategies.s166_halftrend_heikenashi import signals

ASSET_BASE = {
    "XAUUSD": dict(pip=0.1, contract=100.0, pip_value=1.0, spread_pip=3.3, comm=0.0),
    "EURUSD": dict(pip=0.0001, contract=100_000.0, pip_value=10.0, spread_pip=1.4, comm=0.0),
}
ATR_P = 100
MAX_HOLD = 16


def _load(asset, tf):
    path = os.path.join(ROOT, f"data/{asset}_{tf}.csv")
    df = pd.read_csv(path)
    df["dt"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.reset_index(drop=True)


def _atr_pip(df, asset, period=14):
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = pd.Series(tr).rolling(period, min_periods=1).mean().to_numpy()
    return float(np.nanmedian(atr) / ASSET_BASE[asset]["pip"])


def gatecheck(asset, tf, ampl, side, sl_k, rr):
    df = _load(asset, tf)
    key = f"{asset}"
    se.ASSETS[key] = dict(file=f"data/{asset}_{tf}.csv", **ASSET_BASE[asset])
    atr_pip = _atr_pip(df, asset)
    sl = max(1.0, round(sl_k * atr_pip, 1))
    tp = round(rr * sl, 1)

    long_sig, short_sig = signals(df, ampl, ATR_P, use_ha=True)
    z = np.zeros(len(df), dtype=bool)
    if side == "long":
        ls, ss = long_sig, z
    elif side == "short":
        ls, ss = z, short_sig
    else:
        ls, ss = long_sig, short_sig

    tr = se.simulate_trades(df, ls, ss, sl, tp, key, max_hold=MAX_HOLD,
                            allow_overlap=False)
    tr = tr.copy()
    tr["sl_pip"] = float(sl)
    bar_time = df["dt"].values
    res = rqs2.compute_rqs2(tr, key, sl_pip=sl, tp_pip=tp, bar_time=bar_time)

    print(f"=== {asset}_{tf} | ampl={ampl} side={side} sl_k={sl_k} rr={rr} ===")
    print(f"    sl={sl} tp={tp} atr_pip={round(atr_pip,1)}")
    m = res.get("metrics", {})
    print(f"    n={m.get('n_trades')} WR={m.get('win_rate')} "
          f"PF={m.get('profit_factor')} net={m.get('net_profit')}")
    print(f"    lift={m.get('skill_lift_pp')} z={m.get('skill_z')}")
    print(f"    score={res.get('score')} verdict={res.get('verdict')} "
          f"power_limited={res.get('power_limited')}")
    gates = res.get("gates", {})
    print("    GATES:", {k: gates[k] for k in sorted(gates.keys())})
    gf = res.get("gate_families", {})
    if gf:
        print("    economic_all_pass:", gf.get("economic_all_pass"))
        print("    power_defects:", gf.get("power_defects"))
    # چاپِ دلایلِ رد شدنِ گیت‌ها اگر موجود بود
    for rk in ("h_reasons", "reasons", "gate_reasons"):
        if rk in res:
            print(f"    {rk}:", res[rk])
    return res


if __name__ == "__main__":
    # بهترین واریانت‌های اقتصادیِ کشف‌شده (بالاترین PF): long, ampl=2, rr=1.0, sl_k=?
    # sl نمایش‌داده‌شده در اسکن ≈ 1.0*atr_pip بود، پس sl_k=1.0
    for asset, tf in [("XAUUSD", "W1"), ("XAUUSD", "D1")]:
        for sl_k in (1.0, 1.5, 2.0):
            gatecheck(asset, tf, ampl=2, side="long", sl_k=sl_k, rr=1.0)
            print()
