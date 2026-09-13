# -*- coding: utf-8 -*-
"""S1514 — استخرِ چند-TF رکوردِ تازهٔ کف (S1511 منجمد روی H6+H8+H12) ⇒ LONG.

پیش‌ثبت: `results/S1514_PREREG_FRESH_FLOOR_MTF_POOL.md` (کامیت 7937e2df — **قبل** از هر عدد).
عضو: سیگنال/هندسه/شبیه‌ساز عیناً S1511 (s382 simulate_trades)؛ نول مشروط drift>0
(strides 1/3/7 + perm K=500) به‌ازای عضو. ادغام: engine/rqs2_pool.pool_cards (هم‌جهتی،
همگنی، FIFO تقویمی) → نول وزنی (S431/S601/S517) → محور H6 → holdout 60% زمان ورود →
**یک** compute_rqs2 رسمی (n_trials=30) + تنش 100. داده mt5_full با گارد E-16.
"""
from __future__ import annotations
import importlib.util, json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); os.chdir(ROOT)
import engine.rqs2 as R2
import engine.rqs2_pool as rp

OUT = 'results/_scan_S1514'
ASSET = 'XAUUSD'
TFS = ('H6', 'H8', 'H12')
AXIS_TF = 'H6'; AXIS_STEP_NS = 6 * 3600 * 1_000_000_000
LOOKBACK = 90
K_PERM_MEMBER = 500
N_TRIALS = 30; N_TRIALS_STRESS = 100
SPLIT_FRAC = 0.60
SEED = 20260908
COST = 3.3


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


L = _mod('strategies/s382_williamsr_momentum.py', '_s382')


def _b(s): return s.astype('boolean').fillna(False).astype(bool)


def load_full(tf):
    path = f'data/mt5_full/{ASSET}_{tf}.csv'
    assert 'mt5_full' in path and os.path.exists(path), f'E-16 GUARD: {path}'
    df = pd.read_csv(path); df['dt'] = pd.to_datetime(df['time'], unit='s'); return df


def drift_mask(df):
    c = df['close']; return _b((c.shift(1) - c.shift(LOOKBACK)) > 0)


def sig_s1511(df):
    lo = df['low']; ff = _b(lo > lo.rolling(LOOKBACK).max().shift(1))
    return ff & ~ff.shift(1, fill_value=False) & drift_mask(df)


