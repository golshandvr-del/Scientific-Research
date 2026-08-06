# -*- coding: utf-8 -*-
"""
گامِ ۰ از ماموریتِ ممیزی — **شناسنامه‌برداری** از هر فایلِ لایه در `results/`
================================================================================
این اسکریپت هیچ حکمی صادر نمی‌کند. تنها کاری که می‌کند این است که برای هر فایلِ
لایه بگوید «چه چیزی از آن *قابلِ* داوری با RQS2 هست؟» — چون RQS2 بدونِ هندسه
(`sl_pip`/`tp_pip`) و بدونِ (`WR`,`n`) حتی نمی‌تواند دروازهٔ حسابیِ `H2` را بسنجد.

چرا این گام لازم است (و چرا نمی‌شود از آن پرید):
  اسپک صریح است: «نبودِ آزمونِ کنترل، شاهدِ وجودِ مهارت نیست» ⇒ هر دروازه‌ای که
  داده‌اش نباشد `UNKNOWN` و حکم `INCOMPLETE` است، **نه** ACCEPT. پس تفکیکِ
  «داده دارد» از «داده ندارد» خودش بخشی از حکم است، نه کارِ مقدماتی.

طرزِ تفکیکِ فایلِ لایه از فایلِ سند:
  فایل‌هایی با نشانگرهای PREREG/FINDING/LAW/AUDIT/... سندِ روش‌شناسی‌اند و لایه
  تعریف نمی‌کنند ⇒ نامشان عوض نمی‌شود (ماموریت فقط لایه‌ها را می‌خواهد).
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')

DOC_MARKERS = ('PREREG', 'FINDING', '_LAW', 'LAW_', 'AUDIT', 'ADDENDUM',
               'RESULT_', 'STEP1', 'DataExplore', 'DISCOVERY', 'CONFIRMED',
               'SELF_AUDIT', 'REFUTED', 'TRIAGE', 'CENSUS', 'NOTEBOOK',
               'METHODOLOGY', 'PROTOCOL', 'BRIEF', 'SPEC')

# اعدادِ فارسی/عربی → لاتین، چون کلِ مستنداتِ پروژه فارسی‌نویس است
FA = {ord(c): str(i) for i, c in enumerate('۰۱۲۳۴۵۶۷۸۹')}
FA.update({ord(c): str(i) for i, c in enumerate('٠١٢٣٤٥٦٧٨٩')})

PAIRS = ('XAUUSD', 'EURUSD', 'AUDUSD', 'USDCHF', 'DXY')
TFS = ('M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1')


def norm(s: str) -> str:
    return s.translate(FA)


def is_doc(fn: str) -> bool:
    return any(m in fn for m in DOC_MARKERS)


def scan(path: str) -> dict:
    txt = norm(open(path, encoding='utf-8').read())
    out = {}
    # WR — درصدِ برد، هر شکلی که در مستندات نوشته شده
    wr = re.findall(r'(?:WR|Win[- ]?Rate|وین[ ‌]?ریت)\s*[:=|]?\s*≈?\s*([0-9]{1,2}\.?[0-9]*)\s*٪?%?', txt)
    if wr:
        out['wr_candidates'] = sorted({float(x) for x in wr if 5 <= float(x) <= 99})
    # n — تعدادِ معامله
    nn = re.findall(r'(?:n\s*=\s*|تعداد\s*معامله\s*\|?\s*)([0-9]{2,6})', txt)
    if nn:
        out['n_candidates'] = sorted({int(x) for x in nn if 10 <= int(x) <= 500000})
    # هندسه
    sl = re.findall(r'SL\s*[:=|]?\s*(?:ثابت\s*)?([0-9]+\.?[0-9]*)\s*pip', txt)
    tp = re.findall(r'TP\s*[:=|]?\s*(?:ثابت\s*)?([0-9]+\.?[0-9]*)\s*pip', txt)
    if sl:
        out['sl_pip_candidates'] = sorted({float(x) for x in sl})
    if tp:
        out['tp_pip_candidates'] = sorted({float(x) for x in tp})
    pf = re.findall(r'PF\s*[:=|]?\s*≈?\s*([0-9]\.[0-9]+)', txt)
    if pf:
        out['pf_candidates'] = sorted({float(x) for x in pf})
    out['pairs'] = [p for p in PAIRS if p in txt.upper()]
    out['tfs'] = [t for t in TFS if re.search(r'\b' + t + r'\b', txt)]
    out['lines'] = txt.count('\n') + 1
    return out


def main():
    rows = []
    for fn in sorted(os.listdir(RES)):
        if not fn.endswith('.md') or not re.match(r'^S\d', fn):
            continue
        rec = {'file': fn, 'kind': 'DOC' if is_doc(fn) else 'LAYER'}
        if rec['kind'] == 'LAYER':
            rec.update(scan(os.path.join(RES, fn)))
        rows.append(rec)
    layers = [r for r in rows if r['kind'] == 'LAYER']
    have_geom = [r for r in layers if r.get('sl_pip_candidates') and r.get('tp_pip_candidates')]
    have_wr = [r for r in layers if r.get('wr_candidates')]
    print(f"total S-files        : {len(rows)}")
    print(f"  DOC (not renamed)  : {len(rows) - len(layers)}")
    print(f"  LAYER (to audit)   : {len(layers)}")
    print(f"    with WR archived : {len(have_wr)}")
    print(f"    with pip geometry: {len(have_geom)}")
    os.makedirs(os.path.join(RES, '_audit_rename'), exist_ok=True)
    p = os.path.join(RES, '_audit_rename', 'scan.json')
    json.dump(rows, open(p, 'w'), ensure_ascii=False, indent=1)
    print(f"written -> {p}")


if __name__ == '__main__':
    main()
