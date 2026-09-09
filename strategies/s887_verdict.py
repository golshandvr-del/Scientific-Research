#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S887 — آزمونِ نهاییِ Path C روی **نیمهٔ دوم** (hold-out) — یک بار، فقط یک بار.

پیش‌ثبت: results/S887_PREREG_StraightLineShock_PathC.md (commit 605edaa8)
شوک بزرگ (range ≥ θ×ATR21[t−1]) + گیت کارایی مسیر درون‌کندلی M15 (eff ≥ m×median233 غلتان)، follow؛ هیچ چندک منجمدی
وجود ندارد؛ فقط sl/tp منجمد از نیمهٔ اول. محور side از نامزد IS منجمد است.
null کانونی K=500 per-side؛ compute_rqs2 با هر ۵ ورودی؛ n_trials=48؛ seed=887.
usage: python3 strategies/s887_verdict.py <TF> [<TF> ...]
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2
from strategies.s887_feasibility import build_s887, s887_signals, SUB_TF
from strategies.s880_entropy_collapse_scan import wr_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, 'results', '_scan_S887')
N_TRIALS = 48
N_PERM = 500


def null_side(df, side, n_side, sl, tp, hold, rng, n_perm=N_PERM):
    d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
             perm_max=None, perm_k=None)
    n = len(df)
    lo, hi = 200, n - hold - 2
    if hi <= lo or n_side < 1:
        return d
    pool = np.arange(lo, hi)
    z = np.zeros(n, dtype=bool)
    step = max(1, len(pool) // 20000)
    sig = np.zeros(n, dtype=bool); sig[pool[::step]] = True
    tr = se.simulate_trades(df, sig if side == 'long' else z,
                            z if side == 'long' else sig,
                            sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                            max_hold=hold, allow_overlap=False)
    w, m = wr_of(tr)
    d['uncond_wr'] = w
    wrs = []
    for _ in range(n_perm):
        pick = rng.choice(pool, size=min(n_side, len(pool)), replace=False)
        s2 = np.zeros(n, dtype=bool); s2[pick] = True
        t2 = se.simulate_trades(df, s2 if side == 'long' else z,
                                z if side == 'long' else s2,
                                sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                max_hold=hold, allow_overlap=False)
        w2, m2 = wr_of(t2)
        if w2 is not None:
            wrs.append(w2)
    if wrs:
        a = np.asarray(wrs)
        d.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                 perm_max=float(a.max()), perm_k=int(len(a)))
    return d


def judge_tf(tf):
    t0 = time.time()
    with open(os.path.join(SCAN, f'XAUUSD_{tf}.json')) as f:
        scan = json.load(f)
    best = scan.get('best')
    out = {'tf': tf, 'candidate': best}
    if not best:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'no eligible IS candidate — hold-out untouched'
        return out

    th, m, side, hold = best['theta'], best['m'], best['side'], best['hold']
    sl, tp = best['sl_pip'], best['tp_pip']

    d = fd.load_fast('XAUUSD', tf)
    out['src'] = d['src']
    assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
    df_all = fd.as_dataframe(d)
    half = scan['half_idx']
    warm = 233 + 21 + 5   # طبق پیش‌ثبت §4
    df2 = df_all.iloc[half - warm:].reset_index(drop=True)
    high = df2['high'].values; low = df2['low'].values
    close = df2['close'].values

    big = {k: df2[k].values.astype(np.float64) for k in ('time', 'open', 'high', 'low', 'close')}
    ds = fd.load_fast('XAUUSD', SUB_TF)
    out['sub_src'] = ds['src']
    assert 'mt5_full' in ds['src'], f'E-16 trap (sub): {ds["src"]}'
    t0s = float(big['time'][0]); t1s = float(big['time'][-1]) + fd.TF_MINUTES[tf] * 60
    msk = (ds['time'] >= t0s) & (ds['time'] < t1s)
    sub = {k: np.asarray(ds[k][msk], dtype=np.float64) for k in ('time', 'open', 'close')}
    del ds
    pre = build_s887(big, sub, tf)
    ls, ss = s887_signals(pre, th, m)
    ls = ls.copy(); ss = ss.copy()
    ls[:warm] = False; ss[:warm] = False
    if side == 'long':
        ss[:] = False
    out['n_long_sig'] = int(ls.sum()); out['n_short_sig'] = int(ss.sum())

    trades = se.simulate_trades(df2, ls, ss, sl_pip=sl, tp_pip=tp,
                                asset='XAUUSD', max_hold=hold,
                                allow_overlap=False)
    wr, n = wr_of(trades)
    out['oos_n'] = n
    out['oos_wr'] = wr
    if n == 0:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'zero OOS trades'
        return out

    nl = int((trades['direction'] == 'long').sum())
    ns = n - nl
    if nl > 0:
        out['oos_wr_long'] = round(100.0 * float((trades[trades['direction'] == 'long']['pnl_pip'] > 0).mean()), 2)
    if ns > 0:
        out['oos_wr_short'] = round(100.0 * float((trades[trades['direction'] == 'short']['pnl_pip'] > 0).mean()), 2)

    rng = np.random.default_rng(887)
    null = {'long': null_side(df2, 'long', max(nl, 1), sl, tp, hold, rng),
            'short': null_side(df2, 'short', max(ns, 1), sl, tp, hold, rng)}
    out['null'] = null

    split_idx = len(df2) // 2
    r = rqs2.compute_rqs2(trades, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                          bar_time=df2['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split_idx,
                          close=df2['close'].values)
    out['verdict'] = r['verdict']
    out['rqs2_score'] = r['rqs2_score']
    out['gates'] = r['gates']
    out['metrics'] = {kk: (float(vv) if isinstance(vv, (int, float, np.floating)) else vv)
                      for kk, vv in r['metrics'].items()}
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def main():
    for tf in sys.argv[1:]:
        res = judge_tf(tf)
        def _default(o):
            if isinstance(o, (np.integer,)): return int(o)
            if isinstance(o, (np.floating,)): return float(o)
            if isinstance(o, np.ndarray): return o.tolist()
            if isinstance(o, np.bool_): return bool(o)
            return str(o)
        with open(os.path.join(SCAN, f'VERDICT_XAUUSD_{tf}.json'), 'w') as f:
            json.dump(res, f, ensure_ascii=False, indent=1, default=_default)
        print(tf, '→', res.get('verdict'), res.get('rqs2_score'),
              'n=', res.get('oos_n'), 'wr=', res.get('oos_wr'),
              'L/S=', res.get('oos_wr_long'), '/', res.get('oos_wr_short'),
              flush=True)


if __name__ == '__main__':
    main()
