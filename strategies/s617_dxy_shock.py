# -*- coding: utf-8 -*-
"""
S617 — DXY shock transmission to gold (cross-asset) — XAUUSD
============================================================
پیش‌ثبت: results/S617_PREREG_DXY_SHOCK_TRANSMISSION.md (کامیت e962f971)

سیگنال منجمد (روی DXY H1):
  r = ln(close/close[-1]); sigma = Wilder-EMA(|r|,34) علّی (تا بار قبل); zs = r/sigma[-1]
  رویداد: لبهٔ تازهٔ |zs| >= 2.618 ؛ جهت طلا = -sign(zs)
ورود: اولین بار طلا (TF کارت) با open_time >= close_time بار شوک DXY (پس از هم‌ترازی §۳).
خروج: V-TIME متقارن SL=TP=k×ATR34 طلا (تا بار قبل ورود)، تقدم SL، hold=21.

alignment: هم‌بستگی بازده H1 گلد/DXY در lag -4..+4 (کور به lift) قبل از هر شبیه‌سازی.
explore: گرید ۴ نقطه {H1,H4}×{1.272,2.058} فقط نیمهٔ اول رویدادها.
  واجد: n>=100 ∧ net>0 ∧ lift >= 3.72×perm_sd (نول سکه K=500).
verdict: کل داده روی برنده + compute_rqs2 (n_trials=300، K=1000).
seed=20260904.
"""
import os, sys, json, time
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from engine.rqs2 import compute_rqs2

SEED = 20260904
N_TRIALS = 300
Z_LUCK = 3.72
Z_EVENT = 2.618
W_SIG = 34
PIP = 0.10
SPREAD_COST = 3.3
HOLD = 21
MIN_N = 100
RHO_MIN = 0.2
GRID_TF = ['H1', 'H4']
GRID_K = [1.272, 2.058]
OUT_DIR = os.path.join(ROOT, 'results', '_s617_dxy')
os.makedirs(OUT_DIR, exist_ok=True)


def load_gold(tf):
    from tools import s434_fast_data as fd
    return fd.load_fast('XAUUSD', tf)


def load_dxy_h1():
    x = pd.read_csv(os.path.join(ROOT, 'data', 'DXY_H1.csv'))
    x = x.sort_values('time').drop_duplicates('time')
    return dict(time=x['time'].values.astype(np.int64),
                open=x['open'].values.astype(float), high=x['high'].values.astype(float),
                low=x['low'].values.astype(float), close=x['close'].values.astype(float))


def wilder_atr34(h, l, c):
    n = len(c)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                np.abs(h[1:] - c[:-1]),
                                np.abs(l[1:] - c[:-1])])
    atr = np.full(n, np.nan)
    p = 34
    if n <= p:
        return atr
    atr[p] = tr[1:p + 1].mean()
    a = atr[p]
    for i in range(p + 1, n):
        a = (a * (p - 1) + tr[i]) / p
        atr[i] = a
    return atr


def wilder_ema(x, p):
    n = len(x)
    out = np.full(n, np.nan)
    if n <= p:
        return out
    out[p] = np.nanmean(x[1:p + 1])
    a = out[p]
    for i in range(p + 1, n):
        a = (a * (p - 1) + x[i]) / p
        out[i] = a
    return out


# ---------- §3 alignment diagnostic (blind to lift) ----------
def alignment(dxy, gold_h1):
    gt = gold_h1['time']; gc = gold_h1['close']
    gr = pd.Series(np.diff(np.log(gc)), index=gt[1:])
    dr = pd.Series(np.diff(np.log(dxy['close'])), index=dxy['time'][1:])
    res = {}
    for lag in range(-4, 5):
        # shift DXY timestamps by lag hours: dxy_shifted_time = time + lag*3600
        ds = pd.Series(dr.values, index=dr.index + lag * 3600)
        j = pd.concat([gr.rename('g'), ds.rename('d')], axis=1, join='inner').dropna()
        res[lag] = dict(rho=float(j['g'].corr(j['d'])), n=int(len(j)))
    best_lag = min(res, key=lambda L: res[L]['rho'])  # most negative
    out = dict(per_lag=res, best_lag=int(best_lag), rho_peak=res[best_lag]['rho'],
               valid=bool(abs(res[best_lag]['rho']) >= RHO_MIN))
    with open(os.path.join(OUT_DIR, 'alignment.json'), 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"[align] per-lag rho: " + ", ".join(f"{L:+d}:{res[L]['rho']:+.3f}" for L in range(-4, 5)), flush=True)
    print(f"[align] best_lag={best_lag}h rho={res[best_lag]['rho']:+.3f} valid={out['valid']}", flush=True)
    return out


