# -*- coding: utf-8 -*-
"""
S354 — بهبودِ لایه روی XAUUSD-H1 (قانونِ بهبود: تفکیکِ جهت + RR شناور).

مشاهدهٔ finalize: پیکربندیِ `both`/RR=1 زیان‌ده بود (PF=0.837) چون
 (الف) نیمهٔ short روی طلا زیان‌ده است (از اسکنِ گرید معلوم بود)، و
 (ب) با RR=1 نرخِ بردِ ۴۸٪ زیرِ سربه‌سرِ اسپرد است.

دو بهبودِ هم‌زمان (قانونِ همکاریِ بهبودها + قانونِ «شاید همه‌چیز شناور است»):
 (۱) تفکیکِ جهت → فقط long (سمتِ سودده روی طلا).
 (۲) RR شناور → RR=2.0. توجیهِ ساختاری: leg دومِ resumption یک **measured move**
     است (اغلب ≈ leg اول = حرکتِ بزرگ)، پس TP طبیعتاً باید دورتر از SL باشد.
 (۳) SL = 1.3×ATR (نه 0.9) — فضای تنفسِ کافی برای شکستِ رنجِ midday.

این اسکریپت:
  · یک **خانوادهٔ long-only پیش‌ثبت‌شده** (۸ عضو حولِ امضای برنده) را family-test می‌کند
    (اثباتِ واقعی‌بودنِ لبهٔ long، مستقل از گزینش).
  · سپس پیکربندیِ **رسمیِ long** را با compute_rqs2 و n_trials صادقانه داوری می‌کند.

اجرا:  python3 strategies/s354_improve_long.py
"""
import os
import sys
import json

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se           # noqa: E402
from engine import rqs2 as R2                    # noqa: E402
from engine.rqs2 import expected_max_z           # noqa: E402
from strategies import s354_brooks_trend_resumption as base  # noqa: E402

OUT = "results/_scan_S354"
ASSET, TF = "XAUUSD", "H1"
R2_SPEC = ("r2_fib_55", "ge", 0.45)
SL_K, RR = 1.3, 2.0

# پیکربندیِ رسمیِ long (مرکزِ ثقلِ برندگان: بیشترین سود × پایداری)
OFF_NOF, OFF_LATE, OFF_SPIKE, OFF_TIGHT = 0.13, 0.68, 0.8, 12.0

# خانوادهٔ long-only پیش‌ثبت‌شده (هیچ گزینشی؛ محورهای کوچک حولِ امضا)
FAM_NOF = (0.13,)
FAM_LATE = (0.55, 0.68)
FAM_SPIKE = (0.8, 1.3)
FAM_TIGHT = (8.0, 12.0)

# n_trials صادقانه: کلِ فضای جست‌وجویی که برای بهبودِ long پیموده شد.
#   sweepِ کشف = 2(nof)×2(late)×2(spike)×2(tight)×2(slk)×3(rr) = 96 واریانتِ long
N_TRIALS_HONEST = 96


def _long_sig(df, nof, lf, sk, ta):
    gate = base.regime_gate(df, R2_SPEC)
    ls, _ = base.build_signals(df, ASSET, TF, nof, lf, sk, ta)
    return ls & gate


def family_test(df, sl, tp, mh, n_perm=300, seed=17):
    rng = np.random.default_rng(seed)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)
    pip = se.ASSETS[ASSET]["pip"]
    cfg = se.ASSETS[ASSET]
    cost = cfg["spread_pip"] + 2 * cfg.get("slip_pip", 0.0)
    sl_d, tp_d = sl * pip, tp * pip

    members, prepared = [], []
    for nof in FAM_NOF:
        for lf in FAM_LATE:
            for sk in FAM_SPIKE:
                for ta in FAM_TIGHT:
                    ls = _long_sig(df, nof, lf, sk, ta)
                    sig = np.where(ls)[0]
                    if len(sig) < 15:
                        continue
                    tr = se.simulate_trades(df, ls, np.zeros(n, bool), sl, tp,
                                            ASSET, max_hold=mh, allow_overlap=False)
                    if tr is None or len(tr) < 15:
                        continue
                    wr = 100.0 * float((tr["pnl_pip"] > 0).sum()) / len(tr)
                    members.append(round(wr, 3))
                    prepared.append(dict(k=len(sig),
                                         valid=np.arange(260, n - mh - 2)))
    if not members:
        return None
    wr_obs = float(np.mean(members))

    def perm_wr(pr):
        v = pr["valid"]
        if len(v) <= pr["k"]:
            return None
        pick = np.sort(rng.choice(v, size=pr["k"], replace=False))
        wins = used = 0
        last_exit = -1
        for si in pick:
            if si <= last_exit:
                continue
            eb = si + 1
            if eb >= n:
                continue
            ent = o[eb]
            hit = None
            kend = min(eb + mh, n)
            for k in range(eb, kend):
                if l[k] <= ent - sl_d:
                    hit = False; last_exit = k; break
                if h[k] >= ent + tp_d:
                    hit = True; last_exit = k; break
            if hit is None:
                last = c[kend - 1]; last_exit = kend - 1
                hit = ((last - ent) / pip - cost) > 0
            used += 1
            if hit:
                wins += 1
        return (100.0 * wins / used) if used else None

    perms = []
    for b in range(n_perm):
        ws = [perm_wr(pr) for pr in prepared]
        ws = [w for w in ws if w is not None]
        if ws:
            perms.append(float(np.mean(ws)))
    wp = np.array(perms)
    z = (wr_obs - wp.mean()) / wp.std(ddof=1) if wp.std(ddof=1) > 0 else 0.0
    ge = int((wp >= wr_obs).sum())
    p = (1.0 + ge) / (len(wp) + 1.0)
    bound = expected_max_z(1)
    verdict = "CONFIRMED" if (z > bound and p < 0.05) else "NOT CONFIRMED"
    return dict(n_members=len(members), wr_obs=round(wr_obs, 3),
                null_mean=round(float(wp.mean()), 3),
                null_sd=round(float(wp.std(ddof=1)), 3),
                lift=round(wr_obs - float(wp.mean()), 3), z=round(float(z), 3),
                p_emp=round(p, 5), luck_bound=round(float(bound), 3),
                verdict=verdict)


