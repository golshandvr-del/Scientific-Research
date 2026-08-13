# -*- coding: utf-8 -*-
"""
s450_paired_s356.py — S450 · بازپخشِ جفتیِ «کفِ ساعتِ اول» روی S356 (H1 LONG)
================================================================================
بیمارِ دوم از پیش‌ثبتِ S450 (results/S450_PREREG_MGMT_RULES_PROTOCOL.md §2).

بازتولیدِ پایه = عینِ خطِ لولهٔ ACCEPT رسمی (strategies/s356_v24_rejudge.py):
  سیگنال = build_signals_causal(FROZEN) & regime_gate(r2_fib_55 ≥ 0.45)
  معاملات = se.simulate_trades(sl=1.3×ATR_fib، tp=2×sl، mh=20، allow_overlap=False)

بازپخشِ جفتی در فضای pip (سازگار با scalp_engine):
  - قاعده: اگر close[i] < کفِ ساعتِ اولِ روزِ جاری ⇒ خروج در open[i+1]
    (H1: ساعتِ اول = ۱ کندل؛ مرزِ روز = گپ > TF+30 دقیقه — لنگرِ اصلاح‌شده).
  - تقدم: اگر خروجِ پایه در کندلِ i+1 با SL/TP بوده ⇒ SL/TP مقدم است
    (همان قراردادِ هر دو موتور — اولویتِ مدیریتِ ریسک).
  - دلیلِ خروجِ پایه از قیمتِ خروج بازسازی می‌شود (SL/TP ثابت‌اند؛ trailing نداریم).
  - pnl قاعده = (open[i+1] − fill)/pip − spread  (اسلیپیجِ XAU صفر است؛
    عینِ فرمولِ scalp_engine برای خروجِ زمانی).

اجرا: python3 strategies/s450_paired_s356.py
"""
import os
import sys
import json
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from strategies import s354_brooks_trend_resumption as base
from strategies.s354_causal_check import build_signals_causal
from strategies.s450_mgmt_first_hour_low import day_id_and_first_hour_low
from strategies.s450_paired_replay import metrics, judge

# پیکربندیِ منجمدِ ACCEPT (عینِ s356_v24_rejudge.FROZEN)
FROZEN = dict(n_open_frac=0.13, late_hour=16, spike_k=0.8, tight_atr=12.0,
              regime=("r2_fib_55", "ge", 0.45), sl_k=1.3, rr=2.0)
CARD = ("XAUUSD", "H1")


def reproduce_baseline():
    asset, tf = CARD
    df = se.load_data(os.path.join(ROOT, "data", f"{asset}_{tf}.csv"))
    atr_pip = base._atr_pip(df, asset, base.TF_ATR_P.get(tf, 34))
    mh = base.TF_MAX_HOLD.get(tf, 20)
    sl = round(FROZEN["sl_k"] * atr_pip, 1)
    tp = round(FROZEN["rr"] * sl, 1)
    gate = base.regime_gate(df, FROZEN["regime"])
    sig = build_signals_causal(df, asset, tf, FROZEN["n_open_frac"],
                               FROZEN["late_hour"], FROZEN["spike_k"],
                               FROZEN["tight_atr"]) & gate
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp, asset,
                            max_hold=mh, allow_overlap=False)
    return df, tr, dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                        n_signals=int(sig.sum()))


