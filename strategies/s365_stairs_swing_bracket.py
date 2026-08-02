# -*- coding: utf-8 -*-
"""
S365 — Stairs (فصلِ ۲۶ Brooks) با **بریکتِ مقیاس‌شده با ارتفاعِ نوسان**

پیش‌ثبت: `results/S365_PREREG_swing_scaled_bracket.md` (پیش از اجرا commit شد)

════════════════════════════════════════════════════════════════════════════
تفاوتِ یک‌خطی با S364
════════════════════════════════════════════════════════════════════════════
        S364:  SL = s · ext          ← `ext` = «چقدر از پله رد شد» (ذاتاً کوچک)
        S365:  SL = s · pull         ← `pull` = ارتفاعِ نوسان/کانال

`ext` در متنِ Brooks نقشِ **جایِ ورود** را دارد، نه اندازهٔ ریسک. همین یک انتساب،
میانهٔ SL را روی EURUSD-M1 به ۳.۲ پیپ (≈۲ اسپرد) رساند و طبقِ اتحادِ
`E[R]_null = −c/SL` لایه را با بارِ هزینهٔ ۰.۴۹ R دفن کرد — پیش از آنکه هیچ
مهارتی وارد شود.

════════════════════════════════════════════════════════════════════════════
چرا آمارهٔ اصلی از ابتدا R است و نه WR
════════════════════════════════════════════════════════════════════════════
S364 روی XAUUSD-M5 در WR مهارتِ `6.23σ` نشان داد و PF=0.879 داشت. حسابِ واقعی
با ریسکِ درصدیِ ثابت، **R** می‌پردازد نه pip؛ و برای بریکتِ **شناور** این دو
حتی هم‌علامت نیستند (روی همان کارت: `+2794 pip` ولی `−10.97 R`). پس WR به‌عنوان
آمارهٔ حاکم برای این خانوادهٔ لایه‌ها ابزارِ غلطی است.

════════════════════════════════════════════════════════════════════════════
قاعدهٔ تصمیم (از پیش‌ثبت — دو شرطی)
════════════════════════════════════════════════════════════════════════════
    (۱) z ≥ 3.09σ  در برابرِ نالِ جای‌گشتیِ هم‌بریکت      ← مهارت
    (۲) mean R > 0                                       ← قابلِ تبدیل به پول
هر دو لازم‌اند. شرطِ (۲) دقیقاً همان چیزی است که S364 نداشت.
"""

import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s364_stairs_family import (                              # noqa: E402
    stairs_context, _first_per_segment, _armed_fire,
    TF_MAX_HOLD, MIN_TRADES,
)

OUT = "results/_scan_S365"

