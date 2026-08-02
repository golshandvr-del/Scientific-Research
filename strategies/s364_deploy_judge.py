# -*- coding: utf-8 -*-
"""
S364 — مرحلهٔ ۲: انتخابِ «نسخهٔ مستقر» + داوریِ کاملِ RQS2 (۱۱ دروازه)
===================================================================

این فایل **فقط** روی کارت‌هایی اجرا می‌شود که در مرحلهٔ ۱ (آزمونِ خانواده،
`s364_stairs_family.py`) حکمِ `FAMILY_CONFIRMED` گرفته‌اند:

    XAUUSD-M5   z = +6.23σ
    EURUSD-M1   z = +4.60σ
    EURUSD-M15  z = +3.17σ

طبقِ پیش‌ثبتِ `results/S364_PREREG_multiplicity_route.md` (§۴):

  «فقط روی کارتِ تأییدشده اجازهٔ انتخابِ نسخهٔ مستقر هست، و آن انتخاب باید
   **فقط از نیمهٔ اولِ داده** انجام شود تا نیمهٔ دوم دست‌نخورده بماند و
   دروازهٔ H7 معنا داشته باشد.»

بنابراین ترتیبِ اجرا در این فایل **اجباراً** این است:

  ۱) نیمهٔ اولِ داده (کشف)  → هر ۷۲ عضو ارزیابی، بهترین با پراکسیِ لبه انتخاب.
  ۲) نیمهٔ دوم (holdout)    → **هرگز** در انتخاب دیده نمی‌شود.
  ۳) عضوِ منتخب روی **کلِ** داده اجرا و با RQS2 داوری می‌شود، با
     `holdout_mask` = معاملاتی که ورودشان در نیمهٔ دوم است ⇒ H7 واقعی.
  ۴) `n_trials = 72` (اندازهٔ واقعیِ فضایی که در نیمهٔ کشف پیموده شد) ⇒ H5
     صادقانه جریمه می‌شود. این عدد را کم نمی‌کنیم.


⭐ نکتهٔ فنیِ مهم — «بریکتِ شناور و دروازهٔ H2»
--------------------------------------------
`compute_rqs2` برای H2 یک `sl_pip`/`tp_pip` **اسکالر** می‌خواهد، ولی هستهٔ
فصلِ ۲۶ این است که هر معامله بریکتِ خودش را دارد. پس چه عددی صادقانه است؟

میانه (median) وسوسه‌انگیز است ولی **غلط** است. جبرِ درست:

    E = Σᵢ [ p·(TPᵢ − c) − (1−p)·(SLᵢ + c) ]  > 0
  ⇔ p · Σ(TPᵢ + SLᵢ) > Σ(SLᵢ + c)
  ⇔ p > Σ(SLᵢ + c) / Σ(TPᵢ + SLᵢ)
  ⇔ p > ( mean(SL) + c ) / ( mean(TP) + mean(SL) )

و این **دقیقاً** همان چیزی است که `breakeven_wr_cost(mean_SL, mean_TP, c)`
برمی‌گرداند. یعنی برای بریکتِ شناور، **میانگینِ حسابی** (نه میانه) نمایندهٔ
*دقیقِ* سربه‌سرِ پرتفوی است — نه یک تقریب. پس همان را پاس می‌دهیم و این
اشتقاق را اینجا ثبت می‌کنیم تا خوانندهٔ بعدی نپندارد عددی سرانگشتی است.

افزون بر آن، یک **H2-strict** جداگانه هم حساب می‌کنیم: نسبتِ معاملاتی که
`TPᵢ < SLᵢ` دارند. اگر لایه‌ای WR را با TPِ ریز باد کرده باشد (اشتباهِ رایجِ #۸)
این عدد بالا می‌رود، حتی اگر میانگین‌ها ظاهرِ سالمی داشته باشند. میانگین می‌تواند
یک دنبالهٔ بدخیم را پنهان کند؛ این شاخص نمی‌گذارد.


⭐ مدلِ صفر (همان که پیش‌ثبت شد)
------------------------------
جای‌گشتِ **زمانِ ورود** با حفظِ: تعدادِ معامله، نسبتِ long/short، و
**چندگانِ کاملِ بریکت‌ها** (بریکت‌ها بُر می‌خورند و به بارهای تصادفی می‌چسبند).
پس رقیبِ بی‌مهارت دقیقاً همان هندسهٔ معاملاتیِ ما را دارد و تنها چیزی که
ندارد «انتخابِ لحظه» است — یعنی همان چیزی که ادعا می‌کنیم داریم.

دو استخرِ بار آزموده می‌شود و **سخت‌ترینش** مبنا قرار می‌گیرد:
  • استخرِ آزاد  : همهٔ بارهای مجاز.
  • استخرِ گِیتی : فقط بارهایی که *در زمینهٔ stairs* هستند (رقیبِ به‌مراتب
    قوی‌تر: کسی که الگو را می‌شناسد ولی ماشه را نمی‌داند). اگر لبه از این
    هم رد شود، لبه در **ماشه** است نه صرفاً در «بودن داخلِ الگو».
"""

