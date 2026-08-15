# -*- coding: utf-8 -*-
"""S540 — داوریِ استخرِ **لنگردار** {H4,H6,H8,H12} طبقِ پیش‌ثبتِ نسخهٔ ۲.

پیش‌ثبت: `results/S540_PREREG_S382_ANCHORED_POOL_H4H6H8H12.md` (کامیت 11812eca)

تمایز از دو جسد/زنده:
  • S520-POOL {H6,H8,H12} بی‌لنگر → REJECT 21.8 — این استخر لنگرِ H4 دارد.
  • S382-H4 تنها → ACCEPT زنده — این استخر معاملاتِ مستقلِ درشت‌تر را می‌افزاید.

اصلِ صفر-بازنویسی: این فایل کپیِ وفادارِ `tools/s520_pool_adjudicate.py` است
(همان محورِ ۱ساعته، همان FIFO، همان C5، همان تقسیمِ ۶۰/۴۰، همان n_trials)
با فقط این تفاوت‌های اعلام‌شده در پیش‌ثبت:
  ۱. FAMILY شاملِ لنگرِ XAUUSD_H4 است.
  ۲. دادهٔ H4 از `data/XAUUSD_H4.csv` (mt5_full فایلِ H4 ندارد؛ مانیفست
     هم‌فیدبودن را ۱۰۰٪ تأیید کرده). بقیه از `data/full/`.
  ۳. نول و آمارِ per-cardِ H4 از بایگانیِ S382 (`results/_s382/null_model.json`
     + `results/_s382_mtf/XAUUSD_H4.json`) — نه محاسبهٔ نو. بقیه از
     `results/_s520/*.json`. صفر نولِ جدید ⇒ صفر بذرِ جدید.
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
os.chdir(ROOT)

from engine import rqs2  # noqa: E402
from engine.rqs2_pool import pool_cards  # noqa: E402

OUT = 'results/_s540'
FAMILY = ['XAUUSD_H4', 'XAUUSD_H6', 'XAUUSD_H8', 'XAUUSD_H12']
N_TRIALS = 23755
SPLIT_FRAC = 0.60
C5_MAX_MEMBER_SHARE = 0.50
STEP_NS = 3600 * 1_000_000_000        # ۱ ساعت — ریزتر از ریزترین عضو (H4)
PERM_K = 2000


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _load_card_stats(card):
    """آمار و نولِ اندازه‌گیری‌شدهٔ **موجود** هر کارت — صفر محاسبهٔ جدید."""
    if card == 'XAUUSD_H4':
        with open('results/_s382/null_model.json') as f:
            nm = json.load(f)
        with open('results/_s382_mtf/XAUUSD_H4.json') as f:
            mt = json.load(f)
        lg = nm['null']['long']
        return dict(n_trades=nm['n_trades'], lift=mt['lift'],
                    sl_pip=mt['sl_pip'], tp_pip=mt['tp_pip'],
                    uncond_wr=lg['uncond_wr'], perm_mean=lg['perm_mean'],
                    perm_sd=lg['perm_sd'], perm_max=lg['perm_max'],
                    perm_k=lg['perm_k'])
    with open(f'results/_s520/{card}.json') as f:
        s = json.load(f)
    return dict(n_trades=s['n_trades'], lift=s['lift'], sl_pip=s['sl_pip'],
                tp_pip=s['tp_pip'], uncond_wr=s['uncond_wr'],
                perm_mean=s['perm_mean'], perm_sd=s['perm_sd'],
                perm_max=s['perm_max'], perm_k=PERM_K)


def build_member(L, card):
    """بازتولیدِ معاملاتِ کارت (همان شبیه‌ساز) + نولِ ذخیره‌شده."""
    saved = _load_card_stats(card)
    df = L.load(card)
    # گاردِ BUG-DATASETDRIFT
    print(f"[data] {card}: rows={len(df)} "
          f"range={df['dt'].iloc[0]} .. {df['dt'].iloc[-1]}", flush=True)
    ps = L.pip_size('XAUUSD')
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    tr = L.simulate_trades(df, L.signals(df), sl_abs, L.RR, True, ps)
    assert len(tr) == saved['n_trades'], (
        f"{card}: reproduction mismatch! got {len(tr)} expected "
        f"{saved['n_trades']}")
    null = {'long': dict(uncond_wr=saved['uncond_wr'],
                         perm_mean=saved['perm_mean'],
                         perm_sd=saved['perm_sd'],
                         perm_max=saved['perm_max'], perm_k=saved['perm_k']),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    return dict(card=card, tr=tr, dt=df['dt'].values, lift=saved['lift'],
                n=len(tr), null=null, sl_pip=saved['sl_pip'],
                tp_pip=saved['tp_pip'])


def blend_pool_null(members_used, pool_df):
    """عیناً منطقِ S431/S520: ترکیبِ وزنی با سهمِ پس-از-FIFO."""
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
    os.makedirs(OUT, exist_ok=True)
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')

    def load_mixed(card):
        # H4 در mt5_full نیست؛ از دادهٔ ۱۵.۵سالهٔ اصلی (هم‌فید، مانیفست ۱۰۰٪)
        path = (f'data/{card}.csv' if card == 'XAUUSD_H4'
                else f'data/full/{card}.csv')
        df = pd.read_csv(path)
        df['dt'] = pd.to_datetime(df['time'], unit='s')
        print(f'[src] {path}', flush=True)
        return df

    L.load = load_mixed

    print('== S540-POOL | خانوادهٔ لنگردارِ پیش‌ثبت‌شده ==', flush=True)
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

    # ادای دِینِ قانونِ هم‌پوشانی: سهمِ حذفِ FIFO به تفکیکِ کارت
    kept = pool['src_card'].value_counts().to_dict()
    orig = {m['card']: m['n'] for m in members
            if m['card'] in {u['card'] for u in res['used']}}
    fifo_report = {c: dict(orig=orig.get(c, 0), kept=int(kept.get(c, 0)),
                           removed_pct=round(100 * (1 - kept.get(c, 0) /
                                                    max(orig.get(c, 1), 1)), 1))
                   for c in orig}
    print(f"[هم‌پوشانی/FIFO به تفکیک] "
          f"{json.dumps(fifo_report, ensure_ascii=False)}", flush=True)

    # ---- C5: سهمِ اعضا ----
    share = pool['src_card'].value_counts(normalize=True)
    print(f"\n[C5 سهم] {share.round(3).to_dict()}", flush=True)
    if float(share.max()) > C5_MAX_MEMBER_SHARE:
        print(f"[C5 نقض] {share.idxmax()} سهم {share.max():.1%} > "
              f"{C5_MAX_MEMBER_SHARE:.0%} ⇒ توقف (استخر نامشروع طبقِ "
              f"پیش‌ثبت §۷ — بدونِ دستکاریِ آستانه).", flush=True)
        with open(f'{OUT}/pool_c5_violation.json', 'w') as fh:
            json.dump(dict(share=share.to_dict(), fifo=fifo_report),
                      fh, ensure_ascii=False)
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

    ref = load_mixed_ref()
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

    # ---- تقسیمِ ۶۰/۴۰: صدکِ ۶۰٪ زمانِ ورود ----
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
    print('\n' + rqs2.format_rqs2('S540-POOL', r), flush=True)

    out = dict(members=[dict(card=m['card'], n=m['n'], lift=m['lift'])
                        for m in members],
               used=[u['card'] for u in res['used']], dropped=res['dropped'],
               selection=res['selection'], n_before=res['n_before'],
               n_after=res['n_after'], member_share=share.to_dict(),
               fifo_by_card=fifo_report,
               sl_pip_med=sl_med, tp_pip_med=tp_med, n_trials=N_TRIALS,
               split_frac=SPLIT_FRAC,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'),
               notes=[str(x) for x in (r.get('notes') or [])])
    with open(f'{OUT}/POOL_verdict.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, default=str)
    pool.to_csv(f'{OUT}/POOL_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/POOL_verdict.json + POOL_trades.csv', flush=True)


def load_mixed_ref():
    """closeِ محور از H2ِ کامل — کلِ افق را می‌پوشاند (عیناً S520)."""
    df = pd.read_csv('data/full/XAUUSD_H2.csv')
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


if __name__ == '__main__':
    main()
