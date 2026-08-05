# -*- coding: utf-8 -*-
"""گامِ ۱ — بخشِ ۱: سرشماریِ **داده** (نه استراتژی).

منطق در یک جمله: پیش از هر بک‌تستی، فقط بشمار.

چرا این ابزار پیش از هر چیزِ دیگری می‌آید: «نرخِ سیگنال» صفر درجهٔ آزادی
دارد. هیچ TP/SL، هیچ سود، هیچ برد-باخت. فقط «این شرط در بازهٔ واقعیِ داده
چند بار رخ داد؟». پس **غیرقابلِ تقلب** است — با تنظیمِ پارامتر بهتر نمی‌شود.
و برای اینکه نرخِ سالانه معنا داشته باشد، ابتدا باید **بازهٔ تقویمیِ واقعیِ
هر فایل** را بدانیم؛ نشستِ قبل ثابت شد که فرضِ «۳ سال» غلط بود و بازهٔ
واقعی ۱۵.۵ تا ۱۶.۲ سال است. تعدادِ کندل هرگز جای بازهٔ تقویمی را نمی‌گیرد.

خروجی: `results/_step1_census/data_census.json` + جدولِ خوانا.
"""

import csv
import json
import os
from datetime import datetime, timezone

DATA = 'data'
OUT = 'results/_step1_census'
os.makedirs(OUT, exist_ok=True)

# روزهای معاملاتیِ سال (تقویمِ فارکس ≈ ۵ روز در هفته)
TRADING_DAYS = 252
# هدفِ سایت: روزی ۱ سیگنال
SITE_TARGET_PER_YEAR = TRADING_DAYS


def scan_file(path):
    """اولین و آخرین timestamp و تعدادِ ردیف — با یک پاسِ خطی، بی‌بارگذاریِ کل."""
    n = 0
    t_first = t_last = None
    with open(path, newline='', encoding='utf-8', errors='ignore') as fh:
        rd = csv.reader(fh)
        header = next(rd, None)
        for row in rd:
            if not row:
                continue
            try:
                t = int(float(row[0]))
            except (ValueError, IndexError):
                continue
            if t_first is None:
                t_first = t
            t_last = t
            n += 1
    return n, t_first, t_last, header


def main():
    files = sorted(f for f in os.listdir(DATA) if f.endswith('.csv'))
    rows = []
    for fn in files:
        path = os.path.join(DATA, fn)
        n, t0, t1, header = scan_file(path)
        if not n or t0 is None:
            continue
        span_days = (t1 - t0) / 86400.0
        span_years = span_days / 365.25
        card = fn[:-4]
        pair, _, tf = card.rpartition('_')
        rows.append(dict(
            card=card, pair=pair, tf=tf, bars=n,
            t_first=t0, t_last=t1,
            date_first=datetime.fromtimestamp(t0, timezone.utc).strftime('%Y-%m-%d'),
            date_last=datetime.fromtimestamp(t1, timezone.utc).strftime('%Y-%m-%d'),
            span_years=round(span_years, 2),
            bars_per_year=round(n / span_years, 1) if span_years > 0 else 0,
        ))

    rows.sort(key=lambda r: (r['pair'], r['tf']))

    print(f'{"card":16s} {"first":>11s} {"last":>11s} {"years":>7s} '
          f'{"bars":>9s} {"bars/yr":>10s} {"bars/day":>9s}')
    print('-' * 80)
    for r in rows:
        bpd = r['bars_per_year'] / TRADING_DAYS
        print(f'{r["card"]:16s} {r["date_first"]:>11s} {r["date_last"]:>11s} '
              f'{r["span_years"]:7.2f} {r["bars"]:9,d} {r["bars_per_year"]:10,.0f} '
              f'{bpd:9.1f}')

    out = dict(
        trading_days_per_year=TRADING_DAYS,
        site_target_signals_per_year=SITE_TARGET_PER_YEAR,
        n_files=len(rows),
        cards=rows,
    )
    with open(os.path.join(OUT, 'data_census.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f'\nsaved → {OUT}/data_census.json')


if __name__ == '__main__':
    main()