def paired_replay_pip(tr, df, tf, asset):
    cfg = se.ASSETS[asset]
    pip = cfg["pip"]; spread = cfg["spread_pip"]; slip = cfg["slip_pip"]
    o = df["open"].values.astype(float)
    c = df["close"].values.astype(float)
    _, fhl = day_id_and_first_hour_low(df, tf)

    rows = []
    for t in tr.itertuples(index=False):
        eb = int(t.entry_bar); xb = int(t.exit_bar)
        fill = float(t.entry_price)
        sl_price = fill - float(t.sl_pip) * pip
        # tp از rr=2 بازسازی: tp_price = fill + 2*sl_d
        tp_price = fill + 2.0 * float(t.sl_pip) * pip
        # بازسازیِ دلیلِ خروجِ پایه از قیمتِ خروج (بدونِ trailing قیمت‌ها ثابت‌اند)
        xp = float(t.exit_price)
        if abs(xp - sl_price) < 1e-9:
            reason_b = "sl"
        elif abs(xp - tp_price) < 1e-9:
            reason_b = "tp"
        else:
            reason_b = "time"

        pnl_m = float(t.pnl_pip)
        xb_m = xb; reason_m = reason_b; changed = False
        for i in range(eb, xb):
            if i + 1 == xb and reason_b in ("sl", "tp"):
                break  # تقدمِ SL/TP کندلِ خروجِ پایه
            f = fhl[i]
            if np.isfinite(f) and c[i] < f:
                exit_fill = o[i + 1] - slip * pip
                pnl_m = (exit_fill - fill) / pip - spread
                xb_m = i + 1; reason_m = "fhl_exit"; changed = True
                break
        rows.append(dict(entry_bar=eb, exit_bar=xb, exit_bar_mgmt=xb_m,
                         pnl_base=float(t.pnl_pip), pnl_mgmt=pnl_m,
                         reason_base=reason_b, reason_mgmt=reason_m,
                         changed=changed,
                         bars_held_base=xb - eb, bars_held_mgmt=xb_m - eb))
    return pd.DataFrame(rows)


def main():
    asset, tf = CARD
    df, tr, meta = reproduce_baseline()
    print(f"baseline reproduced: n={len(tr)} sl={meta['sl_pip']} "
          f"tp={meta['tp_pip']} mh={meta['max_hold']} signals={meta['n_signals']}")
    pv = se.ASSETS[asset]["pip_value"]  # pnl_pip → USD بر ۱ لات
    pr = paired_replay_pip(tr, df, tf, asset)
    pr["usd_base"] = pr["pnl_base"] * pv
    pr["usd_mgmt"] = pr["pnl_mgmt"] * pv

    mid = len(df) // 2
    h1 = pr[pr["entry_bar"] < mid]; h2 = pr[pr["entry_bar"] >= mid]
    out = dict(
        strategy="S356_BrooksTrendResumption", card=f"{asset}-{tf}",
        params=meta, rule="S450 first-hour-low LONG exit (M1) — paired replay",
        n_trades=int(len(pr)), n_changed=int(pr["changed"].sum()),
        baseline=metrics(pr["usd_base"]), treatment=metrics(pr["usd_mgmt"]),
        judge_full=judge(metrics(pr["usd_base"]), metrics(pr["usd_mgmt"])),
        halves=dict(
            h1=dict(base=metrics(h1["usd_base"]), mgmt=metrics(h1["usd_mgmt"]),
                    judge=judge(metrics(h1["usd_base"]), metrics(h1["usd_mgmt"]))),
            h2=dict(base=metrics(h2["usd_base"]), mgmt=metrics(h2["usd_mgmt"]),
                    judge=judge(metrics(h2["usd_base"]), metrics(h2["usd_mgmt"])))),
        changed_detail=dict(
            avg_base_of_changed=round(float(pr.loc[pr["changed"], "usd_base"].mean()), 2)
            if pr["changed"].any() else None,
            avg_mgmt_of_changed=round(float(pr.loc[pr["changed"], "usd_mgmt"].mean()), 2)
            if pr["changed"].any() else None,
            avg_bars_saved=round(float((pr.loc[pr["changed"], "bars_held_base"]
                                        - pr.loc[pr["changed"], "bars_held_mgmt"]).mean()), 1)
            if pr["changed"].any() else None),
    )
    os.makedirs(os.path.join(ROOT, "research", "mgmt"), exist_ok=True)
    path = os.path.join(ROOT, "research", "mgmt", "S450_paired_S356_H1.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\n===== S450 paired · S356 · {asset}_{tf} =====")
    print(f"trades={out['n_trades']}  changed={out['n_changed']}")
    print("BASE :", out["baseline"])
    print("MGMT :", out["treatment"])
    print("JUDGE:", out["judge_full"])
    print("H1   :", out["halves"]["h1"]["judge"])
    print("H2   :", out["halves"]["h2"]["judge"])
    print("changed detail:", out["changed_detail"])
    print("saved:", path)


if __name__ == "__main__":
    main()
