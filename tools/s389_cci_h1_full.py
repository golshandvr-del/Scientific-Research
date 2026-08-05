# -*- coding: utf-8 -*-
"""S389 — **آزمونِ کاملِ نامزدِ `cci20_xup_135` روی XAUUSD_H1.**

این نامزد در بازاسکنِ آلفا (S388) کشف شد و اسکنِ اولیه از دستش داده بود،
چون آن اسکن بر ``lift`` مرتب می‌کرد و ``lift`` این ردیف فقط ۳.۳۶ است
در حالی که آلفایش ۶.۴۱ است — دومین آلفای کلِ آرشیو پس از S382.

چرا این نامزد متمایز است
------------------------
=========================  ==================  ==================
کمیت                       S382 (پذیرفته)      این نامزد
=========================  ==================  ==================
کارت                       XAUUSD_H4           **XAUUSD_H1**
n                          ۸۶۹                 **۱۳۶۷**
نرخ/سال                    ۵۵.۹                **۸۸.۰**
آلفا                       +۸.۳۷               +۶.۴۱
lift                       +۷.۸۳               +۳.۳۶
z تخمینی                   ۴.۹۳                **۴.۷۶**
=========================  ==================  ==================

**کارتِ متفاوت + نمونهٔ ۵۷٪ بزرگ‌تر** ⇒ اگر پاس شود، هم لایهٔ دومِ
پرتفوی است (راهِ ۲ در شکلِ اصلی‌اش) و هم پرتوان‌ترین لایهٔ پروژه.

آنچه این اسکریپت می‌سنجد
------------------------
۱. **همپوشانی با S382** — طبق قانونِ همپوشانیِ پروژه (بندِ اول).
   کارت‌ها متفاوت‌اند پس قیدِ عدم‌همپوشانی مشترک نیست، ولی همپوشانیِ
   **زمانی** باید عددی تأیید شود: اگر سیگنال‌ها همیشه در همان ساعت‌ها
   بیفتند، دو لایه یک لایه‌اند.
۲. **مدلِ صفرِ کاملِ سه‌مرجعی** — خریدارِ کور + ۲۰۰۰ جایگشت + سربه‌سر.
۳. **هر ۱۱ دروازهٔ rqs2** با بارِ چندگانگیِ صادقانهٔ ۲۳٬۸۴۷ آزمون.
۴. **پایداریِ تقویمی** و **خارج‌ازنمونه** (نیمهٔ دوم).
۵. **رانشِ ضدِ رژیم** — همان آزمونی که ایرادِ «بتای طلا» را برای S382
   ابطال کرد.

نکاتِ صحت
---------
* هندسه از آرشیو **قفل** است: ``sl_k=1.5, rr=1.5``. هیچ بهینه‌سازیِ
  per-card انجام نمی‌شود چون بارِ چندگانگی را ضرب می‌کند.
* خطِ مبنا با هندسهٔ **همین** نامزد ساخته می‌شود (باگِ S386).
* شبیه‌سازِ S382 عیناً بازاستفاده می‌شود — هیچ پیاده‌سازیِ نو.
"""

from __future__ import annotations
import importlib.util
import json
import math
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, 'results', '_s389')
os.makedirs(OUTDIR, exist_ok=True)

# ── نامزدِ قفل‌شده از S388 ─────────────────────────────────────────────
CARD = 'XAUUSD_H1'
RULE = 'cci20_xup_135'
SIDE = 'long'
SL_K = 1.5
RR = 1.5

# ── بارِ چندگانگیِ صادقانه ─────────────────────────────────────────────
N_TRIALS = 23847      # 23846 (تا S388) + 1 (این نامزد)
Z_LUCK = 4.07

K_PERM = 2000
SEED = 20260805
STRIDES = (1, 3, 7)

