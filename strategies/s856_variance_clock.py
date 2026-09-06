# -*- coding: utf-8 -*-
"""
S856 — Variance-Clock Directional Efficiency (زمان واریانس) — XAUUSD فقط
================================================================================
پیش‌ثبت : results/S856_PREREG_VARIANCE_CLOCK_EFFICIENCY.md  (commit 59e73872)
داور    : engine/rqs2.compute_rqs2 — حکم موتور عیناً گزارش می‌شود
مسیر C  : اکتشاف فقط ۶۰٪ نخست؛ یک قضاوت با split_bar. n_trials = 32.

فرضیه (ماندلبرو): قیمت = براونی در زمان معاملاتی T (Mandelbrot-Taylor 1967, Clark 1973).
در پنجره‌ای با بودجه‌ی واریانس ثابت V_B=B·median(r²), نسبت E=ΔP/√V تحت نول ~N(0,1).
عبور تازه‌ی E از θ ⇒ مسیر «مستقیم‌تر از براونی» ⇒ ورود در جهت جابه‌جایی.
"""
import sys
import os
import json
import gc

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s348_rr_sweep import (queue_rr, trades_df,          # noqa: E402
                                      cost_pip)
from strategies.s851_cusum_breakpoint import atr_series             # noqa: E402
from tools import s434_fast_data as fd                              # noqa: E402

# ==================== پارامترهای منجمدِ پیش‌ثبت‌شده ====================
ASSET = 'XAUUSD'
BUDGETS = (21, 55)
THETAS = (2.0, 2.618)
K_SL = (1.272, 1.618)
RRS = (1.618, 2.058)
MED_WIN = 1000
ATR_P = 34
MAX_HOLD = 34
SPLIT_FRAC = 0.60
N_TRIALS = 32                    # 16 ترکیب × 2 سمت
N_PERM = 600
MAX_UNCOND = 50_000
MAX_NULL_POOL = 1_000_000
SEED = 20260905
EXPLORE_MIN_N = 30
SL_FLOOR_PIP = 5.0
OUT = 'results/_scan_S856'


def efficiency_series(close, B, med_win):
    """E_i = ΔP/√V روی پنجره‌ی واریانسیِ به‌عقب با بودجه V_B = B·median(v[i-med_win..i-1]).
    median علّی (shift 1). پنجره: کمترین j با T_i − T_{j-1} ≥ V_B. علّیت سخت."""
    n = len(close)
    E = np.full(n, np.nan)
    lc = np.log(np.maximum(close, 1e-12))
    v = np.zeros(n)
    for i in range(1, n):
        d = lc[i] - lc[i - 1]
        v[i] = d * d
    T = np.zeros(n)
    for i in range(1, n):
        T[i] = T[i - 1] + v[i]
    buf = np.empty(med_win)
    med = 0.0
    for i in range(med_win + 1, n):
        # median علّی هر 50 بار بازمحاسبه (هزینه) — مقدار بین‌آن ثابت (همچنان علّی)
        if (i - med_win - 1) % 50 == 0:
            for q in range(med_win):
                buf[q] = v[i - med_win + q]
            med = np.median(buf)
        if med <= 0.0:
            continue
        VB = B * med
        # جست‌وجوی به‌عقب برای j: T[i] - T[j-1] >= VB
        j = i
        while j > 1 and (T[i] - T[j - 1]) < VB:
            j -= 1
        V = T[i] - T[j - 1]
        if V <= 0.0 or j <= 1:
            continue
        dP = lc[i] - lc[j - 1]
        E[i] = dP / np.sqrt(V)
    return E


def cross_signals(E, theta):
    """لبه‌ی تازه: E_i ≥ θ و E_{i-1} < θ ⇒ LONG؛ آینه‌ای SHORT."""
    n = len(E)
    ls = np.zeros(n, dtype=np.bool_)
    ss = np.zeros(n, dtype=np.bool_)
    for i in range(1, n):
        a = E[i]
        b = E[i - 1]
        if a != a or b != b:
            continue
        if a >= theta and b < theta:
            ls[i] = True
        if a <= -theta and b > -theta:
            ss[i] = True
    return ls, ss


try:
    from numba import njit
    efficiency_series = njit(cache=True)(efficiency_series)
    cross_signals = njit(cache=True)(cross_signals)
