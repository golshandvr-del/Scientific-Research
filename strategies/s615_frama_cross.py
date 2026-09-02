# -*- coding: utf-8 -*-
"""
S615 — FRAMA-cross continuation (Ehlers 2005, N=16) — XAUUSD
============================================================
پیش‌ثبت: results/S615_PREREG_FRAMA_CROSS_CONTINUATION.md (کامیت 243bef6c)

سیگنال منجمد: تغییر علامت (close − FRAMA16) در پایان کندل t ⇒ ورود open[t+1]
  غیرمثبت→مثبت = LONG · غیرمنفی→منفی = SHORT
خروج V-TIME متقارن: SL=TP=k×ATR34(Wilder علّی در t)، تقدم SL؛
  اگر نخورد تا t+1+21 ⇒ close همان کندل. spread=3.3 پیپ.

فاز explore: گرید قفل ۶ نقطه {H4,H8,D1}×{1.272,2.058} فقط نیمهٔ اول رویدادها.
  واجد: n>=100 ∧ net>0 ∧ lift >= 3.84×perm_sd (نول سکه K=500).
فاز verdict: تک‌لمس کل داده روی برنده + compute_rqs2 (n_trials=400، K=1000).
نول: سکهٔ منصف روی همان رویدادها/هندسه، seed=20260827 (قانون هندسه‌نول S612).
"""
import os, sys, json, time
import numpy as np

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from engine.rqs2 import compute_rqs2

SEED = 20260827
N_TRIALS = 400
Z_LUCK = 3.84
PIP = 0.10
SPREAD = 3.3
HOLD = 21
FRAMA_N = 16
GRID_TF = ['H4', 'H8', 'D1']
GRID_K = [1.272, 2.058]
OUT_DIR = os.path.join(ROOT, 'results', '_s615_frama')
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


def frama16(h, l, c):
    """FRAMA کانونی الرز، N=16. بازگشتی روی close؛ D از سه بازهٔ high/low."""
    n = len(c)
    N = FRAMA_N
    half = N // 2
    out = np.full(n, np.nan)
    if n <= N:
        return out
    out[N - 1] = c[:N].mean()   # seed
    log2 = np.log(2.0)
    for t in range(N, n):
        # پنجرهٔ [t-N+1 .. t]؛ نیمهٔ قدیمی و نیمهٔ تازه
        i0 = t - N + 1
        hh1 = h[i0:i0 + half].max(); ll1 = l[i0:i0 + half].min()
        hh2 = h[i0 + half:t + 1].max(); ll2 = l[i0 + half:t + 1].min()
        hh3 = h[i0:t + 1].max(); ll3 = l[i0:t + 1].min()
        n1 = (hh1 - ll1) / half
        n2 = (hh2 - ll2) / half
        n3 = (hh3 - ll3) / N
        if n1 > 0 and n2 > 0 and n3 > 0:
            D = (np.log(n1 + n2) - np.log(n3)) / log2
        else:
            D = 1.0
        alpha = np.exp(-4.6 * (D - 1.0))
        alpha = min(1.0, max(0.01, alpha))
        out[t] = alpha * c[t] + (1.0 - alpha) * out[t - 1]
    return out


def build_events(d):
    """رویدادها: (sig_bar, dir) — تغییر علامت close−FRAMA. atr34 معتبر لازم."""
    h, l, c = d['high'], d['low'], d['close']
    fr = frama16(h, l, c)
    atr = wilder_atr34(h, l, c)
    diff = c - fr
    n = len(c)
    ev = []
    for t in range(1, n - 1):          # ورود open[t+1] لازم
        if np.isnan(fr[t]) or np.isnan(fr[t - 1]) or np.isnan(atr[t]) or atr[t] <= 0:
            continue
        prev, cur = diff[t - 1], diff[t]
        if prev <= 0 and cur > 0:
            ev.append((t, +1))
        elif prev >= 0 and cur < 0:
            ev.append((t, -1))
    return ev, atr


def outcome(d, atr, sig, direction, k):
    """خروجی یک معامله در یک جهت. برمی‌گرداند (win:0/1, pnl_pip)."""
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
            if l[b] <= sl:                    # تقدم SL
                pnl = (sl - entry) / PIP - SPREAD
                return (0, pnl)
            if h[b] >= tp:
                pnl = (tp - entry) / PIP - SPREAD
                return (1, pnl)
        else:
            if h[b] >= sl:
                pnl = (entry - sl) / PIP - SPREAD
                return (0, pnl)
            if l[b] >= 0 and l[b] <= tp:
                pnl = (entry - tp) / PIP - SPREAD
                return (1, pnl)
    px = c[last]
    pnl = ((px - entry) if direction > 0 else (entry - px)) / PIP - SPREAD
    return (1 if pnl > 0 else 0, pnl)


def eval_card(d, atr, events, k):
    """برای هر رویداد، خروجی هر دو جهت (برای نول سکه) + خروجی جهت سیگنال."""
    rows = []   # (sig, dir, win_sig, pnl_sig, win_long, pnl_long, win_short, pnl_short, bar_time)
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
    """نول سکهٔ منصف: جهت تصادفی ± روی همان رویدادها/هندسه."""
    m = len(rows)
    wl = np.array([r[4] for r in rows], dtype=float)
    ws = np.array([r[6] for r in rows], dtype=float)
    rng = np.random.default_rng(seed)
    wrs = np.empty(K)
    for kk in range(K):
        pick = rng.integers(0, 2, m)     # 1=long
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
    return dict(n=len(rows), wr=100.0 * w.mean(), net=float(p.sum()))


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
            z = lift / nl['perm_sd'] if nl['perm_sd'] > 0 else 0.0
            rec = dict(tf=tf, k=k, **st, **nl, ref=ref,
                       lift=round(lift, 2), z=round(z, 2),
                       eligible=bool(st['n'] >= 100 and st['net'] > 0
                                     and lift >= Z_LUCK * nl['perm_sd']))
            grid.append(rec)
            print(f"  {tf} k={k}: n={st['n']} WR={st['wr']:.2f} net={st['net']:.0f} "
                  f"ref={ref:.2f} lift={lift:+.2f} z={z:.2f} elig={rec['eligible']}", flush=True)
    with open(os.path.join(OUT_DIR, 'grid_first_half.json'), 'w') as f:
        json.dump(grid, f, indent=1, ensure_ascii=False)
    elig = [g for g in grid if g.get('eligible')]
    if not elig:
        dec = dict(decision='death', reason='no_eligible_point',
                   rule='n>=100 AND net>0 AND lift>=3.84*perm_sd',
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
