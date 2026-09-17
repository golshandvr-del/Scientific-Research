# -*- coding: utf-8 -*-
"""
S1960 — «رژیمِ ماندگاریِ محقق‌شده» (Kyle Realized-Permanence Regime, pooled) · XAUUSD
================================================================================
پیش‌ثبت: `results/S1960_PREREG_KYLE_REALIZED_PERMANENCE_REGIME.md` (commit 796057fa — پیش از هر آزمون).

پایهٔ منجمد S965: شوک high−low ≥ 2.618×ATR21[t−1]، ρ≥0.618، follow؛ SL=1.272×ATR، TP=2.058×ATR؛ hold=16.
گیت رژیم (علّی): j* = آخرین شوک ماندگار در [t−L, t−1]، L∈{55,144}؛ بدون j* ⇒ حذف.
  persisted = sign(body_j*)·(close[t−1]−close[j*]) > 0
  validated: persisted؛ invalidated: مکمل (P2). mode follow/against (P3).
خانواده/کارت: L{2}×arm{2}×mode{2} = ۸. کارت‌ها {D1,H12,H8,H6}. استخر: engine/rqs2_pool + blend-null S604.
n_trials=1572. SEED=1960. مسیر C. نول کارت: عین S965.
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
import engine.rqs2_pool as rp                  # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_scan_S1960'
os.makedirs(OUT, exist_ok=True)

SEED = 1960
K_PERM = 500
ATR_WIN = 21
COST_PIP = 3.3
WARM = 250
MAX_HOLD = 16
TH = 2.618
RHO = 0.618
K_SL, K_TP = 1.272, 2.058
Q_WIN = 233
DRIFT_K = 180

L_LIST = [55, 144]
ARMS = ['validated', 'invalidated']
MODES = ['follow', 'against']
N_TRIALS = 1572
SPLIT_FRAC = 0.50
ASSET = 'XAUUSD'

CARDS = ['D1', 'H12', 'H8', 'H6']


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
    s = pd.Series(x)
    return s.rolling(w, min_periods=w).median().shift(1).values


def calm_sigma_mask(c):
    """گیت S1911 (برای P5): σ² RiskMetrics علّی؛ σ_t ≤ median(σ_{t−233..t−1})."""
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


def drift_aligned_mask(F):
    """گیت S966 (برای P5): درفت ۱۸۰ کندلی هم‌جهت با شوک."""
    c = F['c']; n = len(c); K = DRIFT_K
    up = np.zeros(n, bool); dn = np.zeros(n, bool)
    if n > K + 1:
        up[K + 1:] = c[K:-1] > c[:-(K + 1)]
        dn[K + 1:] = c[K:-1] < c[:-(K + 1)]
    return (F['ev_up'] & up) | (F['ev_dn'] & dn)


def regime_masks(F, L):
    """validated/invalidated بر مبنای آخرین شوک ماندگار در [t−L, t−1] — O(n)."""
    n = F['n']; c = F['c']; sg = F['body_sgn']
    ev = F['ev_up'] | F['ev_dn']
    last_idx = np.full(n, -1, np.int64)
    last = -1
    for t in range(n):
        last_idx[t] = last            # آخرین شوک اکیداً قبل از t
        if ev[t]:
            last = t
    ar = np.arange(n)
    has = (last_idx >= 0) & ((ar - last_idx) <= L)
    j = np.where(has, last_idx, 0)
    prev_c = c[np.maximum(ar - 1, 0)]
    persisted = has & (sg[j] * (prev_c - c[j]) > 0)
    return dict(validated=persisted, invalidated=has & ~persisted, has=has)


def _signals(F, gm, mode):
    lu, ld = F['ev_up'] & gm, F['ev_dn'] & gm
    return (lu, ld) if mode == 'follow' else (ld, lu)


def _split_of(d):
    t_arr = np.asarray(d['time'], dtype=np.int64)
    return int(np.searchsorted(t_arr, (int(t_arr[0]) + int(t_arr[-1])) // 2))


def _dt(d):
    return (pd.to_datetime(np.asarray(d['time'], dtype=np.int64), unit='s', utc=True)
            .tz_localize(None).values.astype('datetime64[ns]'))


def judge_card(tf):
    """کشف روی نیمهٔ اول؛ داوری کارت روی کل داده؛ برگرداندن عضو استخر (اگر واجد شرایط)."""
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    src = d['src']; pip = se.ASSETS[ASSET]['pip']
    n_bars = len(d['close']); split = _split_of(d)

    df1 = _views_df(d, end=split)
    F = features(df1)
    ev1 = F['ev_up'] | F['ev_dn']
    controls = {'n_events': int(ev1.sum()), 'pass_rates': {}, 'base': None, 'invalidated': {}}
    tr_b, _, _ = _run(df1, F['ev_up'], F['ev_dn'], F['atr_prev'], K_SL, K_TP, ASSET, pip)
    controls['base'] = _stat(tr_b, K_SL, K_TP, screen=False)
    del tr_b
    best = None
    for L in L_LIST:
        RM = regime_masks(F, L)
        nh = int((ev1 & RM['has']).sum())
        controls['pass_rates'][f'L{L}'] = dict(
            with_prior=nh,
            validated=(round(float((ev1 & RM['validated']).sum()) / nh, 3) if nh else None))
        for arm in ARMS:
            for mode in MODES:
                ls, ss = _signals(F, RM[arm], mode)
                tr, _, _ = _run(df1, ls, ss, F['atr_prev'], K_SL, K_TP, ASSET, pip)
                st = _stat(tr, K_SL, K_TP, screen=True)
                if arm == 'invalidated' and mode == 'follow':
                    controls['invalidated'][f'L{L}'] = _stat(tr, K_SL, K_TP, screen=False)
                del tr
                if st and (best is None or st['stat'] > best['stat']):
                    best = dict(L=L, arm=arm, mode=mode, k_sl=K_SL, k_tp=K_TP, **st)
        gc.collect()
    del F, df1
    gc.collect()

    if best is None:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split, verdict='NO-SURVIVOR',
                   controls=controls, pool_eligible=False,
                   note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1, default=str)
        return rec, None

    fals = dict(winner_arm=best['arm'], winner_mode=best['mode'], p1_vs_base=None,
                p2_val_gt_inval=None, p4_pass_rate=None, p4_alive=None)
    eligible = (best['arm'] == 'validated' and best['mode'] == 'follow')
    if eligible:
        b = controls['base']; iv = controls['invalidated'].get(f"L{best['L']}")
        if b:
            fals['p1_vs_base'] = bool(best['lift'] > b['lift'])
        if iv:
            fals['p2_val_gt_inval'] = bool(best['lift'] > iv['lift'])
    pr = controls['pass_rates'][f"L{best['L']}"]['validated']
    if pr is not None:
        pra = pr if best['arm'] == 'validated' else round(1 - pr, 3)
        fals['p4_pass_rate'] = pra; fals['p4_alive'] = bool(0.30 <= pra <= 0.85)

    # ---------- داوری کارت روی کل داده ----------
    df = _views_df(d)
    F = features(df)
    RM = regime_masks(F, best['L'])
    ls, ss = _signals(F, RM[best['arm']], best['mode'])
    sig = ls | ss
    p5 = None
    if sig.sum() > 0:
        calm = calm_sigma_mask(F['c']); al = drift_aligned_mask(F)
        p5 = dict(calm_share=round(float((sig & calm).sum() / sig.sum()), 3),
                  drift_aligned_share=round(float((sig & al).sum() / sig.sum()), 3))
        del calm, al
    fals['p5'] = p5
    tr, sl_arr, tp_arr = _run(df, ls, ss, F['atr_prev'], K_SL, K_TP, ASSET, pip)
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best, n_bars=n_bars, split_bar=split)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1, default=str)
        return rec, None
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = sl_med * (K_TP / K_SL)
    null = build_null(df, ls, ss, sl_arr, tp_arr, MAX_HOLD, ASSET)
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=df['time'].values,
                            null=null, n_trials=N_TRIALS, split_bar=split, close=df['close'].values)
    mt = res['metrics']
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               member=dict(th=TH, rho=RHO, L=best['L'], arm=best['arm'], mode=best['mode'],
                           k_sl=K_SL, k_tp=K_TP, max_hold=MAX_HOLD,
                           sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2)),
               discovery={k: (round(v, 3) if isinstance(v, float) else v) for k, v in best.items()},
               controls=controls, falsifiers=fals, pool_eligible=eligible,
               null_meta=(null or {}).get('_meta'),
               verdict=res['verdict'], score=res['rqs2_score'],
               gates={g: (None if v is None else bool(v)) for g, v in res['gates'].items()},
               n=int(mt.get('n_trades', 0)), wr=mt.get('win_rate'), pf=mt.get('profit_factor'),
               net=mt.get('net_profit'), lift=mt.get('skill_lift_pp'), z=mt.get('skill_z'),
               p_perm=mt.get('skill_p_perm'), notes=res['notes'][:8], sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1, default=str)
    member = None
    if eligible and null is not None:
        wr = float((tr['outcome'] == 'win').mean() * 100)
        ref = null['long']['perm_mean']
        member = dict(card=f'{ASSET}-{tf}', tf=tf, tr=tr, dt=_dt(d), n=len(tr), wr=round(wr, 2),
                      lift=round(wr - ref, 4), null=null, sl_pip=sl_med, tp_pip=tp_med)
    return rec, member


def blend_null(gms, pool_df):
    """عین S604: نول مخلوط وزنی با سهم FIFO هر کارت."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        nu = du = nm = ns = dp = 0.0; kmin = None
        for g in gms:
            w = float(share.get(g['card'], 0.0))
            if w <= 0:
                continue
            dd = g['null'][side]
            if dd.get('uncond_wr') is not None:
                nu += dd['uncond_wr'] * w; du += w
            if dd.get('perm_mean') is not None:
                nm += dd['perm_mean'] * w; ns += (dd['perm_sd'] ** 2) * (w ** 2); dp += w
                k = dd.get('perm_k'); kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(uncond_wr=nu / du if du else None, perm_mean=nm / dp if dp else None,
                         perm_sd=float(np.sqrt(ns)) / dp if dp else None, perm_max=None, perm_k=kmin)
    return out


