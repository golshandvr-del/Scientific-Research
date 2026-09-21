# -*- coding: utf-8 -*-
"""S1914 — «استخر آرامش» H8: چهار شوکِ مطلع در رژیم σ آرام، یک سبد FIFO تقویمی · XAUUSD-H8

پیش‌ثبت: results/S1914_PREREG_calm_shock_pool_h8.md (قبل از هر عدد)
اعضا (هر یک عیناً از فایل منتشرشده import؛ همه با گیت s605 W=233):
  A  انگل  : s604.load_raw('H8') + s605.regime_member(m, 233, 'CALM')          (S606-H8-CALM)
  B  سقف تازه: tools/s1521 {fresh_high, rho>=0.618, drift_mask, calm_mask}، LONG،
               SL=1.5×median(ATR100 EWM)، TP=1.5×SL — اجرا با se.simulate_trades (open بعد)   (S1520/S1521)
  C  کایل  : s1911.signals(df,'gated')                                           (S1911)
  D  پرش   : s1913.signals(df,'gated')                                           (S1913/S955)
استخر: engine.rqs2_pool.pool_cards (شرط ۲ و ۴ مکانیکی) + FIFO تقویمی + blend_pool_null (s431)
       محور H1 یکنواخت (اصلاح BUG-AXIS) + holdout_mask نیمهٔ دوم. n_trials=1.
اجرا: python3 strategies/s1914_calm_shock_pool.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                              # noqa: E402
from engine.rqs2 import compute_rqs2                               # noqa: E402
from engine.rqs2_pool import pool_cards                            # noqa: E402
from strategies.s431_lpsb_multicard_pool import blend_pool_null    # noqa: E402
from tools import s434_fast_data as fd                             # noqa: E402
import strategies.s604_engle_drift as S604                         # noqa: E402
import strategies.s605_engle_sigma_regime as S605                  # noqa: E402
import strategies.s1911_kyle_shock_calm as S1911                   # noqa: E402
import strategies.s1913_jump_aftermath_calm as S1913               # noqa: E402

SEED = 1914
N_PERM = 500
N_TRIALS = 1
TF = 'H8'
W_CALM = 233
ORDER = ['A_engle', 'B_freshhigh', 'C_kyle', 'D_jump']            # ترتیب پیش‌ثبت‌شده
CKPT_DIR = os.path.join(ROOT, 'results', '_s1914_ckpt')
B_MAX_HOLD = 34                                                    # S382/S1520: بدون max_hold صریح؛ 34 = TF_HOLD[H8] دیتابیس


def _mod(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, path))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def load_df():
    d = fd.load_fast('XAUUSD', TF)
    df = fd.as_dataframe(d)
    df.attrs['src'] = d.get('src', '?') if isinstance(d, dict) else '?'
    assert 'mt5_full' in str(df.attrs['src']), 'داده باید mt5_full باشد'
    t = pd.to_datetime(df['time'], unit='s')
    df.attrs['dt'] = t.to_numpy().astype('datetime64[ns]')
    df.attrs['span_years'] = (t.iloc[-1] - t.iloc[0]).days / 365.25
    return df


def stat(tr):
    if tr is None or len(tr) == 0:
        return {'n': 0}
    p = tr['pnl_pip'].to_numpy(); eq = np.cumsum(p)
    gp = p[p > 0].sum(); gl = -p[p < 0].sum()
    return {'n': int(len(tr)), 'wr': round(100 * float((p > 0).mean()), 2), 'e_pip': round(float(p.mean()), 2),
            'net_pip': round(float(p.sum()), 1), 'pf': round(float(gp / gl), 3) if gl > 0 else None,
            'maxdd_pip': round(float((np.maximum.accumulate(eq) - eq).max()), 1)}


def null_for(df, lm, sm, sl, tp, mh, warm, n_perm=N_PERM, seed=SEED):
    n = len(df)
    valid = np.zeros(n, bool); valid[warm:n - mh - 1] = True
    vidx = np.flatnonzero(valid); rng = np.random.default_rng(seed)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False); half = len(pick) // 2
    uml = np.zeros(n, bool); uml[pick[:half]] = True
    ums = np.zeros(n, bool); ums[pick[half:]] = True
    tu = se.simulate_trades(df, uml, ums, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if tu is not None and len(tu) else None
    kl, ks = int(lm.sum()), int(sm.sum()); k = kl + ks
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False); rng.shuffle(p)
        pl = np.zeros(n, bool); pl[p[:kl]] = True
        ps = np.zeros(n, bool); ps[p[kl:]] = True
        t = se.simulate_trades(df, pl, ps, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
        if t is not None and len(t):
            perm.append(100.0 * float((t['pnl_pip'].values > 0).mean()))
    pa = np.array(perm, float)
    d = dict(uncond_wr=wr_unc, perm_mean=float(pa.mean()) if pa.size else None,
             perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
             perm_max=float(pa.max()) if pa.size else None, perm_k=int(pa.size))
    return {'long': d, 'short': dict(d)}


def member_A(df):
    """انگل-CALM H8 عیناً S606: raw از S840 (health gate)، گیت از s605."""
    m = S604.load_raw(TF)
    sig = S605.sigma_series(m['cl'])
    m['reg'] = {W_CALM: S605.regime_ratio(sig, W_CALM)}
    S604.raw_member(m)                                     # health ✓ n=175 WR=60.57
    g, dens = S605.regime_member(m, W_CALM, 'CALM')
    return dict(card='A_engle', tr=g['tr'], dt=m['dt'], lift=g['lift'], null=g['null'],
                sl_pip=g['sl_pip'], tp_pip=g['tp_pip'], asset='XAUUSD',
                desc=dict(n=g['n'], wr=g['wr'], lift=g['lift'], pass=dens))


def member_B(df):
    """سقف تازهٔ مطلع در آرامش (S1521) — سیگنال از توابع منتشرشده، اجرا با se.simulate_trades."""
    R = _mod('tools/s1521_informed_fresh_high_calm_runner.py', '_s1521')
    L = _mod('strategies/s382_williamsr_momentum.py', '_s382')
    base = R.fresh_high(df) & (R.rho(df) >= R.RHO_THR) & R.drift_mask(df)
    calm, _ = R.calm_mask(df)
    lm = (base & calm).to_numpy(bool); sm = np.zeros(len(df), bool)
    pip = se.ASSETS['XAUUSD']['pip']
    sl_pip = float(np.nanmedian(L.atr(df).to_numpy())) * L.SL_K / pip
    tp_pip = sl_pip * L.RR
    tr = se.simulate_trades(df, lm, sm, sl_pip, tp_pip, 'XAUUSD', max_hold=B_MAX_HOLD, allow_overlap=False)
    warm = W_CALM + 60
    null = null_for(df, lm, sm, sl_pip, tp_pip, B_MAX_HOLD, warm)
    st = stat(tr); lift = st['wr'] - (null['long']['perm_mean'] or 0.0)
    return dict(card='B_freshhigh', tr=tr, dt=df.attrs['dt'], lift=lift, null=null,
                sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                desc=dict(**st, lift=round(lift, 2), n_sig=int(lm.sum()), base_sig=int(base.sum()),
                          note='S1521 published: n=87 WR=63.2 (close-entry simulator); here next-open entry'))


def member_from_harness(df, mod, card, mh):
    lm, sm, sl, tp, warm, _ = mod.signals(df, 'gated')
    tr = mod.run(df, lm, sm, sl, tp)
    null = null_for(df, lm, sm, sl, tp, mh, warm)
    st = stat(tr); lift = st['wr'] - (null['long']['perm_mean'] or 0.0)
    sl_med = float(np.median(tr['sl_pip']))
    return dict(card=card, tr=tr, dt=df.attrs['dt'], lift=lift, null=null, sl_pip=sl_med,
                tp_pip=float(np.median(tr['tp_pip'])) if 'tp_pip' in tr else sl_med * (tp[tr['entry_bar'].iloc[0]] / sl[tr['entry_bar'].iloc[0]]),
                asset='XAUUSD', desc=dict(**st, lift=round(lift, 2)))


def save(name, obj):
    os.makedirs(CKPT_DIR, exist_ok=True)
    with open(os.path.join(CKPT_DIR, name), 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    print(f'[ckpt] {name}')


def main():
    df = load_df()
    print(f'src={df.attrs["src"]} n={len(df)} span={df.attrs["span_years"]:.2f}y')
    members = [member_A(df), member_B(df),
               member_from_harness(df, S1911, 'C_kyle', S1911.MAX_HOLD),
               member_from_harness(df, S1913, 'D_jump', S1913.MAX_HOLD)]
    members.sort(key=lambda m: ORDER.index(m['card']))
    for m in members:
        print(f"[member] {m['card']}: {m['desc']}")
    save('members.json', {m['card']: dict(m['desc'], sl_pip=m['sl_pip'], tp_pip=m['tp_pip']) for m in members})

    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'], lift=m['lift']) for m in members])
    out = {'tf': TF, 'src': df.attrs['src'], 'n_trials': N_TRIALS,
           'members': {m['card']: m['desc'] for m in members}}
    if res is None:
        out['verdict'] = 'NO-POOL'; save('judge_POOL.json', out); print(out); return
    pl = res['pool']
    out.update(used=[u['card'] for u in res['used']], dropped=res['dropped'],
               n_before=res['n_before'], n_after=res['n_after'],
               fifo_cut_pct=round(100 * (1 - res['n_after'] / max(res['n_before'], 1)), 1),
               shares=pl['src_card'].value_counts(normalize=True).round(4).to_dict())
    used = [m for m in members if m['card'] in set(out['used'])]
    null = blend_pool_null(used, pl)
    by = {m['card']: m for m in used}
    sl_med = float(sum(by[c]['sl_pip'] * w for c, w in out['shares'].items() if c in by))
    tp_med = float(sum(by[c]['tp_pip'] * w for c, w in out['shares'].items() if c in by))
    # محور تقویمی مشترک H1 یکنواخت (s431 BUG-AXIS/BUG-SPAN)
    STEP = 3600 * 1_000_000_000
    t_lo = int(pl['t_entry'].values.astype(np.int64).min()); t_hi = int(pl['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP, t_hi + 2 * STEP, STEP, dtype=np.int64)
    ref_t = df.attrs['dt'].astype(np.int64); ref_c = df['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)
    pl = pl.copy()
    pl['entry_bar'] = np.clip(np.searchsorted(axis_t, pl['t_entry'].values.astype(np.int64), 'left'), 0, len(axis_t) - 1)
    pl['exit_bar'] = np.clip(np.searchsorted(axis_t, pl['t_exit'].values.astype(np.int64), 'left'), 0, len(axis_t) - 1)
    pl['exit_bar'] = np.maximum(pl['exit_bar'], pl['entry_bar'])
    pl = pl.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    split_ns = t_lo + (t_hi - t_lo) // 2
    holdout = pl['t_entry'].values.astype(np.int64) >= split_ns
    r = compute_rqs2(pl, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_t // 1_000_000_000,
                     close=ref_c[pos], null=null, holdout_mask=holdout, n_trials=N_TRIALS,
                     initial_capital=10000.0, allow_overlap=False)
    g = r.get('gates') or {}; m = r.get('metrics') or {}
    out.update(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'), pool_stat=stat(pl),
               sl_pip_med=round(sl_med, 1), tp_pip_med=round(tp_med, 1), null=null,
               failed_gates=sorted(k for k, v in g.items() if v is False), gates={k: g.get(k) for k in sorted(g)},
               metrics={k: m.get(k) for k in ('win_rate', 'null_ref_wr', 'breakeven_wr_cost', 'rr', 'z_obs',
                                              'z_luck_bound', 'z_margin', 'skill_p_perm', 'skill_lift_pp', 'p_emp',
                                              'perm_k', 'top_win_share', 'profit_factor', 'max_dd_pct', 'oos_wr', 'is_wr')},
               notes=(r.get('notes') or [])[:8])
    save('judge_POOL.json', out)
    print(f"POOL verdict={r.get('verdict')} score={r.get('rqs2_score')} used={out['used']} n={len(pl)} "
          f"fifo_cut={out['fifo_cut_pct']}% shares={out['shares']}")
    print(json.dumps({k: out[k] for k in ('pool_stat', 'dropped', 'failed_gates', 'metrics', 'notes')},
                     ensure_ascii=False, indent=1, default=str))


if __name__ == '__main__':
    main()