except Exception:
    pass


def combo_trades(df, ls, ss, atr, k, rr, lo, hi, pip):
    idx = np.where(ls | ss)[0]
    idx = idx[(idx >= lo) & (idx < hi)]
    a = atr[idx]
    ok = np.isfinite(a) & (a > 0)
    idx, a = idx[ok], a[ok]
    if len(idx) == 0:
        return None
    is_long = ls[idx]
    sl_dist = np.maximum(k * a, SL_FLOOR_PIP * pip)
    return queue_rr(df, idx, is_long, sl_dist, ASSET, MAX_HOLD, rr)


def build_null(df, atr, k, rr, n_long, n_short, warmup, pip, rng,
               verbose=True):
    n = len(df)
    valid = np.arange(warmup, n - MAX_HOLD - 2)
    a = atr[valid]
    ok = np.isfinite(a) & (a > 0)
    valid, a = valid[ok], a[ok]
    if len(valid) > MAX_NULL_POOL:
        sub = np.sort(rng.choice(len(valid), size=MAX_NULL_POOL,
                                 replace=False))
        valid, a = valid[sub], a[sub]
    sl_all = np.maximum(k * a, SL_FLOOR_PIP * pip)
    null = {}
    for side, is_long_flag, n_side in (('long', True, n_long),
                                       ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) > n_side:
            m = min(len(valid), MAX_UNCOND)
            pick0 = np.sort(rng.choice(len(valid), size=m, replace=False))
            s_all = queue_rr(df, valid[pick0], np.full(m, is_long_flag),
                             sl_all[pick0], ASSET, MAX_HOLD, rr)
            if s_all:
                d['uncond_wr'] = s_all['wr']
            wrs = []
            for it in range(N_PERM):
                pick = np.sort(rng.choice(len(valid), size=n_side,
                                          replace=False))
                s_p = queue_rr(df, valid[pick],
                               np.full(n_side, is_long_flag),
                               sl_all[pick], ASSET, MAX_HOLD, rr)
                if s_p:
                    wrs.append(s_p['wr'])
                if verbose and (it + 1) % 200 == 0:
                    print(f'      null {side}: perm {it+1}/{N_PERM}',
                          flush=True)
                if (it + 1) % 50 == 0:
                    gc.collect()
            if wrs:
                w = np.asarray(wrs, dtype='float64')
                d.update(perm_mean=float(w.mean()),
                         perm_sd=float(w.std(ddof=1)),
                         perm_max=float(w.max()), perm_k=int(len(w)))
        null[side] = d
        if verbose:
            print(f"      null {side:<5} uncond={d['uncond_wr']} "
                  f"perm_mean={d['perm_mean']} sd={d['perm_sd']}", flush=True)
    return null


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return (None if not np.isfinite(x) else float(x))
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return None
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(_jsonable(obj), f, indent=1, ensure_ascii=False)
    print(f'  ✓ checkpoint saved: {path}', flush=True)


