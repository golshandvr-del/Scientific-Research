# -*- coding: utf-8 -*-
"""
S697 — Efficient-Run Continuation — XAUUSD {H1,H2,H3,H6,H8}
=============================================================
پیش‌ثبت: results/S697_PREREG_EFFICIENT_RUN_CONTINUATION.md (کامیت 778af464 — قبل از این فایل)

رویداد (بستهٔ کندل t): net = |c[t]−c[t−N]| · path = Σ_{j=t−N+1..t}|c[j]−c[j−1]|
  ER = net/path ≥ e  ∧  net ≥ k·ATR34[t]  (لبه: یک سیگنال per ورود به حالت)
  جهت = sign(c[t]−c[t−N]) · follow · ورود open t+1 (queue_rr)
خانواده: N{8,13} × e{0.786,0.854} × k{2.618,3.618} × k_sl{1.272,2.058} × rr{1.0,1.618} = 32/side · n_trials=64
hold = 72h · نال بی‌قید K=500 با هندسهٔ برنده · stop-rule n_train<40/side.
"""
import sys, os, json, gc, subprocess, argparse, time as _time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from engine import rqs2                                     # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies.s351_lpsb import atr_series                 # noqa: E402
from strategies.s694_keltner_displacement import bars_per_hour  # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402

N_GRID     = (8, 13)
E_GRID     = (0.786, 0.854)
K_GRID     = (2.618, 3.618)
SL_K_GRID  = (1.272, 2.058)
RR_GRID    = (1.0, 1.618)
ATR_P      = 34
N_TRIALS   = 64
HOLD_HOURS = 72.0
SPLIT_FRAC = 0.60
N_PERM     = 500
N_UNCOND_CAP = 25000
SEED       = 697
MIN_TRAIN_SIDE = 40
ASSET      = 'XAUUSD'
TF_ORDER   = ['H1', 'H2', 'H3', 'H6', 'H8']
OUT_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'results', 's697_runs')
MIN_SPAN_YEARS = 15.0


def efficient_run_signals(close, atr, N, e, k, warmup):
    """لبهٔ ورود به حالت (ER≥e ∧ net≥k·ATR) per side. علّی: فقط c[t−N..t] و ATR[t]."""
    n = len(close)
    net_s = np.full(n, np.nan); path = np.full(n, np.nan)
    net_s[N:] = close[N:] - close[:-N]
    steps = np.abs(np.diff(close))                       # steps[j] = |c[j+1]−c[j]|
    cs = np.concatenate(([0.0], np.cumsum(steps)))       # cs[t] = Σ_{j<t}|Δ| تا c[t]
    path[N:] = cs[N:] - cs[:-N]                          # Σ_{j=t−N+1..t}|c[j]−c[j−1]|
    er = np.abs(net_s) / np.where(path > 0, path, np.nan)
    cond = (er >= e) & (np.abs(net_s) >= k * atr) & np.isfinite(er) & np.isfinite(atr)
    out = {}
    for side, sgn in (('long', 1), ('short', -1)):
        c2 = cond & (np.sign(net_s) == sgn)
        edge = np.zeros(n, dtype=bool)
        edge[1:] = c2[1:] & ~c2[:-1]
        edge[:warmup] = False
        out[side] = np.flatnonzero(edge)
    return out


def uncond_wr(df, pop, atr, k_sl, rr, hold, flag, rng):
    pick = pop if len(pop) <= N_UNCOND_CAP else \
        np.sort(rng.choice(pop, size=N_UNCOND_CAP, replace=False))
    sl = k_sl * atr[pick]
    ok = np.isfinite(sl) & (sl > 0)
    s = queue_rr(df, pick[ok], np.full(ok.sum(), flag), sl[ok], ASSET, hold, rr)
    return (float(s['wr']) if s else None, int(s['n']) if s else 0)


