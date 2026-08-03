# -*- coding: utf-8 -*-
"""
S373 — «لایهٔ کانالِ ابزارمحور» (Instrument-Native Channel Breakout)

پیش‌ثبت: results/S373_PREREG_instrument_native_channel.md  (commit پیش از این فایل)

═══════════════════════════════════════════════════════════════════════════
ایده در یک خط
═══════════════════════════════════════════════════════════════════════════
قانونِ §۴ (تولید در S371، آزمونِ پیش‌ثبت‌شده در S372 روی AUDUSD/USDCHF) می‌گوید
منطقِ درستِ شکستِ کانال **به کلاسِ ابزار وابسته است**:

      XAUUSD (کالا، روندِ پرشتاب)  → فقط شاخهٔ هم‌جهت   ⇒ gate=False
      EURUSD (ارز، میانگین‌گَرد)    → قاعدهٔ کاملِ Brooks ⇒ gate=True

هر لایهٔ کانال‌محورِ این فصل تا امروز منطقِ **یکسان** روی هر دو ابزار اجرا کرد،
یعنی روی یکی از دو ابزار منطقِ غلط. این نخستین لایه‌ای است که منطق را
برحسبِ ابزار انتخاب می‌کند.

═══════════════════════════════════════════════════════════════════════════
چه چیزی *جدید* نیست — و این مهم‌ترین ویژگیِ این فایل است
═══════════════════════════════════════════════════════════════════════════
* `member_signals` عیناً از S366 وارد می‌شود — یک خط منطقِ سیگنال بازنویسی نشد.
* خانواده (FAM_K/FAM_M/FAM_S)، بریکتِ هر عضو، warmup و افقِ نگهداری: دست‌نخورده.
* افقِ نگهداری از median channel duration همان کارت استخراج می‌شود (نه جدولِ ثابت).
* آمارهٔ کارت = میانگینِ خانواده ⇒ هیچ عضوی انتخاب نمی‌شود ⇒ چندگانگیِ درون‌کارت=۱.
* تنها تفاوت با S366: مقدارِ `gate` برحسبِ ابزار، که از قانونِ §۴ می‌آید (آزموده
  روی AUDUSD/USDCHF) نه از عملکردِ XAUUSD/EURUSD ⇒ هزینهٔ انتخاب **صفر**.

═══════════════════════════════════════════════════════════════════════════
ادغامِ دو ابزار — در فضای بازده، نه فضای پارامتر
═══════════════════════════════════════════════════════════════════════════
سودِ خالصِ پروژه = جمعِ دو ارز ⇒ آمارهٔ لایه روی حوضِ ادغام‌شده محاسبه می‌شود.

⚠️ درسِ S370 رعایت می‌شود: ادغام روی **R هر معامله** (فضای بازده) انجام می‌شود،
   نه با میانگین‌گیریِ بریکت‌ها. در S370 ثابت شد `E[f(b̄)] ≠ E̅[f(b)]` و
   میانگین‌گیریِ پارامتر می‌تواند علامتِ لبه را عوض کند.

ادغام دو سطح دارد و هر دو ثبت می‌شوند:
   ۱) `fam_pooled`  = میانگینِ meanR روی **همهٔ اعضای هر دو ابزار** (۲۴ عضو)
   ۲) `trade_pooled`= میانگینِ R روی **حوضِ همهٔ معاملاتِ** هر دو ابزار
سطحِ ۱ آمارهٔ پذیرش است (هم‌ارزِ S366)؛ سطحِ ۲ برای تشخیصِ اثرِ وزن‌دهی است
(همان اثری که در S370 کشف شد).

═══════════════════════════════════════════════════════════════════════════
بندهای قفل — از پیش‌ثبت، در کد به‌صورت ثابت
═══════════════════════════════════════════════════════════════════════════
"""
import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from engine.rqs2 import expected_max_z                                   # noqa: E402
from strategies.s366_stairs_channel_breakout import (                    # noqa: E402
    channel_context, member_signals, _perm_meanR,
    FAM_K, FAM_M, FAM_S, MIN_TRADES, HORIZON_MULT, MAX_HOLD_CAP)

