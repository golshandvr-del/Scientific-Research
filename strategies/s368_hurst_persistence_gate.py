# -*- coding: utf-8 -*-
"""
S368 — Stairs channel breakout × **دروازهٔ پایداریِ Hurst**
پیش‌ثبت: `results/S368_PREREG_hurst_persistence_gate.md` (پیش از اجرا commit شد)

─────────────────────────────────────────────────────────────────────────────
چرا این فایل «نازک» است و منطقِ سیگنال را **وارد می‌کند** نه بازنویسی
─────────────────────────────────────────────────────────────────────────────
ادعای علمیِ این نشست دقیقاً یک جمله است: «دروازهٔ رژیم، `e_pip` را بالا می‌برد».
اگر منطقِ کانال/شکست را دوباره تایپ می‌کردم، هر تفاوتی در نتیجه می‌توانست از یک
واگراییِ ناخواسته در تشخیصِ الگو آمده باشد و مقایسه هیچ چیز را جدا نمی‌کرد.
پس `channel_context` و `member_signals` **عیناً** از S366 وارد می‌شوند و تنها
چیزی که اضافه می‌شود یک ماسکِ بولین روی بارهای سیگنال است.

─────────────────────────────────────────────────────────────────────────────
چرا `hurst` و نه یکی از ۴۰۰ اندیکاتورِ دیگر (بندِ ۱ پیش‌ثبت)
─────────────────────────────────────────────────────────────────────────────
گشتن در بانک تا «آنکه جواب می‌دهد» پیدا شود، جست‌وجویی با چندگانگیِ ۴۰۰ است و
بهایش پرداختنی نیست. این فیلتر از **سند** برداشته شد نه از داده:
`docs/indicators/statistical.md` ذیلِ `hurst` صریحاً نسخه می‌پیچد که
«`H>0.55 ⇒ فقط لایهٔ breakout`» و می‌گوید همین یک فیلتر می‌تواند چند لایهٔ سوخته
را احیا کند. لایهٔ ما دقیقاً یک لایهٔ breakout است.

─────────────────────────────────────────────────────────────────────────────
⭐ چرا `e_pip` (نه z و نه mean R) کمیتِ اصلیِ گزارش است
─────────────────────────────────────────────────────────────────────────────
طبقِ `docs/FINDING_R_SPACE_BASELINE_LAW.md §۷`:

        E[R] = (e_pip − c) / SL

`SL` فقط در مخرج است ⇒ علامت را تعیین نمی‌کند. کاری که یک فیلتر *می‌تواند*
بکند فقط بالا بردنِ `e_pip` است. پس آزمونِ واقعیِ این فیلتر این است:
`e_pip` بالا رفت یا نه — نه اینکه z بالا رفت یا نه.

**آزمونِ متقارنِ ابطال (بندِ ۵ پیش‌ثبت):** اگر دروازه فقط تعدادِ معامله را کم کند
و رژیم را انتخاب نکند، `e_pip` تقریباً ثابت می‌ماند و فقط `n` می‌ریزد. در آن حالت
حتی اگر z تصادفاً بالا رفته باشد، حکم این است که **hurst برای این لایه بی‌اثر است**.
برای همین `e_pip` و `n` هر دو در کنارِ نتیجهٔ S366 چاپ می‌شوند.
"""

import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from engine import indicator_bank as ib                                  # noqa: E402
from strategies.s364_stairs_family import MIN_TRADES                     # noqa: E402
from strategies.s366_stairs_channel_breakout import (                    # noqa: E402
    channel_context, member_signals, _perm_meanR,
    FAM_K, FAM_M, FAM_S, HORIZON_MULT, MAX_HOLD_CAP, ALL_CARDS, Z_BAR,
)

OUT = "results/_scan_S368"
N_PERM = 400

# ───────────── محورهای دروازه (قفل‌شده در پیش‌ثبت، تغییرناپذیر) ─────────────
# دوره‌ها فیبوناچی و **غیررند**اند. پیش‌فرضِ سندِ بانک ۶۴ است — عمداً استفاده
# نشد، چون ۶۴ توانِ رندِ ۲ است و اشتباهِ رایجِ #۷ دقیقاً همین عادت است.
GATE_P = (55, 89)
# ۰.۵۰ = مرزِ ریاضیِ گشتِ تصادفی (اصلاً عددِ برازش‌شده نیست)
# ۰.۵۵ = عددی که خودِ سندِ بانک صریح نوشته
GATE_TH = (0.50, 0.55)


def hurst_series(df, p):
    """نمای هرست از بانک. علّی است: پنجرهٔ بارِ t فقط بازده‌های تا خودِ t را
    می‌بیند و ورود در open بارِ t+1 انجام می‌شود ⇒ هیچ نگاهِ‌به‌آینده‌ای نیست."""
    return ib.hurst(df, p=p).values.astype(float)