# ───────────────── خانوادهٔ ازپیش‌ثبت‌شده (۴۸ عضو · قفل) ─────────────────
FAM_K = (2, 3, 5)
FAM_F = (0.70, 1.00)
FAM_G = (0.67, 1.00)
FAM_S = (0.618, 1.000)          # ⭐ SL = s · pull  (نه s · ext)
FAM_MODE = ("close", "stop")
BODY_K = 0.5                    # «strong trend bar» — ثابت، سوئپ نمی‌شود
N_PERM = 500
Z_BAR = 3.09
ALL_CARDS = [("XAUUSD", tf) for tf in ("M5", "M15", "M30", "H1", "H4", "D1", "W1")] + \
            [("EURUSD", tf) for tf in ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1")]


def member_signals(df, ctx, f, g, s, mode, asset):
    """
    عینِ S364 در بخشِ **ورود**، و متفاوت فقط در بخشِ **بریکت**.

    ⚠️ نکتهٔ پیاده‌سازی: در حالتِ `stop`، هم سطحِ مرجع و هم `ext`/`pull` در لحظهٔ
    ماشه منجمد می‌شوند (درسِ باگِ S364). `_armed_fire` همین کار را می‌کند و سه
    آرایه برمی‌گرداند.
    """
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    o = df["open"].values.astype(float)
    n = len(df)
    pip = float(se.ASSETS[asset]["pip"])
    cost = float(se.ASSETS[asset]["spread_pip"]) + \
        2.0 * float(se.ASSETS[asset].get("slip_pip", 0.0))

    rng = np.maximum(h - l, 1e-12)
    body = np.abs(c - o)
    bear_bar = (c < o) & (body >= BODY_K * rng)
    bull_bar = (c > o) & (body >= BODY_K * rng)

    # ── LONG: fade در کانالِ خرسی ──
    btrig = ctx["bear_ok"] & bear_bar & (c <= (ctx["bear_ref"] - f * ctx["bear_ext"]))
    btrig = np.nan_to_num(btrig, nan=False).astype(bool)
    ext_l = np.nan_to_num(ctx["bear_ext"], nan=0.0)
    pull_l = np.nan_to_num(ctx["bear_pull"], nan=0.0)
    if mode == "close":
        long_sig = _first_per_segment(btrig, ctx["bear_seg"])
    else:
        long_sig, ext_l, pull_l = _armed_fire(
            btrig, np.nan_to_num(ctx["bear_ref"], nan=-np.inf),
            ext_l, pull_l, c, h, True)

    # ── SHORT: fade در کانالِ گاوی ──
    utrig = ctx["bull_ok"] & bull_bar & (c >= (ctx["bull_ref"] + f * ctx["bull_ext"]))
    utrig = np.nan_to_num(utrig, nan=False).astype(bool)
    ext_s = np.nan_to_num(ctx["bull_ext"], nan=0.0)
    pull_s = np.nan_to_num(ctx["bull_pull"], nan=0.0)
    if mode == "close":
        short_sig = _first_per_segment(utrig, ctx["bull_seg"])
    else:
        short_sig, ext_s, pull_s = _armed_fire(
            utrig, np.nan_to_num(ctx["bull_ref"], nan=np.inf),
            ext_s, pull_s, c, l, False)

    # ── ⭐ بریکت: هر دو ساق با `pull` مقیاس می‌شوند ──
    sl_pip = np.zeros(n)
    tp_pip = np.zeros(n)
    sl_pip[long_sig] = (s * pull_l[long_sig]) / pip
    tp_pip[long_sig] = (g * pull_l[long_sig]) / pip
    sl_pip[short_sig] = (s * pull_s[short_sig]) / pip
    tp_pip[short_sig] = (g * pull_s[short_sig]) / pip

    # قیدهای ریزساختاری (واقعیتِ بازار، نه پارامترِ قابلِ تنظیم):
    #   هدفی کوچک‌تر از دو برابرِ هزینه اصلاً معامله نیست.
    feasible = (tp_pip >= 2.0 * cost) & (sl_pip >= cost)
    long_sig = long_sig & feasible
    short_sig = short_sig & feasible
    return long_sig, short_sig, sl_pip, tp_pip


def _r_of(df, ls, ss, slv, tpv, asset, mh):
    """میانگینِ R یک عضو + آرایهٔ R + بریکتِ محقق‌شده."""
    tr = se.simulate_trades(df, ls, ss, slv, tpv, asset, max_hold=mh,
                            allow_overlap=False)
    if tr is None or len(tr) < MIN_TRADES:
        return None
    sl_u = tr["sl_pip"].values.astype(float)
    ok = sl_u > 0
    if ok.sum() < MIN_TRADES:
        return None
    R = tr["pnl_pip"].values[ok] / sl_u[ok]
    return dict(R=R, sl=sl_u[ok], n=int(ok.sum()),
                n_long=int((tr["direction"].values[ok] == "long").sum()),
                pnl=tr["pnl_pip"].values[ok])


def run_card(asset, tf, n_perm=N_PERM, seed=365, save=True):
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        print(f"   -- {asset}-{tf}: no data file")
        return None
    df = se.load_data(path)
    n = len(df)
    mh = TF_MAX_HOLD[tf]
    warm = min(260, max(30, n // 8))
    cfg = se.ASSETS[asset]
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    print(f"\n=== S365 FAMILY :: {asset}-{tf} (bars={n:,}) ===", flush=True)

    ctxs = {}
    for k in FAM_K:
        ctxs[k] = stairs_context(df, k)

    members, obs_R, all_sl, all_sig, all_isL, all_rr = [], [], [], [], [], []
    for k in FAM_K:
        for f in FAM_F:
            for g in FAM_G:
                for s in FAM_S:
                    for mode in FAM_MODE:
                        ls, ss, slv, tpv = member_signals(df, ctxs[k], f, g, s, mode, asset)
                        ls[:warm] = False
                        ss[:warm] = False
                        ls[n - mh - 2:] = False
                        ss[n - mh - 2:] = False
                        r = _r_of(df, ls, ss, slv, tpv, asset, mh)
                        if r is None:
                            continue
                        mR = float(r["R"].mean())
                        members.append(dict(k=k, f=f, g=g, s=s, mode=mode,
                                            n=r["n"], meanR=round(mR, 4),
                                            sumR=round(float(r["R"].sum()), 2),
                                            wr=round(100.0 * float((r["pnl"] > 0).mean()), 2),
                                            med_sl=round(float(np.median(r["sl"])), 2),
                                            burden=round(float(np.mean(cost / r["sl"])), 4)))
                        obs_R.append(mR)
                        all_sl.append(r["sl"])
                        idx = np.where(ls | ss)[0]
                        all_sig.append(idx)
                        all_isL.append(ls[idx])
                        # ⭐ نسبتِ TP/SL مالِ **همان عضو** است (g/s) و بینِ اعضا
                        # فرق می‌کند. نالِ هم‌بریکت فقط وقتی صادق است که هر عضو
                        # با نسبتِ خودش جای‌گشت شود، نه با یک ثابتِ سراسری.
                        all_rr.append(float(g) / float(s))
        print(f"    ctx k={k} done, alive={len(members)}", flush=True)

    if not members:
        res = dict(asset=asset, tf=tf, bars=n, verdict="NO_VIABLE_MEMBER",
                   n_members_alive=0)
        if save:
            _save(res, asset, tf)
        print("   >>> NO_VIABLE_MEMBER")
        return res

    fam_obs = float(np.mean(obs_R))
    burden_mean = float(np.mean([m["burden"] for m in members]))
    print(f"  OBSERVED family mean R = {fam_obs:+.4f}   alive={len(members)}/48")
    print(f"           member range   = [{min(obs_R):+.4f}, {max(obs_R):+.4f}]")
    print(f"           mean burden b  = {burden_mean:.4f}   "
          f"(theory says null ≈ {-burden_mean:+.4f})")

    # ── نالِ جای‌گشتی: زمانِ ورود تصادفی، مجموعهٔ بریکت‌ها دست‌نخورده ──
    rng = np.random.default_rng(seed)
    lo, hi = warm + 2, n - mh - 3
    perm_means = []
    o_ = df["open"].values.astype(float)
    h_ = df["high"].values.astype(float)
    l_ = df["low"].values.astype(float)
    pip = float(cfg["pip"])
    for _ in range(n_perm):
        rs = []
        for sl_arr, isL, rr in zip(all_sl, all_isL, all_rr):
            m = len(sl_arr)
            picks = rng.integers(lo, hi, size=m)
            sl_v = sl_arr[rng.permutation(m)]     # مجموعهٔ بریکت‌ها دست‌نخورده
            v = _perm_meanR(o_, h_, l_, picks, isL, sl_v, pip, mh, cost, rr)
            if v is not None:
                rs.append(v)
        perm_means.append(float(np.mean(rs)))
    perm_means = np.asarray(perm_means, dtype=float)
    null_mean = float(perm_means.mean())
    sd = float(perm_means.std(ddof=1)) or 1e-9
    lift = fam_obs - null_mean
    z = lift / sd
    p = float((perm_means >= fam_obs).sum() + 1) / (n_perm + 1)

    print(f"  NULL   family mean R = {null_mean:+.4f}   sd = {sd:.4f}  (perms={n_perm})")
    print(f"  LIFT_R = {lift:+.4f} R/trade   z = {z:+.2f}σ   p = {p:.4f}")

    skill = z >= Z_BAR
    money = fam_obs > 0
    verdict = ("FAMILY_CONFIRMED" if (skill and money) else
               "DEAD_NO_SKILL" if not skill else "DEAD_NEGATIVE_ABSOLUTE")
    print(f"  >>> {verdict}   (skill={skill}, positive={money})")

    res = dict(asset=asset, tf=tf, bars=n, n_members_alive=len(members),
               n_members_total=48, fam_meanR=round(fam_obs, 4),
               null_meanR=round(null_mean, 4), sd=round(sd, 4),
               lift=round(lift, 4), z=round(z, 3), p_perm=round(p, 5),
               burden_mean=round(burden_mean, 4),
               member_min=round(min(obs_R), 4), member_max=round(max(obs_R), 4),
               n_members_positive=int(sum(1 for x in obs_R if x > 0)),
               n_perm=n_perm, max_hold=mh, verdict=verdict, members=members)
    if save:
        _save(res, asset, tf)
    return res


def _perm_meanR(o, h, l, picks, isL, sl_v, pip, mh, cost, rr):
    """R میانگینِ یک جای‌گشت — همان بریکت‌ها و همان نسبتِ RRِ عضو، بارهای تصادفی."""
    m = len(picks)
    if m == 0:
        return None
    if len(isL) != m:
        isL = np.resize(isL, m)
    ent = o[picks + 1]
    sl_pr = sl_v * pip
    out = np.zeros(m)
    for i in range(m):
        st = picks[i] + 1
        en = min(st + mh, len(o) - 1)
        e = ent[i]
        d = sl_pr[i]
        if d <= 0:
            continue
        t = d * rr
        if isL[i]:
            hit_tp = np.argmax(h[st:en] >= e + t) if (h[st:en] >= e + t).any() else -1
            hit_sl = np.argmax(l[st:en] <= e - d) if (l[st:en] <= e - d).any() else -1
        else:
            hit_tp = np.argmax(l[st:en] <= e - t) if (l[st:en] <= e - t).any() else -1
            hit_sl = np.argmax(h[st:en] >= e + d) if (h[st:en] >= e + d).any() else -1
        if hit_tp < 0 and hit_sl < 0:
            px = o[en]
            raw = (px - e) if isL[i] else (e - px)
            out[i] = (raw / pip - cost) / (d / pip)
        elif hit_sl < 0 or (0 <= hit_tp <= hit_sl):
            out[i] = (t / pip - cost) / (d / pip)
        else:
            out[i] = (-d / pip - cost) / (d / pip)
    return float(out.mean())


def _save(res, asset, tf):
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/{asset}_{tf}.json"
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1)
    print(f"    saved -> {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="XAUUSD")
    ap.add_argument("--tf", default="M5")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--perm", type=int, default=N_PERM)
    a = ap.parse_args()
    cards = ALL_CARDS if a.all else [(a.asset, a.tf)]
    for asset, tf in cards:
        try:
            run_card(asset, tf, n_perm=a.perm)
        except Exception as e:                                            # noqa: BLE001
            print(f"   !! {asset}-{tf} failed: {e}", flush=True)


if __name__ == "__main__":
    main()