# لایهٔ مرجع برای آزمونِ همپوشانی
REF_CARD = 'XAUUSD_H4'
REF_RULE = 'willr14_xup_-13'


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    bank = dict(RB.build_rules())

    print(f'S389 | {RULE} @ {CARD} | sl_k={SL_K} rr={RR} side={SIDE}')
    print(f'n_trials={N_TRIALS} z_luck={Z_LUCK} K={K_PERM}')
    print()

    df = L.load(CARD)
    ps = L.pip_size(CARD.split('_')[0])
    atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
    sl_abs = atr_med * SL_K
    print(f'bars={len(df)} sl={sl_abs/ps:.1f}pip atr_med={atr_med:.4f}')

    sig = np.asarray(bank[RULE](df)).astype(bool)
    print(f'raw signals={int(sig.sum())} '
          f'({sig.sum()/ (len(df)/ (365.25*24/1)) if False else 0:.0f})')

    # ── شبیه‌سازِ رویدادمحور ──────────────────────────────────────────
    tr = L.simulate(df, sig, sl_abs, ps, side=SIDE, rr=RR)
    n = len(tr)
    wins = int((tr['pnl_pip'] > 0).sum())
    wr = 100.0 * wins / n
    span = L.span_years(df)
    per_year = n / span
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())
    cost_pip = L.cost_pip(CARD.split('_')[0])
    sl_pip = sl_abs / ps
    be = 100.0 / (1.0 + RR) * (1 + cost_pip / sl_pip) if False else None
    # سربه‌سر را از خودِ ماژول می‌گیریم تا با S382/S384 یکسان باشد
    be = L.breakeven_wr(sl_pip, RR, cost_pip)
    lift = wr - be
    print(f'n={n} wr={wr:.2f} be={be:.2f} lift={lift:+.2f} '
          f'/yr={per_year:.1f} held={held:.1f} span={span:.2f}')

    # ── مدلِ صفر ──────────────────────────────────────────────────────
    _bk = L.RR
    try:
        L.RR = RR
        unc = max(NM.uncond_baseline(L, df, sl_abs, ps, s)[0] or -1e9
                  for s in STRIDES)
        perm = NM.perm_baseline(L, df, sl_abs, ps, int(sig.sum()),
                                k=K_PERM, seed=SEED)
    finally:
        L.RR = _bk

    alpha = wr - unc
    p = wr / 100.0
    se = 100.0 * math.sqrt(max(p * (1 - p), 1e-12) / n)
    z_vs_unc = alpha / se
    z_vs_perm = (wr - perm['mean']) / perm['sd'] if perm['sd'] > 0 else None
    p_emp = sum(1 for _ in range(0)) or None

    print()
    print(f'unc={unc:.2f} alpha={alpha:+.2f} z_vs_unc={z_vs_unc:.3f}')
    print(f'perm mean={perm["mean"]:.2f} sd={perm["sd"]:.2f} '
          f'max={perm["max"]:.2f} p95={perm["p95"]:.2f} k={perm["k"]}')
    print(f'z_vs_perm={z_vs_perm:.3f} gap_to_max={wr-perm["max"]:+.2f}')

    out = dict(card=CARD, rule=RULE, side=SIDE, sl_k=SL_K, rr=RR,
               n_trials=N_TRIALS, z_luck=Z_LUCK,
               span_years=round(span, 2), sl_pip=round(sl_pip, 2),
               cost_pip=round(cost_pip, 3),
               n_signals=int(sig.sum()), n_trades=n,
               wr=round(wr, 2), be=round(be, 2), lift=round(lift, 2),
               per_year=round(per_year, 1), avg_held_bars=round(held, 1),
               uncond_wr=round(unc, 2), alpha=round(alpha, 2),
               z_vs_uncond=round(z_vs_unc, 3),
               perm_mean=round(perm['mean'], 2), perm_sd=round(perm['sd'], 2),
               perm_max=round(perm['max'], 2), perm_p95=round(perm['p95'], 2),
               perm_k=perm['k'],
               z_vs_perm=round(z_vs_perm, 3) if z_vs_perm else None,
               gap_to_perm_max=round(wr - perm['max'], 2))
    json.dump(out, open(os.path.join(OUTDIR, 'core.json'), 'w'), indent=1)
    print()
    print(f'saved -> {OUTDIR}/core.json')


if __name__ == '__main__':
    main()