def adjudicate_pool(members):
    """عین S604/S606: FIFO تقویمی → محور H1 → نول مخلوط → compute_rqs2 یک‌بار."""
    res = rp.pool_cards([dict(card=g['card'], tr=g['tr'], dt=g['dt'], lift=g['lift']) for g in members])
    if res is None:
        rec = dict(verdict='NO-POOL', note='pool_cards returned None')
        json.dump(rec, open(f'{OUT}/POOL.json', 'w'), ensure_ascii=False, indent=1)
        return rec
    pool = res['pool']
    used = [g for g in members if g['card'] in set(pool['src_card'])]
    share = pool['src_card'].value_counts(normalize=True)
    null = blend_null(used, pool)
    by = {g['card']: g for g in used}
    sl_med = float(sum(by[c]['sl_pip'] * w for c, w in share.items()))
    tp_med = float(sum(by[c]['tp_pip'] * w for c, w in share.items()))
    STEP = 3600 * 1_000_000_000
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP, t_hi + 2 * STEP, STEP, dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    d1h = fd.load_fast(ASSET, 'H1')
    ref_t = _dt(d1h).astype(np.int64); ref_c = np.asarray(d1h['close'], float)
    axis_close = ref_c[np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0, len(ref_c) - 1)]
    del d1h
    pool = pool.copy()
    pool['entry_bar'] = np.clip(np.searchsorted(axis_t, pool['t_entry'].values.astype(np.int64), 'left'),
                                0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(np.clip(np.searchsorted(axis_t, pool['t_exit'].values.astype(np.int64), 'left'),
                                          0, len(axis_t) - 1), pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    te = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te, SPLIT_FRAC)); holdout = te >= split_ns
    r = rqs2.compute_rqs2(pool, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=axis_dt, null=null,
                          close=axis_close, holdout_mask=holdout, allow_overlap=False, n_trials=N_TRIALS)
    mt = r['metrics']
    rec = dict(verdict=r['verdict'], score=r['rqs2_score'],
               members=[dict(card=g['card'], n=g['n'], wr=g['wr'], lift=g['lift']) for g in used],
               dropped=res['dropped'], n_before=res['n_before'], n_after=res['n_after'],
               member_share=share.round(4).to_dict(), sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
               pool_null=null, split_utc=str(np.datetime64(split_ns, 'ns')), n_trials=N_TRIALS,
               gates={g: (None if v is None else bool(v)) for g, v in r['gates'].items()},
               n=int(mt.get('n_trades', 0)), wr=mt.get('win_rate'), pf=mt.get('profit_factor'),
               net=mt.get('net_profit'), lift=mt.get('skill_lift_pp'), z=mt.get('skill_z'),
               p_perm=mt.get('skill_p_perm'), notes=r['notes'][:8])
    json.dump(rec, open(f'{OUT}/POOL.json', 'w'), ensure_ascii=False, indent=1, default=str)
    return rec