def member_population(tf):
    df = load_full(tf)
    ps = L.pip_size(ASSET)
    sl_abs = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K
    sl_pip = sl_abs / ps; tp_pip = sl_pip * L.RR
    sig = sig_s1511(df)
    tr = L.simulate_trades(df, sig, sl_abs, L.RR, True, ps)
    if len(tr) < 30:
        print(f'[{tf}] n={len(tr)} — عضو نامعتبر', flush=True); return None
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    m = drift_mask(df).to_numpy(); n = len(df)
    # uncond مشروط (سخت‌ترین استراید)
    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.where(m)[0][::stride]
        s0 = pd.Series(False, index=df.index); s0.iloc[idx] = True
        t0 = L.simulate_trades(df, s0, sl_abs, L.RR, True, ps)
        uncond_rows.append((stride, 100.0 * float((t0['outcome'] == 'win').mean()) if len(t0) else None, int(len(t0))))
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)
    # جایگشت مشروط K=500
    rng = np.random.default_rng(SEED)
    valid = np.where(m[200:n - 2])[0] + 200
    n_sig = int(sig.sum()); wrs = []
    for _ in range(K_PERM_MEMBER):
        pos = rng.choice(valid, size=min(n_sig, len(valid)), replace=False)
        s1 = pd.Series(False, index=df.index); s1.iloc[np.sort(pos)] = True
        t1 = L.simulate_trades(df, s1, sl_abs, L.RR, True, ps)
        if len(t1) >= 30: wrs.append(100.0 * float((t1['outcome'] == 'win').mean()))
    arr = np.asarray(wrs, float)
    perm_mean, perm_sd = float(arr.mean()), float(arr.std(ddof=1))
    lift = obs_wr - perm_mean; z = (obs_wr - perm_mean) / perm_sd if perm_sd > 0 else float('nan')
    be = 100.0 * (sl_pip + COST) / (sl_pip * L.RR + sl_pip)
    print(f'[{tf}] n_sig={n_sig} n_tr={len(tr)} wr={obs_wr:.2f} be={be:.2f} sl={sl_pip:.1f} | '
          f'uncond={uncond_wr:.2f} perm={perm_mean:.2f}±{perm_sd:.2f} → lift={lift:+.2f} z={z:.2f}', flush=True)
    dt = df['dt'].values.astype('datetime64[ns]')
    null_side = dict(uncond_wr=uncond_wr, perm_mean=perm_mean, perm_sd=perm_sd, perm_max=float(arr.max()), perm_k=int(len(arr)))
    return dict(card=f'{ASSET}-{tf}', tf=tf, tr=tr, dt=dt, lift=float(lift), z=float(z), obs_wr=obs_wr, n=int(len(tr)),
                sl_pip=float(sl_pip), tp_pip=float(tp_pip), be=be,
                null={'long': null_side, 'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)},
                uncond=uncond_rows, src=f'data/mt5_full/{ASSET}_{tf}.csv')


def blend_pool_null(members_used, pool_df):
    share = pool_df['src_card'].value_counts(normalize=True).to_dict(); out = {}
    for side in ('long', 'short'):
        num_u = den_u = num_m = num_s = den_p = 0.0; kmin = None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
            if w <= 0: continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None: num_u += d['uncond_wr'] * w; den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w; num_s += (d['perm_sd'] ** 2) * (w ** 2); den_p += w
                k = d.get('perm_k'); kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(uncond_wr=(num_u / den_u) if den_u > 0 else None, perm_mean=(num_m / den_p) if den_p > 0 else None,
                         perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None, perm_max=None, perm_k=kmin)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    members = []
    for tf in TFS:
        m = member_population(tf)
        if m is None: continue
        members.append(m)
        slim = {k: v for k, v in m.items() if k not in ('tr', 'dt')}
        json.dump(slim, open(f'{OUT}/{tf}_member.json', 'w'), ensure_ascii=False, default=str)
        m['tr'].to_csv(f'{OUT}/{tf}_trades.csv', index=False)
    if len(members) < 2:
        print('[توقف] کمتر از ۲ عضو معتبر', flush=True); return
    res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'], lift=m['lift']) for m in members])
    if res is None:
        print('[توقف] pool_cards عضوی نیافت', flush=True); return
    print(f"[انتخاب‌گر] chosen={[c['card'] for c in res['selection']['chosen']]} dropped={res['dropped']}", flush=True)
    pool = res['pool']
    print(f"[تجمیع] n_before={res['n_before']} → n_after={res['n_after']}", flush=True)
    share = pool['src_card'].value_counts(normalize=True); print(f'[سهم اعضا] {share.round(3).to_dict()}', flush=True)
    used_members = [m for m in members if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool); print(f"[نول استخر] long={null['long']}", flush=True)
    shares = share.to_dict(); by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))
    print(f'[هندسهٔ استخر] SL={sl_med:.1f} TP={tp_med:.1f}', flush=True)
    t_lo = int(pool['t_entry'].values.astype(np.int64).min()); t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - AXIS_STEP_NS, t_hi + 2 * AXIS_STEP_NS, AXIS_STEP_NS, dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]'); print(f'[محور مشترک] {AXIS_TF} · {len(axis_t):,} سطل', flush=True)
    dref = load_full(AXIS_TF)
    ref_t = dref['dt'].values.astype('datetime64[ns]').astype(np.int64); ref_c = dref['close'].astype(float).to_numpy()
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1); axis_close = ref_c[pos]
    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, pool['t_entry'].values.astype(np.int64), 'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(axis_t, pool['t_exit'].values.astype(np.int64), 'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    te_all = pool['t_entry'].values.astype(np.int64); split_ns = int(np.quantile(te_all, SPLIT_FRAC)); holdout = te_all >= split_ns
    print(f'[تقسیم ۶۰٪] مرز={np.datetime64(split_ns, "ns")} · کشف={int((~holdout).sum())} · OOS={int(holdout.sum())}', flush=True)
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt, null=null, close=axis_close, holdout_mask=holdout, allow_overlap=False)
    r = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS, **common)
    r_st = R2.compute_rqs2(pool, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print('\n' + R2.format_rqs2('S1514-POOL OFFICIAL', r), flush=True)
    print(R2.format_rqs2(f'S1514-POOL STRESS({N_TRIALS_STRESS})', r_st), flush=True)
    def _slim(rr): return dict(verdict=rr.get('verdict'), rqs2_score=rr.get('rqs2_score'), metrics=rr.get('metrics'), gates=rr.get('gates'), notes=rr.get('notes'))
    json.dump(dict(official=_slim(r), stress=_slim(r_st), used=res['used'], dropped=res['dropped'], n_before=res['n_before'], n_after=res['n_after'],
                   shares={k: float(v) for k, v in shares.items()}, sl_pip=sl_med, tp_pip=tp_med, pool_null=null, n_trials=N_TRIALS,
                   n_trials_stress=N_TRIALS_STRESS, seed=SEED, axis=AXIS_TF, src='data/mt5_full'),
              open(f'{OUT}/pool_verdict.json', 'w'), ensure_ascii=False, default=str)
    pool.to_csv(f'{OUT}/pool_trades.csv', index=False)
    print(f'saved -> {OUT}/pool_verdict.json', flush=True)


if __name__ == '__main__':
    main()
