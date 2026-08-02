# -*- coding: utf-8 -*-
"""
S369 — «ادامهٔ پله» (Stair Continuation): ماشهٔ S365 با **جهتِ معکوس**
پیش‌ثبت: `results/S369_PREREG_stair_continuation.md` (پیش از اجرا commit شد)

─────────────────────────────────────────────────────────────────────────────
تفاوت با S365 دقیقاً یک خط است
─────────────────────────────────────────────────────────────────────────────
`member_signals`ِ S365 **عیناً** وارد می‌شود (بازنویسی نمی‌شود) و سپس:

        long_sig, short_sig  ←→  short_sig, long_sig

یعنی: همان بارِ ماشه، همان `SL`، همان `TP`، فقط سمتِ معامله برعکس.
چرا اینقدر روی «فقط یک خط» تأکید می‌کنم؟ چون ادعای این نشست این است که
«بازار پس از شکستِ پله ادامه می‌دهد». این ادعا فقط وقتی قابلِ اندازه‌گیری است
که هیچ چیزِ دیگری فرق نکند. اگر منطقِ الگو را دوباره تایپ می‌کردم، هر تفاوتی
در نتیجه می‌توانست از یک واگراییِ ناخواسته آمده باشد.

⚠️ **نکتهٔ ظریفِ مهم:** معکوس‌کردنِ جهت با بریکتِ **نامتقارن** (`TP ≠ SL`)
معادلِ قرینه‌کردنِ نتیجه **نیست**. در سمتِ لانگ، `TP` بالای ورود و `SL` پایینِ
آن است؛ با معکوس‌کردنِ سمت، همان دو عدد جای خود را عوض می‌کنند و هندسهٔ
خروج واقعاً فرق می‌کند. پس `e_pip`ِ معکوس ≠ `−e_pip`ِ اصلی، و برآوردِ بندِ ۲
پیش‌ثبت باید **اندازه‌گیری** شود نه استنتاج. انطباق/عدم‌انطباق با آن برآورد
خودش گزارش می‌شود.

─────────────────────────────────────────────────────────────────────────────
حالتِ `stop` عمداً حذف شد
─────────────────────────────────────────────────────────────────────────────
S365 دو حالتِ ورود داشت. حالتِ `stop` منطقش «منتظرِ چرخشِ بازار بمان» است —
که مفهوماً یک قاعدهٔ **fade** است و در جهتِ ادامه بی‌معنا می‌شود. پس خانواده
فقط حالتِ `close` را دارد ⇒ ۳×۲×۲×۲ = **۲۴ عضو** (مطابقِ پیش‌ثبت).
"""

import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s364_stairs_family import (                              # noqa: E402
    stairs_context, TF_MAX_HOLD, MIN_TRADES,
)
from strategies.s365_stairs_swing_bracket import (                       # noqa: E402
    member_signals as fade_signals, _perm_meanR,
    FAM_K, FAM_F, FAM_G, FAM_S, ALL_CARDS, Z_BAR,
)

OUT = "results/_scan_S369"
N_PERM = 500

# معیارِ ۴ پیش‌ثبت: دستِ‌کم نیمی از اعضا باید مثبت باشند (فلاتِ پایدار)
PLATEAU_FRAC = 0.50


def continuation_signals(df, ctx, f, g, s, asset):
    """همان ماشه و همان بریکتِ S365 — فقط سمتِ معامله معکوس."""
    ls, ss, slv, tpv = fade_signals(df, ctx, f, g, s, "close", asset)
    return ss, ls, slv, tpv          # ⭐ تنها تفاوتِ کلِ لایه


