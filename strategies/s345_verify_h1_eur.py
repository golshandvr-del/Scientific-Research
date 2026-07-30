# -*- coding: utf-8 -*-
"""
S345 — اعتبارسنجیِ سختِ دو کاندیدِ جدید: XAUUSD-H1 (RQS+ ۹۳.۸) و EURUSD-M30 (RQS+ ۹۱.۷).

چرا لازم است؟ (شکاکیتِ علمی، نه پذیرشِ خام)
  * XAU-H1: هر ۷ ترکیبِ ACC **دقیقاً n=۳۰** دارند — یعنی روی **کفِ نمونهٔ** RQS+ نشسته‌اند —
    و همه به **یک نقطهٔ پارامتری** (nO=3, k=1.5, sm=0.18, win=[0.25,0.90]) تعلق دارند؛
    پلاتو فقط روی TP/SL است، نه روی پارامترهای سیگنال. این الگوی کلاسیکِ **بیش‌برازش** است.
  * EUR-M30: دو ترکیبِ ACC (nO=6 و nO=4) ⇒ پلاتوی کوچک، اما n=۴۰/۳۶ هم نازک است.

سه آزمون برای هرکدام:
  A) **همسایگیِ پارامتری**: n_open / k_spike / slope_min / پنجرهٔ ورود را یکی‌یکی جابه‌جا
     می‌کنیم. لبهٔ واقعی باید در همسایگی **زنده** بماند (حتی اگر RQS کمی افت کند،
     نباید به زیرِ ۸۰ سقوطِ آزاد کند در **همهٔ** جهت‌ها).
  B) **همپوشانی (قانونِ اجباری)**: نسبت به پنجره‌های زمان-محورِ S139..S144؛ و ارزیابیِ
     مجزّای بخشِ مستقل و بخشِ همپوشان + بررسیِ نقشِ فیلتر.
  C) **نیمه‌های زمانی**: علامتِ سود در هر دو نیمه باید یکسان باشد.

اجرا: PYTHONPATH=. python3 strategies/s345_verify_h1_eur.py [H1|EURM30|ALL]
"""
import os
import sys
import json

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs                          # noqa: E402
from strategies.s345_brooks_reversal_day import reversal_day_signals, load_tf  # noqa: E402
from strategies.s345_overlap_validate import regime_mask, eval_sig, in_time_layers  # noqa: E402

OUT_DIR = os.path.join(ROOT, "results", "_scan_S345")

CAND = {
    "H1": dict(asset="XAUUSD", tf="H1", side="long", n_open=3, k_spike=1.5,
               slope_min=0.18, win=(0.25, 0.90), reg=None, sl=470, tp=800,
               maxhold=22),
    "EURM30": dict(asset="EURUSD", tf="M30", side="short", n_open=6, k_spike=0.8,
                   slope_min=0.18, win=(0.40, 0.95), reg="r2_lo", sl=20, tp=33,
                   maxhold=28),
}


def sig_of(df, c, n_open=None, k_spike=None, slope_min=None, win=None):
    s = reversal_day_signals(df, c["tf"], c["side"],
                             n_open=n_open if n_open is not None else c["n_open"],
                             k_spike=k_spike if k_spike is not None else c["k_spike"],
                             slope_min_frac=(slope_min if slope_min is not None
                                             else c["slope_min"]),
                             entry_from_frac=(win or c["win"])[0],
                             entry_to_frac=(win or c["win"])[1])
    return s & regime_mask(df, c["reg"])


def ev(df, c, sig, min_n=8):
    return eval_sig(df, sig, c["side"], c["asset"], c["sl"], c["tp"],
                    c["maxhold"], min_n=min_n)


def run(key):
    c = CAND[key]
    df = load_tf(c["asset"], c["tf"])
    print(f"\n########## {key}: {c['asset']} {c['tf']} {c['side']} "
          f"(rows={len(df)}) ##########")
    out = {"config": c}

    base_sig = sig_of(df, c)
    base = ev(df, c, base_sig)
    out["base"] = base
    print(f"BASE: {base}")

    # ---------------- A) همسایگیِ پارامتری
    print("\n--- A) parameter neighbourhood (is it a plateau or a single point?) ---")
    out["A_neighbourhood"] = {}
    grid = []
    for v in (c["n_open"] - 1, c["n_open"], c["n_open"] + 1, c["n_open"] + 2):
        if v >= 2:
            grid.append(("n_open", v))
    for v in (round(c["k_spike"] * 0.85, 3), c["k_spike"], round(c["k_spike"] * 1.15, 3)):
        grid.append(("k_spike", v))
    for v in (round(c["slope_min"] * 0.7, 4), c["slope_min"], round(c["slope_min"] * 1.3, 4)):
        grid.append(("slope_min", v))
    for v in [(max(0.05, c["win"][0] - 0.10), c["win"][1]),
              (c["win"][0], min(0.99, c["win"][1] + 0.05)),
              (c["win"][0] + 0.10, c["win"][1])]:
        grid.append(("win", v))

    for pname, val in grid:
        kw = {pname: val}
        s = sig_of(df, c, **kw)
        r = ev(df, c, s)
        out["A_neighbourhood"][f"{pname}={val}"] = r
        flag = "—" if r is None else ("ACC" if r["passed"] else "rej")
        print(f"  {pname:10s}={str(val):14s} {flag} {r}")

    # ---------------- B) همپوشانی (اجباری)
    print("\n--- B) overlap with existing time-based layers (S139..S144) ---")
    dt = pd.to_datetime(df["time"], unit="s")
    tl = in_time_layers(dt)
    tot = int(base_sig.sum())
    ov = int((base_sig & tl).sum())
    pct = round(100.0 * ov / max(tot, 1), 1)
    out["B_overlap"] = {"signals_total": tot, "overlap_pct": pct}
    print(f"  signals={tot}  overlap={pct}%")
    for nm, m in (("independent", base_sig & ~tl), ("overlapping_part", base_sig & tl)):
        r = ev(df, c, m, min_n=6)
        out["B_overlap"][nm] = r
        print(f"  {nm:18s} {r}")

    # ---------------- C) نیمه‌های زمانی
    print("\n--- C) chronological halves ---")
    n = len(df)
    mid = n // 2
    out["C_halves"] = {}
    for nm, sl_ in (("H1st", slice(0, mid)), ("H2nd", slice(mid, n))):
        d = df.iloc[sl_].reset_index(drop=True)
        r = ev(d, c, base_sig[sl_], min_n=6)
        out["C_halves"][nm] = r
        print(f"  {nm}: {r}")

    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    which = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    keys = list(CAND) if which == "ALL" else [which]
    res = {}
    for k in keys:
        res[k] = run(k)
        with open(os.path.join(OUT_DIR, "_verify_h1_eur.json"), "w",
                  encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=str)
        print(f"\nsaved -> results/_scan_S345/_verify_h1_eur.json  (after {k})")


if __name__ == "__main__":
    main()
