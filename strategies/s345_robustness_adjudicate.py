# -*- coding: utf-8 -*-
"""
S345 — داوریِ مقاومت: کدام نسخه به سایت وصل شود؟ (نبوغِ علمی، نه بیشینه‌سازیِ کورِ RQS+)

مسئله:
  سه نسخهٔ کاندید روی XAUUSD-M15-long وجود دارد:
    V1 «پایه»        : RQS+ ۸۹.۸  n=۱۱۳  WR ۶۱.۱  PF ۲.۲۰  net $۲,۵۳۵
    V2 «پایه+dropTOM»: RQS+ ۹۰.۷  n=۱۰۱  WR ۶۲.۴  PF ۲.۳۰  net $۲,۴۲۳
    V3 «انباشته×۳»   : RQS+ ۹۴.۶  n=۴۵   WR ۷۱.۱  PF ۳.۴۱  net $۱,۵۸۴
  V3 بالاترین RQS+ را دارد اما **۶۰٪ نمونه را سوزانده** و سودِ خالص را ۳۷٪ کم کرده.
  پذیرشِ کورِ V3 = خطرِ بیش‌برازش (overfit) و نقضِ روحِ «سودِ خالص».

سه آزمونِ سختِ داوری (هیچ‌کدام در گریدِ اولیه دیده نشده‌اند):
  A) **لرزشِ آستانه (threshold jitter)**: هر آستانهٔ فیلتر ±۱۰٪/±۲۰٪ جابه‌جا می‌شود.
     لبهٔ واقعی باید در همسایگیِ آستانه **زنده** بماند. اگر RQS+ با لرزشِ کوچک از ۸۰
     بیفتد ⇒ آستانه بر نویز برازش شده (overfit) ⇒ رد.
  B) **نیمه‌های زمانیِ خارج‌نمونه (chronological halves)**: داده به دو نیمهٔ زمانی
     تقسیم می‌شود؛ نسخه‌ای که فقط در یک نیمه سودآور است، لبهٔ پایدار ندارد.
     (این مستقل از G4ِ walk-forward است و سخت‌گیرانه‌تر گزارش می‌شود.)
  C) **کاراییِ هر معامله (net/trade)** و **هزینهٔ فرصت**: آیا فیلترها معاملاتِ برنده
     را هم قربانی می‌کنند؟ اگر net/trade بالا برود ولی net کل به‌شدت بیفتد،
     فیلتر «آرایشی» است نه «اطلاعاتی».

خروجی: results/_scan_S345/_adjudicate_M15.json  + حکمِ صریحِ کدام نسخه به سایت برود.

اجرا: PYTHONPATH=. python3 strategies/s345_robustness_adjudicate.py
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
from engine import indicator_bank as ib         # noqa: E402
from strategies.s345_brooks_reversal_day import reversal_day_signals, load_tf  # noqa: E402
from strategies.s345_overlap_validate import regime_mask, eval_sig            # noqa: E402

OUT_DIR = os.path.join(ROOT, "results", "_scan_S345")

# پیکربندیِ پایهٔ برندهٔ اسکن (XAUUSD-M15-long) — دست‌نخورده
CFG = dict(asset="XAUUSD", tf="M15", side="long", n_open=4, k_spike=1.1,
           slope_min=0.05, win=(0.40, 0.95), reg="r2_lo", sl=240, tp=400,
           maxhold=40)


# ---------------------------------------------------------------- فیلترها
def f_er(df, thr):
    v = ib.compute("er_lucas_29", df).to_numpy(dtype=float)
    return (v >= thr) & np.isfinite(v)


def f_r2(df, thr):
    v = ib.compute("r2_fib_55", df).to_numpy(dtype=float)
    return (v <= thr) & np.isfinite(v)


def f_hurst(df, thr):
    v = ib.hurst(df, p=55).to_numpy(dtype=float)
    return (v >= thr) & np.isfinite(v)


def f_tom(df, _thr=None):
    dt = pd.DatetimeIndex(pd.to_datetime(df["time"], unit="s"))
    return (dt.day > 3).to_numpy()


# آستانه‌های «برندهٔ» انباشتِ حریصانه
BEST = dict(er=0.11, r2=0.62, hurst=0.43)


def build_variant(df, which, jit=None):
    """ماسکِ فیلترِ هر نسخه. jit = ضریبِ لرزشِ آستانه (مثلاً 1.10)."""
    n = len(df)
    j = 1.0 if jit is None else float(jit)
    if which == "V1_base":
        return np.ones(n, bool), {}
    if which == "V2_dropTOM":
        return f_tom(df), {}
    if which == "V3_stacked":
        # جهتِ لرزش طوری انتخاب می‌شود که فیلتر **سخت‌تر** یا **شل‌تر** شود؛
        # هر دو جهت در main آزموده می‌شوند.
        thr = dict(er=BEST["er"] * j, r2=BEST["r2"] * j, hurst=BEST["hurst"] * j)
        m = f_tom(df) & f_er(df, thr["er"]) & f_r2(df, thr["r2"]) & f_hurst(df, thr["hurst"])
        return m, thr
    raise ValueError(which)


def evaluate(df, sig_raw, mask, tag, min_n=10):
    sig = sig_raw & mask
    return eval_sig(df, sig, CFG["side"], CFG["asset"], CFG["sl"], CFG["tp"],
                    CFG["maxhold"], min_n=min_n)


def halves_test(df, sig_raw, mask):
    """آزمونِ B: دو نیمهٔ زمانی؛ هر نیمه مستقل ارزیابی می‌شود."""
    n = len(df)
    mid = n // 2
    out = {}
    for name, sl_ in (("H1st", slice(0, mid)), ("H2nd", slice(mid, n))):
        d = df.iloc[sl_].reset_index(drop=True)
        s = (sig_raw & mask)[sl_]
        r = eval_sig(d, s, CFG["side"], CFG["asset"], CFG["sl"], CFG["tp"],
                     CFG["maxhold"], min_n=8)
        out[name] = r
    return out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_tf(CFG["asset"], CFG["tf"])
    print(f"data rows = {len(df)}")

    # سیگنالِ خامِ پایه (یک‌بار) + ماسکِ رژیمِ r2_lo
    sig_raw = reversal_day_signals(df, CFG["tf"], CFG["side"],
                                   n_open=CFG["n_open"], k_spike=CFG["k_spike"],
                                   slope_min_frac=CFG["slope_min"],
                                   entry_from_frac=CFG["win"][0],
                                   entry_to_frac=CFG["win"][1])
    sig_raw = sig_raw & regime_mask(df, CFG["reg"])
    print(f"raw signals (with regime) = {int(sig_raw.sum())}")

    res = {"config": CFG, "best_thresholds": BEST}

    # ---------------- سطحِ ۰: سه نسخه، سنجهٔ کامل
    print("\n--- level 0: three variants (full sample) ---")
    res["variants"] = {}
    for v in ("V1_base", "V2_dropTOM", "V3_stacked"):
        mask, thr = build_variant(df, v)
        r = evaluate(df, sig_raw, mask, v)
        if r:
            r["net_per_trade"] = round(r["net"] / max(r["n"], 1), 2)
        res["variants"][v] = r
        print(f"  {v:12s} {r}")

    # ---------------- آزمونِ A: لرزشِ آستانه روی V3
    print("\n--- test A: threshold jitter on V3 (does the edge survive?) ---")
    res["A_jitter"] = {}
    for j in (0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20):
        mask, thr = build_variant(df, "V3_stacked", jit=j)
        r = evaluate(df, sig_raw, mask, f"V3_j{j}")
        res["A_jitter"][f"x{j:.2f}"] = {"thr": {k: round(x, 4) for k, x in thr.items()},
                                        "res": r}
        flag = "—" if r is None else ("ACC" if r["passed"] else "rej")
        print(f"  jitter x{j:.2f}  thr={ {k: round(x,3) for k,x in thr.items()} }  "
              f"{flag} {r}")

    # لرزشِ تک‌فیلتری (کدام آستانه شکننده است؟)
    print("\n--- test A2: per-filter jitter (isolate the fragile threshold) ---")
    res["A2_per_filter"] = {}
    for key, fn in (("er", f_er), ("r2", f_r2), ("hurst", f_hurst)):
        res["A2_per_filter"][key] = {}
        for j in (0.85, 1.0, 1.15):
            thr = dict(BEST)
            thr[key] = BEST[key] * j
            mask = (f_tom(df) & f_er(df, thr["er"]) & f_r2(df, thr["r2"])
                    & f_hurst(df, thr["hurst"]))
            r = evaluate(df, sig_raw, mask, f"{key}x{j}")
            res["A2_per_filter"][key][f"x{j:.2f}"] = {"thr": round(thr[key], 4), "res": r}
            print(f"  {key:6s} thr={thr[key]:.4f} (x{j:.2f})  {r}")

    # ---------------- آزمونِ B: نیمه‌های زمانی
    print("\n--- test B: chronological halves (out-of-sample stability) ---")
    res["B_halves"] = {}
    for v in ("V1_base", "V2_dropTOM", "V3_stacked"):
        mask, _ = build_variant(df, v)
        h = halves_test(df, sig_raw, mask)
        res["B_halves"][v] = h
        print(f"  {v:12s} H1st={h['H1st']}")
        print(f"  {'':12s} H2nd={h['H2nd']}")

    with open(os.path.join(OUT_DIR, "_adjudicate_M15.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print("\nsaved -> results/_scan_S345/_adjudicate_M15.json")


if __name__ == "__main__":
    main()
