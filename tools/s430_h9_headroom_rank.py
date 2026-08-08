#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S430b — بازرتبه‌بندیِ کلِ بایگانی بر اساسِ **حاشیهٔ H9**
================================================================================
> این ابزار محصولِ *علمیِ* شکستِ `S430` است، نه یک اسکریپتِ کمکی.

درسِ `S430` (فایلِ `results/S430_SessionDriftCostGeometry_Eurusd_M15_rqs2_0_REJECT.md`):
نامزدِ احیا را با `z` انتخاب کردم — و شکست خوردم. `S73` با `z = ۱۱.۳۲σ`
(رکوردِ پروژه) هم نتوانست از `H9` بگذرد، چون:

    شرطِ H9  ⇔  امیدِ خام (pip)  >  ۲ × هزینهٔ کاملِ رفت‌وبرگشت

`z` می‌گوید «لبه **واقعی** است» (یعنی شانسی نیست). ولی `H9` می‌پرسد
«لبه **بزرگ** است؟» (یعنی از هزینه رد می‌شود؟). این دو **مستقل**‌اند:
`S73` یک لبهٔ حقیقیِ ۱.۲ pip داشت در کارتی که سدش ۱.۶ pip بود ⇒ محکوم.

پس معیارِ درستِ رتبه‌بندیِ نامزدهای احیا این است:

    حاشیهٔ H9  =  امیدِ خام  −  ۲ × هزینه

• حاشیهٔ **مثبت** ⇒ لایه از قبل توانِ عبور از H9 را دارد؛ اگر رد شده، گناهش
  جای دیگری است (آماری/رژیمی) و **آن نقص‌ها با فیلتر درمان‌پذیرند**.
• حاشیهٔ **منفی** ⇒ هیچ فیلتر و هیچ هندسه‌ای نجاتش نمی‌دهد مگر لبهٔ خام را
  بزرگ کند. `S430` اثباتِ تجربیِ همین بند است (کمبودِ ۳۲٪ ⇒ مرگِ ابدی).

⚠️ نکتهٔ صداقت: هزینه از **همان** جدولِ `engine/scalp_engine.ASSETS` خوانده
می‌شود که موتورِ داوری با آن حساب می‌کند — نه یک عددِ خوش‌بینانهٔ دستی.
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se   # noqa: E402

VERDICT_DIR = os.path.join(ROOT, 'results', '_audit_rename', 'verdicts')
OUT_DIR = os.path.join(ROOT, 'results', '_s430_headroom')

# دروازه‌هایی که با **فیلتر/رژیم** قابلِ درمان‌اند (اگر بودجهٔ pip موجود باشد)
FILTERABLE = {'H3', 'H5', 'H7', 'H10', 'H4', 'H6'}
# دروازه‌هایی که نشانهٔ نقصِ ساختاری‌اند (فیلتر درمانشان نمی‌کند)
STRUCTURAL = {'H2', 'H8', 'H9', 'H0', 'H1'}


def full_cost_pip(asset: str) -> float:
    """هزینهٔ کاملِ رفت‌وبرگشت بر حسبِ pip — دقیقاً تعریفی که `H9` می‌سنجد."""
    cfg = se.ASSETS.get(asset)
    if cfg is None:
        return float('nan')
    return float(cfg['spread_pip']) + 2.0 * float(cfg['slip_pip'])


def layer_id(d: dict) -> str:
    """نامِ لایه — دو فایلِ بایگانی کلیدِ `layer_file` دارند نه `layer`.

    این تفاوت باید **مدیریت** شود نه نادیده گرفته: پرشِ روی این دو فایل،
    دو لایه را از سرشماری حذف می‌کرد و سرشماریِ ناقص بی‌ارزش است.
    """
    raw = d.get('layer') or d.get('layer_file') or '?'
    return str(raw).split('_')[0]


