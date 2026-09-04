# -*- coding: utf-8 -*-
"""
S847 — شوک + پژواک (Shock & Echo) به سبک رابرت انگل
=====================================================
پیش‌ثبت: results/S847_PREREG_engle_shock_echo.md (کامیت 170fe3a1)
مسیر تعدد: C — جستجو فقط نیمهٔ اول؛ یک آزمون منجمد per-TF روی کل داده.

PRIMARY: |z_t| ≥ 2.618 (ثابت)
ECHO   : |z_t| ≥ z_lo و هم‌علامت با آخرین PRIMARY و فاصله ≤ W کندل
سیگنال = PRIMARY یا ECHO · جهت follow · ورود open t+1 (queue_frozen).

(بازسازی‌شده پس از ریست سندباکس — منطق عیناً مطابق پیش‌ثبت.)
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

OUT = 'results/_scan_S847'
SEED = 847

Z_PRIMARY = 2.618                       # ثابت — جستجو نمی‌شود
ZLO_GRID = (1.618, 2.058)
W_GRID = (13, 21)
SLK_GRID = (1.272, 1.618)
RR_GRID = (1.0, 1.272)
N_GRID = len(ZLO_GRID) * len(W_GRID) * len(SLK_GRID) * len(RR_GRID)   # = 16


def echo_signals(z, atr, z_lo, W, warmup, lo=None, hi=None):
    """
    حلقهٔ علّی O(n): آخرین PRIMARY (اندیس و علامت) دنبال می‌شود.
    سیگنال روی کندل t (بسته‌شده)؛ ورود open t+1 توسط queue_frozen.
    """
    n = len(z)
    valid = np.isfinite(atr) & (atr > 0) & np.isfinite(z)
    sig_m = np.zeros(n, dtype=bool)
    long_m = np.zeros(n, dtype=bool)
    is_echo = np.zeros(n, dtype=bool)
    last_i = -10 ** 9
    last_sign = 0
    for t in range(n):
        if not valid[t]:
            continue
        zt = z[t]
        if abs(zt) >= Z_PRIMARY:
            last_i = t
            last_sign = 1 if zt > 0 else -1
            sig_m[t] = True
            long_m[t] = zt > 0
            continue
        if abs(zt) >= z_lo and last_sign != 0 and (t - last_i) <= W:
            if (zt > 0 and last_sign > 0) or (zt < 0 and last_sign < 0):
                sig_m[t] = True
                long_m[t] = zt > 0
                is_echo[t] = True
    idx = np.where(sig_m)[0]
    idx = idx[idx >= warmup]
    if lo is not None:
        idx = idx[idx >= lo]
    if hi is not None:
        idx = idx[idx < hi]
    if len(idx) == 0:
        return idx, np.zeros(0, bool), np.zeros(0, bool)
    return idx, long_m[idx], is_echo[idx]


def discover_is(df, z, atr, split, warmup, hold, verbose=True):
    c = cost_pip()
    hi = split - hold - 2
    rows = []
    for z_lo in ZLO_GRID:
        for W in W_GRID:
            sig, isl, ech = echo_signals(z, atr, z_lo, W, warmup, hi=hi)
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
                    rows.append(dict(z_lo=z_lo, W=W, sl_k=slk, rr=rr,
                                     n=st['n'], wr=round(st['wr'], 2),
                                     exp=round(st['exp'], 4),
                                     pf=round(st['pf'], 3),
                                     sl_med=round(sl_med, 2),
                                     tp_med=round(tp_med, 2),
                                     be=round(be, 2),
                                     n_sig=int(len(sig)),
                                     echo_share=round(100.0 * ech.mean(), 1),
                                     passes_be=bool(st['wr'] > be)))
    ok = [x for x in rows if x['passes_be']]
    best = max(ok, key=lambda x: x['exp']) if ok else None
    if verbose:
        print(f"    IS grid: {len(rows)}/{N_GRID} combos n>=30 · "
              f"{len(ok)} pass robust-BE", flush=True)
        if best:
            print(f"    IS WINNER: z_lo={best['z_lo']} W={best['W']} "
                  f"sl_k={best['sl_k']} rr={best['rr']} → n={best['n']} "
                  f"WR={best['wr']}% exp={best['exp']:+.3f}pip "
                  f"echo_share={best['echo_share']}%", flush=True)
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

    print(f"\n{'=' * 88}\n=== S847 Shock+Echo :: {ASSET}-{tf} "
          f"(bars={n:,} span={d.get('span_years', '?')}y) ===", flush=True)
    print(f"    hold={hold} split@{split:,} warmup={warmup} "
          f"cost={c:.2f}pip grid={N_GRID} primary=2.618 follow", flush=True)

    out = dict(tf=tf, asset=ASSET, bars=n, src=str(d.get('src')),
               span_years=d.get('span_years'), hold=hold, split_bar=split,
               warmup=warmup, grid=N_GRID, z_primary=Z_PRIMARY)
    if n < warmup + 4 * hold + 100:
        out['verdict'] = 'INCOMPLETE'
        out['reason'] = 'TOO_SHORT'
        _save(tf, out)
        return out

    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    cl = df['close'].values.astype(np.float64)
    atr = atr_series(h, l, cl)
    z, _ = ewma_z(cl)
    del h, l

    rows, best = discover_is(df, z, atr, split, warmup, hold, verbose)
    out['is_grid'] = rows
    if best is None:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'NO_IS_CANDIDATE'
        print(f"    → {tf}: UNPROVEN — no IS candidate; OOS untouched.",
              flush=True)
        _save(tf, out)
        return out
    out['is_winner'] = best

    sig, isl, ech = echo_signals(z, atr, best['z_lo'], best['W'], warmup)
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
    print(f"    FULL frozen: n={len(tr)} (L={n_long} S={n_short}) "
          f"n_OOS={n_oos} WR={st['wr']:.2f}% exp={st['exp']:+.3f}pip "
          f"signals={len(sig)} echo_share={100.0 * ech.mean():.1f}%",
          flush=True)

    valid = np.where(np.isfinite(z) & np.isfinite(atr) & (atr > 0))[0]
    valid_oos = valid[(valid >= split) & (valid >= warmup)]
    del valid
    print(f"    null pool (OOS) = {len(valid_oos):,} bars · 800 perms/side",
          flush=True)
    null = build_null_oos(df, atr, valid_oos, best['sl_k'], best['rr'], hold,
                          n_long, n_short, verbose=verbose)
    del valid_oos

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
                       tp_med=round(tp_med, 2),
                       echo_share=round(100.0 * ech.mean(), 1))
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
        done = os.path.join(OUT, f'{tf}.json')
        if os.path.exists(done):
            print(f"skip {tf} (checkpoint exists)", flush=True)
            continue
        try:
            run_tf(tf)
        except Exception as e:
            print(f"!! {tf} FAILED: {e}", flush=True)
    print("\nS847 scan complete.", flush=True)


if __name__ == '__main__':
    main()
