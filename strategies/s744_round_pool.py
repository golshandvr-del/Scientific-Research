#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S744 — ادغامِ چندکارتهٔ «ردِ سطحِ رند» (Round-Level Pool) — XAUUSD
================================================================================
پیش‌ثبت: results/S744_PREREG_ROUND_LEVEL_POOL_PATH_C.md (کامیت پیش از این کد)
رویدادِ منجمد: s743.build_signals(step=50, rej_k=0.25)
اعضای منجمد: H2,H3,H6,H8,H12,D1 (W1 و M5 قرنطینهٔ ابدی)
شبکه: K_SL∈{1.5,2.5} × RR∈{1.0,1.5} = ۴ پیکربندی · n_trials=48
اجرا: python3 strategies/s744_round_pool.py [--kperm 500]
"""
import sys
import os
import json
import time as _time
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import s434_fast_data as fd                              # noqa: E402
from engine import rqs2                                             # noqa: E402
import engine.rqs2_pool as rp                                       # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies import s740_absorption as s740                      # noqa: E402
from strategies import s743_round_level as s743                     # noqa: E402

ASSET = 'XAUUSD'
MEMBERS = ('H2', 'H3', 'H6', 'H8', 'H12', 'D1')   # منجمد در پیش‌ثبت
STEP, REJ_K = 50.0, 0.25                          # رویدادِ منجمد
K_SL_GRID = (1.5, 2.5)
RR_GRID = (1.0, 1.5)
N_TRIALS = 48                                     # 24 موروثی + 24 جدید
HOLD = 16
SPLIT_FRAC = 0.60
MIN_N_POOL = 60
MIN_PF_POOL = 1.3
SEED = 744

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S744')


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)


def _save(out, name='pool.json'):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=_default)


def load_member(tf):
    """بارگذاریِ کارت + ATR + محورِ زمان (ثانیهٔ epoch و datetime64)."""
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    atr = s740.atr_plain(df['high'].values, df['low'].values,
                         df['close'].values)
    t_sec = np.asarray(d['time'], dtype=np.int64)
    dt = t_sec.astype('datetime64[s]').astype('datetime64[ns]')
    return dict(tf=tf, d=d, df=df, atr=atr, t_sec=t_sec, dt=dt)


def member_trades(m, k_sl, rr, until_sec=None):
    """معاملاتِ یک عضو با رویدادِ منجمد؛ در صورتِ until_sec فقط تا آن مرز."""
    df, atr = m['df'], m['atr']
    if until_sec is not None:
        idx = int(np.searchsorted(m['t_sec'], until_sec, 'left'))
        df = df.iloc[:idx]
        atr = atr[:idx]
        if len(df) < 300:
            return None
    sig, is_long = s743.build_signals(df, atr, STEP, REJ_K)
    if len(sig) < 3:
        return None
    st = queue_rr(df, sig, is_long, k_sl * atr[sig], ASSET, HOLD, rr)
    if st is None or st['n'] < 3:
        return None
    return st


def geo_lift(st, c_pip):
    """lift هندسی (WR − آستانهٔ سربه‌سرِ هزینه‌دار) — فقط برای اکتشاف/گزینش."""
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    be = rqs2.breakeven_wr_cost(sl_med, tp_med, c_pip)
    return float(st['wr'] - be), sl_med, tp_med, be


def build_pool(entries, force_all=False):
    """pool_cards با امکانِ درجِ همهٔ اعضای liftِ مثبت (آزمونِ نهاییِ منجمد)."""
    if not force_all:
        return rp.pool_cards(entries)
    orig = rp.choose_homogeneous_subset
    try:
        rp.choose_homogeneous_subset = (
            lambda c, add_margin=None: orig(c, add_margin=-1.0))
        return rp.pool_cards(entries)
    finally:
        rp.choose_homogeneous_subset = orig


def pool_stats(pool, members_st, c_pip):
    """آمارِ استخر: WR/PF/exp + هندسهٔ وزنی به سهمِ پس-از-FIFO + z اکتشافی."""
    share = pool['src_card'].value_counts(normalize=True).to_dict()
    sl_med = sum(members_st[c]['sl_med'] * w for c, w in share.items())
    tp_med = sum(members_st[c]['tp_med'] * w for c, w in share.items())
    be = rqs2.breakeven_wr_cost(sl_med, tp_med, c_pip)
    pnl = pool['pnl_pip'].values.astype(float)
    n = len(pool)
    wr = 100.0 * float((pnl > 0).mean())
    wins = pnl[pnl > 0].sum()
    loss = -pnl[pnl <= 0].sum()
    pf = float(wins / loss) if loss > 0 else float('inf')
    lift = wr - be
    p0 = be / 100.0
    se = 100.0 * np.sqrt(max(p0 * (1 - p0), 1e-9) / max(n, 1))
    z = lift / se if se > 0 else None
    return dict(n=n, wr=round(wr, 2), pf=round(pf, 3),
                exp=round(float(pnl.mean()), 2), be=round(be, 2),
                lift=round(lift, 2), z=round(z, 3) if z is not None else None,
                sl_med=round(sl_med, 2), tp_med=round(tp_med, 2),
                share={k: round(v, 3) for k, v in share.items()})


def main(k_perm=500):
    t0 = _time.time()
    rng = np.random.default_rng(SEED)
    c_pip = cost_pip(ASSET)
    out = dict(strategy='S744_RoundLevelPool', asset=ASSET,
               members=list(MEMBERS), step=STEP, rej_k=REJ_K,
               n_trials=N_TRIALS, k_perm=k_perm,
               prereg='results/S744_PREREG_ROUND_LEVEL_POOL_PATH_C.md')

    print(f"== S744 ROUND-LEVEL POOL :: {ASSET} · members={MEMBERS} · "
          f"event=(step={STEP}, rej_k={REJ_K}) · grid={len(K_SL_GRID)*len(RR_GRID)} "
          f"· N_TRIALS={N_TRIALS} · cost={c_pip:.2f}pip", flush=True)

    cards = {tf: load_member(tf) for tf in MEMBERS}
    for tf, m in cards.items():
        print(f"   {tf}: bars={len(m['df']):,} src={m['d']['src']} "
              f"span={m['d']['span_years']:.2f}y", flush=True)
        out.setdefault('cards', {})[tf] = dict(
            bars=int(len(m['df'])), src=m['d']['src'],
            span_years=round(float(m['d']['span_years']), 2))

    # مرزِ تقویمیِ مشترک: کندلِ 60٪ کارتِ H2 (پیش‌ثبت §4)
    h2 = cards['H2']
    split_idx = int(SPLIT_FRAC * len(h2['df']))
    T_star = int(h2['t_sec'][split_idx])
    out['T_star_utc'] = str(np.datetime64(T_star, 's'))
    print(f"\n[مرزِ اکتشاف/خارج‌نمونه] T*={out['T_star_utc']} "
          f"(کندلِ {split_idx:,} از H2)", flush=True)

    # ------------------------- اکتشاف (فقط < T*) -------------------------
    print("\n---------- فازِ اکتشاف ----------", flush=True)
    explore = []
    for k_sl in K_SL_GRID:
        for rr in RR_GRID:
            entries, mstats = [], {}
            for tf in MEMBERS:
                st = member_trades(cards[tf], k_sl, rr, until_sec=T_star)
                if st is None:
                    continue
                lift, sl_med, tp_med, be = geo_lift(st, c_pip)
                mstats[tf] = dict(n=int(st['n']), wr=round(st['wr'], 2),
                                  pf=round(st['pf'], 3), lift=round(lift, 2),
                                  sl_med=sl_med, tp_med=tp_med, be=round(be, 2))
                entries.append(dict(card=tf, tr=trades_df(st),
                                    dt=cards[tf]['dt'], lift=lift))
            row = dict(k_sl=k_sl, rr=rr, members=mstats, pool=None)
            res = rp.pool_cards(entries) if entries else None
            if res is not None:
                ps = pool_stats(res['pool'], mstats, c_pip)
                ps['used'] = [u['card'] for u in res['used']]
                ps['dropped'] = res['dropped']
                row['pool'] = ps
                print(f"  k_sl={k_sl} rr={rr} → used={ps['used']} "
                      f"n={ps['n']} wr={ps['wr']} pf={ps['pf']} "
                      f"lift={ps['lift']} z={ps['z']}", flush=True)
            else:
                print(f"  k_sl={k_sl} rr={rr} → استخر ساخته نشد", flush=True)
            explore.append(row)
            _save(dict(out, explore=explore), 'pool.json')

    out['explore'] = explore
    cand = [r for r in explore if r['pool'] is not None
            and r['pool']['z'] is not None
            and r['pool']['n'] >= MIN_N_POOL
            and r['pool']['pf'] >= MIN_PF_POOL]
    if not cand:
        out['verdict'] = 'NO_CANDIDATE'
        _save(out)
        print("\n[نتیجه] هیچ پیکربندی‌ای واجدِ آستانهٔ اکتشاف نشد ⇒ "
              "NO_CANDIDATE — راهبرد بسته شد.", flush=True)
        return out

    win = max(cand, key=lambda r: r['pool']['z'])
    frozen_members = list(win['pool']['used'])
    out['winner'] = dict(k_sl=win['k_sl'], rr=win['rr'],
                         members=frozen_members, disc=win['pool'])
    print(f"\n[برنده] k_sl={win['k_sl']} rr={win['rr']} "
          f"members={frozen_members} z={win['pool']['z']}", flush=True)
    _save(out)

    # --------------------- آزمونِ نهاییِ منجمدِ یگانه ---------------------
    print("\n---------- آزمونِ نهاییِ منجمد (کلِ داده) ----------", flush=True)
    k_sl, rr = win['k_sl'], win['rr']
    entries, mstats, nulls = [], {}, {}
    for tf in frozen_members:
        m = cards[tf]
        st = member_trades(m, k_sl, rr)          # کلِ داده
        if st is None:
            print(f"   {tf}: بدونِ معامله در کلِ داده — حذف", flush=True)
            continue
        tr = trades_df(st)
        n_long = int((tr['direction'] == 'long').sum())
        n_short = int(st['n'] - n_long)
        # نالِ اندازه‌گیری‌شدهٔ همین کارت با همان هندسه (پیش‌ثبت §5)
        null, pool_note = s740.build_null(m['df'], m['atr'], n_long, n_short,
                                          k_sl, rr, k_perm, rng)
        nulls[tf] = null
        # lift عضو نسبت به مبنای بی‌قیدِ وزنی (الگوی s431)
        refs, wts = [], []
        for side, cnt in (('long', n_long), ('short', n_short)):
            u = null[side].get('uncond_wr')
            if u is not None and cnt > 0:
                refs.append(u * cnt)
                wts.append(cnt)
        ref = (sum(refs) / sum(wts)) if wts else None
        wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
        lift = (wr - ref) if ref is not None else None
        sl_med = float(np.median(st['sl_pip']))
        tp_med = float(np.median(st['tp_pip']))
        mstats[tf] = dict(n=int(st['n']), n_long=n_long, n_short=n_short,
                          wr=round(wr, 2), ref_wr=ref,
                          lift=round(lift, 2) if lift is not None else None,
                          pf=round(st['pf'], 3), exp=round(st['exp'], 2),
                          sl_med=sl_med, tp_med=tp_med, null_pool=pool_note)
        print(f"   {tf}: n={st['n']} (L{n_long}/S{n_short}) wr={wr:.2f} "
              f"ref={ref if ref is None else round(ref, 2)} "
              f"lift={mstats[tf]['lift']}", flush=True)
        if lift is None:
            continue
        entries.append(dict(card=tf, tr=tr, dt=m['dt'], lift=float(lift)))
    out['final_members'] = mstats
    _save(out)

    res = build_pool(entries, force_all=True) if entries else None
    if res is None or len(res['pool']) < 5:
        out['verdict'] = 'NO_TRADES_FULL'
        _save(out)
        print("[توقف] استخرِ نهایی ساخته نشد.", flush=True)
        return out

    pool = res['pool']
    used = [u['card'] for u in res['used']]
    print(f"\n[استخرِ نهایی] used={used} n_before={res['n_before']} "
          f"→ n_after={len(pool)} (FIFO)", flush=True)
    for dd in res['dropped']:
        print(f"   dropped {dd['card']}: {dd['reason']}", flush=True)
    out['final_pool'] = dict(used=used, dropped=res['dropped'],
                             n_before=res['n_before'], n_after=int(len(pool)))

    # هندسهٔ وزنی به سهمِ پس-از-FIFO
    share = pool['src_card'].value_counts(normalize=True).to_dict()
    sl_med = float(sum(mstats[c]['sl_med'] * w for c, w in share.items()))
    tp_med = float(sum(mstats[c]['tp_med'] * w for c, w in share.items()))

    # نالِ ترکیبی وزنی (الگوی blend_pool_null s431؛ واریانس با w²)
    null = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
        for tf, w in share.items():
            d = nulls[tf][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * w
                den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w
                num_s += (d['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = d.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        null[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    out['null'] = null
    print(f"[نولِ استخر] {json.dumps(null, default=_default)}", flush=True)

    # محورِ مشترکِ ۲ساعته (پیش‌ثبت §5؛ الگوی s431 پس از BUG-AXIS/QUANT/SPAN)
    STEP_NS = 2 * 3600 * 1_000_000_000
    te = pool['t_entry'].values.astype(np.int64)
    tx = pool['t_exit'].values.astype(np.int64)
    axis_t = np.arange(te.min() - STEP_NS, tx.max() + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    # close هم‌راستا از کارتِ H2 (کلِ افق را دارد؛ بدونِ نگاهِ آینده)
    ref_t = h2['dt'].astype(np.int64)
    ref_c = h2['df']['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]
    axis_sec = (axis_t // 1_000_000_000).astype(np.int64)

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, te, 'left'),
                                0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(axis_t, tx, 'left'),
                               0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    te = pool['t_entry'].values.astype(np.int64)

    # holdout = مرزِ تقویمیِ منجمدِ همان اکتشاف (پیش‌ثبت §5)
    holdout = te >= (T_star * 1_000_000_000)
    print(f"[تقسیم] T*={out['T_star_utc']} · اکتشاف={int((~holdout).sum())} "
          f"· خارج‌نمونه={int(holdout.sum())}", flush=True)

    r = rqs2.compute_rqs2(pool, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=axis_sec, null=null, n_trials=N_TRIALS,
                          holdout_mask=holdout, close=axis_close,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S744-POOL', r), flush=True)

    pnl = pool['pnl_pip'].values.astype(float)
    wins = pnl[pnl > 0].sum()
    loss = -pnl[pnl <= 0].sum()
    out['full'] = dict(n=int(len(pool)),
                       wr=round(100.0 * float((pnl > 0).mean()), 2),
                       exp_pip=round(float(pnl.mean()), 3),
                       pf=round(float(wins / loss) if loss > 0 else float('inf'), 3),
                       sl_med=round(sl_med, 2), tp_med=round(tp_med, 2),
                       share={k: round(v, 3) for k, v in share.items()})
    out['verdict'] = r['verdict']
    out['rqs2_score'] = r.get('rqs2_score')
    out['gates'] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                    for k, v in (r.get('gates') or {}).items()}
    out['metrics'] = {k: v for k, v in (r.get('metrics') or {}).items()
                      if isinstance(v, (int, float, str, bool, np.integer,
                                        np.floating, np.bool_)) or v is None}
    out['elapsed_s'] = round(_time.time() - t0, 1)
    _save(out)
    print(f"\n✔ checkpoint → {os.path.join(OUT_DIR, 'pool.json')} "
          f"({out['elapsed_s']}s) · verdict={out['verdict']} "
          f"score={out['rqs2_score']}", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--kperm', type=int, default=500)
    a = ap.parse_args()
    main(k_perm=a.kperm)
