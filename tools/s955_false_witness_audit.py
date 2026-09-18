# -*- coding: utf-8 -*-
"""S955 — ممیزیِ «شاهدِ کاذب» پیش از سیم‌کشی به سایت · XAUUSD-H8 / H12 / H6

چرا این ابزار وجود دارد
=======================
مکانیزمِ نمایشِ سایت همپوشانیِ معمولِ لایه‌ها را خودش حل می‌کند (لایهٔ صدرِ آرایه
تصمیمِ کارت را می‌دهد، بقیه در otherLayers). اما یک حالت هست که نمایش نمی‌تواند
حلش کند: **وقتی دو لایه در واقع یک رویدادِ واحد با دو اسم باشند.** آن‌وقت سایت دو
کادر نشان می‌دهد، کاربر گمان می‌کند دو شاهدِ مستقل دارد، در حالی که یک شاهد دو بار
شمرده شده — «شاهدِ کاذب»: ریسک دو برابر، اطلاعِ تازه صفر.

قاعدهٔ تصمیم — از خودِ مخزن، نه سلیقه
=====================================
دو پروندهٔ پیشین معیار را تثبیت کرده‌اند:

  ① S404/S408 (strategy_registry.ts، ورودیِ S408 روی کارتِ M15):
     jaccard ۶۹.۳٪ **به‌همراهِ هم‌اندازگی** ⇒ «یکی، نه هر دو».
  ② S966/S1911 (همان فایل، ورودیِ S1911 روی کارتِ H8):
     زیرمجموعه با **نصف** اندازه (۸۲ از ۱۴۴) ⇒ فیلترِ کیفیت، نه شاهدِ نو ⇒
     مجاز است، اما باید **زیرِ** لایهٔ والد در آرایه بنشیند.

پس تمایزگرِ واقعی «هم‌اندازگی» است، نه فقط jaccard:
  · jaccard بالا + n تقریباً مساوی      ⇒ FALSE-WITNESS (یکی، نه هر دو)
  · زیرمجموعه + n به‌مراتب کوچک‌تر       ⇒ فیلترِ کیفیت (مجاز، مرتبهٔ آرایه مقید)
  · jaccard پایین                        ⇒ مستقل (آزاد)

این ابزار فقط **می‌خواند**: از `results/_scan_S955/overlap_audit.json` (اندازه‌گیریِ
منتشرشدهٔ خودِ لایه) و از اسنادِ ACCEPTِ S955/S1913. هیچ عددی را دوباره تولید
نمی‌کند و هیچ حکمی را بازنویسی نمی‌کند — دقیقاً به این دلیل که اندازه‌گیریِ قبلی
مرجع است و بازاجرا ریسکِ انحراف دارد.

خروجی: results/_s955_ckpt/false_witness.json
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OVERLAP = os.path.join(ROOT, 'results', '_scan_S955', 'overlap_audit.json')
DOC_S955 = os.path.join(ROOT, 'results',
                        'S955_JumpAftermathCalmRegime_Xauusd_H8H12H6_rqs2_88_ACCEPT.md')
DOC_S1913 = os.path.join(ROOT, 'results',
                         'S1913_JumpAftermathCalm_Xauusd_H8_rqs2_89.3_ACCEPT.md')
OUT_DIR = os.path.join(ROOT, 'results', '_s955_ckpt')
OUT_FILE = os.path.join(OUT_DIR, 'false_witness.json')

# آستانه‌ها — عیناً از دو پروندهٔ پیشین استخراج شده‌اند، نه انتخابِ تازه
JACCARD_HIGH = 0.45      # S404/S408 روی ۰.۶۹ افتاد؛ S1911/S965 روی ۰.۵۷ *مجاز* شد
SIZE_PARITY = 0.80       # n_min/n_max ≥ ۰.۸ ⇒ «هم‌اندازه» (S1911 روی ۰.۵۷ بود ⇒ مجاز)


def jaccard(n_a, n_b, same_bar):
    union = n_a + n_b - same_bar
    return (same_bar / union) if union > 0 else 0.0


def classify(n_a, n_b, same_bar):
    """طبقه‌بندیِ یک جفت‌لایه طبقِ قاعدهٔ دو-پروندهٔ بالا."""
    jac = jaccard(n_a, n_b, same_bar)
    parity = min(n_a, n_b) / max(n_a, n_b) if max(n_a, n_b) else 0.0
    share_a = (same_bar / n_a * 100) if n_a else 0.0
    if jac >= JACCARD_HIGH and parity >= SIZE_PARITY:
        verdict = 'FALSE-WITNESS'
        rule = 'jaccard بالا + هم‌اندازگی ⇒ یک رویداد با دو اسم (پروندهٔ S404/S408) ⇒ یکی، نه هر دو'
    elif share_a >= 90.0:
        verdict = 'SUBSET-QUALITY-FILTER'
        rule = ('زیرمجموعهٔ ساختاری با اندازهٔ کوچک‌تر ⇒ فیلترِ کیفیت روی رویدادهای والد '
                '(پروندهٔ S966/S1911) ⇒ مجاز، اما نباید هم‌زمان با والد سایز بگیرد')
    elif jac >= JACCARD_HIGH:
        verdict = 'PARTIAL-DEPENDENT'
        rule = 'jaccard بالا بدونِ هم‌اندازگی ⇒ وابستهٔ جزئی ⇒ مرتبهٔ آرایه مقید شود'
    else:
        verdict = 'INDEPENDENT'
        rule = 'jaccard پایین ⇒ شاهدِ مستقل ⇒ هم‌زیستی آزاد'
    return dict(jaccard=round(jac, 3), size_parity=round(parity, 3),
                share_of_s955_pct=round(share_a, 1),
                verdict=verdict, rule=rule)


def grep_numbers(path, patterns):
    """استخراجِ اعدادِ کلیدی از سندِ ACCEPT — برای آزمونِ هم‌اندازگیِ S955 vs S1913."""
    if not os.path.exists(path):
        return {}
    txt = open(path, encoding='utf-8').read()
    out = {}
    for key, rx in patterns.items():
        m = re.search(rx, txt)
        if m:
            out[key] = float(m.group(1))
    return out


def main():
    if not os.path.exists(OVERLAP):
        print(f'ERROR: اندازه‌گیریِ همپوشانی یافت نشد: {OVERLAP}', file=sys.stderr)
        return 2
    os.makedirs(OUT_DIR, exist_ok=True)
    data = json.load(open(OVERLAP, encoding='utf-8'))

    report = {
        'layer': 'S955',
        'purpose': 'ممیزیِ شاهدِ کاذب پیش از سیم‌کشی (H8/H12/H6)',
        'source_of_truth': 'results/_scan_S955/overlap_audit.json (اندازه‌گیریِ منتشرشدهٔ خودِ لایه — فقط خوانده شد)',
        'decision_rule': {
            'jaccard_high': JACCARD_HIGH,
            'size_parity': SIZE_PARITY,
            'precedents': ['S404/S408 ⇒ یکی، نه هر دو', 'S966/S1911 ⇒ زیرمجموعهٔ نصف‌اندازه مجاز است'],
        },
        'per_card': {},
        'twin_layer_check': {},
    }

    print('=' * 100)
    print('S955 — ممیزیِ شاهدِ کاذب در برابرِ ساکنانِ فعلیِ سایت')
    print('=' * 100)
    for card in ('H8', 'H12', 'H6'):
        rows = data.get(card)
        if not isinstance(rows, list):
            continue
        out_rows = []
        print(f'\n### کارتِ XAUUSD-{card}')
        for r in rows:
            cls = classify(r['n_a'], r['n_b'], r['same_bar'])
            row = dict(vs=r['vs'], n_s955=r['n_a'], n_other=r['n_b'],
                       same_bar=r['same_bar'],
                       window_overlap_pct=r.get('window_overlap_pct_of_a'),
                       opposite_dir=r.get('opposite_dir_same_bar'), **cls)
            out_rows.append(row)
            print(f"  · در برابرِ {r['vs']}")
            print(f"      n: {r['n_a']} vs {r['n_b']} · هم‌کندل: {r['same_bar']} "
                  f"({cls['share_of_s955_pct']}٪ از S955)")
            print(f"      jaccard={cls['jaccard']} · هم‌اندازگی={cls['size_parity']} "
                  f"· پنجرهٔ نگهداری={r.get('window_overlap_pct_of_a')}٪ "
                  f"· جهتِ مخالف={r.get('opposite_dir_same_bar')}")
            print(f"      ⇒ {cls['verdict']}: {cls['rule']}")
        report['per_card'][card] = out_rows

    # ---- آزمونِ لایهٔ دوقلو: S955-H8 در برابرِ S1913-H8 -------------------
    # این جفت در overlap_audit نیست چون S1913 لایهٔ نویسندهٔ دیگری است؛ اما
    # هر دو سند اعلام می‌کنند که همان قاعده را آزموده‌اند. آزمونِ هم‌اندازگی
    # اینجا روی **اعدادِ حکم** انجام می‌شود (n/WR/PF/maxDD) — اگر هر چهار عدد
    # یکی باشند، دو نام یک رویداد است.
    pats = {
        'n': r'n=(\d+)\s+WR=',
        'wr': r'WR=([\d.]+)%',
        'pf': r'PF=([\d.]+)',
        'maxdd': r'maxDD=([\d.]+)%',
    }
    a = grep_numbers(DOC_S955, pats)
    b = grep_numbers(DOC_S1913, pats)
    identical = bool(a) and bool(b) and all(
        abs(a.get(k, -1) - b.get(k, -2)) < 1e-9 for k in ('n', 'wr', 'pf', 'maxdd'))
    twin = dict(
        pair='S955-H8 vs S1913-H8',
        s955=a, s1913=b, all_four_identical=identical,
        verdict='FALSE-WITNESS' if identical else 'DISTINCT',
        rule=('هر چهار عددِ حکم (n/WR/PF/maxDD) عیناً یکی ⇒ یک رویدادِ واحد با دو اسم. '
              'هر دو سند خودشان همین را اعلام می‌کنند (S955 §۸: «یک لایه، دو نام؛ فقط یکی '
              'مستقر شود»؛ S1913 §پایانی: «عیناً همان اعدادِ S1913»). ⇒ روی سایت فقط یکی '
              'وصل شود؛ دیگری حتی به‌عنوانِ otherLayers هم نباید کادرِ جدا بگیرد.')
        if identical else 'اعداد متفاوت ⇒ دو رویدادِ متمایز',
    )
    report['twin_layer_check'] = twin
    print('\n' + '=' * 100)
    print('### آزمونِ لایهٔ دوقلو — S955-H8 در برابرِ S1913-H8')
    print(f"  S955-H8 : {a}")
    print(f"  S1913-H8: {b}")
    print(f"  ⇒ {twin['verdict']}")
    print(f"    {twin['rule']}")

    # ---- جمع‌بندیِ قابلِ اجرا -------------------------------------------
    actions = []
    for card, rows in report['per_card'].items():
        for r in rows:
            if r['verdict'] == 'FALSE-WITNESS':
                actions.append(f"XAUUSD-{card}: S955 و «{r['vs']}» نباید هم‌زمان وصل باشند.")
            elif r['verdict'] == 'SUBSET-QUALITY-FILTER':
                actions.append(
                    f"XAUUSD-{card}: S955 زیرمجموعهٔ «{r['vs']}» است "
                    f"({r['share_of_s955_pct']}٪ · اندازه {r['size_parity']}) ⇒ "
                    f"جانشینی یا مرتبهٔ مقید لازم است، نه افزودنِ ساده.")
    if identical:
        actions.append('S1913 نباید به‌صورتِ لایهٔ جدا وصل شود — دوقلوی S955-H8 است.')
    report['actions'] = actions
    print('\n### اقدامِ الزامی')
    for x in actions:
        print('  ▸ ' + x)

    json.dump(report, open(OUT_FILE, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\nخروجی نوشته شد: {os.path.relpath(OUT_FILE, ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
