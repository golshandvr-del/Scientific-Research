# -*- coding: utf-8 -*-
"""
S360 — آزمونِ «فلاتِ پایدار در برابرِ قلهٔ تیز» روی افقِ نگهداریِ `S323`
==========================================================================

## چرا این اسکریپت وجود دارد

`s359` روی کارتِ `XAUUSD-M30` یک سلولِ عبورکننده یافت:

    mh=29 → n=160  WR=73.12%  ref=57.68  z=3.609   (سد=3.509)

ولی همان جدول یک **پرچمِ قرمز** هم نشان داد؛ همسایه‌های آن سلول می‌ریزند:

    mh=24 → z=3.470   ✗
    mh=29 → z=3.609   ✅
    mh=34 → z=3.196   ✗

یعنی یک حرکتِ ۵ کندلی در هر جهت، بینِ ۰.۱۴ تا ۰.۴۱ سیگما هزینه دارد.
`docs/indicators/variants.md` در بخشِ «آزمونِ پایداریِ خانواده» صریح است:

  > «اگر یک لایه فقط روی یک دورهٔ خانواده RQS+>80 می‌دهد و همسایه‌هایش ناگهان
  >  می‌ریزند، آن یک **over-fitِ کلاسیک** است و باید رد شود (حتی اگر RQS+ آن
  >  لحظه بالای ۸۰ باشد). اما اگر یک **بازهٔ پیوسته** از دوره‌ها همگی RQS+>80
  >  می‌دهند، edge **واقعی و مقاوم** است. همیشه به فلاتِ پایدار اعتماد کن،
  >  نه به قلهٔ تیزِ تکی.»

جدولِ `s359` فقط ۸ نقطهٔ پراکنده داشت (11,18,24,29,34,47,48,76) — با این
تفکیکِ درشت **نمی‌توان** فلات را از قله تشخیص داد. این اسکریپت همان محورِ
افق را با گامِ ۱ کندل از ۱۴ تا ۶۰ می‌پیماید تا شکلِ واقعیِ منحنی دیده شود.

## این اسکریپت چه چیزی را اثبات یا رد می‌کند

سه سناریو ممکن است و هرکدام تصمیمِ متفاوتی می‌سازد:

  الف) یک **بازهٔ پیوسته** از افق‌ها (مثلاً ۲۶..۳۳) همگی از سد رد شوند
       ⇒ edge واقعی است؛ می‌رویم سراغِ داوریِ کاملِ ۱۱-دروازه‌ای با
         افقِ مرکزِ بازه (نه بیشینهٔ z — که خودش over-fit است).

  ب) فقط **یک یا دو نقطهٔ پراکنده** رد شوند
       ⇒ over-fitِ کلاسیک؛ طبقِ `variants.md` باید رد شود حتی با z>سد.

  ج) **هیچ نقطه‌ای** رد نشود
       ⇒ عبورِ `s359` صرفاً نوفهٔ برآوردِ میانگینِ جای‌گشت با ۶۰۰ قرعه بود.

## دو تصحیحِ روش‌شناختی نسبت به `s359`

۱. **قرعهٔ بیشتر برای مبنا.** در `s359` میانگینِ جای‌گشت با ۶۰۰ قرعه برآورد
   شد. خطای استانداردِ آن برآورد ≈ sd/√600 است و مستقیماً به `ref` و از آنجا
   به z نشت می‌کند. چون حاشیهٔ عبور فقط ۰.۱ سیگما بود، این نوفه هم‌مرتبهٔ
   خودِ حاشیه است. اینجا ۱۵۰۰ قرعه می‌گیریم (۲.۵ برابر) تا شکلِ منحنی از
   نوفهٔ مبنا تمیز شود، و علاوه بر آن با **سه بذر** تکرار می‌کنیم و
   بدترینِ سه z را گزارش می‌کنیم — یعنی محافظه‌کارانه‌ترین قرائت.

۲. **هزینهٔ آزمون صادقانه شمرده می‌شود.** ۴۷ افق = ۴۷ آزمونِ جدید که روی
   بودجهٔ انباشته (۲۴۰۰ ساخت + ۸۸ اسکنِ فیلتر + ۳۲ سلولِ افق) می‌نشیند.
   سدِ H5 با آن بالا می‌رود و همان سدِ بالاتر ملاکِ داوری است. اگر اسکنِ
   متراکم خودش سد را آن‌قدر بالا ببرد که قله زیرِ آن بیفتد، این **پاسخِ
   درست** است نه شکستِ اسکریپت: هزینهٔ جست‌وجو بخشی از حقیقت است.

## آنچه این اسکریپت ادعا نمی‌کند

- عبور از H5 ≠ پذیرش. ده دروازهٔ دیگر رأیِ خود را دارند و در `s357` روی
  همان کارت با افقِ ۴۸ سنجیده شدند؛ با تغییرِ افق باید **دوباره** سنجیده
  شوند، چون افق روی مدتِ نگهداری، سرمایهٔ درگیر و توزیعِ خروج اثر دارد.
- منحنی روی **یک کارت** است. تعمیم به کارت‌های دیگر بی‌معناست چون
  `s357` نشان داد فقط همین کارت بالای ۳ سیگما است.
"""

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine import scalp_engine as se           # noqa: E402
from engine import indicators as ind            # noqa: E402
from engine import rqs2 as R2                   # noqa: E402
from s357_s323_v24_rejudge import (             # noqa: E402
    cfg_for, signals_backtested, outcome_table, wr_of,
)
from s358_s323_h5_rescue import binom_z, perm_mean_for   # noqa: E402