def collect():
    rows = []
    files = sorted(glob.glob(os.path.join(VERDICT_DIR, '*.json')))
    for fp in files:
        with open(fp, encoding='utf-8') as fh:
            d = json.load(fh)
        lay = layer_id(d)
        n_trials = d.get('n_trials')
        for c in d.get('cards', []) or []:
            m = c.get('metrics') or {}
            g = c.get('gates') or {}
            asset = c.get('asset')
            e = m.get('expectancy_pip')
            n = m.get('n_trades')
            if e is None or n is None or asset not in se.ASSETS:
                continue
            cost2 = 2.0 * full_cost_pip(asset)
            failed = sorted([k for k, v in g.items() if v is False])
            rows.append(dict(
                layer=lay, card=c.get('card'), asset=asset, n=int(n),
                exp=float(e), cost2=cost2, headroom=float(e) - cost2,
                wr=m.get('win_rate'), pf=m.get('profit_factor'),
                z=m.get('skill_z'), lift=m.get('skill_lift_pp'),
                sl=m.get('sl_pip'), tp=m.get('tp_pip'),
                verdict=c.get('verdict'), score=c.get('rqs2_score'),
                failed=failed,
                only_filterable=bool(failed) and all(f in FILTERABLE for f in failed),
                struct_fail=sorted(set(failed) & STRUCTURAL),
                n_trials=n_trials))
    return rows, len(files)


def main():
    rows, nfiles = collect()
    print(f'== بازرتبه‌بندیِ حاشیهٔ H9 — {nfiles} فایلِ حکم · '
          f'{len(rows)} جفتِ (لایه×کارت) با متریکِ کامل ==')

    pos = [r for r in rows if r['headroom'] > 0]
    print(f'\nجفت‌های با حاشیهٔ **مثبت** (بودجهٔ pip دارند): {len(pos)} از {len(rows)}'
          f'  ({100.0*len(pos)/max(len(rows),1):.1f}%)')

    # ⭐ طلای واقعی: حاشیهٔ مثبت + نقص‌ها همه درمان‌پذیر با فیلتر
    gold = [r for r in pos if r['only_filterable']]
    gold.sort(key=lambda r: -r['headroom'])

    hdr = (f'{"layer":7} {"card":14} {"n":>6} {"exp":>8} {"2c":>5} '
           f'{"HEAD":>8} {"WR":>6} {"PF":>6} {"z":>6} {"lift":>6} '
           f'{"verdict":13} failed')

    def fmt(r):
        f = lambda v, w, p=2: ('?'.rjust(w) if v is None else f'{v:{w}.{p}f}')
        return (f"{r['layer']:7} {str(r['card']):14} {r['n']:6} "
                f"{r['exp']:+8.3f} {r['cost2']:5.1f} {r['headroom']:+8.3f} "
                f"{f(r['wr'],6)} {f(r['pf'],6,3)} {f(r['z'],6)} {f(r['lift'],6)} "
                f"{str(r['verdict']):13} {','.join(r['failed']) or '-'}")

    print('\n=== ⭐ طبقهٔ طلایی: حاشیهٔ H9 مثبت **و** فقط نقصِ درمان‌پذیر ===')
    print('  (این‌ها بودجهٔ اقتصادی دارند و نقصشان با فیلتر/رژیم برطرف می‌شود)')
    print(hdr)
    for r in gold[:40]:
        print(fmt(r))
    if not gold:
        print('  (خالی)')

    print('\n=== حاشیهٔ مثبت ولی نقصِ ساختاری (فیلتر کافی نیست) ===')
    hard = [r for r in pos if not r['only_filterable']]
    hard.sort(key=lambda r: -r['headroom'])
    print(hdr)
    for r in hard[:25]:
        print(fmt(r))

    # درسِ S430 به‌صورتِ عدد: S73 کجای این رتبه‌بندی می‌نشیند؟
    print('\n=== جایگاهِ نامزدِ شکست‌خوردهٔ S430 (اعتبارسنجیِ خودِ معیار) ===')
    print(hdr)
    for r in rows:
        if r['layer'] == 'S73':
            print(fmt(r))

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'headroom_rank.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(dict(n_files=nfiles, n_rows=len(rows),
                       n_positive=len(pos), gold=gold, hard=hard[:50]),
                  fh, ensure_ascii=False, indent=1)
    print(f'\n[saved] {os.path.relpath(out, ROOT)}')


if __name__ == '__main__':
    main()
