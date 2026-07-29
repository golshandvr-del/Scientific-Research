# -*- coding: utf-8 -*-
"""
S344 — اعتبارسنجیِ همپوشانی و لبهٔ مستقل (قانونِ همپوشانیِ اجباری).

چرا این تست حیاتی است؟ لایهٔ نزدیکِ S169 (Spike-and-Channel) دقیقاً به این دلیل
مرد که ~۴۷٪ همپوشانی با لایه‌های زمان-محور (S139..S144) داشت و سهمِ مستقلش breakeven بود.
S344 هم intraday و زمان-آگاه است ⇒ باید پیش از پذیرش، مستقل‌بودنِ لبه‌اش اثبات شود.

سه آزمون برای هر لایهٔ پذیرفته‌شده (XAU M15 short + XAU H1 long):
  (۱) کلِ دوره (baseline).
  (۲) لبهٔ مستقل: فقط سیگنال‌های *خارج* از پنجره‌های زمان-محورِ موجود (S139..S144)
      — اگر خارج از آن‌ها هم RQS+/WR جامد ماند ⇒ لبهٔ نو (نه بازتولید).
  (۳) درصدِ همپوشانیِ سیگنال با ماسکِ زمان-محور.

اجرا: PYTHONPATH=. python3 strategies/s344_overlap_validate.py
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib
from strategies.s344_brooks_trend_from_open import trend_from_open_signals, load_tf

OUT = os.path.join(ROOT, "results", "_scan_S344", "_overlap_validate.json")

# دو لایهٔ پذیرفته‌شدهٔ S344 (پارامترهای برنده از اسکنِ MTF)
LAYERS = [
    dict(name="XAU_M15_short", asset="XAUUSD", tf="M15", side="short",
         n_open=4, f_range=0.20, pull_max=0.62, min_spike=0.20, reg="r2h",
         sl=220, tp=340, maxhold=32),
    dict(name="XAU_H1_long", asset="XAUUSD", tf="H1", side="long",
         n_open=6, f_range=0.20, pull_max=0.50, min_spike=0.30, reg=None,
         sl=450, tp=720, maxhold=20),
]


def regime_mask(df, reg):
    n = len(df)
    if reg is None:
        return np.ones(n, bool)
    if reg == "r2_34":
        v = ib.r2(df, p=34).to_numpy()
        return (v >= 0.34) & np.isfinite(v)
    if reg == "r2h":
        a = ib.r2(df, p=34).to_numpy()
        b = ib.hurst(df, p=55).to_numpy()
        return (a >= 0.30) & (b >= 0.52) & np.isfinite(a) & np.isfinite(b)
    return np.ones(n, bool)


def in_time_layers(dt_series):
    """ماسکِ کندل‌های داخلِ پنجره‌های زمان-محورِ موجودِ پروژه (S139..S144).
    عیناً مطابقِ روشِ اعتبارسنجیِ S169 (s169_spike_channel_validate.py)."""
    dt = pd.DatetimeIndex(dt_series)
    hour = dt.hour
    dow = dt.dayofweek           # Monday=0
    dom = dt.day
    days_in_month = dt.days_in_month
    days_to_end = days_in_month - dom
    m = (
        ((hour == 22) | (hour == 23)) |            # S139 Overnight
        (dow == 0) |                               # S140 Monday
        (dom <= 3) |                               # S141 Turn-of-Month
        (np.isin(dom, [10, 13, 20])) |             # S142/143 Mid-Month
        ((days_to_end >= 6) & (days_to_end <= 8))  # S144 Pre-End
    )
    return np.asarray(m)


def eval_sig(df, sig, side, asset, sl, tp, maxhold):
    n = len(df)
    long_sig = sig if side == "long" else np.zeros(n, bool)
    short_sig = sig if side == "short" else np.zeros(n, bool)
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                            asset=asset, max_hold=maxhold, allow_overlap=False)
    if tr is None or len(tr) < 10:
        return None
    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
    m = r["metrics"]
    return dict(rqs=round(r["rqs_score"], 1), passed=bool(r["passed"]),
                gates="".join("1" if r["gates"][g] else "0"
                              for g in ["G0", "G1", "G2", "G3", "G4", "G5"]),
                n=int(m["n_trades"]), wr=round(m["win_rate"], 2),
                pf=round(m["profit_factor"], 3) if m["profit_factor"] != float("inf") else 999.0,
                net=round(m["net_profit"], 1))


def main():
    out = {}
    for L in LAYERS:
        df = load_tf(L["asset"], L["tf"])
        dt = pd.to_datetime(df["time"], unit="s")
        sig = trend_from_open_signals(df, L["tf"], L["side"], n_open=L["n_open"],
                                      f_range=L["f_range"], pull_max=L["pull_max"],
                                      min_spike_frac=L["min_spike"])
        sig = sig & regime_mask(df, L["reg"])

        tmask = in_time_layers(dt)
        sig_idx = np.where(sig)[0]
        n_total = len(sig_idx)
        n_in = int(tmask[sig_idx].sum()) if n_total else 0
        overlap_pct = round(100.0 * n_in / n_total, 1) if n_total else 0.0

        sig_indep = sig & (~tmask)   # سیگنال‌های خارج از پنجره‌های زمان-محور

        full = eval_sig(df, sig, L["side"], L["asset"], L["sl"], L["tp"], L["maxhold"])
        indep = eval_sig(df, sig_indep, L["side"], L["asset"], L["sl"], L["tp"], L["maxhold"])

        out[L["name"]] = dict(config=L, signals_total=n_total,
                              overlap_with_time_layers_pct=overlap_pct,
                              full=full, independent=indep)

        print(f"\n===== {L['name']} =====")
        print(f"  signals={n_total}  overlap_with_S139..S144 = {overlap_pct}%")
        print(f"  FULL       : {full}")
        print(f"  INDEPENDENT: {indep}")
        if indep and indep["passed"]:
            print("  ⇒ لبهٔ مستقل جامد (خارج از زمان-محور هم RQS+≥80) — لبهٔ نو تأیید.")
        elif indep and indep["rqs"] >= 60:
            print("  ⇒ لبهٔ مستقل نسبی؛ بخشی همپوشان — بررسیِ نقشِ فیلتر.")
        else:
            print("  ⚠️ لبهٔ مستقل ضعیف — ریسکِ بازتولیدِ زمان-محور (مثلِ S169).")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