import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se            # noqa: E402
from engine import rqs2                          # noqa: E402
from strategies.s364_stairs_family import (      # noqa: E402
    FAM_K, FAM_F, FAM_G, FAM_S, FAM_MODE, TF_MAX_HOLD, MIN_TRADES,
    stairs_context, member_signals, _sim_vec, _wr_no_overlap,
)

OUT = "results/_scan_S364"
CONFIRMED = [("XAUUSD", "M5"), ("EURUSD", "M1"), ("EURUSD", "M15")]
N_PERM = 500
N_TRIALS = 72          # اندازهٔ واقعیِ فضای جست‌وجو در نیمهٔ کشف — کم نمی‌شود


def _edge_proxy(pf, n):
    """پراکسیِ لبه برای رتبه‌بندی در نیمهٔ کشف: (PF−1)·√n.

    چرا حاصل‌ضرب: PF به‌تنهایی با n=۳ معامله بی‌معنا بالا می‌رود و n به‌تنهایی
    کیفیت را نمی‌سنجد. √n وزنِ شواهد است. این همان پراکسیِ S354 است تا بینِ
    لایه‌ها قابلِ مقایسه بماند.
    """
    return (float(pf) - 1.0) * (max(int(n), 0) ** 0.5)


def _perm_null_floating(o, h, l, c, pool, n_side, is_long_flag, brackets,
                        pip, mh, cost, n, rng, n_perm):
    """توزیعِ WRِ صفر با حفظِ چندگانِ بریکت‌ها.

    `brackets` = آرایهٔ (n_side, 2) از (sl_pip, tp_pip)ِ *واقعیِ* همان سمت.
    در هر جای‌گشت: n_side بارِ تصادفی از `pool` + بُرِ همان بریکت‌ها.
    """
    if n_side < 1 or pool.size <= n_side:
        return None
    wrs = []
    for _ in range(n_perm):
        picks = rng.choice(pool, size=n_side, replace=False)
        picks.sort()
        perm = rng.permutation(n_side)
        slv = brackets[perm, 0]
        tpv = brackets[perm, 1]
        flags = np.full(n_side, bool(is_long_flag))
        r = _sim_vec(o, h, l, c, picks, flags, slv, tpv, pip, mh, cost, n)
        if r is None:
            continue
        p2, win, exit_bar = r
        wr, used = _wr_no_overlap(p2, win, exit_bar)
        if wr is not None and used >= max(5, n_side // 3):
            wrs.append(wr)
    if len(wrs) < max(30, n_perm // 8):
        return None
    a = np.asarray(wrs, dtype=float)
    return dict(uncond_wr=float(a.mean()), perm_mean=float(a.mean()),
                perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()),
                perm_k=int(a.size))


def build_null(df, asset, tf, trades, ls, ss, slv, tpv, ctx, warm, mh, rng):
    """مدلِ صفرِ کانونیِ RQS2 برای بریکتِ شناور — دو استخر، سخت‌ترین برنده."""
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    n = len(df)
    pip = se.ASSETS[asset]["pip"]
    cfg = se.ASSETS[asset]
    cost = cfg["spread_pip"] + 2.0 * cfg.get("slip_pip", 0.0)

    free_pool = np.arange(warm, n - mh - 2)
    in_ctx = np.nan_to_num(ctx["bear_ok"], nan=False).astype(bool) | \
        np.nan_to_num(ctx["bull_ok"], nan=False).astype(bool)
    gated_pool = free_pool[in_ctx[free_pool]]

    null, diag = {}, {}
    for side, flag, sig in (("long", True, ls), ("short", False, ss)):
        idx = np.where(sig)[0]
        n_side = int(idx.size)
        if n_side < 1:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)
            continue
        br = np.column_stack([slv[idx], tpv[idx]])
        cands = []
        u = _perm_null_floating(o, h, l, c, free_pool, n_side, flag, br,
                                pip, mh, cost, n, rng, N_PERM)
        if u:
            cands.append(("free", u))
        g = _perm_null_floating(o, h, l, c, gated_pool, n_side, flag, br,
                                pip, mh, cost, n, rng, N_PERM)
        if g:
            cands.append(("gated", g))
        if cands:
            tag, best = max(cands, key=lambda kv: kv[1]["perm_mean"])
            null[side] = best
            diag[side] = dict(chosen=tag,
                              wrs={k: round(v["perm_mean"], 2) for k, v in cands},
                              n_side=n_side)
        else:
            null[side] = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                              perm_max=None, perm_k=None)
    return null, diag


