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

# پایه‌های دارایی — دقیقاً مطابقِ موتورِ رسمی se.ASSETS (تناقض ممنوع).
ASSET_BASE = {
    "XAUUSD": dict(pip=0.10, contract=100.0, pip_value=10.0,
                   spread_pip=3.3, comm=0.0, slip_pip=0.0),
    "EURUSD": dict(pip=0.0001, contract=100_000.0, pip_value=10.0,
                   spread_pip=1.0, comm=0.0, slip_pip=0.3),
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


def build_null(df, asset, key, sl, tp, n_long, n_short, n_perm=200, seed=7):
    """
    مدلِ صفرِ اندازه‌گیری‌شده برای S166: «اگر همان تعدادِ معامله را در بارهای
    **تصادفی** (نه سیگنالِ HalfTrend) با همان SL/TP می‌زدیم، WR چه می‌شد؟»
    این می‌پرسد آیا سیگنالِ HalfTrend واقعاً بهتر از ورودِ تصادفی است.
    خروجی با فرمتی که blend_null انتظار دارد: {side: {uncond_wr, perm_mean,
    perm_sd, perm_max, perm_k}}.
    """
    rng = np.random.default_rng(seed)
    n = len(df)
    null = {}
    for sd_side, is_long, n_side in (("long", True, n_long),
                                     ("short", False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side and n_side >= 1:
            wrs = []
            # بازهٔ مجازِ ورود: از warmup تا n-max_hold
            lo, hi = 260, n - MAX_HOLD - 1
            if hi > lo + n_side:
                for _ in range(n_perm):
                    bars = np.sort(rng.choice(np.arange(lo, hi),
                                              size=n_side, replace=False))
                    sig = np.zeros(n, dtype=bool)
                    sig[bars] = True
                    zero = np.zeros(n, dtype=bool)
                    if is_long:
                        rtr = se.simulate_trades(df, sig, zero, sl, tp, key,
                                                 max_hold=MAX_HOLD,
                                                 allow_overlap=False)
                    else:
                        rtr = se.simulate_trades(df, zero, sig, sl, tp, key,
                                                 max_hold=MAX_HOLD,
                                                 allow_overlap=False)
                    if rtr is not None and len(rtr) >= 1:
                        w = 100.0 * float((rtr["outcome"] > 0).mean()) \
                            if "outcome" in rtr.columns else None
                        if w is not None:
                            wrs.append(w)
            if wrs:
                a = np.asarray(wrs, dtype="float64")
                d.update(uncond_wr=float(a.mean()), perm_mean=float(a.mean()),
                         perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()),
                         perm_k=int(len(a)))
        null[sd_side] = d
    return null


def gatecheck(asset, tf, ampl, side, sl_k, rr, with_null=False):
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

    null = None
    if with_null:
        n_long = int((tr["direction"] > 0).sum()) if "direction" in tr.columns else len(tr)
        n_short = int((tr["direction"] < 0).sum()) if "direction" in tr.columns else 0
        null = build_null(df, asset, key, sl, tp, n_long, n_short)

    res = rqs2.compute_rqs2(tr, key, sl_pip=sl, tp_pip=tp, bar_time=bar_time,
                            null=null)

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
    # واریانت‌های طلایی که همهٔ گیت‌های اقتصادی را پاس کردند (INCOMPLETE، نه REJECT):
    # با null اندازه‌گیری‌شده اجرا می‌شوند تا H3/lift/z واقعی و تصمیمِ POWER-LIMITED
    # مشخص شود. فقط این‌ها چون null کند است (۲۰۰ جای‌گشت × شبیه‌سازی).
    targets = []
    if len(sys.argv) > 1 and sys.argv[1] == "gold":
        targets = [("XAUUSD", "D1", 2.0), ("XAUUSD", "W1", 1.5),
                   ("XAUUSD", "W1", 1.0)]
    else:
        # پیش‌فرض: مرورِ سریع بدونِ null روی همهٔ sl_k
        for asset, tf in [("XAUUSD", "W1"), ("XAUUSD", "D1")]:
            for sl_k in (1.0, 1.5, 2.0):
                gatecheck(asset, tf, ampl=2, side="long", sl_k=sl_k, rr=1.0)
                print()
        sys.exit(0)
    for asset, tf, sl_k in targets:
        gatecheck(asset, tf, ampl=2, side="long", sl_k=sl_k, rr=1.0,
                  with_null=True)
        print()
