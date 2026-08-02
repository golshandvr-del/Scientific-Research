# -*- coding: utf-8 -*-
"""
S364 — **قانونِ بارِ هزینه در فضای R** و آزمونِ نجاتِ لایه

════════════════════════════════════════════════════════════════════════════
چرا این فایل وجود دارد
════════════════════════════════════════════════════════════════════════════
کاوشِ فضای R (`s364_rspace_probe.py`) سه چیز را هم‌زمان نشان داد:

    کارت            لبهٔ نسبی (R/trade)      z        سطحِ مطلق (R/trade)
    XAUUSD-M5           +0.045            2.72σ          −0.205
    EURUSD-M1           +0.219            9.37σ          −0.296
    EURUSD-M15          +0.104            7.56σ          −0.246

یعنی «ورودها مهارت دارند، ولی خطِ مبنا آن‌قدر پایین است که مهارت جبرانش نمی‌کند».
پرسشِ بعدی این است: **این خطِ مبنای منفی از کجا می‌آید؟**

── اتحادِ نظری ──────────────────────────────────────────────────────────────
یک معاملهٔ بی‌مهارت (ورود در بارِ تصادفی) را با بریکتِ (SL, TP) در نظر بگیرید.
اگر قیمت بدونِ رانش حرکت کند، احتمالِ رسیدن به TP پیش از SL طبقِ مسئلهٔ کلاسیکِ
«ویرانیِ قمارباز» برابر است با SL/(SL+TP). پس امیدِ سود بر حسبِ pip:

    E[pip] = (TP)·SL/(SL+TP) − (SL)·TP/(SL+TP) − c  =  −c

که در آن `c` = هزینهٔ رفت‌وبرگشت (اسپرد + لغزش). یعنی امیدِ pip **دقیقاً منهای
هزینه** است، مستقل از شکلِ بریکت. حالا همان را در فضای R (تقسیم بر SL) بنویسیم:

    ┌───────────────────────────────────────────────────────────┐
    │   E[R]_null  =  − c / SL      ⇐  «بارِ هزینه» (cost burden) │
    └───────────────────────────────────────────────────────────┘

⭐ نتیجهٔ تکان‌دهنده: در فضای R، خطِ مبنا **به شکلِ بریکت کاری ندارد** و فقط به
یک چیز وابسته است: اینکه SL چند برابرِ اسپرد است. هر معامله‌ای با SL کوچک، پیش
از آنکه هیچ مهارتی وارد شود، `c/SL` واحدِ ریسک بدهکار است.

اندازه‌گیریِ اولیه روی XAUUSD-M5 این را با دقتِ چشمگیری تأیید کرد:
    پیش‌بینیِ نظری  −0.2494   ·   اندازه‌گیریِ واقعیِ نالِ جای‌گشتی  −0.2504
    خطای نسبی: %۰.۴

── چرا این «فیلترِ برازش‌شده» نیست ─────────────────────────────────────────
اتحاد می‌گوید بخشی از R که مالِ بازار نیست و صرفاً مالیاتِ اسپرد است، **از قبل
و بدونِ نگاه‌کردن به سود** قابلِ محاسبه است: `b = c/SL`. حذفِ معاملاتی که بارِ
هزینهٔ کمرشکن دارند، انتخاب بر اساسِ نتیجه نیست، انتخاب بر اساسِ **هندسهٔ
شناخته‌شدهٔ هزینه در لحظهٔ ورود** است. این همان «قانونِ بارِ هزینه»ی خودِ پروژه
(`docs/FINDING_COST_BURDEN_GEOMETRY_LAW.md`) است، اما تعمیم‌یافته از سطحِ
«کارت» به سطحِ «هر معامله» — که برای بریکتِ شناور تنها تعمیمِ درست است.

── شرطِ نجات (قابلِ محاسبه پیش از اجرا) ────────────────────────────────────
اگر لبهٔ مهارت در فضای R تقریباً ثابت و برابرِ `e` باشد، آنگاه:

    E[R] = e − b   >   0   ⟺   b < e   ⟺   SL > c/e

    XAUUSD-M5   e=0.045 → SL > 22.2c = 73 pip
    EURUSD-M1   e=0.219 → SL >  4.6c =  7.4 pip
    EURUSD-M15  e=0.104 → SL >  9.6c = 15.4 pip

پس **پیش‌بینیِ سختِ این فایل**: با سقف‌گذاری روی بارِ هزینه، کارت‌های یورو باید
به ناحیهٔ مثبت بروند و طلای M5 باید (به‌خاطرِ لبهٔ کوچکش) در بهترین حالت مرزی
بماند. اگر عکسِ این رخ دهد، فرضِ «ثابت‌بودنِ e» غلط است و باید ثبت شود.

════════════════════════════════════════════════════════════════════════════
این فایل چه می‌کند (و چه نمی‌کند)
════════════════════════════════════════════════════════════════════════════
۱. اتحادِ `E[R]_null = −mean(c/SL)` را روی هر سه کارت **می‌سنجد** (نه فرض می‌کند).
۲. R هر معاملهٔ خانواده را در باندهای بارِ هزینه تفکیک می‌کند.
۳. منحنیِ «میانگینِ R خانواده به‌ازای سقفِ b» را رسم می‌کند (عددی).

⚠️ این فایل **تصمیمِ پذیرش نمی‌گیرد** و هیچ آستانه‌ای را «انتخاب» نمی‌کند.
خروجی‌اش صرفاً نقشهٔ تشخیصی است. انتخابِ آستانه، اگر انجام شود، در یک
پیش‌ثبتِ جداگانه و با نیمهٔ اولِ داده انجام خواهد شد.
"""

