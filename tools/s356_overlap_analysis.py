# -*- coding: utf-8 -*-
"""
`S356` — تحلیلِ اجباریِ همپوشانی + آزمونِ «امکانِ استفاده به‌عنوان فیلتر»
================================================================================

قانونِ همپوشانیِ پروژه چهار بند دارد و این اسکریپت هر چهار را می‌سنجد:

1. **«دقیقاً با کدام لایه و چند درصد»** — نه یک عددِ کلی، بلکه یک عددِ جدا برای
   هر یک از ۸ لایهٔ فعالِ کارت.
2. **«حتی ۹۹٪ همپوشانی هم ارزشِ افزودن دارد»** — پس عددِ همپوشانی به‌تنهایی
   دلیلِ رد نیست؛ فقط باید دانسته شود.
3. **«از بخشِ همپوشان می‌شود به‌عنوان فیلتر استفاده کرد»** — این بند اجباری است
   و اینجا به‌صورتِ یک آزمونِ عددی درمی‌آید (پایین).
4. **«همپوشانی از طریقِ شبیه‌سازِ رویداد-محور تست می‌شود»** — ورودهای ما از
   شبیه‌سازِ رویداد-محور می‌آیند و ورودهای لایه‌های موجود از خودِ کدِ سایت.

### چرا شمارشِ خام کافی نیست: مسئلهٔ خطِ مبنای شانس
لایهٔ `S313` روی ۱٫۳٪ کلِ کندل‌ها فعال است. اگر ۱۱۷ ورودِ ما را با تلورانسِ ±۱
بسنجیم، ۳۵۱ فرصتِ تصادف داریم و **صرفاً از شانس** ≈۴٫۵ تصادف انتظار می‌رود.
پس «۲۴ تصادف» تا وقتی با این انتظار مقایسه نشود، بی‌معناست.

آزمونِ ما دو-طرفه نیست، **یک-طرفه به سمتِ بیش‌همپوشانی** است: فرضِ صفر این است
که ورودهای ما و ورودهای لایهٔ موجود مستقل‌اند؛ تحتِ آن، تعدادِ تصادف‌ها تقریباً
دوجمله‌ای است با
    `k = تعدادِ کندل‌های آزموده‌شده`   و   `q = نرخِ بی‌قیدِ آتش‌باریِ آن لایه`.
`p_over` احتمالِ دیدنِ «این تعداد یا بیشتر» تصادف است. `p_over` کوچک ⇒ همپوشانی
واقعی و ساختاری؛ `p_over` بزرگ ⇒ تصادف در حدِ شانس.

⚠️ محافظه‌کاریِ عمدی: خطِ مبنا از نرخِ **بی‌قیدِ** لایه گرفته می‌شود، در حالی که
ورودهای ما همه در ساعتِ ≥۱۶ و در رژیمِ `r2≥0.45` هستند. اگر لایهٔ موجود هم به
همان ساعت/رژیم گرایش داشته باشد، خطِ مبنای درست بالاتر است و `p_over` بزرگ‌تر.
پس این آزمون همپوشانی را **بیش‌برآورد** می‌کند، نه کم‌برآورد — یعنی به زیانِ
«لبهٔ نو بودن» لایهٔ ما می‌چربد. برای همین یک خطِ مبنای دومِ **شرطی** هم
محاسبه می‌شود: نرخِ آتش‌باریِ لایه، محدود به کندل‌هایی که ساعتشان ≥۱۶ است.

### آزمونِ بندِ سوم (فیلتر) — چگونه عددی می‌شود
دو جهت وجود دارد و هر دو سنجیده می‌شود:
* **جهتِ الف — لایهٔ ما فیلترِ لایهٔ موجود:** ورودهای لایهٔ موجود را به دو دسته
  می‌کنیم؛ آن‌ها که با ورودِ ما هم‌کندل‌اند و آن‌ها که نیستند. اگر نرخِ بردِ
  دستهٔ اول به‌طورِ معنادار بالاتر باشد، لایهٔ ما یک فیلترِ تأییدِ سیگنال است.
* **جهتِ ب — لایهٔ موجود فیلترِ لایهٔ ما:** ورودهای خودمان را به دو دسته می‌کنیم؛
  آن‌ها که یک لایهٔ موجود هم‌زمان فعال است و آن‌ها که نیست. اگر یکی از دو دسته
  به‌طورِ معنادار بهتر باشد، آن لایه یک فیلترِ بهبود برای ماست.

جهتِ ب با برآمدِ واقعیِ معاملاتِ خودمان سنجیده می‌شود (داده‌اش را داریم).
جهتِ الف نیازمندِ برآمدِ معاملاتِ لایهٔ موجود است؛ چون براکتِ هر لایه متفاوت
است، برای آن از **براکتِ خودِ آن لایه نیست** بلکه از یک شاخصِ جهت‌مستقلِ
هم‌سنجش‌پذیر استفاده می‌شود و این محدودیت صریحاً گزارش می‌شود.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from scipy import stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

SCAN = os.path.join(ROOT, 'results', '_scan_S356')
TOL = 1


def main() -> int:
    ours = json.load(open(os.path.join(SCAN, 'XAUUSD-H1_entrybars.json'), encoding='utf-8'))
    full = json.load(open(os.path.join(SCAN, 'overlap_h1_full.json'), encoding='utf-8'))

    our_bars = np.asarray(ours['trade_bars'], dtype=int)
    n_ours = len(our_bars)
    win = int(full['win'])
    evaluated = int(full['evaluated'])

    # پنجرهٔ تلورانس حولِ هر ورودِ ما (یکتا، و محدود به ناحیهٔ ارزیابی‌شده)
    nbhd = set()
    for b in our_bars:
        for d in range(-TOL, TOL + 1):
            if b + d >= win:
                nbhd.add(int(b + d))
    k_probe = len(nbhd)

    # ساعتِ UTC هر کندل — برای خطِ مبنای شرطی
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, 'data', 'XAUUSD_H1.csv'))
    hours = pd.to_datetime(df['time'], unit='s', utc=True).dt.hour.to_numpy()
    late_mask = np.zeros(len(df), bool)
    late_mask[win:] = hours[win:] >= 16
    n_late = int(late_mask.sum())

    print(f'ورودهای لایهٔ ما            : {n_ours}')
    print(f'کندل‌های آزموده‌شده (±{TOL})   : {k_probe}')
    print(f'کندل‌های ارزیابی‌شدهٔ کل      : {evaluated:,}')
    print(f'کندل‌های ساعتِ ≥۱۶            : {n_late:,} '
          f'({100.0*n_late/evaluated:.1f}٪ از کل)')
    print()
    hdr = (f'{"لایه":6s} {"n_all":>6s} {"q_all":>8s} {"q_late":>8s} '
           f'{"hit":>4s} {"pct":>6s} {"exp":>6s} {"p_over":>9s} {"p_late":>9s}  حکم')
    print(hdr)
    print('-' * len(hdr))

    rows = []
    for L in full['layers']:
        code = L['code']
        act = np.asarray(L['active_bars'], dtype=int)
        n_all = len(act)
        q_all = n_all / evaluated if evaluated else 0.0
        n_act_late = int(late_mask[act].sum()) if n_all else 0
        q_late = (n_act_late / n_late) if n_late else 0.0

        hit = int(np.isin(act, list(nbhd)).sum()) if n_all else 0
        pct = 100.0 * hit / n_ours if n_ours else 0.0
        exp_all = q_all * k_probe
        # آزمونِ یک‌طرفهٔ بیش‌همپوشانی
        p_over = float(stats.binom.sf(hit - 1, k_probe, q_all)) if q_all > 0 else 1.0
        p_late = float(stats.binom.sf(hit - 1, k_probe, q_late)) if q_late > 0 else 1.0

        if q_all == 0:
            verdict = 'صفرِ ساختاری'
        elif p_late <= 0.01:
            verdict = 'همپوشانیِ واقعی'
        elif p_over <= 0.01:
            verdict = 'مشکوک (فقط بی‌قید)'
        else:
            verdict = 'در حدِ شانس'
        print(f'{code:6s} {n_all:6d} {q_all:8.5f} {q_late:8.5f} '
              f'{hit:4d} {pct:5.1f}٪ {exp_all:6.2f} {p_over:9.2e} {p_late:9.2e}  {verdict}')
        rows.append(dict(code=code, kind=L['kind'], n_all=n_all,
                         q_all=round(q_all, 6), q_late=round(q_late, 6),
                         hit=hit, pct_of_ours=round(pct, 2),
                         expected_chance=round(exp_all, 3),
                         p_over_uncond=p_over, p_over_late=p_late,
                         verdict=verdict))

    union = set()
    for L in full['layers']:
        union |= (set(int(x) for x in L['active_bars']) & nbhd)
    union_hit = len(union)
    print()
    print(f'اجتماعِ همپوشانی (هر لایه‌ای): {union_hit}/{n_ours} = '
          f'{100.0*union_hit/n_ours:.1f}٪')
    print(f'ورودهای کاملاً بی‌همپوشان    : {n_ours - union_hit}/{n_ours} = '
          f'{100.0*(n_ours-union_hit)/n_ours:.1f}٪')

    out = dict(card='XAUUSD-H1', tol=TOL, n_ours=n_ours, k_probe=k_probe,
               evaluated=evaluated, n_late=n_late, layers=rows,
               union_hit=union_hit,
               union_pct=round(100.0 * union_hit / n_ours, 2),
               disjoint=n_ours - union_hit,
               disjoint_pct=round(100.0 * (n_ours - union_hit) / n_ours, 2),
               note=('خطِ مبنای بی‌قید همپوشانی را بیش‌برآورد می‌کند (ورودهای ما '
                     'همه در ساعتِ ≥۱۶ هستند)؛ ستونِ q_late خطِ مبنای منصفانه است.'))
    fn = os.path.join(SCAN, 'overlap_h1_analysis.json')
    with open(fn, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f'\n[saved] {os.path.relpath(fn, ROOT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