def run_card(asset, tf, seed=364):
    path = f"data/{asset}_{tf}.csv"
    df = se.load_data(path)
    n = len(df)
    mh = TF_MAX_HOLD.get(tf, 40)
    warm = min(260, max(30, n // 8))
    split = n // 2
    rng = np.random.default_rng(seed)

    print(f"\n=== S364 DEPLOY-JUDGE :: {asset}-{tf} (bars={n:,} split@{split:,}) ===",
          flush=True)

    ctxs = {k: stairs_context(df, k) for k in FAM_K}

    # ---------- گامِ ۱: انتخاب فقط روی نیمهٔ اول ----------
    cands = []
    for k in FAM_K:
        for f in FAM_F:
            for g in FAM_G:
                for s in FAM_S:
                    for mode in FAM_MODE:
                        ls, ss, slv, tpv = member_signals(df, ctxs[k], f, g, s,
                                                          mode, asset)
                        ls[:warm] = False; ss[:warm] = False
                        ls[n - mh - 2:] = False; ss[n - mh - 2:] = False
                        # ⚠️ کشف = فقط نیمهٔ اول
                        d_ls = ls.copy(); d_ss = ss.copy()
                        d_ls[split:] = False; d_ss[split:] = False
                        if int(d_ls.sum() + d_ss.sum()) < MIN_TRADES:
                            continue
                        tr = se.simulate_trades(df, d_ls, d_ss, slv, tpv, asset,
                                                max_hold=mh, allow_overlap=False)
                        if tr is None or len(tr) < MIN_TRADES:
                            continue
                        pnl = tr["pnl_pip"].values
                        gain = float(pnl[pnl > 0].sum())
                        loss = float(-pnl[pnl < 0].sum())
                        pf = (gain / loss) if loss > 0 else 999.0
                        cands.append(dict(k=k, f=f, g=g, s=s, mode=mode,
                                          disc_n=int(len(tr)),
                                          disc_pf=round(pf, 3),
                                          disc_wr=round(100.0 * float((pnl > 0).sum())
                                                        / len(tr), 2),
                                          disc_net=round(float(pnl.sum()), 1),
                                          proxy=round(_edge_proxy(pf, len(tr)), 3)))
    if not cands:
        print("   NO discovery-half candidate")
        return dict(asset=asset, tf=tf, verdict="NO_DISCOVERY_CANDIDATE")

    cands.sort(key=lambda r: r["proxy"], reverse=True)
    pick = cands[0]
    print(f"   discovery candidates = {len(cands)}   picked = "
          f"k={pick['k']} f={pick['f']} g={pick['g']} s={pick['s']} "
          f"mode={pick['mode']}  (disc n={pick['disc_n']} PF={pick['disc_pf']} "
          f"WR={pick['disc_wr']}%)", flush=True)

    # ---------- گامِ ۲: همان عضو روی کلِ داده ----------
    ls, ss, slv, tpv = member_signals(df, ctxs[pick["k"]], pick["f"], pick["g"],
                                      pick["s"], pick["mode"], asset)
    ls[:warm] = False; ss[:warm] = False
    ls[n - mh - 2:] = False; ss[n - mh - 2:] = False
    trades = se.simulate_trades(df, ls, ss, slv, tpv, asset, max_hold=mh,
                                allow_overlap=False)
    if trades is None or len(trades) == 0:
        return dict(asset=asset, tf=tf, verdict="NO_TRADES_FULL")

    eb = trades["entry_bar"].values.astype(int)
    sl_used = slv[eb - 1]
    tp_used = tpv[eb - 1]
    mean_sl = float(np.mean(sl_used))
    mean_tp = float(np.mean(tp_used))
    frac_tp_lt_sl = float(np.mean(tp_used < sl_used))
    print(f"   full-sample trades = {len(trades):,}   mean SL={mean_sl:.2f}pip "
          f"mean TP={mean_tp:.2f}pip  RR={mean_tp/mean_sl:.3f}  "
          f"frac(TP<SL)={frac_tp_lt_sl:.3f}", flush=True)

    # ---------- گامِ ۳: مدلِ صفر ----------
    null, ndiag = build_null(df, asset, tf, trades, ls, ss, slv, tpv,
                             ctxs[pick["k"]], warm, mh, rng)
    print(f"   null: {json.dumps(ndiag, ensure_ascii=False)}", flush=True)

    # ---------- گامِ ۴: داوریِ RQS2 ----------
    holdout_mask = (eb >= split)
    bar_time = df["time"].values if "time" in df.columns else None
    res = rqs2.compute_rqs2(trades, asset, sl_pip=mean_sl, tp_pip=mean_tp,
                            bar_time=bar_time, null=null, n_trials=N_TRIALS,
                            holdout_mask=holdout_mask,
                            close=df["close"].values.astype(float))
    gates = res.get("gates", {})
    print(f"   VERDICT = {res.get('verdict')}   score={res.get('rqs2_score')}",
          flush=True)
    print("   gates: " + "  ".join(f"{k}={'✓' if v else ('?' if v is None else '✗')}"
                                   for k, v in gates.items()), flush=True)
    for nt in res.get("notes", [])[:14]:
        print("     · " + str(nt), flush=True)

    out = dict(asset=asset, tf=tf, bars=n, split=split, picked=pick,
               n_candidates=len(cands),
               n_trades=int(len(trades)),
               mean_sl=round(mean_sl, 3), mean_tp=round(mean_tp, 3),
               rr=round(mean_tp / mean_sl, 3),
               frac_tp_lt_sl=round(frac_tp_lt_sl, 4),
               n_trials=N_TRIALS,
               null_diag=ndiag,
               verdict=res.get("verdict"), rqs2_score=res.get("rqs2_score"),
               gates=gates, metrics=res.get("metrics"),
               notes=res.get("notes"),
               top5_discovery=cands[:5])
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/JUDGE_{asset}_{tf}.json"
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f"   saved -> {p}", flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset")
    ap.add_argument("--tf")
    args = ap.parse_args()
    cards = ([(args.asset, args.tf)] if args.asset and args.tf else CONFIRMED)
    for a, t in cards:
        try:
            run_card(a, t)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"   !! {a}-{t} failed: {e}", flush=True)


if __name__ == "__main__":
    main()
