# -*- coding: utf-8 -*-
"""
S354 — بررسیِ حیاتیِ CAUSAL بودن (کشفِ look-ahead در late_start).

کشف: در نسخهٔ اصلیِ build_signals، `late_start = ds + round(0.68 * ndlen)` که
`ndlen` = طولِ **کلِ روز** است — یعنی در زمانِ زنده هنوز معلوم نیست (non-causal /
look-ahead). این اسکریپت نسخهٔ کاملاً causal را می‌سازد که پنجرهٔ پایانی را با یک
**آستانهٔ ساعتِ ثابتِ UTC** تعریف می‌کند (که طبقِ توزیعِ واقعی، late_start تقریباً
همیشه ساعتِ ۱۶–۱۷ UTC است) و RQS2 را دوباره می‌سنجد.

اگر لبه با نسخهٔ causal هم ACCEPT بماند ⇒ لبه واقعی است و فقط باید پورتِ TS را
causal کرد. اگر افت کرد ⇒ لبه به look-ahead آلوده بوده و باید صادقانه رد شود.
"""
import os
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs2 as R2
from strategies import s354_brooks_trend_resumption as base

ASSET, TF = "XAUUSD", "H1"
OUT = "results/_scan_S354"


def build_signals_causal(df, asset, tf, n_open_frac, late_hour, spike_k, tight_atr):
    """نسخهٔ کاملاً causal: پنجرهٔ پایانی با آستانهٔ ساعتِ ثابتِ UTC (نه نسبتِ طولِ کلِ روز).
    همه‌چیزِ دیگر منطبق با build_signals اصلی."""
    n = len(df)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    dtt = pd.to_datetime(df["time"].values, unit="s")
    dayid = dtt.floor("D").astype("int64").values
    hours = dtt.hour.values

    p = base._nearest_fib(base.TF_ATR_P.get(tf, 34))
    atr = np.asarray(ib.compute(f"atr_fib_{p}", df), dtype=float)
    bpd = base.bars_per_day(tf)
    n_open = max(2, round(n_open_frac * bpd))

    long_sig = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        d = dayid[i]
        j = i
        while j < n and dayid[j] == d:
            j += 1
        ndlen = j - i
        if ndlen >= n_open + 4:
            ds = i
            open_end = ds + n_open
            init_ret = c[open_end - 1] - o[ds]
            init_dir = np.sign(init_ret)
            leg1 = abs(init_ret)
            atr_ref = atr[open_end - 1] if open_end - 1 < n and np.isfinite(atr[open_end - 1]) else np.nan
            if init_dir > 0 and np.isfinite(atr_ref) and atr_ref > 0 and leg1 >= spike_k * atr_ref:
                mid_lo_idx = open_end
                # پنجرهٔ پایانیِ CAUSAL: اولین کندلی که ساعتش ≥ late_hour است
                late_candidates = np.where((np.arange(n) >= open_end + 1) &
                                           (np.arange(n) < j) & (hours >= late_hour) &
                                           (np.arange(n) >= ds))[0]
                late_candidates = late_candidates[(late_candidates >= ds) & (late_candidates < j)]
                if late_candidates.size > 0:
                    late_start = int(late_candidates[0])
                    mid_hi_idx = max(open_end + 1, late_start)
                    if mid_hi_idx - mid_lo_idx >= 2 and mid_hi_idx < j:
                        for t in range(max(mid_hi_idx, late_start), j):
                            mseg_hi = np.max(h[mid_lo_idx:t]) if t > mid_lo_idx else np.nan
                            mseg_lo = np.min(l[mid_lo_idx:t]) if t > mid_lo_idx else np.nan
                            if not (np.isfinite(mseg_hi) and np.isfinite(mseg_lo)):
                                continue
                            mid_range = mseg_hi - mseg_lo
                            atr_now = atr[t - 1] if (t - 1) < n and np.isfinite(atr[t - 1]) else atr_ref
                            if not (np.isfinite(atr_now) and atr_now > 0):
                                continue
                            if mid_range > tight_atr * atr_now or mid_range <= 0:
                                continue
                            if c[t] > mseg_hi:
                                long_sig[t] = True
                                break
        i = j
    return long_sig


def main():
    df = se.load_data(os.path.join("data", f"{ASSET}_{TF}.csv"))
    atr_pip = base._atr_pip(df, ASSET, base.TF_ATR_P.get(TF, 34))
    mh = base.TF_MAX_HOLD.get(TF, 20)
    sl = round(1.3 * atr_pip, 1)
    tp = round(2.0 * sl, 1)
    gate = base.regime_gate(df, ("r2_fib_55", "ge", 0.45))

    print(f"=== S354 CAUSAL CHECK :: {ASSET}-{TF} (fixed-hour late window) ===", flush=True)
    print(f"    SL={sl}pip TP={tp}pip maxhold={mh}", flush=True)

    # جاروبِ آستانهٔ ساعت (causal) — انتخابِ صادقانه بر پایهٔ توزیعِ late_start (۱۶/۱۷)
    for late_hour in (15, 16, 17):
        ls = build_signals_causal(df, ASSET, TF, 0.13, late_hour, 0.8, 12.0) & gate
        tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), sl, tp,
                                ASSET, max_hold=mh, allow_overlap=False)
        if tr is None or len(tr) < 20:
            print(f"  late_hour={late_hour}: too few trades ({0 if tr is None else len(tr)})")
            continue
        cap, _ = se.run_capital(tr, ASSET)
        n = len(tr)
        wr = 100.0 * float((tr["pnl_pip"] > 0).sum()) / n
        print(f"  late_hour={late_hour}: n={n} WR={wr:.2f} PF={cap['profit_factor']:.3f} "
              f"net={cap['net_profit']:.1f}", flush=True)

    # RQS2 نهایی روی بهترین آستانهٔ causal (۱۶)
    print("\n  --- RQS2 on CAUSAL late_hour=16 ---", flush=True)
    ls = build_signals_causal(df, ASSET, TF, 0.13, 16, 0.8, 12.0) & gate
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), sl, tp,
                            ASSET, max_hold=mh, allow_overlap=False)
    # null کانونی
    from strategies import s354_improve_long as imp
    null = imp.build_null_canonical(df, ls, sl, tp, mh)
    res = R2.compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                          bar_time=df["time"].values, close=df["close"].values,
                          null=null, n_trials=96, split_bar=int(len(df) * 0.60))
    m = res.get("metrics", {})
    print(f"  n={len(tr)} WR={m.get('win_rate')} PF={m.get('profit_factor')} net={m.get('net_profit')}")
    print(f"  RQS2 = {res.get('rqs2_score')}  verdict = {res.get('verdict')}")
    print(f"  skill_z={m.get('skill_z')} lift={m.get('skill_lift_pp')} OOS={m.get('oos')}")
    for k, v in (res.get("gates") or {}).items():
        print(f"      {k}: {v}")

    import json
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/XAUUSD_H1_causal_check.json", "w") as fh:
        json.dump(dict(rqs2=res.get("rqs2_score"), verdict=res.get("verdict"),
                       n=len(tr), metrics=m, gates=res.get("gates"),
                       late_hour=16), fh, default=float)
    print(f"  saved -> {OUT}/XAUUSD_H1_causal_check.json")


if __name__ == "__main__":
    main()
