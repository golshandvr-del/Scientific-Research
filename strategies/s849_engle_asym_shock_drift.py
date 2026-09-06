# -*- coding: utf-8 -*-
"""
S849 — شوک نامتقارن انگل–انگ × درفت (GJR-style news impact) به سبک رابرت انگل
===============================================================================
پیش‌ثبت: results/S849_PREREG_engle_asymmetric_shock_drift.md (کامیت 5c0b0fcb)
مسیر تعدد: C — جستجو فقط نیمهٔ اول؛ یک آزمون منجمد per-TF روی کل داده.

LONG : z_t ≥ z_up  و close[t] > close[t−K]
SHORT: z_t ≤ −z_dn و close[t] < close[t−K]
follow · ورود open t+1 · rr=1.0 منجمد · بازوهای تشخیصی P1–P3 فقط روی IS.
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

OUT = 'results/_scan_S849'
SEED = 849

Z_GRID = (2.058, 2.618)                 # برای z_up و z_dn مستقل
K_GRID = (89, 144, 233)
SLK_GRID = (1.272, 1.618)
RR_FIXED = 1.0
N_GRID = len(Z_GRID) ** 2 * len(K_GRID) * len(SLK_GRID)     # = 24


def asym_signals(z, close, atr, z_up, z_dn, K, warmup, lo=None, hi=None,
                 drift='aligned'):
    """
    drift='aligned' : هم‌جهت با درفت K (لایهٔ اصلی)
    drift='none'    : بی‌درفت (تشخیصی P1 پایه)
    drift='counter' : خلاف درفت (تشخیصی P3)
    """
    n = len(z)
    valid = np.isfinite(atr) & (atr > 0) & np.isfinite(z)
    d = np.zeros(n)
    d[K:] = close[K:] - close[:-K]
    long_m = valid & (z >= z_up)
    short_m = valid & (z <= -z_dn)
    if drift == 'aligned':
        long_m &= d > 0
        short_m &= d < 0
    elif drift == 'counter':
        long_m &= d < 0
        short_m &= d > 0
    m = long_m | short_m
    idx = np.where(m)[0]
    idx = idx[idx >= max(warmup, K + 1)]
    if lo is not None:
        idx = idx[idx >= lo]
    if hi is not None:
        idx = idx[idx < hi]
    if len(idx) == 0:
        return idx, np.zeros(0, bool)
    return idx, long_m[idx]


def _card(df, sig, isl, atr, slk, hold):
    if len(sig) < 5:
        return None
    st = queue_frozen(df, sig, isl, slk * atr[sig], hold, RR_FIXED)
    if st is None or st['n'] < 5:
        return None
    return dict(n=st['n'], wr=round(st['wr'], 2), exp=round(st['exp'], 4),
                pf=round(st['pf'], 3))


def _side_wr(df, sig, isl, atr, slk, hold):
    """WR جداگانهٔ لانگ/شورت با همان هندسه (برای lift سمتی روی IS)."""
    out = {}
    for name, mask in (('long', isl), ('short', ~isl)):
        s = sig[mask]
        if len(s) < 5:
            out[name] = None
            continue
        st = queue_frozen(df, s, np.full(len(s), name == 'long'),
                          slk * atr[s], hold, RR_FIXED)
        out[name] = None if st is None else dict(n=st['n'],
                                                 wr=round(st['wr'], 2))
    return out


def discover_is(df, z, cl, atr, split, warmup, hold, verbose=True):
    c = cost_pip()
    hi = split - hold - 2
    rows = []
    for z_up in Z_GRID:
        for z_dn in Z_GRID:
            for K in K_GRID:
                sig, isl = asym_signals(z, cl, atr, z_up, z_dn, K, warmup,
                                        hi=hi)
                if len(sig) < MIN_N_IS:
                    continue
                for slk in SLK_GRID:
                    st = queue_frozen(df, sig, isl, slk * atr[sig], hold,
                                      RR_FIXED)
                    if st is None or st['n'] < MIN_N_IS:
                        continue
                    sl_med = float(np.median(st['sl_pip']))
                    tp_med = float(np.median(st['tp_pip']))
                    be = 100.0 * (sl_med + 2.0 * c) / (sl_med + tp_med)
                    rows.append(dict(z_up=z_up, z_dn=z_dn, K=K, sl_k=slk,
                                     rr=RR_FIXED, n=st['n'],
                                     wr=round(st['wr'], 2),
                                     exp=round(st['exp'], 4),
                                     pf=round(st['pf'], 3),
                                     sl_med=round(sl_med, 2),
                                     tp_med=round(tp_med, 2),
                                     be=round(be, 2),
                                     passes_be=bool(st['wr'] > be)))
    ok = [x for x in rows if x['passes_be']]
    best = max(ok, key=lambda x: x['exp']) if ok else None
    if verbose:
        print(f"    IS grid: {len(rows)}/{N_GRID} combos n>=30 · "
              f"{len(ok)} pass robust-BE", flush=True)
        if best:
            print(f"    IS WINNER: z_up={best['z_up']} z_dn={best['z_dn']} "
                  f"K={best['K']} sl_k={best['sl_k']} → n={best['n']} "
                  f"WR={best['wr']}% exp={best['exp']:+.3f}pip", flush=True)
    return rows, best


def diagnostics_is(df, z, cl, atr, split, warmup, hold, best, verbose=True):
    """P1–P3 روی IS. نول سمتی = WR غیرشرطی همان سمت روی IS (زیرنمونهٔ منظم)."""
    hi = split - hold - 2
    slk, K = best['sl_k'], best['K']
    out = {}
    # نول سمتی IS: ورود غیرشرطی روی هر kامین کندل معتبر (≤ 4000 ورود per side)
    valid = np.where(np.isfinite(z) & np.isfinite(atr) & (atr > 0))[0]
    valid = valid[(valid >= max(warmup, K + 1)) & (valid < hi)]
    step = max(1, len(valid) // 4000)
    sub = valid[::step]
    null = {}
    for name, isl_val in (('long', True), ('short', False)):
        st = queue_frozen(df, sub, np.full(len(sub), isl_val), slk * atr[sub],
                          hold, RR_FIXED)
        null[name] = None if st is None else round(st['wr'], 2)
    out['null_is'] = null

    arms = {}
    for label, dr in (('base_sym', 'none'), ('aligned_sym', 'aligned'),
                      ('counter_sym', 'counter')):
        sig, isl = asym_signals(z, cl, atr, 2.618, 2.618, K, warmup, hi=hi,
                                drift=dr)
        arms[label] = dict(card=_card(df, sig, isl, atr, slk, hold),
                           sides=_side_wr(df, sig, isl, atr, slk, hold))
    out['arms'] = arms

    def lift(label):
        s = arms[label]['sides']
        vals = []
        for side in ('long', 'short'):
            if s.get(side) and null.get(side) is not None:
                vals.append((s[side]['wr'] - null[side], s[side]['n']))
        if not vals:
            return None
        tot = sum(n for _, n in vals)
        return round(sum(l * n for l, n in vals) / tot, 2)

    out['lift_base'] = lift('base_sym')
    out['lift_aligned'] = lift('aligned_sym')
    p1 = (out['lift_aligned'] is not None and out['lift_base'] is not None
          and out['lift_aligned'] > out['lift_base'])
    s = arms['base_sym']['sides']
    side_gap = None
    if s.get('long') and s.get('short') and all(
            null.get(k) is not None for k in ('long', 'short')):
        side_gap = round((s['long']['wr'] - null['long'])
                         - (s['short']['wr'] - null['short']), 2)
    out['side_lift_gap_base'] = side_gap
    p2 = (best['z_up'] != best['z_dn']) or (side_gap is not None
                                            and abs(side_gap) < 3.0)
    ca = arms['counter_sym']['card']
    al = arms['aligned_sym']['card']
    p3 = bool(ca and al and ca['wr'] < al['wr'])
    out['P1_drift_adds_lift'] = bool(p1)
    out['P2_asymmetry_consistent'] = bool(p2)
    out['P3_counter_worse'] = p3
    if verbose:
        print(f"    DIAG(IS) null={null} | base={arms['base_sym']['card']} "
              f"lift={out['lift_base']} | aligned={al} "
              f"lift={out['lift_aligned']} | counter={ca} | "
              f"side_gap={side_gap}", flush=True)
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
    df = fd.as_dataframe(d)
    n = len(df)
    warmup = 250 if n >= 5000 else max(60, n // 10)
    split = int(n * SPLIT_FRAC)
    c = cost_pip()

    print(f"\n{'=' * 88}\n=== S849 Asym-Shock×Drift :: {ASSET}-{tf} "
          f"(bars={n:,} span={d.get('span_years', '?')}y) ===", flush=True)
    print(f"    hold={hold} split@{split:,} warmup={warmup} "
          f"cost={c:.2f}pip grid={N_GRID} follow rr=1.0", flush=True)

    out = dict(tf=tf, asset=ASSET, bars=n, src=str(d.get('src')),
               span_years=d.get('span_years'), hold=hold, split_bar=split,
               warmup=warmup, grid=N_GRID)
    if n < warmup + 4 * hold + 100 + max(K_GRID):
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

    rows, best = discover_is(df, z, cl, atr, split, warmup, hold, verbose)
    out['is_grid'] = rows
    if best is None:
        out['verdict'] = 'UNPROVEN'
        out['reason'] = 'NO_IS_CANDIDATE'
        print(f"    → {tf}: UNPROVEN — no IS candidate; OOS untouched.",
              flush=True)
        _save(tf, out)
        return out
    out['is_winner'] = best
    out['diag_is'] = diagnostics_is(df, z, cl, atr, split, warmup, hold,
                                    best, verbose)

    sig, isl = asym_signals(z, cl, atr, best['z_up'], best['z_dn'], best['K'],
                            warmup)
    st = queue_frozen(df, sig, isl, best['sl_k'] * atr[sig], hold, RR_FIXED)
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
    null = build_null_oos(df, atr, valid_oos, best['sl_k'], RR_FIXED, hold,
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
    print("\nS849 scan complete.", flush=True)


if __name__ == '__main__':
    main()
