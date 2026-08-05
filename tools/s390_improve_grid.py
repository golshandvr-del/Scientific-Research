# -*- coding: utf-8 -*-
"""S390 — **شبکهٔ بهبودِ هندسه برای نامزدِ S389** (`cci20_xup_135 @ XAUUSD_H1`).

نامزد ۹ از ۱۱ دروازه را پاس کرد و **فقط** روی دو دروازهٔ اقتصادی رد شد:
``H1`` (ضریبِ سود ۱.۲۴۳) و ``H8`` (افتِ سرمایه ۱۴.۶۱٪). خانوادهٔ آماری
**کاملاً** پاس شد (آلفا +۶.۴۱، z=۴.۷۱ بالای کرانِ ۴.۰۷، گذر از سقفِ
شانس +۱.۰۶).

تشخیصِ پیش‌ثبت‌شده
-----------------
انتظار ۸.۳۱ pip روی براکتی به عرضِ ۱۴۹ pip ⇒ هر معامله فقط ۵.۶٪ از عرضِ
براکت را نگه می‌دارد. مشکل **براکتِ بزرگ** است، نه لبهٔ کوچک.

پس دو محورِ بهبود آزموده می‌شوند:

* ``sl_k`` کوچک‌تر ⇒ افتِ سرمایه کم می‌شود (خطی) **ولی** سهمِ هزینه بالا
  می‌رود ⇒ سربه‌سر بالا و lift کوچک (قانونِ S383). مبادلهٔ واقعی.
* ``rr`` بزرگ‌تر ⇒ PF خطی رشد می‌کند **ولی** WR زیرخطی افت می‌کند.

قیدهای سختِ ضدِ اشتباه
---------------------
* ``rr >= 1.5`` **همیشه** — اشتباهِ رایجِ ۸ (TP<SL ⇒ WR کاذب) ساختاراً
  ممکن نیست، چون شبکه هیچ مقدارِ کمتری ندارد.
* مقادیرِ **غیررند** عمداً در هر دو شبکه (اشتباهِ رایجِ ۷): ۰.۹، ۱.۱۵،
  ۱.۳۵ و ۱.۸، ۲.۲، ۲.۶.
* **مدلِ صفر برای هر سلول از نو ساخته می‌شود** — درسِ S385/S387:
  ``perm_max`` تابعِ n است نه ثابتِ کارت. با ۲۸ سلول این گران است ولی
  بازاستفاده، پذیرشِ کاذب می‌سازد.
* هندسهٔ خطِ مبنا با ``L.RR`` جایگزین می‌شود (باگِ S386) — **هر دو**
  خطِ مبنا داخلِ بلوکِ جایگزینی.
* بارِ چندگانگیِ صادقانه: ۲۳٬۸۷۵ = ۲۳٬۸۴۷ + ۲۸.
* ذخیرهٔ **مرحله‌به‌مرحله** روی دیسک (قانونِ اندک‌اندک — ۶ ریستِ سندباکس).
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

OUT = os.path.join(ROOT, 'results', '_s390')
os.makedirs(OUT, exist_ok=True)

CARD = 'XAUUSD_H1'
RULE = 'cci20_xup_135'
ASSET = 'XAUUSD'

COST_PIP = 3.3
SEED = 20260805
K_PERM = 2000
STRIDES = (1, 3, 7)
SITE_TARGET = 252.0

N_TRIALS = 23875          # ۲۳٬۸۴۷ + ۲۸ سلولِ این شبکه
Z_LUCK = 4.07

# شبکهٔ قفل‌شده در پیش‌ثبتِ S390 — مقادیرِ غیررند عمدی
SL_K_GRID = [0.8, 0.9, 1.0, 1.15, 1.2, 1.35, 1.5]
RR_GRID = [1.5, 1.8, 2.2, 2.6]      # هرگز < 1.5


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_cell(L, NM, df, sig, n_sig, atr_med, ps, span, sl_k, rr):
    sl_abs = atr_med * sl_k
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * rr
    cost_share = 100.0 * COST_PIP / sl_pip

    tr = L.simulate_trades(df, sig, sl_abs, rr, True, ps)
    n = len(tr)
    base = dict(card=CARD, rule=RULE, sl_k=sl_k, rr=rr,
                span_years=round(span, 2), n_signals=n_sig, n_trades=n,
                sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                cost_share_pct=round(cost_share, 2))
    if n < 300:
        base['verdict'] = 'TOO_FEW_TRADES'
        return base

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())
    per_year = n / span

    # ── مدلِ صفرِ **این** سلول — هرگز بازاستفاده ──────────────────────
    _bk = L.RR
    try:
        L.RR = rr
        unc = max(NM.uncond_baseline(L, df, sl_abs, ps, s)[0] or -1e9
                  for s in STRIDES)
        perm = NM.perm_baseline(L, df, sl_abs, ps, n_sig,
                                k=K_PERM, seed=SEED)
    finally:
        L.RR = _bk

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

    base.update(
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        per_year=round(per_year, 1), avg_held_bars=round(held, 1),
        uncond_wr=round(unc, 2), alpha=round(wr - unc, 2),
        perm_mean=round(perm['mean'], 2), perm_sd=round(perm['sd'], 2),
        perm_max=round(perm['max'], 2),
        gap_to_perm_max=round(wr - perm['max'], 2),
        pf=m.get('profit_factor'), net=m.get('net_profit'),
        z=m.get('skill_z'), max_dd_pct=m.get('max_dd_pct'),
        expectancy_pip=m.get('expectancy_pip'),
        max_consec_losses=m.get('max_consec_losses'),
        rqs2=res.get('rqs2_score'), verdict=res.get('verdict'),
        gates=g,
        n_gates_fail=sum(1 for v in g.values() if v is False),
        failed_gates=sorted(k for k, v in g.items() if v is False),
        c1_lift_pos=bool(wr - be > 0),
        c2_alpha_pos=bool(wr > unc),
        c3_beats_perm_max=bool(wr > perm['max']),
        c4_n_ok=bool(n >= 300),
        c5_accept=bool(res.get('verdict') == 'ACCEPT'))
    base['all_five'] = bool(
        base['c1_lift_pos'] and base['c2_alpha_pos']
        and base['c3_beats_perm_max'] and base['c4_n_ok']
        and base['c5_accept'])
    return base


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    bank = dict(RB.build_rules())

    print(f'S390 improve grid | {RULE} @ {CARD} | LOCKED rule, free geometry')
    print(f'sl_k={SL_K_GRID} rr={RR_GRID} | n_trials={N_TRIALS} '
          f'z_luck={Z_LUCK} K={K_PERM}')
    print()

    df = L.load(CARD)
    ps = L.pip_size(ASSET)
    atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    sig = bank[RULE](df)
    n_sig = int(np.asarray(sig).astype(bool).sum())
    print(f'bars={len(df)} span={span:.2f}y raw_signals={n_sig}')
    print()

    hdr = ('slk', 'rr', 'slpip', 'c/SL%', 'n', '/yr', 'held', 'wr', 'be',
           'lift', 'unc', 'alpha', 'pmax', 'gap', 'pf', 'dd', 'z',
           'rqs2', 'fail')
    print('%4s %4s %7s %6s %6s %7s %6s %6s %6s %7s %6s %7s %6s %6s '
          '%6s %6s %6s %6s %s' % hdr)
    print('-' * 132)

    for sl_k in SL_K_GRID:
        for rr in RR_GRID:
            fn = os.path.join(OUT, f'k{sl_k}_rr{rr}.json')
            if os.path.exists(fn):
                r = json.load(open(fn))
            else:
                r = run_cell(L, NM, df, sig, n_sig, atr_med, ps,
                             span, sl_k, rr)
                json.dump(r, open(fn, 'w'), indent=1)
            if r.get('verdict') == 'TOO_FEW_TRADES':
                print('%4.2f %4.1f %7.1f %6.2f %6d  TOO_FEW' % (
                    sl_k, rr, r['sl_pip'], r['cost_share_pct'],
                    r['n_trades']))
                continue
            print('%4.2f %4.1f %7.1f %6.2f %6d %7.1f %6.1f %6.2f %6.2f '
                  '%+7.2f %6.2f %+7.2f %6.2f %+6.2f %6.3f %6.2f %6.2f '
                  '%6.1f %s' % (
                      sl_k, rr, r['sl_pip'], r['cost_share_pct'],
                      r['n_trades'], r['per_year'], r['avg_held_bars'],
                      r['wr'], r['be'], r['lift'], r['uncond_wr'],
                      r['alpha'], r['perm_max'], r['gap_to_perm_max'],
                      r['pf'] or 0, r['max_dd_pct'] or 0, r['z'] or 0,
                      r['rqs2'] or 0,
                      ('ACCEPT' if r['all_five']
                       else ','.join(r['failed_gates']) or 'cond')))
    print()
    print('done.')


if __name__ == '__main__':
    main()
