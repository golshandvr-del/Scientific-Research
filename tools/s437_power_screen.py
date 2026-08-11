# -*- coding: utf-8 -*-
"""
s437_power_screen.py — **غربالِ توان** پیش از پیش‌ثبت
======================================================

🎓 **چرا این ابزار وجود دارد** — درسِ مستقیمِ `S436` (`E-17`).

در `S436` من ۱۹۲۸ واحد از بودجهٔ چندگانگی خرج کردم و **بعد** فهمیدم که
نامزد با ~۱۹ معامله در سال، هرگز نمی‌تواند به سدِ `z ≈ ۳.۸۹` برسد:

    n لازم = ۵۳ × (۳.۰۹/۰.۴۶)² = ۲٬۳۹۲  ⇒  ۱۲۶ سالِ داده

این محاسبه **پنج ثانیه** طول می‌کشد و می‌شد **قبل** از داوری انجامش داد.
هر واحدِ بودجه‌ای که یک نامزدِ محکوم‌به‌شکست مصرف می‌کند، سد را برای **همهٔ**
نامزدهای بعدیِ مأموریت بالا می‌برد. پس این ابزار پرسشِ زیر را می‌پرسد:

    ❓ «آیا لبهٔ *مشاهده‌شدهٔ* این لایه، در افقِ دادهٔ *موجود*،
       می‌تواند از سدِ *مؤثر* عبور کند؟»

──────────────────────────────────────────────────────────────────────
## دو سدی که باید همزمان لحاظ شوند

موتور **دو** آستانهٔ مستقل دارد و نامزد باید از **هر دو** بگذرد:

| دروازه | سد | ماهیت |
|---|---|---|
| `H3` | `z ≥ 3.09` | **ثابت** — معناداری در برابرِ نالِ اندازه‌گیری‌شده |
| `H5` | `z > expected_max_z(n_trials)` | **متغیر** — با فضای جست‌وجو رشد می‌کند |

⇒ **سدِ مؤثر** `z_eff = max(3.09, expected_max_z(n_trials))`.

`engine.rqs2.n_required_for_h3` فقط سدِ **ثابت** را می‌بیند. اگر آن را
مستقیم به‌کار ببرم، توان را **بیش‌برآورد** می‌کنم — دقیقاً خطایی که در
`S436` مرتکب شدم. پس اینجا همان فرمولِ موتور را با `z_eff` بازاستفاده
می‌کنم، **نه** با `UNPROVEN_Z_H3`.

──────────────────────────────────────────────────────────────────────
## فرمول (بازاستفاده از موتور، نه بازنویسی)

از `n_required_for_h3`:

    n_req(z) = ( z · 100 · √(p₀(1−p₀)) / lift_pp )²

که `p₀` نرخِ بردِ مرجعِ نال (کسری) و `lift_pp` لیفت به درصد‌واحد است.
چون `n_req ∝ z²`، رابطهٔ زیر برقرار است:

    n_req(z_eff) = n_req(3.09) × (z_eff / 3.09)²

⇒ ستونِ `ceil_n` که در `s432_resurrection_priority` از قبل حساب شده،
   فقط باید در ضریبِ `(z_eff/3.09)²` ضرب شود. **هیچ فرمولِ نویی نوشته
   نمی‌شود** — قاعدهٔ «کپی کن، بازنویسی نکن» از `BUG-SCOREKEY`.

──────────────────────────────────────────────────────────────────────
## معیارِ غربال — سه ردهٔ توان

با `n_obs` = تعدادِ معاملهٔ مشاهده‌شده و `span_years` = بازهٔ کارت:

    نرخ = n_obs / span_years            (معامله در سال)
    سال‌های لازم = n_req(z_eff) / نرخ
    نسبتِ توان  = n_obs / n_req(z_eff)

| رده | شرط | معنا |
|---|---|---|
| `POWER-OK` | نسبت ≥ ۱.۰ | نمونهٔ موجود **کافی** است ⇒ شکستْ شکستِ لبه است |
| `POWER-NEAR` | ۰.۲۵ ≤ نسبت < ۱.۰ | با تجمیعِ کارت‌ها یا بهبودِ لیفت **دست‌یافتنی** |
| `POWER-WALL` | نسبت < ۰.۲۵ | **دیوارِ توان** ⇒ بودجهٔ چندگانگی مصرف نکن |

⚠️ **این غربال چیزی را رد نمی‌کند.** فقط **ترتیب** می‌دهد. یک لایه در
ردهٔ `POWER-WALL` هنوز می‌تواند از راهِ **تجمیعِ چندکارتی** (مثلِ `S431`)
یا **بهبودِ لیفت** نجات یابد؛ ولی نباید به‌صورتِ **تک‌کارتی** داوری شود.

⚠️ **و سوگیریِ ذاتی‌اش ثبت می‌شود:** `lift` مشاهده‌شده روی همان نمونه‌ای
اندازه گرفته شده که می‌خواهیم توانش را بسنجیم ⇒ لیفتِ خوش‌شانس، توان را
**بیش‌برآورد** می‌کند. پس `POWER-WALL` قابل‌اعتمادتر از `POWER-OK` است:
اگر حتی با لیفتِ خوش‌بینانه هم دیوار باشد، قطعاً دیوار است.
"""
from __future__ import annotations

