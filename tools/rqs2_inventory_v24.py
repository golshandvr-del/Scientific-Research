#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ابزارِ سرشماریِ کاملِ «هر حکمی که تا امروز با معیارِ RQS2 صادر شده»
=================================================================

پرسشِ کاربر: «چند لایه با معیارِ RQS2 (نه RQS+) بررسی شده‌اند؟ جدول بساز و با
معیارِ اصلاح‌شدهٔ v2.4 دوباره داوری کن.»

این ابزار **هیچ بک‌تستی اجرا نمی‌کند** و هیچ حکمی نمی‌سازد. کارش سه چیز است:

1. **سرشماری:** هر JSONِ زیرِ `results/` را می‌گردد و هر بلوکی را که یک حکمِ
   RQS2 است (یعنی `gates` با کلیدهای `H0..H10` دارد) استخراج می‌کند.

2. **تشخیصِ کهنگی (`staleness`):** هر رکورد را برحسبِ اینکه با کدام نسخهٔ موتور
   داوری شده برچسب می‌زند. امضاهای قابلِ اندازه‌گیری:
     - `perm_k < 500`            ⇒ زیرِ کفِ همگراییِ v2.4 ⇒ حکمِ `H3` **بی‌اعتبار**
     - نبودِ `skill_p_perm`      ⇒ موتور، p-valueِ جای‌گشتی نمی‌ساخت (پیش از v2.4)
     - نبودِ `counter_drift`     ⇒ موتور، آزمونِ جانشینِ F4 را نداشت (پیش از v2.4)
   این‌ها **حدس** نیستند؛ کلیدهایی‌اند که فقط v2.4 می‌نویسد.

3. **غربالِ «کاندیدای برگشت»:** رکوردی که **همهٔ** دروازه‌های موضوعی
   (`H0,H1,H2,H4,H5,H6,H7,H8,H9`) را پاس کرده و تنها روی `H3` و/یا `H10`
   افتاده است. فقط همین خانواده می‌تواند با اصلاحاتِ v2.4 برگردد، چون v2.4
   دقیقاً و فقط همین دو دروازه را عوض کرد. هر رکوردی که یک دروازهٔ موضوعی را
   شکسته باشد، اصلاحِ معیار هیچ کمکی به آن نمی‌کند — و **نباید** بکند.

اجرا:
    python3 tools/rqs2_inventory_v24.py            # جدول در stdout
    python3 tools/rqs2_inventory_v24.py --json out.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, OrderedDict

