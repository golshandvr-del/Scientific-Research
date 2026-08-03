# -*- coding: utf-8 -*-
"""
S375 — «احیای S371 با قاعدهٔ شکستِ Kennedy روی ابزارِ تک»

پیش‌ثبت: results/S375_PREREG_kennedy_single_instrument_h1.md
         (commit شده **پیش از** این فایل — مُهرِ زمانیِ git سند است)

═══════════════════════════════════════════════════════════════════════════
پرسشِ این فایل — در یک خط
═══════════════════════════════════════════════════════════════════════════
لایهٔ سوختهٔ `S371` (شکستِ هم‌جهتِ کانال) روی `XAUUSD-H1` **تنها با یک بند** مرد:

      مهارت  z = +2.855  ✅ پاس
      نمونه  n = 1,637   ✅ فراوان
      اقتصاد e_pip = +3.38  در برابرِ  c = 3.3   ⇒  مازاد +0.08   ❌ کشنده

قاعدهٔ Kennedy (`high < lower` / `low > upper` به‌جای `close`) طبقِ یافتهٔ
`S374_FINDING_not_subset_but_delay.md` **الگوها را غربال نمی‌کند** (همپوشانیِ
کانال ≈۱۰۰٪) بلکه **بارِ ورود را عوض می‌کند** (تأخیرِ ۱ تا ۷ کندل) ⇒ مستقیماً
روی `e_pip` اثر می‌گذارد، که همان بندِ کشندهٔ `S371` است.

⇒ ابزار و بیماری هم‌جنس‌اند. این فایل آن را می‌آزماید.

═══════════════════════════════════════════════════════════════════════════
تفاوت با S374 — چرا این تکرار نیست
═══════════════════════════════════════════════════════════════════════════
  S374: آمارهٔ پذیرش = جفتِ ادغام‌شدهٔ XAU+EUR ، کارتِ هدف = H4 ، ۴ شرط
  S375: آمارهٔ پذیرش = **طلای تنها**       ، کارتِ هدف = **H1** ، **۱۱ دروازه**

`_scan_S374/H1.json` هر دو بازو را روی همین کارت دارد و بازوی طلا `gate=False`
است ⇒ عیناً همان شاخهٔ هم‌جهتِ `S371`. اعدادِ بایگانی:

      close    : n=1,637  e_pip=+3.839   ⇒ مازاد +0.539
      kennedy  : n=  644  e_pip=+10.506  ⇒ مازاد +7.206

ولی آن اعداد **هرگز داوری نشدند**، چون بندِ اقتصادِ S374 «هر دو ابزار» بود و
یورو در H1 مازادِ −1.896 داشت ⇒ کلِ کارت `DEAD_BELOW_COST` گرفت.

═══════════════════════════════════════════════════════════════════════════
بندهای قفل — از پیش‌ثبت §۶، در کد به‌صورت ثابت
═══════════════════════════════════════════════════════════════════════════
۱) قفلِ تعریف : تنها `close` (پایه) و `kennedy`. هیچ تعریفِ میانی.
۲) قفلِ خانواده: FAM_K/FAM_M/FAM_S دست‌نخورده از s366.
۳) قفلِ تک‌فیلتر: هیچ فیلترِ رژیمی/اندیکاتوریِ تازه.
۴) قفلِ کارت  : داوریِ ۱۱ دروازه فقط روی XAUUSD-H1 — ولی **گزارشِ MTF اجباری**.
۵) قفلِ لنگر  : عضوِ واحد از متن ⇒ k=3 ، m=1.000 ، s=0.786. ردِ لنگر = ردِ لایه.
۶) قفلِ اقتصاد: e_pip طلا باید > 3.3 باشد، بی‌اعتنا به معناداری.
۷) قفلِ گزارش : حکم هرچه بود ثبت می‌شود، در کنارِ اعدادِ پیش‌بینی‌شدهٔ §۴.۲.

N_TRIALS = 117  ⇒  Z_LUCK = expected_max_z(117) = 2.5854   (تثبیت پیش از اجرا)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from engine import rqs2                                                  # noqa: E402
from engine.rqs2 import expected_max_z                                   # noqa: E402
from strategies.s366_stairs_channel_breakout import (                    # noqa: E402
    channel_context, _first_per_seg, _perm_meanR,
    FAM_K, FAM_M, FAM_S, MIN_TRADES, HORIZON_MULT, MAX_HOLD_CAP)
from strategies.s374_kennedy_break_gate import member_signals_mode       # noqa: E402

OUT = "results/_scan_S375"
N_PERM = 400

# ⛔ شمارشِ چندگانگی و سد — پیش‌ثبت §۵، تثبیت‌شده پیش از وجودِ نتیجه.
N_TRIALS = 117
Z_LUCK = expected_max_z(N_TRIALS)              # = 2.5854

# ⛔ ابزارِ هدفِ این لایه: طلا تنها (پیش‌ثبت §۲).
ASSET = "XAUUSD"
JUDGE_TF = "H1"                                # قفلِ کارت (بندِ ۴)

# ⛔ دروازهٔ کوچک‌شوندگی برای طلا خاموش — عیناً S371/S372/S373/S374.
GATE = False

# گزارشِ MTF اجباری (بندِ ۷ + قانونِ اولِ پروژه)
TFS_XAU = ("M5", "M15", "M30", "H1", "H4", "D1", "W1")
TFS_EUR = ("M5", "M15", "M30", "H1", "H4", "D1", "W1")

MODES = ("close", "kennedy")

# ⛔ لنگرِ متنی (بندِ ۵) — بدونِ نگاه به هیچ عددِ عملکردی:
#     k=3     میانهٔ محورِ FAM_K=(2,3,5)
#     m=1.000 هدفِ کاملِ measured-move (خوانشِ متنِ Brooks)
#     s=0.786 = √0.618 (نسبتِ فیبوناچیِ خودِ خانواده، نه یک عددِ رند)
ANCHOR = dict(k=3, m=1.000, s=0.786)


# ═════════════════════ یک پا = طلا روی یک تایم‌فریم ═════════════════════
def run_leg(asset, tf, mode, mh_override=None):
    """کلونِ `s374.run_leg` با یک تفاوت: تک‌ابزاری است (بدونِ جفت).

    ⚠️ افقِ نگهداری از **بازوی پایه** گرفته و به Kennedy تحمیل می‌شود، عیناً
       مثلِ S374. اگر هر بازو افقِ خودش را استخراج کند، دو متغیر همزمان عوض
       می‌شوند و اثرِ تعریفِ شکست از اثرِ افق جدا نمی‌شود.
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

    ctxs = {k: channel_context(df, k) for k in FAM_K}

    if mh_override is not None:
        mh = int(mh_override)
    else:
        durs = []
        for k in FAM_K:
            ls, ss, _, _, dur = member_signals_mode(df, ctxs[k], FAM_M[0],
                                                    FAM_S[0], asset, GATE, mode)
            sel = ls | ss
            if sel.any():
                durs.extend(dur[sel].tolist())
        if not durs:
            return None
        mh = int(min(MAX_HOLD_CAP,
                     max(5, round(HORIZON_MULT * float(np.median(durs))))))

    members, obsR, sls, rrs, isLs = [], [], [], [], []
    allR, allEB, burdens, tp_lt_sl = [], [], [], []
    n_raw_sig = 0
    for k in FAM_K:
        ctx = ctxs[k]
        for m_ in FAM_M:
            for s_ in FAM_S:
                ls, ss, slv, tpv, _ = member_signals_mode(df, ctx, m_, s_,
                                                          asset, GATE, mode)
                ls[:warm] = False
                ss[:warm] = False
                ls[n - mh - 2:] = False
                ss[n - mh - 2:] = False
                n_raw_sig += int(ls.sum() + ss.sum())
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

    return dict(asset=asset, tf=tf, gate=GATE, bars=n, max_hold=mh,
                warm=warm, pip=pip, cost=cost, mode=mode,
                n_raw_sig=n_raw_sig,
                o=df["open"].values.astype(float),
                h=df["high"].values.astype(float),
                l=df["low"].values.astype(float),
                members=members, obsR=obsR, sls=sls, rrs=rrs, isLs=isLs,
                burdens=burdens, allR=allR, allFirstHalf=allEB,
                tp_lt_sl=tp_lt_sl)


