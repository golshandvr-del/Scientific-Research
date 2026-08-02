# -*- coding: utf-8 -*-
"""
S363 · پروتکل **P3-B — داوریِ کاملِ ۱۱-دروازه‌ایِ هندسهٔ مستقر**

پیش‌ثبت: ``results/S363_ADDENDUM_P3B_DEPLOYMENT_JUDGEMENT_PREREG.md``

این اسکریپت **هیچ جست‌وجویی ندارد**. نه گرید، نه انتخاب، نه رتبه‌بندی.
تنها کارش این است که پیکربندیِ **از پیش قفل‌شده** را از دو منبعِ کامیت‌شده
سرِهم کند و به موتورِ واقعیِ RQS2 بدهد:

  ① پارامترهای **سیگنال** ← ``ARCHIVE_CFG`` (پیش از این نشست قفل شده)
  ② پارامترهای **هندسه**  ← قانونِ کم‌ترین‌انحرافِ §۵ الحاقیهٔ P1
                             (``pick_deployment``، کامیتِ ``adf818d``،
                              پیش از اجرای اولین بک‌تستِ P1)

چرا این «انتخابِ پس‌رویدادی» نیست
---------------------------------
``pick_deployment`` یک مرتب‌سازیِ محضِ ساختاری است: ① `RR` کمینه ② نزدیک‌ترین
`sl_m` به آرشیو ③ نزدیک‌ترین `hold`. **هیچ عددِ عملکردی را نمی‌بیند.** خروجی‌اش
برای هر ۷ کارت در commitِ `adf818d` به‌صورت خشک چاپ شده بود، یعنی هر کسی
می‌توانست بدونِ اجرای یک خط بک‌تست آن را از قبل بگوید. پس درجهٔ آزادیِ این
پروتکل **صفر** است.

سه قیدِ سخت‌گیرانه‌ترِ §۱ پیش‌ثبت که اینجا اجرا می‌شوند
-----------------------------------------------------
1. **صورت‌حسابِ چندگانگی = نسخهٔ محافظه‌کارانهٔ قدیم.** `n_eff` از رکوردهای
   کامیت‌شدهٔ P0 خوانده می‌شود (`~5053`, یعنی `m_eff_signal × 15`)، **نه** از
   ضریبِ اصلاح‌شدهٔ `7.24`ِ P3-A. تخفیفِ P3-A عمداً خرج نمی‌شود؛ فقط به‌عنوان
   عددِ تشخیصی کنارش گزارش می‌شود. دلیل در §۱.۱ پیش‌ثبت.
2. **هر ۱۱ دروازه، هر ۳ بذر، `simulate_trades`ِ واقعیِ موتور.**
3. **بازخوانیِ `n_eff` به‌جای بازمحاسبه‌اش.** اگر دوباره اندازه بگیریم، یک
   درجهٔ آزادیِ نو باز می‌شود (نتیجه ممکن است ۰.۱ فرق کند و آن ۰.۱ می‌تواند
   حکم را بچرخاند). خواندن از دیسک ⇒ صورت‌حساب **بیت‌به‌بیت** همان است که در
   P0 روی همین کارت پرداخت شد.

نکتهٔ مهندسی
------------
به‌جای بازنویسیِ منطقِ داوری، ``run_card``ِ خودِ هارنسِ P0 با دو monkeypatch
فراخوانی می‌شود. این عمدی است: هر بازنویسی یک فرصتِ نوِ خطاست، و تنها چیزی که
باید بین P0 و P3-B فرق کند **هندسه** است. با استفاده از همان تابع، این ادعا
«با ساخت» درست است نه «با آزمون».
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import strategies.s363_s327_v24_rejudge as P0                            # noqa: E402
from strategies.s363_p1_legal_geometry import (                          # noqa: E402
    build_family, pick_deployment)

OUT = "results/_scan_S363"
ALL_CARDS = P0.SITE_CARDS + P0.ARCHIVE_ONLY_CARDS


# ═════════════ ۱. صورت‌حسابِ چندگانگیِ کامیت‌شدهٔ P0 (بازخوانی، نه بازمحاسبه) ═════════════
def p0_bill(card):
    """`n_eff`ِ همان کارت از رکوردِ کامیت‌شدهٔ P0 + عددِ تشخیصیِ اصلاح‌شدهٔ P3-A."""
    with open(os.path.join(OUT, f'P0_{card}.json')) as f:
        p0 = json.load(f)
    neff = p0['neff']
    n_eff_old = float(neff['n_eff'])                 # m_eff_signal × 15
    m_sig = float(neff['m_eff_signal'])
    corrected = None
    p3a_path = os.path.join(OUT, f'P3A_{card}.json')
    if os.path.exists(p3a_path):
        with open(p3a_path) as f:
            corrected = m_sig * float(json.load(f)['m_eff_bracket'])
    return n_eff_old, corrected, m_sig


# ═════════════════════════ ۲. اجرا برای یک کارت ═════════════════════════
def run(card, family, verbose=True):
    archive = P0.ARCHIVE_CFG[card]
    dep = pick_deployment(family, archive)

    # پیکربندیِ مستقر = سیگنالِ آرشیو + هندسهٔ قانونیِ ساختاری
    cfg = dict(archive)
    cfg['sl_m'] = dep['sl_m']
    cfg['tp_m'] = dep['tp_m']
    cfg['hold'] = dep['hold']

    n_eff_old, n_eff_corr, m_sig = p0_bill(card)

    if verbose:
        print(f"\n{'='*96}")
        print(f"=== {card} :: P3-B")
        print(f"    signal  (frozen, archive): "
              f"k_body={archive['k_body']} br_min={archive['br_min']} "
              f"streak={archive['streak_n']} rsi={archive['rsi_lo']} "
              f"regime={archive['regime']}")
        print(f"    geometry(frozen, min-perturbation rule, commit adf818d): "
              f"sl={cfg['sl_m']} tp={cfg['tp_m']} RR={dep['rr']} hold={cfg['hold']}")
        print(f"    archive geometry was      : "
              f"sl={archive['sl_m']} tp={archive['tp_m']} "
              f"RR={archive['tp_m']/archive['sl_m']:.4f} hold={archive['hold']}")
        print(f"    multiplicity bill USED    : n_eff={n_eff_old:.1f} "
              f"(conservative P0 bill, bracket×15)")
        if n_eff_corr:
            print(f"    (diagnostic only, NOT used: P3-A corrected bill "
                  f"= {n_eff_corr:.1f})")

    # ── monkeypatch ①: هندسهٔ مستقر جای هندسهٔ آرشیو ──
    saved_cfg = P0.ARCHIVE_CFG[card]
    P0.ARCHIVE_CFG[card] = cfg
    # ── monkeypatch ②: `n_eff` خوانده می‌شود، بازمحاسبه نمی‌شود ──
    saved_neff = P0.measure_neff
    P0.measure_neff = lambda feat, asset, verbose=True: (
        n_eff_old, m_sig, P0.N_SIGNAL_COLUMNS, P0.N_SIGNAL_COLUMNS)
    try:
        rec = P0.run_card(card, do_neff=True, verbose=verbose)
    finally:
        P0.ARCHIVE_CFG[card] = saved_cfg
        P0.measure_neff = saved_neff

    rec['protocol'] = 'P3-B'
    rec['prereg'] = 'results/S363_ADDENDUM_P3B_DEPLOYMENT_JUDGEMENT_PREREG.md'
    rec['geometry_source'] = 'P1 §5 min-perturbation rule (commit adf818d)'
    rec['archive_geometry'] = dict(sl_m=archive['sl_m'], tp_m=archive['tp_m'],
                                   hold=archive['hold'],
                                   rr=round(archive['tp_m'] / archive['sl_m'], 4))
    rec['bill'] = dict(used=n_eff_old, used_label='conservative P0 (bracket×15)',
                       p3a_corrected_diagnostic_only=n_eff_corr,
                       note='P3-A discount deliberately NOT spent — see prereg §1.1')

    path = os.path.join(OUT, f'P3B_{card}.json')
    with open(path, 'w') as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    if verbose:
        h = rec.get('honest') or {}
        print(f"  → saved {path}  status={rec.get('status')} "
              f"decision={h.get('decision')}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default=','.join(ALL_CARDS))
    a = ap.parse_args()
    cards = [c.strip() for c in a.cards.split(',') if c.strip()]

    print(f"{'='*96}")
    print("S363 · P3-B — full 11-gate judgement of the PRE-FROZEN deployment geometry")
    print(f"  prereg   : results/S363_ADDENDUM_P3B_DEPLOYMENT_JUDGEMENT_PREREG.md")
    print(f"  bill     : conservative P0 (bracket×15) — P3-A discount NOT spent")
    print(f"  search   : NONE. zero degrees of freedom.")
    print(f"{'='*96}")

    family, dropped = build_family()
    print(f"  legal family = {len(family)} members ({len(dropped)} unreachable dropped)")

    os.makedirs(OUT, exist_ok=True)
    summary = []
    for c in cards:
        try:
            rec = run(c, family)
        except Exception as exc:                      # noqa: BLE001
            print(f"  !! {c}: {type(exc).__name__}: {exc}", flush=True)
            continue
        h = rec.get('honest') or {}
        s23 = (rec.get('seeds') or {}).get('23', {}).get('neff', {})
        gates = s23.get('gates') or {}
        summary.append(dict(
            card=c, status=rec.get('status'), decision=h.get('decision'),
            score=s23.get('score'), verdict=s23.get('verdict'),
            failing=[g for g, v in gates.items() if v is not True],
            n=rec.get('n_trades'), wr=rec.get('wr_obs'),
            z_obs=(s23.get('metrics') or {}).get('z_obs'),
            z_bound=(s23.get('metrics') or {}).get('z_luck_bound')))

    print(f"\n{'='*96}")
    print("P3-B SUMMARY")
    print(f"{'card':13s}{'n':>5}{'WR':>8}{'z_obs':>8}{'z_bar':>8}{'score':>7}  failing")
    for r in summary:
        z = r['z_obs'] if r['z_obs'] is not None else float('nan')
        zb = r['z_bound'] if r['z_bound'] is not None else float('nan')
        print(f"{r['card']:13s}{r['n'] or 0:5d}{r['wr'] or 0:8.2f}{z:8.2f}{zb:8.2f}"
              f"{r['score'] or 0:7.1f}  {','.join(r['failing']) or 'NONE — ALL GATES PASS'}")

    alive = [r['card'] for r in summary if r['decision'] == 'ALIVE']
    print(f"\n  ALIVE cards: {alive or 'none'}")
    print(f"  prediction P3B-6 (no card passes all 11): "
          f"{'CONFIRMED' if not alive else 'FALSIFIED — layer survives'}")

    with open(os.path.join(OUT, 'P3B_SUMMARY.json'), 'w') as f:
        json.dump(dict(protocol='P3-B', summary=summary, alive=alive), f,
                  indent=1, ensure_ascii=False)
    print(f"→ saved {OUT}/P3B_SUMMARY.json")


if __name__ == '__main__':
    main()