GATES = ['H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10']
# دروازه‌هایی که v2.4 **دست نزد** ⇒ شکست در هرکدام با اصلاحِ معیار برنمی‌گردد
SUBSTANTIVE = ['H0', 'H1', 'H2', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9']
# دروازه‌هایی که v2.4 عوض کرد
V24_TOUCHED = ['H3', 'H10']

PERM_K_MIN = 500


# ---------------------------------------------------------------- استخراج

def iter_verdicts(obj, path, fname, out):
    """هر زیر-دیکشنری‌ای که یک حکمِ RQS2 است را بازگردان."""
    if isinstance(obj, dict):
        g = obj.get('gates')
        if isinstance(g, dict) and 'H10' in g and 'H0' in g:
            out.append((fname, path or '/', obj))
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                iter_verdicts(v, f'{path}/{k}', fname, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (dict, list)):
                iter_verdicts(v, f'{path}[{i}]', fname, out)


def layer_of(fname):
    """شمارهٔ لایه را از مسیر بیرون بکش (`_scan_S351/...` ⇒ `S351`)."""
    m = re.search(r'_scan_(S\d+)', fname)
    if m:
        return m.group(1)
    m = re.search(r'(S\d{2,4})', os.path.basename(fname))
    return m.group(1) if m else '?'


def card_of(fname, rec):
    for k in ('card', 'cardId', 'card_id'):
        if isinstance(rec.get(k), str):
            return rec[k].replace('_', '-')
    base = os.path.basename(fname).replace('.json', '')
    m = re.search(r'(XAUUSD|EURUSD)[_-]([A-Z0-9]+)', base)
    return f'{m.group(1)}-{m.group(2)}' if m else base


def staleness(met):
    """با کدام نسخهٔ موتور داوری شده؟ (بر پایهٔ امضاهای کلیدی، نه حدس)"""
    reasons = []
    pk = met.get('perm_k')
    if pk is None:
        reasons.append('no-perm_k')
    elif pk < PERM_K_MIN:
        reasons.append(f'perm_k={pk}<{PERM_K_MIN}')
    if 'skill_p_perm' not in met:
        reasons.append('no-skill_p_perm')
    if 'counter_drift' not in met:
        reasons.append('no-counter_drift')
    return ('STALE' if reasons else 'V24'), reasons


def classify(rec):
    """کدام دروازه‌ها افتاده‌اند و آیا رکورد «کاندیدای برگشت» است؟"""
    g = rec.get('gates', {})
    failed = [k for k in GATES if g.get(k) is False]
    unknown = [k for k in GATES if g.get(k) is None]
    bad = failed + unknown
    subst_bad = [k for k in bad if k in SUBSTANTIVE]
    touched_bad = [k for k in bad if k in V24_TOUCHED]
    if not bad:
        cls = 'ALL_PASS'
    elif not subst_bad:
        cls = 'FLIP_CANDIDATE'      # فقط H3/H10 ⇒ تنها خانوادهٔ قابلِ برگشت
    else:
        cls = 'SUBSTANTIVE_FAIL'    # اصلاحِ معیار اینجا بی‌اثر است
    return cls, failed, unknown, subst_bad, touched_bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='results')
    ap.add_argument('--json', default='')
    ap.add_argument('--md', default='')
    args = ap.parse_args()

    raw = []
    for fn in sorted(glob.glob(os.path.join(args.root, '**', '*.json'), recursive=True)):
        try:
            with open(fn, encoding='utf-8') as fh:
                d = json.load(fh)
        except Exception:
            continue
        iter_verdicts(d, '', fn, raw)

    rows = []
    for fname, path, rec in raw:
        met = rec.get('metrics', {}) or {}
        stale, why = staleness(met)
        cls, failed, unknown, subst_bad, touched_bad = classify(rec)
        cd = met.get('counter_drift') or {}
        rows.append(OrderedDict(
            layer=layer_of(fname),
            card=card_of(fname, rec),
            file=fname,
            branch=path.strip('/').split('/')[0] or '-',
            verdict=rec.get('verdict'),
            score=rec.get('rqs2_score'),
            engine=stale,
            stale_why=';'.join(why),
            klass=cls,
            failed=','.join(failed),
            unknown=','.join(unknown),
            subst_bad=','.join(subst_bad),
            touched_bad=','.join(touched_bad),
            n=met.get('n_trades'),
            wr=met.get('win_rate'),
            pf=met.get('profit_factor'),
            lift=met.get('skill_lift_pp'),
            z=met.get('skill_z'),
            p_perm=met.get('skill_p_perm'),
            perm_k=met.get('perm_k'),
            perm_max=met.get('perm_max'),
            n_counter=cd.get('n_counter'),
            exp_counter=cd.get('exp_counter'),
            net=met.get('net_profit'),
        ))

    # ---------------------------------------------------------- خلاصه
    print(f'رکوردهای دارای حکمِ RQS2 : {len(rows)}')
    print('حکم‌ها                    :', dict(Counter(r['verdict'] for r in rows)))
    print('موتورِ داوری             :', dict(Counter(r['engine'] for r in rows)))
    print('طبقه‌بندی                :', dict(Counter(r['klass'] for r in rows)))
    print('لایه‌های متمایز           :', len({r['layer'] for r in rows}),
          sorted({r['layer'] for r in rows}))
    print('(لایه,کارت)ِ متمایز      :', len({(r['layer'], r['card']) for r in rows}))

    print('\n--- کاندیداهای برگشت (فقط H3/H10 افتاده) ---')
    cands = [r for r in rows if r['klass'] in ('FLIP_CANDIDATE', 'ALL_PASS')]
    cands.sort(key=lambda r: (-(r['n'] or 0)))
    hdr = f"{'layer':6s} {'card':13s} {'branch':12s} {'verdict':14s} {'eng':5s} " \
          f"{'bad':9s} {'n':>6s} {'wr':>6s} {'pf':>6s} {'lift':>6s} {'z':>5s} {'permk':>6s}"
    print(hdr)
    for r in cands:
        print(f"{r['layer']:6s} {r['card'][:13]:13s} {r['branch'][:12]:12s} "
              f"{str(r['verdict'])[:14]:14s} {r['engine']:5s} "
              f"{(r['touched_bad'] or '-'):9s} {str(r['n'] or ''):>6s} "
              f"{(f'{r_wr:.1f}' if (r_wr := r['wr']) is not None else ''):>6s} "
              f"{(f'{r_pf:.2f}' if (r_pf := r['pf']) is not None else ''):>6s} "
              f"{(f'{r_l:.1f}' if (r_l := r['lift']) is not None else ''):>6s} "
              f"{(f'{r_z:.2f}' if (r_z := r['z']) is not None else ''):>5s} "
              f"{str(r['perm_k'] or ''):>6s}")

    if args.json:
        os.makedirs(os.path.dirname(args.json) or '.', exist_ok=True)
        with open(args.json, 'w', encoding='utf-8') as fh:
            json.dump({'n_records': len(rows), 'rows': rows}, fh,
                      ensure_ascii=False, indent=1)
        print(f'\n[نوشته شد] {args.json}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
