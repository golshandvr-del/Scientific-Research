# -*- coding: utf-8 -*-
"""S392 — **شبکهٔ مشترکِ هندسه × فیلترِ ساعت** (قانونِ همکاریِ بهبود‌ها).

چرا این گام لازم است
--------------------
S390 هندسه را **در غیابِ فیلتر** بهینه کرد و `sl_k=1.5, rr=2.2` برنده شد.
S391 نشان داد فیلترِ ساعتِ ۷–۱۷ روی همان هندسه، افت را از ۱۱.۶۷ به ۶.۶۳
می‌رساند (H8 تعمیر) و آلفا را حتی **بالا** می‌برد — ولی ۳۳٪ معامله دور
می‌ریزد و `z_obs` به ۳.۷۳۶ می‌افتد، یعنی **۰.۳۳۳ واحد** زیرِ کرانِ
قضیهٔ استراتژیِ کاذب (۴.۰۶۸۵).

نکتهٔ ساختاری: هندسه‌ای که **بی‌فیلتر** بازنده بود، ممکن است **با فیلتر**
برنده باشد. مثلاً `k=0.9, rr=1.5` بی‌فیلتر ۱۵۴۵ معامله داشت (در برابرِ
۱۲۸۵) ولی افتِ ۲۰.۰۴٪ — و اگر فیلترِ ساعت افتش را ۴۳٪ کم کند، به ۱۱.۴
می‌رسد که هنوز رد است. ولی `k=1.15, rr=2.6` بی‌فیلتر ۱۳۷۷ معامله و
افتِ ۱۲.۸۳ داشت ⇒ با کاهشِ ۴۳٪ به ~۷.۳ می‌رسد **و** n بیشتری دارد.

پس ترکیب باید **مشترک** بهینه شود، نه دنباله‌ای. این عیناً «قانونِ
همکاریِ بهبود‌ها»ست.

قیدهای ضدِ تقلب
--------------
* **شبکه کوچک و پیش‌ثبت‌شده** — نه جست‌وجوی آزاد. فقط ۵ هندسهٔ برترِ S390
  (بر اساسِ `n` و افت) × ۲ پنجرهٔ ساعتِ برترِ S391 = **۱۰ سلول**.
  علت: هر سلولِ جدید کرانِ `H5` را بالا می‌برد.
* `rr >= 1.5` همیشه — اشتباهِ رایجِ ۸ ساختاراً ممکن نیست.
* خطِ مبنا **فیلترشده** (محافظِ S391 — وگرنه اثرِ سشن «مهارت» ثبت می‌شود).
* مدلِ صفر برای **هر** سلول از نو (`perm_max` تابعِ n است).
* بارِ چندگانگیِ صادقانه: ۲۳٬۸۹۷ = ۲۳٬۸۸۷ + ۱۰.
  ⇒ کرانِ `H5` از ۴.۰۶۸۵ به مقدارِ نو می‌رود (لگاریتمی ⇒ ناچیز، ولی
  محاسبه و گزارش می‌شود).
* ذخیرهٔ مرحله‌به‌مرحله (۷ ریستِ سندباکس).
* سلولِ `k1.5_rr2.2 × hour_7_17` **شاهدِ درونی** است و باید عیناً با
  `results/_s391/hour_no_lastbar.json` بخواند.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2 as R  # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s392')
os.makedirs(OUT, exist_ok=True)

CARD = 'XAUUSD_H1'
RULE = 'cci20_xup_135'
ASSET = 'XAUUSD'
COST_PIP = 3.3
SEED = 20260805
K_PERM = 2000
STRIDES = (1, 3, 7)
DD_TARGET = 8.0

N_TRIALS = 23897          # ۲۳٬۸۸۷ + ۱۰
# شبکهٔ قفل‌شده: ۵ هندسه × ۲ پنجرهٔ ساعت
GEOMS = [(1.5, 2.2), (1.15, 2.6), (1.20, 2.6), (1.15, 1.5), (0.9, 1.5)]
HOURS = [('h7_17', 7, 17), ('h7_15', 7, 15)]


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_cell(L, NM, df, sig_base, hmask, sl_k, rr, atr_med, ps, span):
    sig = np.asarray(sig_base).astype(bool) & np.asarray(hmask).astype(bool)
    n_sig = int(sig.sum())
    sl_abs = atr_med * sl_k
    sl_pip = sl_abs / ps
    tp_pip = sl_pip * rr

    tr = L.simulate_trades(df, pd.Series(sig, index=df.index),
                           sl_abs, rr, True, ps)
    n = len(tr)
    base = dict(card=CARD, rule=RULE, sl_k=sl_k, rr=rr,
                span_years=round(span, 2), n_signals=n_sig, n_trades=n,
                sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                cost_share_pct=round(100.0 * COST_PIP / sl_pip, 2))
    if n < 300:
        base['verdict'] = 'TOO_FEW_TRADES'
        return base

    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    be = 100.0 * (sl_pip + COST_PIP) / (tp_pip + sl_pip)
    held = float((tr['exit_bar'] - tr['entry_bar']).mean())

    # ── مدلِ صفر روی **همان زیرمجموعهٔ ساعتی** (محافظِ S391) ─────────────
    _bk = L.RR
    try:
        L.RR = rr
        sub = df.loc[np.asarray(hmask).astype(bool)].reset_index(drop=True)
        unc = max(NM.uncond_baseline(L, sub, sl_abs, ps, s)[0] or -1e9
                  for s in STRIDES)
        perm = NM.perm_baseline(L, sub, sl_abs, ps, n_sig,
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
                         close=df['close'].to_numpy(float),
                         null=null, n_trials=N_TRIALS,
                         split_bar=int(0.70 * len(df)))
    g = res.get('gates') or {}
    wins = int((tr['outcome'] == 'win').sum())
    base.update(
        wr=round(wr, 2), be=round(be, 2), lift=round(wr - be, 2),
        per_year=round(n / span, 1), avg_held_bars=round(held, 1),
        uncond_wr=round(unc, 2), alpha=round(wr - unc, 2),
        perm_max=round(perm['max'], 2),
        gap_to_perm_max=round(wr - perm['max'], 2),
        z_obs=round(R.binom_z(wins, n, unc / 100.0), 3),
        z_bar=round(R.expected_max_z(N_TRIALS), 4),
        rqs2=res.get('rqs2_score'), verdict=res.get('verdict'), gates=g,
        n_gates_fail=sum(1 for v in g.values() if v is False),
        failed_gates=sorted(k for k, v in g.items() if v is False))
    for k in ('profit_factor', 'net_profit', 'skill_z', 'max_dd_pct',
              'expectancy_pip', 'max_consec_losses'):
        base[k] = res.get(k)
    base['all_gates'] = bool(base['n_gates_fail'] == 0)
    return base


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    NM = _mod('tools/s382_null_model.py', '_nm')
    RB = _mod('tools/step1_rule_bank.py', '_rb')
    bank = dict(RB.build_rules())

    zbar = R.expected_max_z(N_TRIALS)
    print(f'S392 joint grid | {RULE} @ {CARD} | geoms={GEOMS} hours={HOURS}')
    print(f'n_trials={N_TRIALS} z_bar={zbar:.4f} K={K_PERM} '
          f'dd_target<={DD_TARGET}')
    print()

    df = L.load(CARD)
    ps = L.pip_size(ASSET)
    atr_med = float(np.nanmedian(L.atr(df).to_numpy()))
    span = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    sig_base = np.asarray(bank[RULE](df)).astype(bool)
    hr = df['dt'].dt.hour.to_numpy()

    print('%-8s %4s %4s %6s %6s %6s %7s %7s %6s %6s %6s %6s %s' % (
        'hours', 'slk', 'rr', 'n', '/yr', 'wr', 'alpha', 'z_obs',
        'gap_z', 'pf', 'dd', 'rqs2', 'fails'))
    print('-' * 118)

    for hname, h0, h1 in HOURS:
        hmask = (hr >= h0) & (hr <= h1)
        for sl_k, rr in GEOMS:
            fn = os.path.join(OUT, f'{hname}_k{sl_k}_rr{rr}.json')
            if os.path.exists(fn):
                r = json.load(open(fn))
            else:
                r = run_cell(L, NM, df, sig_base, hmask, sl_k, rr,
                             atr_med, ps, span)
                json.dump(r, open(fn, 'w'), indent=1)
            if r.get('verdict') == 'TOO_FEW_TRADES':
                print('%-8s %4.2f %4.1f %6d TOO_FEW' % (
                    hname, sl_k, rr, r['n_trades']))
                continue
            print('%-8s %4.2f %4.1f %6d %6.1f %6.2f %+7.2f %7.3f %+6.3f '
                  '%6.3f %6.2f %6.1f %s' % (
                      hname, sl_k, rr, r['n_trades'], r['per_year'], r['wr'],
                      r['alpha'], r['z_obs'], r['z_obs'] - r['z_bar'],
                      r.get('profit_factor') or 0, r.get('max_dd_pct') or 0,
                      r.get('rqs2') or 0,
                      ','.join(r['failed_gates']) or 'ALL-PASS'))
    print()
    print('done.')


if __name__ == '__main__':
    main()
