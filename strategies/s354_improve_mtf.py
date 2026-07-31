# -*- coding: utf-8 -*-
"""
S354 — اسکنِ **بهبودِ MTF** (قانونِ مولتی‌تایم‌فریم + قانونِ «شاید همه‌چیز شناور است»).

مشاهدهٔ XAUUSD-H1: با تفکیکِ جهت (long) + RR=2.0 → RQS2=79.5 ACCEPT.
اکنون طبقِ قانونِ MTF باید **همان خانوادهٔ بهبود** روی همهٔ TFها و هر دو ارز آزموده شود.
هر کارت ممکن است بهبودِ متناسبِ خود را بخواهد (SL_k/RR/side)، پس برای هر کارت:

  ۱) هر دو جهت (long-only و short-only) جدا آزموده می‌شود (چون روی طلا long و روی
     یورو short سودده بود ⇒ فرضِ ثابتِ جهت اشتباه است).
  ۲) sweepِ کوچکِ صادقانه: SL_k∈{0.9,1.3} × RR∈{1.0,1.5,2.0} × امضای سیگنالِ
     ثابتِ کارت-محور (nof/late/spike/tight از مرکزِ ثقلِ اسکنِ گرید همان کارت).
  ۳) از میانِ واریانت‌های **سودده**، بهترین بر پایهٔ PF×√n انتخاب و با
     compute_rqs2 (+ null کانونی + split_bar 60٪) داوری می‌شود.
  ۴) n_trials صادقانه = تعدادِ کلِ واریانت‌های sweep (2 side × 2 slk × 3 rr = 12).

خروجی هر کارت در results/_scan_S354/<ASSET>_<TF>_improve.json ذخیره و لاگ می‌شود
(قانونِ اندک‌اندک: مرحله‌به‌مرحله).

اجرا:  python3 strategies/s354_improve_mtf.py [ASSET TF] ...
       بدونِ آرگومان → همهٔ ۱۰ کارت.
"""
import os
import sys
import json
import itertools

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as R2                    # noqa: E402
from strategies import s354_brooks_trend_resumption as base  # noqa: E402

OUT = "results/_scan_S354"
R2_SPEC = ("r2_fib_55", "ge", 0.45)

# امضای سیگنالِ کارت-محور (مرکزِ ثقلِ اسکنِ گرید). اگر کارت خاصی امضای بهتری
# داشت، همان‌جا override می‌شود. پیش‌فرض همان امضای برندهٔ H1.
CARD_SIG = {
    # asset-tf: (nof, late, spike, tight)
    "XAUUSD-M5":  (0.13, 0.68, 0.8, 12.0),
    "XAUUSD-M15": (0.13, 0.68, 0.8, 12.0),
    "XAUUSD-M30": (0.13, 0.68, 0.8, 12.0),
    "XAUUSD-H1":  (0.13, 0.68, 0.8, 12.0),
    "XAUUSD-H4":  (0.13, 0.68, 0.8, 12.0),
    "EURUSD-M5":  (0.13, 0.68, 0.8, 12.0),
    "EURUSD-M15": (0.13, 0.68, 0.8, 12.0),
    "EURUSD-M30": (0.13, 0.68, 0.8, 12.0),
    "EURUSD-H1":  (0.13, 0.68, 0.8, 12.0),
    "EURUSD-H4":  (0.13, 0.68, 0.8, 12.0),
}

SL_K_GRID = (0.9, 1.3)
RR_GRID = (1.0, 1.5, 2.0)
N_TRIALS_HONEST = 2 * len(SL_K_GRID) * len(RR_GRID)   # 2 side × 2 × 3 = 12


def _sig(df, asset, tf, side):
    """سیگنالِ یک‌جهته (long یا short) با گیتِ رژیمِ r2≥0.45."""
    nof, lf, sk, ta = CARD_SIG[f"{asset}-{tf}"]
    gate = base.regime_gate(df, R2_SPEC)
    ls, ss = base.build_signals(df, asset, tf, nof, lf, sk, ta)
    if side == "long":
        return (ls & gate), np.zeros(len(df), bool)
    return np.zeros(len(df), bool), (ss & gate)


