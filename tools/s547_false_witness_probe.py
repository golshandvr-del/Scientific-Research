# -*- coding: utf-8 -*-
"""S547 — سنجشِ «شاهدِ کاذب» پیش از اتصال به سایت.

پرسش (تنها پرسشی که مکانیزمِ نمایشِ سایت نمی‌تواند پاسخ دهد):
    آیا S547 و یکی از لایه‌های **از پیش وصلِ همان کارت** در واقع یک رویدادِ
    واحد با دو نام‌اند؟ اگر بله، سایت دو کادر نشان می‌دهد و کاربر می‌پندارد دو
    شاهدِ مستقل دارد، در حالی که یک شاهد دوبار شمرده شده — ریسک دوبرابر بدونِ
    هیچ اطلاعِ تازه. تشخیص فقط با اندازه‌گیری ممکن است، نه با UI.

سابقهٔ مستندِ ریپو: S404/S408 با jaccard ۶۹.۳٪ و share_of_b ۹۹.۴٪ ⇒ حکمِ
«یکی، نه هر دو» (strategy_registry.ts:۹۵۶–۹۵۹ و FALSE_WITNESS_PAIRS).

روش (روز-محور، عیناً همان واحدی که `_s408_overlap.json` و `_s1400_overlap.json`
استفاده کرده‌اند تا اعداد قابلِ مقایسه بمانند):
    • رویدادِ S547 = روزِ P (روزِ پیش‌تعطیلات) — سیگنال روی آخرین کندلِ روزِ
      معاملاتیِ **قبل** از P، ورود در openِ روزِ P ⇒ روزِ اثر = P.
      (تولید عیناً با `tools/s547_preholiday_runner.py::preholiday_days`)
    • رویدادِ لایه‌های وصل‌شدهٔ گپ (S408-M15 / S562-M15 / S562-H1) = روزِ ورود.
      منبع: آرتیفکت‌های منجمدِ read-only همان بلوک‌ها (هیچ بازاجرایی لازم نیست).
    • رویدادِ S312 (تنها لایهٔ تقویمیِ وصل‌شده، روی هر سه کارتِ M15/M30/H1):
      قاعده‌اش صفر-پارامتر و تقویمی است (dom ∈ {۱۰,۱۳,۲۰}) ⇒ مستقیم از تقویم.
    • معیار: jaccard و share_of_a/share_of_b روی مجموعهٔ روزها.

این اسکریپت **فقط می‌خواند و چاپ می‌کند**؛ هیچ فایلی از قلمروِ بلوک‌های دیگر
را تغییر نمی‌دهد و هیچ حکمی صادر نمی‌کند.
"""

from __future__ import annotations

import json
import os
import sys

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from dateutil.easter import easter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)


def preholiday_days(y0=2010, y1=2027):
    """عیناً کپیِ تابعِ رانرِ S547 — هیچ بازتعریفی، تا اعداد همان باشند."""
    h = USFederalHolidayCalendar().holidays(f'{y0}-01-01', f'{y1}-12-31', return_name=True)
    keep = h[~h.str.contains('Columbus|Veterans')]
    gf = pd.DatetimeIndex([pd.Timestamp(easter(y)) - pd.Timedelta(days=2) for y in range(y0, y1 + 1)])
    hol = keep.index.union(gf).sort_values()
    pre = []
    for d in hol:
        p = d - pd.offsets.BDay(1)
        while p in hol:
            p = p - pd.offsets.BDay(1)
        pre.append(p)
    return pd.DatetimeIndex(pre).unique().sort_values()


def jaccard(a: set, b: set) -> dict:
    if not a or not b:
        return {'n_a': len(a), 'n_b': len(b), 'shared': 0, 'share_of_a': 0.0,
                'share_of_b': 0.0, 'jaccard': 0.0}
    sh = len(a & b)
    return {
        'n_a': len(a), 'n_b': len(b), 'shared': sh,
        'share_of_a': round(100.0 * sh / len(a), 1),
        'share_of_b': round(100.0 * sh / len(b), 1),
        'jaccard': round(100.0 * sh / len(a | b), 1),
    }


def days_from_times(times) -> set:
    """لیستِ رشته/عددِ زمانِ سیگنال → مجموعهٔ روزهای تقویمیِ UTC."""
    s = pd.to_datetime(pd.Series(list(times)), utc=True, errors='coerce')
    if s.isna().all():
        s = pd.to_datetime(pd.Series(list(times)), unit='s', utc=True, errors='coerce')
    return set(s.dropna().dt.tz_convert('UTC').dt.normalize().dt.date)


def main():
    out = {'unit': 'calendar day (UTC)', 'purpose': 'false-witness screen before wiring S547'}

    # --- دامنهٔ زمانیِ مشترک: بازهٔ دادهٔ رسمی (۲۰۱۱-۰۱-۰۳ → ۲۰۲۶-۰۸-۰۷) ---
    lo, hi = pd.Timestamp('2011-01-03').date(), pd.Timestamp('2026-08-07').date()
    pre = {d.date() for d in preholiday_days() if lo <= d.date() <= hi}
    out['S547_pre_holiday_days'] = len(pre)

    # --- S312: تنها لایهٔ تقویمیِ از پیش وصل (کارت‌های M15/M30/H1) ---
    all_days = pd.date_range(lo, hi, freq='D')
    s312 = {d.date() for d in all_days if d.day in (10, 13, 20)}
    out['vs_S312_midmonth_calendar'] = jaccard(pre, s312)

    # --- لایه‌های گپ‌محورِ وصل‌شده: از آرتیفکت‌های منجمد ---
    for tag, path, key in [
        ('vs_S562_M15', 'results/_s562_arms/signal_bars_M15.json', 'signal_times_frozen'),
        ('vs_S562_H1', 'results/_s562_arms/signal_bars_H1.json', 'signal_times_frozen'),
    ]:
        if not os.path.exists(path):
            out[tag] = {'error': f'missing {path}'}
            continue
        d = json.load(open(path))
        days = {x for x in days_from_times(d[key]) if lo <= x <= hi}
        out[tag] = jaccard(pre, days)

    # --- S408-M15: روزهای سیگنال از سندِ هم‌پوشانیِ خودش قابلِ استخراج نیست،
    #     ولی تعدادِ روزها (۴۹۳) و پنجره‌اش ثبت است. برای اینکه ادعای بی‌پشتوانه
    #     نسازیم، فقط چیزی را گزارش می‌کنیم که واقعاً اندازه گرفته‌ایم. ---
    ov408 = 'results/_s408_overlap.json'
    if os.path.exists(ov408):
        d = json.load(open(ov408))
        out['S408_M15_reference'] = {
            'n_days': d.get('S408_n_days'),
            'window': [d.get('S408_first'), d.get('S408_last')],
            'note': 'روزهای دقیقِ S408 در آرتیفکت ذخیره نشده؛ استدلالِ سازوکاری در گزارش.',
        }

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


if __name__ == '__main__':
    sys.exit(0 if main() else 0)