# ═════════════════ آمارهٔ تک‌ابزاری + مدلِ صفرِ جای‌گشتی ═════════════════
def score_leg(lg, n_perm, seed):
    """آمارهٔ پذیرش = `trade_pooled` (قانونِ سوگیریِ خوش‌بینیِ میانگینِ خانواده).

    میانگینِ خانواده هر عضو را هم‌وزن می‌گیرد و اعضای کم‌معامله را بزرگ
    می‌نمایاند؛ ادغامِ معامله‌محور این سوگیری را ندارد. هر دو محاسبه و
    اختلافشان در `weighting_effect` ثبت می‌شود.
    """
    fam = float(np.mean(lg["obsR"]))
    R_pool = np.concatenate(lg["allR"])
    F_pool = np.concatenate(lg["allFirstHalf"])
    trade_pooled = float(R_pool.mean())
    h1 = float(R_pool[F_pool].mean()) if F_pool.any() else float("nan")
    h2 = float(R_pool[~F_pool].mean()) if (~F_pool).any() else float("nan")
    tot = int(sum(m["n"] for m in lg["members"]))
    share_tp_lt_sl = float(np.mean(lg["tp_lt_sl"]))

    bur = float(np.mean(lg["burdens"]))
    sl_eff = lg["cost"] / bur if bur > 0 else float("nan")
    econ = dict(
        n=tot, n_raw_sig=lg["n_raw_sig"],
        fam_meanR=round(fam, 4), trade_meanR=round(trade_pooled, 4),
        burden=round(bur, 4), sl_eff=round(sl_eff, 2), cost=lg["cost"],
        e_pip=round(trade_pooled * sl_eff + lg["cost"], 3),
        surplus=round(trade_pooled * sl_eff, 3),
        e_pip_fam=round(fam * sl_eff + lg["cost"], 3),
        gate=lg["gate"], max_hold=lg["max_hold"])

    # ── مدلِ صفر: عیناً از S373/S374 — بارِ تصادفی + بُرِ همان بریکت‌ها ──
    rng = np.random.default_rng(seed)
    perms = []
    lo, hi = lg["warm"], lg["bars"] - lg["max_hold"] - 2
    for _ in range(n_perm):
        vals = []
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
    perms = np.array(perms, dtype=float)
    null_mean = float(perms.mean()) if len(perms) else float("nan")
    sd = float(perms.std(ddof=1)) if len(perms) > 1 else float("nan")

    lift = trade_pooled - null_mean
    z = lift / sd if (sd and sd > 0) else float("nan")
    p_perm = float((perms >= trade_pooled).sum() + 1) / (len(perms) + 1)
    n_needed = int(round((Z_LUCK * sd / lift) ** 2 * tot)) if lift > 0 else -1

    return dict(asset=lg["asset"], tf=lg["tf"], mode=lg["mode"],
                n_trials=N_TRIALS, z_luck=round(float(Z_LUCK), 4),
                n_members=len(lg["obsR"]), n_trades=tot,
                fam_pooled=round(fam, 4), trade_pooled=round(trade_pooled, 4),
                weighting_effect=round(fam - trade_pooled, 4),
                null_meanR=round(null_mean, 4), sd=round(sd, 4),
                lift=round(lift, 4), z=round(z, 3), p_perm=round(p_perm, 4),
                half1=round(h1, 4), half2=round(h2, 4),
                share_tp_lt_sl=round(share_tp_lt_sl, 3),
                n_needed=n_needed, econ=econ, n_perm=len(perms),
                max_hold=lg["max_hold"], members=lg["members"])


