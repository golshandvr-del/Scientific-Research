# -*- coding: utf-8 -*-
"""
S604 — شوکِ انگلِ هم‌راستا با روند (drift-aligned) — احیای H12/H6 + تقویت استخر
================================================================================
پیش‌ثبت: results/S604_PREREG_ENGLE_SHOCK_DRIFT_ALIGNED.md (commit 0af0632d —
قبل از هر محاسبه). خلاصه‌ی عهد:

  · گیتِ دریفتِ علّی: drift(t)=close[t-1]-close[t-1-K]؛ long⇔drift>0،
    short⇔drift<0. K معادل {30,60,90} روز تقویمی به کندلِ کارت
    (D1:K=k · H12:2k · H8:3k · H6:4k).
  · کشف فقط قبل از مرز خانواده 2020-01-06T17:36.
  · احیا: n_disc>=60 و lift_disc >= lift خام همان کارت +2pp.
  · استخر: {D1خام, H8خام} ∪ احیاشده‌ها؛ انتخاب‌گر رسمی margin=0.15 +
    وتوی پس‌ازFIFO (سهم قوی‌ترین <10% ⇒ حذف ضعیف‌ترین، تکرار).
  · داوری: n_trials=5163 + تنش 8000، نول منجمد S840، SEED=20260820.

اجرا: python3 strategies/s604_engle_drift.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from engine import rqs2 as R2
import engine.rqs2_pool as rp
from tools import s434_fast_data as fd
from strategies.s840_engle_shock import (
    atr_series, ewma_z, signals_for, queue_frozen, trades_from_st, TF_HOLD)

import warnings
warnings.filterwarnings('ignore')

ASSET = 'XAUUSD'
CARDS = ['D1', 'H8', 'H12', 'H6']
RAW_POOL = ['D1', 'H8']                     # اعضای ACCEPT والد (بدون گیت)
K_DAYS = (30, 60, 90)
BARS_PER_DAY = {'D1': 1, 'H12': 2, 'H8': 3, 'H6': 4}
SEED = 20260820
N_TRIALS = 5163
N_TRIALS_STRESS = 8000
MIN_N_DISC = 60
REVIVE_LIFT_GAIN = 2.0
SPLIT_FRAC = 0.60
OUT = 'results/_s604_drift'
SCAN = 'results/_scan_S840'
FAMILY_SPLIT = np.datetime64('2020-01-06T17:36:00.000000000')

EXPECTED = {'D1': dict(n=87, wr=64.37), 'H8': dict(n=337, wr=58.75),
            'H12': dict(n=450, wr=55.11), 'H6': dict(n=470, wr=50.43)}


def load_raw(tf):
    ck = json.load(open(os.path.join(SCAN, f'{tf}.json')))
    w = ck['is_winner']
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    warmup = 250 if len(df) >= 5000 else max(60, len(df) // 10)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    z, _ = ewma_z(cl)
    dt = (pd.to_datetime(df['time'].values, unit='s', utc=True)
          .tz_localize(None).values.astype('datetime64[ns]'))
    return dict(tf=tf, df=df, cl=cl, z=z, atr=atr, w=w, warmup=warmup,
                null=ck['null'], hold=TF_HOLD[tf], dt=dt)


def member_from_idx(m, idx, isl):
    """صف/معاملات منجمد + متریک‌های عضو از اندیس‌های داده‌شده."""
    if len(idx) < 5:
        return None
    st = queue_frozen(m['df'], idx, isl, m['w']['sl_k'] * m['atr'][idx],
                      m['hold'], m['w']['rr'])
    if st is None or st['n'] < 5:
        return None
    tr = trades_from_st(st)
    n = len(tr)
    n_long = int((tr['direction'] == 'long').sum())
    ref = ((m['null']['long']['perm_mean'] or 0) * n_long +
           (m['null']['short']['perm_mean'] or 0) * (n - n_long)) / n
    wr = float((tr['pnl_pip'] > 0).mean() * 100)
    return dict(card=f'{ASSET}-{m["tf"]}', tf=m['tf'], tr=tr, dt=m['dt'],
                n=n, wr=round(wr, 2), lift=round(wr - ref, 4), null=m['null'],
                sl_pip=float(np.median(tr['sl_pip'])),
                tp_pip=float(np.median(tr['tp_pip'])))


def raw_member(m, health=True):
    w = m['w']
    idx, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    g = member_from_idx(m, idx, isl)
    if health:
        exp = EXPECTED[m['tf']]
        ok = g and g['n'] == exp['n'] and abs(g['wr'] - exp['wr']) < 0.01
        print(f"-- {m['tf']} raw: n={g['n'] if g else 0} "
              f"WR={g['wr'] if g else 0:.2f} vs {exp['n']}/{exp['wr']} "
              f"⇒ {'✅' if ok else '❌'}", flush=True)
        if not ok:
            raise RuntimeError(f'health gate failed: {m["tf"]}')
    return g


def drift_member(m, k_days):
    """گیتِ دریفتِ علّی روی سیگنالِ منجمد."""
    w = m['w']
    K = k_days * BARS_PER_DAY[m['tf']]
    idx, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    cl = m['cl']
    keep = []
    for j, i in enumerate(idx):
        if i - 1 - K < 0:
            continue
        drift = cl[i - 1] - cl[i - 1 - K]
        want_long = bool(isl[j])
        if (want_long and drift > 0) or ((not want_long) and drift < 0):
            keep.append(j)
    if len(keep) < 5:
        return None
    return member_from_idx(m, idx[keep], isl[keep])


def disc_stats(g):
    """متریکِ کشف (قبل از مرز خانواده) روی معاملاتِ عضو."""
    te = pd.to_datetime(g['tr']['t_entry'] if 't_entry' in g['tr'] else
                        g['dt'][g['tr']['entry_bar'].values.astype(int)])
    te = np.asarray(te).astype('datetime64[ns]')
    mask = te < FAMILY_SPLIT
    n_d = int(mask.sum())
    if n_d == 0:
        return 0, 0.0, 0.0
    pnl = g['tr']['pnl_pip'].values[mask]
    dirs = g['tr']['direction'].values[mask]
    n_long = int((dirs == 'long').sum())
    ref = ((g['null']['long']['perm_mean'] or 0) * n_long +
           (g['null']['short']['perm_mean'] or 0) * (n_d - n_long)) / n_d
    wr = float((pnl > 0).mean() * 100)
    return n_d, wr, wr - ref


def blend_null(gms, pool_df):
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        nu = du = nm = ns = dp = 0.0
        kmin = None
        for g in gms:
            wgt = float(share.get(g['card'], 0.0))
            if wgt <= 0:
                continue
            d = g['null'][side]
            if d.get('uncond_wr') is not None:
                nu += d['uncond_wr'] * wgt
                du += wgt
            if d.get('perm_mean') is not None:
                nm += d['perm_mean'] * wgt
                ns += (d['perm_sd'] ** 2) * (wgt ** 2)
                dp += wgt
                k = d.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(uncond_wr=nu / du if du else None,
                         perm_mean=nm / dp if dp else None,
                         perm_sd=float(np.sqrt(ns)) / dp if dp else None,
                         perm_max=None, perm_k=kmin)
    return out


def adjudicate(pool, gms, tag):
    share = pool['src_card'].value_counts(normalize=True)
    null = blend_null(gms, pool)
    by = {g['card']: g for g in gms}
    sl_med = float(sum(by[c]['sl_pip'] * w for c, w in share.items()))
    tp_med = float(sum(by[c]['tp_pip'] * w for c, w in share.items()))

    STEP = 3600 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP, t_hi + 2 * STEP, STEP, dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    d1h = fd.load_fast(ASSET, 'H1')
    ref_t = (pd.to_datetime(d1h['time'], unit='s', utc=True)
             .tz_localize(None).values.astype('datetime64[ns]')
             .astype(np.int64))
    ref_c = d1h['close'].astype(float)
    axis_close = ref_c[np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1,
                               0, len(ref_c) - 1)]
    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(
        axis_t, pool['t_entry'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(np.clip(np.searchsorted(
        axis_t, pool['t_exit'].values.astype(np.int64), 'left'),
        0, len(axis_t) - 1), pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt, null=null,
                  close=axis_close, holdout_mask=holdout, allow_overlap=False)
    r = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS, **common)
    r_st = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print('\n' + R2.format_rqs2(f'{tag} OFFICIAL', r), flush=True)
    print(R2.format_rqs2(f'{tag} STRESS({N_TRIALS_STRESS})', r_st), flush=True)
    return r, r_st, null, sl_med, tp_med, str(np.datetime64(split_ns, 'ns')), \
        share, holdout


def _slim(rr_):
    m_ = rr_.get('metrics', {})
    return dict(verdict=rr_.get('verdict'), rqs2_score=rr_.get('rqs2_score'),
                gates=rr_.get('gates'), notes=rr_.get('notes'),
                metrics={k: m_[k] for k in m_ if isinstance(
                    m_[k], (int, float, str, bool, type(None)))})


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== S604 drift-aligned Engle · K={K_DAYS} days · seed={SEED} '
          f'n_trials={N_TRIALS} ==', flush=True)
    raws = {tf: load_raw(tf) for tf in CARDS}
    raw_g = {tf: raw_member(raws[tf]) for tf in CARDS}

    # ---------------- گام ۱: کشفِ احیا (هر کارت × K) ----------------
    explore = []
    revived = {}
    for tf in CARDS:
        n_raw_d, wr_raw_d, lift_raw_d = disc_stats(raw_g[tf])
        print(f'[{tf}] raw disc: n={n_raw_d} WR={wr_raw_d:.2f} '
              f'lift={lift_raw_d:+.2f}', flush=True)
        best = None
        for k in K_DAYS:
            g = drift_member(raws[tf], k)
            if g is None:
                explore.append(dict(tf=tf, K=k, note='too few'))
                continue
            n_d, wr_d, lift_d = disc_stats(g)
            row = dict(tf=tf, K=k, n_full=g['n'], n_disc=n_d,
                       wr_disc=round(wr_d, 2), lift_disc=round(lift_d, 2),
                       lift_raw_disc=round(lift_raw_d, 2))
            explore.append(row)
            print(f'  K={k:>2}d: n_disc={n_d:>3} WR={wr_d:5.2f} '
                  f'lift={lift_d:+5.2f} (raw {lift_raw_d:+.2f})', flush=True)
            ok = n_d >= MIN_N_DISC and lift_d >= lift_raw_d + REVIVE_LIFT_GAIN
            if ok and (best is None or lift_d > best[1]):
                best = (k, lift_d, g)
        if best:
            revived[tf] = dict(K=best[0], g=best[2])
            print(f'  ⇒ {tf} REVIVED با K={best[0]}d', flush=True)
        else:
            print(f'  ⇒ {tf}: احیا نشد (P2)', flush=True)
    json.dump(explore, open(f'{OUT}/explore_grid.json', 'w'),
              ensure_ascii=False, indent=1, default=str)

    # ---------------- گام ۲: ترکیب استخر + وتوی پس‌ازFIFO ----------------
    members = [raw_g[tf] for tf in RAW_POOL]
    for tf, rv in revived.items():
        if tf in RAW_POOL:
            continue  # عضو خام والد مقدم است؛ نسخه‌ی گیت‌خورده اضافه نمی‌شود
        members.append(rv['g'])
    print(f'\n[استخر نامزد] {[m["card"] for m in members]} '
          f'lifts={[m["lift"] for m in members]}', flush=True)

    trace_veto = []
    while True:
        res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'],
                                  lift=g['lift']) for g in members])
        if res is None:
            print('[توقف] pool تهی.', flush=True)
            return
        pool = res['pool']
        share = pool['src_card'].value_counts(normalize=True)
        used = [g for g in members if g['card'] in set(pool['src_card'])]
        strongest = max(used, key=lambda g: g['lift'])
        s_share = float(share.get(strongest['card'], 0.0))
        print(f'[FIFO shares] {share.round(3).to_dict()} · '
              f'strongest={strongest["card"]} share={s_share:.3f}', flush=True)
        if s_share >= 0.10 or len(used) <= 2:
            break
        weakest = min(used, key=lambda g: g['lift'])
        trace_veto.append(dict(removed=weakest['card'],
                               strongest_share=round(s_share, 4)))
        print(f'[وتوی پس‌ازFIFO] حذف {weakest["card"]} — تکرار انتخاب',
              flush=True)
        members = [g for g in members if g['card'] != weakest['card']]

    fifo_cut = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f'[نهایی] members={[g["card"] for g in used]} n={len(pool)} '
          f'(FIFO cut {fifo_cut:.1f}%)', flush=True)

    r, r_st, null, sl_med, tp_med, split_utc, share, holdout = \
        adjudicate(pool, used, 'S604-DRIFT')

    out = dict(session='S604',
               prereg='results/S604_PREREG_ENGLE_SHOCK_DRIFT_ALIGNED.md',
               revived={tf: rv['K'] for tf, rv in revived.items()},
               explore=explore, veto_trace=trace_veto,
               members=[dict(card=g['card'], n=g['n'], wr=g['wr'],
                             lift=g['lift']) for g in used],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED, n_trials=N_TRIALS,
               n_trials_stress=N_TRIALS_STRESS, split_utc=split_utc,
               official=_slim(r), stress=_slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    json.dump(out, open(f'{OUT}/verdict.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print(f'[saved] {OUT}/verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
