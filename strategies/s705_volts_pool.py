# -*- coding: utf-8 -*-
"""
S705 — استخر دوکارتهٔ VolTS Cross {H2 θ=1.6, H6 θ=1.3} · cont · مسیر C
پیش‌ثبت: results/S705_PREREG_VOLTS_POOL_H2H6.md (کامیت b5d150fe — قبل از هر آزمون)
الگو: strategies/s701_aroon_slowpool.py (S431) — FIFO تقویمی، نول ترکیبی،
محور مصنوعی ۱ساعته، مرز holdout = بیشینهٔ زمان نیمهٔ جست‌وجوی اعضا،
یک فراخوان compute_rqs2 با n_trials=236.
درس‌ها: BUG-EPOCH ([s]→[ns])، BUG-DEFAULTARG (خاموشی گزینش درونی pool).
SEED=705.
"""
import sys, os, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2
from engine import rqs2_pool as rp

SEED = 705
K_PERM = 1000
N_TRIALS = 236
RR = 1.5
DRIFT_L = 34
QUIET_MIN = 3
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s705')
os.makedirs(OUT, exist_ok=True)

# اعضای منجمد پیش‌ثبت (آمار نیمهٔ جست‌وجو از آرتیفکت‌های کامیت‌شدهٔ S704)
MEMBERS = {
    'H2': dict(theta=1.6, k_sl=1.618, max_hold=64,
               alpha_search=8.731, n_search=183, pf_search=1.344),
    'H6': dict(theta=1.3, k_sl=1.618, max_hold=32,
               alpha_search=9.759, n_search=112, pf_search=1.420),
}

# توابع رویداد عیناً از اسکن S704 (تغییر ممنوع)
from importlib import util as _u
_spec = _u.spec_from_file_location(
    's704scan', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             's704_vol_termstructure_scan.py'))
_scan = _u.module_from_spec(_spec); _spec.loader.exec_module(_scan)
true_range = _scan.true_range
atr = _scan.atr
build_events = _scan.build_events


