# -*- coding: utf-8 -*-
"""
`S356` — آزمونِ تفکیکِ «همپوشان / بی‌همپوشان» + بندِ سومِ قانونِ همپوشانی
============================================================================
پیش‌ثبت: `results/S356_PREREG_OVERLAP_SPLIT.md` (پیش از اجرا commit شده).

این اسکریپت **هیچ جست‌وجویی ندارد**. همهٔ پارامترها از `s356_v24_rejudge`
وارد می‌شوند (منجمد)، و مجموعهٔ ورودها از فایل‌های commit‌شده خوانده می‌شود:

* ورودهای ما            : `results/_scan_S356/XAUUSD-H1_entrybars.json`
* ورودهای لایه‌های فعال : `results/_scan_S356/overlap_h1_atS356.json` (`active_bars`)

سه شاخه داوری می‌شوند:

| شاخه | تعریف | نقش |
|---|---|---|
| `FULL` | هر ۱۱۷ ورود | مرجع (لایهٔ پذیرفته‌شده) |
| `OVERLAP` | ورودهایی که ≥۱ لایهٔ فعال در `[b-1,b+1]` آتش کرده | «هم‌آتشی» |
| `DISJOINT` | بقیه | «لبهٔ خالصِ نو» |

⚠️ **آمارهٔ حاکم `lift` است، نه حکمِ دروازه‌ایِ زیرمجموعه.** دلیلش در بندِ ۲
پیش‌ثبت آمده: حذفِ ۲۸٪ معاملات به‌ناچار `z` را با ضریبِ `√(84/117)=0.847`
می‌کاهد، پس ردِ `H3` در `DISJOINT` **از قبل پیش‌بینی شده** و شکست تلقی نمی‌شود.
به همین دلیل این اسکریپت هم `verdict` و هم `lift` را چاپ می‌کند ولی تصمیم را
روی `lift` می‌گذارد.

جریمهٔ چندگانگی: `n_trials = 288` (`96 × 3` شاخه) — چون سه شاخه دیده شده است.

بندِ سومِ قانون (فیلتر) هم اینجا آزموده می‌شود:
  جهتِ الف) لایهٔ ما به‌عنوان فیلترِ تأییدِ `S313`/`S335`/`S328`
            → ورودهای آن لایه را **با براکتِ خودمان** حل می‌کنیم و `WR`ِ
              «همهٔ ورودهای آن لایه» را با `WR`ِ «زیرمجموعهٔ هم‌آتشی با ما»
              مقایسه می‌کنیم. (محدودیت در پیش‌ثبت اعلام شد: این «آن لایه با
              هندسهٔ ریسکِ ما» است، نه لایهٔ اصلی.)
  جهتِ ب) لایه‌های موجود به‌عنوان فیلترِ ما → همان `KEEP`/`DROP` بالا.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ⚠️ نامِ ماژولِ موتور عیناً همان است که `s356_v24_rejudge` وارد می‌کند
# (`engine.scalp_engine`). هر نامِ دیگری یک موتورِ دیگر است.
from engine import scalp_engine as se                          # noqa: E402
from engine import rqs2 as R2                                  # noqa: E402
from strategies import s354_brooks_trend_resumption as base    # noqa: E402
from strategies.s354_causal_check import build_signals_causal   # noqa: E402
from strategies.s356_v24_rejudge import (     # noqa: E402
    FROZEN, SEEDS, P_BAR, PERM_K_PRE,
    outcome_table, wr_of, build_null, empirical_p,
)

CARD = "XAUUSD-H1"
OUT = "results/_scan_S356"
N_TRIALS_SPLIT = 288        # ۹۶ × ۳ شاخه — جریمهٔ دیدنِ سه شاخه
TOL = 1                     # عیناً تلورانسِ ممیزی‌های پیشینِ پروژه


# ═══════════════════════════ ساختِ کارت و ماسک‌ها ═══════════════════════════
def build():
    asset, tf = CARD.split("-")
    df = se.load_data(os.path.join("data", f"{asset}_{tf}.csv"))
    atr_pip = base._atr_pip(df, asset, base.TF_ATR_P.get(tf, 34))
    mh = base.TF_MAX_HOLD.get(tf, 20)
    sl = round(FROZEN["sl_k"] * atr_pip, 1)
    tp = round(FROZEN["rr"] * sl, 1)
    gate = base.regime_gate(df, FROZEN["regime"])
    sig = build_signals_causal(df, asset, tf, FROZEN["n_open_frac"],
                               FROZEN["late_hour"], FROZEN["spike_k"],
                               FROZEN["tight_atr"]) & gate
    return df, asset, tf, sl, tp, mh, np.asarray(sig, bool)


def overlap_masks(sig):
    """ماسکِ `OVERLAP`/`DISJOINT` از **سوییپِ کاملِ** موتورِ واقعیِ سایت.

    ⚠️ منبع عمداً `overlap_h1_full.json` است (سوییپِ `stride=1` روی کلِ تاریخ)، نه
    `overlap_h1_atS356.json`. دلیل: پروبِ `atbars` فقط در همسایگیِ **کندل‌های
    ورودِ** ما ارزیابی شده بود و کندلِ ورود یکی بعد از کندلِ تصمیم است، پس
    پنجره‌اش نسبت به تصمیمِ ما `{۰,+۱,+۲}` را می‌پوشاند و لایه‌ای که **یک کندل
    قبل** از ما آتش کرده بود را نمی‌دید — سوگیریِ نامتقارن. سوییپِ کامل همهٔ
    کندل‌های آتش‌باریِ هر ۸ لایه را دارد، پس پنجرهٔ متقارنِ `[b-TOL, b+TOL]` حولِ
    **کندلِ تصمیمِ** ما بی‌سوگیری محاسبه می‌شود.

    `sig` روی کندلِ تصمیم است (`flatnonzero(sig)` = `signal_bars`)، و لایه‌های
    سایت هم `ENTRY` را روی کندلِ تصمیم می‌دهند ⇒ مقایسه «تصمیم به تصمیم» است.
    """
    full = json.load(open(f"{OUT}/overlap_h1_full.json", encoding="utf-8"))
    n = len(sig)
    inc = np.zeros(n, bool)                    # کندل‌هایی که ≥۱ لایهٔ فعال ENTRY داده
    per_layer = {}
    for L in full["layers"]:
        bars = np.asarray(L.get("active_bars", []), dtype=np.int64)
        per_layer[L["code"]] = bars
        for b in bars:
            lo, hi = max(0, b - TOL), min(n - 1, b + TOL)
            inc[lo:hi + 1] = True

    ours = np.flatnonzero(sig)
    ov = sig & inc
    dj = sig & ~inc
    return ov, dj, inc, per_layer, ours


# ═══════════════════════════════ داوریِ یک شاخه ═══════════════════════════════
def judge(df, asset, sig_branch, sl, tp, mh, label, verbose=True):
    n_sig = int(sig_branch.sum())
    tr = se.simulate_trades(df, sig_branch, np.zeros(len(df), bool), sl, tp,
                            asset, max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 5:
        return dict(label=label, status="TOO_FEW", n_signals=n_sig)
    n = len(tr)
    wr = 100.0 * float((tr["pnl_pip"] > 0).sum()) / n
    # `simulate_trades` یک DataFrame با ستونِ `pnl_pip` برمی‌گرداند (نه structured
    # array و نه ستونِ دلاری). تبدیل به دلار با مشخصاتِ حسابِ دمو:
    #   CONTRACT_SIZE=100 ⇒ حرکتِ ۱.۰۰ دلاری = ۱۰۰$/لات؛ pip طلا = ۰.۱ ⇒ ۱۰$/pip/لات
    #   pip یورو = ۰.۰۰۰۱ ⇒ ۱۰$/pip/لات (۱ لات = ۱۰۰٬۰۰۰)
    usd_per_pip = 10.0
    net = float(tr["pnl_pip"].sum()) * usd_per_pip
    close = df["close"].values.astype(float)
    bar_time = df["time"].values
    split_bar = int(len(df) * 0.60)

    rec = dict(label=label, status="JUDGED", n_signals=n_sig, n_trades=n,
               wr=round(wr, 2), net_usd=(round(net, 1) if net is not None else None),
               seeds={})
    for seed in SEEDS:
        null, draws = build_null(df, asset, sig_branch, sl, tp, mh,
                                 PERM_K_PRE, seed)
        p_emp, n_ge = empirical_p(draws, wr)
        r = R2.compute_rqs2(tr, asset, sl_pip=sl, tp_pip=tp, bar_time=bar_time,
                            close=close, null=null, n_trials=N_TRIALS_SPLIT,
                            split_bar=split_bar)
        m = r.get("metrics", {})
        bad = [g for g, v in (r.get("gates") or {}).items() if v is not True]
        rec["seeds"][str(seed)] = dict(
            verdict=r.get("verdict"), score=r.get("rqs2_score"),
            lift=m.get("skill_lift_pp"), z=m.get("skill_z"),
            uncond=null["long"]["uncond_wr"], p_emp=round(p_emp, 6),
            n_ge=n_ge, perm_k=null["long"]["perm_k"], failed=bad,
        )
    s0 = rec["seeds"][str(SEEDS[0])]
    rec["lift"] = s0["lift"]
    rec["z"] = s0["z"]
    rec["uncond"] = s0["uncond"]
    verds = {s: v["verdict"] for s, v in rec["seeds"].items()}
    rec["seed_stable"] = len(set(verds.values())) == 1
    rec["verdicts"] = verds
    if verbose:
        print(f"  {label:9s} n={n:4d} WR={wr:6.2f} uncond={s0['uncond']:6.2f} "
              f"lift={s0['lift']:+7.2f} z={s0['z']:+5.2f} "
              f"| {verds[str(SEEDS[0])]:13s} score={s0['score']:5.1f} "
              f"p_emp={s0['p_emp']:.4f}", flush=True)
        print(f"            failing gates: {s0['failed'] or 'NONE'}", flush=True)
    return rec


# ═══════════════════ بندِ سومِ قانون — جهتِ الف (فیلترِ تأیید) ═══════════════════
def filter_direction_a(df, asset, sl, tp, mh, per_layer, sig, res, xbar):
    """آیا لایهٔ ما `WR`ِ لایه‌های موجود را بالا می‌برد؟

    ⚠️ محدودیتِ اعلام‌شده در پیش‌ثبت: ورودهای لایهٔ موجود با **براکتِ ما**
    حل می‌شوند تا هم‌سنگ باشند؛ پس این «آن لایه با هندسهٔ ریسکِ ما» است.
    """
    n = len(df)
    ours_win = np.zeros(n, bool)
    for b in np.flatnonzero(sig):
        lo, hi = max(0, b - TOL), min(n - 1, b + TOL)
        ours_win[lo:hi + 1] = True

    rows = []
    for code, bars in per_layer.items():
        bars = np.asarray([b for b in bars if 260 <= b < n - mh - 2], dtype=np.int64)
        if bars.size == 0:
            rows.append(dict(code=code, n_all=0, note="بدونِ ورودِ قابلِ‌حل"))
            continue
        wr_all = wr_of(np.sort(bars), res, xbar)
        conf = np.sort(bars[ours_win[bars]])
        wr_conf = wr_of(conf, res, xbar) if conf.size else None
        anti = np.sort(bars[~ours_win[bars]])
        wr_anti = wr_of(anti, res, xbar) if anti.size else None
        rows.append(dict(
            code=code, n_all=int(bars.size), wr_all=(round(wr_all, 2) if wr_all else None),
            n_conf=int(conf.size), wr_conf=(round(wr_conf, 2) if wr_conf else None),
            n_anti=int(anti.size), wr_anti=(round(wr_anti, 2) if wr_anti else None),
            delta=(round(wr_conf - wr_all, 2) if (wr_conf and wr_all) else None),
        ))
    return rows


# ═════════════════════════════════ اجرا ═════════════════════════════════
def main():
    df, asset, tf, sl, tp, mh, sig = build()
    ov, dj, inc, per_layer, ours = overlap_masks(sig)
    res, xbar = outcome_table(df, asset, sl, tp, mh)

    print(f"\n=== {CARD} :: SL={sl}pip TP={tp}pip mh={mh} "
          f"| ورودهای ما={int(sig.sum())} "
          f"| OVERLAP={int(ov.sum())} DISJOINT={int(dj.sum())}", flush=True)
    print(f"    جریمهٔ چندگانگی: n_trials={N_TRIALS_SPLIT} (۹۶×۳ شاخه)\n", flush=True)

    rec = dict(card=CARD, sl_pip=sl, tp_pip=tp, maxhold=mh, tol=TOL,
               n_ours=int(sig.sum()), n_overlap=int(ov.sum()),
               n_disjoint=int(dj.sum()), n_trials=N_TRIALS_SPLIT,
               prereg="results/S356_PREREG_OVERLAP_SPLIT.md", branches={})

    for label, mask in (("FULL", sig), ("DISJOINT", dj), ("OVERLAP", ov)):
        rec["branches"][label] = judge(df, asset, mask, sl, tp, mh, label)
        # ⛳ قانونِ سومِ پروژه: پس از هر شاخه فوراً روی دیسک
        with open(f"{OUT}/overlap_split.json", "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1, default=float)

    # ── ارزیابیِ فرضیه‌های پیش‌ثبت‌شده ──
    F = rec["branches"]["FULL"]
    D = rec["branches"]["DISJOINT"]
    O = rec["branches"]["OVERLAP"]
    lf, ld = F.get("lift"), D.get("lift")
    lo_ = O.get("lift")
    P = {}
    P["P1_disjoint_lift_pos"] = bool(ld is not None and ld > 0)
    P["P2_disjoint_ge_60pct"] = bool(ld is not None and lf and ld >= 0.60 * lf)
    P["P3_z_in_band"] = bool(D.get("z") is not None and 2.2 <= D["z"] <= 3.4)
    P["P4_disjoint_H3_failed"] = bool("H3" in (D["seeds"][str(SEEDS[0])]["failed"] or []))
    P["P5_overlap_gt_disjoint"] = bool(lo_ is not None and ld is not None and lo_ > ld)
    rec["predictions"] = P

    if not P["P1_disjoint_lift_pos"]:
        verdict = "REPACKAGING — لایه لبهٔ مستقل ندارد"
    elif not P["P2_disjoint_ge_60pct"]:
        verdict = "NOVEL_BUT_COFIRING_HEAVY — لبه عمدتاً هم‌آتشی است"
    else:
        verdict = "NOVEL_EDGE_CONFIRMED — لبهٔ نوِ مستقل"
    rec["split_verdict"] = verdict

    print(f"\n  ── فرضیه‌های پیش‌ثبت‌شده ──", flush=True)
    for k, v in P.items():
        print(f"    {k:26s} = {v}", flush=True)
    print(f"\n  ══ حکمِ تفکیک: {verdict}", flush=True)
    print(f"     lift: FULL={lf}  DISJOINT={ld}  OVERLAP={lo_}", flush=True)

    # ── بندِ سومِ قانون: جهتِ الف ──
    print(f"\n  ── بندِ سومِ قانونِ همپوشانی · جهتِ الف "
          f"(لایهٔ ما به‌عنوانِ فیلترِ تأییدِ لایه‌های موجود، با براکتِ ما) ──",
          flush=True)
    rows = filter_direction_a(df, asset, sl, tp, mh, per_layer, sig, res, xbar)
    rec["filter_direction_a"] = rows
    print(f"    {'لایه':6s} {'n_all':>6s} {'WR_all':>7s} {'n_conf':>7s} "
          f"{'WR_conf':>8s} {'Δ':>7s} {'n_anti':>7s} {'WR_anti':>8s}", flush=True)
    for r in rows:
        if r.get("n_all", 0) == 0:
            print(f"    {r['code']:6s} {'—':>6s}  {r.get('note','')}", flush=True)
            continue
        f_ = lambda x: ('—' if x is None else f'{x:.2f}')
        print(f"    {r['code']:6s} {r['n_all']:6d} {f_(r['wr_all']):>7s} "
              f"{r['n_conf']:7d} {f_(r['wr_conf']):>8s} "
              f"{f_(r['delta']):>7s} {r['n_anti']:7d} {f_(r['wr_anti']):>8s}",
              flush=True)

    with open(f"{OUT}/overlap_split.json", "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1, default=float)
    print(f"\n[saved] {OUT}/overlap_split.json", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
