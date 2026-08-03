# -*- coding: utf-8 -*-
"""
ابزارِ تریاژِ توان (Power Triage) — «چند معامله کم داشتیم؟»

این ابزار از یک اعتراضِ درستِ کاربر زاده شد: «۱.۵۸ میلیون کندل داری، چرا مدام
می‌گویی کمبودِ نمونهٔ آماری؟»

پاسخِ عددی: چون `z ∝ √n`، فاصله تا کرانِ شانس یک **محاسبهٔ بسته** است:

        n_needed = n_obs · (z_luck / z_obs)²

⇒ برای هر لایهٔ سوخته می‌توان **دقیقاً** گفت چند معامله کم داشت. این عدد سه دستهٔ
کاملاً متفاوت را از هم جدا می‌کند که تا امروز همه با یک برچسبِ مبهمِ «کمبودِ نمونه»
گزارش می‌شدند:

  🟢 RESCUABLE   : z مثبت، n_needed در دسترس (< ×۵ فعلی) ⇒ ارزشِ تلاشِ دوباره دارد
  🟡 HARD        : z مثبت، ولی n_needed ≥ ×۵ فعلی      ⇒ گران ولی نه ناممکن
  🔴 NEGATIVE    : z منفی                               ⇒ هیچ نمونه‌ای نجاتش نمی‌دهد

نکتهٔ حیاتی: دستهٔ 🔴 با **هیچ مقدار داده‌ای** نجات نمی‌یابد. نمونهٔ بیشتر فقط
منفی‌بودن را با اطمینانِ بیشتری اثبات می‌کند. جدا کردنِ این دسته از 🟢 مهم‌ترین
کارِ این ابزار است.

روشِ افزایشِ نمونه (بدونِ هزینهٔ چندگانگی) در
`docs/METHOD_ENSEMBLE_UNION_DEPLOYMENT.md` مستند است.

اجرا:
    python3 tools/power_triage.py                 # همهٔ پوشه‌های _scan_*
    python3 tools/power_triage.py --scan S369     # فقط یکی
    python3 tools/power_triage.py --md            # خروجیِ جدولِ markdown
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.rqs2 import expected_max_z                                   # noqa: E402

# نسبتِ n_needed/n_obs که بالاتر از آن «گران» تلقی می‌شود.
HARD_RATIO = 5.0

# ⚠️ تصحیحِ شمارشِ آزمون. تعدادِ فایل‌های یک پوشهٔ اسکن **کفِ** شمارشِ آزمون است،
#    نه شمارشِ درست. چندگانگی به کلِ تاریخچهٔ جست‌وجوی همان فصل/خطِ کاری بدهکار است.
#    فصلِ ۲۶ (S364…S370) در مجموع ۷۶ آزمونِ سطح-کارت داشت ⇒ کران = 2.432.
#    این عدد در `results/S370_PREREG_ensemble_union.md` پیش‌ثبت شده است.
CHAPTER26 = {"S364", "S365", "S366", "S367", "S368", "S369", "S370"}
TRIALS_OVERRIDE = {s: 76 for s in CHAPTER26}

# پیشوندهایی که «فایلِ اسکن» نیستند بلکه خروجیِ داوری/کاوشِ جانبی‌اند.
JUDGE_PREFIXES = ("JUDGE_", "ANCHORJUDGE_")
AUX_PREFIXES = ("RPROBE_", "BURDEN_", "ABL_")


def _first(d, *names, default=None):
    """اولین کلیدِ موجود — اسکیمای پوشه‌های اسکن در طولِ پروژه یکسان نمانده."""
    for k in names:
        if k in d and d[k] is not None:
            return d[k]
    return default


def triage_one(path):
    """یک فایلِ نتیجه ⇒ dict تریاژ، یا None اگر قابلِ تریاژ نباشد."""
    try:
        d = json.load(open(path))
    except Exception:
        return None
    if not isinstance(d, dict):
        return None

    z = _first(d, "z", "z_obs", "skill_z")
    n = _first(d, "n_trades", "n_total_trades", "n_obs")
    if z is None or n is None:
        return None
    try:
        z = float(z)
        n = int(n)
    except Exception:
        return None
    if n <= 0:
        return None

    scan = os.path.basename(os.path.dirname(path)).replace("_scan_", "")
    card = os.path.basename(path)[:-5]

    kind = "scan"
    if card.startswith(JUDGE_PREFIXES):
        kind = "JUDGED"
    elif card.startswith(AUX_PREFIXES):
        kind = "aux"

    # ⚠️ شمارشِ آزمون. ترتیبِ اولویت:
    #   ۱) جدولِ تصحیح (تاریخچهٔ واقعیِ جست‌وجوی آن خطِ کاری)
    #   ۲) عددِ ثبت‌شده در خودِ فایل
    #   ۳) تعدادِ کارت‌های همان پوشه — این فقط **کف** است، نه عددِ درست.
    n_trials = TRIALS_OVERRIDE.get(scan)
    if not n_trials:
        n_trials = _first(d, "n_trials")
    if not n_trials:
        n_trials = len(glob.glob(os.path.join(os.path.dirname(path), "*.json")))
    z_luck = expected_max_z(max(int(n_trials), 1))

    # آیا این کارت قبلاً به داوریِ ۱۱ دروازه رفته؟ (فایلِ داوریِ هم‌نام در همان پوشه)
    judged = False
    for pref in JUDGE_PREFIXES:
        if os.path.exists(os.path.join(os.path.dirname(path), pref + card + ".json")):
            judged = True
            break

    if z <= 0:
        cat, need = "NEGATIVE", None
    else:
        need = n * (z_luck / z) ** 2
        if z >= z_luck:
            # ⚠️ عبور از کرانِ شانس **شرطِ لازم** است نه کافی. اگر این کارت قبلاً
            #    به داوریِ ۱۱ دروازه رفته و رد شده، «نامزدِ احیا» نیست.
            cat = "JUDGED_REJECTED" if judged else "CLEARS_BAR_UNJUDGED"
        elif need <= HARD_RATIO * n:
            cat = "RESCUABLE"
        else:
            cat = "HARD"

    return dict(scan=scan, card=card, z=z, n=n, n_trials=int(n_trials),
                z_luck=z_luck, n_needed=need, kind=kind, judged=judged,
                ratio=(need / n if need else None), category=cat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", default=None, help="فقط یک اسکن، مثلاً S369")
    ap.add_argument("--md", action="store_true", help="خروجیِ markdown")
    a = ap.parse_args()

    pat = f"results/_scan_{a.scan}/*.json" if a.scan else "results/_scan_*/*.json"
    rows = [r for r in (triage_one(p) for p in sorted(glob.glob(pat))) if r]

    if not rows:
        print("هیچ نتیجهٔ قابلِ تریاژی یافت نشد.")
        return

    order = {"CLEARS_BAR_UNJUDGED": 0, "RESCUABLE": 1,
             "JUDGED_REJECTED": 2, "HARD": 3, "NEGATIVE": 4}
    rows.sort(key=lambda r: (order[r["category"]],
                             -(r["z"] if r["z"] else 0)))

    ICON = {"CLEARS_BAR_UNJUDGED": "⭐", "RESCUABLE": "🟢",
            "JUDGED_REJECTED": "⚖️", "HARD": "🟡", "NEGATIVE": "🔴"}

    if a.md:
        print("| اسکن | کارت | n | z | کران | n لازم | ضریب | دسته |")
        print("|---|---|---|---|---|---|---|---|")
        for r in rows:
            nn = f"{r['n_needed']:,.0f}" if r["n_needed"] else "—"
            rt = f"×{r['ratio']:.1f}" if r["ratio"] else "—"
            print(f"| {r['scan']} | {r['card'].replace('_','-')} | {r['n']:,} "
                  f"| {r['z']:+.2f} | {r['z_luck']:.2f} | {nn} | {rt} "
                  f"| {ICON[r['category']]} {r['category']} |")
    else:
        print(f"{'scan':9}{'card':14}{'n':>7}{'z':>8}{'z_luck':>8}"
              f"{'n_needed':>10}{'ratio':>8}  category")
        for r in rows:
            nn = f"{r['n_needed']:,.0f}" if r["n_needed"] else "—"
            rt = f"x{r['ratio']:.1f}" if r["ratio"] else "—"
            print(f"{r['scan']:9}{r['card']:14}{r['n']:>7,}{r['z']:>+8.2f}"
                  f"{r['z_luck']:>8.2f}{nn:>10}{rt:>8}  "
                  f"{ICON[r['category']]} {r['category']}")

    import collections
    c = collections.Counter(r["category"] for r in rows)
    print(f"\nخلاصه ({len(rows)} نتیجه):  "
          f"✅ {c['ALREADY_CLEARS']}   🟢 {c['RESCUABLE']}   "
          f"🟡 {c['HARD']}   🔴 {c['NEGATIVE']}")
    resc = [r for r in rows if r["category"] == "RESCUABLE"]
    if resc:
        print("\n🟢 نامزدهای احیا (به ترتیبِ کم‌هزینه‌ترین):")
        for r in sorted(resc, key=lambda x: x["ratio"])[:15]:
            print(f"   {r['scan']:8} {r['card']:13} n={r['n']:>6,} → "
                  f"{r['n_needed']:>7,.0f}  (کمبود {r['n_needed']-r['n']:>7,.0f})")


if __name__ == "__main__":
    main()
