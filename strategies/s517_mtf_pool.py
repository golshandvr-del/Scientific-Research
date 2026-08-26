# -*- coding: utf-8 -*-
"""
S517 — استخر چند-TF هستهٔ V-TIME رخداد نوسانی (XAUUSD)
پیش‌ثبت: results/S517_PREREG_VTIME_MTF_POOL.md + الحاقیهٔ ۱ (H4→H3)
قانون منجمد از S515: atr_fib_55 عبور↑q90(کشف همان TF) → LONG، خروج زمانی
k=4 + براکت نادر متقارن SL=TP=q98(|MFE₄|∪|MAE₄|) از کشف همان TF.
اعضا: {M15, H1, H2, H3} جدید + M30 منجمد. عضویت: n_full>=30 و lift>0
(نول اندازه‌گیری‌شده: uncond stride 1/3/7 سخت‌ترین + جای‌گشت K=500).
استخر: engine/rqs2_pool (همگنی رسمی + FIFO تقویمی) → یک compute_rqs2
با n_trials=5019 + تنش 8000. holdout = صدک ۶۰٪ زمانِ ورود (BUG-SPLITDIR).
stages: members | pool
SEED=20260823
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategies.s511_gross_census import (load_fast, cross_above,
                                          SPLIT_FRAC, WARMUP, Q_HI, PIP)
from strategies.s515_voltime import (sim_vtime, bracket_from_discovery,
                                     IND, Q_BRACKET)
from engine.indicator_bank import IndicatorBank
import engine.rqs2 as R2
import engine.rqs2_pool as rp

SEED = 20260823
K_VT = 4                       # منجمد از S515
TFS_NEW = ('M15', 'H1', 'H2', 'H3')
TF_FROZEN = 'M30'
K_PERM_MEMBER = 500            # طبق پیش‌ثبت
MIN_N_FULL = 30
N_TRIALS = 5019
N_TRIALS_STRESS = 8000
OUT = 'results/_scan_S517'
ASSET = 'XAUUSD'

ib = IndicatorBank()


def as_dataframe(d):
    return pd.DataFrame(d)


def member_population(tf):
    """بازتولید کامل قانون منجمد روی یک TF + نول اندازه‌گیری‌شده."""
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
        print(f'[{tf}] فقط {len(sig_disc)} سیگنال کشف — عضو نامعتبر', flush=True)
        return None
    br = bracket_from_discovery(d, sig_disc, K_VT, split)

    sig_idx = np.flatnonzero(sig_bool)
    tr = sim_vtime(d, sig_idx, K_VT, br)
    if len(tr) < MIN_N_FULL:
        print(f'[{tf}] n_full={len(tr)} < {MIN_N_FULL} — عضو نامعتبر', flush=True)
        return None
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())

    # نول اندازه‌گیری‌شده: uncond سخت‌ترین + جای‌گشت K=500
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
    print(f'[{tf}] n_sig={len(sig_idx)} n_tr={len(tr)} wr={obs_wr:.2f}% '
          f'br={br/PIP:.1f}pip | null: uncond={uncond_wr:.2f} '
          f'perm={perm_mean:.2f}±{perm_sd:.2f} → lift={lift:+.2f}pp z={z:.2f}',
          flush=True)

    dt = (pd.to_datetime(d['time'], unit='s', utc=True)
          .tz_localize(None).values.astype('datetime64[ns]'))
    null_side = dict(uncond_wr=uncond_wr, perm_mean=perm_mean,
                     perm_sd=perm_sd, perm_max=float(arr.max()),
                     perm_k=int(len(arr)))
    sl_pip = br / PIP
    return dict(card=f'{ASSET}-{tf}', tf=tf, tr=tr, dt=dt, lift=float(lift),
                z=float(z), obs_wr=obs_wr, n=int(len(tr)),
                br_pip=float(sl_pip), sl_pip=float(sl_pip),
                tp_pip=float(sl_pip),
                null={'long': null_side,
                      'short': dict(uncond_wr=None, perm_mean=None,
                                    perm_sd=None, perm_max=None, perm_k=None)},
                thr=thr, split=int(split), n_bars=int(n),
                uncond=uncond_rows)


def stage_members():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for tf in TFS_NEW + (TF_FROZEN,):
        m = member_population(tf)
        if m is None:
            rows.append(dict(tf=tf, valid=False))
            continue
        slim = {k: v for k, v in m.items() if k not in ('tr', 'dt')}
        with open(f'{OUT}/{tf}_member.json', 'w', encoding='utf-8') as f:
            json.dump(slim, f, ensure_ascii=False, default=str)
        m['tr'].to_csv(f'{OUT}/{tf}_trades.csv', index=False)
        rows.append(dict(tf=tf, valid=True, n=m['n'], wr=m['obs_wr'],
                         lift=m['lift'], z=m['z'], br_pip=m['br_pip']))
    with open(f'{OUT}/members_summary.json', 'w', encoding='utf-8') as f:
        json.dump(dict(rows=rows, seed=SEED, k_vt=K_VT,
                       k_perm=K_PERM_MEMBER), f, ensure_ascii=False)
    print(f'saved -> {OUT}/members_summary.json', flush=True)


def blend_pool_null(members_used, pool_df):
    """نول استخر: ترکیب وزنی نول‌های منجمد اعضا به سهم پس-از-FIFO (الگوی S431/S601)."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0
        kmin = None
        for m in members_used:
            wgt = float(share.get(m['card'], 0.0))
            if wgt <= 0:
                continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * wgt
                den_u += wgt
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * wgt
                num_s += (d['perm_sd'] ** 2) * (wgt ** 2)
                den_p += wgt
                k = d.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def stage_pool():
    os.makedirs(OUT, exist_ok=True)
    members = []
    for tf in TFS_NEW + (TF_FROZEN,):
        m = member_population(tf)
        if m is not None:
            members.append(m)
    if len(members) < 2:
        print('[توقف] کمتر از ۲ عضو معتبر — استخر بی‌معناست.', flush=True)
        return

    res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                              lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] pool_cards عضوی نیافت.', flush=True)
        return
    print(f"[انتخاب‌گر] chosen={[c['card'] for c in res['selection']['chosen']]} "
          f"dropped={res['dropped']}", flush=True)
    pool = res['pool']
    print(f"[تجمیع] n_before={res['n_before']} → n_after={res['n_after']}",
          flush=True)
    share = pool['src_card'].value_counts(normalize=True)
    print(f'[سهم اعضا] {share.round(3).to_dict()}', flush=True)

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f"[نول استخر] long={null['long']}", flush=True)

    shares = share.to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))
    print(f'[هندسهٔ استخر] SL={sl_med:.1f} TP={tp_med:.1f}', flush=True)

    # محور مشترک: شبکهٔ M15 (ریزترین TF عضو)
    STEP_NS = 15 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f'[محور مشترک] M15 · {len(axis_t):,} سطل', flush=True)

    dref = load_fast(ASSET, 'M15')
    assert 'mt5_full' in dref['src']
    ref_t = (pd.to_datetime(dref['time'], unit='s', utc=True)
             .tz_localize(None).values.astype('datetime64[ns]')
             .astype(np.int64))
    ref_c = dref['close'].astype(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1,
                  0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_entry'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_exit'].values.astype(np.int64),
                        'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[تقسیم ۶۰٪ زمان ورود] مرز={np.datetime64(split_ns, "ns")} · '
          f'کشف={int((~holdout).sum())} · OOS={int(holdout.sum())}', flush=True)

    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt, null=null,
                  close=axis_close, holdout_mask=holdout, allow_overlap=False)
    r = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS, **common)
    r_st = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print('\n' + R2.format_rqs2('S517-POOL OFFICIAL', r), flush=True)
    print(R2.format_rqs2(f'S517-POOL STRESS({N_TRIALS_STRESS})', r_st),
          flush=True)

    def _slim(rr_):
        return dict(verdict=rr_.get('verdict'),
                    rqs2_score=rr_.get('rqs2_score'),
                    metrics=rr_.get('metrics'), gates=rr_.get('gates'),
                    notes=rr_.get('notes'))
    with open(f'{OUT}/pool_verdict.json', 'w', encoding='utf-8') as f:
        json.dump(dict(official=_slim(r), stress=_slim(r_st),
                       used=res['used'], dropped=res['dropped'],
                       n_before=res['n_before'], n_after=res['n_after'],
                       shares={k: float(v) for k, v in shares.items()},
                       sl_pip=sl_med, tp_pip=tp_med, pool_null=null,
                       n_trials=N_TRIALS, n_trials_stress=N_TRIALS_STRESS,
                       seed=SEED), f, ensure_ascii=False, default=str)
    pool.to_csv(f'{OUT}/pool_trades.csv', index=False)
    print(f'saved -> {OUT}/pool_verdict.json', flush=True)


if __name__ == '__main__':
    stage = sys.argv[sys.argv.index('--stage') + 1] \
        if '--stage' in sys.argv else 'members'
    dict(members=stage_members, pool=stage_pool)[stage]()
