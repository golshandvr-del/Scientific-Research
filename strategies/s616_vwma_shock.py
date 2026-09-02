# -*- coding: utf-8 -*-
"""
S616 — VWMA−SMA accumulation shock (follow) — XAUUSD
====================================================
پیش‌ثبت: results/S616_PREREG_VWMA_ACCUMULATION_SHOCK.md (کامیت 83308f20)

سیگنال منجمد:
  spread = VWMA34 − SMA34 (روی close، حجم tick MT5)
  z = zscore علّی 233 کندلی spread
  رویداد: عبور |z| از 2.618 (لحظهٔ ورود به شوک)؛ جهت = sign(spread)
  ورود open[t+1]؛ خروج V-TIME متقارن SL=TP=k×ATR34، تقدم SL، hold=21.

explore: گرید ۶ نقطه {H4,H8,D1}×{1.272,2.058} فقط نیمهٔ اول رویدادها.
  واجد: n>=60 ∧ net>0 ∧ lift >= 3.77×perm_sd (نول سکه K=500).
verdict: کل داده روی برنده + compute_rqs2 (n_trials=300، K=1000).
seed=20260829.
"""
import os, sys, json, time
import numpy as np

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from engine.rqs2 import compute_rqs2

SEED = 20260829
N_TRIALS = 300
Z_LUCK = 3.77
Z_EVENT = 2.618
W_MA = 34
W_Z = 233
PIP = 0.10
SPREAD_COST = 3.3
HOLD = 21
GRID_TF = ['H4', 'H8', 'D1']
GRID_K = [1.272, 2.058]
OUT_DIR = os.path.join(ROOT, 'results', '_s616_vwma')
os.makedirs(OUT_DIR, exist_ok=True)


def load_tf(tf):
    from tools import s434_fast_data as fd
    return fd.load_fast('XAUUSD', tf)


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


