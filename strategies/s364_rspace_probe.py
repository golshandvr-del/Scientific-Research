# -*- coding: utf-8 -*-
"""
S364 — کاوشِ تعیین‌کننده: آیا لبهٔ ورود در **فضای R** وجود دارد؟
================================================================

## چرا این آزمون لازم شد

مرحلهٔ ۱ (آزمونِ خانواده) گفت: **بله، لبهٔ WR واقعی است.**
    XAUUSD-M5  +2.61pp  z=+6.23σ
    EURUSD-M1  +4.58pp  z=+4.60σ
    EURUSD-M15 +1.40pp  z=+3.17σ

مرحلهٔ ۲ (داوریِ کامل) گفت: **ولی هیچ پولی درنمی‌آورد.** هر سه کارت REJECT،
با PF دلاری ۰.۸۷۹ / ۰.۸۷۲ / ۰.۸۰۰.

و تشخیصِ پس از آن، شکافِ دقیق را پیدا کرد — شکافی که **فقط** برای یک لایهٔ
بریکت-شناور ممکن است و هیچ لایهٔ قبلیِ پروژه نمی‌توانست به آن بخورد:

    سودِ pip   = +2794 pip   (XAUUSD-M5)   ⇒ ظاهراً سودده
    سودِ دلاری = −1233 $                    ⇒ در واقع زیان‌ده

چون `engine/capital_engine.py` **ریسکِ درصدیِ ثابت** دارد:
`lots = risk_$ / (SL × contract_size)`. یعنی معاملهٔ با SLِ کوچک لاتِ بزرگ
می‌گیرد و برعکس. با بریکتِ ثابت این فقط یک ضریبِ مقیاس است و علامت را عوض
نمی‌کند؛ با بریکتِ **شناور** وزنِ هر معامله تغییر می‌کند و علامت می‌تواند
**برگردد**. و اینجا دقیقاً برگشت:

    corr(pnl_pip, SL) = +0.779     ⇐ سودِ pip تقریباً هم‌ارزِ «بزرگیِ بریکت» است
    SL از 3.4 تا 1694.7 pip        ⇐ دامنهٔ ۵۰۰ برابری، عملاً بی‌کران
    چارکِ بالا (SL≈187): +2736 pip از کلِ +2794    ⇒ اما فقط +8.81R
    چارکِ پایین (SL≈6.4):  −29.5 pip                ⇒ اما −18.11R

پس واحدِ سنجش باید **R** باشد، نه pip. این فایل همان آزمونِ خانوادهٔ
پیش‌ثبت‌شده را با آمارهٔ **میانگینِ R** تکرار می‌کند.


## وضعیتِ روش‌شناختیِ این فایل — صادقانه

این یک آزمونِ **تأییدی** نیست، یک **تشخیصِ اکتشافی** است. خانواده، مدلِ صفر و
همهٔ پارامترها **دقیقاً** همان‌های پیش‌ثبت‌شده‌اند و هیچ محورِ تازه‌ای اضافه
نشده؛ تنها چیزی که عوض شده «آمارهٔ خروجی» است (R به‌جای WR). چون آمارهٔ
جدید **پس از دیدنِ داده** انتخاب شد، عددِ z اینجا **ارزشِ تأییدی ندارد** و
به‌عنوان مدرکِ پذیرش استفاده نمی‌شود.

کاری که این آزمون *می‌تواند* بکند دقیقاً یک چیز است — و آن هم کافی است:

  · اگر لبهٔ R **منفی یا صفر** باشد ⇒ جست‌وجو برای «بریکتِ نجات‌دهنده» بی‌معناست،
    چون چیزی برای پول‌کردن وجود ندارد. این یک **حکمِ مرگ** است و حکمِ مرگ
    نیازی به پیش‌ثبت ندارد (پیش‌ثبت برای جلوگیری از پذیرشِ کاذب است، نه ردِ کاذب).
  · اگر لبهٔ R **مثبت** باشد ⇒ آن‌گاه — و فقط آن‌گاه — یک پیش‌ثبتِ **تازه** برای
    خانوادهٔ بریکت نوشته می‌شود و از نو آزموده می‌شود.

یعنی این فایل فقط می‌تواند «ادامه بده» یا «تمام» بگوید؛ نمی‌تواند «قبول» بگوید.
"""

import os
import sys
import json
import argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se            # noqa: E402
from strategies.s364_stairs_family import (      # noqa: E402
    FAM_K, FAM_F, FAM_G, FAM_S, FAM_MODE, TF_MAX_HOLD, MIN_TRADES,
    stairs_context, member_signals, _sim_vec,
)

OUT = "results/_scan_S364"
CARDS = [("XAUUSD", "M5"), ("EURUSD", "M1"), ("EURUSD", "M15")]
N_PERM = 300


def _queue_R(picks, win, exit_bar, sl_v, tp_v, cost):
    """صفِ بی‌همپوشانی ⇒ فهرستِ R-multipleها.

    R = سود/زیانِ معامله بر حسبِ «واحدِ ریسک» = دقیقاً چیزی که ریسکِ درصدیِ
    ثابت می‌پردازد. برد ⇒ (TP−c)/SL ، باخت ⇒ −(SL+c)/SL.
    """
    order = np.argsort(picks, kind="stable")
    last_exit = -1
    out = []
    for i in order:
        p = picks[i]
        if p <= last_exit:
            continue
        sl = sl_v[i]
        if sl <= 0:
            continue
        out.append(((tp_v[i] - cost) / sl) if win[i] else (-(sl + cost) / sl))
        last_exit = exit_bar[i]
    return out


