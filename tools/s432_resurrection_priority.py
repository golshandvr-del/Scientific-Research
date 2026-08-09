#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S432 — اولویت‌بندیِ **علمیِ** نامزدهای بعدیِ احیا
================================================================================
> این ابزار محصولِ مستقیمِ سه درسِ اندازه‌گیری‌شدهٔ این مأموریت است، نه یک
> فهرستِ سلیقه‌ای. هر ستونش به یک شکستِ واقعی برمی‌گردد که خودم دیدم.

┌─ درسِ ۱ (از شکستِ `S430`) ─────────────────────────────────────────────────┐
│ نامزد را با `z` انتخاب کردم و باختم. `S73` با `z=۱۱.۳۲σ` (رکوردِ بایگانی)   │
│ هم از `H9` نگذشت. علت: `z` می‌پرسد «آیا لبه **واقعی** است؟» ولی `H9`       │
│ می‌پرسد «آیا لبه **بزرگ** است؟». این دو **مستقل**‌اند.                      │
│ ⇒ ستونِ `h9_margin` = امیدِ خام − ۲×هزینه.  منفی ⇒ هیچ فیلتری نجاتش نمی‌دهد │
│   (چون فیلتر لبه را بزرگ نمی‌کند، فقط نمونه را کم می‌کند).                  │
└────────────────────────────────────────────────────────────────────────────┘
┌─ درسِ ۲ (از پیروزیِ `S431`) ───────────────────────────────────────────────┐
│ چهار کارت که هر یک `POWER-LIMITED` بودند، در **یک جمعیتِ تقویمیِ واحد**    │
│ به `z=۴.۷۰۶` و `RQS2=93.9` رسیدند — **بدونِ یک پارامترِ نو**.               │
│ ⇒ ستونِ `glass_ceiling` = `n_required_for_h3(lift, p0)` از خودِ موتور.      │
│   اگر `n < n_required` ⇒ شکستِ `H3` **ریاضیاً** کمبودِ نمونه است، نه نبودِ   │
│   لبه ⇒ **تجمیع** درمانِ درست است، نه فیلترِ بیشتر.                          │
└────────────────────────────────────────────────────────────────────────────┘
┌─ درسِ ۳ (از `BUG-PROBEWINDOW` و `E-00`) ──────────────────────────────────┐
│ «نبودِ داده ≠ صفر». هر کمیتِ غایب `None` می‌ماند و در جدول `?` چاپ می‌شود.  │
│ هرگز با صفر پر نمی‌شود، چون صفرِ ساختگی به نفعِ یا ضررِ لایه تحریف می‌کند.  │
└────────────────────────────────────────────────────────────────────────────┘

معیارِ اولویت (به‌ترتیبِ اهمیت، همه از دادهٔ موجود و بدونِ اجرای بک‌تستِ نو):

  ۱) `h9_margin > 0`         — سختِ **حذفی**. منفی ⇒ طبقهٔ `DEAD-COST`.
  ۲) `below_ceiling`         — آیا `n < n_required_for_h3`؟ (نامزدِ تجمیع)
  ۳) `only_power_gates`      — آیا **تنها** دروازه‌های توانی افتاده‌اند؟
                               (`H3`/`H5`/`H7`/`H10` بخشودنی‌اند؛ `H9` نیست)
  ۴) `oos_ok`                — آیا خارج‌نمونه هم مثبت است؟ (ضدِ بیش‌برازش)
  ۵) `n_siblings`            — چند کارتِ هم‌لایه‌ی هم‌جهت وجود دارد؟
                               (`S431` ثابت کرد این عاملِ تعیین‌کنندهٔ تجمیع است)

خروجی: `results/_s432_priority/priority_rank.json` + جدولِ فارسی در stdout.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from math import sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine.rqs2 import n_required_for_h3, UNPROVEN_Z_H3   # noqa: E402

VERDICT_DIR = os.path.join(ROOT, 'results', '_audit_rename', 'verdicts')
OUT_DIR = os.path.join(ROOT, 'results', '_s432_priority')

# دروازه‌های **توانی** (بخشودنی: با نمونهٔ بیشتر یا تجمیع درمان می‌شوند)
POWER_GATES = {'H3', 'H5', 'H7', 'H10'}
# دروازه‌های **ساختاری** (نابخشودنی در v2.6 — خصوصاً H9)
STRUCT_GATES = {'H0', 'H1', 'H2', 'H4', 'H6', 'H8', 'H9'}


def gv(m, key):
    """خواندنِ امنِ متریک: غایب ⇒ None (هرگز صفر)."""
    if not isinstance(m, dict):
        return None
    v = m.get(key)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return v


