# -*- coding: utf-8 -*-
"""S386 گامِ ۱ — **ماتریسِ همپوشانیِ زوجیِ نامزدهای راهِ ۲.**

پرسشِ این ابزار (و تنها همین پرسش):
    ۹۱ نامزدی که آرشیوِ ۲۳٬۷۵۵ آزمونی بیرون داد، **چند لبهٔ مستقل‌اند؟**

چرا این پرسش پیش از هر چیزِ دیگری می‌آید:
    تجمیعِ پرتفوی (راهِ ۲) فقط با لایه‌های **مستقل** کار می‌کند. اگر پنج
    نامزد روی همان کارت، همان جهت و همان کندل‌ها سیگنال بدهند، نرخشان جمع
    نمی‌شود — پنج نام برای یک لایه‌اند. پس پیش از اجرای rqs2 روی هر نامزد
    (که گران است) باید استقلال سنجیده شود (که ارزان است).

روشِ اندازه‌گیریِ همپوشانی — و چرا این روش:
    همپوشانی روی **کندلِ ورود** سنجیده می‌شود، نه روی نتیجهٔ معامله. دلیل:
    دو قاعده که در همان کندل وارد می‌شوند، دقیقاً همان معامله را می‌گیرند
    (چون هندسهٔ SL/TP از ATR همان کارت می‌آید)، پس نتیجه‌شان الزاماً یکی است
    و مقایسهٔ نتیجه اطلاعِ نو نمی‌دهد.

    شاخصِ همپوشانی = **ژاکارد** روی مجموعهٔ کندل‌های ورود:
        J(A,B) = |A ∩ B| / |A ∪ B|
    و شاخصِ نامتقارنِ «پوشش»:
        C(A→B) = |A ∩ B| / |A|
    هر دو گزارش می‌شوند، چون J کوچک می‌ماند وقتی یک قاعده بسیار پرنرخ‌تر از
    دیگری است، در حالی که C نشان می‌دهد قاعدهٔ کوچک‌تر کاملاً داخلِ بزرگ‌تر
    است یا نه. قانونِ همپوشانیِ پروژه به «چند درصد» نیاز دارد و C همان است.

پنجرهٔ تحملِ همزمانی:
    دو ورود در کندل‌های *مجاور* عملاً همان معامله‌اند (قیمت تقریباً یکی).
    پس علاوه بر تطبیقِ دقیق، تطبیق با تحملِ ±TOL کندل هم گزارش می‌شود.

صفر پارامترِ قابلِ تنظیم برای بهتر کردنِ نتیجه ⇒ غیرقابلِ تقلب.
"""

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATA = 'data'
ARCH = 'results/_step2_rawedge'
OUT = 'results/_s386'
os.makedirs(OUT, exist_ok=True)

# دروازه‌های نامزدی — عیناً همان دو عددِ پیش‌ثبتِ S386
MIN_N = 300
MIN_LIFT = 5.0

# تحملِ همزمانی (کندل). ۱ یعنی ورودهای فاصلهٔ ۱ کندلی هم «همان» شمرده شوند.
TOL = 1