# ---------- events on DXY ----------
def build_dxy_events(dxy, lag_hours):
    c = dxy['close']; t = dxy['time'] + lag_hours * 3600
    n = len(c)
    r = np.full(n, np.nan); r[1:] = np.diff(np.log(c))
    sig = wilder_ema(np.abs(np.nan_to_num(r)), W_SIG)
    ev = []
    prev_ok = False
    for i in range(1, n):
        s_prev = sig[i - 1]
        if np.isnan(s_prev) or s_prev <= 0 or np.isnan(r[i]):
            prev_ok = False
            continue
        zs = r[i] / s_prev
        hit = abs(zs) >= Z_EVENT
        if hit and not prev_ok:
            ev.append((int(t[i] + 3600), -1 if zs > 0 else 1, float(zs)))  # close time of shock bar, gold dir
        prev_ok = hit
    return ev


def map_to_gold(events, d):
    """first gold bar with open_time >= shock close_time → signal index sig such that entry = open[sig+1]?
    Convention here: we enter at open of that first bar directly; keep 'sig' = that bar - 1 for ATR causality."""
    gt = d['time']
    out = []
    for (ct, direction, zs) in events:
        j = int(np.searchsorted(gt, ct, side='left'))
        if j - 1 < 1 or j >= len(gt):
            continue
        out.append((j - 1, direction, zs))  # entry at open[j] = open[sig+1]
    return out


def outcome(d, atr, sig, direction, k):
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    n = len(c)
    e = sig + 1
    if e >= n or np.isnan(atr[sig]) or atr[sig] <= 0:
        return None
    entry = o[e]
    dist = k * atr[sig]
    if direction > 0:
        sl, tp = entry - dist, entry + dist
    else:
        sl, tp = entry + dist, entry - dist
    last = min(e + HOLD, n - 1)
    for b in range(e, last + 1):
        if direction > 0:
            if l[b] <= sl:
                return (0, (sl - entry) / PIP - SPREAD_COST)
            if h[b] >= tp:
                return (1, (tp - entry) / PIP - SPREAD_COST)
        else:
            if h[b] >= sl:
                return (0, (entry - sl) / PIP - SPREAD_COST)
            if l[b] <= tp:
                return (1, (entry - tp) / PIP - SPREAD_COST)
    px = c[last]
    pnl = ((px - entry) if direction > 0 else (entry - px)) / PIP - SPREAD_COST
    return (1 if pnl > 0 else 0, pnl)


def eval_card(d, atr, events, k):
    rows = []
    t_arr = d['time']
    last_sig = -10**9
    for (sig, direction, zs) in events:
        if sig <= last_sig:  # no duplicate entries on same gold bar
            continue
        oL = outcome(d, atr, sig, +1, k)
        oS = outcome(d, atr, sig, -1, k)
        if oL is None or oS is None:
            continue
        osig = oL if direction > 0 else oS
        rows.append((sig, direction, osig[0], osig[1], oL[0], oL[1], oS[0], oS[1], int(t_arr[sig])))
        last_sig = sig
    return rows


def coin_null(rows, K, seed):
    m = len(rows)
    wl = np.array([r[4] for r in rows], dtype=float)
    ws = np.array([r[6] for r in rows], dtype=float)
    rng = np.random.default_rng(seed)
    wrs = np.empty(K)
    for kk in range(K):
        pick = rng.integers(0, 2, m)
        w = np.where(pick == 1, wl, ws)
        wrs[kk] = 100.0 * w.mean()
    uncond = 100.0 * np.concatenate([wl, ws]).mean()
    return dict(uncond_wr=float(uncond), perm_mean=float(wrs.mean()),
                perm_sd=float(wrs.std(ddof=1)), perm_max=float(wrs.max()), perm_k=K)


def stats(rows):
    if not rows:
        return dict(n=0)
    w = np.array([r[2] for r in rows]); p = np.array([r[3] for r in rows])
    nL = sum(1 for r in rows if r[1] > 0)
    # mirror arm (P2 record only): aligned-with-DXY direction
    wm = np.array([r[6] if r[1] > 0 else r[4] for r in rows])
    return dict(n=len(rows), n_long=nL, n_short=len(rows) - nL,
                wr=100.0 * w.mean(), net=float(p.sum()), mirror_wr=100.0 * wm.mean())