# ═════════════════ یک کارت = پایه + Kennedy (تک‌ابزاری) ═════════════════
def run_card(asset, tf, n_perm=N_PERM, seed=375, save=True):
    print(f"\n{'='*74}")
    print(f"=== S375 :: {asset}-{tf}  (single-instrument, gate={GATE}) ===")
    print(f"{'='*74}", flush=True)

    base_lg = run_leg(asset, tf, "close")
    if base_lg is None:
        res = dict(asset=asset, tf=tf, verdict="NO_SAMPLE_BASE")
        if save:
            _save(res, asset, tf)
        print("   >>> NO_SAMPLE_BASE")
        return res
    base = score_leg(base_lg, n_perm, seed)

    ken_lg = run_leg(asset, tf, "kennedy", mh_override=base_lg["max_hold"])
    if ken_lg is None:
        res = dict(asset=asset, tf=tf, verdict="NO_SAMPLE_KENNEDY", base=base)
        if save:
            _save(res, asset, tf)
        print("   >>> NO_SAMPLE_KENNEDY")
        return res
    ken = score_leg(ken_lg, n_perm, seed)

    for tag, r in (("BASE   (close)", base), ("KENNEDY(high/low)", ken)):
        e = r["econ"]
        print(f"\n  ── {tag} ──")
        print(f"     members={r['n_members']}  Σn={r['n_trades']:,}"
              f"   trade_pooled={r['trade_pooled']:+.4f}"
              f"  (fam={r['fam_pooled']:+.4f})")
        print(f"     null={r['null_meanR']:+.4f}  sd={r['sd']:.4f}"
              f"  lift={r['lift']:+.4f}  z={r['z']:+.3f}"
              f"  p_perm={r['p_perm']:.4f}")
        print(f"     halves=({r['half1']:+.4f}, {r['half2']:+.4f})"
              f"   n_needed={r['n_needed']:,}  mh={r['max_hold']}")
        print(f"     SL_eff={e['sl_eff']:.1f}p  e_pip={e['e_pip']:+.3f}"
              f" vs c={e['cost']:.1f}  ⇒ surplus={e['surplus']:+.3f}",
              flush=True)

    retain = 100.0 * ken["n_trades"] / base["n_trades"] if base["n_trades"] else 0.0
    d_epip = ken["econ"]["e_pip"] - base["econ"]["e_pip"]
    print(f"\n  ── Δ (KENNEDY − BASE) ──")
    print(f"     retention = {ken['n_trades']:,}/{base['n_trades']:,}"
          f" = {retain:.1f}%")
    print(f"     Δ trade_pooled = {ken['trade_pooled']-base['trade_pooled']:+.4f}")
    print(f"     Δ z            = {ken['z']-base['z']:+.3f}")
    print(f"     Δ e_pip        = {d_epip:+.3f}"
          f"   ({base['econ']['e_pip']:+.2f} → {ken['econ']['e_pip']:+.2f})",
          flush=True)

    # ── چهار شرطِ سطح-کارت (پیش‌غربال؛ داوریِ نهایی ۱۱ دروازه است) ──
    conds = dict(
        luck=bool(ken["z"] >= Z_LUCK),
        sample=bool(ken["n_needed"] > 0 and ken["n_trades"] >= ken["n_needed"]),
        econ=bool(ken["econ"]["surplus"] > 0),
        replication=bool(ken["half1"] > 0 and ken["half2"] > 0),
    )
    passed = all(conds.values())
    print(f"\n  ── PRE-SCREEN (z_luck={Z_LUCK:.4f}) ──")
    for k, v in conds.items():
        print(f"     {k:12} : {'PASS' if v else 'FAIL'}")
    if passed:
        verdict = "PRESCREEN_PASS"
    elif not conds["econ"]:
        verdict = "DEAD_BELOW_COST"
    elif not conds["luck"]:
        verdict = "DEAD_LUCK_BOUND"
    elif not conds["sample"]:
        verdict = "DEAD_INSUFFICIENT_SAMPLE"
    else:
        verdict = "DEAD_NO_REPLICATION"
    print(f"     >>> {verdict}", flush=True)

    res = dict(asset=asset, tf=tf, verdict=verdict, conds=conds,
               retention_pct=round(retain, 1), d_e_pip=round(d_epip, 3),
               d_z=round(ken["z"] - base["z"], 3),
               d_trade_pooled=round(ken["trade_pooled"] - base["trade_pooled"], 4),
               base=base, kennedy=ken)
    if save:
        _save(res, asset, tf)
    return res


