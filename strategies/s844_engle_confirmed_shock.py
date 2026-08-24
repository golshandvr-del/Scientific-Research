# -*- coding: utf-8 -*-
"""
S844 — شوک استانداردشدهٔ تأییدشده (Confirmed Shock) به سبک رابرت انگل
=======================================================================
پیش‌ثبت: results/S844_PREREG_engle_confirmed_shock.md (کامیت d80c24a8 پیش از اجرا)
مسیر تعدد: C — جستجو فقط نیمهٔ اول؛ یک آزمون منجمد per-TF روی کل داده.

قاعده: |z_t| ≥ z_thr و sign(r_{t+1})==sign(z_t) ⇒ سیگنال روی کندل t+1 بسته
می‌شود ⇒ queue_frozen ورود را در open کندل t+2 می‌گذارد (صفر نشت).
فقط follow (توجیه پیش‌ثبت: S840/S842/S950).
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

OUT = 'results/_scan_S844'
SEED = 844

Z_GRID = (1.272, 1.618, 2.058)
SLK_GRID = (1.0, 1.272, 1.618)
RR_GRID = (1.0, 1.272, 1.618)
N_GRID = len(Z_GRID) * len(SLK_GRID) * len(RR_GRID)      # = 27


def confirmed_signals(z, r, atr, z_thr, warmup, lo=None, hi=None):
    """سیگنال = کندل تأیید (t+1). شوک در t، تأیید r_{t+1} هم‌جهت.

    خروجی اندیس‌های t+1 و ماسک long. atr/validity روی t+1 سنجیده می‌شود
    (ورود در open t+2 توسط queue_frozen)."""
    n = len(z)
    up = np.isfinite(z) & (z >= z_thr)
    dn = np.isfinite(z) & (z <= -z_thr)
    shock = np.zeros(n, dtype=np.int8)
    shock[up] = 1
    shock[dn] = -1
    conf = np.zeros(n, dtype=np.int8)
    # کندل t+1: بازده r[t+1] هم‌جهت شوک t
    conf[1:] = np.where((shock[:-1] == 1) & (r[1:] > 0), 1,
                        np.where((shock[:-1] == -1) & (r[1:] < 0), -1, 0))
    valid = np.isfinite(atr) & (atr > 0)
    sig_m = (conf != 0) & valid
    idx = np.where(sig_m)[0]
    idx = idx[idx >= warmup]
    if lo is not None:
        idx = idx[idx >= lo]
    if hi is not None:
        idx = idx[idx < hi]
    if len(idx) == 0:
        return idx, np.zeros(0, bool)
    return idx, conf[idx] == 1


def discover_is(df, z, r, atr, split, warmup, hold, verbose=True):
    c = cost_pip()
    hi = split - hold - 2
    rows = []
    for z_thr in Z_GRID:
        sig, isl = confirmed_signals(z, r, atr, z_thr, warmup, hi=hi)
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
                rows.append(dict(z_thr=z_thr, sl_k=slk, rr=rr,
                                 n=st['n'], wr=round(st['wr'], 2),
                                 exp=round(st['exp'], 4),
                                 pf=round(st['pf'], 3),
                                 sl_med=round(sl_med, 2),
                                 tp_med=round(tp_med, 2), be=round(be, 2),
                                 passes_be=bool(st['wr'] > be)))
    ok = [x for x in rows if x['passes_be']]
    best = max(ok, key=lambda x: x['exp']) if ok else None
    if verbose:
        print(f"    IS grid: {len(rows)}/{N_GRID} combos n>=30 · "
              f"{len(ok)} pass robust-BE", flush=True)
        if best:
            print(f"    IS WINNER: z>={best['z_thr']} sl_k={best['sl_k']} "
                  f"rr={best['rr']} → n={best['n']} WR={best['wr']}% "
                  f"exp={best['exp']:+.3f}pip", flush=True)
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

    print(f"\n{'=' * 88}\n=== S844 Confirmed-Shock :: {ASSET}-{tf} "
          f"(bars={n:,} span={d.get('span_years', '?')}y) ===", flush=True)
    print(f"    hold={hold} split@{split:,} warmup={warmup} "
          f"cost={c:.2f}pip grid={N_GRID} follow-only+confirm", flush=True)

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
    z, r = ewma_z(cl)
    del h, l

    rows, best = discover_is(df, z, r, atr, split, warmup, hold, verbose)
    out['is_grid'] = rows
    if best is None:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'NO_IS_CANDIDATE'
        print(f"    → {tf}: UNPROVEN — no IS candidate; OOS untouched.",
              flush=True)
        _save(tf, out)
        return out
    out['is_winner'] = best

    sig, isl = confirmed_signals(z, r, atr, best['z_thr'], warmup)
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
          f"n_OOS={n_oos} WR={st['wr']:.2f}% exp={st['exp']:+.3f}pip",
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
                       tp_med=round(tp_med, 2))
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
    print("\nS844 scan complete.", flush=True)


if __name__ == '__main__':
    main()
