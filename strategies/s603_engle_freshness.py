# -*- coding: utf-8 -*-
"""
S603 — تازگیِ شوکِ انگل روی استخرِ ACCEPTشده‌ی S602 {D1,H8}
================================================================================
پیش‌ثبت: results/S603_PREREG_ENGLE_SHOCK_FRESHNESS.md (commit ea52778b — قبل از
هر محاسبه). خلاصه‌ی عهد:

  · ماده‌ی فریز: دو عضوِ S602 (برندگانِ منجمدِ S840). سنجه‌ی سلامت بیت‌به‌بیت.
  · گیتِ تازگی روی سیگنال (قبل از FIFO): رویدادِ i «FRESH» اگر در m کندلِ
    قبل هیچ |z|≥z_thr نبوده باشد؛ وگرنه «ECHO».
  · شبکه: m∈{3,5,8,13,21} × {FRESH,ECHO} = ۱۰ پیکربندی — کشف فقط روی
    ورودهای قبل از مرزِ خانواده (S602 split 2020-01-06T17:36).
  · انتخاب: بیشینه‌ی z_proxy=lift·√n در کشف، قید n_disc≥60.
  · داوری نهایی یک‌باره: n_trials=5147 (+ تنش 8000)، نولِ منجمدِ S840
    وزنی به سهمِ پس‌ازFIFO، محور H1 مصنوعی، holdout=صدک60% زمانِ ورود.
  · SEED=20260819. هیچ monkey-patch. حکم فقط از compute_rqs2 v2.6.

اجرا: python3 strategies/s603_engle_freshness.py
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
MEMBERS = ['D1', 'H8']
SEED = 20260819
N_TRIALS = 5147
N_TRIALS_STRESS = 8000
M_GRID = (3, 5, 8, 13, 21)
ARMS = ('FRESH', 'ECHO')
MIN_N_DISC = 60
SPLIT_FRAC = 0.60
OUT = 'results/_s603_freshness'
SCAN = 'results/_scan_S840'
# مرزِ کشفِ خانواده — عینِ S602 (pool_verdict.json: split_utc)
FAMILY_SPLIT = np.datetime64('2020-01-06T17:36:00.000000000')

EXPECTED = {'D1': dict(n=87, wr=64.37), 'H8': dict(n=337, wr=58.75)}


def load_member_raw(tf):
    """بارِ خام کارت: z، atr، df، برنده‌ی منجمد، نولِ منجمد."""
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
    return dict(tf=tf, df=df, z=z, atr=atr, w=w, warmup=warmup,
                null=ck['null'], hold=TF_HOLD[tf], dt=dt)


def base_trades(m):
    """بازتولید بیت‌به‌بیت (سنجه‌ی سلامت)."""
    w = m['w']
    sig, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    st = queue_frozen(m['df'], sig, isl, w['sl_k'] * m['atr'][sig],
                      m['hold'], w['rr'])
    tr = trades_from_st(st)
    n, wr = len(tr), float((tr['pnl_pip'] > 0).mean() * 100)
    exp = EXPECTED[m['tf']]
    ok = (n == exp['n']) and abs(wr - exp['wr']) < 0.01
    print(f"-- {m['tf']}: n={n} WR={wr:.2f} vs expected "
          f"{exp['n']}/{exp['wr']} ⇒ {'✅' if ok else '❌'}", flush=True)
    if not ok:
        raise RuntimeError(f'health gate failed for {m["tf"]}')
    return sig


def gated_member(m, mm, arm):
    """اعمالِ گیتِ تازگی روی سیگنال، سپس صف/معاملاتِ منجمد."""
    w = m['w']
    sig, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'], m['warmup'])
    # رویدادِ خام: |z|>=z_thr (پایه‌ی تعریفِ تازگی — مستقل از mode)
    ev = np.abs(np.nan_to_num(m['z'])) >= w['z_thr']
    idx = np.where(sig)[0]
    keep = np.zeros(len(sig), bool)
    for i in idx:
        lo = max(0, i - mm)
        fresh = not ev[lo:i].any()
        if (arm == 'FRESH') == fresh:
            keep[i] = True
    isl2 = isl[keep[sig]] if isl is not None else None
    if keep.sum() < 5:
        return None
    st = queue_frozen(m['df'], keep, isl2, m['w']['sl_k'] * m['atr'][keep],
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
                n=n, wr=wr, lift=wr - ref, null=m['null'],
                sl_pip=float(np.median(tr['sl_pip'])),
                tp_pip=float(np.median(tr['tp_pip'])))


def build_pool(gms):
    res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'],
                              lift=g['lift']) for g in gms])
    if res is None:
        return None
    return res


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


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f'== S603 تازگیِ شوک · grid={len(M_GRID)}×{len(ARMS)} · '
          f'seed={SEED} · n_trials={N_TRIALS} ==', flush=True)
    raws = [load_member_raw(tf) for tf in MEMBERS]
    for m in raws:
        base_trades(m)  # سنجه‌ی سلامت

    # ---------------- اکتشاف: فقط ورودهای قبل از مرزِ خانواده ----------------
    rows = []
    for mm in M_GRID:
        for arm in ARMS:
            gms = [g for g in (gated_member(m, mm, arm) for m in raws)
                   if g is not None]
            if not gms:
                rows.append(dict(m=mm, arm=arm, note='no members'))
                continue
            res = build_pool(gms)
            if res is None:
                rows.append(dict(m=mm, arm=arm, note='pool empty'))
                continue
            pool = res['pool']
            te = pd.to_datetime(pool['t_entry'].values).values \
                .astype('datetime64[ns]')
            disc = pool[te < FAMILY_SPLIT]
            n_d = len(disc)
            if n_d < MIN_N_DISC:
                rows.append(dict(m=mm, arm=arm, n_disc=n_d, note='underpowered'))
                print(f'm={mm:>2} {arm:<5} n_disc={n_d} — کم‌توان', flush=True)
                continue
            null = blend_null(gms, disc)
            n_long = int((disc['direction'] == 'long').sum())
            ref = ((null['long']['perm_mean'] or 0) * n_long +
                   (null['short']['perm_mean'] or 0) * (n_d - n_long)) / n_d
            wr_d = float((disc['pnl_pip'] > 0).mean() * 100)
            lift_d = wr_d - ref
            zp = lift_d * np.sqrt(n_d)
            rows.append(dict(m=mm, arm=arm, n_disc=n_d, wr_disc=round(wr_d, 2),
                             ref=round(ref, 2), lift_disc=round(lift_d, 2),
                             z_proxy=round(zp, 1),
                             n_full=len(pool)))
            print(f'm={mm:>2} {arm:<5} n_disc={n_d:>3} WR={wr_d:5.2f} '
                  f'lift={lift_d:+5.2f} z_proxy={zp:7.1f} (full n={len(pool)})',
                  flush=True)

    json.dump(rows, open(f'{OUT}/explore_grid.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    valid = [r for r in rows if 'z_proxy' in r]
    # مرجعِ مقایسه: خودِ S602 (بدون گیت) در کشف
    if not valid:
        print('\n[نتیجه] هیچ پیکربندیِ باتوان — REJECT در اکتشاف؛ '
              'holdout بکر ماند.', flush=True)
        print('FINISHED-EXPLORE-EMPTY', flush=True)
        return

    best = max(valid, key=lambda r: r['z_proxy'])
    print(f"\n[برنده‌ی کشف] m={best['m']} {best['arm']} "
          f"z_proxy={best['z_proxy']}", flush=True)

    # ---- مرجعِ بدونِ گیت (S602) در کشف برای مقایسه‌ی P1 (فقط گزارشی) ----
    gms_all = []
    for m in raws:
        w = m['w']
        sig, isl = signals_for(m['z'], m['atr'], w['z_thr'], w['mode'],
                               m['warmup'])
        st = queue_frozen(m['df'], sig, isl, w['sl_k'] * m['atr'][sig],
                          m['hold'], w['rr'])
        tr = trades_from_st(st)
        n = len(tr)
        n_long = int((tr['direction'] == 'long').sum())
        ref = ((m['null']['long']['perm_mean'] or 0) * n_long +
               (m['null']['short']['perm_mean'] or 0) * (n - n_long)) / n
        gms_all.append(dict(card=f'{ASSET}-{m["tf"]}', tf=m['tf'], tr=tr,
                            dt=m['dt'], n=n,
                            wr=float((tr['pnl_pip'] > 0).mean() * 100),
                            lift=float((tr['pnl_pip'] > 0).mean() * 100 - ref),
                            null=m['null'],
                            sl_pip=float(np.median(tr['sl_pip'])),
                            tp_pip=float(np.median(tr['tp_pip']))))
    res0 = build_pool(gms_all)
    pool0 = res0['pool']
    te0 = pd.to_datetime(pool0['t_entry'].values).values \
        .astype('datetime64[ns]')
    d0 = pool0[te0 < FAMILY_SPLIT]
    wr0 = float((d0['pnl_pip'] > 0).mean() * 100)
    print(f'[مرجع S602 در کشف] n={len(d0)} WR={wr0:.2f}', flush=True)

    # ---------------- داوری نهایی: برنده روی کل داده ----------------
    gms = [g for g in (gated_member(m, best['m'], best['arm']) for m in raws)
           if g is not None]
    res = build_pool(gms)
    pool = res['pool']
    share = pool['src_card'].value_counts(normalize=True)
    null = blend_null(gms, pool)
    by = {g['card']: g for g in gms}
    sl_med = float(sum(by[c]['sl_pip'] * w for c, w in share.items()))
    tp_med = float(sum(by[c]['tp_pip'] * w for c, w in share.items()))
    fifo_cut = 100 * (1 - res['n_after'] / max(res['n_before'], 1))
    print(f'[نهایی] n={len(pool)} (FIFO cut {fifo_cut:.1f}%) '
          f'shares={share.round(3).to_dict()} SL=TP={sl_med:.1f}', flush=True)

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
    print(f'[split] {np.datetime64(split_ns, "ns")} disc={int((~holdout).sum())} '
          f'hold={int(holdout.sum())}', flush=True)

    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt, null=null,
                  close=axis_close, holdout_mask=holdout, allow_overlap=False)
    r = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS, **common)
    r_st = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print('\n' + R2.format_rqs2('S603-FRESH OFFICIAL', r), flush=True)
    print(R2.format_rqs2(f'S603-FRESH STRESS({N_TRIALS_STRESS})', r_st),
          flush=True)

    def _slim(rr_):
        m_ = rr_.get('metrics', {})
        return dict(verdict=rr_.get('verdict'), rqs2_score=rr_.get('rqs2_score'),
                    gates=rr_.get('gates'), notes=rr_.get('notes'),
                    metrics={k: m_[k] for k in m_ if isinstance(
                        m_[k], (int, float, str, bool, type(None)))})

    out = dict(session='S603',
               prereg='results/S603_PREREG_ENGLE_SHOCK_FRESHNESS.md',
               winner=dict(m=best['m'], arm=best['arm']),
               explore=rows, reference_s602_disc=dict(n=len(d0),
                                                      wr=round(wr0, 2)),
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(fifo_cut, 2),
               member_share=share.round(4).to_dict(),
               sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, seed=SEED, n_trials=N_TRIALS,
               n_trials_stress=N_TRIALS_STRESS,
               split_utc=str(np.datetime64(split_ns, 'ns')),
               official=_slim(r), stress=_slim(r_st),
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'))
    json.dump(out, open(f'{OUT}/verdict.json', 'w'),
              ensure_ascii=False, indent=1, default=str)
    print(f'[saved] {OUT}/verdict.json', flush=True)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