OUT = "results/_scan_S373"
N_PERM = 400

# ⛔ قفلِ منطق (بندِ ۱ پیش‌ثبت). این نگاشت از قانونِ §۴ می‌آید و **تغییرپذیر نیست**.
#    اگر لایه شکست خورد، نگاشتِ معکوس/ترکیبی آزموده نمی‌شود — آن جست‌وجو در
#    فضای ۲ حالته است و قبضِ چندگانگی دارد.
GATE_BY_ASSET = {"XAUUSD": False, "EURUSD": True}

# ⛔ شمارشِ آزمون و آستانه — پیش از اجرا در پیش‌ثبت تثبیت شد (§۴ پیش‌ثبت).
N_TRIALS = 107
Z_LUCK = expected_max_z(N_TRIALS)          # = 2.554

# تایم‌فریم‌هایی که **هر دو** ابزار داده دارند.
SHARED_TFS = ("M5", "M15", "M30", "H1", "H4")

PAIR = ("XAUUSD", "EURUSD")


# ═══════════════════ اجرای یک ابزار روی یک تایم‌فریم ═══════════════════
def run_leg(asset, tf, seed):
    """
    یک «پا» = یک ابزار روی یک تایم‌فریم، با منطقِ ابزارمحورِ خودش.
    خروجی: دیکشنریِ اعضا + آرایه‌های لازم برای مدلِ صفر.
    """
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        return None
    df = se.load_data(path)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    warm = min(260, max(30, n // 8))
    half = n // 2
    gate = GATE_BY_ASSET[asset]

    ctxs = {k: channel_context(df, k) for k in FAM_K}

    # افقِ نگهداری از هندسهٔ خودِ الگو (عیناً روشِ S366 — نه جدولِ ثابت).
    durs = []
    for k in FAM_K:
        ls, ss, _, _, dur = member_signals(df, ctxs[k], FAM_M[0], FAM_S[0],
                                           asset, gate)
        sel = ls | ss
        if sel.any():
            durs.extend(dur[sel].tolist())
    if not durs:
        return None
    mh = int(min(MAX_HOLD_CAP, max(5, round(HORIZON_MULT * float(np.median(durs))))))

    members, obsR, sls, rrs, isLs = [], [], [], [], []
    allR, allEB, burdens = [], [], []
    tp_lt_sl = []
    for k in FAM_K:
        ctx = ctxs[k]
        for m_ in FAM_M:
            for s_ in FAM_S:
                ls, ss, slv, tpv, _ = member_signals(df, ctx, m_, s_, asset, gate)
                ls[:warm] = False
                ss[:warm] = False
                ls[n - mh - 2:] = False
                ss[n - mh - 2:] = False
                tr = se.simulate_trades(df, ls, ss, slv, tpv, asset,
                                        max_hold=mh, allow_overlap=False)
                if tr is None or len(tr) == 0:
                    continue
                sl = tr["sl_pip"].values.astype(float)
                okm = sl > 0
                if okm.sum() < MIN_TRADES:
                    continue
                R = tr["pnl_pip"].values[okm] / sl[okm]
                eb = tr["entry_bar"].values.astype(int)[okm]
                isL = (tr["direction"].values[okm] == "long")
                # نسبتِ TP/SL این عضو ثابت است (m/s) ⇒ سهمِ TP<SL یا ۰ یا ۱.
                tp_lt_sl.append(1.0 if (float(m_) < float(s_)) else 0.0)
                members.append(dict(asset=asset, k=k, m=m_, s=s_,
                                    n=int(okm.sum()),
                                    meanR=round(float(R.mean()), 4),
                                    burden=round(float(np.mean(cost / sl[okm])), 4)))
                obsR.append(float(R.mean()))
                sls.append(sl[okm])
                rrs.append(float(m_) / float(s_))
                isLs.append(isL)
                burdens.append(float(np.mean(cost / sl[okm])))
                allR.append(R)
                allEB.append(eb < half)

    if not members:
        return None

    return dict(asset=asset, tf=tf, gate=gate, bars=n, max_hold=mh,
                warm=warm, pip=pip, cost=cost,
                o=df["open"].values.astype(float),
                h=df["high"].values.astype(float),
                l=df["low"].values.astype(float),
                members=members, obsR=obsR, sls=sls, rrs=rrs, isLs=isLs,
                burdens=burdens, allR=allR, allFirstHalf=allEB,
                tp_lt_sl=tp_lt_sl)


# ═══════════════════ اجرای یک کارتِ ادغام‌شده (دو ابزار) ═══════════════════
def run_card(tf, n_perm=N_PERM, seed=373, save=True):
    print(f"\n=== S373 INSTRUMENT-NATIVE :: {tf} "
          f"(XAU:gate=False | EUR:gate=True) ===", flush=True)

    legs = []
    for a in PAIR:
        lg = run_leg(a, tf, seed)
        if lg is None:
            print(f"   !! leg {a}-{tf} unavailable")
            continue
        legs.append(lg)
    if len(legs) < 2:
        res = dict(tf=tf, verdict="INCOMPLETE_PAIR")
        if save:
            _save(res, tf)
        print("   >>> INCOMPLETE_PAIR")
        return res

    # ── آمارهٔ سطحِ ۱: میانگینِ meanR روی همهٔ اعضای هر دو ابزار ──
    obs_all = [x for lg in legs for x in lg["obsR"]]
    fam = float(np.mean(obs_all))

    # ── آمارهٔ سطحِ ۲: حوضِ معاملات (فضای بازده) ──
    R_pool = np.concatenate([r for lg in legs for r in lg["allR"]])
    F_pool = np.concatenate([f for lg in legs for f in lg["allFirstHalf"]])
    trade_pooled = float(R_pool.mean())
    h1 = float(R_pool[F_pool].mean()) if F_pool.any() else float("nan")
    h2 = float(R_pool[~F_pool].mean()) if (~F_pool).any() else float("nan")

    tot = int(sum(m["n"] for lg in legs for m in lg["members"]))
    share_tp_lt_sl = float(np.mean([x for lg in legs for x in lg["tp_lt_sl"]]))

    # اقتصادِ هر ابزار جداگانه (قفلِ ۴ پیش‌ثبت).
    econ = {}
    for lg in legs:
        bur = float(np.mean(lg["burdens"]))
        famA = float(np.mean(lg["obsR"]))
        sl_eff = lg["cost"] / bur if bur > 0 else float("nan")
        econ[lg["asset"]] = dict(
            n=int(sum(m["n"] for m in lg["members"])),
            fam_meanR=round(famA, 4), burden=round(bur, 4),
            sl_eff=round(sl_eff, 2), cost=lg["cost"],
            e_pip=round(famA * sl_eff + lg["cost"], 3),
            surplus=round(famA * sl_eff, 3),
            gate=lg["gate"], max_hold=lg["max_hold"])

    print(f"  POOLED family mean R = {fam:+.4f}   members={len(obs_all)}"
          f"  Σn={tot:,}")
    print(f"  trade-space meanR    = {trade_pooled:+.4f}"
          f"   (weighting effect = {fam - trade_pooled:+.4f})")
    print(f"  halves (trade-space) = ({h1:+.4f}, {h2:+.4f})")
    for a, e in econ.items():
        print(f"    {a}: n={e['n']:>6,} gate={str(e['gate']):>5} "
              f"SL_eff={e['sl_eff']:>6.1f}p  e_pip={e['e_pip']:>+7.2f}"
              f"  vs c={e['cost']:.1f}  ⇒ surplus={e['surplus']:>+6.2f}",
              flush=True)

    # ── مدلِ صفر: بارهای تصادفی، مجموعهٔ بریکت و RRِ هر عضو دست‌نخورده ──
    #    هر عضو در ابزارِ خودش جای‌گشت می‌خورد؛ آمارهٔ جای‌گشت = میانگینِ
    #    همهٔ اعضای هر دو ابزار (هم‌ساختار با آمارهٔ مشاهده‌شده).
    rng = np.random.default_rng(seed)
    perms = []
    for _ in range(n_perm):
        vals = []
        for lg in legs:
            lo, hi = lg["warm"], lg["bars"] - lg["max_hold"] - 2
            for sl_arr, isL, rr in zip(lg["sls"], lg["isLs"], lg["rrs"]):
                mlen = len(sl_arr)
                picks = rng.integers(lo, hi, size=mlen)
                v = _perm_meanR(lg["o"], lg["h"], lg["l"], picks, isL,
                                sl_arr[rng.permutation(mlen)], lg["pip"],
                                lg["max_hold"], lg["cost"], rr)
                if v is not None:
                    vals.append(v)
        if vals:
            perms.append(float(np.mean(vals)))
    perms = np.asarray(perms, dtype=float)
    nullm = float(perms.mean())
    sd = float(perms.std(ddof=1)) or 1e-9
    z = (fam - nullm) / sd
    p = float((perms >= fam).mean())

    # ── داوریِ شرایطِ پیش‌ثبت‌شده ──
    luck_ok = z >= Z_LUCK
    positive = fam > 0
    halves_ok = (h1 > 0) and (h2 > 0)
    econ_ok = all(e["e_pip"] > e["cost"] for e in econ.values())

    n_needed = (tot * (Z_LUCK / z) ** 2) if z > 0 else None

    if luck_ok and positive and halves_ok and econ_ok:
        verdict = "CANDIDATE_FOR_JUDGEMENT"
    elif not econ_ok:
        verdict = "DEAD_BELOW_COST"
    elif not luck_ok:
        verdict = "DEAD_UNDERPOWERED"
    else:
        verdict = "DEAD_NO_REPLICATION"

    print(f"  NULL   pooled mean R = {nullm:+.4f}   sd = {sd:.4f}"
          f"  (perms={len(perms)})")
    print(f"  LIFT_R = {fam - nullm:+.4f} R/trade   z = {z:+.3f}σ"
          f"   vs z_luck({N_TRIALS}) = {Z_LUCK:.3f}   p = {p:.4f}")
    if n_needed:
        print(f"  n_needed = {n_needed:,.0f}   (have {tot:,}) ⇒ "
              + ("کافی" if n_needed <= tot else f"کمبود {n_needed - tot:,.0f}"))
    print(f"  share(TP<SL) = {share_tp_lt_sl:.3f}")
    print(f"  >>> {verdict}   (luck={luck_ok}, positive={positive}, "
          f"halves={halves_ok}, econ={econ_ok})", flush=True)

    res = dict(tf=tf, pair=list(PAIR), gate_map=GATE_BY_ASSET,
               n_trials=N_TRIALS, z_luck=round(Z_LUCK, 3),
               n_members=len(obs_all), n_trades=tot,
               fam_pooled=round(fam, 4), trade_pooled=round(trade_pooled, 4),
               weighting_effect=round(fam - trade_pooled, 4),
               null_meanR=round(nullm, 4), sd=round(sd, 4),
               lift=round(fam - nullm, 4), z=round(z, 3), p_perm=round(p, 4),
               half1=round(h1, 4), half2=round(h2, 4),
               share_tp_lt_sl=round(share_tp_lt_sl, 4),
               n_needed=(round(n_needed) if n_needed else None),
               econ=econ, n_perm=len(perms),
               members=[m for lg in legs for m in lg["members"]],
               verdict=verdict)
    if save:
        _save(res, tf)
    return res


def _save(res, tf):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"{tf}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"    saved -> {path}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", default="H4")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--perm", type=int, default=N_PERM)
    a = ap.parse_args()
    tfs = SHARED_TFS if a.all else [a.tf]
    for tf in tfs:
        try:
            run_card(tf, n_perm=a.perm)
        except Exception as exc:                                   # noqa: BLE001
            print(f"   !! {tf} failed: {exc}", flush=True)


if __name__ == "__main__":
    main()
