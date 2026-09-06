# -*- coding: utf-8 -*-
"""
S695 — Drift-Gated Keltner Displacement — XAUUSD {H3,H6,H8,H12}
=================================================================
پیش‌ثبت: results/S695_PREREG_DRIFT_GATED_DISPLACEMENT.md (کامیت 3251386f — قبل از این فایل)

قاعده (منجمد):
  band = EMA_p ± 2.618·ATR_p · رویداد = لبهٔ عبور close از باند (S694)
  گیت = sign(close[t−1] − close[t−1−K_bars]) هم‌علامت با جهت · K_bars = K_days × bars_per_day
  ورود open t+1 · SL=k_sl·ATR_p · TP=max(rr·SL,SL) · hold=96h
خانواده: p∈{21,34} × K_days∈{30,60,90} × k_sl∈{1.0,1.618} × rr∈{1.618,2.058} = 24/side
n_trials = 120 (72 ارثی S694 + 48)
نال شرطی: جامعهٔ نال = همهٔ کندل‌های معتبر که گیت دریفتِ برنده را (per side) پاس می‌کنند.
"""
import sys, os, json, gc, subprocess, argparse, time as _time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from engine import rqs2                                     # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies.s351_lpsb import atr_series                 # noqa: E402
from strategies.s694_keltner_displacement import (          # noqa: E402
    bars_per_hour, ema_series, displacement_signals)
from tools import s434_fast_data as fd                      # noqa: E402

P_GRID     = (21, 34)
KDAY_GRID  = (30, 60, 90)
SL_K_GRID  = (1.0, 1.618)
RR_GRID    = (1.618, 2.058)
K_BAND     = 2.618
N_TRIALS   = 120
HOLD_HOURS = 96.0
SPLIT_FRAC = 0.60
N_PERM     = 500
N_UNCOND_CAP = 25000
SEED       = 695
ASSET      = 'XAUUSD'
TF_ORDER   = ['H3', 'H6', 'H8', 'H12']
OUT_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'results', 's695_runs')
MIN_SPAN_YEARS = 15.0                     # درس S694 (تلهٔ E-16 در کلون تازه)


def drift_mask(close, k_bars):
    """گیت علّی: drift[t] = close[t−1] − close[t−1−k]. برمی‌گرداند (long_ok, short_ok)."""
    n = len(close)
    dr = np.full(n, np.nan)
    if k_bars + 1 < n:
        dr[k_bars + 1:] = close[k_bars:-1] - close[:-(k_bars + 1)]
    return dr > 0, dr < 0


def uncond_wr(df, pop, atr, k_sl, rr, hold, flag, rng):
    pick = pop if len(pop) <= N_UNCOND_CAP else \
        np.sort(rng.choice(pop, size=N_UNCOND_CAP, replace=False))
    sl = k_sl * atr[pick]
    ok = np.isfinite(sl) & (sl > 0)
    s = queue_rr(df, pick[ok], np.full(ok.sum(), flag), sl[ok], ASSET, hold, rr)
    return (float(s['wr']) if s else None, int(s['n']) if s else 0)


def build_null(df, pop_by_side, atr_by_p, geo_by_side, n_by_side, hold, rng):
    null = {}
    for side, flag in (('long', True), ('short', False)):
        dnull = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                     perm_max=None, perm_k=None)
        p, k_sl, rr = geo_by_side[side]
        atr = atr_by_p[p]
        pop = pop_by_side[side]
        n_side = n_by_side[side]
        if n_side >= 1 and len(pop) > n_side:
            dnull['uncond_wr'] = uncond_wr(df, pop, atr, k_sl, rr, hold, flag, rng)[0]
            slv = k_sl * atr[pop]
            ok = np.isfinite(slv) & (slv > 0)
            vi, slv = pop[ok], slv[ok]
            wrs = []
            for _ in range(N_PERM):
                pick = np.sort(rng.choice(len(vi), size=n_side, replace=False))
                s = queue_rr(df, vi[pick], np.full(n_side, flag), slv[pick],
                             ASSET, hold, rr)
                if s:
                    wrs.append(s['wr'])
            if wrs:
                a = np.asarray(wrs)
                dnull.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = dnull
        print(f"    null {side:<5} (gated pop={len(pop)}) uncond={dnull['uncond_wr']} "
              f"μ={dnull['perm_mean']} σ={dnull['perm_sd']} K={dnull['perm_k']}",
              flush=True)
    return null