def run_card(asset, tf, seed=364, n_perm=N_PERM):
    df = se.load_data(f"data/{asset}_{tf}.csv")
    n = len(df)
    o = df["open"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    c = df["close"].values.astype(float)
    pip = se.ASSETS[asset]["pip"]
    cfg = se.ASSETS[asset]
    cost = cfg["spread_pip"] + 2.0 * cfg.get("slip_pip", 0.0)
    mh = TF_MAX_HOLD.get(tf, 40)
    warm = min(260, max(30, n // 8))
    rng = np.random.default_rng(seed)
    pool = np.arange(warm, n - mh - 2)

    print(f"\n=== S364 R-SPACE PROBE :: {asset}-{tf} (bars={n:,}) ===", flush=True)
    ctxs = {k: stairs_context(df, k) for k in FAM_K}

    obs_R, alive = [], 0
    per_member = []
    perm_pool_R = [[] for _ in range(n_perm)]

    for k in FAM_K:
        for f in FAM_F:
            for g in FAM_G:
                for s in FAM_S:
                    for mode in FAM_MODE:
                        ls, ss, slv, tpv = member_signals(df, ctxs[k], f, g, s,
                                                          mode, asset)
                        ls[:warm] = False; ss[:warm] = False
                        ls[n - mh - 2:] = False; ss[n - mh - 2:] = False
                        idx = np.where(ls | ss)[0]
                        if idx.size < MIN_TRADES:
                            continue
                        flags = ls[idx]
                        r = _sim_vec(o, h, l, c, idx, flags, slv[idx], tpv[idx],
                                     pip, mh, cost, n)
                        if r is None:
                            continue
                        p2, win, xb = r
                        keep = np.isin(idx, p2)
                        Rs = _queue_R(p2, win, xb, slv[idx][keep], tpv[idx][keep], cost)
                        if len(Rs) < MIN_TRADES:
                            continue
                        alive += 1
                        obs_R.extend(Rs)
                        per_member.append(dict(k=k, f=f, g=g, s=s, mode=mode,
                                               n=len(Rs),
                                               meanR=round(float(np.mean(Rs)), 4),
                                               sumR=round(float(np.sum(Rs)), 2)))
                        # ---- مدلِ صفر: همان بریکت‌ها، بارهای تصادفی ----
                        ns = int(idx.size)
                        brk = np.column_stack([slv[idx], tpv[idx]])
                        for pi in range(n_perm):
                            pk = rng.choice(pool, size=ns, replace=False)
                            pk.sort()
                            pm = rng.permutation(ns)
                            sv, tv = brk[pm, 0], brk[pm, 1]
                            fl = rng.permutation(flags)
                            rr = _sim_vec(o, h, l, c, pk, fl, sv, tv, pip, mh,
                                          cost, n)
                            if rr is None:
                                continue
                            q2, w2, x2 = rr
                            kp = np.isin(pk, q2)
                            perm_pool_R[pi].extend(
                                _queue_R(q2, w2, x2, sv[kp], tv[kp], cost))
        print(f"    ctx k={k} done, alive so far = {alive}", flush=True)

    if not obs_R:
        print("   no member alive")
        return None

    obs = float(np.mean(obs_R))
    perm_means = np.array([np.mean(x) for x in perm_pool_R if len(x) > 50])
    nullm = float(perm_means.mean())
    sd = float(perm_means.std(ddof=1))
    z = (obs - nullm) / sd if sd > 0 else float("nan")
    p = float(np.mean(perm_means >= obs))

    print(f"  OBSERVED family mean R = {obs:+.4f}   (pooled trades = {len(obs_R):,}, "
          f"alive={alive}/72)", flush=True)
    print(f"  member meanR range = [{min(m['meanR'] for m in per_member):+.4f}, "
          f"{max(m['meanR'] for m in per_member):+.4f}]", flush=True)
    print(f"  NULL   family mean R = {nullm:+.4f}   sd = {sd:.4f}  (perms={perm_means.size})",
          flush=True)
    print(f"  LIFT_R = {obs - nullm:+.4f} R/trade   z = {z:+.2f}σ   p = {p:.4f}", flush=True)
    print(f"  >>> absolute sign: {'POSITIVE' if obs > 0 else 'NEGATIVE'} "
          f"| relative edge: {'YES' if z > 3.09 else 'no'}", flush=True)

    res = dict(asset=asset, tf=tf, bars=n, alive=alive, n_pooled=len(obs_R),
               obs_meanR=round(obs, 5), null_meanR=round(nullm, 5),
               sd=round(sd, 5), z=round(z, 3), p=round(p, 5),
               lift_R=round(obs - nullm, 5),
               member_meanR_min=min(m['meanR'] for m in per_member),
               member_meanR_max=max(m['meanR'] for m in per_member),
               n_members_positive=sum(1 for m in per_member if m['meanR'] > 0),
               members=per_member)
    os.makedirs(OUT, exist_ok=True)
    with open(f"{OUT}/RPROBE_{asset}_{tf}.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print(f"    saved -> {OUT}/RPROBE_{asset}_{tf}.json", flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset")
    ap.add_argument("--tf")
    ap.add_argument("--perm", type=int, default=N_PERM)
    a = ap.parse_args()
    cards = [(a.asset, a.tf)] if a.asset and a.tf else CARDS
    for x, y in cards:
        try:
            run_card(x, y, n_perm=a.perm)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            print(f"  !! {x}-{y}: {e}")


if __name__ == "__main__":
    main()
