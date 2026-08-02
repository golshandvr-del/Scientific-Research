# -*- coding: utf-8 -*-
"""
S363 · پروتکل **P3-C — فیلترِ نظریه‌محورِ نااستواریِ Amihud**

پیش‌ثبت: ``results/S363_ADDENDUM_P3C_AMIHUD_FILTER_PREREG.md``

این اسکریپت **هیچ جست‌وجویی ندارد** — نه گرید، نه رتبه‌بندی، نه انتخاب.
دقیقاً **یک** فیلتر را اعمال می‌کند که فرمول، جهت و آستانه‌اش در §۳ پیش‌ثبت
قفل شده‌اند، و نتیجه را به موتورِ واقعیِ ۱۱-دروازه‌ای می‌دهد.

نظریه (§۲ پیش‌ثبت)
------------------
Amihud (2002) · Da–Liu–Schaumburg (2011) · Lou–Shu (2016):

    نااستواری بالا  ⇒ حرکتِ قیمت از **خلأِ نقدشوندگی** آمده (اثرِ موقت) ⇒ برمی‌گردد
    نااستواری پایین ⇒ حرکتِ قیمت از **اطلاعات** آمده (اثرِ دائمی)      ⇒ برنمی‌گردد

S327 یک شرط‌بندی روی «بازگشت» است، پس فقط کندل‌های پرنااستوایی باید نگه داشته
شوند. **جهتِ `KEEP_HIGH` از نظریه می‌آید، نه از داده.**

فرمول — صفر پارامترِ آزاد
-------------------------
    ILLIQ_t     = |close_t − open_t| / volume_t
    ILLIQ_rel_t = ILLIQ_t / median_20(ILLIQ).shift(1)
    KEEP        ⟺ ILLIQ_rel_t > 1.0

* پنجرهٔ ۲۰ ← از `body_ma`/`bollinger`ِ خودِ S327 به ارث می‌رسد (عددِ نو نیست)
* `median` ← نااستواری توزیعِ چولهٔ سنگین دارد؛ `mean` را یک کندلِ کم‌حجم منفجر می‌کند
* آستانهٔ `1.0` ← «بالاتر از هنجارِ خودش»؛ تنها عددِ **بی‌مقیاسِ** ممکن
* `.shift(1)` ← هنجار فقط از کندل‌های **قبل**؛ صفرِ نگاه‌به‌جلو

نکتهٔ مهندسی
------------
مثلِ P3-B، منطقِ داوری **بازنویسی نمی‌شود**؛ همان ``run_card``ِ P0 با سه
monkeypatch فراخوانی می‌شود. تنها چیزی که نسبت به P3-B فرق می‌کند **یک `AND`
روی بردارِ سیگنال** است. با این کار، هر تفاوتِ عددی بینِ P3-B و P3-C
**فقط و فقط** می‌تواند از فیلتر آمده باشد.

مدلِ صفر خودبه‌خود روی شمارشِ **فیلترشده** بازساخته می‌شود، چون ``run_card``
تعدادِ ورودهای تصادفیِ جای‌گشت را از ``n_sig``ِ همان اجرا می‌گیرد. این حیاتی
است: مقایسهٔ WRِ فیلترشده با نولی که روی شمارشِ فیلترنشده ساخته شده باشد،
یک لیفتِ ساختگی می‌سازد.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                    # noqa: E402
import strategies.s363_s327_v24_rejudge as P0                            # noqa: E402
from strategies.s363_p1_legal_geometry import (                          # noqa: E402
    build_family, pick_deployment)

OUT = "results/_scan_S363"
ALL_CARDS = P0.SITE_CARDS + P0.ARCHIVE_ONLY_CARDS

# ═══════════ ثابت‌های قفل‌شدهٔ §۳ پیش‌ثبت — تغییرناپذیر ═══════════
ILLIQ_WINDOW = 20          # به ارث رسیده از body_ma/bollinger خودِ S327
ILLIQ_THRESHOLD = 1.0      # بی‌مقیاس: «بالاتر از میانهٔ خودش»
ILLIQ_DIRECTION = 'KEEP_HIGH'   # 🔒 از نظریه، نه از داده


# ═════════════════════ ۱. سنجهٔ Amihud (قفل‌شده) ═════════════════════
def amihud_keep_mask(df):
    """ماسکِ `KEEP` طبق §۳ پیش‌ثبت. هیچ پارامترِ تنظیم‌پذیری ندارد.

    برمی‌گرداند: (mask, rel) که `rel` برای گزارشِ تشخیصی است.
    """
    o = df['open'].to_numpy(float)
    c = df['close'].to_numpy(float)
    v = df['volume'].to_numpy(float)

    # نااستواریِ خام. حجمِ صفر ⇒ نامعتبر (نه بی‌نهایت): در داده‌های ما ۰٪ است
    # ولی این محافظ باید باشد تا یک کندلِ خرابِ احتمالی کلِ فیلتر را نچرخاند.
    with np.errstate(divide='ignore', invalid='ignore'):
        illiq = np.where(v > 0, np.abs(c - o) / v, np.nan)

    s = pd.Series(illiq)
    # هنجارِ اخیر: میانهٔ ۲۰ کندلِ **قبل** (shift(1) ⇒ خودِ کندل داخل نیست)
    norm = s.rolling(ILLIQ_WINDOW).median().shift(1).to_numpy()

    with np.errstate(divide='ignore', invalid='ignore'):
        rel = np.where(np.isfinite(norm) & (norm > 0), illiq / norm, np.nan)

    keep = np.isfinite(rel) & (rel > ILLIQ_THRESHOLD)
    return keep, rel


# ═════════════ ۲. صورت‌حسابِ کامیت‌شدهٔ P0 (بازخوانی، نه بازمحاسبه) ═════════════
def p0_bill(card):
    with open(os.path.join(OUT, f'P0_{card}.json')) as f:
        p0 = json.load(f)
    neff = p0['neff']
    n_eff_old = float(neff['n_eff'])
    m_sig = float(neff['m_eff_signal'])
    corrected = None
    p3a = os.path.join(OUT, f'P3A_{card}.json')
    if os.path.exists(p3a):
        with open(p3a) as f:
            corrected = m_sig * float(json.load(f)['m_eff_bracket'])
    return n_eff_old, corrected, m_sig


# ═════════════════════════ ۳. اجرا برای یک کارت ═════════════════════════
def run(card, family, verbose=True):
    asset, tf = card.split('-')
    archive = P0.ARCHIVE_CFG[card]
    dep = pick_deployment(family, archive)

    cfg = dict(archive)
    cfg['sl_m'], cfg['tp_m'], cfg['hold'] = dep['sl_m'], dep['tp_m'], dep['hold']

    n_eff_old, n_eff_corr, m_sig = p0_bill(card)

    # ماسکِ فیلتر را **یک‌بار** می‌سازیم (روی همان df که run_card می‌خواند)
    df = se.load_data(os.path.join('data', f'{asset}_{tf}.csv'))
    keep_mask, rel = amihud_keep_mask(df)

    if verbose:
        print(f"\n{'='*96}")
        print(f"=== {card} :: P3-C  (Amihud illiquidity filter)")
        print(f"    signal   (frozen, archive): k_body={archive['k_body']} "
              f"br_min={archive['br_min']} streak={archive['streak_n']} "
              f"rsi={archive['rsi_lo']} regime={archive['regime']}")
        print(f"    geometry (frozen, P1 §5)  : sl={cfg['sl_m']} tp={cfg['tp_m']} "
              f"RR={dep['rr']} hold={cfg['hold']}")
        print(f"    filter   (frozen, P3-C §3): ILLIQ_rel > {ILLIQ_THRESHOLD} "
              f"[{ILLIQ_DIRECTION}, window={ILLIQ_WINDOW}, median, shift(1)]")
        print(f"    bill USED                 : n_eff={n_eff_old:.1f} "
              f"(conservative P0; P3-A discount NOT spent)")

    # ── سیگنالِ فیلترنشده/فیلترشده برای گزارشِ تشخیصی (پیش‌بینیِ C-1) ──
    feat = P0.build_features(df, asset)
    sig_raw = P0.signal_of(feat, cfg, asset)
    sig_flt = sig_raw & keep_mask
    n_raw, n_flt = int(sig_raw.sum()), int(sig_flt.sum())
    retention = (n_flt / n_raw) if n_raw else float('nan')
    if verbose:
        print(f"    signals: raw={n_raw}  kept={n_flt}  retention={retention:.1%}")

    # ── monkeypatch ①: هندسهٔ مستقر ──
    saved_cfg = P0.ARCHIVE_CFG[card]
    P0.ARCHIVE_CFG[card] = cfg
    # ── monkeypatch ②: صورت‌حساب خوانده می‌شود، بازمحاسبه نمی‌شود ──
    saved_neff = P0.measure_neff
    P0.measure_neff = lambda feat, asset, verbose=True: (
        n_eff_old, m_sig, P0.N_SIGNAL_COLUMNS, P0.N_SIGNAL_COLUMNS)
    # ── monkeypatch ③: تنها تفاوتِ واقعیِ این پروتکل — یک AND روی سیگنال ──
    saved_sig = P0.signal_of
    P0.signal_of = lambda feat, cfg_, asset_: saved_sig(feat, cfg_, asset_) & keep_mask
    try:
        rec = P0.run_card(card, do_neff=True, verbose=verbose)
    finally:
        P0.ARCHIVE_CFG[card] = saved_cfg
        P0.measure_neff = saved_neff
        P0.signal_of = saved_sig

    rec['protocol'] = 'P3-C'
    rec['prereg'] = 'results/S363_ADDENDUM_P3C_AMIHUD_FILTER_PREREG.md'
    rec['filter'] = dict(
        name='amihud_illiquidity_relative',
        formula='|close-open|/volume, normalised by median_20(.).shift(1)',
        direction=ILLIQ_DIRECTION, threshold=ILLIQ_THRESHOLD,
        window=ILLIQ_WINDOW, free_parameters=0,
        theory='Amihud 2002; Da-Liu-Schaumburg 2011; Lou-Shu 2016',
        in_indicator_bank=False)
    rec['filter_effect'] = dict(
        n_signals_raw=n_raw, n_signals_kept=n_flt,
        retention=round(retention, 4) if n_raw else None,
        rel_median=round(float(np.nanmedian(rel[sig_raw])), 4) if n_raw else None)
    rec['geometry_source'] = 'P1 §5 min-perturbation rule (commit adf818d)'
    rec['bill'] = dict(used=n_eff_old, used_label='conservative P0 (bracket×15)',
                       p3a_corrected_diagnostic_only=n_eff_corr,
                       note='P3-A discount deliberately NOT spent')

    path = os.path.join(OUT, f'P3C_{card}.json')
    with open(path, 'w') as f:
        json.dump(rec, f, indent=1, ensure_ascii=False)
    if verbose:
        print(f"  → saved {path}  status={rec.get('status')}")
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cards', default=','.join(ALL_CARDS))
    a = ap.parse_args()
    cards = [c.strip() for c in a.cards.split(',') if c.strip()]

    os.makedirs(OUT, exist_ok=True)
    family, _ = build_family()

    print(f"{'='*96}")
    print("S363 · P3-C — theory-derived Amihud illiquidity filter")
    print(f"  prereg : results/S363_ADDENDUM_P3C_AMIHUD_FILTER_PREREG.md")
    print(f"  filter : ILLIQ_rel > 1.0 (KEEP_HIGH) — 0 free parameters, 1 test")
    print(f"  bill   : conservative P0 (~5053) — luck bound 3.69σ")
    print(f"{'='*96}")

    recs = []
    for c in cards:
        try:
            recs.append(run(c, family))
        except Exception as exc:                      # noqa: BLE001
            print(f"  !! {c} failed: {exc}", flush=True)

    # ── خلاصه + داوریِ پیش‌بینی‌ها ──
    print(f"\n{'='*96}")
    print(f"{'card':13s}{'ret':>7}{'n':>6}{'WR':>8}{'null':>8}{'z':>7}"
          f"{'bar':>7}{'score':>7}  failing")
    alive, deltas, rets = [], [], []
    for r in recs:
        if r.get('status') != 'JUDGED':
            print(f"{r['card']:13s}  {r.get('status')}")
            continue
        s = r['seeds']['23']['neff']
        m, g = s['metrics'], s['gates']
        bad = [k for k, v in g.items() if v is False]
        rets.append(r['filter_effect']['retention'])
        print(f"{r['card']:13s}{r['filter_effect']['retention']:7.1%}"
              f"{m['n_trades']:6d}{m['win_rate']:8.2f}{m['null_ref_wr']:8.2f}"
              f"{m['z_obs']:7.2f}{m['z_luck_bound']:7.2f}{s['score']:7.1f}"
              f"  {','.join(bad) if bad else '— ALL PASS —'}")
        if not bad:
            alive.append(r['card'])
        # ΔWR در برابرِ همان کارت در P3-B
        p3b = os.path.join(OUT, f"P3B_{r['card']}.json")
        if os.path.exists(p3b):
            with open(p3b) as f:
                b = json.load(f)
            deltas.append((r['card'],
                           m['win_rate'] - b['seeds']['23']['neff']['metrics']['win_rate'],
                           m['z_obs'] - b['seeds']['23']['neff']['metrics']['z_obs']))

    print(f"\n  ΔWR / Δz versus P3-B (same signal, same geometry, filter only):")
    for c, dwr, dz in deltas:
        print(f"    {c:13s} ΔWR={dwr:+6.2f}pp  Δz={dz:+5.2f}")

    if rets:
        print(f"\n  prediction C-1 (retention in 40–60% on all cards): "
              f"{'CONFIRMED' if all(0.40 <= x <= 0.60 for x in rets) else 'FALSIFIED'}")
    if deltas:
        pos = sum(1 for _, d, _ in deltas if d > 0)
        print(f"  prediction C-2 (ΔWR positive on majority): "
              f"{'CONFIRMED' if pos > len(deltas)/2 else 'FALSIFIED'} "
              f"({pos}/{len(deltas)} positive)")
    print(f"  prediction C-4 (no card passes all 11): "
          f"{'FALSIFIED — LAYER ALIVE' if alive else 'CONFIRMED'}")
    print(f"  ALIVE cards: {alive if alive else 'none'}")

    with open(os.path.join(OUT, 'P3C_SUMMARY.json'), 'w') as f:
        json.dump(dict(protocol='P3-C', alive=alive,
                       deltas=[dict(card=c, d_wr=round(d, 3), d_z=round(z, 3))
                               for c, d, z in deltas],
                       retentions=rets), f, indent=1, ensure_ascii=False)
    print(f"→ saved {OUT}/P3C_SUMMARY.json")


if __name__ == '__main__':
    main()
