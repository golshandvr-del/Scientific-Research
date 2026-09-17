# -*- coding: utf-8 -*-
"""
s686_shockday_london.py — S686: رویدادِ روزانه × ورودِ جلسه‌ایِ H1 (مسیرِ C)
================================================================================
پیش‌ثبت: results/S686_PREREG_SHOCKDAY_LONDON_RESUME.md (کامیت پیش از اجرا).

دو حالت:
  --explore   : فقط نیمهٔ اولِ H1، ۶ سلولِ قفل، غربالِ نالِ غیرشرطی.
  --adjudicate: یک بار روی کلِ داده با نامزدِ مکانیکی از JSONِ اکتشاف.
  --m1control : اجرایِ کنترلیِ M1 (هزینه؛ نه داوری، نه گزینش).
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from engine import rqs2                                    # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402
from strategies.s680_lagsat_adjudicate import build_null   # noqa: E402
from strategies.s684_kalman_explore import (               # noqa: E402
    atr_wilder, uncond_wr)

EXPLORE_DIR = os.path.join(ROOT, 'results', '_s686_explore')
ADJ_DIR = os.path.join(ROOT, 'results', '_s686_adjudicate')

BS = (1.272, 1.618)
RRS = (1.0, 1.5, 2.0)
RHO = 0.618
W_DRIFT_D = 60
LONDON_H = 7
WARM = 400
MH = {'H1': 13, 'M1': 34}
K_PERM = 500
N_TRIALS = 295
SEED = 20260830


def daily_shock_days(t, o, h, l, c, b):
    """روزهای شوکِ روزانهٔ هم‌جهت با رانش — از سریِ درون‌روزی (علّی در پایانِ روز).

    برمی‌گرداند dict day_index -> direction(+1/-1) و آماره‌ها.
    """
    day = (t // 86400).astype(np.int64)
    days, first = np.unique(day, return_index=True)
    nd = len(days)
    O = o[first]
    C = np.empty(nd); H = np.empty(nd); L = np.empty(nd)
    last = np.append(first[1:], len(t))
    for k in range(nd):
        s, e = first[k], last[k]
        C[k] = c[e - 1]; H[k] = h[s:e].max(); L[k] = l[s:e].min()
    atr = atr_wilder(H, L, C, 21)
    atr_prev = np.concatenate(([np.nan], atr[:-1]))
    body = C - O
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(H - L > 0, body / (H - L), 0.0)
    shock = (np.abs(body) >= b * atr_prev) & (np.abs(rho) >= RHO)
    drift = np.full(nd, np.nan)
    drift[W_DRIFT_D + 1:] = C[W_DRIFT_D:-1] - C[:-W_DRIFT_D - 1]
    aligned = shock & (np.sign(body) == np.sign(drift)) & (drift != 0)
    st = dict(n_days=int(nd), n_shock=int(np.nansum(shock)),
              n_aligned=int(np.nansum(aligned)),
              drift_pass=round(float(aligned.sum() / max(1, shock.sum())), 3))
    return days, aligned, np.sign(body), st


def signals(t, o, h, l, c, b, warm=WARM):
    """سیگنالِ H1: اولین بارِ روزِ بعدیِ موجود با hour>=7."""
    days, aligned, sgn, st = daily_shock_days(t, o, h, l, c, b)
    day = (t // 86400).astype(np.int64)
    hour = ((t % 86400) // 3600).astype(np.int64)
    n = len(t)
    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)
    day_to_pos = {}
    for i in range(n):
        if day[i] not in day_to_pos:
            day_to_pos[day[i]] = i
    day_list = np.array(sorted(day_to_pos))
    for k in np.flatnonzero(aligned):
        d = days[k]
        # روزِ بعدیِ موجود
        j = np.searchsorted(day_list, d, side='right')
        if j >= len(day_list):
            continue
        nd_ = day_list[j]
        i0 = day_to_pos[nd_]
        i = i0
        while i < n and day[i] == nd_ and hour[i] < LONDON_H:
            i += 1
        if i >= n or day[i] != nd_:
            continue
        if sgn[k] > 0:
            long_sig[i] = True
        else:
            short_sig[i] = True
    long_sig[:warm] = False
    short_sig[:warm] = False
    return long_sig, short_sig, st


def explore(tf='H1', asset='XAUUSD'):
    t0 = time.time()
    d = fd.load_fast(asset, tf); src = d['src']
    df_full = fd.as_dataframe(d); del d; gc.collect()
    n_full = len(df_full); n_half = n_full // 2
    df = df_full.iloc[:n_half].reset_index(drop=True); del df_full; gc.collect()
    t = df['time'].values.astype(np.int64)
    o = df['open'].values; h = df['high'].values; l = df['low'].values; c = df['close'].values
    pip = se.ASSETS[asset]['pip']
    cost = se.ASSETS[asset]['spread_pip'] + 2 * se.ASSETS[asset]['slip_pip']
    a34 = atr_wilder(h, l, c, 34)
    sl = round(float(np.median(a34[100:]) / pip) * 1.618, 1)
    mh = MH[tf]
    rng = np.random.default_rng(SEED)
    unc = {str(rr): uncond_wr(df, asset, sl, round(rr * sl, 1), mh, rng) for rr in RRS}
    print(f'[{tf}] uncond: ' + ' | '.join(f"rr{rr}: L{unc[str(rr)]['long']['wr']} S{unc[str(rr)]['short']['wr']}" for rr in RRS), flush=True)
    cells = []; gate_stats = {}
    for b in BS:
        ls_, ss_, st = signals(t, o, h, l, c, b)
        gate_stats[f'b{b}'] = st
        nsig = int(ls_.sum() + ss_.sum())
        for rr in RRS:
            tp = round(rr * sl, 1)
            if nsig == 0:
                cells.append(dict(b=b, rr=rr, n=0, skipped='no_sig')); continue
            tr = se.simulate_trades(df, ls_, ss_, sl, tp, asset, max_hold=mh, allow_overlap=False)
            if tr is None or len(tr) == 0:
                cells.append(dict(b=b, rr=rr, n=0, skipped='no_trades')); continue
            pnl = tr['pnl_pip'].values; dirv = tr['direction'].values
            isl = (dirv == 'long') if dirv.dtype.kind in 'OU' else (dirv > 0)
            n = len(pnl); nl = int(isl.sum()); ns = n - nl
            wr = 100.0 * float((pnl > 0).mean()); u = unc[str(rr)]
            ref = (nl * u['long']['wr'] + ns * u['short']['wr']) / n
            lift = wr - ref
            zsc = lift / max(1e-9, 100.0 * np.sqrt(ref / 100 * (1 - ref / 100) / n))
            be = 100.0 * (sl + cost) / (sl + tp)
            cells.append(dict(b=b, rr=rr, n=n, n_long=nl, n_sig=nsig, wr=round(wr, 2),
                              uncond_ref=round(ref, 2), lift_uncond=round(lift, 2),
                              be_wr=round(be, 2), lift_be=round(wr - be, 2),
                              wr_long=round(100 * float((pnl[isl] > 0).mean()), 2) if nl else None,
                              wr_short=round(100 * float((pnl[~isl] > 0).mean()), 2) if ns else None,
                              exp_pip=round(float(pnl.mean()), 3), z_screen=round(float(zsc), 2)))
    res = dict(asset=asset, tf=tf, src=src, n_full=n_full, n_half=n_half, sl_pip=sl,
               atr_per=34, sl_mult=1.618, max_hold=mh, cost_pip=cost, warm=WARM,
               rho=RHO, w_drift_days=W_DRIFT_D, london_hour=LONDON_H, uncond=unc,
               gate_stats=gate_stats, grid_cells=len(BS) * len(RRS), cells=cells,
               elapsed_s=round(time.time() - t0, 1))
    os.makedirs(EXPLORE_DIR, exist_ok=True)
    json.dump(res, open(os.path.join(EXPLORE_DIR, f'explore_{tf}.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'[{tf}] done {res["elapsed_s"]}s sl={sl} gates={gate_stats}', flush=True)
    for cc in cells:
        print('  ', cc, flush=True)
    return res


def pick_candidate(cells):
    ok = [c for c in cells if 'skipped' not in c and c['n'] >= 30 and c['exp_pip'] > 0 and c['lift_uncond'] > 0]
    if not ok:
        return None, 'no_valid_cells'
    by = {(c['b'], c['rr']): c for c in cells if 'skipped' not in c}
    ok.sort(key=lambda c: c['z_screen'], reverse=True)
    for c in ok:
        if any(by.get((b2, c['rr']), {}).get('lift_uncond', -99) > 0 for b2 in BS if b2 != c['b']):
            return c, 'plateau_ok'
    return None, 'no_plateau'


def adjudicate(tf='H1', asset='XAUUSD'):
    t0 = time.time()
    ex = json.load(open(os.path.join(EXPLORE_DIR, f'explore_{tf}.json'), encoding='utf-8'))
    cand, why = pick_candidate(ex['cells'])
    if cand is None:
        print(f'[{tf}] هیچ نامزدی — {why}', flush=True)
        os.makedirs(ADJ_DIR, exist_ok=True)
        json.dump(dict(layer='S686', tf=tf, verdict_engine=None, selection=why),
                  open(os.path.join(ADJ_DIR, f'adj_{tf}.json'), 'w'), indent=1)
        return None
    sl = float(ex['sl_pip']); tp = round(float(cand['rr']) * sl, 1); mh = int(ex['max_hold'])
    if tp < sl:
        raise ValueError('TP<SL')
    d = fd.load_fast(asset, tf); src = d['src']
    df = fd.as_dataframe(d); del d; gc.collect()
    n_full = len(df); split = n_full // 2
    t = df['time'].values.astype(np.int64)
    print(f'\n═══ داوریِ S686 {asset}-{tf} ═══\n  نامزد: b={cand["b"]} rr={cand["rr"]} ({why})\n'
          f'  هندسه: SL={sl} TP={tp} mh={mh} | src={src} n_full={n_full:,} split={split:,}', flush=True)
    ls_, ss_, st = signals(t, df['open'].values, df['high'].values, df['low'].values,
                           df['close'].values, float(cand['b']))
    trades = se.simulate_trades(df, ls_, ss_, sl, tp, asset, max_hold=mh, allow_overlap=False)
    pnl = trades['pnl_pip'].values
    print(f'  کلِ داده: n={len(trades):,} WR={100 * (pnl > 0).mean():.2f}% exp={pnl.mean():+.2f}pip gates={st}', flush=True)
    null = build_null(df, asset, ls_, ss_, sl, tp, mh, k_perm=K_PERM, seed=SEED, verbose=True)
    r = rqs2.compute_rqs2(trades, asset, sl_pip=sl, tp_pip=tp, bar_time=t, null=null,
                          n_trials=N_TRIALS, split_bar=split, close=df['close'].values)
    res = dict(layer='S686', tf=tf, asset=asset, src=src, n_full=n_full, split_bar=split,
               candidate=cand, selection=why, sl_pip=sl, tp_pip=tp, max_hold=mh,
               n_trades=int(len(trades)), wr_full=round(100 * float((pnl > 0).mean()), 2),
               exp_pip_full=round(float(pnl.mean()), 3), gate_stats_full=st, null=null,
               n_trials=N_TRIALS, k_perm=K_PERM,
               entry_days=sorted(set((t[trades['entry_bar'].values] // 86400).tolist())),
               rqs2=r, elapsed_s=round(time.time() - t0, 1))
    os.makedirs(ADJ_DIR, exist_ok=True)
    json.dump(res, open(os.path.join(ADJ_DIR, f'adj_{tf}.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, default=str)
    m = r.get('metrics') or {}
    print(f'\n  ⚖️ حکمِ موتور [{tf}]: {r.get("verdict")} · score={r.get("rqs2_score")} · '
          f'skill_p_perm={m.get("skill_p_perm")} · z={m.get("skill_z")} · lift={m.get("skill_lift_pp")}pp · WR={m.get("win_rate")}', flush=True)
    g = r.get('gates') or {}
    print('  گیت‌ها: ' + ' '.join(f'{k}={g[k]}' for k in sorted(g)), flush=True)
    return res


def m1_control(asset='XAUUSD'):
    """کنترلِ هزینه روی M1 — نیمهٔ اول، هندسهٔ M1، b=1.272 و 1.618، RR=1. نه داوری."""
    d = fd.load_fast(asset, 'M1'); df_full = fd.as_dataframe(d); del d; gc.collect()
    n_half = len(df_full) // 2
    df = df_full.iloc[:n_half].reset_index(drop=True); del df_full; gc.collect()
    t = df['time'].values.astype(np.int64)
    pip = se.ASSETS[asset]['pip']
    a34 = atr_wilder(df['high'].values, df['low'].values, df['close'].values, 34)
    sl = round(float(np.median(a34[100:]) / pip) * 1.618, 1)
    out = {}
    for b in BS:
        ls_, ss_, st = signals(t, df['open'].values, df['high'].values, df['low'].values, df['close'].values, b)
        tr = se.simulate_trades(df, ls_, ss_, sl, sl, asset, max_hold=MH['M1'], allow_overlap=False)
        pnl = tr['pnl_pip'].values if tr is not None and len(tr) else np.array([])
        out[str(b)] = dict(n=int(len(pnl)), wr=round(100 * float((pnl > 0).mean()), 2) if len(pnl) else None,
                           exp_pip=round(float(pnl.mean()), 3) if len(pnl) else None, gates=st)
        print(f'[M1 control] b={b} sl={sl}: {out[str(b)]}', flush=True)
    os.makedirs(EXPLORE_DIR, exist_ok=True)
    json.dump(dict(control='M1', sl_pip=sl, note='cost control only; not adjudicated', cells=out),
              open(os.path.join(EXPLORE_DIR, 'control_M1.json'), 'w'), indent=1)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--explore', action='store_true')
    ap.add_argument('--adjudicate', action='store_true')
    ap.add_argument('--m1control', action='store_true')
    a = ap.parse_args()
    if a.m1control:
        m1_control()
    if a.explore:
        explore()
    if a.adjudicate:
        adjudicate()