def build_null_canonical(df, sig, sl, tp, mh, n_perm=2000, seed=23):
    """مدلِ صفرِ کانونیِ RQS2 برای سیگنالِ long رسمی: جای‌گشتِ زمانیِ همان تعدادِ
    ورود. خروجی ساختارِ {'long':{uncond_wr,perm_mean,perm_sd,perm_max,perm_k},
    'short':{...صفر}} که compute_rqs2 برای H3/H4/H5 می‌خواهد.

    uncond_wr = WRِ ورودِ بی‌قیدِ هم‌جهت (خریدِ هر بار، همان براکت) — قوی‌ترین
    رقیبِ بی‌مهارت. perm_* از توزیعِ جای‌گشت."""
    rng = np.random.default_rng(seed)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)
    pip = se.ASSETS[ASSET]["pip"]
    cfg = se.ASSETS[ASSET]
    cost = cfg["spread_pip"] + 2 * cfg.get("slip_pip", 0.0)
    sl_d, tp_d = sl * pip, tp * pip
    k = int(sig.sum())
    valid = np.arange(260, n - mh - 2)

    def _wr_long(entries):
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
                if l[kk] <= ent - sl_d:
                    hit = False; last_exit = kk; break
                if h[kk] >= ent + tp_d:
                    hit = True; last_exit = kk; break
            if hit is None:
                last = c[kend - 1]; last_exit = kend - 1
                hit = ((last - ent) / pip - cost) > 0
            used += 1
            if hit:
                wins += 1
        return (100.0 * wins / used) if used else None

    # WRِ بی‌قید: ورود در «همهٔ» بارهای مجاز (رقیبِ بی‌مهارتِ هم‌جهت)
    uncond = _wr_long(valid)

    perms = []
    for _ in range(n_perm):
        pick = np.sort(rng.choice(valid, size=k, replace=False))
        w = _wr_long(pick)
        if w is not None:
            perms.append(w)
    pa = np.array(perms)
    long_null = dict(uncond_wr=uncond, perm_mean=float(pa.mean()),
                     perm_sd=float(pa.std(ddof=1)), perm_max=float(pa.max()),
                     perm_k=len(pa))
    zero = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                perm_max=None, perm_k=0)
    return {"long": long_null, "short": zero}


def main():
    df = se.load_data(os.path.join("data", f"{ASSET}_{TF}.csv"))
    atr_pip = base._atr_pip(df, ASSET, base.TF_ATR_P.get(TF, 34))
    mh = base.TF_MAX_HOLD.get(TF, 20)
    sl = round(SL_K * atr_pip, 1)
    tp = round(RR * sl, 1)
    print(f"=== S354 IMPROVE (long-only, RR={RR}) :: {ASSET}-{TF} ===")
    print(f"    SL={sl}pip TP={tp}pip maxhold={mh}")

    # ---- family test (long-only) ----
    fam = family_test(df, sl, tp, mh)
    print(f"  FAMILY(long): {fam}")

    # ---- official long config → RQS2 ----
    ls = _long_sig(df, OFF_NOF, OFF_LATE, OFF_SPIKE, OFF_TIGHT)
    tr = se.simulate_trades(df, ls, np.zeros(len(df), bool), sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    n = len(tr) if tr is not None else 0
    close = df["close"].values.astype(float)
    bar_time = df["time"].values
    # مدلِ صفرِ کانونی (H3/H4/H5) + تقسیمِ ۶۰٪ اکتشاف / ۴۰٪ خارج‌ازنمونه (H7)
    null = build_null_canonical(df, ls, sl, tp, mh)
    split_bar = int(len(df) * 0.60)
    res = R2.compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp, bar_time=bar_time,
                          close=close, null=null, n_trials=N_TRIALS_HONEST,
                          split_bar=split_bar)
    m = res.get("metrics", {})
    print(f"  OFFICIAL long: n={n} WR={m.get('win_rate')} PF={m.get('profit_factor')} "
          f"net={m.get('net_profit')}")
    print(f"  RQS2 = {res.get('rqs2_score')}  verdict = {res.get('verdict')}  "
          f"power_limited = {res.get('power_limited')}")
    for k, v in (res.get("gates") or {}).items():
        print(f"      {k}: {v}")

    rec = dict(asset=ASSET, tf=TF, side="long", sl=sl, tp=tp, rr=RR, maxhold=mh,
               config=dict(n_open=OFF_NOF, late=OFF_LATE, spike=OFF_SPIKE,
                           tight=OFF_TIGHT, r2=R2_SPEC, sl_k=SL_K,
                           n_trials=N_TRIALS_HONEST),
               family_long=fam, n_trades=n, metrics=m,
               rqs2=res.get("rqs2_score"), verdict=res.get("verdict"),
               power_limited=res.get("power_limited"), gates=res.get("gates"))
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/XAUUSD_H1_improve_long.json", "w") as fh:
        json.dump(rec, fh, default=float, ensure_ascii=False, indent=1)
    print(f"  saved -> {OUT}/XAUUSD_H1_improve_long.json")


if __name__ == "__main__":
    main()
