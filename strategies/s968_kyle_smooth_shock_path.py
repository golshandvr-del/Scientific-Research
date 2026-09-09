# -*- coding: utf-8 -*-
"""
S968 — «مسیرِ هموارِ شوک» (Kyle Smooth Shock Path — sub-bar decomposition) · XAUUSD
================================================================================
پیش‌ثبت: `results/S968_PREREG_KYLE_SMOOTH_SHOCK_PATH.md`
(commit 8893d10d — پیش از اجرای هر آزمونی).

پایهٔ منجمد S965 روی TF درشت X: شوک high−low ≥ 2.618×ATR21[t−1] و ρ≥0.618؛ follow.
زیرکندل‌ها از TF ریز Y (SUB_TF): همهٔ کندل‌های Y درون [time_X[t], time_X[t]+len(X)).
  r_j = close_j − open_j ؛ K = تعداد زیرکندل (K<3 ⇒ نامعتبر)
  conc    = (HHI − 1/K)/(1 − 1/K)،  HHI = Σ (|r_j|/Σ|r_j|)²
  dircons = #{sign(r_j) == sign(body_t)} / K
بازوی smooth: conc ≤ C (C∈{0.25,0.40}) یا dircons ≥ D (D∈{0.618,0.75}).
خانواده: metric{2}×thr{2}×mode{2}×geom{2} = ۱۶/کارت. n_trials=1228. SEED=968.
کنترل‌ها (نیمهٔ کشف، فقط گزارش): base (بی‌گیت) و concentrated (مکمل آستانهٔ برنده).
مدل صفر: عین S965 (K=500، سه تلهٔ s434، perm_k=تعداد جایگشت، uncond chunked).
"""
import sys
import os
import gc
import json
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_scan_S968'
os.makedirs(OUT, exist_ok=True)

SEED = 968
K_PERM = 500
ATR_WIN = 21
COST_PIP = 3.3
WARM = 250
MAX_HOLD = 16
TH = 2.618
RHO = 0.618
MIN_SUB = 3

METRICS = {'conc': [0.25, 0.40], 'dircons': [0.618, 0.75]}
MODES = ['follow', 'against']
GEOMS = [(1.0, 1.618), (1.272, 2.058)]
N_TRIALS = 1228

SUB_TF = {'MN1': 'D1', 'W1': 'D1', 'D1': 'H1', 'H12': 'H1', 'H8': 'H1',
          'H6': 'H1', 'H3': 'M15', 'H2': 'M15', 'H1': 'M5', 'M30': 'M3',
          'M20': 'M3', 'M15': 'M3', 'M12': 'M1', 'M10': 'M1', 'M6': 'M1',
          'M5': 'M1', 'M4': 'M1', 'M3': 'M1'}
TFS = ['MN1', 'W1', 'D1', 'H12', 'H8', 'H6', 'H3', 'H2', 'H1', 'M30', 'M20',
       'M15', 'M12', 'M10', 'M6', 'M5', 'M4', 'M3']


def _views_df(d, end=None):
    sl = slice(None, end)
    return pd.DataFrame({'time': d['time'][sl], 'open': d['open'][sl],
                         'high': d['high'][sl], 'low': d['low'][sl],
                         'close': d['close'][sl], 'volume': d['volume'][sl]},
                        copy=False)


def _rollsum(x, w):
    n = len(x)
    cs = np.concatenate(([0.0], np.cumsum(x)))
    if w >= n:
        return cs[1:].copy()
    out = np.empty(n)
    out[:w - 1] = cs[1:w]
    out[w - 1:] = cs[w:] - cs[:n - w + 1]
    return out


def features(df):
    o = np.asarray(df['open'].values, dtype=np.float64)
    h = np.asarray(df['high'].values, dtype=np.float64)
    l = np.asarray(df['low'].values, dtype=np.float64)
    c = np.asarray(df['close'].values, dtype=np.float64)
    n = len(c)
    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr = _rollsum(tr_arr, ATR_WIN) / ATR_WIN
    del tr_arr
    atr_prev = np.empty(n)
    atr_prev[0] = atr[0]
    atr_prev[1:] = atr[:-1]
    del atr
    rng = h - l
    shock = (rng >= TH * atr_prev) & (rng > 0) & (atr_prev > 1e-12)
    body = c - o
    rho = np.divide(np.abs(body), rng, out=np.zeros_like(rng), where=rng > 0)
    body_sgn = np.sign(body)
    idx = np.arange(n)
    ev = shock & (idx >= WARM) & (body_sgn != 0) & (rho >= RHO)
    return dict(ev_up=ev & (body_sgn > 0), ev_dn=ev & (body_sgn < 0),
                atr_prev=atr_prev, body_sgn=body_sgn, n=n)


