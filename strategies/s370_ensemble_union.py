# -*- coding: utf-8 -*-
"""
S370 — «اتحادِ خانوادهٔ S369» (Ensemble-Union Deployment)
پیش‌ثبت: `results/S370_PREREG_ensemble_union.md`  (پیش از این فایل commit شد)
روش‌شناسی: `docs/METHOD_ENSEMBLE_UNION_DEPLOYMENT.md`

─────────────────────────────────────────────────────────────────────────────
ایدهٔ کل فایل در یک جمله
─────────────────────────────────────────────────────────────────────────────
`S369` یک خانوادهٔ ۲۴ عضوی بود و من برای داوری **یک** عضو را برداشتم
(۱۱۰ معامله ⇒ رد به‌خاطرِ توان). این‌جا **هیچ عضوی انتخاب نمی‌شود**: هر باری
که دستِ‌کم یک عضو سیگنال بدهد، *یک* معامله با بریکتِ **میانگینِ اعضای موافق**
باز می‌شود. نتیجه روی `XAUUSD-H1`: **۳۱۳** معاملهٔ مستقل به‌جای ۱۱۰ —
بدونِ یک واحد هزینهٔ چندگانگیِ اضافه، چون انتخابی رخ نداده.

⚠️ چرا ۲٬۴۴۵ معاملهٔ اسکنِ خانوادگی را مستقیم به موتور نمی‌دهیم؟
چون اعضا روی بارهای مشترک شلیک می‌کنند ⇒ آن معاملات شدیداً **همبسته**‌اند و
`n` مؤثرشان بسیار کمتر است. دادنشان به موتور `z` را **مصنوعاً متورم** می‌کند.
اتحاد در سطحِ **بار** این تورم را حذف می‌کند.

─────────────────────────────────────────────────────────────────────────────
بندهای قفلِ پیش‌ثبت (در کد هم صریح‌اند تا سهواً نقض نشوند)
─────────────────────────────────────────────────────────────────────────────
  VOTE_THRESHOLD = 1     ← اتحادِ کامل. تنها مقداری که «هیچ انتخابی» است.
  تجمیعِ بریکت  = میانگینِ حسابی. نه میانه، نه وزن‌دار، نه بیشینه.
  هیچ فیلترِ جدیدی افزوده نمی‌شود.

─────────────────────────────────────────────────────────────────────────────
نکتهٔ فنیِ مدلِ صفر
─────────────────────────────────────────────────────────────────────────────
`_perm_meanR`ِ موجود یک `rr` **اسکالر** می‌گیرد، چون آن‌جا هر عضو نسبتِ
`g/s` ثابتِ خودش را داشت. در اتحاد، `TP/SL` هر معامله از میانگین‌گیری می‌آید
پس `rr` **به‌ازای هر معامله** فرق می‌کند. بنابراین نسخهٔ برداریِ `_perm_meanR`
این‌جا نوشته شده — منطقِ خط‌به‌خط عیناً همان است، فقط `rr` آرایه شد.
"""

import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s364_stairs_family import (                              # noqa: E402
    stairs_context, TF_MAX_HOLD,
)
from strategies.s365_stairs_swing_bracket import (                       # noqa: E402
    FAM_K, FAM_F, FAM_G, FAM_S, ALL_CARDS,
)
from strategies.s369_stair_continuation import continuation_signals      # noqa: E402

OUT = "results/_scan_S370"
N_PERM = 500

# ── بندهای قفل‌شدهٔ پیش‌ثبت ────────────────────────────────────────────────
VOTE_THRESHOLD = 1          # 🔒 هرگز تغییر نمی‌کند (بندِ قفلِ ۱)
MIN_TRADES = 60             # کفِ حداقلیِ پروژه برای اینکه کارت اصلاً گزارش شود

# کرانِ شانس با شمارشِ آزمونِ فصل: ۶۱ (S364…S369) + ۱۵ (این آزمون) = ۷۶
N_TRIALS_CHAPTER = 76
Z_LUCK = 2.432              # expected_max_z(76) — در پیش‌ثبت نوشته شد


