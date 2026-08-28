# -*- coding: utf-8 -*-
"""
S518 — درمان اقتصادی استخر V-TIME با پنجرهٔ نشستی علّی (XAUUSD)
پیش‌ثبت: results/S518_PREREG_VTIME_SESSION_ECON.md (پیش از هر عدد)
پایهٔ منجمد: استخر S517 {M15,M30} عیناً (member_population + pool_cards +
blend_pool_null + محور M15 + هندسهٔ وزنی). فیلتر: ساعت ورود UTC در ۴ پنجره.
stages: select | identity | judge
SEED=20260824
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategies.s511_gross_census import SPLIT_FRAC                  # noqa: E402
from strategies.s517_mtf_pool import (member_population,             # noqa: E402
                                      blend_pool_null, load_fast, ASSET)
import engine.rqs2 as R2                                             # noqa: E402
import engine.rqs2_pool as rp                                        # noqa: E402

SEED = 20260824
WINDOWS = (('W1_Asia', 0, 7), ('W2_London', 7, 12),
           ('W3_Overlap', 12, 17), ('W4_LateNY', 17, 24))
MIN_N_DISC = 60
RET_LO, RET_HI = 0.20, 0.80
K_IDENTITY = 1000
N_TRIALS = 5024
N_TRIALS_STRESS = 8000
OUT = 'results/_scan_S518'
POOL_TFS = ('M15', 'M30')


def build_pool():
    """بازسازی قطعی استخر S517 (بذرها/قوانین منجمد) + محور M15 + هندسه."""
    members = [member_population(tf) for tf in POOL_TFS]
    members = [m for m in members if m is not None]
    assert len(members) == 2, 'pool base must reproduce exactly'
    res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                              lift=m['lift']) for m in members])
    pool = res['pool']
    share = pool['src_card'].value_counts(normalize=True).to_dict()
    used = [m for m in members
            if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used, pool)
    by_card = {m['card']: m for m in used}
    sl = float(sum(by_card[c]['sl_pip'] * w for c, w in share.items()))
    tp = float(sum(by_card[c]['tp_pip'] * w for c, w in share.items()))

    STEP_NS = 15 * 60 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
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

    te = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te, SPLIT_FRAC))     # مرز منجمد از پایه
    pool['hour_utc'] = pd.to_datetime(pool['t_entry']).dt.hour.values
    pool['is_oos'] = te >= split_ns
    print(f'[POOL] n={len(pool)} · مرز OOS={np.datetime64(split_ns, "ns")} · '
          f'کشف={int((~pool["is_oos"]).sum())} OOS={int(pool["is_oos"].sum())} '
          f'· SL=TP={sl:.1f}pip', flush=True)
    return dict(pool=pool, null=null, sl=sl, tp=tp,
                axis_dt=axis_t.astype('datetime64[ns]'),
                axis_close=axis_close, split_ns=split_ns)


def t_stat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return float('nan')
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def stage_select():
    os.makedirs(OUT, exist_ok=True)
    B = build_pool()
    pool = B['pool']
    disc = pool[~pool['is_oos']]
    pnl = disc['pnl_pip'].values
    half = len(disc) // 2
    base = dict(n=int(len(disc)), mean=float(pnl.mean()), t=t_stat(pnl),
                m1=float(pnl[:half].mean()), m2=float(pnl[half:].mean()))
    print(f"[BASE-کشف] n={base['n']} mean={base['mean']:+.2f}pip "
          f"t={base['t']:+.2f} (m1={base['m1']:+.2f} m2={base['m2']:+.2f})",
          flush=True)

    rows, winner = [], None
    for name, h0, h1 in WINDOWS:
        m = (disc['hour_utc'].values >= h0) & (disc['hour_utc'].values < h1)
        sub = pnl[m]
        ret = len(sub) / len(disc)
        r = dict(window=name, h0=h0, h1=h1, n=int(len(sub)), ret=float(ret))
        valid = False
        if len(sub) >= MIN_N_DISC and RET_LO <= ret <= RET_HI:
            s1, s2 = pnl[:half][m[:half]], pnl[half:][m[half:]]
            r.update(mean=float(sub.mean()), t=t_stat(sub),
                     m1=float(s1.mean()) if len(s1) else None,
                     m2=float(s2.mean()) if len(s2) else None)
            valid = (len(s1) > 0 and len(s2) > 0 and
                     r['m1'] > base['m1'] and r['m2'] > base['m2'])
        r['valid'] = bool(valid)
        rows.append(r)
        msg = (f"  {name}: n={r['n']} ret={ret:.3f}"
               + (f" mean={r.get('mean', float('nan')):+.2f} "
                  f"t={r.get('t', float('nan')):+.2f}" if 'mean' in r else '')
               + ('  VALID' if valid else '  -'))
        print(msg, flush=True)
        if valid and (winner is None or r['t'] > winner['t']):
            winner = r
    out = dict(base=base, rows=rows, winner=winner, seed=SEED)
    with open(f'{OUT}/select.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    print(f"[SELECT] winner={winner['window'] if winner else None}",
          flush=True)
    print(f'saved -> {OUT}/select.json', flush=True)


def stage_identity():
    with open(f'{OUT}/select.json') as f:
        S = json.load(f)
    w = S['winner']
    if not w:
        raise SystemExit('no winner — REJECT-by-no-candidate')
    B = build_pool()
    pool = B['pool']
    disc = pool[~pool['is_oos']]
    pnl = disc['pnl_pip'].values
    m = ((disc['hour_utc'].values >= w['h0']) &
         (disc['hour_utc'].values < w['h1']))
    obs = float(pnl[m].mean())
    k = int(m.sum())
    rng = np.random.default_rng(SEED)
    means = np.empty(K_IDENTITY)
    for i in range(K_IDENTITY):
        sel = rng.choice(len(pnl), size=k, replace=False)
        means[i] = pnl[sel].mean()
    p_exact = float((means >= obs - 1e-12).mean())
    ok = p_exact <= 0.05
    print(f'[IDENTITY] obs_mean={obs:+.3f}pip (n={k}) · random: '
          f'mean={means.mean():+.3f} p95={np.quantile(means, 0.95):+.3f} '
          f'max={means.max():+.3f} · P(rand>=obs)={p_exact:.4f} → '
          f'{"PASS" if ok else "FAIL"}', flush=True)
    with open(f'{OUT}/identity.json', 'w', encoding='utf-8') as f:
        json.dump(dict(winner=w['window'], obs_mean=obs, n=k,
                       rand_mean=float(means.mean()),
                       rand_p95=float(np.quantile(means, 0.95)),
                       rand_max=float(means.max()), p_exact=p_exact,
                       gate='P<=0.05', result='PASS' if ok else 'FAIL',
                       k=K_IDENTITY, seed=SEED), f, ensure_ascii=False)
    print(f'saved -> {OUT}/identity.json', flush=True)


def stage_judge():
    with open(f'{OUT}/select.json') as f:
        S = json.load(f)
    with open(f'{OUT}/identity.json') as f:
        I = json.load(f)
    assert I['result'] == 'PASS', 'identity FAIL — judging forbidden by prereg'
    w = S['winner']
    B = build_pool()
    pool = B['pool']
    m = ((pool['hour_utc'].values >= w['h0']) &
         (pool['hour_utc'].values < w['h1']))
    sub = pool[m].reset_index(drop=True)
    te = sub['t_entry'].values.astype(np.int64)
    holdout = te >= B['split_ns']
    print(f"[JUDGE] window={w['window']} n={len(sub)} "
          f"کشف={int((~holdout).sum())} OOS={int(holdout.sum())}", flush=True)
    common = dict(sl_pip=B['sl'], tp_pip=B['tp'], bar_time=B['axis_dt'],
                  null=B['null'], close=B['axis_close'],
                  holdout_mask=holdout, allow_overlap=False)
    r = R2.compute_rqs2(sub, ASSET, n_trials=N_TRIALS, **common)
    r_st = R2.compute_rqs2(sub, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print('\n' + R2.format_rqs2('S518 OFFICIAL', r), flush=True)
    print(R2.format_rqs2(f'S518 STRESS({N_TRIALS_STRESS})', r_st), flush=True)

    def _slim(rr_):
        return dict(verdict=rr_.get('verdict'),
                    rqs2_score=rr_.get('rqs2_score'),
                    metrics=rr_.get('metrics'), gates=rr_.get('gates'),
                    notes=rr_.get('notes'))
    with open(f'{OUT}/rqs2.json', 'w', encoding='utf-8') as f:
        json.dump(dict(official=_slim(r), stress=_slim(r_st),
                       window=w, n_trials=N_TRIALS,
                       n_trials_stress=N_TRIALS_STRESS, seed=SEED),
                  f, ensure_ascii=False, default=str)
    sub.to_csv(f'{OUT}/trades.csv', index=False)
    print(f'saved -> {OUT}/rqs2.json', flush=True)


if __name__ == '__main__':
    stage = sys.argv[sys.argv.index('--stage') + 1] \
        if '--stage' in sys.argv else 'select'
    dict(select=stage_select, identity=stage_identity,
         judge=stage_judge)[stage]()
