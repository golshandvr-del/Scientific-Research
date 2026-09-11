# -*- coding: utf-8 -*-
"""
S696 — Weekly Informed-Bar Cascade — XAUUSD، ورود در {H4,H8,H12,D1}
====================================================================
پیش‌ثبت: results/S696_PREREG_WEEKLY_INFORMED_CASCADE.md (کامیت 058fb9eb — قبل از این فایل)

رویداد (W1، ساخته‌شده از خودِ کندل‌های کارت با مرز دوشنبه 00:00 UTC — تا هم‌ترازی زمانی
با کارت دقیق باشد و از ناهمخوانی فایل W1 بروکر مصون بمانیم):
  ρ_w = |C−O|/(H−L) ≥ 0.618 · (H−L)_w ≥ k_r × ATR_W(13)[w−1] (وایلدر هفتگی، علّی)
  جهت = sign(C−O). سیگنال = آخرین کندل کارت در هفتهٔ w ⇒ queue_rr در open کندل بعد
  (= اولین کندل هفتهٔ w+1) وارد می‌شود. یک معامله per هفتهٔ مطلع.
هندسه: SL = k_sl × ATR_card(34)[sig] · TP = max(rr·SL, SL) · hold ∈ {72h,120h} زمانی.
خانواده: k_r{1.0,1.272} × k_sl{1.618,2.618} × rr{1.0,1.618} × hold{72,120} = 16/side · n_trials=32
نال: جامعه = آخرین کندلِ هر هفته (همان اسلات) — K=500 زیرنمونه با هندسهٔ برنده.
stop-rule: n_train < 40 per side ⇒ آن سمت حذف.
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

KR_GRID    = (1.0, 1.272)
SL_K_GRID  = (1.618, 2.618)
RR_GRID    = (1.0, 1.618)
HOLD_GRID  = (72.0, 120.0)
RHO_MIN    = 0.618
ATR_W_P    = 13
ATR_CARD_P = 34
N_TRIALS   = 32
SPLIT_FRAC = 0.60
N_PERM     = 500
SEED       = 696
MIN_TRAIN_SIDE = 40
ASSET      = 'XAUUSD'
WEEK_OFF   = 345600                     # مرز دوشنبه 00:00 UTC (ارثی S693)
TF_ORDER   = ['H4', 'H8', 'H12', 'D1']
OUT_DIR    = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'results', 's696_runs')
MIN_SPAN_YEARS = 15.0


def weekly_bars(d):
    """کندل‌های هفتگی از کندل‌های کارت. برمی‌گرداند dict آرایه‌های هفتگی + w_idx per bar + last_bar per week."""
    t = d['time'].astype(np.int64)
    n = len(t)
    week = (t - WEEK_OFF) // 604800
    starts = np.concatenate(([0], np.flatnonzero(np.diff(week)) + 1))
    ends = np.concatenate((starts[1:] - 1, [n - 1]))
    o = d['open'][starts].astype(np.float64)
    c = d['close'][ends].astype(np.float64)
    h = np.maximum.reduceat(d['high'].astype(np.float64), starts)
    l = np.minimum.reduceat(d['low'].astype(np.float64), starts)
    w_idx = np.searchsorted(starts, np.arange(n), side='right') - 1
    return dict(o=o, h=h, l=l, c=c, starts=starts, ends=ends, w_idx=w_idx,
                n_weeks=len(starts))


def wilder_atr(h, l, c, p):
    """ATR وایلدر روی سری‌های هفتگی؛ خروجی[w] فقط از هفته‌های ≤ w استفاده می‌کند."""
    n = len(c)
    tr = np.empty(n); tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]),
                                np.abs(l[1:] - c[:-1])])
    atr = np.full(n, np.nan)
    if n > p:
        atr[p - 1] = tr[:p].mean()
        for i in range(p, n):
            atr[i] = (atr[i - 1] * (p - 1) + tr[i]) / p
    return atr


def informed_weeks(W, k_r):
    """هفته‌های مطلع per side. برمی‌گرداند dict side → آرایهٔ اندیس هفته."""
    rng_w = W['h'] - W['l']
    body = W['c'] - W['o']
    rho = np.abs(body) / np.where(rng_w > 0, rng_w, np.nan)
    atr_w = wilder_atr(W['h'], W['l'], W['c'], ATR_W_P)
    atr_prev = np.full(len(rho), np.nan); atr_prev[1:] = atr_w[:-1]        # علّی
    ok = (rho >= RHO_MIN) & (rng_w >= k_r * atr_prev) & np.isfinite(atr_prev)
    # هفتهٔ آخر داده ناقص است و هفتهٔ بعدی ندارد ⇒ حذف
    ok[-1] = False
    return {'long': np.flatnonzero(ok & (body > 0)),
            'short': np.flatnonzero(ok & (body < 0))}


def uncond_wr(df, pop, atr, k_sl, rr, hold, flag, rng):
    sl = k_sl * atr[pop]
    ok = np.isfinite(sl) & (sl > 0)
    s = queue_rr(df, pop[ok], np.full(ok.sum(), flag), sl[ok], ASSET, hold, rr)
    return (float(s['wr']) if s else None, int(s['n']) if s else 0)


def build_null(df, pop, atr, geo_by_side, n_by_side, rng):
    null = {}
    for side, flag in (('long', True), ('short', False)):
        dnull = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                     perm_max=None, perm_k=None)
        k_sl, rr, hold = geo_by_side[side]
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
        print(f"    null {side:<5} (slot pop={len(pop)}) uncond={dnull['uncond_wr']} "
              f"μ={dnull['perm_mean']} σ={dnull['perm_sd']} K={dnull['perm_k']}",
              flush=True)
    return null


def run_tf(tf, do_git=True):
    t0 = _time.time()
    print(f"\n{'='*88}\n=== S696 Weekly-Informed Cascade :: XAUUSD-{tf} ===", flush=True)
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
    holds = {hh: max(1, int(round(hh * bph))) for hh in HOLD_GRID}
    atr = atr_series(df, p=ATR_CARD_P)
    split = int(n * SPLIT_FRAC)
    c = cost_pip(ASSET)
    W = weekly_bars(d)
    warmup_week = ATR_W_P + 2
    print(f"    weeks={W['n_weeks']} · holds={holds} bars · split_bar={split} · cost={c:.2f}pip",
          flush=True)

    out = dict(strategy='S696', concept='weekly_informed_cascade', asset=ASSET, tf=tf,
               bars=n, src=d['src'], span_years=span, n_weeks=int(W['n_weeks']),
               hold_bars=holds, split_bar=split, n_trials=N_TRIALS,
               family='2x2x2x2=16/side (32)', rho_min=RHO_MIN, cost_pip=c)

    rng = np.random.default_rng(SEED)

    # ── ۱) سیگنال‌ها: آخرین کندلِ کارت در هفتهٔ مطلع ──
    sig_map = {}
    for k_r in KR_GRID:
        iw = informed_weeks(W, k_r)
        sm = {}
        for side in ('long', 'short'):
            ws = iw[side]; ws = ws[ws >= warmup_week]
            sm[side] = W['ends'][ws]
        sig_map[k_r] = sm
        print(f"    k_r={k_r}: informed weeks L={len(sm['long'])} S={len(sm['short'])}", flush=True)

    # جامعهٔ نال = آخرین کندل هر هفته (اسلات یکسان)
    pop_all = W['ends'][warmup_week:-1]
    pop_all = pop_all[np.isfinite(atr[pop_all]) & (atr[pop_all] > 0)]
    max_hold = max(holds.values())
    pop_all = pop_all[pop_all < n - max_hold - 2]
    pop_tr = pop_all[pop_all < split]

    u_cache = {}

    def u_train(side, k_sl, rr, hold):
        key = (side, k_sl, rr, hold)
        if key not in u_cache:
            u_cache[key] = uncond_wr(df, pop_tr, atr, k_sl, rr, hold,
                                     side == 'long', rng)[0]
        return u_cache[key]

    # ── ۲) جست‌وجوی ۱۶ سلول per side — فقط TRAIN ──
    best = {'long': None, 'short': None}
    scan = []
    stop = {}
    for k_r, sm in sig_map.items():
        for side, flag in (('long', True), ('short', False)):
            sig = sm[side]
            sig_tr = sig[sig < split - max_hold]
            if len(sig_tr) < MIN_TRAIN_SIDE:
                stop[(k_r, side)] = int(len(sig_tr))
                continue
            for k_sl in SL_K_GRID:
                sl = k_sl * atr[sig_tr]
                okm = np.isfinite(sl) & (sl > 0)
                for rr in RR_GRID:
                    for hh, hold in holds.items():
                        st = queue_rr(df, sig_tr[okm], np.full(okm.sum(), flag),
                                      sl[okm], ASSET, hold, rr)
                        if not st:
                            continue
                        u_wr = u_train(side, k_sl, rr, hold)
                        if u_wr is None:
                            continue
                        lift = st['wr'] - u_wr
                        n_req = rqs2.n_required_for_h3(lift, u_wr / 100.0) \
                            if lift > 0 else float('inf')
                        score = lift * np.sqrt(st['n']) if lift > 0 else -1e9
                        feas = st['n'] >= n_req
                        scan.append(dict(k_r=k_r, k_sl=k_sl, rr=rr, hold_h=hh, side=side,
                                         n=st['n'], wr=round(st['wr'], 2),
                                         u=round(u_wr, 2), lift=round(lift, 2),
                                         exp=round(st['exp'], 2),
                                         n_req=(round(float(n_req)) if np.isfinite(n_req) else None),
                                         feas=bool(feas)))
                        if feas and (best[side] is None or score > best[side][0]):
                            best[side] = (score, k_r, k_sl, rr, hh, st['n'], lift)
    out['stop_rule_hits'] = {f"{k[0]}_{k[1]}": v for k, v in stop.items()}
    out['train_scan_top'] = sorted(
        scan, key=lambda r: -(r['lift'] * np.sqrt(r['n']) if r['lift'] > 0 else -1e9))[:12]
    for side in ('long', 'short'):
        print(f"    TRAIN winner {side}: {best[side]}", flush=True)
    out['winner'] = {s: (None if best[s] is None else dict(
        zip(('score', 'k_r', 'k_sl', 'rr', 'hold_h', 'n_train', 'lift_train'),
            [round(float(x), 3) for x in best[s]]))) for s in ('long', 'short')}

    if best['long'] is None and best['short'] is None:
        out['verdict'] = 'REJECT (no feasible cell on TRAIN — glass ceiling)'
        _save(tf, out, do_git); return out

    # ── ۳) اجرای کامل + نال اسلات + حکم ──
    frames, geo_by_side, n_by_side = [], {}, {'long': 0, 'short': 0}
    for side, flag in (('long', True), ('short', False)):
        if best[side] is None:
            geo_by_side[side] = (SL_K_GRID[0], RR_GRID[0], holds[HOLD_GRID[0]])
            continue
        _, k_r, k_sl, rr, hh, _, _ = best[side]
        hold = holds[hh]
        geo_by_side[side] = (k_sl, rr, hold)
        sig = sig_map[k_r][side]
        sl = k_sl * atr[sig]
        okm = np.isfinite(sl) & (sl > 0)
        st = queue_rr(df, sig[okm], np.full(okm.sum(), flag), sl[okm], ASSET, hold, rr)
        if st:
            frames.append(trades_df(st))
            n_by_side[side] = st['n']

    if not frames:
        out['verdict'] = 'REJECT (no trades on full run)'
        _save(tf, out, do_git); return out

    trades = pd.concat(frames, ignore_index=True)
    sl_med = float(trades['sl_pip'].median())
    tp_med = float(trades['tp_pip'].median())
    print(f"    full-run trades={len(trades)} (L={n_by_side['long']} S={n_by_side['short']}) "
          f"sl_med={sl_med:.1f} tp_med={tp_med:.1f}", flush=True)

    null = build_null(df, pop_all, atr, geo_by_side, n_by_side, rng)

    r = rqs2.compute_rqs2(trades, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=d['time'], null=null, n_trials=N_TRIALS,
                          split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S696 {tf} ', r), flush=True)

    out.update(verdict=r['verdict'], rqs2_score=r['rqs2_score'],
               gates={k2: (None if v is None else bool(v)) for k2, v in r['gates'].items()},
               metrics={k2: (float(v) if isinstance(v, (int, float, np.floating))
                             and np.isfinite(float(v)) else str(v))
                        for k2, v in r['metrics'].items()},
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
            subprocess.run(['git', 'add', 'results/s696_runs'], cwd=root, check=True)
            subprocess.run(['git', 'commit', '-m',
                            f"S696 incremental: XAUUSD-{tf} → {out.get('verdict','?')}"],
                           cwd=root, capture_output=True)
            subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=root,
                           capture_output=True, timeout=90)
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=root,
                           capture_output=True, timeout=90)
            print(f"    git ✓ pushed XAUUSD-{tf}", flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f"    git ✗ {e}", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', nargs='*', default=TF_ORDER)
    ap.add_argument('--no-git', action='store_true')
    a = ap.parse_args()
    for tf in a.tfs:
        jp = os.path.join(OUT_DIR, f'XAUUSD_{tf}.json')
        if os.path.exists(jp):
            print(f"skip {tf} (result exists)", flush=True); continue
        try:
            run_tf(tf, do_git=not a.no_git)
        except Exception as e:                                   # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f"!! {tf} failed: {e}", flush=True)
        gc.collect()
    print("\n=== S696 sweep complete ===", flush=True)
