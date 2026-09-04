# -*- coding: utf-8 -*-
"""
S796 — داوری رسمی (یک بار) — Volume-Climax Fade, Drift-Aligned — استخر {H3,H6,H8,H12}
طبق strategies/S796_PREREG.md (کامیت 8fc69b20). هیچ پارامتری اینجا جست‌وجو نمی‌شود.
پروتکل استخر: engine/rqs2_pool.pool_cards + blend_pool_null (الگوی S431/S770-pool2).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2
from engine.rqs2_pool import pool_cards

LAYER = 796
PIP = 0.10
K_REL, LD, KSL, RR = 2.618, 90, 3.33, 1.0
MH = {'H3': 24, 'H6': 16, 'H8': 13, 'H12': 10}
MEMBERS = ('H3', 'H6', 'H8', 'H12')
N_TRIALS = 212
K_PERM = 500
HOLDOUT_START = np.datetime64('2018-11-16T03:00:00').astype('datetime64[ns]').astype(np.int64)
HERE = os.path.dirname(os.path.abspath(__file__))


def atr89(h, l, c):
    n = len(c)
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    tr = np.r_[h[0] - l[0], tr]
    a = np.empty(n); a[0] = tr[0]; al = 2 / 90
    for i in range(1, n):
        a[i] = a[i - 1] + (tr[i] - a[i - 1]) * al
    return np.r_[np.nan, a[:-1]]


def cmed(v, w=89):
    import bisect
    from collections import deque
    n = len(v); out = np.full(n, np.nan); buf = []; q = deque()
    for i in range(n):
        if len(q) == w:
            old = q.popleft(); buf.pop(bisect.bisect_left(buf, old))
        if buf:
            m = len(buf); out[i] = buf[m // 2] if m % 2 else 0.5 * (buf[m // 2 - 1] + buf[m // 2])
        bisect.insort(buf, v[i]); q.append(v[i])
    return out


def member_for(tf, rng):
    d = fd.load_fast('XAUUSD', tf); df = fd.as_dataframe(d)
    assert 'mt5_full' in d['src'], 'E-16 guard'
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    v = df['volume'].values.astype(float); n = len(c)
    atr = atr89(h, l, c); vmed = cmed(v); relv = v / vmed
    r = np.r_[0.0, np.diff(c)]
    dr = np.full(n, np.nan); dr[LD:] = c[LD - 1:-1] - c[:n - LD]
    dirn = -np.sign(r)
    valid = ~np.isnan(vmed) & ~np.isnan(atr) & ~np.isnan(dr)
    sig = valid & (relv >= K_REL) & (r != 0) & (np.sign(dr) == dirn)
    ls = sig & (dirn > 0); ss = sig & (dirn < 0)
    sl = np.where(~np.isnan(atr), KSL * atr / PIP, 0.0); tp = sl * RR
    tr = se.simulate_trades(df, ls, ss, sl, tp, 'XAUUSD', max_hold=MH[tf], allow_overlap=False)
    nL = int((tr['direction'] == 'long').sum()); nS = len(tr) - nL
    wr = 100 * (tr['pnl_pip'] > 0).mean()
    print(f'[member {tf}] src={d["src"]} bars={n} n={len(tr)} (L={nL},S={nS}) WR={wr:.2f}', flush=True)

    # نول متعارف: uncond (allow_overlap=True روی همهٔ کندل‌های معتبر) + K=500 جایگشت با حفظ nL/nS
    vi = np.where(valid)[0]; zero = np.zeros(n, bool)
    null = {}
    for side, ns in (('long', nL), ('short', nS)):
        dd = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)
        if ns >= 1:
            s_all = np.zeros(n, bool); s_all[vi] = True
            ta = se.simulate_trades(df, s_all if side == 'long' else zero, zero if side == 'long' else s_all,
                                    sl, tp, 'XAUUSD', max_hold=MH[tf], allow_overlap=True)
            dd['uncond_wr'] = float(100 * (ta['pnl_pip'] > 0).mean())
            wrs = []
            for _ in range(K_PERM):
                pick = vi[np.sort(rng.choice(len(vi), ns, replace=False))]
                s2 = np.zeros(n, bool); s2[pick] = True
                tp_ = se.simulate_trades(df, s2 if side == 'long' else zero, zero if side == 'long' else s2,
                                         sl, tp, 'XAUUSD', max_hold=MH[tf], allow_overlap=True)
                if len(tp_):
                    wrs.append(float(100 * (tp_['pnl_pip'] > 0).mean()))
            a = np.asarray(wrs)
            dd.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = dd
        print(f'    null {side}: {json.dumps(dd)}', flush=True)
    lift = wr - np.nanmean([null[s]['perm_mean'] for s in null if null[s]['perm_mean'] is not None])
    dt = pd.to_datetime(df['time'], unit='s').values
    return dict(card=f'XAUUSD_{tf}', tr=tr, dt=dt, lift=float(lift), null=null,
                sl_med=float(np.nanmedian(sl[sl > 0])), tp_med=float(np.nanmedian(tp[tp > 0])), src=d['src'])


def blend_pool_null(members_used, pool_df):
    w_by_card = pool_df['src_card'].value_counts().to_dict(); out = {}
    for side in ('long', 'short'):
        num_u = num_m = num_s = den_u = den_p = 0.0; kmin = None
        for m in members_used:
            w = float(w_by_card.get(m['card'], 0))
            if w <= 0: continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * w; den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w; num_s += (d['perm_sd'] ** 2) * (w ** 2); den_p += w
                k = d.get('perm_k'); kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(uncond_wr=(num_u / den_u) if den_u > 0 else None,
                         perm_mean=(num_m / den_p) if den_p > 0 else None,
                         perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
                         perm_max=None, perm_k=kmin)
    return out


def main():
    rng = np.random.default_rng(LAYER)
    members = [member_for(tf, rng) for tf in MEMBERS]
    # نکته: pool_cards عضو با lift<=0 را طبق پروتکل حذف می‌کند (شرط ۲) — این بخشی از پروتکل رسمی است و
    # در پیش‌ثبت اعلام شده (استخر = pool_cards). گزارش کامل اعضای حذف‌شده منتشر می‌شود.
    res = pool_cards(members)
    if res is None:
        print('[S796] no valid member ⇒ REJECT_BY_RULE'); return
    print(f"[pool selection] {json.dumps(res['selection'], default=str)}")
    print(f"[pool] used={res['used']} dropped={res['dropped']} n_before={res['n_before']} n_after={res['n_after']}", flush=True)
    pool = res['pool']; used = {u['card'] for u in res['used']}
    mu = [m for m in members if m['card'] in used]
    null = blend_pool_null(mu, pool)
    print('[pool null]', json.dumps(null, default=str), flush=True)

    dh = fd.load_fast('XAUUSD', 'H1'); assert 'mt5_full' in dh['src']
    ref_t = dh['time'].astype(np.int64) * 10**9; ref_c = dh['close'].astype(np.float64)
    pool = pool.sort_values('t_entry', kind='mergesort').reset_index(drop=True)
    pool['entry_bar'] = np.clip(np.searchsorted(ref_t, pool['t_entry'].values, 'left'), 0, len(ref_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(ref_t, pool['t_exit'].values, 'left'), 0, len(ref_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    bar_time = (ref_t / 10**9).astype('int64')
    holdout = pool['t_entry'].values.astype(np.int64) >= HOLDOUT_START
    print(f'[split] holdout from 2018-11-16T03 | explore={int((~holdout).sum())} oos={int(holdout.sum())}', flush=True)
    sl_med = float(np.median([m['sl_med'] for m in mu])); tp_med = float(np.median([m['tp_med'] for m in mu]))

    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time, null=null,
                          close=ref_c, holdout_mask=holdout, n_trials=N_TRIALS, allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S796-POOL', r), flush=True)
    safe = lambda m: {k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in m.items()}
    out = dict(layer=LAYER, prereg='strategies/S796_PREREG.md@8fc69b20', rule=dict(K=K_REL, Ld=LD, ksl=KSL, rr=RR, mh=MH),
               members=[dict(card=u['card'], lift=u['lift'], n=u['n']) for u in res['used']], dropped=res['dropped'],
               src={m['card']: m['src'] for m in members}, n_before=res['n_before'], n_after=res['n_after'],
               n_trials=N_TRIALS, holdout_start='2018-11-16T03:00:00Z', null=null,
               verdict=r['verdict'], rqs2_score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics=safe(r.get('metrics', {})), notes=r.get('notes'))
    with open(os.path.join(HERE, 's796_final_result_POOL.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    pool.to_json(os.path.join(HERE, 's796_trades_POOL.json'), orient='records')
    print(f"\n[S796 OFFICIAL] {r['verdict']} score={r.get('rqs2_score')}", flush=True)


if __name__ == '__main__':
    main()
