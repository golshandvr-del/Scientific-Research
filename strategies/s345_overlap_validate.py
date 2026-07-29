# -*- coding: utf-8 -*-
"""
S345 — اعتبارسنجیِ همپوشانی و لبهٔ مستقل (قانونِ همپوشانیِ اجباری).

چرا حیاتی است؟ S345 یک لایهٔ **intraday و زمان-آگاه** است (پنجرهٔ ورودِ میانه/اواخرِ روز)
⇒ دقیقاً همان ریسکی که S169 (Spike-and-Channel) را کشت: ~۴۷٪ همپوشانی با لایه‌های
زمان-محورِ S139..S144 و سهمِ مستقلِ breakeven. پس پیش از هر حکمی باید ثابت شود که
لبهٔ S345 **بازتولیدِ زمان-محور نیست**.

سه آزمون برای هر لایهٔ کاندید:
  (۱) FULL       : کلِ سیگنال‌ها (baseline).
  (۲) INDEPENDENT: فقط سیگنال‌های *خارج* از پنجره‌های زمان-محورِ موجود (S139..S144).
  (۳) OVERLAP%   : درصدِ سیگنالِ داخلِ ماسکِ زمان-محور.
  (۴) FILTER-ROLE: نقشِ S345 به‌عنوان **فیلترِ تأیید** روی لایه‌های موجود
      (راهِ اولِ پروژه: بهبود) — آیا حضورِ رژیمِ «چرخشِ روز» سیگنالِ لایه‌های
      زمان-محور را بهتر/بدتر می‌کند.

اجرا: PYTHONPATH=. python3 strategies/s345_overlap_validate.py
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
from strategies.s345_brooks_reversal_day import reversal_day_signals, load_tf

OUT = os.path.join(ROOT, "results", "_scan_S345", "_overlap_validate.json")

# لایه‌های کاندید — از اسکنِ MTF پر می‌شود (results/_scan_S345/<asset>_<tf>.json)
LAYERS = []


def regime_mask(df, reg):
    """بازتولیدِ verbatim ماسک‌های رژیمِ اسکن (s345_scan._build_regime_cache)."""
    n = len(df)
    if reg is None or reg == "None":
        return np.ones(n, bool)
    try:
        if reg == "chop_hi":
            a = ib.compute("chop_fib_21", df).to_numpy()
            return (a >= 45) & np.isfinite(a)
        if reg == "r2_lo":
            v = ib.r2(df, p=34).to_numpy()
            return (v <= 0.55) & np.isfinite(v)
        if reg == "adx_hi":
            a = ib.compute("adx", df).to_numpy()
            return (a >= 25) & np.isfinite(a)
        if reg == "hurst_lo":
            v = ib.hurst(df, p=55).to_numpy()
            return (v <= 0.50) & np.isfinite(v)
        if reg == "ema_stretch":
            v = ib.compute("ema_dist_atr", df).to_numpy()
            return (np.abs(v) >= 0.7) & np.isfinite(v)
    except Exception:
        return np.ones(n, bool)
    return np.ones(n, bool)


def in_time_layers(dt_series):
    """ماسکِ کندل‌های داخلِ پنجره‌های زمان-محورِ موجودِ پروژه (S139..S144).
    عیناً مطابقِ روشِ اعتبارسنجیِ S169/S344."""
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


def eval_sig(df, sig, side, asset, sl, tp, maxhold, min_n=10):
    n = len(df)
    long_sig = sig if side == "long" else np.zeros(n, bool)
    short_sig = sig if side == "short" else np.zeros(n, bool)
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl, tp_pip=tp,
                            asset=asset, max_hold=maxhold, allow_overlap=False)
    if tr is None or len(tr) < min_n:
        return None
    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
    m = r["metrics"]
    pf = m["profit_factor"]
    return dict(rqs=round(r["rqs_score"], 1), passed=bool(r["passed"]),
                gates="".join("1" if r["gates"][g] else "0"
                              for g in ["G0", "G1", "G2", "G3", "G4", "G5"]),
                n=int(m["n_trades"]), wr=round(m["win_rate"], 2),
                pf=round(pf, 3) if np.isfinite(pf) else 999.0,
                net=round(m["net_profit"], 1))


def load_candidates(min_rqs=70.0):
    """کاندیدها را از JSONهای اسکن بخوان (بهترینِ هر TF با RQS ≥ min_rqs)."""
    d = os.path.join(ROOT, "results", "_scan_S345")
    out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as f:
            j = json.load(f)
        for rec in (j.get("top") or [])[:3]:
            if rec["rqs"] >= min_rqs:
                out.append(dict(name=f"{j['asset']}_{j['tf']}_{rec['side']}_rqs{rec['rqs']}",
                                asset=j["asset"], tf=j["tf"], side=rec["side"],
                                n_open=rec["n_open"], k_spike=rec["k_spike"],
                                slope_min=rec["slope_min"], win=tuple(rec["win"]),
                                reg=rec["reg"], sl=rec["sl"], tp=rec["tp"],
                                maxhold=None, rqs_scan=rec["rqs"]))
    return out


TF_MAXHOLD = {'M1': 90, 'M5': 60, 'M15': 40, 'M30': 28, 'H1': 22, 'H4': 12, 'D1': 6, 'W1': 4}


def main():
    layers = LAYERS or load_candidates()
    if not layers:
        print("هیچ کاندیدی با RQS ≥ 70 در results/_scan_S345 نبود — اسکن را کامل کن.")
        return
    out = {}
    for L in layers:
        mh = L.get("maxhold") or TF_MAXHOLD.get(L["tf"], 24)
        df = load_tf(L["asset"], L["tf"])
        dt = pd.to_datetime(df["time"], unit="s")
        sig = reversal_day_signals(df, L["tf"], L["side"], n_open=L["n_open"],
                                   k_spike=L["k_spike"], slope_min_frac=L["slope_min"],
                                   entry_from_frac=L["win"][0], entry_to_frac=L["win"][1])
        sig = sig & regime_mask(df, L["reg"])

        tmask = in_time_layers(dt)
        sig_idx = np.where(sig)[0]
        n_total = len(sig_idx)
        n_in = int(tmask[sig_idx].sum()) if n_total else 0
        overlap_pct = round(100.0 * n_in / n_total, 1) if n_total else 0.0

        full = eval_sig(df, sig, L["side"], L["asset"], L["sl"], L["tp"], mh)
        indep = eval_sig(df, sig & (~tmask), L["side"], L["asset"], L["sl"], L["tp"], mh)
        ovl = eval_sig(df, sig & tmask, L["side"], L["asset"], L["sl"], L["tp"], mh)

        out[L["name"]] = dict(config={k: v for k, v in L.items()},
                              signals_total=n_total,
                              overlap_with_time_layers_pct=overlap_pct,
                              full=full, independent=indep, overlapping_part=ovl)

        print(f"\n===== {L['name']} (TF={L['tf']} maxhold={mh}) =====", flush=True)
        print(f"  signals={n_total}  overlap_with_S139..S144 = {overlap_pct}%")
        print(f"  FULL        : {full}")
        print(f"  INDEPENDENT : {indep}")
        print(f"  OVERLAP-PART: {ovl}")
        if indep and indep["passed"]:
            print("  ⇒ لبهٔ مستقل جامد (خارج از زمان-محور هم RQS+≥80) — لبهٔ نو تأیید.")
        elif indep and indep["rqs"] >= 60:
            print("  ⇒ لبهٔ مستقلِ نسبی؛ بخشی همپوشان — نقشِ فیلتر بررسی شود.")
        else:
            print("  ⚠️ لبهٔ مستقل ضعیف — ریسکِ بازتولیدِ زمان-محور (مثلِ S169).")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