def run_tf(tf, verbose=True):
    print(f"\n{'='*90}\n=== S856 Variance-Clock Efficiency :: XAUUSD-{tf} ===", flush=True)
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    n = len(df)
    close = df['close'].values.astype(np.float64)
    bar_time = d['time']
    for _k in ('hour', 'dow', 'volume'):
        d.pop(_k, None)
    gc.collect()
    pip = se.ASSETS[ASSET]['pip']
    c_pip = cost_pip(ASSET)
    warmup = max(ATR_P + 2, MED_WIN + 2)
    split = int(n * SPLIT_FRAC)
    print(f'    src={src}', flush=True)
    print(f'    bars={n:,}  split(60%)={split:,}  warmup={warmup}  '
          f'cost={c_pip:.2f}pip', flush=True)

    if n < warmup + 500 or split <= warmup + 100:
        out = dict(tf=tf, src=src, bars=n, verdict='TOO_SHORT')
        _save(tf, out)
        return out

    atr = atr_series(df)

    # ---------- ۱) اکتشاف: فقط ۶۰٪ نخست ----------
    hi_explore = split - MAX_HOLD - 2
    grid = []
    sig_cache = {}
    for B in BUDGETS:
        E = efficiency_series(close, B, MED_WIN)
        fin = E[np.isfinite(E)]
        print(f'    B={B}: E finite={len(fin):,} mean={fin.mean():.3f} sd={fin.std():.3f} '
              f'p(|E|>=2)={(np.abs(fin) >= 2).mean():.4f}', flush=True)
        for th in THETAS:
            ls, ss = cross_signals(E, th)
            sig_cache[(B, th)] = (ls, ss)
            for k in K_SL:
                for rr in RRS:
                    st = combo_trades(df, ls, ss, atr, k, rr,
                                      warmup, hi_explore, pip)
                    row = dict(B=B, th=th, k=k, rr=rr,
                               n=(st['n'] if st else 0),
                               exp=(round(st['exp'], 4) if st else None),
                               wr=(round(st['wr'], 2) if st else None),
                               pf=(round(st['pf'], 3) if st else None))
                    grid.append(row)
                    if verbose:
                        print(f"    explore B={B:<3} th={th:<6} k={k:<6} rr={rr:<6} "
                              f"n={row['n']:<7} exp={row['exp']} wr={row['wr']} "
                              f"pf={row['pf']}", flush=True)
        del E
    elig = [g for g in grid if g['n'] >= EXPLORE_MIN_N and g['exp'] is not None]
    if not elig:
        out = dict(tf=tf, src=src, bars=n, grid=grid,
                   verdict='NO_ELIGIBLE_COMBO')
        _save(tf, out)
        return out
    elig.sort(key=lambda g: (g['exp'], g['n']), reverse=True)
    win = elig[0]
    B_w, th_w, k_w, rr_w = win['B'], win['th'], win['k'], win['rr']
    print(f"\n    ★ winner (exploration only): B={B_w} th={th_w} k={k_w} rr={rr_w}  "
          f"exp={win['exp']}pip n={win['n']}", flush=True)

    # ---------- ۲) قضاوت: یک بار، کل داده، split_bar ----------
    ls, ss = sig_cache[(B_w, th_w)]
    for key in list(sig_cache.keys()):
        if key != (B_w, th_w):
            del sig_cache[key]
    gc.collect()
    st = combo_trades(df, ls, ss, atr, k_w, rr_w, warmup,
                      n - MAX_HOLD - 2, pip)
    if st is None or st['n'] < 5:
        out = dict(tf=tf, src=src, bars=n, grid=grid, winner=win,
                   verdict='NO_TRADES_FULL')
        _save(tf, out)
        return out
    del sig_cache, ls, ss
    gc.collect()
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    print(f"    full-data trades n={st['n']} (L={n_long}/S={n_short}) "
          f"wr={st['wr']:.2f} exp={st['exp']:.3f}pip "
          f"sl_med={sl_med:.1f} tp_med={tp_med:.1f}", flush=True)

    rng = np.random.default_rng(SEED)
    null = build_null(df, atr, k_w, rr_w, n_long, n_short, warmup, pip, rng,
                      verbose=verbose)

    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null, n_trials=N_TRIALS,
                          split_bar=split, close=close)
    print(f"\n    ═══ RQS2 verdict [{tf}]: {r['verdict']}  "
          f"score={r['rqs2_score']}", flush=True)
    print(f"    gates: {r['gates']}", flush=True)

    out = dict(tf=tf, src=src, bars=n, split_bar=split,
               grid=grid, winner=win,
               judged=dict(B=B_w, th=th_w, k=k_w, rr=rr_w,
                           n=int(st['n']), n_long=n_long, n_short=n_short,
                           wr=round(st['wr'], 2), exp=round(st['exp'], 4),
                           pf=round(st['pf'], 3),
                           sl_med=round(sl_med, 2), tp_med=round(tp_med, 2)),
               null=null, gates=r['gates'], metrics=r['metrics'],
               verdict=r['verdict'], rqs2_score=r['rqs2_score'],
               notes=r['notes'])
    _save(tf, out)
    del df, d, atr
    gc.collect()
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else ['H6']
    for tf in tfs:
        try:
            run_tf(tf)
        except Exception as e:
            import traceback
            traceback.print_exc()
            _save(tf, dict(tf=tf, verdict='ERROR', error=str(e)))
    print('\nS856 scan done.', flush=True)