def run_tf(tf, do_git=True):
    t0 = _time.time()
    print(f"\n{'='*88}\n=== S695 Drift-Gated Displacement :: XAUUSD-{tf} ===", flush=True)
    d = fd.load_fast(ASSET, tf)
    span = float(d.get('span_years', 0) or 0)
    if span < MIN_SPAN_YEARS or 'mt5_full' not in str(d.get('src', '')):
        raise RuntimeError(f"E-16 trap: src={d.get('src')} span={span}y — اجرا متوقف")
    for _k in ('volume', 'hour', 'minute', 'dow'):
        d.pop(_k, None)
    gc.collect()
    df = pd.DataFrame({'time': d['time'], 'open': d['open'], 'high': d['high'],
                       'low': d['low'], 'close': d['close']}, copy=False)
    n = len(df)
    close = d['close'].astype(np.float64)
    print(f"    bars={n:,}  src={d['src']}  span={span}y", flush=True)

    bph = bars_per_hour(d['time'])
    hold = max(1, int(round(HOLD_HOURS * bph)))
    kbars = {kd: max(1, int(round(kd * 24 * bph))) for kd in KDAY_GRID}
    warmup = max(4 * max(P_GRID), max(kbars.values()) + 2, 60)
    split = int(n * SPLIT_FRAC)
    c = cost_pip(ASSET)
    print(f"    hold={hold} bars (96h) · K_bars={kbars} · warmup={warmup} · "
          f"split_bar={split} · cost={c:.2f}pip", flush=True)

    out = dict(strategy='S695', concept='drift_gated_keltner_displacement', asset=ASSET,
               tf=tf, bars=n, src=d['src'], span_years=span, hold_bars=hold,
               split_bar=split, n_trials=N_TRIALS, k_band=K_BAND, k_bars=kbars,
               family='2x3x2x2=24/side (cum 120)', cost_pip=c)

    rng = np.random.default_rng(SEED)

    # ── ۱) اندیکاتورها، رویدادهای خام، گیت‌ها ──
    atr_by_p, raw_sig, gates = {}, {}, {}
    for p in P_GRID:
        atr_by_p[p] = atr_series(df, p=p)
        ema = ema_series(close, p)
        raw_sig[p] = displacement_signals(close, ema, atr_by_p[p], K_BAND, warmup)
        del ema
    for kd, kb in kbars.items():
        gates[kd] = drift_mask(close, kb)          # (long_ok, short_ok)
    sig_map = {}
    for p in P_GRID:
        for kd in KDAY_GRID:
            lo, so = gates[kd]
            sL = raw_sig[p]['long'];  sL = sL[lo[sL]]
            sS = raw_sig[p]['short']; sS = sS[so[sS]]
            sig_map[(p, kd)] = {'long': sL, 'short': sS}
            print(f"    p={p} K={kd}d: raw L={len(raw_sig[p]['long'])} S={len(raw_sig[p]['short'])}"
                  f" → gated L={len(sL)} S={len(sS)}", flush=True)
    gc.collect()

    # ── ۲) جامعهٔ نال شرطی TRAIN per (p, kd, side) ──
    valid_all = np.arange(warmup, n - hold - 2)
    fin = np.ones(len(valid_all), dtype=bool)
    for p in P_GRID:
        a = atr_by_p[p][valid_all]
        fin &= np.isfinite(a) & (a > 0)
    valid_all = valid_all[fin]
    valid_tr = valid_all[valid_all < split]
    u_cache = {}

    def u_train(p, kd, side, k_sl, rr):
        key = (p, kd, side, k_sl, rr)
        if key not in u_cache:
            lo, so = gates[kd]
            pop = valid_tr[(lo if side == 'long' else so)[valid_tr]]
            u_cache[key] = uncond_wr(df, pop, atr_by_p[p], k_sl, rr, hold,
                                     side == 'long', rng)[0]
        return u_cache[key]

    # ── ۳) جست‌وجوی ۲۴ سلول per side — فقط TRAIN ──
    best = {'long': None, 'short': None}
    scan = []
    for (p, kd), sm in sig_map.items():
        atr = atr_by_p[p]
        for side, flag in (('long', True), ('short', False)):
            sig = sm[side]
            sig_tr = sig[sig < split - hold]
            if len(sig_tr) < 5:
                continue
            for k_sl in SL_K_GRID:
                sl = k_sl * atr[sig_tr]
                okm = np.isfinite(sl) & (sl > 0)
                for rr in RR_GRID:
                    st = queue_rr(df, sig_tr[okm], np.full(okm.sum(), flag),
                                  sl[okm], ASSET, hold, rr)
                    if not st:
                        continue
                    u_wr = u_train(p, kd, side, k_sl, rr)
                    if u_wr is None:
                        continue
                    lift = st['wr'] - u_wr
                    n_req = rqs2.n_required_for_h3(lift, u_wr / 100.0) \
                        if lift > 0 else float('inf')
                    score = lift * np.sqrt(st['n']) if lift > 0 else -1e9
                    feas = st['n'] >= n_req
                    scan.append(dict(p=p, K=kd, k_sl=k_sl, rr=rr, side=side,
                                     n=st['n'], wr=round(st['wr'], 2),
                                     u=round(u_wr, 2), lift=round(lift, 2),
                                     exp=round(st['exp'], 2), n_req=round(float(n_req), 0)
                                     if np.isfinite(n_req) else None, feas=bool(feas)))
                    if feas and (best[side] is None or score > best[side][0]):
                        best[side] = (score, p, kd, k_sl, rr, st['n'], lift)
    out['train_scan_top'] = sorted(
        scan, key=lambda r: -(r['lift'] * np.sqrt(r['n'])
                              if r['lift'] > 0 else -1e9))[:12]
    for side in ('long', 'short'):
        print(f"    TRAIN winner {side}: {best[side]}", flush=True)
    out['winner'] = {s: (None if best[s] is None else dict(
        zip(('score', 'p', 'K', 'k_sl', 'rr', 'n_train', 'lift_train'),
            [round(float(x), 3) for x in best[s]]))) for s in ('long', 'short')}

    if best['long'] is None and best['short'] is None:
        out['verdict'] = 'REJECT (no feasible cell on TRAIN — glass ceiling)'
        _save(tf, out, do_git); return out

    # ── ۴) اجرای کامل + نال شرطی + حکم ──
    frames, geo_by_side, pop_by_side = [], {}, {}
    n_by_side = {'long': 0, 'short': 0}
    for side, flag in (('long', True), ('short', False)):
        if best[side] is None:
            geo_by_side[side] = (P_GRID[0], 1.0, RR_GRID[0])
            pop_by_side[side] = valid_all
            continue
        _, p, kd, k_sl, rr, _, _ = best[side]
        geo_by_side[side] = (p, k_sl, rr)
        lo, so = gates[kd]
        pop_by_side[side] = valid_all[(lo if side == 'long' else so)[valid_all]]
        sig = sig_map[(p, kd)][side]
        sl = k_sl * atr_by_p[p][sig]
        okm = np.isfinite(sl) & (sl > 0)
        st = queue_rr(df, sig[okm], np.full(okm.sum(), flag), sl[okm],
                      ASSET, hold, rr)
        if st:
            frames.append(trades_df(st))
            n_by_side[side] = st['n']

    if not frames:
        out['verdict'] = 'REJECT (no trades on full run)'
        _save(tf, out, do_git); return out

    trades = pd.concat(frames, ignore_index=True)
    sl_med = float(trades['sl_pip'].median())
    tp_med = float(trades['tp_pip'].median())
    print(f"    full-run trades={len(trades)} (L={n_by_side['long']} "
          f"S={n_by_side['short']}) sl_med={sl_med:.1f} tp_med={tp_med:.1f}",
          flush=True)

    null = build_null(df, pop_by_side, atr_by_p, geo_by_side, n_by_side, hold, rng)

    r = rqs2.compute_rqs2(trades, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=d['time'], null=null, n_trials=N_TRIALS,
                          split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S695 {tf} ', r), flush=True)

    out.update(verdict=r['verdict'], rqs2_score=r['rqs2_score'],
               gates={k2: (None if v is None else bool(v))
                      for k2, v in r['gates'].items()},
               metrics={k2: (float(v) if isinstance(v, (int, float, np.floating))
                             and np.isfinite(float(v)) else str(v))
                        for k2, v in r['metrics'].items()},
               notes=r['notes'], null=null,
               n_trades=int(len(trades)), sl_med=sl_med, tp_med=tp_med,
               elapsed_s=round(_time.time() - t0, 1))
    _save(tf, out, do_git)
    return out


def _save(tf, out, do_git):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f'XAUUSD_{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"    saved → {path}", flush=True)
    if do_git:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            subprocess.run(['git', 'add', 'results/s695_runs'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-m',
                            f"S695 incremental: XAUUSD-{tf} → {out.get('verdict','?')}"],
                           cwd=root, capture_output=True)
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=root,
                           capture_output=True, timeout=90)
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=root,
                           capture_output=True, timeout=90)
            print(f"    git ✓ pushed XAUUSD-{tf}", flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f"    git ✗ {e} (ادامه — قانون افزایشی)", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', nargs='*', default=TF_ORDER)
    ap.add_argument('--no-git', action='store_true')
    a = ap.parse_args()
    for tf in a.tfs:
        jp = os.path.join(OUT_DIR, f'XAUUSD_{tf}.json')
        if os.path.exists(jp):
            print(f"skip {tf} (result exists)", flush=True)
            continue
        try:
            run_tf(tf, do_git=not a.no_git)
        except Exception as e:                                   # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f"!! {tf} failed: {e} — ادامه به TF بعدی", flush=True)
        gc.collect()
    print("\n=== S695 sweep complete ===", flush=True)
