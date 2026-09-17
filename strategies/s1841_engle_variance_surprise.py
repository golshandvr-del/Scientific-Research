# -*- coding: utf-8 -*-
"""
S1841 — شگفتیِ واریانس شرطی (Variance Forecast Surprise) × درفت — رابرت انگل
=============================================================================
پیش‌ثبت: results/S1841_PREREG_engle_variance_surprise.md (کامیت 18be7809)
مسیر C. S_t = RV_m(t)/(m·σ²_{t−m+1})؛ عبور تازه از s؛ بدون شوک منفرد در پنجره؛
جهت = درفت پنجره؛ ورود open t+1.
"""
import os
import sys
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2                                   # noqa: E402
from tools import s434_fast_data as fd                    # noqa: E402
from strategies.s840_engle_shock import (                 # noqa: E402
    ASSET, TF_HOLD, ALL_TFS, MIN_N_IS, SPLIT_FRAC, cost_pip, atr_series,
    ewma_z, queue_frozen, build_null_oos, trades_from_st, _slim)

OUT = 'results/_scan_S1841'
SEED = 1841
Z_SHOCK_EXCL = 2.618
M_GRID = (8, 13, 21)
S_GRID = (1.618, 2.058)
SLK_GRID = (1.272, 1.618)
RR_GRID = (1.0, 1.272)
N_GRID = len(M_GRID) * len(S_GRID) * len(SLK_GRID) * len(RR_GRID)   # 24


def surprise_series(r, z, m):
    """S_t = Σ_{i<m} r²_{t−i} / (m·σ²_{t−m+1}); σ² بازسازی از z: σ²=r²/z² نامناسب
    (z=0 ممکن) ⇒ σ² مستقیماً با همان بازگشت RiskMetrics دوباره ساخته می‌شود."""
    n = len(r)
    var = np.full(n, np.nan)
    k0 = min(50, n - 1)
    v = float(np.var(r[1:k0 + 1]))
    v = v if v > 0 else 1e-12
    var[k0] = v
    for t in range(k0 + 1, n):
        v = 0.94 * v + 0.06 * r[t - 1] * r[t - 1]
        var[t] = v
    r2 = r * r
    cs = np.concatenate([[0.0], np.cumsum(r2)])
    rv = np.full(n, np.nan)
    rv[m - 1:] = cs[m:] - cs[:-m]                 # Σ r²_{t-m+1..t}
    sig0 = np.full(n, np.nan)
    sig0[m - 1:] = var[:n - m + 1]                # σ² در آغاز پنجره (t−m+1)
    with np.errstate(divide='ignore', invalid='ignore'):
        S = rv / (m * sig0)
    # بیشینهٔ |z| در پنجره
    az = np.abs(np.nan_to_num(z, nan=0.0))
    from numpy.lib.stride_tricks import sliding_window_view as swv
    mx = np.full(n, np.nan)
    mx[m - 1:] = swv(az, m).max(axis=1)
    return S, mx


def surprise_signals(S, mx, close, atr, m, s, warmup, lo=None, hi=None,
                     mode='event'):
    """
    mode='event'  : عبور تازه S≥s، بدون شوک منفرد، جهت درفت پنجره
    mode='drift'  : بازوی P1 — همهٔ کندل‌های معتبر (بی‌شرط شگفتی) با جهت درفت
    mode='counter': رویداد، جهت خلاف درفت (P3)
    بازگشت: idx, is_long, had_shock (برای P0)
    """
    n = len(S)
    valid = np.isfinite(atr) & (atr > 0) & np.isfinite(S)
    d = np.zeros(n)
    d[m:] = close[m:] - close[:-m]
    if mode == 'drift':
        ev = valid & (d != 0)
    else:
        cross = np.zeros(n, bool)
        cross[1:] = (S[1:] >= s) & (S[:-1] < s)
        ev = valid & cross & (d != 0)
    had_shock = ev & (mx >= Z_SHOCK_EXCL)
    if mode != 'drift':
        ev = ev & ~(mx >= Z_SHOCK_EXCL)
    idx = np.where(ev)[0]
    idx = idx[idx >= max(warmup, m + 1)]
    if lo is not None:
        idx = idx[idx >= lo]
    if hi is not None:
        idx = idx[idx < hi]
    n_shock = int(had_shock[np.where(had_shock)[0] >= max(warmup, m + 1)].sum())
    if len(idx) == 0:
        return idx, np.zeros(0, bool), n_shock
    isl = d[idx] > 0
    if mode == 'counter':
        isl = ~isl
    return idx, isl, n_shock


