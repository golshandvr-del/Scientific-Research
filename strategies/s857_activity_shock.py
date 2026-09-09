# -*- coding: utf-8 -*-
"""
S857 — Activity-Breakpoint Shock (شوک درون رژیم فعالیت) — XAUUSD فقط
================================================================================
پیش‌ثبت : results/S857_PREREG_ACTIVITY_BREAKPOINT_SHOCK.md  (commit dae2942e)
داور    : engine/rqs2.compute_rqs2 — حکم موتور عیناً گزارش می‌شود
مسیر C  : اکتشاف فقط ۶۰٪ نخست؛ یک قضاوت با split_bar. n_trials = 32.

فرضیه (ماندلبرو/Clark/Easley-O'Hara): CUSUM روی لگ‌حجم استانداردشده‌ی علّی، تغییر پایدار
سطح فعالیت (ورود مطلعان) را می‌یابد. شوک قیمتی |z|≥2.618 که *درون* این رژیم فعال رخ دهد
اطلاعاتی است ⇒ follow. شرط‌گذار ناهم‌جنس (حجم) — نه قیمت.
هارد‌گارد داده: فقط data/mt5_full.
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
from strategies.s851_cusum_breakpoint import atr_series, zscores    # noqa: E402
from tools import s434_fast_data as fd                              # noqa: E402

# ==================== پارامترهای منجمدِ پیش‌ثبت‌شده ====================
ASSET = 'XAUUSD'
H_VOL = (5.0, 8.0)
G_BARS = (21, 55)
K_SL = (1.272, 1.618)
RRS = (1.618, 2.058)
Z_SHOCK = 2.618                  # ارث S602/S965 — ثابت
K_DRIFT_V = 0.5
STD_WIN = 500
ATR_P = 34
MAX_HOLD = 34
SPLIT_FRAC = 0.60
N_TRIALS = 32                    # 16 ترکیب × 2 سمت
N_PERM = 600
MAX_UNCOND = 50_000
MAX_NULL_POOL = 1_000_000
SEED = 20260906
EXPLORE_MIN_N = 30
SL_FLOOR_PIP = 5.0
OUT = 'results/_scan_S857'


def std_logvol(vol, win):
    """u_i = (log v_i − mean_{i-win..i-1}) / sd_{i-win..i-1} — پنجره‌ی علّی (shift 1), O(n)."""
    n = len(vol)
    lv = np.empty(n)
    for i in range(n):
        lv[i] = np.log(vol[i] if vol[i] > 0.0 else 1.0)
    u = np.zeros(n)
    s1 = 0.0
    s2 = 0.0
    for i in range(n):
        if i >= win:
            m = s1 / win
            var = s2 / win - m * m
            sd = np.sqrt(var) if var > 1e-12 else 0.0
            if sd > 0.0:
                u[i] = (lv[i] - m) / sd
        # افزودن i به پنجره برای بار بعد؛ حذف i-win
        s1 += lv[i]
        s2 += lv[i] * lv[i]
        if i - win >= 0:
            s1 -= lv[i - win]
            s2 -= lv[i - win] * lv[i - win]
    return u


def active_regime(u, k_drift, h, G, warmup):
    """CUSUM یک‌طرفه‌ی صعودی روی u؛ شلیک ⇒ رژیم فعال برای G بار (شامل بار شلیک)؛ ریست S."""
    n = len(u)
    act = np.zeros(n, dtype=np.bool_)
    S = 0.0
    until = -1
    for i in range(warmup, n):
        S = max(0.0, S + u[i] - k_drift)
        if S > h:
            until = i + G
            S = 0.0
        if i <= until:
            act[i] = True
    return act


def shock_signals(z, act, zt):
    n = len(z)
    ls = np.zeros(n, dtype=np.bool_)
    ss = np.zeros(n, dtype=np.bool_)
    for i in range(n):
        if not act[i]:
            continue
        if z[i] >= zt:
            ls[i] = True
        elif z[i] <= -zt:
            ss[i] = True
    return ls, ss


try:
    from numba import njit
    std_logvol = njit(cache=True)(std_logvol)
    active_regime = njit(cache=True)(active_regime)
    shock_signals = njit(cache=True)(shock_signals)
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
    print(f"\n{'='*90}\n=== S857 Activity-Breakpoint Shock :: XAUUSD-{tf} ===", flush=True)
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    n = len(df)
    close = df['close'].values.astype(np.float64)
    vol = df['volume'].values.astype(np.float64)
    assert 'mt5_full' in src, f'DATA GUARD: {src}'
    bar_time = d['time']
    for _k in ('hour', 'dow', 'volume'):
        d.pop(_k, None)
    gc.collect()
    pip = se.ASSETS[ASSET]['pip']
    c_pip = cost_pip(ASSET)
    warmup = max(ATR_P + 2, STD_WIN + 2)
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
    z = zscores(close)
    u = std_logvol(vol, STD_WIN)
    shock_all = (np.abs(z) >= Z_SHOCK)
    shock_all[:warmup] = False
    print(f'    shocks |z|>={Z_SHOCK}: {int(shock_all.sum()):,}  '
          f'u stats mean={u[warmup:].mean():.3f} sd={u[warmup:].std():.3f}', flush=True)
    diag = {}
    for hv in H_VOL:
        for G in G_BARS:
            act = active_regime(u, K_DRIFT_V, hv, G, warmup)
            ls, ss = shock_signals(z, act, Z_SHOCK)
            sig_cache[(hv, G)] = (ls, ss)
            # P1 تشخیصی (IS-only): شوک‌های بیرون رژیم
            lo_, so_ = shock_signals(z, ~act, Z_SHOCK)
            diag[(hv, G)] = dict(active_frac=float(act[warmup:].mean()),
                                 n_in=int((ls | ss)[warmup:hi_explore].sum()),
                                 n_out=int((lo_ | so_)[warmup:hi_explore].sum()),
                                 out_sigs=(lo_, so_))
            print(f'    regime hv={hv} G={G}: active_frac={diag[(hv, G)]["active_frac"]:.3f} '
                  f'shocks in={diag[(hv, G)]["n_in"]} out={diag[(hv, G)]["n_out"]}', flush=True)
            for k in K_SL:
                for rr in RRS:
                    st = combo_trades(df, ls, ss, atr, k, rr,
                                      warmup, hi_explore, pip)
                    row = dict(hv=hv, G=G, k=k, rr=rr,
                               n=(st['n'] if st else 0),
                               exp=(round(st['exp'], 4) if st else None),
                               wr=(round(st['wr'], 2) if st else None),
                               pf=(round(st['pf'], 3) if st else None))
                    grid.append(row)
                    if verbose:
                        print(f"    explore hv={hv:<4} G={G:<3} k={k:<6} rr={rr:<6} "
                              f"n={row['n']:<7} exp={row['exp']} wr={row['wr']} "
                              f"pf={row['pf']}", flush=True)
    elig = [g for g in grid if g['n'] >= EXPLORE_MIN_N and g['exp'] is not None]
    if not elig:
        out = dict(tf=tf, src=src, bars=n, grid=grid,
                   verdict='NO_ELIGIBLE_COMBO')
        _save(tf, out)
        return out
    elig.sort(key=lambda g: (g['exp'], g['n']), reverse=True)
    win = elig[0]
    hv_w, G_w, k_w, rr_w = win['hv'], win['G'], win['k'], win['rr']
    print(f"\n    ★ winner (exploration only): hv={hv_w} G={G_w} k={k_w} rr={rr_w}  "
          f"exp={win['exp']}pip n={win['n']}", flush=True)

    # ---------- ۲) قضاوت: یک بار، کل داده، split_bar ----------
    ls, ss = sig_cache[(hv_w, G_w)]
    # P1: همان هندسه روی شوک‌های بیرون رژیم (IS فقط)
    lo_, so_ = diag[(hv_w, G_w)]['out_sigs']
    st_out = combo_trades(df, lo_, so_, atr, k_w, rr_w, warmup, hi_explore, pip)
    p1 = dict(in_exp=win['exp'], in_n=win['n'],
              out_exp=(round(st_out['exp'], 4) if st_out else None),
              out_wr=(round(st_out['wr'], 2) if st_out else None),
              out_n=(st_out['n'] if st_out else 0),
              active_frac=diag[(hv_w, G_w)]['active_frac'])
    print(f'    P1 diag (IS): in exp={p1["in_exp"]} n={p1["in_n"]} | out exp={p1["out_exp"]} wr={p1["out_wr"]} n={p1["out_n"]}', flush=True)
    for kk in list(diag.keys()):
        diag[kk].pop('out_sigs', None)
    for key in list(sig_cache.keys()):
        if key != (hv_w, G_w):
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
               p1_diag=p1, judged=dict(hv=hv_w, G=G_w, k=k_w, rr=rr_w,
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
    print('\nS857 scan done.', flush=True)