def build_null(df, pop, atr, geo_by_side, n_by_side, hold, rng):
    null = {}
    for side, flag in (('long', True), ('short', False)):
        dnull = dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)
        k_sl, rr = geo_by_side[side]
        n_side = n_by_side[side]
        if n_side >= 1 and len(pop) > n_side:
            dnull['uncond_wr'] = uncond_wr(df, pop, atr, k_sl, rr, hold, flag, rng)[0]
            slv = k_sl * atr[pop]
            ok = np.isfinite(slv) & (slv > 0)
            vi, slv = pop[ok], slv[ok]
            wrs = []
            for _ in range(N_PERM):
                pick = np.sort(rng.choice(len(vi), size=n_side, replace=False))
                s = queue_rr(df, vi[pick], np.full(n_side, flag), slv[pick], ASSET, hold, rr)
                if s:
                    wrs.append(s['wr'])
            if wrs:
                a = np.asarray(wrs)
                dnull.update(perm_mean=float(a.mean()), perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = dnull
        print(f"    null {side:<5} uncond={dnull['uncond_wr']} μ={dnull['perm_mean']} "
              f"σ={dnull['perm_sd']} K={dnull['perm_k']}", flush=True)
    return null


def run_tf(tf, do_git=True):
    t0 = _time.time()
    print(f"\n{'='*88}\n=== S697 Efficient-Run :: XAUUSD-{tf} ===", flush=True)
    d = fd.load_fast(ASSET, tf)
    span = float(d.get('span_years', 0) or 0)
    if span < MIN_SPAN_YEARS or 'mt5_full' not in str(d.get('src', '')):
        raise RuntimeError(f"E-16 trap: src={d.get('src')} span={span}y — اجرا متوقف")
    for _k in ('volume', 'hour', 'minute', 'dow'):
        d.pop(_k, None)
    df = pd.DataFrame({'time': d['time'], 'open': d['open'], 'high': d['high'],
                       'low': d['low'], 'close': d['close']}, copy=False)
    n = len(df)
    close = d['close'].astype(np.float64)
    print(f"    bars={n:,}  src={d['src']}  span={span}y", flush=True)

    bph = bars_per_hour(d['time'])
    hold = max(1, int(round(HOLD_HOURS * bph)))
    atr = atr_series(df, p=ATR_P)
    warmup = max(4 * ATR_P, max(N_GRID) + 2, 60)
    split = int(n * SPLIT_FRAC)
    c = cost_pip(ASSET)
    print(f"    hold={hold} bars (72h) · warmup={warmup} · split_bar={split} · cost={c:.2f}pip", flush=True)

    out = dict(strategy='S697', concept='efficient_run_continuation', asset=ASSET, tf=tf,
               bars=n, src=d['src'], span_years=span, hold_bars=hold, split_bar=split,
               n_trials=N_TRIALS, family='2x2x2x2x2=32/side (64)', cost_pip=c)
    rng = np.random.default_rng(SEED)

    sig_map = {}
    for N in N_GRID:
        for e in E_GRID:
            for k in K_GRID:
                sm = efficient_run_signals(close, atr, N, e, k, warmup)
                sig_map[(N, e, k)] = sm
                print(f"    N={N} e={e} k={k}: L={len(sm['long'])} S={len(sm['short'])}", flush=True)

    valid_all = np.arange(warmup, n - hold - 2)
    a = atr[valid_all]; valid_all = valid_all[np.isfinite(a) & (a > 0)]
    valid_tr = valid_all[valid_all < split]
    u_cache = {}

    def u_train(side, k_sl, rr):
        key = (side, k_sl, rr)
        if key not in u_cache:
            u_cache[key] = uncond_wr(df, valid_tr, atr, k_sl, rr, hold, side == 'long', rng)[0]
        return u_cache[key]

    best = {'long': None, 'short': None}
    scan, stop = [], {}
    for (N, e, k), sm in sig_map.items():
        for side, flag in (('long', True), ('short', False)):
            sig = sm[side]
            sig_tr = sig[sig < split - hold]
            if len(sig_tr) < MIN_TRAIN_SIDE:
                stop[f"N{N}_e{e}_k{k}_{side}"] = int(len(sig_tr)); continue
            for k_sl in SL_K_GRID:
                sl = k_sl * atr[sig_tr]
                okm = np.isfinite(sl) & (sl > 0)
                for rr in RR_GRID:
                    st = queue_rr(df, sig_tr[okm], np.full(okm.sum(), flag), sl[okm], ASSET, hold, rr)
                    if not st:
                        continue
                    u_wr = u_train(side, k_sl, rr)
                    if u_wr is None:
                        continue
                    lift = st['wr'] - u_wr
                    n_req = rqs2.n_required_for_h3(lift, u_wr / 100.0) if lift > 0 else float('inf')
                    score = lift * np.sqrt(st['n']) if lift > 0 else -1e9
                    feas = st['n'] >= n_req
                    scan.append(dict(N=N, e=e, k=k, k_sl=k_sl, rr=rr, side=side, n=st['n'],
                                     wr=round(st['wr'], 2), u=round(u_wr, 2), lift=round(lift, 2),
                                     exp=round(st['exp'], 2),
                                     n_req=(round(float(n_req)) if np.isfinite(n_req) else None),
                                     feas=bool(feas)))
                    if feas and (best[side] is None or score > best[side][0]):
                        best[side] = (score, N, e, k, k_sl, rr, st['n'], lift)
    out['stop_rule_hits'] = stop
    out['train_scan_top'] = sorted(scan, key=lambda r: -(r['lift'] * np.sqrt(r['n'])
                                                        if r['lift'] > 0 else -1e9))[:16]
    # ثبت یکنوایی در e برای P1 (فقط TRAIN؛ گزارشی)
    out['p1_monotonic_e'] = {}
    for side in ('long', 'short'):
        for N in N_GRID:
            for k in K_GRID:
                cells = {e: [r for r in scan if r['side'] == side and r['N'] == N and r['k'] == k
                             and r['e'] == e and r['k_sl'] == SL_K_GRID[0] and r['rr'] == RR_GRID[0]]
                         for e in E_GRID}
                out['p1_monotonic_e'][f"{side}_N{N}_k{k}"] = {
                    str(e): (cells[e][0]['lift'] if cells[e] else None) for e in E_GRID}
    for side in ('long', 'short'):
        print(f"    TRAIN winner {side}: {best[side]}", flush=True)
    out['winner'] = {s: (None if best[s] is None else dict(
        zip(('score', 'N', 'e', 'k', 'k_sl', 'rr', 'n_train', 'lift_train'),
            [round(float(x), 3) for x in best[s]]))) for s in ('long', 'short')}

    if best['long'] is None and best['short'] is None:
        out['verdict'] = 'REJECT (no feasible cell on TRAIN — glass ceiling)'
        _save(tf, out, do_git); return out

    frames, geo_by_side, n_by_side = [], {}, {'long': 0, 'short': 0}
    for side, flag in (('long', True), ('short', False)):
        if best[side] is None:
            geo_by_side[side] = (SL_K_GRID[0], RR_GRID[0]); continue
        _, N, e, k, k_sl, rr, _, _ = best[side]
        geo_by_side[side] = (k_sl, rr)
        sig = sig_map[(N, e, k)][side]
        sl = k_sl * atr[sig]
        okm = np.isfinite(sl) & (sl > 0)
        st = queue_rr(df, sig[okm], np.full(okm.sum(), flag), sl[okm], ASSET, hold, rr)
        if st:
            frames.append(trades_df(st)); n_by_side[side] = st['n']
    if not frames:
        out['verdict'] = 'REJECT (no trades on full run)'
        _save(tf, out, do_git); return out

    trades = pd.concat(frames, ignore_index=True)
    sl_med = float(trades['sl_pip'].median()); tp_med = float(trades['tp_pip'].median())
    print(f"    full-run trades={len(trades)} (L={n_by_side['long']} S={n_by_side['short']}) "
          f"sl_med={sl_med:.1f} tp_med={tp_med:.1f}", flush=True)

    null = build_null(df, valid_all, atr, geo_by_side, n_by_side, hold, rng)
    r = rqs2.compute_rqs2(trades, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=d['time'],
                          null=null, n_trials=N_TRIALS, split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S697 {tf} ', r), flush=True)
    out.update(verdict=r['verdict'], rqs2_score=r['rqs2_score'],
               gates={k2: (None if v is None else bool(v)) for k2, v in r['gates'].items()},
               metrics={k2: (float(v) if isinstance(v, (int, float, np.floating))
                             and np.isfinite(float(v)) else str(v)) for k2, v in r['metrics'].items()},
               notes=r['notes'], null=null, n_trades=int(len(trades)),
               sl_med=sl_med, tp_med=tp_med, elapsed_s=round(_time.time() - t0, 1))
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
            subprocess.run(['git', 'add', 'results/s697_runs'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-m', f"S697 incremental: XAUUSD-{tf} → {out.get('verdict','?')}"],
                           cwd=root, capture_output=True)
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=root, capture_output=True, timeout=90)
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=root, capture_output=True, timeout=90)
            print(f"    git ✓ pushed XAUUSD-{tf}", flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f"    git ✗ {e}", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', nargs='*', default=TF_ORDER)
    ap.add_argument('--no-git', action='store_true')
    a = ap.parse_args()
    for tf in a.tfs:
        if os.path.exists(os.path.join(OUT_DIR, f'XAUUSD_{tf}.json')):
            print(f"skip {tf}", flush=True); continue
        try:
            run_tf(tf, do_git=not a.no_git)
        except Exception as e:                                   # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f"!! {tf} failed: {e}", flush=True)
        gc.collect()
    print("\n=== S697 sweep complete ===", flush=True)