def failed_gates(card):
    """مجموعهٔ دروازه‌های افتاده + نامعلوم، از خودِ فیلدِ gates."""
    g = card.get('gates') or {}
    failed, unknown = set(), set()
    for name, val in g.items():
        key = str(name).split('_')[0].upper()
        if isinstance(val, bool):
            if not val:
                failed.add(key)
        elif isinstance(val, dict):
            ok = val.get('ok', val.get('passed'))
            if ok is False:
                failed.add(key)
            elif ok is None:
                unknown.add(key)
        elif val is None:
            unknown.add(key)
        elif isinstance(val, str):
            s = val.strip().lower()
            if s in ('fail', 'failed', 'no', 'false', '✗', '❌'):
                failed.add(key)
            elif s in ('unknown', '?', 'na', 'n/a'):
                unknown.add(key)
    return failed, unknown


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(VERDICT_DIR, '*.json')))
    if not files:
        print(f'[توقف] هیچ فایلِ حکمی در {VERDICT_DIR} نیست.')
        return

    rows = []
    for fp in files:
        try:
            doc = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        layer = doc.get('layer') or os.path.basename(fp)
        cards = doc.get('cards') or []
        if not isinstance(cards, list):
            continue
        for card in cards:
            if not isinstance(card, dict):
                continue
            m = card.get('metrics') or {}
            verdict = str(card.get('verdict') or '')
            if verdict == 'ACCEPT':
                continue                      # از قبل زنده است، نامزدِ احیا نیست

            exp = gv(m, 'expectancy_pip')
            cost = gv(m, 'cost_pip')
            n = gv(m, 'n_trades')
            lift = gv(m, 'skill_lift_pp')
            p0 = gv(m, 'null_ref_wr')

            # --- درسِ ۱: حاشیهٔ H9 (سختِ حذفی) ---
            h9m = None
            if exp is not None and cost is not None:
                h9m = exp - 2.0 * cost

            # --- درسِ ۲: سقفِ شیشه‌ای H3 ---
            ceil_n, below = None, None
            if lift is not None and p0 is not None:
                p0f = p0 / 100.0 if p0 > 1.0 else p0
                try:
                    ceil_n = n_required_for_h3(lift, p0f)
                except Exception:
                    ceil_n = None
                if ceil_n is not None and n is not None:
                    below = bool(n < ceil_n)

            failed, unknown = failed_gates(card)
            bad = failed | unknown
            only_power = bool(bad) and bad.issubset(POWER_GATES)
            h9_failed = 'H9' in failed

            # --- درسِ ۴: خارج‌نمونه ---
            oos = m.get('oos') if isinstance(m.get('oos'), dict) else None
            oos_ok = None
            if oos:
                w, req = oos.get('wr'), oos.get('wr_req')
                if isinstance(w, (int, float)) and isinstance(req, (int, float)):
                    oos_ok = bool(w >= req)

            rows.append(dict(
                layer=layer, card=card.get('card') or card.get('asset'),
                verdict=verdict, score=card.get('rqs2_score'),
                n=n, lift=lift, exp=exp, cost=cost, h9_margin=h9m,
                ceil_n=ceil_n, below_ceiling=below,
                failed=sorted(failed), unknown=sorted(unknown),
                only_power=only_power, h9_failed=h9_failed, oos_ok=oos_ok,
                wr=gv(m, 'win_rate'), z=gv(m, 'skill_z'),
            ))

    # ---- درسِ ۵: شمردنِ خواهر-کارت‌های هم‌جهت (پتانسیلِ تجمیع) ----
    sib = {}
    for r in rows:
        if r['lift'] is not None and r['lift'] > 0:
            sib[r['layer']] = sib.get(r['layer'], 0) + 1
    for r in rows:
        r['n_siblings'] = sib.get(r['layer'], 0)

    # ---- طبقه‌بندی ----
    def tier(r):
        if r['h9_margin'] is None:
            return 'UNKNOWN-COST'          # داده نیست ⇒ ادعا نمی‌کنیم
        if r['h9_margin'] <= 0 or r['h9_failed']:
            return 'DEAD-COST'             # درسِ S430: هیچ فیلتری نجاتش نمی‌دهد
        if r['only_power'] and r['below_ceiling'] and r['n_siblings'] >= 2:
            return 'POOL-READY'            # الگویِ دقیقِ S431
        if r['only_power'] and r['below_ceiling']:
            return 'POOL-SOLO'             # لبه واقعی، ولی خواهرِ کافی ندارد
        if r['only_power']:
            return 'FILTER-CAND'           # توانی ولی زیرِ سقف نیست
        return 'STRUCT-BROKEN'             # نقصِ ساختاریِ غیرِ H9

    for r in rows:
        r['tier'] = tier(r)

    ORDER = {'POOL-READY': 0, 'POOL-SOLO': 1, 'FILTER-CAND': 2,
             'STRUCT-BROKEN': 3, 'UNKNOWN-COST': 4, 'DEAD-COST': 5}

    # =======================================================================
    # اصلاحِ `BUG-SCALEBIAS` — رتبه‌بندیِ خامِ `h9_margin` سوگیریِ مقیاس داشت
    # -----------------------------------------------------------------------
    # نشانه: صدرِ فهرست شد `S350 / XAUUSD-W1` با `h9_margin = +۱۷۳.۲`
    # (بزرگ‌ترینِ کلِ بایگانی) — ولی `z = ۱.۰۴` و `lift = ۵.۹۸` و `WR = ۵۰.۰`.
    # یعنی نامزدِ «شمارهٔ یکِ» من لبه‌اش از نویز قابلِ تفکیک نبود.
    #
    # تشخیص (اندازه‌گیری، نه حدس): میانهٔ `h9_margin` را per-TF گرفتم:
    #     M5 ۳۸.۵ · M15 ۵۷.۰ · M30 ۶۴.۶ · H1 ۳۸.۷ · D1 ۸۹.۸ · W1 **۱۷۳.۲**
    # و میانهٔ `lift` در همان مسیر **نزولی** است (۱۴.۰ → ۵.۹۸).
    # ⇒ `h9_margin` عمدتاً **مقیاسِ تایم‌فریم** را می‌سنجد نه مهارت را: در `W1`
    #   هر معامله صدها pip دامنه دارد و هزینهٔ ۳.۳ pip در برابرش ناچیز است.
    #   پس یک لایهٔ بی‌مهارتِ W1 خودبه‌خود حاشیهٔ عظیم می‌گیرد.
    #
    # این دقیقاً **اشتباهِ رایجِ ۷** است در لباسِ نو: من از تلهٔ «فقط z»
    # (که `S430` را کشت) فرار کردم و مستقیم در تلهٔ «فقط H9» افتادم — یک
    # شبکهٔ محدودِ دیگر. علاجش هیچ‌کدام به‌تنهایی نیست، **هردو** با هم است.
    #
    # اصلاح: کلیدِ رتبه = `sqrt(z_norm × margin_norm)` (میانگینِ هندسی).
    #   • میانگینِ هندسی چون **هر دو** عامل باید بزرگ باشند؛ اگر یکی ~۰ شود
    #     حاصل ~۰ می‌شود (برخلافِ میانگینِ حسابی که یکی می‌تواند دیگری را
    #     بپوشاند). این همان «قفلِ دوگانه»ای است که `S430`+`S431` آموختند.
    #   • `margin_norm = margin / (2×cost)` ⇒ **بی‌بعد**: «امید چند برابرِ سدِ
    #     H9 است». این نرمال‌سازی سوگیریِ pip-مقیاس را حذف نمی‌کند کامل، ولی
    #     `z` که ذاتاً مقیاس‌ناپذیر است عاملِ دوم را مهار می‌کند.
    #   • `h9_margin` خام در ستون‌ها **می‌ماند** (حذفِ اطلاعات نمی‌کنم)، فقط
    #     دیگر تنها معیارِ ترتیب نیست.
    # =======================================================================
    # -----------------------------------------------------------------------
    # اصلاحِ دومِ همان باگ (`BUG-SCALEBIAS-2`): نرمال‌سازیِ اولم **کار نکرد**.
    # علت را از خروجی فهمیدم نه از حدس: ستونِ `cost` برای **هر** ردیف دقیقاً
    # `3.30` است (اسپردِ ثابتِ حسابِ دمو). پس `m/(2×cost)` صرفاً تقسیم بر یک
    # عددِ ثابت است ⇒ **ترتیب را عوض نمی‌کند** و `W1` با `m_norm = ۲۶.۲` باز
    # صدرنشین ماند. یک نرمال‌سازی که مقسوم‌علیهش ثابت است، نرمال‌سازی نیست.
    #
    # علاجِ درست، دو تغییر:
    #   ۱) حاشیه بر **دامنهٔ خودِ آن کارت** نرمال شود، نه بر هزینهٔ ثابت. بهترین
    #      نمایندهٔ در دسترس: `exp` (امیدِ خامِ همان کارت) هم‌مقیاسِ حاشیه است،
    #      پس `m/exp` = «چه سهمی از امید پس از پرداختِ ۲× هزینه می‌ماند» —
    #      کسری **بی‌بعد** در بازهٔ (۰,۱] که با بزرگ شدنِ TF ذاتاً رشد نمی‌کند.
    #   ۲) وزنِ `z` بیشتر شود، چون `z` تنها معیارِ **ذاتاً مقیاس‌ناپذیرِ** ما
    #      است: کلید = `z^(2/3) × ratio^(1/3)`. توانِ کسری همان خاصیتِ
    #      «قفلِ دوگانه» را نگه می‌دارد (اگر یکی ~۰ شود حاصل ~۰ می‌شود) ولی
    #      دیگر به بزرگیِ pip پاداش نمی‌دهد.
    #
    # درسِ روش‌شناختی که ثبتش می‌کنم: «نرمال‌سازی کردم» ادعای کافی نیست؛ باید
    # **تأیید** شود که مقسوم‌علیه واقعاً بینِ ردیف‌ها تغییر می‌کند. اگر خروجیِ
    # اصلاح را دوباره نمی‌خواندم، گمان می‌کردم سوگیری رفع شده در حالی که نشده بود
    # — همان شکستِ خاموشی که در `BUG-DEFAULTARG` هم گرفتارش شدم.
    # -----------------------------------------------------------------------
    def rank_key(r):
        m, z, e = r['h9_margin'], r.get('z'), r.get('exp')
        if m is None or m <= 0:
            return 0.0
        z_eff = max(0.0, z if z is not None else 0.0)
        if z_eff <= 0:
            return 0.0
        # سهمِ باقی‌ماندهٔ امید پس از سدِ H9 — بی‌بعد، مستقل از مقیاسِ TF
        ratio = (m / e) if (e is not None and e > 0) else None
        if ratio is None:
            return 0.0                      # دادهٔ ناقص ⇒ ادعا نمی‌کنیم
        ratio = min(1.0, max(0.0, ratio))
        return (z_eff ** (2.0 / 3.0)) * (ratio ** (1.0 / 3.0))

    for r in rows:
        r['rank_score'] = round(rank_key(r), 4)

    rows.sort(key=lambda r: (ORDER[r['tier']],
                             -r['rank_score'],
                             -(r['n_siblings'] or 0)))

    counts = {}
    for r in rows:
        counts[r['tier']] = counts.get(r['tier'], 0) + 1

    print('== S432 — اولویت‌بندیِ علمیِ نامزدهای احیا ==')
    print(f'جفت‌های (لایه×کارت) بررسی‌شده: {len(rows)}  ·  '
          f'فایلِ حکم: {len(files)}\n')
    print('طبقه‌بندی:')
    for t in sorted(counts, key=lambda x: ORDER[x]):
        print(f'  {t:14s} {counts[t]:4d}')

    def fmt(v, nd=2):
        return '?' if v is None else f'{v:.{nd}f}'

    print('\n-- صدرِ فهرست (۲۵ نامزدِ اولِ قابلِ احیا) --')
    hdr = (f"{'لایه':28s} {'کارت':13s} {'n':>5s} {'lift':>7s} "
           f"{'H9مرج':>8s} {'سقف':>8s} {'خواهر':>5s} {'OOS':>4s} {'طبقه':14s} افتاده")
    print(hdr)
    print('-' * len(hdr))
    shown = 0
    for r in rows:
        if r['tier'] in ('DEAD-COST', 'UNKNOWN-COST'):
            continue
        if shown >= 25:
            break
        oos_s = '?' if r['oos_ok'] is None else ('✓' if r['oos_ok'] else '✗')
        print(f"{str(r['layer'])[:28]:28s} {str(r['card'])[:13]:13s} "
              f"{fmt(r['n'],0):>5s} {fmt(r['lift']):>7s} {fmt(r['h9_margin'],1):>8s} "
              f"{fmt(r['ceil_n'],0):>8s} {r['n_siblings']:>5d} {oos_s:>4s} "
              f"{r['tier']:14s} {','.join(r['failed']+['?'+u for u in r['unknown']])}")
        shown += 1

    out = os.path.join(OUT_DIR, 'priority_rank.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(dict(n_pairs=len(rows), n_files=len(files),
                       counts=counts, rows=rows), f,
                  ensure_ascii=False, indent=1)
    print(f'\n[saved] {out}')

    print('\n== تفسیرِ طبقه‌ها ==')
    print('  POOL-READY   : الگویِ دقیقِ S431 ⇒ بالاترین شانسِ احیا با **تجمیع**.')
    print('  POOL-SOLO    : لبه واقعی و زیرِ سقفِ شیشه‌ای، ولی خواهرِ هم‌جهتِ کافی ندارد.')
    print('  FILTER-CAND  : فقط دروازهٔ توانی افتاده ولی n از سقف گذشته ⇒ فیلترِ کیفیت لازم است.')
    print('  STRUCT-BROKEN: نقصِ ساختاریِ غیرِ H9 (هندسی/رژیمی) ⇒ نیازمندِ بازطراحی.')
    print('  DEAD-COST    : حاشیهٔ H9 ≤ ۰ ⇒ درسِ S430: فیلتر لبه را بزرگ نمی‌کند ⇒ بی‌فایده.')
    print('  UNKNOWN-COST : دادهٔ هزینه/امید غایب ⇒ **هیچ ادعایی نمی‌کنیم** (نه مثبت نه منفی).')


if __name__ == '__main__':
    main()
