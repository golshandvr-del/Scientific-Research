# -*- coding: utf-8 -*-
"""
S345 — کاوشِ بهبود (قانونِ بهبود + قانونِ بی‌نهایت + قانونِ «همه‌چیز شناور»).

سه پرسشِ علمیِ باز پس از اسکنِ MTF:
  (پ۱) لایهٔ XAU-M15-long با RQS+ ۸۹.۸ پاس شد، اما ۴۴–۴۹٪ همپوشانی با لایه‌های
       زمان-محور (S139..S144) دارد و بخشِ مستقلش **باکیفیت‌تر** است
       (WR ۶۵.۰ / PF ۲.۵۶) در حالی که بخشِ همپوشان ضعیف‌تر است (WR ۵۶.۶ / PF ۱.۷۳).
       ⇒ آیا **حذفِ بخشِ ضعیفِ همپوشان** لایه را بهتر می‌کند یا فقط n را می‌کُشد؟
       (قانونِ سومِ همپوشانی: بخشِ همپوشان را به‌عنوان فیلتر بررسی کن.)
  (پ۲) M30 (و شاید H1/H4) فقط **G4** را می‌شکنند (`111101`) با n=۴۷ ⇒ کمبودِ نمونه،
       نه فقدانِ لبه. آیا با شل‌کردنِ ماشه (نه دستکاریِ TP/SL) n بالا می‌رود و G4 پاس می‌شود؟
  (پ۳) قانونِ «همه‌چیز شناور»: TP/SL **شناور بر پایهٔ ADR/ATR** (نه pipِ ثابت) — آیا
       RQS+ را بالاتر می‌برد؟ + تریلِ Brooks («trail your stop above the prior swing»).

⚠️ قیدِ ضدِ اشتباهِ رایجِ #۸: در همهٔ سناریوها **TP > SL** حفظ می‌شود (نسبت ≥ ۱.۲۵)؛
   هیچ WRای با کوچک‌کردنِ TP نسبت به SL خریداری نمی‌شود.

اجرا: PYTHONPATH=. python3 strategies/s345_improve_probe.py [M15|M30|ALL]
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
from strategies.s345_brooks_reversal_day import reversal_day_signals, load_tf, _atr
from strategies.s344_brooks_trend_from_open import _bars_per_day, _daily_atr_from_intraday
from strategies.s345_overlap_validate import in_time_layers, regime_mask, eval_sig

OUT_DIR = os.path.join(ROOT, "results", "_scan_S345")

# پیکربندیِ پایهٔ برندهٔ هر TF (از اسکنِ MTF)
BASE = {
    "M15": dict(asset="XAUUSD", tf="M15", side="long", n_open=4, k_spike=1.1,
                slope_min=0.05, win=(0.40, 0.95), reg="r2_lo", sl=240, tp=400, maxhold=40),
    "M30": dict(asset="XAUUSD", tf="M30", side="long", n_open=4, k_spike=1.1,
                slope_min=0.05, win=(0.40, 0.95), reg=None, sl=270, tp=460, maxhold=28),
}


def float_tpsl(df, tf, sl_mult, tp_mult, adr_lb=14):
    """TP/SL شناور بر پایهٔ ADR روز (قانونِ همه‌چیز شناور).
    خروجی بر حسبِ pip (طلا: pip=0.1$ ⇒ pip = دلار/۰.۱)."""
    dt = pd.to_datetime(df["time"], unit="s")
    day_id = dt.dt.floor("D").astype("int64").to_numpy()
    adr = _daily_atr_from_intraday(df, day_id, adr_lb)   # دلار
    pip = se.ASSETS["XAUUSD"]["pip"]
    adr_pip = adr / pip
    med = np.nanmedian(adr_pip[np.isfinite(adr_pip) & (adr_pip > 0)])
    adr_pip = np.where(np.isfinite(adr_pip) & (adr_pip > 0), adr_pip, med)
    return adr_pip * sl_mult, adr_pip * tp_mult


def probe(tf_key):
    B = BASE[tf_key]
    df = load_tf(B["asset"], B["tf"])
    dt = pd.to_datetime(df["time"], unit="s")
    tmask = in_time_layers(dt)
    out = {}

    def base_sig(n_open=None, k_spike=None, slope_min=None, win=None, reg="__base__"):
        s = reversal_day_signals(df, B["tf"], B["side"],
                                 n_open=n_open or B["n_open"],
                                 k_spike=B["k_spike"] if k_spike is None else k_spike,
                                 slope_min_frac=B["slope_min"] if slope_min is None else slope_min,
                                 entry_from_frac=(win or B["win"])[0],
                                 entry_to_frac=(win or B["win"])[1])
        r = B["reg"] if reg == "__base__" else reg
        return s & regime_mask(df, r)

    sig0 = base_sig()
    print(f"\n########## {B['asset']} {B['tf']} — improvement probe ##########", flush=True)
    print(f"BASE: {eval_sig(df, sig0, B['side'], B['asset'], B['sl'], B['tp'], B['maxhold'])}", flush=True)

    # ---------- پ۱: نقشِ بخشِ همپوشان (فیلترِ مثبت یا منفی؟) ----------
    print("\n--- P1: overlap-part as FILTER (drop weak overlapping subset) ---", flush=True)
    p1 = {}
    for nm, m in [("drop_overlap(indep only)", ~tmask),
                  ("keep_overlap only", tmask),
                  ("drop_monday_only", ~(pd.DatetimeIndex(dt).dayofweek == 0)),
                  ("drop_overnight_only", ~np.isin(pd.DatetimeIndex(dt).hour, [22, 23])),
                  ("drop_TOM_only", ~(pd.DatetimeIndex(dt).day <= 3))]:
        r = eval_sig(df, sig0 & np.asarray(m), B["side"], B["asset"], B["sl"], B["tp"], B["maxhold"])
        p1[nm] = r
        print(f"  {nm:28}: {r}", flush=True)
    out["P1_overlap_filter"] = p1

    # ---------- پ۲: افزایشِ نمونه با شل‌کردنِ ماشه (نه دستکاریِ TP/SL) ----------
    print("\n--- P2: raise sample size via trigger relaxation (TP/SL untouched) ---", flush=True)
    p2 = {}
    for k in [0.7, 0.85, 1.1, 1.3]:
        for sm in [0.02, 0.05, 0.09]:
            for w in [(0.20, 0.97), (0.40, 0.95), (0.30, 0.90)]:
                s = base_sig(k_spike=k, slope_min=sm, win=w)
                if s.sum() < 30:
                    continue
                r = eval_sig(df, s, B["side"], B["asset"], B["sl"], B["tp"], B["maxhold"], min_n=30)
                if r is None:
                    continue
                key = f"k={k} sm={sm} win={w}"
                p2[key] = r
                flag = "ACC" if r["passed"] else "rej"
                print(f"  {key:34} {flag} RQS={r['rqs']:5.1f} G[{r['gates']}] n={r['n']:4} WR={r['wr']:5.2f} PF={r['pf']}", flush=True)
    out["P2_relax"] = p2

    # ---------- پ۳: TP/SL شناور بر ADR + تریلِ Brooks ----------
    print("\n--- P3: floating TP/SL on ADR (+ Brooks trail) — ratio always > 1 ---", flush=True)
    p3 = {}
    n = len(df)
    long_sig = sig0 if B["side"] == "long" else np.zeros(n, bool)
    short_sig = sig0 if B["side"] == "short" else np.zeros(n, bool)
    for (slm, tpm) in [(0.34, 0.55), (0.42, 0.68), (0.55, 0.95), (0.28, 0.47), (0.47, 0.82)]:
        sl_a, tp_a = float_tpsl(df, B["tf"], slm, tpm)
        if np.nanmedian(tp_a) <= np.nanmedian(sl_a) * 1.25:
            continue    # قیدِ ضدِ #۸
        for trail in [None, 0.6, 1.0]:
            tr_pip = None if trail is None else float(np.nanmedian(sl_a) * trail)
            trd = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_a, tp_pip=tp_a,
                                     asset=B["asset"], max_hold=B["maxhold"],
                                     allow_overlap=False, trail_pip=tr_pip)
            if trd is None or len(trd) < 30:
                continue
            r = rqs.compute_rqs(trd, B["asset"], sl_pip=float(np.nanmedian(sl_a)),
                                tp_pip=float(np.nanmedian(tp_a)))
            m = r["metrics"]
            pf = m["profit_factor"]
            rec = dict(rqs=round(r["rqs_score"], 1), passed=bool(r["passed"]),
                       gates="".join("1" if r["gates"][g] else "0"
                                     for g in ["G0", "G1", "G2", "G3", "G4", "G5"]),
                       n=int(m["n_trades"]), wr=round(m["win_rate"], 2),
                       pf=round(pf, 3) if np.isfinite(pf) else 999.0,
                       net=round(m["net_profit"], 1),
                       sl_med=round(float(np.nanmedian(sl_a)), 1),
                       tp_med=round(float(np.nanmedian(tp_a)), 1))
            key = f"ADR sl={slm} tp={tpm} trail={trail}"
            p3[key] = rec
            flag = "ACC" if rec["passed"] else "rej"
            print(f"  {key:32} {flag} RQS={rec['rqs']:5.1f} G[{rec['gates']}] n={rec['n']:4} "
                  f"WR={rec['wr']:5.2f} PF={rec['pf']} SL/TP={rec['sl_med']}/{rec['tp_med']}", flush=True)
    out["P3_floating_tpsl"] = p3

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"_improve_{B['tf']}.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\nsaved -> results/_scan_S345/_improve_{B['tf']}.json", flush=True)
    return out


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "M15").upper()
    if which == "ALL":
        for k in BASE:
            probe(k)
    else:
        probe(which)