def build_union(df, asset, tf):
    """اتحادِ ۲۴ عضو در سطحِ بار → آرایه‌های سیگنالِ واحد + بریکتِ میانگین."""
    n = len(df)
    mh = TF_MAX_HOLD[tf]
    warm = min(260, max(30, n // 8))
    ctxs = {k: stairs_context(df, k) for k in FAM_K}

    votes_L = np.zeros(n, dtype=int)
    votes_S = np.zeros(n, dtype=int)
    sum_sl = np.zeros(n, dtype=float)
    sum_tp = np.zeros(n, dtype=float)
    n_members = 0

    for k in FAM_K:
        for f in FAM_F:
            for g in FAM_G:
                for s in FAM_S:
                    ls, ss, slv, tpv = continuation_signals(df, ctxs[k], f, g, s, asset)
                    ls[:warm] = False
                    ss[:warm] = False
                    ls[n - mh - 2:] = False
                    ss[n - mh - 2:] = False
                    sig = ls | ss
                    # فقط بارهایی که بریکتِ معتبر دارند رأی می‌دهند
                    ok = sig & np.isfinite(slv) & np.isfinite(tpv) & (slv > 0)
                    votes_L += (ls & ok).astype(int)
                    votes_S += (ss & ok).astype(int)
                    sum_sl += np.where(ok, np.nan_to_num(slv), 0.0)
                    sum_tp += np.where(ok, np.nan_to_num(tpv), 0.0)
                    n_members += 1

    votes = votes_L + votes_S
    active = votes >= VOTE_THRESHOLD

    # تعارضِ جهت (اندازه‌گیری‌شده = صفر روی هر ۱۵ کارت، ولی چک می‌ماند)
    conflict = int((active & (votes_L > 0) & (votes_S > 0)).sum())

    long_sig = active & (votes_L > 0)
    short_sig = active & (votes_L == 0) & (votes_S > 0)

    with np.errstate(invalid="ignore", divide="ignore"):
        slv = np.where(active, sum_sl / np.maximum(votes, 1), np.nan)
        tpv = np.where(active, sum_tp / np.maximum(votes, 1), np.nan)

    meta = dict(n_members=n_members, n_union=int(active.sum()),
                sum_signals=int(votes.sum()),
                mean_vote=round(float(votes[active].mean()), 2) if active.any() else 0.0,
                conflict=conflict, max_hold=mh, warm=warm)
    return long_sig, short_sig, slv, tpv, meta


def _perm_meanR_vec(o, h, l, picks, isL, sl_v, rr_v, pip, mh, cost):
    """نسخهٔ برداریِ `_perm_meanR`ِ S365 — تنها تفاوت: `rr` per-trade است."""
    m = len(picks)
    if m == 0:
        return None
    ent = o[picks + 1]
    sl_pr = sl_v * pip
    out = np.zeros(m)
    N = len(o)
    for i in range(m):
        st = picks[i] + 1
        en = min(st + mh, N - 1)
        if en <= st:
            continue
        e = ent[i]
        d = sl_pr[i]
        if d <= 0:
            continue
        t = d * rr_v[i]
        hs = h[st:en]
        lsg = l[st:en]
        if isL[i]:
            up = hs >= e + t
            dn = lsg <= e - d
        else:
            up = lsg <= e - t
            dn = hs >= e + d
        hit_tp = int(np.argmax(up)) if up.any() else -1
        hit_sl = int(np.argmax(dn)) if dn.any() else -1
        if hit_tp < 0 and hit_sl < 0:
            px = o[en]
            raw = (px - e) if isL[i] else (e - px)
            out[i] = (raw / pip - cost) / (d / pip)
        elif hit_sl < 0 or (0 <= hit_tp <= hit_sl):
            out[i] = (t / pip - cost) / (d / pip)
        else:
            out[i] = (-d / pip - cost) / (d / pip)
    return float(out.mean())


def run_card(asset, tf, n_perm=N_PERM, seed=370, save=True):
    path = f"data/{asset}_{tf}.csv"
    if not os.path.exists(path):
        return None
    df = se.load_data(path)
    n = len(df)
    cfg = se.ASSETS[asset]
    pip = float(cfg["pip"])
    cost = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))

    print(f"\n=== S370 UNION :: {asset}-{tf} (bars={n:,}) ===", flush=True)
    ls, ss, slv, tpv, meta = build_union(df, asset, tf)
    mh = meta["max_hold"]
    print(f"   union bars={meta['n_union']:,}  mean_vote={meta['mean_vote']}"
          f"/{meta['n_members']}  conflict={meta['conflict']}", flush=True)

    if meta["conflict"] > 0:
        print("   ⚠️ تعارضِ جهت مشاهده شد — پیش‌ثبت این حالت را پیش‌بینی نکرده بود.")

    tr = se.simulate_trades(df, ls, ss, slv, tpv, asset, max_hold=mh,
                            allow_overlap=False)
    if tr is None or len(tr) < MIN_TRADES:
        res = dict(asset=asset, tf=tf, bars=n, verdict="TOO_FEW_TRADES",
                   n_trades=0 if tr is None else int(len(tr)), **meta)
        if save:
            _save(res, asset, tf)
        print(f"   >>> TOO_FEW_TRADES (n={0 if tr is None else len(tr)})")
        return res

    sl_pip = tr["sl_pip"].values.astype(float)
    ok = sl_pip > 0
    tr = tr[ok]
    sl_pip = sl_pip[ok]
    tp_pip = tr["tp_pip"].values.astype(float)
    R = tr["pnl_pip"].values.astype(float) / sl_pip
    obs = float(R.mean())
    burden = float(np.mean(cost / sl_pip))
    nT = len(R)

    # ── مدلِ صفرِ جای‌گشتی: بارهای تصادفی، مجموعهٔ بریکت‌ها دست‌نخورده ──
    rng = np.random.default_rng(seed)
    warm = meta["warm"]
    lo, hi = warm + 2, n - mh - 3
    o_ = df["open"].values.astype(float)
    h_ = df["high"].values.astype(float)
    l_ = df["low"].values.astype(float)
    isL = (tr["side"].values == "long") if "side" in tr.columns else \
          (tr["dir"].values > 0)
    rr = tp_pip / np.maximum(sl_pip, 1e-9)

    perm = []
    for _ in range(n_perm):
        picks = rng.integers(lo, hi, size=nT)
        p = rng.permutation(nT)
        v = _perm_meanR_vec(o_, h_, l_, picks, isL, sl_pip[p], rr[p], pip, mh, cost)
        if v is not None:
            perm.append(v)
    perm = np.asarray(perm, dtype=float)
    null_mean = float(perm.mean())
    sd = float(perm.std(ddof=1)) or 1e-9
    lift = obs - null_mean
    z = lift / sd
    pval = float((perm >= obs).sum() + 1) / (len(perm) + 1)

    e_pip = lift * float(np.mean(sl_pip))          # قانونِ لبهٔ پیپی
    wr = 100.0 * float((tr["pnl_pip"].values > 0).mean())
    net_pip = float(tr["pnl_pip"].values.sum())
    share_tp_lt_sl = float(np.mean(tp_pip < sl_pip))

    half = nT // 2
    h1 = float(R[:half].mean())
    h2 = float(R[half:].mean())

    print(f"   OBS meanR={obs:+.4f}  n={nT:,}  burden b={burden:.4f}")
    print(f"   NULL meanR={null_mean:+.4f}  sd={sd:.4f}  (perms={len(perm)})")
    print(f"   LIFT={lift:+.4f} R/trade   z={z:+.3f}σ   p={pval:.4f}")
    print(f"   ⭐ e_pip={e_pip:+.2f} vs c={cost}  ⇒ "
          f"{'ABOVE' if e_pip > cost else 'BELOW'} cost")
    print(f"   halves: {h1:+.4f} / {h2:+.4f}   WR={wr:.2f}%  "
          f"share(TP<SL)={share_tp_lt_sl:.3f}")

    passes_luck = z > Z_LUCK
    positive = obs > 0
    both_halves = (h1 > 0) and (h2 > 0)
    verdict = ("UNION_CONFIRMED" if (passes_luck and positive and both_halves)
               else "DEAD_NO_SKILL" if not passes_luck
               else "DEAD_UNSTABLE")
    print(f"   >>> {verdict}  (luck={passes_luck} [z={z:.3f} vs {Z_LUCK}], "
          f"positive={positive}, halves={both_halves})", flush=True)

    res = dict(asset=asset, tf=tf, bars=n, n_trades=nT,
               obs_meanR=round(obs, 4), null_meanR=round(null_mean, 4),
               sd=round(sd, 4), lift=round(lift, 4), z=round(z, 3),
               p_perm=round(pval, 5), e_pip=round(e_pip, 2), cost=cost,
               burden=round(burden, 4), wr=round(wr, 2),
               net_pip=round(net_pip, 1),
               share_tp_lt_sl=round(share_tp_lt_sl, 4),
               mean_sl=round(float(np.mean(sl_pip)), 2),
               mean_tp=round(float(np.mean(tp_pip)), 2),
               half1_meanR=round(h1, 4), half2_meanR=round(h2, 4),
               z_luck=Z_LUCK, n_trials=N_TRIALS_CHAPTER,
               n_perm=len(perm), verdict=verdict, **meta)
    if save:
        _save(res, asset, tf)
    return res


def _save(res, asset, tf):
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/{asset}_{tf}.json"
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1)
    print(f"    saved -> {p}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset", default="XAUUSD")
    ap.add_argument("--tf", default="H1")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--perm", type=int, default=N_PERM)
    a = ap.parse_args()
    cards = ALL_CARDS if a.all else [(a.asset, a.tf)]
    for asset, tf in cards:
        try:
            run_card(asset, tf, n_perm=a.perm)
        except Exception as exc:                      # noqa: BLE001
            print(f"   !! {asset}-{tf} failed: {exc}", flush=True)


if __name__ == "__main__":
    main()