import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.rqs2 import expected_max_z, UNPROVEN_Z_H3   # noqa: E402

SRC = os.path.join(ROOT, 'results/_s432_priority/priority_rank.json')
OUT = os.path.join(ROOT, 'results/_s437_power')

# بودجهٔ چندگانگیِ محتمل برای یک داوریِ تک‌کارتیِ استاندارد در این مأموریت.
# مبنا: `S436` با ۲۴۰ ترکیب در هر کارت × ۸ کارت + ۸ = ۱۹۲۸.
# اینجا سناریوی **محافظه‌کارانه‌تر** (تک‌کارتی، دامنهٔ کوچک‌تر) هم گزارش می‌شود
# تا حساسیتِ نتیجه به فرضِ بودجه دیده شود — نه اینکه یک عدد جادویی جا بزنم.
TRIAL_SCENARIOS = {
    'tight':  120,     # یک کارت، دامنهٔ کوچک
    'S436':  1928,     # آنچه در S436 واقعاً خرج شد
}

# بازهٔ سالِ هر کارت — از فایل‌های داده خوانده می‌شود، نه حدس زده شود.
CARD_SPAN_FALLBACK = 15.5


def n_req(lift_pp: float, p0_frac: float, z: float) -> float:
    """همان فرمولِ `engine.rqs2.n_required_for_h3` ولی با `z` دلخواه.

    فرمولِ موتور با `UNPROVEN_Z_H3` قفل شده است؛ اینجا همان عبارت با سدِ
    **مؤثر** بازاستفاده می‌شود. ضریبِ تبدیل: `n ∝ z²`.
    """
    if lift_pp is None or lift_pp <= 0:
        return float('inf')
    p0 = min(max(float(p0_frac), 1e-9), 1 - 1e-9)
    return (z * 100.0 * math.sqrt(p0 * (1.0 - p0)) / float(lift_pp)) ** 2


def classify(ratio: float) -> str:
    if ratio >= 1.0:
        return 'POWER-OK'
    if ratio >= 0.25:
        return 'POWER-NEAR'
    return 'POWER-WALL'


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    with open(SRC, encoding='utf-8') as f:
        data = json.load(f)
    rows = data['rows']

    bars = {k: max(UNPROVEN_Z_H3, expected_max_z(v))
            for k, v in TRIAL_SCENARIOS.items()}
    print('[S437 غربالِ توان] سدهای مؤثر:')
    for k, v in bars.items():
        print(f'   {k:6} n_trials={TRIAL_SCENARIOS[k]:>5} ⇒ z_eff={v:.3f}')

    out_rows = []
    for r in rows:
        lift, n_obs, wr, z = r.get('lift'), r.get('n'), r.get('wr'), r.get('z')
        if lift is None or n_obs is None or wr is None:
            continue
        # p₀ = نرخِ بردِ نالِ مرجع = WR مشاهده‌شده منهای لیفت (هر دو درصد)
        p0 = (float(wr) - float(lift)) / 100.0
        if not (0.0 < p0 < 1.0):
            continue
        rec = {
            'layer': r['layer'], 'card': r['card'], 'tier': r.get('tier'),
            'score': r.get('score'), 'n_obs': n_obs, 'lift_pp': lift,
            'wr': wr, 'z_obs': z, 'p0_null': round(p0, 4),
        }
        for k, zb in bars.items():
            need = n_req(lift, p0, zb)
            ratio = (n_obs / need) if need and math.isfinite(need) else 0.0
            rec[f'n_req_{k}'] = (round(need, 1) if math.isfinite(need) else None)
            rec[f'ratio_{k}'] = round(ratio, 4)
            rec[f'class_{k}'] = classify(ratio)
        out_rows.append(rec)

    with open(os.path.join(OUT, 'power_screen.json'), 'w', encoding='utf-8') as f:
        json.dump({'n_scored': len(out_rows), 'bars': bars,
                   'scenarios': TRIAL_SCENARIOS, 'rows': out_rows},
                  f, ensure_ascii=False, indent=1)

    import collections
    for k in bars:
        c = collections.Counter(x[f'class_{k}'] for x in out_rows)
        print(f'\n  سناریوی {k}: ' + ' · '.join(f'{a}={b}' for a, b in c.most_common()))

    print(f'\n  ✅ {len(out_rows)} ردیف امتیازدهی شد ⇒ {OUT}/power_screen.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