def sub_metrics(tf, t_x, ev_mask, body_sgn):
    """conc/dircons/K برای هر کندل رویداد X از زیرکندل‌های Y. فقط کندل‌های رویداد محاسبه می‌شوند."""
    n = len(t_x)
    conc = np.full(n, np.nan)
    dirc = np.full(n, np.nan)
    kcnt = np.zeros(n, np.int32)
    sub = SUB_TF[tf]
    dy = fd.load_fast('XAUUSD', sub)
    t_y = np.asarray(dy['time'], dtype=np.int64)
    r_y = np.asarray(dy['close'], dtype=np.float64) - np.asarray(dy['open'], dtype=np.float64)
    del dy
    span = fd.TF_MINUTES[tf] * 60
    ev_idx = np.flatnonzero(ev_mask)
    lo = np.searchsorted(t_y, t_x[ev_idx], side='left')
    hi = np.searchsorted(t_y, t_x[ev_idx] + span, side='left')
    for i, a, b in zip(ev_idx, lo, hi):
        k = b - a
        kcnt[i] = k
        if k < MIN_SUB:
            continue
        r = r_y[a:b]
        s = np.abs(r).sum()
        if s <= 0:
            continue
        w = np.abs(r) / s
        hhi = float((w * w).sum())
        conc[i] = (hhi - 1.0 / k) / (1.0 - 1.0 / k)
        dirc[i] = float((np.sign(r) == body_sgn[i]).mean())
    del t_y, r_y
    gc.collect()
    return conc, dirc, kcnt, sub


def gate_mask(metric, thr, conc, dirc, kcnt, smooth=True):
    valid = kcnt >= MIN_SUB
    if metric == 'conc':
        m = np.nan_to_num(conc, nan=np.inf) <= thr
    else:
        m = np.nan_to_num(dirc, nan=-np.inf) >= thr
    return (m if smooth else ~m) & valid


def _run(df, ls, ss, atr_ref, k_sl, k_tp, asset, pip):
    sl_arr = np.maximum(k_sl * atr_ref / pip, 1e-9)
    tp_arr = np.maximum(k_tp * atr_ref / pip, 1e-9)
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset,
                            max_hold=MAX_HOLD, allow_overlap=False)
    return tr, sl_arr, tp_arr


def _stat(tr, k_sl, k_tp, screen):
    if tr is None or len(tr) == 0:
        return None
    n = len(tr)
    exp_pip = float(tr['pnl_pip'].mean())
    if screen and (n < 30 or exp_pip <= 0):
        return None
    wr = float((tr['outcome'] == 'win').mean())
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (k_tp / k_sl)
    be_rob = (sl_med + 2 * COST_PIP) / (sl_med + tp_med)
    lift = (wr - be_rob) * 100.0
    return dict(stat=lift * np.sqrt(n), n=n, wr=round(wr * 100, 2),
                be_rob=round(be_rob * 100, 2), lift=round(lift, 3),
                exp_pip=round(exp_pip, 2), sl_med=sl_med, tp_med=tp_med)


def _wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return float((tr['outcome'] == 'win').mean() * 100.0)