def run_card(asset, tf, n_perm=N_PERM, seed=368, save=True):
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        print(f"   !! missing {path}")
        return None
    df = se.load_data(path)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    warm = min(260, max(30, n // 8))
    half = n // 2
    print(f"\n=== S368 hurst-gate :: {asset}-{tf} (bars={n:,}) ===", flush=True)

    ctxs = {k: channel_context(df, k) for k in FAM_K}

    # افقِ نگه‌داری دقیقاً مثلِ S366 از هندسهٔ الگو می‌آید (نه از نتیجهٔ معاملات)
    # و **بدونِ دروازه** محاسبه می‌شود، تا دروازه نتواند افق را جابه‌جا کند و
    # مقایسهٔ S366↔S368 روی یک افقِ یکسان بماند.
    durs = []
    for k in FAM_K:
        ls, ss, _, _, dur = member_signals(df, ctxs[k], FAM_M[0], FAM_S[0], asset, True)
        sel = ls | ss
        if sel.any():
            durs.extend(dur[sel].tolist())
    if not durs:
        res = dict(asset=asset, tf=tf, bars=n, verdict="NO_CONTEXT")
        if save:
            _save(res, asset, tf)
        print("   NO_CONTEXT")
        return res
    mh = int(min(MAX_HOLD_CAP, max(5, round(HORIZON_MULT * float(np.median(durs))))))
    print(f"    max_hold={mh} (median channel duration={np.median(durs):.0f})", flush=True)

    hs = {p: hurst_series(df, p) for p in GATE_P}
    for p in GATE_P:
        v = hs[p][np.isfinite(hs[p])]
        print(f"    hurst p={p}: med={np.median(v):.3f} "
              f"share>0.50={np.mean(v > 0.50):.3f} share>0.55={np.mean(v > 0.55):.3f}",
              flush=True)

    members, obsR, sls, rrs, isLs, halves, burdens = [], [], [], [], [], [], []
    n_alive = 0
    for k in FAM_K:
        ctx = ctxs[k]
        for m_ in FAM_M:
            for s_ in FAM_S:
                ls0, ss0, slv, tpv, _ = member_signals(df, ctx, m_, s_, asset, True)
                for gp in GATE_P:
                    H = hs[gp]
                    for th in GATE_TH:
                        keep = np.nan_to_num(H > th, nan=False)
                        ls = ls0 & keep
                        ss = ss0 & keep
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
                        n_alive += 1
                        R = tr["pnl_pip"].values[okm] / sl[okm]
                        eb = tr["entry_bar"].values.astype(int)[okm]
                        isL = (tr["direction"].values[okm] == "long")
                        members.append(dict(k=k, m=m_, s=s_, p=gp, th=th,
                                            n=int(okm.sum()),
                                            meanR=round(float(R.mean()), 4),
                                            med_sl=round(float(np.median(sl[okm])), 2),
                                            burden=round(float(np.mean(cost / sl[okm])), 4),
                                            wr=round(100.0 * float((R > 0).mean()), 2)))
                        obsR.append(float(R.mean()))
                        sls.append(sl[okm])
                        rrs.append(float(m_) / float(s_))
                        isLs.append(isL)
                        burdens.append(float(np.mean(cost / sl[okm])))
                        f1 = eb < half
                        halves.append((float(R[f1].mean()) if f1.sum() >= 5 else np.nan,
                                       float(R[~f1].mean()) if (~f1).sum() >= 5 else np.nan))

    n_total_fam = len(FAM_K) * len(FAM_M) * len(FAM_S) * len(GATE_P) * len(GATE_TH)
    if not members:
        res = dict(asset=asset, tf=tf, bars=n, n_members_alive=0,
                   n_members_total=n_total_fam, verdict="NO_VIABLE_MEMBER")
        if save:
            _save(res, asset, tf)
        print("   NO_VIABLE_MEMBER")
        return res

    fam = float(np.mean(obsR))
    h1 = float(np.nanmean([a for a, _ in halves]))
    h2 = float(np.nanmean([b for _, b in halves]))
    tot = int(sum(m_["n"] for m_ in members))
    mean_sl = float(np.mean([np.mean(s_) for s_ in sls]))
    print(f"  OBSERVED family mean R = {fam:+.4f}   alive={n_alive}/{n_total_fam}"
          f"  Σn={tot:,}")
    print(f"           member range   = [{min(obsR):+.4f}, {max(obsR):+.4f}]")
    print(f"           halves         = ({h1:+.4f}, {h2:+.4f})")
    print(f"           mean burden b  = {np.mean(burdens):.4f}   mean SL={mean_sl:.1f}pip",
          flush=True)

    rng = np.random.default_rng(seed)
    o_ = df["open"].values.astype(float)
    h_ = df["high"].values.astype(float)
    l_ = df["low"].values.astype(float)
    lo, hi = warm, n - mh - 2
    perms = []
    for _ in range(n_perm):
        vals = []
        for sl_arr, isL, rr in zip(sls, isLs, rrs):
            mlen = len(sl_arr)
            picks = rng.integers(lo, hi, size=mlen)
            v = _perm_meanR(o_, h_, l_, picks, isL,
                            sl_arr[rng.permutation(mlen)], pip, mh, cost, rr)
            if v is not None:
                vals.append(v)
        if vals:
            perms.append(float(np.mean(vals)))
    perms = np.asarray(perms, dtype=float)
    nullm = float(perms.mean())
    sd = float(perms.std(ddof=1)) or 1e-9
    z = (fam - nullm) / sd
    p_perm = float((perms >= fam).mean())
    lift = fam - nullm
    e_pip = lift * mean_sl          # ⭐ کمیتِ تصمیم‌ساز

    skill = z >= Z_BAR
    positive = fam > 0
    repl = (h1 > 0) and (h2 > 0)
    if skill and positive and repl:
        verdict = "FAMILY_CONFIRMED"
    elif skill and positive:
        verdict = "DEAD_NO_REPLICATION"
    elif skill:
        verdict = "DEAD_NEGATIVE_ABSOLUTE"
    else:
        verdict = "DEAD_NO_SKILL"

    print(f"  NULL   family mean R = {nullm:+.4f}   sd = {sd:.4f}  (perms={len(perms)})")
    print(f"  LIFT_R = {lift:+.4f} R/trade   z = {z:+.2f}σ   p = {p_perm:.4f}")
    print(f"  ⭐ e_pip = {e_pip:+.2f} pip   vs cost c = {cost:.2f}   "
          f"⇒ {'CLEARS' if e_pip > cost else 'BELOW'} cost")
    print(f"  >>> {verdict}   (skill={skill}, positive={positive}, repl={repl})",
          flush=True)

    # ── مقایسهٔ مستقیم با S366 (تشخیصی؛ در معیارِ پذیرش دخالت ندارد) ──
    base = _load_s366(asset, tf)
    if base:
        b_lift = base.get("lift")
        b_burd = base.get("burden_mean") or 0.0
        b_sl = (cost / b_burd) if b_burd > 0 else np.nan
        b_e = (b_lift * b_sl) if (b_lift is not None and np.isfinite(b_sl)) else np.nan
        b_n = base.get("n_total_trades")
        if np.isfinite(b_e) and b_n:
            d_e = 100.0 * (e_pip - b_e) / abs(b_e) if b_e else np.nan
            d_n = 100.0 * (tot - b_n) / b_n
            print(f"  ── vs S366(ungated): e_pip {b_e:+.2f} → {e_pip:+.2f} "
                  f"({d_e:+.0f}%)   n {b_n:,} → {tot:,} ({d_n:+.0f}%)")
            # آزمونِ متقارنِ ابطالِ بندِ ۵ پیش‌ثبت
            if abs(d_e) < 15.0 and d_n < -15.0:
                print("     ⚠️ FILTER-INERT: n افت کرد ولی e_pip تقریباً ثابت ماند "
                      "⇒ دروازه رژیم انتخاب نمی‌کند، فقط نمونه را کوچک می‌کند.")

    res = dict(asset=asset, tf=tf, bars=n, max_hold=mh,
               n_members_alive=n_alive, n_members_total=n_total_fam,
               n_total_trades=tot, fam_meanR=round(fam, 4),
               null_meanR=round(nullm, 4), sd=round(sd, 4), lift=round(lift, 4),
               z=round(z, 3), p_perm=round(p_perm, 4),
               burden_mean=round(float(np.mean(burdens)), 4),
               mean_sl_pip=round(mean_sl, 2), e_pip=round(e_pip, 3), cost=cost,
               half1_meanR=round(h1, 4), half2_meanR=round(h2, 4),
               member_min=round(min(obsR), 4), member_max=round(max(obsR), 4),
               n_members_positive=int(sum(1 for x in obsR if x > 0)),
               gate_p=list(GATE_P), gate_th=list(GATE_TH),
               members=members, verdict=verdict)
    if save:
        _save(res, asset, tf)
    return res


def _load_s366(asset, tf):
    p = f"results/_scan_S366/{asset}_{tf}.json"
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception:
        return None


def _save(res, asset, tf):
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/{asset}_{tf}.json"
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1)
    print(f"    saved -> {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset")
    ap.add_argument("--tf")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--perm", type=int, default=N_PERM)
    a = ap.parse_args()
    cards = ALL_CARDS if a.all else [(a.asset, a.tf)]
    for asset, tf in cards:
        try:
            run_card(asset, tf, n_perm=a.perm)
        except Exception as ex:
            print(f"   !! {asset}-{tf} failed: {ex}", flush=True)


if __name__ == "__main__":
    main()