def load_rule_bank():
    spec = importlib.util.spec_from_file_location(
        'step1_rule_bank',
        os.path.join(ROOT, 'tools', 'step1_rule_bank.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def candidates_for(card):
    """نامزدهای یک کارت را از آرشیو بیرون می‌کشد (صفر محاسبهٔ نو)."""
    p = os.path.join(ARCH, f'{card}.json')
    if not os.path.exists(p):
        return []
    d = json.load(open(p))
    rows = [r for r in d['rows'] if r['n'] >= MIN_N and r['lift'] >= MIN_LIFT]
    return rows


def jaccard(a, b):
    inter = len(a & b)
    union = len(a | b)
    return (inter / union) if union else 0.0, inter


def dilate(idx, tol):
    """مجموعهٔ اندیس را به اندازهٔ ±tol پهن می‌کند."""
    if tol <= 0:
        return set(idx)
    out = set()
    for i in idx:
        for d in range(-tol, tol + 1):
            out.add(i + d)
    return out


def main():
    cards = sys.argv[1:] or ['XAUUSD_H4']
    RB = load_rule_bank()
    rules = RB.build_rules()
    rule_map = {name: fn for name, fn in rules}

    for card in cards:
        cands = candidates_for(card)
        if not cands:
            print(f'{card}: no candidates')
            continue

        # نامِ یکتای قواعد (چند هندسهٔ متفاوت روی همان قاعده = همان کندل‌ها)
        uniq_rules = sorted({r['rule'] for r in cands})
        print(f'\n=== {card} ===')
        print(f'candidate rows: {len(cands)}  |  distinct rules: {len(uniq_rules)}')

        df = RB.load(card)
        sig = {}
        for rn in uniq_rules:
            fn = rule_map.get(rn)
            if fn is None:
                print(f'  !! rule not in bank: {rn}')
                continue
            s = np.asarray(fn(df), dtype=bool)
            sig[rn] = set(np.flatnonzero(s).tolist())

        names = sorted(sig.keys())
        print(f'signals materialised for {len(names)} rules')
        print()
        print('%-26s %7s %8s' % ('rule', 'n_sig', '/yr'))
        span = json.load(open(os.path.join(ARCH, f'{card}.json')))['span_years']
        for n in names:
            print('%-26s %7d %8.1f' % (n, len(sig[n]), len(sig[n]) / span))

        # ماتریسِ همپوشانی
        rec = {'card': card, 'span_years': span, 'tol': TOL,
               'min_n': MIN_N, 'min_lift': MIN_LIFT,
               'n_candidate_rows': len(cands),
               'n_distinct_rules': len(names),
               'rules': {n: {'n_sig': len(sig[n]),
                             'per_year': round(len(sig[n]) / span, 1)}
                         for n in names},
               'pairs': []}

        dil = {n: dilate(sig[n], TOL) for n in names}
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                j, inter = jaccard(sig[a], sig[b])
                ca = inter / len(sig[a]) if sig[a] else 0.0
                cb = inter / len(sig[b]) if sig[b] else 0.0
                jt, intert = jaccard(dil[a], dil[b])
                cat = intert / len(dil[a]) if dil[a] else 0.0
                cbt = intert / len(dil[b]) if dil[b] else 0.0
                rec['pairs'].append({
                    'a': a, 'b': b,
                    'jaccard': round(j, 4), 'inter': inter,
                    'cover_a': round(ca, 4), 'cover_b': round(cb, 4),
                    'jaccard_tol': round(jt, 4),
                    'cover_a_tol': round(cat, 4), 'cover_b_tol': round(cbt, 4),
                })

        js = [p['jaccard'] for p in rec['pairs']]
        cvs = [max(p['cover_a'], p['cover_b']) for p in rec['pairs']]
        jts = [p['jaccard_tol'] for p in rec['pairs']]
        rec['summary'] = {
            'n_pairs': len(rec['pairs']),
            'jaccard_mean': round(float(np.mean(js)), 4) if js else None,
            'jaccard_max': round(float(np.max(js)), 4) if js else None,
            'jaccard_median': round(float(np.median(js)), 4) if js else None,
            'cover_max_mean': round(float(np.mean(cvs)), 4) if cvs else None,
            'cover_max_max': round(float(np.max(cvs)), 4) if cvs else None,
            'jaccard_tol_mean': round(float(np.mean(jts)), 4) if jts else None,
            'pairs_j_over_50': sum(1 for x in js if x > 0.50),
            'pairs_cover_over_50': sum(1 for x in cvs if x > 0.50),
            'pairs_cover_over_70': sum(1 for x in cvs if x > 0.70),
            'pairs_j_under_10': sum(1 for x in js if x < 0.10),
        }

        print()
        print('--- overlap summary ---')
        for k, v in rec['summary'].items():
            print(f'  {k:24s} {v}')

        with open(os.path.join(OUT, f'{card}_overlap.json'), 'w') as f:
            json.dump(rec, f, indent=1)
        print(f'\nwrote {OUT}/{card}_overlap.json')


if __name__ == '__main__':
    main()
