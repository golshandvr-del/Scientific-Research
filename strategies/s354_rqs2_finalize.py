# -*- coding: utf-8 -*-
"""
S354 — داوریِ **RQS2 نهایی** روی پیکربندیِ رسمیِ `both` (XAUUSD-H1).

چرا این گام؟
------------
Family-test ثابت کرد لبهٔ resumption روی XAU-H1 **واقعی و مستقل** است
(z=4.82σ کل، z=3.65σ خارج از پنجره‌های زمان-محور). اما — دقیقاً مطابقِ پیشینهٔ
S346 — family-confirm شرطِ **لازم** است نه **کافی**. پذیرشِ رسمی مستلزم آن است که
پیکربندیِ **رسمیِ `both`** (بدونِ گزینشِ سمت) خودش از `engine.rqs2.compute_rqs2`
با همهٔ دروازه‌های H1..H10 و **n_trials صادقانه** عبور کند.

پیکربندیِ رسمی (نمایندهٔ خانواده، پیش‌ثبت‌شده — هیچ گزینشی):
  side = both  ·  r2_fib_55 ≥ 0.45  ·  SL = 1.3×ATR_pip  ·  RR = 1.0
  n_open_frac = 0.21 · late_from = 0.55 · spike_k = 0.8 · tight_atr = 8.0
  (مرکزِ ثقلِ خانواده: بیشترین n برای پایداریِ آماری)

n_trials صادقانه = 824 (کلِ واریانت‌های stage-1 اسکنِ گرید) — کم‌گفتنش تقلبِ H5 است.

اجرا:  python3 strategies/s354_rqs2_finalize.py
"""
import os
import sys
import json

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as R2                    # noqa: E402
from strategies import s354_brooks_trend_resumption as base  # noqa: E402

OUT = "results/_scan_S354"

ASSET, TF = "XAUUSD", "H1"
R2_SPEC = ("r2_fib_55", "ge", 0.45)
N_OPEN, LATE, SPIKE, TIGHT = 0.21, 0.55, 0.8, 8.0
SL_K, RR = 1.3, 1.0
N_TRIALS_HONEST = 824      # کلِ stage-1 اسکنِ گرید (results/_scan_S354/XAUUSD_H1.json)


def main():
    df = se.load_data(os.path.join("data", f"{ASSET}_{TF}.csv"))
    atr_pip = base._atr_pip(df, ASSET, base.TF_ATR_P.get(TF, 34))
    mh = base.TF_MAX_HOLD.get(TF, 20)
    sl = round(SL_K * atr_pip, 1)
    tp = round(RR * sl, 1)

    gate = base.regime_gate(df, R2_SPEC)
    ls, ss = base.build_signals(df, ASSET, TF, N_OPEN, LATE, SPIKE, TIGHT)
    ls, ss = ls & gate, ss & gate

    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=mh,
                            allow_overlap=False)
    n = len(tr) if tr is not None else 0
    print(f"=== S354 RQS2 FINALIZE :: {ASSET}-{TF} (official BOTH config) ===")
    print(f"    SL={sl}pip TP={tp}pip maxhold={mh}  n_trades={n}")
    if tr is None or n < 15:
        print("!!! too few trades")
        return

    close = df["close"].values.astype(float)
    bar_time = df["time"].values
    res = R2.compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp, bar_time=bar_time,
                          close=close, n_trials=N_TRIALS_HONEST)

    m = res.get("metrics", {})
    print(f"    WR={m.get('win_rate')}  PF={m.get('profit_factor')}  "
          f"net={m.get('net_profit')}")
    print(f"    RQS2 = {res.get('score')}   verdict = {res.get('verdict')}")
    print(f"    power_limited = {res.get('power_limited')}")
    print("    gates:")
    for k, v in (res.get("gates") or {}).items():
        print(f"      {k}: {v}")

    rec = dict(asset=ASSET, tf=TF, config=dict(
        side="both", r2=R2_SPEC, sl_k=SL_K, rr=RR, sl=sl, tp=tp,
        n_open=N_OPEN, late=LATE, spike=SPIKE, tight=TIGHT,
        n_trials=N_TRIALS_HONEST),
        n_trades=n, metrics=m, rqs2=res.get("score"),
        verdict=res.get("verdict"), power_limited=res.get("power_limited"),
        gates=res.get("gates"))
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/XAUUSD_H1_rqs2_finalize.json", "w") as fh:
        json.dump(rec, fh, default=float, ensure_ascii=False, indent=1)
    print(f"  saved -> {OUT}/XAUUSD_H1_rqs2_finalize.json")


if __name__ == "__main__":
    main()