def _card(df, sig, isl, atr, slk, rr, hold):
    if len(sig) < 5:
        return None
    st = queue_frozen(df, sig, isl, slk * atr[sig], hold, rr)
    if st is None or st['n'] < 5:
        return None
    return dict(n=st['n'], wr=round(st['wr'], 2), exp=round(st['exp'], 4),
                pf=round(st['pf'], 3))


def discover_is(df, r, z, cl, atr, split, warmup, hold, verbose=True):
    c = cost_pip()
    hi = split - hold - 2
    rows = []
    cache = {}
    for m in M_GRID:
        S, mx = surprise_series(r, z, m)
        cache[m] = (S, mx)
        for s in S_GRID:
            sig, isl, nsh = surprise_signals(S, mx, cl, atr, m, s, warmup, hi=hi)
            if len(sig) < MIN_N_IS:
                continue
            for slk in SLK_GRID:
                for rr in RR_GRID:
                    st = queue_frozen(df, sig, isl, slk * atr[sig], hold, rr)
                    if st is None or st['n'] < MIN_N_IS:
                        continue
                    sl_med = float(np.median(st['sl_pip']))
                    tp_med = float(np.median(st['tp_pip']))
                    be = 100.0 * (sl_med + 2.0 * c) / (sl_med + tp_med)
                    rows.append(dict(m=m, s=s, sl_k=slk, rr=rr, n=st['n'],
                                     wr=round(st['wr'], 2),
                                     exp=round(st['exp'], 4),
                                     pf=round(st['pf'], 3),
                                     sl_med=round(sl_med, 2),
                                     tp_med=round(tp_med, 2), be=round(be, 2),
                                     n_sig=int(len(sig)), n_excl_shock=nsh,
                                     passes_be=bool(st['wr'] > be)))
    ok = [x for x in rows if x['passes_be']]
    best = max(ok, key=lambda x: x['exp']) if ok else None
    if verbose:
        print(f"    IS grid: {len(rows)}/{N_GRID} combos n>=30 · "
              f"{len(ok)} pass robust-BE", flush=True)
        if best:
            print(f"    IS WINNER: m={best['m']} s={best['s']} sl_k={best['sl_k']} "
                  f"rr={best['rr']} → n={best['n']} WR={best['wr']}% "
                  f"exp={best['exp']:+.3f}pip excl_shock={best['n_excl_shock']}",
                  flush=True)
    return rows, best, cache


def diagnostics_is(df, cache, cl, atr, split, warmup, hold, best, verbose=True):
    hi = split - hold - 2
    m, slk, rr = best['m'], best['sl_k'], best['rr']
    S, mx = cache[m]
    out = {}
    sig, isl, _ = surprise_signals(S, mx, cl, atr, m, 0.0, warmup, hi=hi,
                                   mode='drift')
    step = max(1, len(sig) // 4000)
    out['drift_only'] = _card(df, sig[::step], isl[::step], atr, slk, rr, hold)
    for s in S_GRID:
        sig, isl, nsh = surprise_signals(S, mx, cl, atr, m, s, warmup, hi=hi)
        out[f'event_{s}'] = _card(df, sig, isl, atr, slk, rr, hold)
        out[f'excl_shock_{s}'] = nsh
    sig, isl, _ = surprise_signals(S, mx, cl, atr, m, best['s'], warmup, hi=hi,
                                   mode='counter')
    out['counter'] = _card(df, sig, isl, atr, slk, rr, hold)

    def wr(k):
        return out[k]['wr'] if out.get(k) else None
    ev = wr(f"event_{best['s']}")
    p1 = ev is not None and wr('drift_only') is not None and ev > wr('drift_only')
    p2 = (wr('event_2.058') is not None and wr('event_1.618') is not None
          and wr('event_2.058') >= wr('event_1.618'))
    p3 = ev is not None and wr('counter') is not None and wr('counter') < ev
    out.update(P1_surprise_adds=bool(p1), P2_monotone=bool(p2),
               P3_counter_worse=bool(p3))
    if verbose:
        print(f"    DIAG(IS) drift_only={out['drift_only']} | "
              f"event1.618={out['event_1.618']} | event2.058={out['event_2.058']}"
              f" | counter={out['counter']} | excl_shock={out[f'excl_shock_{best['s']}']}",
              flush=True)
        print(f"    P1={p1} P2={p2} P3={p3}", flush=True)
    return out


def _save(tf, out):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"    checkpoint saved → {path}", flush=True)


