# -*- coding: utf-8 -*-
"""
S362 — ممیزیِ **بودجهٔ آزمون** و محاسبهٔ سدِ صادقانهٔ `H5` برای `S323`
==========================================================================

## چرا این ممیزی ضروری شد

سدِ `H5` تابعِ تعدادِ پیکربندی‌هایی است که برای یافتنِ نتیجه آزموده‌ایم:

    z_bar = expected_max_z(n_trials)        (قضیهٔ «استراتژیِ کاذب»)

در سه نشستِ گذشته این عدد **۲۴۰۰** فرض شده بود (`s357.N_TRIALS_HONEST`)،
ولی هیچ‌جا مستند نشده بود که ۲۴۰۰ از کجا آمده. چون کلِ داوریِ `S323` روی
حاشیه‌ای در حدِ ۰.۲ سیگما می‌چرخد، یک فرضِ مستندنشده در ورودیِ سد می‌تواند
حکم را وارونه کند. پس شبکهٔ واقعیِ ساختِ لایه شمرده شد.

## شمارشِ واقعی از `strategies/s323_s11_sr_pullback_revival.py`

    near_max  3   room_min 2   rsi_max 3   slope_min 2
    adx_min   2   golden   2   h_lo    1   h_hi    1
    sl_mult   3   tp_mult  3

    ترکیبِ پایه            = 3·2·3·2·2·2·1·1 = 144
    جفت‌های معتبرِ tp<sl    = 9   (هر ۹ جفت معتبرند)
    ⇒ پیکربندی در هر کارت  = 144 × 9 = 1296
    × افق‌های آزموده        = MH.get(tf, [48, 72, 96]) ⇒ ۳
    ⇒ **۳۸۸۸ آزمون در هر کارت**

یعنی فرضِ ۲۴۰۰ حدودِ **۳۸٪ کمتر از واقعیت** بوده — و در جهتِ خوش‌بینانه،
یعنی سدی که تا امروز اعمال می‌شد **آسان‌تر از سدِ درست** بود.

## دو قرائتِ ممکن و چرا محافظه‌کارانه‌ترین انتخاب می‌شود

الف) **قرائتِ درون‌کارتی** — ۳۸۸۸ آزمون برای یافتنِ پیکربندیِ همین کارت.
ب) **قرائتِ سراسری** — اسکن روی چند کارت اجرا شده و بهترین کارت انتخاب
   شده، پس چندگانگی شاملِ کارت‌ها هم می‌شود.

اسپکِ RQS2 در جدولِ نقص‌ها می‌گوید چندگانگی باید کلِ جست‌وجویی را بپوشاند
که به انتخابِ نهایی منجر شده. چون در این نشست از میانِ ۸ کارت، کارتِ M30
**به‌دلیلِ بالاترین z انتخاب شد**، قرائتِ (ب) دقیق‌تر است. ولی برای اینکه
حکم به یک انتخابِ روش‌شناختیِ سخت‌گیرانه وابسته نباشد، **هر دو** گزارش
می‌شوند و اگر لایه حتی زیرِ قرائتِ آسان‌تر هم رد شود، حکم بدونِ ابهام است.

## هزینهٔ جست‌وجوی همین نشست

    ۸۸  اسکنِ فیلترِ s358
    ۳۲  سلول‌های افقِ s359
    ۴۷  اسکنِ متراکمِ افقِ s360
    ۱   آینهٔ s361  (بدونِ پارامترِ آزاد)
    ───
    ۱۶۸ آزمونِ افزوده در این نشست

## این اسکریپت چه چیزی را تصمیم می‌گیرد

بهترین z ای که در کلِ نشست برای `S323` روی کارتِ M30 به دست آمد را در
برابرِ سدِ تصحیح‌شده می‌گذارد. اگر حتی بهترین (و over-fitِ شناخته‌شده)
هم زیرِ سد بیفتد، «قانونِ مرگِ ابدی» با شواهدِ کافی ارضا می‌شود.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import rqs2 as R2       # noqa: E402

OUT = 'results/_s362_s323_budget/audit.json'

# ---- شبکهٔ واقعیِ ساخت (شمرده‌شده از فایلِ ساخت) --------------------------
GRID_BASE = 3 * 2 * 3 * 2 * 2 * 2 * 1 * 1      # 144
TPSL_PAIRS = 9
MH_VALUES = 3
PER_CARD = GRID_BASE * TPSL_PAIRS * MH_VALUES  # 3888
CARDS_SCANNED = 8                              # کارت‌هایی که در این نشست داوری شدند

# ---- هزینهٔ جست‌وجوی این نشست ---------------------------------------------
SESSION = dict(s358_filter=88, s359_hold=32, s360_dense=47, s361_mirror=1)
SESSION_TOTAL = sum(SESSION.values())

# ---- بهترین zهایی که در نشست دیده شد --------------------------------------
OBSERVED = [
    ("پایه (بدونِ بهبود، mh=48)", 3.258,
     "s361 long-only، ref با ۱۵۰۰ قرعه × ۳ بذر"),
    ("بهترین فیلتر (chop≥q، n=63)", 3.423,
     "s358 — n از ۱۶۰ به ۶۳ ریخت"),
    ("بهترین افق (mh=28)", 3.821,
     "s360 — قلهٔ تیز؛ همسایهٔ mh=30 برابرِ 3.115 ⇒ over-fit طبقِ variants.md"),
    ("آینهٔ دوسویه (n=269)", 1.291,
     "s361 — سمتِ شورت لیفتِ منفی دارد"),
]


def main():
    prev_assumed = 2400
    honest_in_card = PER_CARD + SESSION_TOTAL
    honest_global = PER_CARD * CARDS_SCANNED + SESSION_TOTAL

    z_prev = R2.expected_max_z(prev_assumed + SESSION_TOTAL)
    z_in = R2.expected_max_z(honest_in_card)
    z_gl = R2.expected_max_z(honest_global)

    print("S362 — ممیزیِ بودجهٔ آزمون و سدِ صادقانهٔ H5 برای S323\n")
    print("شبکهٔ واقعیِ ساخت (شمرده‌شده از فایلِ ساخت):")
    print(f"  ترکیبِ پایه {GRID_BASE} × جفتِ tp/sl {TPSL_PAIRS} "
          f"× افق {MH_VALUES} = {PER_CARD} در هر کارت")
    print(f"هزینهٔ جست‌وجوی این نشست: {SESSION} ⇒ {SESSION_TOTAL}\n")

    print(f"{'قرائت':38s} {'n_trials':>9s} {'سدِ H5':>8s}")
    print(f"{'فرضِ قبلی (مستندنشده)':38s} {prev_assumed+SESSION_TOTAL:9d} {z_prev:8.4f}")
    print(f"{'الف) درون‌کارتی (شمرده‌شده)':38s} {honest_in_card:9d} {z_in:8.4f}")
    print(f"{'ب) سراسری (۸ کارت داوری‌شده)':38s} {honest_global:9d} {z_gl:8.4f}")

    print("\nبهترین zهای مشاهده‌شده در برابرِ هر سد:")
    print(f"{'مورد':34s} {'z':>6s}  {'فرضِ قبلی':>9s} {'الف':>6s} {'ب':>6s}")
    rows = []
    for name, z, note in OBSERVED:
        f = lambda b: '✅' if z > b else '✗'      # noqa: E731
        print(f"{name:34s} {z:6.3f}  {f(z_prev):>9s} {f(z_in):>6s} {f(z_gl):>6s}")
        rows.append(dict(name=name, z=z, note=note,
                         pass_prev=bool(z > z_prev), pass_in=bool(z > z_in),
                         pass_global=bool(z > z_gl)))

    any_in = any(r['pass_in'] for r in rows)
    any_gl = any(r['pass_global'] for r in rows)
    print(f"\nزیرِ قرائتِ الف: {'دستِ‌کم یک مورد عبور می‌کند' if any_in else 'هیچ موردی عبور نمی‌کند'}")
    print(f"زیرِ قرائتِ ب:  {'دستِ‌کم یک مورد عبور می‌کند' if any_gl else 'هیچ موردی عبور نمی‌کند'}")

    # موردِ عبورکننده‌ای که خودش over-fit شناخته شده، عبورِ معتبر نیست
    valid = [r for r in rows if r['pass_in'] and 'over-fit' not in r['note']]
    print(f"\nعبورِ **معتبر** (بدونِ موردِ over-fitِ شناخته‌شده): "
          f"{len(valid)} مورد")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(per_card_grid=PER_CARD, session_cost=SESSION,
                   session_total=SESSION_TOTAL,
                   n_trials_prev=prev_assumed + SESSION_TOTAL,
                   n_trials_in_card=honest_in_card,
                   n_trials_global=honest_global,
                   zbar_prev=round(z_prev, 4), zbar_in_card=round(z_in, 4),
                   zbar_global=round(z_gl, 4), observed=rows,
                   valid_passes=len(valid)),
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\n→ wrote {OUT}")


if __name__ == '__main__':
    main()