def run_card(asset, tf, n_perm=N_PERM, seed=369, save=True):
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        print(f"   !! missing {path}")
        return None
    df = se.load_data(path)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))
    mh = TF_MAX_HOLD[tf]
    warm = min(260, max(30, n // 8))
    half = n // 2
    print(f"\n=== S369 continuation :: {asset}-{tf} (bars={n:,}, mh={mh}) ===", flush=True)

    ctxs = {k: stairs_context(df, k) for k in FAM_K}

    members, obsR, sls, rrs, isLs, halves, burdens = [], [], [], [], [], [], []
    n_alive = 0
    for k in FAM_K:
        ctx = ctxs[k]
        for f in FAM_F:
            for g in FAM_G:
                for s in FAM_S:
                    ls, ss, slv, tpv = continuation_signals(df, ctx, f, g, s, asset)
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
                    members.append(dict(k=k, f=f, g=g, s=s, n=int(okm.sum()),
                                        meanR=round(float(R.mean()), 4),
                                        med_sl=round(float(np.median(sl[okm])), 2),
                                        burden=round(float(np.mean(cost / sl[okm])), 4),
                                        wr=round(100.0 * float((R > 0).mean()), 2)))
                    obsR.append(float(R.mean()))
                    sls.append(sl[okm])
                    rrs.append(float(g) / float(s))
                    isLs.append(isL)
                    burdens.append(float(np.mean(cost / sl[okm])))
                    f1 = eb < half
                    halves.append((float(R[f1].mean()) if f1.sum() >= 5 else np.nan,
                                   float(R[~f1].mean()) if (~f1).sum() >= 5 else np.nan))

    n_total_fam = len(FAM_K) * len(FAM_F) * len(FAM_G) * len(FAM_S)
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
    tot = int(sum(m["n"] for m in members))
    mean_sl = float(np.mean([np.mean(x) for x in sls]))
    n_pos = int(sum(1 for x in obsR if x > 0))
    print(f"  OBSERVED family mean R = {fam:+.4f}   alive={n_alive}/{n_total_fam}"
          f"  Σn={tot:,}")
    print(f"           member range   = [{min(obsR):+.4f}, {max(obsR):+.4f}]"
          f"   positive={n_pos}/{n_alive}")
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
    e_pip = lift * mean_sl

    skill = z >= Z_BAR
    positive = fam > 0
    repl = (h1 > 0) and (h2 > 0)
    plateau = n_pos >= PLATEAU_FRAC * n_alive
    if skill and positive and repl and plateau:
        verdict = "FAMILY_CONFIRMED"
    elif skill and positive and repl:
        verdict = "DEAD_NO_PLATEAU"
    elif skill and positive:
        verdict = "DEAD_NO_REPLICATION"
    elif skill:
        verdict = "DEAD_NEGATIVE_ABSOLUTE"
    else:
        verdict = "DEAD_NO_SKILL"

    print(f"  NULL   family mean R = {nullm:+.4f}   sd = {sd:.4f}  (perms={len(perms)})")
    print(f"  LIFT_R = {lift:+.4f} R/trade   z = {z:+.2f}σ   p = {p_perm:.4f}")
    print(f"  ⭐ e_pip = {e_pip:+.2f} pip   vs c = {cost:.2f}   "
          f"⇒ {'CLEARS' if e_pip > cost else 'BELOW'} cost")

    # انطباق با برآوردِ پیش‌ثبت (بندِ ۲): از S365 همان کارت
    base = _load(f"results/_scan_S365/{asset}_{tf}.json")
    if base and base.get("burden_mean"):
        b_sl = cost / base["burden_mean"]
        pred = -(base["lift"] * b_sl)
        print(f"  ── prereg §2 predicted e_pip ≈ {pred:+.2f} · measured {e_pip:+.2f}"
              f" · gap {e_pip - pred:+.2f}")
    print(f"  >>> {verdict}   (skill={skill}, positive={positive}, "
          f"repl={repl}, plateau={plateau})", flush=True)

    res = dict(asset=asset, tf=tf, bars=n, max_hold=mh,
               n_members_alive=n_alive, n_members_total=n_total_fam,
               n_total_trades=tot, fam_meanR=round(fam, 4),
               null_meanR=round(nullm, 4), sd=round(sd, 4), lift=round(lift, 4),
               z=round(z, 3), p_perm=round(p_perm, 4),
               burden_mean=round(float(np.mean(burdens)), 4),
               mean_sl_pip=round(mean_sl, 2), e_pip=round(e_pip, 3), cost=cost,
               half1_meanR=round(h1, 4), half2_meanR=round(h2, 4),
               member_min=round(min(obsR), 4), member_max=round(max(obsR), 4),
               n_members_positive=n_pos, members=members, verdict=verdict)
    if save:
        _save(res, asset, tf)
    return res


def _load(p):
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