import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                    # noqa: E402
from strategies.s364_stairs_family import (                              # noqa: E402
    stairs_context, member_signals,
    FAM_K, FAM_F, FAM_G, FAM_S, FAM_MODE,
    TF_MAX_HOLD, MIN_TRADES, OUT,
)

CARDS = [("XAUUSD", "M5"), ("EURUSD", "M1"), ("EURUSD", "M15")]
BANDS = [0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.40, 1.00]


def pooled_trades(asset, tf):
    """R و بارِ هزینهٔ هر معاملهٔ **همهٔ اعضای زندهٔ خانواده** (بدونِ انتخاب)."""
    df = se.load_data(f"data/{asset}_{tf}.csv")
    n = len(df)
    mh = TF_MAX_HOLD[tf]
    warm = min(260, max(30, n // 8))
    cfg = se.ASSETS[asset]
    c = float(cfg["spread_pip"]) + 2.0 * float(cfg.get("slip_pip", 0.0))

    ctxs = {k: stairs_context(df, k) for k in FAM_K}
    R, B, MID, SIGN = [], [], [], []
    n_alive = 0
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
                        if int(ls.sum() + ss.sum()) < MIN_TRADES:
                            continue
                        tr = se.simulate_trades(df, ls, ss, slv, tpv, asset,
                                                max_hold=mh, allow_overlap=False)
                        if tr is None or len(tr) < MIN_TRADES:
                            continue
                        n_alive += 1
                        eb = tr["entry_bar"].values.astype(int)
                        sl_u = slv[eb - 1]
                        ok = sl_u > 0
                        R.extend((tr["pnl_pip"].values[ok] / sl_u[ok]).tolist())
                        B.extend((c / sl_u[ok]).tolist())
                        MID.extend([f"k{k}f{f}g{g}s{s}{mode}"] * int(ok.sum()))
                        SIGN.extend(np.where(tr["side"].values[ok] == "long", 1, -1).tolist())
    return (np.asarray(R), np.asarray(B), np.asarray(MID), np.asarray(SIGN),
            n_alive, c)


def run_card(asset, tf):
    print(f"\n=== S364 BURDEN-LAW :: {asset}-{tf} ===")
    R, B, MID, SIGN, alive, c = pooled_trades(asset, tf)
    if R.size == 0:
        print("   no trades")
        return None

    pred = -float(B.mean())
    print(f"   alive members={alive}  pooled trades={R.size:,}  cost c={c} pip")
    print(f"   ⭐ identity check:  E[R]_null predicted = {pred:+.4f}")
    print(f"      (compare with the permutation null already measured in RPROBE)")
    print(f"   observed family mean R = {R.mean():+.4f}")
    print(f"   burden b=c/SL:  med={np.median(B):.4f}  mean={B.mean():.4f}  "
          f"max={B.max():.4f}")

    print(f"\n   {'band b<':>10}{'n':>8}{'share':>8}{'meanR':>10}{'predNull':>10}"
          f"{'lift':>9}{'WR%':>8}")
    curve = []
    for hi in BANDS:
        m = B < hi
        if m.sum() < 30:
            continue
        mr = float(R[m].mean())
        pn = -float(B[m].mean())
        curve.append(dict(cap=hi, n=int(m.sum()), meanR=round(mr, 4),
                          predNull=round(pn, 4), lift=round(mr - pn, 4),
                          wr=round(100.0 * float((R[m] > 0).mean()), 2)))
        print(f"   {hi:>10.2f}{m.sum():>8,}{m.mean():>8.3f}{mr:>10.4f}{pn:>10.4f}"
              f"{mr - pn:>+9.4f}{100.0 * (R[m] > 0).mean():>8.2f}")

    # باندهای مجزا (نه تجمعی) — برای دیدنِ اینکه لبه در کجا زندگی می‌کند
    print(f"\n   disjoint bands:")
    edges = [0.0] + BANDS
    disj = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (B >= lo) & (B < hi)
        if m.sum() < 30:
            continue
        mr = float(R[m].mean())
        pn = -float(B[m].mean())
        disj.append(dict(lo=lo, hi=hi, n=int(m.sum()), meanR=round(mr, 4),
                         predNull=round(pn, 4), lift=round(mr - pn, 4)))
        print(f"   [{lo:.2f},{hi:.2f}) n={m.sum():>7,}  meanR={mr:+.4f}  "
              f"predNull={pn:+.4f}  lift={mr - pn:+.4f}")

    res = dict(asset=asset, tf=tf, cost_pip=c, alive=alive, n_pooled=int(R.size),
               pred_null=round(pred, 4), obs_meanR=round(float(R.mean()), 4),
               burden_med=round(float(np.median(B)), 4),
               cumulative=curve, disjoint=disj)
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/BURDEN_{asset}_{tf}.json"
    json.dump(res, open(p, "w"), ensure_ascii=False, indent=1)
    print(f"     saved -> {p}")
    return res


def main():
    for a, t in CARDS:
        try:
            run_card(a, t)
        except Exception as e:                                            # noqa: BLE001
            print(f"   !! {a}-{t} failed: {e}")


if __name__ == "__main__":
    main()