def phase_explore():
    t0 = time.time()
    dxy = load_dxy_h1()
    g1 = load_gold('H1')
    al = alignment(dxy, g1)
    if not al['valid']:
        dec = dict(decision='incomplete', reason='alignment_rho_below_0.2', verdict='INCOMPLETE',
                   score=0, alignment=al, elapsed_s=round(time.time() - t0, 1))
        with open(os.path.join(OUT_DIR, 'decision.json'), 'w') as f:
            json.dump(dec, f, indent=1, ensure_ascii=False)
        print("⛔ داده‌ها ناسازگارند — INCOMPLETE 0", flush=True)
        return
    events = build_dxy_events(dxy, al['best_lag'])
    print(f"[DXY] bars={len(dxy['close'])} shock events={len(events)} "
          f"(gold-long={sum(1 for e in events if e[1] > 0)}, gold-short={sum(1 for e in events if e[1] < 0)})", flush=True)
    grid = []
    for tf in GRID_TF:
        d = g1 if tf == 'H1' else load_gold(tf)
        atr = wilder_atr34(d['high'], d['low'], d['close'])
        gev = map_to_gold(events, d)
        half = gev[:len(gev) // 2]
        for k in GRID_K:
            rows = eval_card(d, atr, half, k)
            st = stats(rows)
            if st['n'] == 0:
                grid.append(dict(tf=tf, k=k, n=0)); continue
            nl = coin_null(rows, 500, SEED + hash((tf, k)) % 10000)
            ref = max(nl['uncond_wr'], nl['perm_mean'])
            lift = st['wr'] - ref
            zv = lift / nl['perm_sd'] if nl['perm_sd'] > 0 else 0.0
            rec = dict(tf=tf, k=k, **st, **nl, ref=ref, lift=round(lift, 2), z=round(zv, 2),
                       eligible=bool(st['n'] >= MIN_N and st['net'] > 0 and lift >= Z_LUCK * nl['perm_sd']))
            grid.append(rec)
            print(f"  {tf} k={k}: n={st['n']} (L{st['n_long']}/S{st['n_short']}) WR={st['wr']:.2f} "
                  f"mirrorWR={st['mirror_wr']:.2f} net={st['net']:.0f} ref={ref:.2f} "
                  f"lift={lift:+.2f} z={zv:.2f} elig={rec['eligible']}", flush=True)
    with open(os.path.join(OUT_DIR, 'grid_first_half.json'), 'w') as f:
        json.dump(grid, f, indent=1, ensure_ascii=False)
    elig = [g for g in grid if g.get('eligible')]
    if not elig:
        dec = dict(decision='death', reason='no_eligible_point',
                   rule=f'n>={MIN_N} AND net>0 AND lift>={Z_LUCK}*perm_sd',
                   verdict='REJECT', score=0, holdout='VIRGIN', alignment=al,
                   n_events_total=len(events), elapsed_s=round(time.time() - t0, 1))
        print("⛔ مرگ شرافتمندانه: هیچ نقطه‌ای واجد نشد — هولد‌اوت بکر می‌ماند.", flush=True)
    else:
        best = max(elig, key=lambda g: g['z'])
        dec = dict(decision='proceed', winner=dict(tf=best['tf'], k=best['k']), best=best,
                   alignment=al, elapsed_s=round(time.time() - t0, 1))
        print(f"✅ برنده: {best['tf']} k={best['k']} z={best['z']} → فاز verdict", flush=True)
    with open(os.path.join(OUT_DIR, 'decision.json'), 'w') as f:
        json.dump(dec, f, indent=1, ensure_ascii=False)


def phase_verdict():
    with open(os.path.join(OUT_DIR, 'decision.json')) as f:
        dec = json.load(f)
    assert dec['decision'] == 'proceed', 'no winner — verdict phase illegal'
    tf, k = dec['winner']['tf'], dec['winner']['k']
    dxy = load_dxy_h1()
    events = build_dxy_events(dxy, dec['alignment']['best_lag'])
    d = load_gold(tf)
    atr = wilder_atr34(d['high'], d['low'], d['close'])
    rows = eval_card(d, atr, map_to_gold(events, d), k)
    st = stats(rows)
    nl = coin_null(rows, 1000, SEED)
    null = {'long': nl, 'short': nl}
    wins = [r[2] for r in rows]; pnls = [r[3] for r in rows]
    bar_time = [r[8] for r in rows]
    dirs = ['long' if r[1] > 0 else 'short' for r in rows]
    split_bar = int(len(rows) * 0.5)
    tp_pip = float(np.median([abs(r[3]) for r in rows if r[2] == 1])) if any(wins) else 50.0
    res = compute_rqs2(trades=dict(win=wins, pnl_pip=pnls, direction=dirs, bar_time=bar_time),
                       tp_pip=tp_pip, null=null, n_trials=N_TRIALS,
                       split_bar=split_bar, bar_time=bar_time, close=d['close'].tolist())
    out = dict(tf=tf, k=k, **st, null=nl, rqs2=res)
    with open(os.path.join(OUT_DIR, 'verdict.json'), 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str), flush=True)


if __name__ == '__main__':
    phase = sys.argv[1] if len(sys.argv) > 1 else 'explore'
    if phase == 'explore':
        phase_explore()
    else:
        phase_verdict()