def build_null(df, ls, ss, sl_arr, tp_arr, mh, asset, seed=SEED, K=K_PERM):
    n = len(df)
    sig_n = int((ls | ss).sum())
    if sig_n < 30:
        return None
    valid = np.zeros(n, bool)
    valid[WARM:n - mh - 1] = True
    z = np.zeros(n, bool)
    UNC_CAP = 250_000
    rng = np.random.default_rng(seed)
    vidx_all = np.flatnonzero(valid)
    if len(vidx_all) == 0:
        return None
    if len(vidx_all) > UNC_CAP:
        unc_idx = np.sort(rng.choice(vidx_all, size=UNC_CAP, replace=False))
    else:
        unc_idx = vidx_all
    unc_wins = unc_n = 0
    CH = 25_000
    for s0 in range(0, len(unc_idx), CH):
        pm = np.zeros(n, bool)
        pm[unc_idx[s0:s0 + CH]] = True
        tr_c = se.simulate_trades(df, pm, z, sl_arr, tp_arr, asset,
                                  max_hold=mh, allow_overlap=True)
        if tr_c is not None and len(tr_c):
            unc_wins += int((tr_c['outcome'] == 'win').sum())
            unc_n += int(len(tr_c))
        del tr_c, pm
        gc.collect()
    wr_unc = (unc_wins / unc_n * 100.0) if unc_n else None
    del unc_idx
    k = min(sig_n, len(vidx_all))
    perm_wrs = []
    for _ in range(K):
        pick = rng.choice(vidx_all, size=k, replace=False)
        pm = np.zeros(n, bool)
        pm[pick] = True
        tr_p = se.simulate_trades(df, pm, z, sl_arr, tp_arr, asset,
                                  max_hold=mh, allow_overlap=False)
        w = _wr_of(tr_p)
        del tr_p, pm
        if w is not None:
            perm_wrs.append(w)
    pa = np.array(perm_wrs, float)
    side = dict(uncond_wr=wr_unc,
                perm_mean=float(pa.mean()) if pa.size else None,
                perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                perm_max=float(pa.max()) if pa.size else None,
                perm_k=int(pa.size))
    return {'long': dict(side), 'short': dict(side),
            '_meta': {'n_perm': int(pa.size), 'draw_size': int(k), 'uncond_n': unc_n}}