def run_tf(tf, verbose=True):
    hold = TF_HOLD[tf]
    d = fd.load_fast(ASSET, tf)
    assert 'mt5_full' in str(d.get('src')), f'{tf}: data not mt5_full — STOP'
    df = fd.as_dataframe(d)
    n = len(df)
    warmup = 250 if n >= 5000 else max(60, n // 10)
    split = int(n * SPLIT_FRAC)
    c = cost_pip()
    print(f"\n{'=' * 88}\n=== S1841 Variance-Surprise×Drift :: {ASSET}-{tf} "
          f"(bars={n:,} span={d.get('span_years', '?')}y) ===", flush=True)
    print(f"    hold={hold} split@{split:,} warmup={warmup} cost={c:.2f}pip "
          f"grid={N_GRID} src={d.get('src')}", flush=True)
    out = dict(tf=tf, asset=ASSET, bars=n, src=str(d.get('src')),
               span_years=d.get('span_years'), hold=hold, split_bar=split,
               warmup=warmup, grid=N_GRID)
    if n < warmup + 4 * hold + 200:
        out['verdict'] = 'INCOMPLETE'
        out['reason'] = 'TOO_SHORT'
        _save(tf, out)
        return out
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    z, r = ewma_z(cl)
    del h, l

    rows, best, cache = discover_is(df, r, z, cl, atr, split, warmup, hold,
                                    verbose)
    out['is_grid'] = rows
    if best is None:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'NO_IS_CANDIDATE'
        print(f"    → {tf}: UNPROVEN — no IS candidate; OOS untouched.",
              flush=True)
        _save(tf, out)
        return out
    out['is_winner'] = best
    out['diag_is'] = diagnostics_is(df, cache, cl, atr, split, warmup, hold,
                                    best, verbose)

    S, mx = cache[best['m']]
    sig, isl, nsh = surprise_signals(S, mx, cl, atr, best['m'], best['s'],
                                     warmup)
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
    print(f"    FULL frozen: n={len(tr)} (L={n_long} S={n_short}) n_OOS={n_oos} "
          f"WR={st['wr']:.2f}% exp={st['exp']:+.3f}pip excl_shock={nsh}",
          flush=True)
    valid = np.where(np.isfinite(S) & np.isfinite(atr) & (atr > 0))[0]
    valid_oos = valid[(valid >= split) & (valid >= warmup)]
    del valid
    null = build_null_oos(df, atr, valid_oos, best['sl_k'], best['rr'], hold,
                          n_long, n_short, verbose=verbose)
    del valid_oos
    bar_time = df['time'].values if 'time' in df.columns else None
    common = dict(sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time, null=null,
                  split_bar=split, close=cl)
    res_official = rqs2.compute_rqs2(tr, ASSET, n_trials=1, **common)
    res_cons = rqs2.compute_rqs2(tr, ASSET, n_trials=N_GRID, **common)
    print(rqs2.format_rqs2(f'{tf} OFFICIAL(pathC) ', res_official), flush=True)
    print(rqs2.format_rqs2(f'{tf} SENS(n_t={N_GRID}) ', res_cons), flush=True)
    out['full'] = dict(n=len(tr), n_long=n_long, n_short=n_short, n_oos=n_oos,
                       wr=round(st['wr'], 2), exp=round(st['exp'], 4),
                       pf=round(st['pf'], 3), sl_med=round(sl_med, 2),
                       tp_med=round(tp_med, 2), n_excl_shock=nsh)
    out['null'] = null
    out['rqs2_official'] = _slim(res_official)
    out['rqs2_sensitivity'] = _slim(res_cons)
    out['verdict'] = res_official.get('verdict')
    _save(tf, out)
    return out


def main():
    tfs = sys.argv[1:] if len(sys.argv) > 1 else ALL_TFS
    os.makedirs(OUT, exist_ok=True)
    for tf in tfs:
        if os.path.exists(os.path.join(OUT, f'{tf}.json')):
            print(f"skip {tf} (checkpoint exists)", flush=True)
            continue
        try:
            run_tf(tf)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"!! {tf} FAILED: {e}", flush=True)
    print("\nS1841 scan complete.", flush=True)


if __name__ == '__main__':
    main()
