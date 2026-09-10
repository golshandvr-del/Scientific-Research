# -*- coding: utf-8 -*-
"""
S969 — «شوکِ مطلع در بازارِ پُرنویز» (Kyle Noisy-Depth Shock) · XAUUSD — آخرین لایهٔ بلوک
================================================================================
پیش‌ثبت: `results/S969_PREREG_KYLE_NOISY_DEPTH.md` (commit 02777238 — پیش از هر آزمون).

پایهٔ منجمد S965: شوک high−low ≥ 2.618×ATR21[t−1]، ρ≥0.618، follow، ورود open t+1.
گیت پیشین (علّی): ER_W[t] = |close[t−1]−close[t−1−W]| / Σ_{t−W..t−1} range،  W∈{21,55}
  thr[t] = median(ER_W[t−233..t−1]) (پنجرهٔ بستهٔ گذشته — روش S606)
  noisy: ER_W ≤ thr (فرضیهٔ λ پایین)؛ efficient: ER_W > thr (کنترل P2).
خانواده: W{2}×arm{2}×mode{2}×geom{2} = ۱۶/کارت؛ ۱۹ TF؛ n_trials=1532؛ SEED=969.
P5: سهم رویدادهای noisy که هم‌زمان σ آرام S1911 هستند (σ² RiskMetrics 0.94/0.06،
σ_t ≤ median(σ_{t−233..t−1})) — فقط گزارش.
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

OUT = 'results/_scan_S969'
os.makedirs(OUT, exist_ok=True)

SEED = 969
K_PERM = 500
ATR_WIN = 21
COST_PIP = 3.3
WARM = 250
MAX_HOLD = 16
TH = 2.618
RHO = 0.618
Q_WIN = 233

W_LIST = [21, 55]
ARMS = ['noisy', 'efficient']
MODES = ['follow', 'against']
GEOMS = [(1.0, 1.618), (1.272, 2.058)]
N_TRIALS = 1532

TFS = ['MN1', 'W1', 'D1', 'H12', 'H8', 'H6', 'H3', 'H2', 'H1', 'M30', 'M20',
       'M15', 'M12', 'M10', 'M6', 'M5', 'M4', 'M3', 'M1']


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
                atr_prev=atr_prev, body_sgn=body_sgn, n=n, c=c, rng=rng)


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



def _roll_median_prev(x, w):
    """median(x[t−w..t−1]) — پنجرهٔ بستهٔ گذشته (shift 1)؛ NaN تا پر شدن پنجره."""
    s = pd.Series(x)
    return s.rolling(w, min_periods=w).median().shift(1).values


def er_series(c, rng, W):
    """ER_W[t] = |c[t−1]−c[t−1−W]| / Σ_{j=t−W}^{t−1} rng_j — همه تا t−1."""
    n = len(c)
    er = np.full(n, np.nan)
    if n <= W + 1:
        return er
    rs = _rollsum(rng, W)                     # Σ rng[t−W+1..t]
    num = np.abs(c[W:-1] - c[:-(W + 1)])      # index t = W+1..n−1 → |c[t−1]−c[t−1−W]|
    den = rs[W:-1]                            # Σ rng[t−W..t−1]
    with np.errstate(divide='ignore', invalid='ignore'):
        er[W + 1:] = np.where(den > 0, num / den, np.nan)
    return er


def calm_sigma_mask(c):
    """گیت S1911 برای P5: σ² RiskMetrics علّی؛ σ_t ≤ median(σ_{t−233..t−1})."""
    n = len(c)
    r = np.zeros(n)
    r[1:] = np.log(c[1:] / c[:-1])
    var = np.zeros(n)
    v = float(np.var(r[1:min(n, WARM)])) if n > 2 else 1e-8
    for i in range(n):
        if i > 0:
            v = 0.94 * v + 0.06 * r[i - 1] ** 2
        var[i] = v
    sig = np.sqrt(var)
    med = _roll_median_prev(sig, Q_WIN)
    return np.nan_to_num(sig, nan=np.inf) <= np.nan_to_num(med, nan=-np.inf)


def gate_masks(F):
    """برای هر W: ماسک noisy و efficient (NaN ⇒ هیچ‌کدام)."""
    out = {}
    for W in W_LIST:
        er = er_series(F['c'], F['rng'], W)
        thr = _roll_median_prev(er, Q_WIN)
        ok = ~np.isnan(er) & ~np.isnan(thr)
        out[W] = {'noisy': ok & (er <= thr), 'efficient': ok & (er > thr)}
    return out


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

    # ---------- کشف: نیمهٔ اول ----------
    df1 = _views_df(d, end=split)
    F = features(df1)
    ev1 = F['ev_up'] | F['ev_dn']
    GM = gate_masks(F)
    n_ev = int(ev1.sum())
    pass_rates = {}
    for W in W_LIST:
        ok = GM[W]['noisy'] | GM[W]['efficient']
        nv = int((ev1 & ok).sum())
        pass_rates[f'W{W}'] = dict(valid=nv,
                                   noisy=(round(float((ev1 & GM[W]['noisy']).sum()) / nv, 3) if nv else None))
    controls = {'n_events': n_ev, 'pass_rates': pass_rates, 'base': {}, 'efficient': {}}
    for (k_sl, k_tp) in GEOMS:
        tag = f'{k_sl}/{k_tp}'
        tr_b, _, _ = _run(df1, F['ev_up'], F['ev_dn'], F['atr_prev'], k_sl, k_tp, asset, pip)
        controls['base'][tag] = _stat(tr_b, k_sl, k_tp, screen=False)
        del tr_b
    best = None
    for W in W_LIST:
        for arm in ARMS:
            gm = GM[W][arm]
            for mode in MODES:
                ls, ss = _signals(F, gm, mode)
                for (k_sl, k_tp) in GEOMS:
                    tr, _, _ = _run(df1, ls, ss, F['atr_prev'], k_sl, k_tp, asset, pip)
                    st = _stat(tr, k_sl, k_tp, screen=True)
                    if arm == 'efficient' and mode == 'follow':
                        controls['efficient'][f'W{W}:{k_sl}/{k_tp}'] = _stat(tr, k_sl, k_tp, screen=False)
                    del tr
                    if st and (best is None or st['stat'] > best['stat']):
                        best = dict(W=W, arm=arm, mode=mode, k_sl=k_sl, k_tp=k_tp, **st)
            gc.collect()
    del F, df1, GM
    gc.collect()

    if best is None:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split, verdict='NO-SURVIVOR',
                   controls=controls, note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1, default=str)
        return rec

    fals = dict(p1_vs_base=None, p2_noisy_gt_eff=None, p4_pass_rate=None, p4_alive=None,
                p5_calm_share=None, winner_arm=best['arm'])
    tag = f"{best['k_sl']}/{best['k_tp']}"
    b = controls['base'].get(tag)
    ef = controls['efficient'].get(f"W{best['W']}:{tag}")
    if best['mode'] == 'follow' and best['arm'] == 'noisy':
        if b:
            fals['p1_vs_base'] = bool(best['lift'] > b['lift'])
        if ef:
            fals['p2_noisy_gt_eff'] = bool(best['lift'] > ef['lift'])
    pr = pass_rates[f"W{best['W']}"]['noisy']
    if pr is not None:
        pr_arm = pr if best['arm'] == 'noisy' else round(1 - pr, 3)
        fals['p4_pass_rate'] = pr_arm
        fals['p4_alive'] = bool(0.30 <= pr_arm <= 0.85)

    # ---------- داوری یک‌باره روی کل داده ----------
    df = _views_df(d)
    F = features(df)
    GM = gate_masks(F)
    gm = GM[best['W']][best['arm']]
    ls, ss = _signals(F, gm, best['mode'])
    sig = ls | ss
    if sig.sum() > 0:
        calm = calm_sigma_mask(F['c'])
        fals['p5_calm_share'] = round(float((sig & calm).sum() / sig.sum()), 3)
        del calm
    tr, sl_arr, tp_arr = _run(df, ls, ss, F['atr_prev'], best['k_sl'], best['k_tp'], asset, pip)
    del GM, gm
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
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               member=dict(th=TH, rho=RHO, W=best['W'], arm=best['arm'], q_win=Q_WIN,
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