def rolling_sum(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(len(x), np.nan)
    out[w - 1:] = cs[w:] - cs[:-w]
    return out


def build_signal(d):
    c = d['close'].astype(float)
    v = d['volume'].astype(float)
    sv = rolling_sum(v, W_MA)
    svc = rolling_sum(v * c, W_MA)
    sc = rolling_sum(c, W_MA)
    with np.errstate(invalid='ignore', divide='ignore'):
        vwma = svc / sv
    sma = sc / W_MA
    spread = vwma - sma
    # z علّی 233
    s1 = rolling_sum(np.nan_to_num(spread), W_Z)
    s2 = rolling_sum(np.nan_to_num(spread) ** 2, W_Z)
    mean = s1 / W_Z
    var = s2 / W_Z - mean ** 2
    sd = np.sqrt(np.maximum(var, 1e-18))
    z = (spread - mean) / sd
    # جایی که spread هنوز nan است z را nan کن
    z[np.isnan(spread)] = np.nan
    z[:W_MA + W_Z] = np.nan
    return spread, z


def build_events(d):
    h, l, c = d['high'], d['low'], d['close']
    spread, z = build_signal(d)
    atr = wilder_atr34(h, l, c)
    n = len(c)
    az = np.abs(z)
    ev = []
    for t in range(1, n - 1):
        if np.isnan(az[t]) or np.isnan(az[t - 1]) or np.isnan(atr[t]) or atr[t] <= 0:
            continue
        if az[t - 1] < Z_EVENT and az[t] >= Z_EVENT:
            direction = 1 if spread[t] > 0 else -1
            ev.append((t, direction))
    return ev, atr


def outcome(d, atr, sig, direction, k):
    o, h, l, c = d['open'], d['high'], d['low'], d['close']
    n = len(c)
    e = sig + 1
    if e >= n:
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
    for (sig, direction) in events:
        oL = outcome(d, atr, sig, +1, k)
        oS = outcome(d, atr, sig, -1, k)
        if oL is None or oS is None:
            continue
        osig = oL if direction > 0 else oS
        rows.append((sig, direction, osig[0], osig[1],
                     oL[0], oL[1], oS[0], oS[1], int(t_arr[sig])))
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
    return dict(uncond_wr=float(uncond),
                perm_mean=float(wrs.mean()), perm_sd=float(wrs.std(ddof=1)),
                perm_max=float(wrs.max()), perm_k=K)


def stats(rows):
    if not rows:
        return dict(n=0)
    w = np.array([r[2] for r in rows]); p = np.array([r[3] for r in rows])
    nL = sum(1 for r in rows if r[1] > 0)
    return dict(n=len(rows), n_long=nL, n_short=len(rows) - nL,
                wr=100.0 * w.mean(), net=float(p.sum()))


def phase_explore():
    t0 = time.time()
    grid = []
    cache = {}
    for tf in GRID_TF:
        d = load_tf(tf)
        events, atr = build_events(d)
        cache[tf] = (d, events, atr)
        print(f"[{tf}] bars={d['n_bars']} events={len(events)}", flush=True)
    for tf in GRID_TF:
        d, events, atr = cache[tf]
        half_ev = events[:len(events) // 2]
        for k in GRID_K:
            rows = eval_card(d, atr, half_ev, k)
            st = stats(rows)
            if st['n'] == 0:
                grid.append(dict(tf=tf, k=k, n=0)); continue
            nl = coin_null(rows, 500, SEED + hash((tf, k)) % 10000)
            ref = max(nl['uncond_wr'], nl['perm_mean'])
            lift = st['wr'] - ref
            zv = lift / nl['perm_sd'] if nl['perm_sd'] > 0 else 0.0
            rec = dict(tf=tf, k=k, **st, **nl, ref=ref,
                       lift=round(lift, 2), z=round(zv, 2),
                       eligible=bool(st['n'] >= 60 and st['net'] > 0
                                     and lift >= Z_LUCK * nl['perm_sd']))
            grid.append(rec)
            print(f"  {tf} k={k}: n={st['n']} (L{st['n_long']}/S{st['n_short']}) "
                  f"WR={st['wr']:.2f} net={st['net']:.0f} ref={ref:.2f} "
                  f"lift={lift:+.2f} z={zv:.2f} elig={rec['eligible']}", flush=True)
    with open(os.path.join(OUT_DIR, 'grid_first_half.json'), 'w') as f:
        json.dump(grid, f, indent=1, ensure_ascii=False)
    elig = [g for g in grid if g.get('eligible')]
    if not elig:
        dec = dict(decision='death', reason='no_eligible_point',
                   rule='n>=60 AND net>0 AND lift>=3.77*perm_sd',
                   verdict='REJECT', score=0, holdout='VIRGIN',
                   elapsed_s=round(time.time() - t0, 1))
        print("⛔ مرگ شرافتمندانه: هیچ نقطه‌ای واجد نشد — هولد‌اوت بکر می‌ماند.", flush=True)
    else:
        best = max(elig, key=lambda g: g['z'])
        dec = dict(decision='proceed', winner=dict(tf=best['tf'], k=best['k']),
                   best=best, elapsed_s=round(time.time() - t0, 1))
        print(f"✅ برنده: {best['tf']} k={best['k']} z={best['z']} → فاز verdict", flush=True)
    with open(os.path.join(OUT_DIR, 'decision.json'), 'w') as f:
        json.dump(dec, f, indent=1, ensure_ascii=False)


def phase_verdict():
    with open(os.path.join(OUT_DIR, 'decision.json')) as f:
        dec = json.load(f)
    assert dec['decision'] == 'proceed', 'no winner — verdict phase illegal'
    tf, k = dec['winner']['tf'], dec['winner']['k']
    d = load_tf(tf)
    events, atr = build_events(d)
    rows = eval_card(d, atr, events, k)
    st = stats(rows)
    nl = coin_null(rows, 1000, SEED)
    null = {'long': nl, 'short': nl}
    wins = [r[2] for r in rows]; pnls = [r[3] for r in rows]
    bar_time = [r[8] for r in rows]
    dirs = ['long' if r[1] > 0 else 'short' for r in rows]
    split_bar = int(len(rows) * 0.7)
    tp_pip = float(np.median([abs(r[3]) for r in rows if r[2] == 1])) if any(wins) else 50.0
    res = compute_rqs2(
        trades=dict(win=wins, pnl_pip=pnls, direction=dirs, bar_time=bar_time),
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