def _line(tag, rec):
    return (f"[{tag}] verdict={rec.get('verdict')} score={rec.get('score')} n={rec.get('n')} "
            f"wr={rec.get('wr')} lift={rec.get('lift')} z={rec.get('z')} "
            f"fals={rec.get('falsifiers')} elig={rec.get('pool_eligible')}")


def main():
    args = sys.argv[1:] if len(sys.argv) > 1 else CARDS + ['pool']
    do_pool = 'pool' in args
    cards = [c for c in args if c != 'pool']
    members = []
    for tf in cards:
        try:
            rec, m = judge_card(tf)
            print(_line(tf, rec), flush=True)
            if m is not None:
                members.append(m)
        except Exception as e:                                     # noqa: BLE001
            print(f"[{tf}] ERROR {e!r}", flush=True)
            json.dump(dict(tf=tf, error=repr(e)), open(f'{OUT}/{tf}.json', 'w'))
        gc.collect()
    if do_pool:
        if len(members) >= 2:
            print(_line('POOL', adjudicate_pool(members)), flush=True)
        else:
            json.dump(dict(verdict='NO-POOL', n_eligible=len(members),
                           note='fewer than 2 eligible validated-follow cards'),
                      open(f'{OUT}/POOL.json', 'w'), ensure_ascii=False, indent=1)
            print(f'[POOL] NO-POOL eligible={len(members)}', flush=True)


if __name__ == '__main__':
    main()
