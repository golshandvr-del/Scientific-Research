# -*- coding: utf-8 -*-
"""
S354 — اعتبارسنجیِ همپوشانیِ اجباری برای «Trend Resumption Day» روی XAUUSD-H1.

چرا حیاتی است؟ قانونِ همپوشانیِ اجباریِ پروژه می‌گوید پیش از پذیرشِ هر لایه باید
دقیقاً بدانیم با کدام لایه/لایه‌ها و چند درصد همپوشانی دارد، و اگر همپوشانیِ جزئی بود،
امکانِ استفاده از بخشِ همپوشان به‌عنوان فیلتر بررسی شود.

S354 یک لبهٔ **زمان‌آگاه** است (ورود در «ساعتِ پایانیِ روز» بعد از یک رنجِ میانی).
بنابراین بزرگ‌ترین خطرِ همپوشانی، لایه‌های **زمان‌محورِ** موجودِ پروژه (S139..S144) و
هفت لایهٔ ساختاریِ کارتِ XAUUSD-H1 (S341/S333/S313/S328/S327/S323/S312/S335) است.

سه آزمون:
 (۱) درصدِ همپوشانیِ کندلیِ سیگنال‌ها با ماسکِ زمان-محورِ استانداردِ پروژه (in_time_layers).
 (۲) لبهٔ مستقل در سطحِ خانواده: family-permutation فقط روی سیگنال‌های *خارج* از
     پنجره‌های زمان-محور. اگر لبهٔ خانواده آنجا هم جامد ماند ⇒ لبهٔ نو (نه بازتولید).
 (۳) امضای ساعتِ ورود در برابرِ امضای زمانیِ لایه‌های H1 (تفکیکِ ساختاری).

اجرا: PYTHONPATH=. python3 strategies/s354_overlap_validate.py
"""
import os
import sys
import json
import collections

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from strategies import s354_brooks_trend_resumption as base
from strategies import s354_family as fam

OUT = os.path.join(ROOT, "results", "_scan_S354", "_overlap_validate.json")

# پارامترهای برندهٔ کارتِ XAUUSD-H1 (از family-confirm)
ASSET, TF = "XAUUSD", "H1"
R2_SPEC = ("r2_fib_55", "ge", 0.45)


def in_time_layers(dt_series):
    """ماسکِ کندل‌های داخلِ پنجره‌های زمان-محورِ موجودِ پروژه (S139..S144).
    عیناً مطابقِ روشِ S169/S344."""
    dt = pd.DatetimeIndex(dt_series)
    hour = dt.hour
    dow = dt.dayofweek
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


def build_family_signals(df, extra_mask=None):
    """سیگنال‌های همهٔ اعضای خانوادهٔ S354 روی این TF (با گیتِ r2 مشترک).
    خروجی: dict[member_key] -> (long_sig, short_sig)."""
    gate = base.regime_gate(df, R2_SPEC)
    if extra_mask is not None:
        gate = gate & extra_mask
    out = {}
    for i, g in enumerate(fam.members()):
        ls, ss = base.build_signals(df, ASSET, TF, g["n_open_frac"],
                                    g["late_from"], g["spike_k"], g["tight_atr"])
        out[i] = (ls & gate, ss & gate)
    return out


def union_sig(fam_sigs):
    """اجتماعِ همهٔ سیگنال‌های خانواده (برای سنجشِ همپوشانیِ کندلی)."""
    any_long = None
    any_short = None
    for (ls, ss) in fam_sigs.values():
        any_long = ls if any_long is None else (any_long | ls)
        any_short = ss if any_short is None else (any_short | ss)
    return any_long | any_short


def main():
    df = se.load_data(os.path.join(ROOT, "data", f"{ASSET}_{TF}.csv"))
    dt = pd.to_datetime(df["time"].values, unit="s")
    tmask = in_time_layers(dt)

    # ---- (۱) همپوشانیِ کندلیِ اجماعِ خانواده با ماسکِ زمان-محور ----
    fam_sigs = build_family_signals(df)
    u = union_sig(fam_sigs)
    sig_idx = np.where(u)[0]
    n_total = len(sig_idx)
    n_in = int(tmask[sig_idx].sum()) if n_total else 0
    overlap_pct = round(100.0 * n_in / n_total, 1) if n_total else 0.0

    # امضای ساعتِ ورود
    hrs = pd.DatetimeIndex(dt[sig_idx]).hour
    hour_hist = dict(sorted(collections.Counter(hrs).items()))
    # سهمِ ورودها در «ساعتِ پایانیِ روز» (16..23 UTC)
    late_share = round(100.0 * sum(v for h, v in hour_hist.items() if 16 <= h <= 23)
                       / n_total, 1) if n_total else 0.0

    print("===== S354 XAUUSD-H1 — OVERLAP VALIDATE =====")
    print(f"  union family signals = {n_total}")
    print(f"  overlap with time-layers S139..S144 = {overlap_pct}%")
    print(f"  entry-hour histogram (UTC) = {hour_hist}")
    print(f"  share of entries in late-day window 16..23 UTC = {late_share}%")

    # ---- (۲) لبهٔ مستقل در سطحِ خانواده: خارج از پنجره‌های زمان-محور ----
    print("\n  --- family edge OUTSIDE time-layer windows (independent edge) ---")
    indep_rec = fam.run(ASSET, TF, n_perm=300, extra_mask=(~tmask),
                        label="indep_outside_time_layers")
    indep = None
    if indep_rec is not None:
        indep = {k: indep_rec.get(k) for k in
                 ("n_members", "n_trades_total", "wr_obs", "null_wr_mean",
                  "lift_wr", "z_wr", "p_emp_wr", "luck_bound_n1", "verdict")}

    out = dict(
        asset=ASSET, tf=TF,
        union_signals=n_total,
        overlap_with_time_layers_pct=overlap_pct,
        entry_hour_hist={int(k): int(v) for k, v in hour_hist.items()},
        late_day_share_pct=late_share,
        independent_family=indep,
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
