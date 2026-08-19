# -*- coding: utf-8 -*-
"""
S842 — لایهٔ «رانش استانداردشدهٔ چندکندلی» (Standardized Drift Burst)
======================================================================
پیش‌ثبت: results/S842_PREREG_engle_standardized_drift_burst.md
مسیر تعدد: C (تأیید Holdout).

D_t = Σ_{i=t-W+1..t} r_i / (σ_t·√W) با W=8 و σ از EWMA λ=0.94 (علّی).
رویداد: عبور |D| از d_thr. جهت follow/fade از علامت D_t.
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2                                  # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402
from strategies.s840_engle_shock import (                # noqa: E402
    ASSET, TF_HOLD, ALL_TFS, ATR_P, MIN_N_IS, SPLIT_FRAC, N_PERM,
    NULL_POOL_CAP, LAMBDA, cost_pip, atr_series, queue_frozen,
    build_null_oos, trades_from_st, _slim)

OUT = 'results/_scan_S842'
SEED = 842

# ---------------- شبکهٔ پیش‌ثبت‌شده (منجمد — عیناً PREREG S842) ----------------
W = 8
D_GRID = (1.618, 2.058, 2.618)
MODES = ('follow', 'fade')
SLK_GRID = (1.0, 1.272, 1.618)
RR_GRID = (1.0, 1.272, 1.618)
N_GRID = len(D_GRID) * len(MODES) * len(SLK_GRID) * len(RR_GRID)   # = 54


def drift_stat(close):
    """D_t = rolling-sum(r, W) / (σ_t·√W). σ از EWMA علّی λ=0.94.

    نکتهٔ حافظه (درس OOM روی M1): هیچ آرایهٔ زائدی ساخته نمی‌شود؛ temporaries
    بلافاصله del می‌شوند. روی ۵M کندل peak < 200MB اضافه.
    """
    c = np.asarray(close, dtype=np.float64)
    n = len(c)
    rr = np.zeros(n)
    with np.errstate(divide='ignore', invalid='ignore'):
        rr[1:] = np.log(c[1:] / c[:-1])
    rr[~np.isfinite(rr)] = 0.0
    k0 = min(50, n - 1)
    if k0 < 5:
        return np.full(n, np.nan)
    v = float(np.var(rr[1:k0 + 1]))
    if v <= 0:
        v = 1e-12
    var = np.full(n, np.nan)
    var[k0] = v
    for t in range(k0 + 1, n):
        v = LAMBDA * v + (1.0 - LAMBDA) * rr[t - 1] * rr[t - 1]
        var[t] = v
    sd = np.sqrt(var)
    del var
    csum = np.cumsum(rr)
    del rr
    roll = np.full(n, np.nan)
    roll[W:] = csum[W:] - csum[:-W]
    roll[W - 1] = csum[W - 1]
    del csum
    with np.errstate(divide='ignore', invalid='ignore'):
        D = np.where(sd > 0, roll / (sd * np.sqrt(W)), np.nan)
    return D


def signals_for(D, atr, d_thr, mode, warmup, hi=None):
    """عبور |D| از d_thr (نه سطح). جهت از علامت D_t."""
    valid = np.isfinite(D) & np.isfinite(atr) & (atr > 0)
    absD = np.abs(D)
    cross = np.zeros(len(D), dtype=bool)
    cross[1:] = (valid[1:] & np.isfinite(D[:-1]) &
                 (absD[1:] >= d_thr) & (absD[:-1] < d_thr))
    idx = np.where(cross)[0]
    idx = idx[idx >= warmup]
    if hi is not None:
        idx = idx[idx < hi]
    if len(idx) == 0:
        return idx, np.zeros(0, bool)
    is_long = (D[idx] > 0) if mode == 'follow' else (D[idx] < 0)
    return idx, is_long


def discover_is(df, D, atr, split, warmup, hold, verbose=True):
    c = cost_pip()
    hi = split - hold - 2
    rows = []
    for d_thr in D_GRID:
        for mode in MODES:
            sig, isl = signals_for(D, atr, d_thr, mode, warmup, hi=hi)
            if len(sig) < MIN_N_IS:
                continue
            for slk in SLK_GRID:
                sl_dist = slk * atr[sig]
                for rr in RR_GRID:
                    st = queue_frozen(df, sig, isl, sl_dist, hold, rr)
                    if st is None or st['n'] < MIN_N_IS:
                        continue
                    sl_med = float(np.median(st['sl_pip']))
                    tp_med = float(np.median(st['tp_pip']))
                    be = 100.0 * (sl_med + 2.0 * c) / (sl_med + tp_med)
                    rows.append(dict(d_thr=d_thr, mode=mode, sl_k=slk, rr=rr,
                                     n=st['n'], wr=round(st['wr'], 2),
                                     exp=round(st['exp'], 4),
                                     pf=round(st['pf'], 3),
                                     sl_med=round(sl_med, 2),
                                     tp_med=round(tp_med, 2),
                                     be=round(be, 2),
                                     passes_be=bool(st['wr'] > be)))
    ok = [x for x in rows if x['passes_be']]
    best = max(ok, key=lambda x: x['exp']) if ok else None
    if verbose:
        print(f"    IS grid evaluated: {len(rows)}/{N_GRID} combos with n>=30 · "
              f"{len(ok)} pass robust-BE", flush=True)
        if best:
            print(f"    IS WINNER: |D|>={best['d_thr']} {best['mode']} "
                  f"sl_k={best['sl_k']} rr={best['rr']} → n={best['n']} "
                  f"WR={best['wr']}% exp={best['exp']:+.3f}pip", flush=True)
    return rows, best


def _save(tf, out):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"    checkpoint saved → {path}", flush=True)


def run_tf(tf, verbose=True):
    hold = TF_HOLD[tf]
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    warmup = 250 if n >= 5000 else max(60, n // 10)
    split = int(n * SPLIT_FRAC)
    c = cost_pip()

    print(f"\n{'=' * 88}\n=== S842 Drift-Burst :: {ASSET}-{tf} "
          f"(bars={n:,} src={d.get('src', '?')} span={d.get('span_years', '?')}y) ===",
          flush=True)
    print(f"    λ={LAMBDA} W={W} ATR_P={ATR_P} hold={hold} split@{split:,} "
          f"warmup={warmup} cost={c:.2f}pip grid={N_GRID}", flush=True)

    out = dict(tf=tf, asset=ASSET, bars=n, src=str(d.get('src')),
               span_years=d.get('span_years'), hold=hold, split_bar=split,
               warmup=warmup, grid=N_GRID)

    if n < warmup + 4 * hold + 100:
        out['verdict'] = 'INCOMPLETE'
        out['reason'] = 'TOO_SHORT'
        _save(tf, out)
        return out

    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    D = drift_stat(cl)

    rows, best = discover_is(df, D, atr, split, warmup, hold, verbose)
    out['is_grid'] = rows
    if best is None:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'NO_IS_CANDIDATE'
        print(f"    → {tf}: UNPROVEN — no IS candidate; OOS untouched.", flush=True)
        _save(tf, out)
        return out
    out['is_winner'] = best

    sig, isl = signals_for(D, atr, best['d_thr'], best['mode'], warmup)
    st = queue_frozen(df, sig, isl, best['sl_k'] * atr[sig], hold, best['rr'])
    if st is None or st['n'] < 5:
        out['verdict'] = 'INCOMPLETE'
        out['reason'] = 'NO_TRADES_FULL'
        _save(tf, out)
        return out
    tr = trades_from_st(st)
    n_oos = int((tr['entry_bar'] >= split).sum())
    sl_med = float(np.median(tr['sl_pip']))
    tp_med = float(np.median(tr['tp_pip']))
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    print(f"    FULL frozen run: n={len(tr)} (L={n_long} S={n_short}) "
          f"n_OOS={n_oos} WR={st['wr']:.2f}% exp={st['exp']:+.3f}pip "
          f"SL={sl_med:.1f} TP={tp_med:.1f}", flush=True)

    valid = np.where(np.isfinite(D) & np.isfinite(atr) & (atr > 0))[0]
    valid_oos = valid[(valid >= split) & (valid >= warmup)]
    print(f"    null pool (OOS) = {len(valid_oos):,} bars · {N_PERM} perms/side",
          flush=True)
    null = build_null_oos(df, atr, valid_oos, best['sl_k'], best['rr'], hold,
                          n_long, n_short, verbose=verbose)

    bar_time = df['time'].values if 'time' in df.columns else None
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                  null=null, split_bar=split, close=cl)
    res_official = rqs2.compute_rqs2(tr, ASSET, n_trials=1, **common)
    res_cons = rqs2.compute_rqs2(tr, ASSET, n_trials=N_GRID, **common)
    print(rqs2.format_rqs2(f'{tf} OFFICIAL(pathC) ', res_official), flush=True)
    print(rqs2.format_rqs2(f'{tf} SENS(n_t={N_GRID}) ', res_cons), flush=True)

    out['full'] = dict(n=len(tr), n_long=n_long, n_short=n_short, n_oos=n_oos,
                       wr=round(st['wr'], 2), exp=round(st['exp'], 4),
                       pf=round(st['pf'], 3), sl_med=round(sl_med, 2),
                       tp_med=round(tp_med, 2))
    out['null'] = null
    out['rqs2_official'] = _slim(res_official)
    out['rqs2_sensitivity'] = _slim(res_cons)
    out['verdict'] = res_official['verdict']
    out['rqs2_score'] = res_official.get('rqs2_score')
    _save(tf, out)
    print(f"    → {tf}: {out['verdict']} (score={out['rqs2_score']})", flush=True)
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else ALL_TFS
    for tf in tfs:
        run_tf(tf)
