# -*- coding: utf-8 -*-
"""
S650 — آزمونِ استخرِ چند-کارتی (نجاتِ رسمیِ POWER-LIMITED) — طبق الحاقیهٔ PREREG
==================================================================================
پیش‌ثبت: research/S650_PREREG.md §5 (کامیت 192330d4) — **پیش از** اجرا.

  • اعضای نامزد: H1, H3, H6, H12, D1 (هر TF با lift>0 در آزمونِ اول).
  • هندسه/پارامترها عیناً جدولِ قفل‌شده — هیچ تغییری.
  • انتخابِ زیرمجموعهٔ همگن با الگوریتمِ رسمیِ `pool_cards` (شرط‌های ۱–۴ ماژول).
  • نولِ استخر = ترکیبِ وزنیِ نول‌های اندازه‌گیری‌شدهٔ اعضا (الگوی S431).
  • n_trials = 18 (۱۷ آزمونِ اول + این) — شمارشِ صادقانهٔ لمس‌ها.
  • این دومین و آخرین لمسِ نیمهٔ دوم است.

الگوها: strategies/s431_lpsb_multicard_pool.py (محورِ مشترک، ماسکِ hold-out،
مدیانِ وزنیِ هندسه) — همان اصلاح‌های BUG-AXIS/BUG-SPAN/BUG-OOS رعایت شده.
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import rqs2                                    # noqa: E402
from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2_pool import pool_cards                    # noqa: E402
from strategies.s650_ehlers_explore import (               # noqa: E402
    _atr_rma_nb, signals, GEO_ATR_P, GEO_SL_K, GEO_RR, GEO_HOLD)
from strategies.s650_final_test import (                   # noqa: E402
    LOCKED, build_null, SEED)
from tools import s434_fast_data as fd                     # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S650')
ASSET = 'XAUUSD'
CANDIDATES = ('H1', 'H3', 'H6', 'H12', 'D1')   # پیش‌ثبت‌شده (lift>0 در آزمون اول)
N_TRIALS = 18                                   # ۱۷ + ۱ — شمارشِ صادقانه
SPLIT_FRAC = 0.70                               # قراردادِ S650 (H7)


def member(tf):
    """معاملاتِ عضو روی نیمهٔ دوم — عیناً همان مسیرِ s650_final_test."""
    pt, pr = LOCKED[tf]
    d = fd.load_fast(ASSET, tf)
    assert 'mt5_full' in d['src'], f"E-16! {d['src']}"
    df_full = fd.as_dataframe(d)
    half = len(df_full) // 2
    df = df_full.iloc[half:].reset_index(drop=True)
    del df_full
    close = df['close'].values.astype(np.float64)
    atr = _atr_rma_nb(df['high'].values.astype(np.float64),
                      df['low'].values.astype(np.float64), close, GEO_ATR_P)
    warmup = max(4 * 89, 4 * GEO_ATR_P, 300)
    ok = np.isfinite(atr) & (atr > 0)
    ls, ss = signals(close, pt, pr)
    ls &= ok
    ss &= ok
    ls[:warmup] = False
    ss[:warmup] = False
    pipv = se.ASSETS[ASSET]['pip']
    sl_arr = GEO_SL_K * atr / pipv
    tr = se.simulate_trades(df, ls, ss, sl_arr, GEO_RR * sl_arr, ASSET,
                            max_hold=GEO_HOLD, allow_overlap=False)
    # نولِ عضو از JSONِ آزمونِ اول خوانده می‌شود (همان بذر/K — بازتولیدپذیر)
    with open(os.path.join(OUT, f'final_{tf}.json')) as f:
        fin = json.load(f)
    lift = fin['metrics'].get('skill_lift_pp')
    # ساختارِ کانونیِ نول از metrics بازیابی نمی‌شود ⇒ بازسازیِ قطعی با همان
    # بذر (650650) و همان تابعِ رسمی — چون rng بذردار است، عیناً همان اعداد.
    valid = np.where(ok)[0]
    valid = valid[(valid >= warmup) & (valid + 1 + GEO_HOLD < len(df))]
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int((tr['direction'] == 'short').sum())
    rng = np.random.default_rng(SEED)
    null = build_null(df, atr, valid, n_long, n_short, rng)
    dt = pd.to_datetime(df['time'], unit='s').values
    sl_med = float(np.median(tr['sl_pip'].values))
    return dict(card=tf, tr=tr, dt=dt, lift=float(lift), null=null,
                sl_pip=sl_med, tp_pip=GEO_RR * sl_med,
                n=len(tr), verdict=fin['verdict'])


def blend_pool_null(members_used, pool_df):
    """عیناً الگوی S431 — وزن با سهمِ پس-از-FIFO."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
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
    t0 = time.time()
    print(f"== S650-POOL — اعضای نامزد: {CANDIDATES} · n_trials={N_TRIALS} ==",
          flush=True)
    members = []
    for tf in CANDIDATES:
        m = member(tf)
        print(f"   {tf}: n={m['n']} lift={m['lift']} ({m['verdict']})",
              flush=True)
        members.append(m)

    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                           lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] هیچ عضوِ معتبری نماند.', flush=True)
        return
    pool = res['pool']
    print(f"\n[انتخابِ همگن] used={[u['card'] for u in res['used']]} "
          f"dropped={[(x['card'], x['reason']) for x in res['dropped']]} "
          f"n_before={res['n_before']} n_after={res['n_after']}", flush=True)

    used = [m for m in members
            if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used, pool)
    print(f"[نولِ استخر] {json.dumps(null, ensure_ascii=False)}", flush=True)

    # هندسهٔ وزنی (سهمِ پس-از-FIFO) — الگوی S431
    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by = {m['card']: m for m in used}
    sl_med = float(sum(by[c]['sl_pip'] * w for c, w in shares.items() if c in by))
    tp_med = float(sum(by[c]['tp_pip'] * w for c, w in shares.items() if c in by))

    # محورِ مشترک: شبکهٔ ساعتی (ریزترین عضو H1) روی کلِ افقِ استخر — ضد BUG-SPAN
    STEP_NS = 3600 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    # closeِ هم‌راستا از H1 (کلِ افقِ نیمهٔ دوم را دارد) — بدونِ نگاهِ آینده
    dh1 = fd.load_fast(ASSET, 'H1')
    ref_t = pd.to_datetime(dh1['time'], unit='s').values.astype(np.int64)
    ref_c = dh1['close'].astype(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_entry'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_exit'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # ماسکِ hold-out روی صدکِ ۷۰٪ زمانِ ورود (ضد BUG-SPLITDIR — نسبتِ نمونه)
    te = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te, SPLIT_FRAC))
    holdout = te >= split_ns
    print(f"[تقسیم {SPLIT_FRAC:.0%}] مرز={np.datetime64(split_ns, 'ns')} · "
          f"اکتشاف={int((~holdout).sum())} · OOS={int(holdout.sum())}",
          flush=True)

    r = rqs2.compute_rqs2(pool, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=axis_dt, close=axis_close, null=null,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S650-POOL', r), flush=True)

    out = dict(layer='S650-POOL', asset=ASSET,
               candidates=list(CANDIDATES),
               used=[u['card'] for u in res['used']],
               dropped=res['dropped'], selection=res['selection'],
               n_before=res['n_before'], n_after=res['n_after'],
               member_stats=[dict(card=m['card'], n=m['n'], lift=m['lift'])
                             for m in members],
               sl_pip_w=sl_med, tp_pip_w=tp_med,
               n_trials=N_TRIALS, seed=SEED,
               verdict=r['verdict'], rqs2_score=r['rqs2_score'],
               gates=r['gates'], metrics=r['metrics'], notes=r['notes'],
               elapsed_s=round(time.time() - t0, 1))
    fp = os.path.join(OUT, 'final_POOL.json')
    with open(fp, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"✔ saved {fp}", flush=True)


if __name__ == '__main__':
    main()