def build_member(tf, spec, rng):
    d = fd.load_fast('XAUUSD', tf)
    assert 'mt5_full' in d['src'], f"E-16 TRAP: {tf} src={d['src']}"
    df = fd.as_dataframe(d)
    n = len(df)
    half = n // 2
    pip = 0.1
    dt = df['time'].values.astype('datetime64[s]').astype('datetime64[ns]')

    # هندسهٔ منجمد از نیمهٔ جست‌وجو (بازتولید عینی اسکن S704)
    df_half = df.iloc[:half].reset_index(drop=True)
    tr_h = true_range(df_half)
    a55 = atr(tr_h, 55)
    a55_s = np.full(len(df_half), np.nan); a55_s[1:] = a55[:-1]
    atr55_med_pip = float(np.nanmedian(a55_s)) / pip
    sl_pip = spec['k_sl'] * atr55_med_pip
    tp_pip = RR * sl_pip
    mh = spec['max_hold']

    ev = build_events(df, spec['theta'])
    ev_next = np.zeros_like(ev); ev_next[1:] = ev[:-1]
    ls = pd.Series(ev_next == 1, index=df.index)
    ss = pd.Series(ev_next == -1, index=df.index)
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset='XAUUSD', max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 3:
        return None
    if 'win' not in tr.columns:
        tr = tr.copy()
        tr['win'] = (tr['pnl_pip'].to_numpy() > 0).astype(int)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = len(tr) - n_long

    # نول دوطرفهٔ اندازه‌گیری‌شده K=1000 (کش‌شونده)
    null_path = os.path.join(OUT, f'null_{tf}.json')
    if os.path.exists(null_path):
        null = json.load(open(null_path))
    else:
        null = {}
        lo, hi = 200, n - mh - 2
        no_sig = pd.Series(np.zeros(n, dtype=bool), index=df.index)
        sig = np.zeros(n, dtype=bool); sig[np.arange(lo, hi)] = True
        s_ser = pd.Series(sig, index=df.index)
        for side, n_side in (('long', n_long), ('short', n_short)):
            u_tr = se.simulate_trades(df, s_ser if side == 'long' else no_sig,
                                      no_sig if side == 'long' else s_ser,
                                      sl_pip=sl_pip, tp_pip=tp_pip,
                                      asset='XAUUSD', max_hold=mh,
                                      allow_overlap=True)
            w = (u_tr['pnl_pip'].to_numpy() > 0).astype(np.float64)
            uwr = float(w.mean() * 100)
            if n_side >= 3:
                perms = np.empty(K_PERM)
                for k in range(K_PERM):
                    take = rng.choice(len(w), size=min(n_side, len(w)),
                                      replace=False)
                    perms[k] = w[take].mean() * 100
                null[side] = dict(uncond_wr=uwr, perm_mean=float(perms.mean()),
                                  perm_sd=float(perms.std(ddof=1)),
                                  perm_max=float(perms.max()), perm_k=K_PERM,
                                  n_uncond=int(len(w)))
            else:
                null[side] = dict(uncond_wr=uwr, perm_mean=None, perm_sd=None,
                                  perm_max=None, perm_k=None)
        json.dump(null, open(null_path, 'w'), ensure_ascii=False, indent=1)

    wr = float((tr['pnl_pip'] > 0).mean() * 100)
    m = dict(card=f'XAUUSD_{tf}', tf=tf, tr=tr, dt=dt,
             lift=float(spec['alpha_search']),      # گزینش فقط با آمار جست‌وجو
             null=null, n=int(len(tr)), wr=wr,
             sl_pip=float(sl_pip), tp_pip=float(tp_pip), max_hold=int(mh),
             exp_pip=float(tr['pnl_pip'].mean()),
             half_time_ns=int(dt[half].astype('datetime64[ns]').astype(np.int64)))
    json.dump({k: v for k, v in m.items() if k not in ('tr', 'dt')},
              open(os.path.join(OUT, f'member_{tf}.json'), 'w'),
              ensure_ascii=False, indent=1, default=str)
    return m


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
    print('== S705 — استخر VolTS {H2,H6} · اعضا از پیش‌ثبت ==', flush=True)
    rng = np.random.default_rng(SEED)

    members = []
    for tf, spec in MEMBERS.items():
        t0 = time.time()
        m = build_member(tf, spec, rng)
        if m is None:
            print(f'   {tf}: ناکافی', flush=True)
            continue
        print(f"   {tf}: n_full={m['n']} WR={m['wr']:.2f}% "
              f"exp={m['exp_pip']:+.1f}pip SL={m['sl_pip']:.1f} "
              f"({time.time()-t0:.0f}s)", flush=True)
        members.append(m)

    if len(members) < 2:
        print('[توقف] کمتر از دو عضو ⇒ UNPROVEN.', flush=True)
        return

    # تجمیع — گزینش درونی خاموش (BUG-DEFAULTARG-safe): اعضا پیش‌ثبتی‌اند
    _orig = rp.choose_homogeneous_subset

    def _accept_all(cands, add_margin=None):
        return _orig(cands, add_margin=-1.0)

    try:
        rp.choose_homogeneous_subset = _accept_all
        res = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                                  lift=m['lift']) for m in members])
    finally:
        rp.choose_homogeneous_subset = _orig
    if res is None:
        print('[توقف] pool_cards عضوی نیافت.', flush=True)
        return

    pool = res['pool']
    print(f"[تجمیع] n_before={res['n_before']} → n_after={res['n_after']} "
          f"(FIFO حذف {100*(1-res['n_after']/max(res['n_before'],1)):.1f}%)",
          flush=True)
    share = pool['src_card'].value_counts(normalize=True)
    print(f"[سهم] {share.round(3).to_dict()}", flush=True)

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    shares = share.to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))

    # محور مشترک مصنوعی ۱ساعته (BUG-AXIS/QUANT/SPAN-safe)
    STEP_NS = 3600 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    print(f"[محور] {axis_dt[0]} → {axis_dt[-1]} · {len(axis_t):,} سطل", flush=True)

    ref = fd.as_dataframe(fd.load_fast('XAUUSD', 'H1'))
    ref_t = (ref['time'].values.astype('datetime64[s]')
             .astype('datetime64[ns]').astype(np.int64))
    ref_c = ref['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    axis_close = ref_c[pos]

    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, pool['t_entry'].values,
                                                'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(axis_t, pool['t_exit'].values,
                                               'left'), 0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    split_ns = max(m['half_time_ns'] for m in used_members)
    te = pool['t_entry'].values.astype(np.int64)
    holdout = te >= split_ns
    print(f"[تقسیم] مرز={np.datetime64(split_ns, 'ns')} · "
          f"اکتشاف={int((~holdout).sum())} · خارج‌نمونه={int(holdout.sum())}",
          flush=True)

    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=axis_dt, null=null, close=axis_close,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S705-POOL', r), flush=True)

    out = dict(members=[dict(card=m['card'], n=m['n'], wr=m['wr'],
                             lift_search=m['lift'], exp_pip=m['exp_pip'],
                             sl_pip=m['sl_pip'], tp_pip=m['tp_pip'],
                             max_hold=m['max_hold']) for m in members],
               used=[u['card'] for u in res['used']],
               n_before=res['n_before'], n_after=res['n_after'],
               member_share={k: float(v) for k, v in shares.items()},
               sl_pip_w=sl_med, tp_pip_w=tp_med, null=null,
               split_ns=int(split_ns),
               n_explore=int((~holdout).sum()), n_holdout=int(holdout.sum()),
               n_trials=N_TRIALS, seed=SEED, k_perm=K_PERM, rqs2=r)
    json.dump(out, open(os.path.join(OUT, 'verdict.json'), 'w'),
              ensure_ascii=False, indent=1, default=str)
    print('[ذخیره] results/_s705/verdict.json', flush=True)


if __name__ == '__main__':
    main()
