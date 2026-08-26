# -*- coding: utf-8 -*-
"""
S640 — KamaRegimeCross — حکمِ رسمیِ موتور (پیش‌ثبتِ تکمیلی — یک بار اجرا)
==========================================================================
پیش‌ثبت: results/S640_PREREG_COMPLETION_ENGINE_VERDICT.md (commit قبل از این کد)
قاعدهٔ منجمد: شورت-فقط — close کراسِ پایینِ KAMA(10,2,30) و شیبِ منفی (slope_len=1)
کارت‌ها {H3,H4,H6,H8,H12} · SL=1.5×medATR100 نیمهٔ دوم · TP=SL · mh=64 ·
K=500 · n_trials=1 · seed=640640 · داور: compute_rqs2 روی استخرِ pool_cards.
زیرساخت عیناً s641_final_holdout.py (محورِ ۵دقیقه‌ای، axis_close از H1،
holdout_mask=میانهٔ زمانِ ورود).
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib          # noqa: E402
from engine import scalp_engine as se            # noqa: E402
from engine import rqs2 as R                     # noqa: E402
from engine import rqs2_pool as RP               # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

SEED = 640640
K_PERM = 500
N_UNCOND = 20000
PIP = 0.1
MAX_HOLD = 64
CARDS = ['H3', 'H4', 'H6', 'H8', 'H12']
WARMUP = 120
SPLIT_FRAC = 0.5

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s640_final')
os.makedirs(OUT, exist_ok=True)


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return 100.0 * float((tr['pnl_pip'] > 0).mean())


def sim(df, ls, ss, sl, tp):
    return se.simulate_trades(df, ls, ss, sl_pip=sl, tp_pip=tp,
                              asset='XAUUSD', max_hold=MAX_HOLD,
                              allow_overlap=False)


def build_null(df, vidx, sl, tp, n_long, n_short, rng):
    n = len(df)
    null = {}
    for side, n_side in (('long', n_long), ('short', n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side > 0:
            n_samp = min(N_UNCOND, len(vidx))
            pick = np.sort(rng.choice(len(vidx), size=n_samp, replace=False))
            sig = np.zeros(n, bool); sig[vidx[pick]] = True
            ls = sig if side == 'long' else np.zeros(n, bool)
            ss = sig if side == 'short' else np.zeros(n, bool)
            d['uncond_wr'] = wr_of(sim(df, ls, ss, sl, tp))
            wrs = []
            for _ in range(K_PERM):
                pick = np.sort(rng.choice(len(vidx),
                                          size=min(n_side, len(vidx)),
                                          replace=False))
                sig = np.zeros(n, bool); sig[vidx[pick]] = True
                ls = sig if side == 'long' else np.zeros(n, bool)
                ss = sig if side == 'short' else np.zeros(n, bool)
                w = wr_of(sim(df, ls, ss, sl, tp))
                if w is not None:
                    wrs.append(w)
            if wrs:
                a = np.asarray(wrs, 'float64')
                d.update(perm_mean=float(a.mean()),
                         perm_sd=float(a.std(ddof=1)),
                         perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        print(f"    null {side:<5} uncond={d['uncond_wr']} "
              f"perm_mean={d['perm_mean']} sd={d['perm_sd']} k={d['perm_k']}",
              flush=True)
    return null


def run_card(tf, rng):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    df_all = fd.as_dataframe(d)
    half = len(df_all) // 2
    df = df_all.iloc[half:].reset_index(drop=True)
    src = d.get('src', '?')
    del df_all

    kama = ib.compute('kama', df).values
    close = df['close'].values
    prev_c = np.roll(close, 1); prev_c[0] = close[0]
    prev_k = np.roll(kama, 1); prev_k[0] = kama[0]
    k_sh = np.roll(kama, 1); k_sh[:1] = kama[:1]      # slope_len=1 منجمد
    slope_dn = kama < k_sh
    cross_dn = (prev_c >= prev_k) & (close < kama)
    short_sig = cross_dn & slope_dn
    long_sig = np.zeros(len(df), bool)                # شورت-فقط، منجمد

    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr_ = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    slb = float(np.nanmedian(pd.Series(tr_).rolling(100).mean().values)) / PIP
    sl = max(1.0, round(1.5 * slb, 1)); tp = sl

    tr = sim(df, long_sig, short_sig, sl, tp)
    n_tr = 0 if tr is None else len(tr)
    nL = 0 if n_tr == 0 else int((tr['direction'] == 'long').sum())
    nS = n_tr - nL
    wr = wr_of(tr)
    print(f"[{tf}] src={src} bars2nd={len(df):,} sl={sl} "
          f"cost%={100*3.3/sl:.1f} n={n_tr} (S={nS}) wr={wr}", flush=True)

    vidx = np.arange(WARMUP, len(df) - MAX_HOLD - 1)
    null = build_null(df, vidx, sl, tp, nL, nS, rng)

    base = null['short'].get('uncond_wr') if nS > 0 else None
    lift = (wr - base) if (wr is not None and base is not None) else None
    ep = float(tr['pnl_pip'].mean()) if n_tr else None
    print(f"[{tf}] lift={None if lift is None else round(lift,2)} "
          f"exp_pip={None if ep is None else round(ep,2)} "
          f"({time.time()-t0:.1f}s)", flush=True)

    dt = pd.to_datetime(df['time'], unit='s').values.astype('datetime64[ns]')
    return dict(card=f'XAUUSD-{tf}', tf=tf, src=src, tr=tr, dt=dt,
                sl=sl, tp=tp, n=n_tr, nL=nL, nS=nS, wr=wr, lift=lift,
                exp_pip=ep, null=null)


def blend_pool_null(members_used, pool_df):
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
                num_u += d['uncond_wr'] * w; den_u += w
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
    rng = np.random.default_rng(SEED)
    print('== S640 — حکمِ رسمیِ موتور · KAMA cross-down SHORT · '
          '{H3,H4,H6,H8,H12} · K=500 · n_trials=1 ==', flush=True)

    members = []
    for tf in CARDS:
        m = run_card(tf, rng)
        with open(os.path.join(OUT, f'{tf}_member.json'), 'w',
                  encoding='utf-8') as f:
            json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
                      f, ensure_ascii=False, indent=1, default=str)
        members.append(m)

    res = RP.pool_cards(members)
    if res is None:
        print('\n[S640] استخر تهی — همهٔ اعضا lift<=0.', flush=True)
        with open(os.path.join(OUT, 'pool_verdict.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(dict(verdict='REJECT-EMPTY-POOL',
                           members=[dict(card=m['card'], n=m['n'],
                                         lift=m['lift']) for m in members]),
                      f, ensure_ascii=False, indent=1, default=str)
        return

    pool = res['pool']
    used_cards = {u['card'] for u in res['used']}
    used_members = [m for m in members if m['card'] in used_cards]
    share = pool['src_card'].value_counts(normalize=True)
    print(f"\n[pool] used={sorted(used_cards)} dropped={res['dropped']} "
          f"n_before={res['n_before']} n_after={res['n_after']}", flush=True)
    print(f"[pool] share={share.round(3).to_dict()}", flush=True)

    null = blend_pool_null(used_members, pool)
    print(f"[نولِ استخر] {json.dumps(null, ensure_ascii=False, default=str)}",
          flush=True)

    sl_med = float(pool['sl_pip'].median())
    tp_med = float(pool['tp_pip'].median()) if 'tp_pip' in pool.columns else sl_med

    STEP_NS = 5 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f"[محور] {axis_dt[0]} → {axis_dt[-1]} · {len(axis_t):,} سطل",
          flush=True)

    dref = fd.load_fast('XAUUSD', 'H1')
    ref_df = fd.as_dataframe(dref)
    ref_t = pd.to_datetime(ref_df['time'], unit='s').values.astype(
        'datetime64[ns]').astype(np.int64)
    ref_c = ref_df['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]
    del dref, ref_df

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
    print(f"[split] مرز={np.datetime64(split_ns,'ns')} · "
          f"پیش={int((~holdout).sum())} · پس={int(holdout.sum())}", flush=True)

    r = R.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                       bar_time=axis_dt, null=null, close=axis_close,
                       holdout_mask=holdout, n_trials=1,
                       allow_overlap=False)

    print('\n' + R.format_rqs2('S640-KAMA-POOL', r), flush=True)

    out = dict(prereg='S640_PREREG_COMPLETION_ENGINE_VERDICT.md',
               members=[dict(card=m['card'], src=m['src'], n=m['n'],
                             nS=m['nS'], wr=m['wr'], lift=m['lift'],
                             exp_pip=m['exp_pip'], sl_pip=m['sl'])
                        for m in members],
               used=[u['card'] for u in res['used']],
               dropped=res['dropped'], selection=res['selection'],
               n_before=res['n_before'], n_after=res['n_after'],
               member_share=share.to_dict(),
               pool_null=null, sl_pip_med=sl_med, tp_pip_med=tp_med,
               n_trials=1, k_perm=K_PERM, seed=SEED, split_ns=split_ns,
               verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
               gates=r.get('gates'), metrics=r.get('metrics'))
    with open(os.path.join(OUT, 'pool_verdict.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n[saved] {OUT}/pool_verdict.json", flush=True)


if __name__ == '__main__':
    main()
