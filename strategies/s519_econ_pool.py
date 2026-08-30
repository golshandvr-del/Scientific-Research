# -*- coding: utf-8 -*-
"""
S519 — استخر اقتصادی-سالم V-TIME زیر-ساعتی (XAUUSD) — آخرین لایهٔ بلوک S510
پیش‌ثبت: results/S519_PREREG_VTIME_ECON_POOL.md (پیش از هر عدد)
عضویت دوگانه: (الف) lift>0 در برابر نول اندازه‌گیری‌شده (K=500)
              (ب) میانگین پیپ خالص > 0 در هر دو نیمهٔ کشفِ همان کارت.
اعضا: نامزدهای جدید {M10,M12,M20} + M30 منجمد (S515).
stages: members | pool
SEED=20260825
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategies.s511_gross_census import (load_fast, cross_above,   # noqa: E402
                                          SPLIT_FRAC, WARMUP, Q_HI, PIP)
from strategies.s515_voltime import (sim_vtime, bracket_from_discovery,  # noqa: E402
                                     IND)
from engine import indicator_bank as ib                              # noqa: E402
from tools.s434_fast_data import as_dataframe                        # noqa: E402
import engine.rqs2 as R2                                             # noqa: E402
import engine.rqs2_pool as rp                                        # noqa: E402

SEED = 20260825
K_VT = 4
TFS_NEW = ('M10', 'M12', 'M20')
TF_FROZEN = 'M30'
K_PERM_MEMBER = 500
MIN_N_FULL = 30
N_TRIALS = 5028
N_TRIALS_STRESS = 8000
OUT = 'results/_scan_S519'
ASSET = 'XAUUSD'
TF_MIN = {'M10': 10, 'M12': 12, 'M20': 20, 'M30': 30}


def member_population(tf):
    """قانون منجمد V-TIME روی یک کارت + نول اندازه‌گیری‌شده + گیت اقتصادی دوگانه."""
    d = load_fast(ASSET, tf)
    assert 'mt5_full' in d['src'], f'E-16 TRAP: {tf} fell back to short data!'
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    df_full = as_dataframe({k: d[k] for k in
                            ('time', 'open', 'high', 'low', 'close', 'volume')})
    x = ib.compute(IND, df_full).to_numpy()
    x[:WARMUP] = np.nan
    thr = float(np.nanquantile(x[:split], Q_HI))
    sig_bool = np.nan_to_num(cross_above(x, thr), nan=False).astype(bool)
    sig_bool[:WARMUP] = False

    sig_disc = np.flatnonzero(sig_bool[:split])
    if len(sig_disc) < 10:
        print(f'[{tf}] فقط {len(sig_disc)} سیگنال کشف — نامعتبر', flush=True)
        return None
    br = bracket_from_discovery(d, sig_disc, K_VT, split)

    sig_idx = np.flatnonzero(sig_bool)
    tr = sim_vtime(d, sig_idx, K_VT, br)
    if len(tr) < MIN_N_FULL:
        print(f'[{tf}] n_full={len(tr)} < {MIN_N_FULL} — نامعتبر', flush=True)
        return None
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())

    # ---- گیت (ب): اقتصاد پایدار در کشف ----
    disc_tr = tr[tr['entry_bar'].values < split]
    pnl_d = disc_tr['pnl_pip'].values
    hd = len(pnl_d) // 2
    m1 = float(pnl_d[:hd].mean()) if hd > 0 else float('nan')
    m2 = float(pnl_d[hd:].mean()) if len(pnl_d) - hd > 0 else float('nan')
    econ_ok = bool(m1 > 0 and m2 > 0)

    # ---- گیت (الف): نول اندازه‌گیری‌شده ----
    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(WARMUP, n - K_VT - 1, stride, dtype=np.int64)
        t0 = sim_vtime(d, idx, K_VT, br)
        wr0 = (100.0 * float((t0['outcome'] == 'win').mean())
               if len(t0) else None)
        uncond_rows.append((stride, wr0, int(len(t0))))
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)

    rng = np.random.default_rng(SEED)
    space = np.arange(WARMUP, n - K_VT - 1, dtype=np.int64)
    wrs = []
    for k in range(K_PERM_MEMBER):
        pos = np.sort(rng.choice(space, size=min(len(sig_idx), len(space)),
                                 replace=False))
        tp_ = sim_vtime(d, pos, K_VT, br)
        if len(tp_) >= 20:
            wrs.append(100.0 * float((tp_['outcome'] == 'win').mean()))
    arr = np.asarray(wrs, float)
    perm_mean, perm_sd = float(arr.mean()), float(arr.std(ddof=1))
    lift = obs_wr - perm_mean
    z = (obs_wr - perm_mean) / perm_sd if perm_sd > 0 else float('nan')
    stat_ok = bool(lift > 0)

    print(f'[{tf}] n_tr={len(tr)} wr={obs_wr:.2f}% br={br/PIP:.1f}pip | '
          f'lift={lift:+.2f}pp z={z:.2f} [الف:{"OK" if stat_ok else "X"}] | '
          f'econ کشف m1={m1:+.2f} m2={m2:+.2f} [ب:{"OK" if econ_ok else "X"}]',
          flush=True)

    dt = (pd.to_datetime(d['time'], unit='s', utc=True)
          .tz_localize(None).values.astype('datetime64[ns]'))
    null_side = dict(uncond_wr=uncond_wr, perm_mean=perm_mean,
                     perm_sd=perm_sd, perm_max=float(arr.max()),
                     perm_k=int(len(arr)))
    sl_pip = br / PIP
    return dict(card=f'{ASSET}-{tf}', tf=tf, tr=tr, dt=dt, lift=float(lift),
                z=float(z), obs_wr=obs_wr, n=int(len(tr)),
                sl_pip=float(sl_pip), tp_pip=float(sl_pip),
                null={'long': null_side,
                      'short': dict(uncond_wr=None, perm_mean=None,
                                    perm_sd=None, perm_max=None,
                                    perm_k=None)},
                econ_m1=m1, econ_m2=m2, stat_ok=stat_ok, econ_ok=econ_ok,
                valid=bool(stat_ok and econ_ok),
                thr=thr, split=int(split), n_bars=int(n),
                uncond=uncond_rows)


def blend_pool_null(members_used, pool_df):
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
        for m in members_used:
            wgt = float(share.get(m['card'], 0.0))
            if wgt <= 0:
                continue
            dd = m['null'][side]
            if dd.get('uncond_wr') is not None:
                num_u += dd['uncond_wr'] * wgt
                den_u += wgt
            if dd.get('perm_mean') is not None and dd.get('perm_sd') is not None:
                num_m += dd['perm_mean'] * wgt
                num_s += (dd['perm_sd'] ** 2) * (wgt ** 2)
                den_p += wgt
                k = dd.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def stage_members():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for tf in TFS_NEW + (TF_FROZEN,):
        m = member_population(tf)
        if m is None:
            rows.append(dict(tf=tf, valid=False, reason='too few trades'))
            continue
        slim = {k: v for k, v in m.items() if k not in ('tr', 'dt')}
        with open(f'{OUT}/{tf}_member.json', 'w', encoding='utf-8') as f:
            json.dump(slim, f, ensure_ascii=False, default=str)
        m['tr'].to_csv(f'{OUT}/{tf}_trades.csv', index=False)
        rows.append(dict(tf=tf, valid=m['valid'], stat_ok=m['stat_ok'],
                         econ_ok=m['econ_ok'], n=m['n'], wr=m['obs_wr'],
                         lift=m['lift'], z=m['z'],
                         econ_m1=m['econ_m1'], econ_m2=m['econ_m2']))
    with open(f'{OUT}/members_summary.json', 'w', encoding='utf-8') as f:
        json.dump(dict(rows=rows, seed=SEED), f, ensure_ascii=False)
    print(f'saved -> {OUT}/members_summary.json', flush=True)


def stage_pool():
    os.makedirs(OUT, exist_ok=True)
    all_m = {}
    for tf in TFS_NEW + (TF_FROZEN,):
        m = member_population(tf)
        if m is not None:
            all_m[tf] = m
    valid_new = [m for tf, m in all_m.items()
                 if tf != TF_FROZEN and m['valid']]
    frozen = all_m.get(TF_FROZEN)
    frozen_ok = frozen is not None and frozen['valid']

    members = list(valid_new) + ([frozen] if frozen_ok else [])
    if len(members) >= 2:
        mode = 'pool'
    elif len(valid_new) == 1:
        mode, members = 'single_new', valid_new
    elif not valid_new and all_m:
        # هیچ عضو جدید دوگانه-معتبر: طبق پیش‌ثبت بهترین کارت جدید (بیشینهٔ lift)
        best = max((m for tf, m in all_m.items() if tf != TF_FROZEN),
                   key=lambda m: m['lift'], default=None)
        if best is None:
            print('[توقف] هیچ کارت جدیدی بازتولید نشد.', flush=True)
            return
        mode, members = 'best_new_fallback', [best]
    else:
        print('[توقف] هیچ عضوی نیست.', flush=True)
        return
    print(f'[MODE] {mode} · members={[m["card"] for m in members]}', flush=True)

    if len(members) >= 2:
        res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                                  lift=m['lift']) for m in members])
        pool = res['pool']
        used = [m for m in members
                if m['card'] in {u['card'] for u in res['used']}]
        meta_sel = dict(used=res['used'], dropped=res['dropped'],
                        n_before=res['n_before'], n_after=res['n_after'])
    else:
        m0 = members[0]
        pool = m0['tr'].copy()
        dtv = m0['dt']
        eb = np.clip(pool['entry_bar'].values.astype(np.int64), 0, len(dtv)-1)
        xb = np.clip(pool['exit_bar'].values.astype(np.int64), 0, len(dtv)-1)
        pool['t_entry'] = dtv[eb].astype('datetime64[ns]').astype(np.int64)
        pool['t_exit'] = dtv[xb].astype('datetime64[ns]').astype(np.int64)
        pool['src_card'] = m0['card']
        used = [m0]
        meta_sel = dict(used=[dict(card=m0['card'], lift=m0['lift'],
                                   n=m0['n'])], dropped=[],
                        n_before=len(pool), n_after=len(pool))

    share = pool['src_card'].value_counts(normalize=True).to_dict()
    null = blend_pool_null(used, pool)
    by_card = {m['card']: m for m in used}
    sl = float(sum(by_card[c]['sl_pip'] * w for c, w in share.items()))
    tp = float(sum(by_card[c]['tp_pip'] * w for c, w in share.items()))
    print(f'[استخر] n={len(pool)} سهم={ {k: round(v,3) for k,v in share.items()} } '
          f'SL=TP={sl:.1f}pip', flush=True)

    # محور مشترک: ریزترین TF عضو
    tf_axis = min((m['tf'] for m in used), key=lambda t: TF_MIN[t])
    STEP_NS = TF_MIN[tf_axis] * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    dref = load_fast(ASSET, tf_axis)
    assert 'mt5_full' in dref['src']
    ref_t = (pd.to_datetime(dref['time'], unit='s', utc=True)
             .tz_localize(None).values.astype('datetime64[ns]')
             .astype(np.int64))
    ref_c = dref['close'].astype(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1,
                  0, len(ref_c) - 1)
    axis_close = ref_c[pos]
    print(f'[محور] {tf_axis} · {len(axis_t):,} سطل', flush=True)

    pool = pool.copy()
    pool['entry_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_entry'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_exit'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    te = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te, SPLIT_FRAC))
    holdout = te >= split_ns
    print(f'[تقسیم ۶۰٪ زمان ورود] کشف={int((~holdout).sum())} '
          f'OOS={int(holdout.sum())}', flush=True)

    common = dict(sl_pip=sl, tp_pip=tp, bar_time=axis_t.astype('datetime64[ns]'),
                  null=null, close=axis_close, holdout_mask=holdout,
                  allow_overlap=False)
    r = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS, **common)
    r_st = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print('\n' + R2.format_rqs2('S519 OFFICIAL', r), flush=True)
    print(R2.format_rqs2(f'S519 STRESS({N_TRIALS_STRESS})', r_st), flush=True)

    def _slim(rr_):
        return dict(verdict=rr_.get('verdict'),
                    rqs2_score=rr_.get('rqs2_score'),
                    metrics=rr_.get('metrics'), gates=rr_.get('gates'),
                    notes=rr_.get('notes'))
    with open(f'{OUT}/pool_verdict.json', 'w', encoding='utf-8') as f:
        json.dump(dict(mode=mode, official=_slim(r), stress=_slim(r_st),
                       selection=meta_sel,
                       shares={k: float(v) for k, v in share.items()},
                       sl_pip=sl, tp_pip=tp, pool_null=null,
                       axis_tf=tf_axis, n_trials=N_TRIALS,
                       n_trials_stress=N_TRIALS_STRESS, seed=SEED),
                  f, ensure_ascii=False, default=str)
    pool.to_csv(f'{OUT}/pool_trades.csv', index=False)
    print(f'saved -> {OUT}/pool_verdict.json', flush=True)


if __name__ == '__main__':
    stage = sys.argv[sys.argv.index('--stage') + 1] \
        if '--stage' in sys.argv else 'members'
    dict(members=stage_members, pool=stage_pool)[stage]()
