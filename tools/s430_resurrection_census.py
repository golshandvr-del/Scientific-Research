#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S430 — فهرست‌برداریِ نامزدهای احیا (MISSION_4، گامِ ۱)
=======================================================

هدف: پاسخِ دقیق و اندازه‌گیری‌شده به «کدام لایهٔ ردشده، شانسِ واقعیِ احیا دارد؟»

منبعِ حقیقت: results/_audit_rename/verdicts/*.json  (۱۴۷ فایلِ حکم، ۱۸۱ لایه)
هر فایل شاملِ آرایهٔ cards[] است و هر کارت، هر ۱۱ دروازه + متریک‌های کاملِ v2.4 را دارد.

⚠️ قانونِ صداقتِ این اسکنر (از MISSION_4 بندِ «هشدارهای اختصاصی»):
   لایه‌ای که یک دروازهٔ «اقتصادی/ساختاری» را باخته (H1 PF، H2 هندسه، H8 ریسک،
   H9 هزینه) با هیچ فیلترِ رژیمی برنمی‌گردد — چون فیلتر فقط زیرمجموعه می‌گیرد و
   PF/RR را عوض نمی‌کند به‌طورِ تضمینی. اما دقیقاً همان‌جاست که یک استثنا وجود دارد:
   فیلتر *می‌تواند* PF را بالا ببرد اگر معاملاتِ بازنده را هدف بگیرد.
   پس دو طبقه می‌سازیم و به‌صراحت تفکیک می‌کنیم:

   TIER-A  «احیای رایگان»   : هر ۱۱ دروازه پاس ولی برچسبِ بایگانی ACCEPT نیست
                              (مصداقِ بازنشستگیِ کفِ ۸۰ در v2.3) ⇒ فقط بازداوری
   TIER-B  «تک‌نقص آماری»   : فقط H3 و/یا H10 و/یا H5 و/یا H7 افتاده و بقیه پاس
                              ⇒ فیلترِ رژیم/توان می‌تواند نجات دهد
   TIER-C  «تک‌نقصِ اقتصادی» : فقط یکی از H1/H2/H8/H9 افتاده و بقیه پاس
                              ⇒ نجات با هندسه (TP/SL شناور) نه فیلتر
   TIER-D  «چندنقص»        : ≥۲ دروازه افتاده ⇒ گران، آخرین اولویت

خروجی: results/_s430_census/candidates.json  +  جدولِ چاپی
"""
from __future__ import annotations
import json
import glob
import os
from collections import defaultdict

VERDICT_DIR = 'results/_audit_rename/verdicts'
OUT_DIR = 'results/_s430_census'

GATES = ['H0', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10']
# دروازه‌هایی که با «فیلترِ رژیم / توانِ آماری» قابلِ حمله‌اند
POWER_GATES = {'H3', 'H5', 'H7', 'H10'}
# دروازه‌هایی که با «هندسه / انتخابِ معامله» قابلِ حمله‌اند
ECON_GATES = {'H1', 'H2', 'H8', 'H9'}
# دروازه‌هایی که تقریباً غیرقابلِ حمله‌اند (کفایتِ نمونه و تقارنِ سمت)
HARD_GATES = {'H0', 'H4', 'H6'}


def classify(gates: dict) -> tuple[str, list[str]]:
    """طبقهٔ احیا + فهرستِ دروازه‌های افتاده."""
    failed = [g for g in GATES if gates.get(g) is False]
    unknown = [g for g in GATES if gates.get(g) is None]
    if not failed and not unknown:
        return 'TIER-A', failed
    fs = set(failed)
    if len(failed) == 0:
        return 'TIER-A', failed
    if fs <= POWER_GATES:
        return 'TIER-B', failed
    if fs <= ECON_GATES and len(failed) <= 2:
        return 'TIER-C', failed
    if len(failed) <= 2:
        return 'TIER-C', failed
    return 'TIER-D', failed


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(VERDICT_DIR, '*.json')))
    rows = []
    for fp in files:
        try:
            d = json.load(open(fp, encoding='utf-8'))
        except Exception as exc:                                    # pragma: no cover
            print(f'  ! unreadable {os.path.basename(fp)}: {exc}')
            continue
        layer = (d.get('layer') or os.path.basename(fp)).split('_')[0]
        script = d.get('script')
        for card in d.get('cards') or []:
            g = card.get('gates') or {}
            m = card.get('metrics') or {}
            tier, failed = classify(g)
            rows.append({
                'layer': layer,
                'script': script,
                'card': card.get('card'),
                'verdict': card.get('verdict'),
                'score': card.get('rqs2_score'),
                'tier': tier,
                'failed': failed,
                'n_fail': len(failed),
                'n': m.get('n_trades'),
                'wr': m.get('win_rate'),
                'pf': m.get('profit_factor'),
                'rr': m.get('rr'),
                'lift': m.get('skill_lift_pp'),
                'z': m.get('skill_z'),
                'p_perm': m.get('skill_p_perm'),
                'perm_k': m.get('perm_k'),
                'net': m.get('net_profit'),
                'wr_excess': m.get('wr_excess_cost'),
                'oos_n': (m.get('oos') or {}).get('n'),
                'oos_pf': (m.get('oos') or {}).get('pf'),
                'maxdd': m.get('max_dd_pct'),
                'exp_pip': m.get('expectancy_pip'),
                'z_obs': m.get('z_obs'),
                'z_bound': m.get('z_luck_bound'),
                'sl_pip': m.get('sl_pip'),
                'tp_pip': m.get('tp_pip'),
            })

    # ---------- خلاصهٔ طبقات ----------
    by_tier = defaultdict(list)
    for r in rows:
        by_tier[r['tier']].append(r)

    print(f'\n== سرشماریِ احیا: {len(files)} فایلِ حکم · {len(rows)} جفتِ (لایه×کارت) ==\n')
    for t in ('TIER-A', 'TIER-B', 'TIER-C', 'TIER-D'):
        print(f'  {t}: {len(by_tier[t])}')

    # ---------- هیستوگرامِ دروازه‌های افتاده ----------
    hist = defaultdict(int)
    for r in rows:
        for g in r['failed']:
            hist[g] += 1
    print('\n-- هیستوگرامِ شکست (روی همهٔ کارت‌ها) --')
    for g in GATES:
        print(f'  {g:4s}: {hist[g]}')

    # ---------- TIER-A: احیای رایگان ----------
    print('\n=== TIER-A — هر ۱۱ دروازه پاس (احیای رایگان) ===')
    ta = sorted(by_tier['TIER-A'], key=lambda r: -(r['n'] or 0))
    for r in ta:
        print(f"  {r['layer']:6s} {str(r['card']):14s} score={r['score']:6} "
              f"verdict={r['verdict']:12s} n={r['n']:6} wr={r['wr']} pf={r['pf']} "
              f"z={r['z']} p={r['p_perm']} K={r['perm_k']}")

    # ---------- TIER-B: تک/چندنقصِ آماری ----------
    print('\n=== TIER-B — فقط دروازه‌های آماری (H3/H5/H7/H10) افتاده ===')
    tb = sorted(by_tier['TIER-B'], key=lambda r: (r['n_fail'], -(r['n'] or 0)))
    for r in tb[:60]:
        print(f"  {r['layer']:6s} {str(r['card']):14s} fail={','.join(r['failed']):16s} "
              f"n={r['n']:6} wr={r['wr']} pf={r['pf']} rr={r['rr']} "
              f"lift={r['lift']} z={r['z']} p={r['p_perm']} K={r['perm_k']} "
              f"oosN={r['oos_n']} oosPF={r['oos_pf']}")

    # ---------- TIER-C ----------
    print('\n=== TIER-C — تک/دو نقصِ اقتصادی-هندسی ===')
    tc = sorted(by_tier['TIER-C'], key=lambda r: (r['n_fail'], -(r['n'] or 0)))
    for r in tc[:60]:
        print(f"  {r['layer']:6s} {str(r['card']):14s} fail={','.join(r['failed']):16s} "
              f"n={r['n']:6} wr={r['wr']} pf={r['pf']} rr={r['rr']} "
              f"sl={r['sl_pip']} tp={r['tp_pip']} z={r['z']} maxdd={r['maxdd']}")

    out = os.path.join(OUT_DIR, 'candidates.json')
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump({'n_files': len(files), 'n_cards': len(rows),
                   'gate_fail_hist': dict(hist), 'rows': rows},
                  fh, ensure_ascii=False, indent=1)
    print(f'\n[saved] {out}')


if __name__ == '__main__':
    main()