CARD = 'XAUUSD-M30'
HOLD_LO, HOLD_HI = 14, 60
K_PERM = 1500
SEEDS = (23, 101, 777)

# بودجهٔ آزمونِ انباشته تا پیش از این اسکریپت:
#   ۲۴۰۰ = ساختِ اولیهٔ لایه (بایگانی)  ·  ۸۸ = اسکنِ فیلترِ s358
#   ۳۲   = سلول‌های افق × فیلترِ s359
PRIOR_TRIALS = 2400 + 88 + 32

OUT_DIR = 'results/_s360_s323_plateau'


def main():
    holds = list(range(HOLD_LO, HOLD_HI + 1))
    n_trials = PRIOR_TRIALS + len(holds)
    zbar = R2.expected_max_z(n_trials)

    print(f"S360 — اسکنِ متراکمِ افقِ نگهداری روی {CARD}")
    print(f"محور: mh = {HOLD_LO}..{HOLD_HI} (گامِ ۱، {len(holds)} آزمون)")
    print(f"بودجهٔ آزمون: {PRIOR_TRIALS} + {len(holds)} = {n_trials}")
    print(f"سدِ H5 = expected_max_z({n_trials}) = {zbar:.4f}")
    print(f"قرعه: K={K_PERM} × {len(SEEDS)} بذر (بدترین z گزارش می‌شود)\n",
          flush=True)

    asset, tf = CARD.split('-')
    df = se.load_data(f'data/{asset}_{tf}.csv')
    cfg = cfg_for(CARD)
    sig = signals_backtested(df, asset, cfg)

    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    am = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['slMult'] * am, 1)
    tp = round(cfg['tpMult'] * am, 1)

    print(f"SL={sl}pip TP={tp}pip RR={tp/sl:.3f}  سیگنالِ خام={int(sig.sum())}\n",
          flush=True)
    print(f"{'mh':>3s} {'n':>4s} {'W':>4s} {'WR':>6s} {'uncond':>7s} "
          f"{'permM':>6s} {'ref':>6s} {'zmin':>6s} {'zmax':>6s}  pass")

    rows = []
    for mh in holds:
        res, xbar = outcome_table(df, asset, sl, tp, mh)
        valid = np.arange(260, max(261, len(df) - mh - 2))
        valid = valid[res[valid] != 0]
        uncond = wr_of(valid, res, xbar)

        tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), sl, tp,
                                asset, max_hold=mh, allow_overlap=False)
        n = len(tr)
        w = int((tr['pnl_pip'] > 0).sum())
        wr = 100.0 * w / n if n else 0.0

        zs, pms = [], []
        for sd in SEEDS:
            pm = perm_mean_for(res, xbar, valid, n, K_PERM, sd)
            pms.append(pm)
            zs.append(binom_z(w, n, max(uncond, pm) / 100.0))
        zmin, zmax = min(zs), max(zs)
        ref = max(uncond, float(np.mean(pms)))

        ok = zmin > zbar
        bar = '█' * max(0, int((zmin - 2.9) * 30))
        print(f"{mh:3d} {n:4d} {w:4d} {wr:6.2f} {uncond:7.2f} "
              f"{np.mean(pms):6.2f} {ref:6.2f} {zmin:6.3f} {zmax:6.3f}  "
              f"{'✅' if ok else '  '}{bar}", flush=True)

        rows.append(dict(mh=mh, n=n, wins=w, wr=round(wr, 2),
                         uncond=round(uncond, 2),
                         perm_mean=round(float(np.mean(pms)), 2),
                         ref=round(ref, 2), z_min=round(zmin, 3),
                         z_max=round(zmax, 3), passes=bool(ok)))

    # ---- تحلیلِ شکلِ منحنی: بلندترین بازهٔ پیوستهٔ عبورکننده ----------------
    best_run, cur = [], []
    for r in rows:
        if r['passes']:
            cur.append(r['mh'])
            if len(cur) > len(best_run):
                best_run = list(cur)
        else:
            cur = []

    n_pass = sum(r['passes'] for r in rows)
    print(f"\nعبورکننده: {n_pass}/{len(rows)} نقطه")
    if best_run:
        print(f"بلندترین بازهٔ پیوسته: mh = {best_run[0]}..{best_run[-1]} "
              f"(طول {len(best_run)})")
        centre = best_run[len(best_run) // 2]
        print(f"مرکزِ بازه (نامزدِ داوریِ کامل، نه بیشینهٔ z): mh={centre}")
    else:
        print("هیچ بازهٔ پیوسته‌ای وجود ندارد.")

    verdict = ('PLATEAU' if len(best_run) >= 5 else
               'SPIKE' if best_run else 'NONE')
    print(f"\nحکمِ شکلِ منحنی: {verdict}")
    if verdict == 'PLATEAU':
        print("  ⇒ طبقِ variants.md، edge مقاوم است. برو سراغِ داوریِ کاملِ ۱۱-دروازه‌ای.")
    elif verdict == 'SPIKE':
        print("  ⇒ طبقِ variants.md، over-fitِ کلاسیک. رد می‌شود حتی با z>سد.")
    else:
        print("  ⇒ عبورِ s359 نوفهٔ برآوردِ مبنا با ۶۰۰ قرعه بود.")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'dense_hold.json')
    json.dump(dict(card=CARD, sl_pip=sl, tp_pip=tp, k_perm=K_PERM,
                   seeds=list(SEEDS), n_trials=n_trials, zbar=round(zbar, 4),
                   n_pass=n_pass, longest_run=best_run, verdict=verdict,
                   rows=rows),
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n→ wrote {out}")


if __name__ == '__main__':
    main()
