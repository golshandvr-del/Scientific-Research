# -*- coding: utf-8 -*-
"""S520 — داوریِ **استخرِ** تایم‌فریم‌های بکر طبقِ پیش‌ثبت (مسیرِ B).

پیش‌ثبت: `results/S520_PREREG_WilliamsRVirginTFs_Xauusd_H2H3H6H8H12.md`
نتایجِ per-card (checkpoint شده): H2 lift=−0.26 · H3 +2.59 · H6 +5.66 ·
H8 +8.50 (z=3.07!) · H12 +7.28 — همه REJECTِ منفرد (کمبودِ توان).

مکانیزم: همان دارویِ S431/S432 — یک قانونِ منجمد روی چند کارت، ادغامِ
FIFOِ تقویمی، صفر پارامترِ آزادِ جدید، z∝√n.

ترکیبِ استخر را **الگوریتمِ از-پیش-موجود** `choose_homogeneous_subset`
تعیین می‌کند (حریصانه از قوی‌ترین lift، حاشیهٔ ۱۵٪) — نه انتخابِ پسینیِ من.
H2 با lift≤0 خودکار حذف می‌شود (شرطِ ۲). کارتِ H4 عمداً عضو **نیست**:
خانوادهٔ پیش‌ثبت‌شده فقط ۵ کارتِ بکر است؛ افزودنِ H4ِ پذیرفته‌شده پس از
دیدنِ نتایج = تصمیمِ پسینی = نقضِ پیش‌ثبت.

الگوبرداریِ کامل از `strategies/s431_lpsb_multicard_pool.py` (سه باگِ
مستندِ آن — BUG-AXIS/BUG-QUANT/BUG-SPAN — اینجا از روز اول اجتناب شده):
  • محورِ مشترک: شبکهٔ مصنوعیِ یکنواخت روی افقِ کاملِ استخر (نه هیچ فایلی).
    گام = ۱ ساعت (ریزترین عضوِ ممکن H2=۲ساعت ⇒ هیچ برخوردِ سطلی ممکن نیست).
  • closeِ محور: از H2ِ کامل (کلِ افق را دارد) با نگه‌داشتِ آخرین مقدار —
    searchsorted(right)−1 ⇒ هیچ قیمتِ آینده به گذشته نمی‌نشیند.
  • نولِ استخر: ترکیبِ وزنیِ نول‌های اندازه‌گیری‌شدهٔ اعضا با وزنِ سهمِ
    **پس-از-FIFO** (واریانس‌ها وزن می‌گیرند، نه sdها).
  • C5: هیچ عضوی >۵۰٪ استخر (شرطِ مشروعیتِ S431).
  • تقسیمِ ۶۰/۴۰: صدکِ ۶۰٪ِ زمانِ ورود (holdout_mask تقویمی).
  • n_trials = 23755 (ارثی از جست‌وجوی S382 — کم‌گزارشی ممنوع).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import rqs2  # noqa: E402
from engine.rqs2_pool import pool_cards  # noqa: E402

OUT = 'results/_s520'
FAMILY = ['XAUUSD_H2', 'XAUUSD_H3', 'XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12']
N_TRIALS = 23755
SPLIT_FRAC = 0.60
C5_MAX_MEMBER_SHARE = 0.50
STEP_NS = 3600 * 1_000_000_000          # ۱ ساعت — ریزتر از ریزترین عضو (H2)
PERM_K = 2000                            # K مدل‌های صفرِ per-card (بذر 20260805)


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_member(L, card):
    """بازتولیدِ معاملاتِ کارت (همان شبیه‌ساز) + نولِ اندازه‌گیری‌شدهٔ ذخیره‌شده."""
    with open(f'{OUT}/{card}.json') as f:
        saved = json.load(f)
    df = L.load(card)
    ps = L.pip_size('XAUUSD')
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    tr = L.simulate_trades(df, L.signals(df), sl_abs, L.RR, True, ps)
    # سلامت: بازتولید باید عیناً همان n و wr ذخیره‌شده را بدهد
    assert len(tr) == saved['n_trades'], f'{card}: reproduction mismatch!'
    null = {'long': dict(uncond_wr=saved['uncond_wr'],
                         perm_mean=saved['perm_mean'],
                         perm_sd=saved['perm_sd'],
                         perm_max=saved['perm_max'], perm_k=PERM_K),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    return dict(card=card, tr=tr, dt=df['dt'].values, lift=saved['lift'],
                n=len(tr), null=null, sl_pip=saved['sl_pip'],
                tp_pip=saved['tp_pip'])


def blend_pool_null(members_used, pool_df):
    """عیناً منطقِ S431: ترکیبِ وزنی با سهمِ پس-از-FIFO؛ واریانس‌ها وزن می‌گیرند."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u, den_u = 0.0, 0.0
        num_m, num_s, den_p, kmin = 0.0, 0.0, 0.0, None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
            if w <= 0:
                continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * w
                den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w
                num_s += (d['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = d.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def main():
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')

    def load_full(card):
        df = pd.read_csv(f'data/full/{card}.csv')
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        return df

    L.load = load_full

    print('== S520-POOL | اعضای نامزد = خانوادهٔ پیش‌ثبت‌شده ==', flush=True)
    members = [build_member(L, c) for c in FAMILY]
    for m in members:
        print(f"  {m['card']}: n={m['n']} lift={m['lift']:+.2f}", flush=True)

    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                           lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] هیچ عضوِ معتبری نماند.', flush=True)
        return
    pool = res['pool']
    print(f"\n[انتخاب] used={[u['card'] for u in res['used']]} "
          f"dropped={[(d['card'], d['reason']) for d in res['dropped']]}",
          flush=True)
    print(f"[FIFO] n_before={res['n_before']} n_after={res['n_after']}",
          flush=True)
    print(f"[trace] {json.dumps(res['selection']['trace'], ensure_ascii=False)}",
          flush=True)

    # ---- C5: سهمِ اعضا ----
    share = pool['src_card'].value_counts(normalize=True)
    print(f"\n[C5 سهم] {share.round(3).to_dict()}", flush=True)
    if float(share.max()) > C5_MAX_MEMBER_SHARE:
        print(f"[C5 نقض] {share.idxmax()} سهم {share.max():.1%} > "
              f"{C5_MAX_MEMBER_SHARE:.0%} ⇒ توقف (استخر نامشروع).", flush=True)
        with open(f'{OUT}/pool_c5_violation.json', 'w') as fh:
            json.dump(dict(share=share.to_dict()), fh, ensure_ascii=False)
        return

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f"[نولِ استخر] {json.dumps(null, ensure_ascii=False)}", flush=True)

    # ---- محورِ مشترکِ مصنوعی (ضد BUG-AXIS/QUANT/SPAN) ----
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f"[محور] 1h grid · {axis_dt[0]} → {axis_dt[-1]} · "
          f"{len(axis_t):,} سطل", flush=True)

    ref = load_full('XAUUSD_H2')             # کلِ افق را پوشش می‌دهد
    ref_t = ref['dt'].values.astype('datetime64[ns]').astype(np.int64)
    ref_c = ref['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_entry'].values, 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_exit'].values, 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # ---- هندسهٔ استخر: میانگینِ وزنی به سهمِ پس-از-FIFO ----
    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))
    print(f"[هندسه] sl_med={sl_med:.1f} tp_med={tp_med:.1f} pip", flush=True)

    # ---- تقسیمِ ۶۰/۴۰: صدکِ ۶۰٪ زمانِ ورود (آینده‌نگر) ----
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f"[تقسیم] مرز={np.datetime64(split_ns, 'ns')} · "
          f"اکتشاف={int((~holdout).sum())} · OOS={int(holdout.sum())}",
          flush=True)

    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=axis_dt, null=null, close=axis_close,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S520-POOL', r), flush=True)

    out = dict(members=[dict(card=m['card'], n=m['n'], lift=m['lift'])
                        for m in members],
               used=[u['card'] for u in res['used']], dropped=res['dropped'],
               selection=res['selection'], n_before=res['n_before'],
               n_after=res['n_after'], member_share=share.to_dict(),
               sl_pip_med=sl_med, tp_pip_med=tp_med, n_trials=N_TRIALS,
               split_frac=SPLIT_FRAC,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=[str(x) for x in (r.get('notes') or [])])
    with open(f'{OUT}/POOL_verdict.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, default=str)
    pool.to_csv(f'{OUT}/POOL_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/POOL_verdict.json + POOL_trades.csv', flush=True)


if __name__ == '__main__':
    main()