# ═════════════ داوریِ کاملِ ۱۱ دروازه روی لنگرِ متنی (بندِ ۵) ═════════════
def judge_anchor(asset=JUDGE_TF and ASSET, tf=JUDGE_TF, mode="kennedy",
                 seed=375, save=True):
    """۱۱ دروازهٔ RQS2 روی **یک عضوِ واحدِ متن‌محور**.

    چرا عضوِ واحد و نه خانواده؟ چون `compute_rqs2` یک سریِ معاملاتِ واقعی و
    یک بریکتِ مشخص می‌خواهد (H2 سربه‌سر، H6 پنجرهٔ تقویمی، H8 دنبالهٔ باخت).
    خانواده ۱۲ سریِ هم‌پوشان است و ادغامشان دنبالهٔ زمانیِ معنادار نمی‌سازد.

    عضو **از متن** انتخاب شد (ANCHOR)، نه از عملکرد ⇒ هزینهٔ انتخاب صفر
    ⇒ `n_trials` همان ۱۱۷ می‌ماند. بندِ ۵ پیش‌ثبت: ردِ لنگر = ردِ لایه.
    """
    from strategies.s364_deploy_judge import _perm_null_floating

    path = f"data/{asset}_{tf}.csv"
    df = se.load_data(path)
    n = len(df)
    warm = min(260, max(30, n // 8))
    split = n // 2
    rng = np.random.default_rng(seed)

    print(f"\n{'#'*74}")
    print(f"### S375 ANCHOR-JUDGE (11 gates) :: {asset}-{tf}  mode={mode}")
    print(f"###   anchor (text-chosen, zero selection cost) = {ANCHOR}")
    print(f"###   n_trials={N_TRIALS}  z_luck={Z_LUCK:.4f}")
    print(f"{'#'*74}", flush=True)

    # افقِ نگهداری: از بازوی **پایه** روی همین کارت (جداسازیِ متغیر، مثلِ run_leg)
    base_lg = run_leg(asset, tf, "close")
    if base_lg is None:
        print("   !! no base sample")
        return None
    mh = base_lg["max_hold"]

    ctx = channel_context(df, ANCHOR["k"])
    ls, ss, slv, tpv, _ = member_signals_mode(
        df, ctx, ANCHOR["m"], ANCHOR["s"], asset, GATE, mode)
    ls[:warm] = False
    ss[:warm] = False
    ls[n - mh - 2:] = False
    ss[n - mh - 2:] = False

    trades = se.simulate_trades(df, ls, ss, slv, tpv, asset,
                                max_hold=mh, allow_overlap=False)
    if trades is None or len(trades) == 0:
        print("   !! anchor produced no trades")
        return None

    sl = trades["sl_pip"].values.astype(float)
    eb = trades["entry_bar"].values.astype(int)
    okm = sl > 0
    mean_sl = float(np.mean(sl[okm]))
    tp = (trades["tp_pip"].values.astype(float) if "tp_pip" in trades
          else tpv[eb - 1])
    mean_tp = float(np.mean(np.asarray(tp)[okm]))
    share_tp_lt_sl = float(np.mean(np.asarray(tp)[okm] < sl[okm]))

    print(f"   n_trades={len(trades)}  mh={mh}  mean SL={mean_sl:.2f}p  "
          f"mean TP={mean_tp:.2f}p  RR={mean_tp/mean_sl:.3f}  "
          f"share(TP<SL)={share_tp_lt_sl:.3f}", flush=True)

    # ── مدلِ صفرِ کانونی: دو استخر (آزاد / مشروط به زمینهٔ کانال)، سخت‌ترین برنده ──
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    pip = float(se.ASSETS[asset]["pip"])
    cfg = se.ASSETS[asset]
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))

    free_pool = np.arange(warm, n - mh - 2)
    in_ctx = np.nan_to_num(ctx["ok"], nan=False).astype(bool)
    gated_pool = free_pool[in_ctx[free_pool]]
    print(f"   null pools: free={free_pool.size:,}  gated={gated_pool.size:,}",
          flush=True)

    null, ndiag = {}, {}
    for side, flag, sig in (("long", True, ls), ("short", False, ss)):
        idx = np.where(sig)[0]
        n_side = int(idx.size)
        if n_side < 1:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)
            continue
        br = np.column_stack([slv[idx], tpv[idx]])
        cands = []
        for tag, pool in (("free", free_pool), ("gated", gated_pool)):
            v = _perm_null_floating(o, h, l, c, pool, n_side, flag, br,
                                    pip, mh, cost, n, rng, N_PERM)
            if v:
                cands.append((tag, v))
        if cands:
            tag, best = max(cands, key=lambda kv: kv[1]["perm_mean"])
            null[side] = best
            ndiag[side] = dict(chosen=tag, n_side=n_side,
                               wrs={k: round(v["perm_mean"], 2)
                                    for k, v in cands})
            print(f"   null[{side}]: chosen={tag}  "
                  f"WRs={ndiag[side]['wrs']}  n_side={n_side}", flush=True)
        else:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)

    bar_time = df["time"].values if "time" in df else np.arange(n)
    holdout_mask = (eb >= split)
    print(f"   holdout (2nd half) = {int(holdout_mask.sum())}/{len(trades)}",
          flush=True)

    res = rqs2.compute_rqs2(
        trades, asset,
        sl_pip=mean_sl, tp_pip=mean_tp,
        bar_time=bar_time,
        null=null, n_trials=N_TRIALS,
        holdout_mask=holdout_mask, split_bar=split,
        close=c, allow_overlap=False,
    )

    g = res.get("gates", {})
    m = res.get("metrics", {})
    print(f"\n   VERDICT = {res.get('verdict')}   "
          f"score={res.get('rqs2_score', res.get('score'))}")
    print("   gates: " + "  ".join(
        f"{k}={'OK' if v else ('X' if v is False else '?')}"
        for k, v in g.items()))
    print(f"   z_obs={m.get('z_obs')}  bound={m.get('z_luck_bound')}"
          f"  margin={m.get('z_margin')}")
    print(f"   PF={m.get('profit_factor')}  WR={m.get('win_rate')}"
          f"  net={m.get('net_profit')}  n={m.get('n_trades')}")
    for r in (res.get("reasons") or res.get("notes") or [])[:12]:
        print(f"     · {r}", flush=True)

    out = dict(asset=asset, tf=tf, mode=mode, anchor=ANCHOR,
               n_trials=N_TRIALS, z_luck=round(float(Z_LUCK), 4),
               max_hold=mh, mean_sl=round(mean_sl, 3),
               mean_tp=round(mean_tp, 3),
               rr=round(mean_tp / mean_sl, 4),
               share_tp_lt_sl=round(share_tp_lt_sl, 4),
               n_trades=int(len(trades)),
               holdout_n=int(holdout_mask.sum()),
               null_diag=ndiag, rqs2=_jsonable(res))
    if save:
        os.makedirs(OUT, exist_ok=True)
        p = f"{OUT}/ANCHORJUDGE_{asset}_{tf}_{mode}.json"
        with open(p, "w") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
        print(f"   → {p}", flush=True)
    return out


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def _save(res, asset, tf):
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/{asset}_{tf}.json"
    with open(p, "w") as fh:
        json.dump(_jsonable(res), fh, ensure_ascii=False, indent=1, default=str)
    print(f"   → {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tfs", default="")
    ap.add_argument("--asset", default=ASSET)
    ap.add_argument("--perm", type=int, default=N_PERM)
    ap.add_argument("--seed", type=int, default=375)
    ap.add_argument("--judge", action="store_true",
                    help="اجرای داوریِ ۱۱ دروازه روی لنگر")
    ap.add_argument("--mode", default="kennedy")
    a = ap.parse_args()

    if a.judge:
        judge_anchor(a.asset, JUDGE_TF, a.mode, a.seed)
        return

    tfs = ([t for t in a.tfs.split(",") if t] or
           list(TFS_XAU if a.asset == "XAUUSD" else TFS_EUR))
    for tf in tfs:
        try:
            run_card(a.asset, tf, a.perm, a.seed)
        except Exception as exc:                              # noqa: BLE001
            print(f"   !! {a.asset}-{tf} EXCEPTION: {exc}", flush=True)


if __name__ == "__main__":
    main()