def _split_of(d):
    t_arr = np.asarray(d['time'], dtype=np.int64)
    return int(np.searchsorted(t_arr, (int(t_arr[0]) + int(t_arr[-1])) // 2))


def _signals(F, gm, mode):
    lu, ld = F['ev_up'] & gm, F['ev_dn'] & gm
    return (lu, ld) if mode == 'follow' else (ld, lu)


def judge_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    src, asset = d['src'], 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    n_bars = len(d['close'])
    split = _split_of(d)
    t_x = np.asarray(d['time'], dtype=np.int64)

    # ---------- کشف: نیمهٔ اول ----------
    df1 = _views_df(d, end=split)
    F = features(df1)
    ev1 = F['ev_up'] | F['ev_dn']
    conc, dirc, kcnt, sub = sub_metrics(tf, t_x[:split], ev1, F['body_sgn'])
    n_ev = int(ev1.sum())
    valid_ev = int((ev1 & (kcnt >= MIN_SUB)).sum())
    pass_rates = {}
    for metric, thrs in METRICS.items():
        for thr in thrs:
            gm = gate_mask(metric, thr, conc, dirc, kcnt)
            pass_rates[f'{metric}<={thr}' if metric == 'conc' else f'{metric}>={thr}'] = \
                round(float((ev1 & gm).sum()) / valid_ev, 3) if valid_ev else None
    controls = {'n_events': n_ev, 'n_valid_sub': valid_ev, 'sub_tf': sub,
                'pass_rates': pass_rates, 'base': {}, 'concentrated': {}}
    for (k_sl, k_tp) in GEOMS:
        tag = f'{k_sl}/{k_tp}'
        tr_b, _, _ = _run(df1, F['ev_up'], F['ev_dn'], F['atr_prev'], k_sl, k_tp, asset, pip)
        controls['base'][tag] = _stat(tr_b, k_sl, k_tp, screen=False)
        del tr_b
    best = None
    for metric, thrs in METRICS.items():
        for thr in thrs:
            gm = gate_mask(metric, thr, conc, dirc, kcnt)
            for mode in MODES:
                ls, ss = _signals(F, gm, mode)
                for (k_sl, k_tp) in GEOMS:
                    tr, _, _ = _run(df1, ls, ss, F['atr_prev'], k_sl, k_tp, asset, pip)
                    st = _stat(tr, k_sl, k_tp, screen=True)
                    del tr
                    if st and (best is None or st['stat'] > best['stat']):
                        best = dict(metric=metric, thr=thr, mode=mode, k_sl=k_sl, k_tp=k_tp, **st)
            gc.collect()
    # کنترل concentrated برای همهٔ آستانه‌ها (follow، هر دو geom) — فقط گزارش
    for metric, thrs in METRICS.items():
        for thr in thrs:
            gm = gate_mask(metric, thr, conc, dirc, kcnt, smooth=False)
            for (k_sl, k_tp) in GEOMS:
                ls, ss = _signals(F, gm, 'follow')
                tr, _, _ = _run(df1, ls, ss, F['atr_prev'], k_sl, k_tp, asset, pip)
                controls['concentrated'][f'{metric}:{thr}:{k_sl}/{k_tp}'] = _stat(tr, k_sl, k_tp, screen=False)
                del tr
    del F, df1, conc, dirc, kcnt
    gc.collect()

    if best is None:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split, verdict='NO-SURVIVOR',
                   controls=controls, note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1, default=str)
        return rec

    fals = dict(p1_vs_base=None, p2_smooth_gt_conc=None, p4_pass_rate=None)
    tag = f"{best['k_sl']}/{best['k_tp']}"
    b = controls['base'].get(tag)
    cc = controls['concentrated'].get(f"{best['metric']}:{best['thr']}:{tag}")
    if best['mode'] == 'follow':
        if b:
            fals['p1_vs_base'] = bool(best['lift'] > b['lift'])
        if cc:
            fals['p2_smooth_gt_conc'] = bool(best['lift'] > cc['lift'])
    pr_key = f"{best['metric']}<={best['thr']}" if best['metric'] == 'conc' else f"{best['metric']}>={best['thr']}"
    pr = pass_rates.get(pr_key)
    fals['p4_pass_rate'] = pr
    fals['p4_alive'] = (None if pr is None else bool(0.30 <= pr <= 0.85))

    # ---------- داوری یک‌باره روی کل داده ----------
    df = _views_df(d)
    F = features(df)
    ev = F['ev_up'] | F['ev_dn']
    conc, dirc, kcnt, _ = sub_metrics(tf, t_x, ev, F['body_sgn'])
    gm = gate_mask(best['metric'], best['thr'], conc, dirc, kcnt)
    ls, ss = _signals(F, gm, best['mode'])
    tr, sl_arr, tp_arr = _run(df, ls, ss, F['atr_prev'], best['k_sl'], best['k_tp'], asset, pip)
    del conc, dirc, kcnt, gm
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best, n_bars=n_bars, split_bar=split)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1, default=str)
        return rec
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (best['k_tp'] / best['k_sl'])
    null = build_null(df, ls, ss, sl_arr, tp_arr, MAX_HOLD, asset)
    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split, close=df['close'].values)
    mt = res['metrics']
    rec = dict(tf=tf, src=src, sub_src=sub, n_bars=n_bars, split_bar=split,
               member=dict(th=TH, rho=RHO, metric=best['metric'], thr=best['thr'],
                           mode=best['mode'], k_sl=best['k_sl'], k_tp=best['k_tp'],
                           max_hold=MAX_HOLD, sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2)),
               discovery={k: (round(v, 3) if isinstance(v, float) else v) for k, v in best.items()},
               controls=controls, falsifiers=fals,
               null_meta=(null or {}).get('_meta'),
               verdict=res['verdict'], score=res['rqs2_score'],
               gates={g: (None if v is None else bool(v)) for g, v in res['gates'].items()},
               n=int(mt.get('n_trades', 0)), wr=mt.get('win_rate'), pf=mt.get('profit_factor'),
               net=mt.get('net_profit'), lift=mt.get('skill_lift_pp'), z=mt.get('skill_z'),
               p_perm=mt.get('skill_p_perm'), notes=res['notes'][:8], sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1, default=str)
    return rec


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        try:
            rec = judge_tf(tf)
            print(f"[{tf}] verdict={rec.get('verdict')} score={rec.get('score')} n={rec.get('n')} "
                  f"wr={rec.get('wr')} lift={rec.get('lift')} z={rec.get('z')} "
                  f"fals={rec.get('falsifiers')} ({rec.get('sec')}s)", flush=True)
        except Exception as e:                                     # noqa: BLE001
            print(f"[{tf}] ERROR {e!r}", flush=True)
            json.dump(dict(tf=tf, error=repr(e)), open(f'{OUT}/{tf}.json', 'w'))
        gc.collect()


if __name__ == '__main__':
    main()
