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
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R                                    # noqa: E402

OUTDIR = os.path.join(ROOT, 'results', '_s389')
os.makedirs(OUTDIR, exist_ok=True)

# ── نامزدِ قفل‌شده از S388 ─────────────────────────────────────────────
CARD = 'XAUUSD_H1'
RULE = 'cci20_xup_135'
ASSET = 'XAUUSD'
SIDE = 'long'
SL_K = 1.5
RR = 1.5

# ── ثابت‌های حساب — عیناً از S384 (هرگز بازتعریف نمی‌شوند) ────────────
COST_PIP = 3.3            # اسپردِ ۰.۳۳ $/oz = ۳.۳ pip روی طلا
SEED = 20260805
K_PERM = 2000
STRIDES = (1, 3, 7)
SITE_TARGET = 252.0
RQS2_FLOOR = 50.0

# ── بارِ چندگانگیِ صادقانه ─────────────────────────────────────────────
N_TRIALS = 23847          # ۲۳٬۸۴۶ (تا S388) + ۱ (این نامزد)
Z_LUCK = 4.07

# لایهٔ مرجع برای آزمونِ همپوشانیِ زمانی
REF_CARD = 'XAUUSD_H4'
REF_RULE = 'willr14_xup_-13'


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def temporal_overlap(L, bank, df_cand, sig_cand):
    """همپوشانیِ **زمانی** با لایهٔ مرجع روی کارتِ دیگر.

    دو کارت قیدِ عدم‌همپوشانیِ مشترک ندارند (هر کارت جداگانه اعمال
    می‌شود)، پس تصادمِ مکانیکی ممکن نیست. ولی اگر سیگنال‌های دو لایه
    همیشه در همان **ساعت‌های تقویمی** بیفتند، عملاً یک لایه‌اند و راهِ
    پرتفوی هیچ نمی‌گیرد. پس همپوشانی روی مُهرِ زمانیِ ساعتِ ورود سنجیده
    می‌شود، نه روی شمارهٔ کندل.
    """
    df_ref = L.load(REF_CARD)
    sig_ref = np.asarray(bank[REF_RULE](df_ref)).astype(bool)

    def hours(df, sig):
        t = df['dt'].to_numpy()[sig]
        return set(np.asarray(t, dtype='datetime64[h]').tolist())

    a = hours(df_cand, sig_cand)
    b = hours(df_ref, sig_ref)
    inter = len(a & b)
    union = len(a | b)
    return dict(
        n_hours_cand=len(a), n_hours_ref=len(b),
        n_shared_hours=inter,
        jaccard=round(inter / union, 4) if union else None,
        cover_cand=round(inter / len(a), 4) if a else None,
        cover_ref=round(inter / len(b), 4) if b else None)


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    bank = dict(RB.build_rules())

    print(f'S389 | {RULE} @ {CARD} | sl_k={SL_K} rr={RR} side={SIDE}')
    print(f'n_trials={N_TRIALS} z_luck={Z_LUCK} K={K_PERM}')
    print()

    df = L.load(CARD)
    ps = L.pip_size(ASSET)
    atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
    sl_abs = atr_med * SL_K
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * RR
    cost_share = 100.0 * COST_PIP / sl_pip
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    print(f'bars={len(df)} span={span:.2f}y sl={sl_pip:.1f}pip '
          f'tp={tp_pip:.1f}pip cost/SL={cost_share:.2f}%')

    sig = bank[RULE](df)
    n_sig = int(np.asarray(sig).astype(bool).sum())
    print(f'raw signals={n_sig} ({n_sig/span:.1f}/yr)')

    # ── شبیه‌سازِ رویدادمحور — عیناً مسیرِ S384 ────────────────────────
    tr = L.simulate_trades(df, sig, sl_abs, RR, True, ps)
    n = len(tr)
    if n < 30:
        print('TOO_FEW_TRADES')
        return
    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())
    per_year = n / span
    print(f'n={n} wr={wr:.2f} be={be:.2f} lift={wr-be:+.2f} '
          f'/yr={per_year:.1f} held={held:.1f}')

    # ── مدلِ صفرِ **همین** نامزد — هندسه جایگزین می‌شود (باگِ S386) ────
    _bk = L.RR
    try:
        L.RR = RR
        unc = max(NM.uncond_baseline(L, df, sl_abs, ps, s)[0] or -1e9
                  for s in STRIDES)
        perm = NM.perm_baseline(L, df, sl_abs, ps, n_sig,
                                k=K_PERM, seed=SEED)
    finally:
        L.RR = _bk

    alpha = wr - unc
    print()
    print(f'unc={unc:.2f} alpha={alpha:+.2f}')
    print(f'perm mean={perm["mean"]:.2f} sd={perm["sd"]:.2f} '
          f'max={perm["max"]:.2f} p95={perm["p95"]:.2f} k={perm["k"]}')
    print(f'gap_to_perm_max={wr-perm["max"]:+.2f}')

    null = {'long': dict(uncond_wr=unc, perm_mean=perm['mean'],
                         perm_sd=perm['sd'], perm_max=perm['max'],
                         perm_k=perm['k']),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}

    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=df['time'].to_numpy(),
                         close=df['close'].to_numpy(float), null=null,
                         n_trials=N_TRIALS, split_bar=int(0.70 * len(df)))
    m = res.get('metrics') or {}
    g = res.get('gates') or {}
    print()
    print(f'rqs2={res.get("rqs2_score")} verdict={res.get("verdict")}')
    print('gates: ' + ' '.join(
        f'{k}:{"OK" if v is True else ("no" if v is False else "?")}'
        for k, v in sorted(g.items())))
    print(f'PF={m.get("profit_factor")} net={m.get("net_profit")} '
          f'z={m.get("skill_z")} maxdd={m.get("max_dd_pct")}')

    ov = temporal_overlap(L, bank, df, np.asarray(sig).astype(bool))
    print()
    print(f'temporal overlap vs {REF_RULE}@{REF_CARD}: '
          f'jaccard={ov["jaccard"]} cover_cand={ov["cover_cand"]} '
          f'cover_ref={ov["cover_ref"]}')

    out = dict(
        card=CARD, rule=RULE, side=SIDE, sl_k=SL_K, rr=RR,
        n_trials=N_TRIALS, z_luck=Z_LUCK, span_years=round(span, 2),
        sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
        cost_pip=COST_PIP, cost_share_pct=round(cost_share, 2),
        n_signals=n_sig, n_trades=n,
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        per_year=round(per_year, 1), avg_held_bars=round(held, 1),
        uncond_wr=round(unc, 2), alpha=round(alpha, 2),
        perm_mean=round(perm['mean'], 2), perm_sd=round(perm['sd'], 2),
        perm_max=round(perm['max'], 2), perm_p95=round(perm['p95'], 2),
        perm_k=perm['k'], gap_to_perm_max=round(wr - perm['max'], 2),
        pf=m.get('profit_factor'), net=m.get('net_profit'),
        z=m.get('skill_z'), max_dd_pct=m.get('max_dd_pct'),
        rqs2=res.get('rqs2_score'), verdict=res.get('verdict'),
        gates=g, metrics=m, temporal_overlap=ov,
        c1_lift_pos=bool(wr - be > 0),
        c2_beats_uncond=bool(wr > unc),
        c3_beats_perm_max=bool(wr > perm['max']),
        c4_site_rate=bool(per_year >= SITE_TARGET),
        c5_accept=bool(res.get('verdict') == 'ACCEPT'))
    out['all_five'] = bool(out['c1_lift_pos'] and out['c2_beats_uncond']
                           and out['c3_beats_perm_max']
                           and out['c4_site_rate'] and out['c5_accept'])
    json.dump(out, open(os.path.join(OUTDIR, 'core.json'), 'w'), indent=1)
    print()
    print(f'saved -> {OUTDIR}/core.json')


if __name__ == '__main__':
    main()