def build_null_canonical(df, asset, entries_bool, sl, tp, mh, side,
                         n_perm=400, seed=23):
    """مدلِ صفرِ کانونیِ RQS2 برای سیگنالِ یک‌جهته: جای‌گشتِ زمانیِ همان تعدادِ ورود."""
    rng = np.random.default_rng(seed)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = cfg["pip"]
    cost = cfg["spread_pip"] + 2 * cfg.get("slip_pip", 0.0)
    sl_d, tp_d = sl * pip, tp * pip
    k = int(entries_bool.sum())
    valid = np.arange(260, n - mh - 2)

    def _wr(entries):
        wins = used = 0
        last_exit = -1
        for si in entries:
            if si <= last_exit:
                continue
            eb = si + 1
            if eb >= n:
                continue
            ent = o[eb]
            hit = None
            kend = min(eb + mh, n)
            for kk in range(eb, kend):
                if side == "long":
                    if l[kk] <= ent - sl_d:
                        hit = False; last_exit = kk; break
                    if h[kk] >= ent + tp_d:
                        hit = True; last_exit = kk; break
                else:
                    if h[kk] >= ent + sl_d:
                        hit = False; last_exit = kk; break
                    if l[kk] <= ent - tp_d:
                        hit = True; last_exit = kk; break
            if hit is None:
                last = c[kend - 1]; last_exit = kend - 1
                if side == "long":
                    hit = ((last - ent) / pip - cost) > 0
                else:
                    hit = ((ent - last) / pip - cost) > 0
            used += 1
            if hit:
                wins += 1
        return (100.0 * wins / used) if used else None

    uncond = _wr(valid)
    perms = []
    for _ in range(n_perm):
        pick = np.sort(rng.choice(valid, size=k, replace=False))
        w = _wr(pick)
        if w is not None:
            perms.append(w)
    pa = np.array(perms)
    side_null = dict(uncond_wr=uncond, perm_mean=float(pa.mean()),
                     perm_sd=float(pa.std(ddof=1)), perm_max=float(pa.max()),
                     perm_k=len(pa))
    zero = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                perm_max=None, perm_k=0)
    if side == "long":
        return {"long": side_null, "short": zero}
    return {"long": zero, "short": side_null}


def scan_card(asset, tf):
    path = os.path.join("data", f"{asset}_{tf}.csv")
    if not os.path.exists(path):
        print(f"  [skip] {asset}-{tf}: no data", flush=True)
        return None
    df = se.load_data(path)
    atr_pip = base._atr_pip(df, asset, base.TF_ATR_P.get(tf, 34))
    mh = base.TF_MAX_HOLD.get(tf, 20)
    print(f"=== S354 IMPROVE-MTF :: {asset}-{tf} (bars={len(df)}, atr={atr_pip:.1f}pip) ===",
          flush=True)

    # مرحلهٔ ۱: sweepِ صادقانه، جمعِ واریانت‌های سودده
    cands = []
    for side, slk, rr in itertools.product(("long", "short"), SL_K_GRID, RR_GRID):
        ls, ss = _sig(df, asset, tf, side)
        sl = round(slk * atr_pip, 1)
        tp = round(rr * sl, 1)
        tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh,
                                allow_overlap=False)
        if tr is None or len(tr) < 40:
            continue
        cap, _ = se.run_capital(tr, asset)
        pf = float(cap["profit_factor"]); net = float(cap["net_profit"])
        n = len(tr)
        wr = 100.0 * float((tr["pnl_pip"] > 0).sum()) / n
        if pf > 1.0 and net > 0:
            key = pf * (n ** 0.5)
            cands.append((key, side, slk, rr, sl, tp, n, wr, pf, net))

    if not cands:
        print("  no profitable long/short variant → card NOT improvable this pass",
              flush=True)
        rec = dict(asset=asset, tf=tf, verdict="NO_PROFITABLE_VARIANT",
                   n_cands=0)
        _save(asset, tf, rec)
        return rec

    cands.sort(reverse=True)
    _, side, slk, rr, sl, tp, n0, wr0, pf0, net0 = cands[0]
    print(f"  best profitable: side={side} slk={slk} rr={rr} "
          f"n={n0} wr={wr0:.1f} pf={pf0:.3f} net={net0:.0f}", flush=True)

    # مرحلهٔ ۲: داوریِ RQS2 روی همان پیکربندی
    ls, ss = _sig(df, asset, tf, side)
    entries = ls if side == "long" else ss
    tr = se.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=mh,
                            allow_overlap=False)
    null = build_null_canonical(df, asset, entries, sl, tp, mh, side)
    split_bar = int(len(df) * 0.60)
    res = R2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp,
                          bar_time=df["time"].values,
                          close=df["close"].values, null=null,
                          n_trials=N_TRIALS_HONEST, split_bar=split_bar)
    m = res.get("metrics", {})
    verdict = res.get("verdict")
    score = res.get("rqs2_score")
    print(f"  RQS2 = {score}  verdict = {verdict}  "
          f"(skill_z={m.get('skill_z')} lift={m.get('skill_lift_pp')})", flush=True)
    gates = res.get("gates") or {}
    print("  gates:", {k: v for k, v in gates.items()}, flush=True)

    rec = dict(asset=asset, tf=tf, side=side, sl_k=slk, rr=rr, sl=sl, tp=tp,
               maxhold=mh, sig=CARD_SIG[f"{asset}-{tf}"],
               n_trials=N_TRIALS_HONEST, n_trades=len(tr), metrics=m,
               rqs2=score, verdict=verdict, gates=gates)
    _save(asset, tf, rec)
    return rec


def _save(asset, tf, rec):
    os.makedirs(OUT, exist_ok=True)
    fn = f"{OUT}/{asset}_{tf}_improve.json"
    with open(fn, "w") as fh:
        json.dump(rec, fh, default=float, ensure_ascii=False, indent=1)
    print(f"  saved -> {fn}", flush=True)


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        pairs = [(args[i], args[i + 1]) for i in range(0, len(args) - 1, 2)]
    else:
        pairs = [(a, t) for a in ("XAUUSD", "EURUSD")
                 for t in ("M5", "M15", "M30", "H1", "H4")]
    for asset, tf in pairs:
        scan_card(asset, tf)
        print("", flush=True)


if __name__ == "__main__":
    main()
