#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S896 — رکورد پس از خشکسالی (Record after Drought) · مسیر C · نالِ کانونی.

قرارداد: results/S896_PREREG_RecordAfterDrought_Xauusd_MTF.md (کامیت d7338160)
  - رکورد: nh = close[i] > max(close[i-90..i-1]) ؛ لبهٔ تازه nh & ~nh[i-1]
    آینه: nl = close[i] < min(close[i-90..i-1])
  - خشکسالی: فاصله از آخرین لبهٔ هم‌جهت >= D ، D in {30,90,180}
  - جهت follow · ورود open کندل بعد · براکت شناور ATR21[i-1]:
      G1: SL=1.272 TP=2.058 (S965) · G2: SL=1.5 TP=2.25 (S526)
  - max_hold=16 · allow_overlap=False · 12 config/کارت · n_trials=228
  - اهلیت: n_IS>=100 و exp@2xcost_IS>0 · قفل با t_pnl · بدون اهل ⇒ UNPROVEN
  - نال کانونی: uncond {896,1896,2896} (ref=max) + perm K=500 seed=896
  - P1 تشخیصی (IS): lift قفل‌شده در برابر لبهٔ رکورد بی‌قید (D=0) با همان هندسه

اجرا: python3 strategies/s896_record_drought.py H8
"""
import sys, os, json, gc, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'
PIP = 0.1
COST_PIP = 3.3
N_TRIALS = 228
PERM_K = 500
PERM_SEED = 896
UNC_SEEDS = (896, 1896, 2896)
OUT = 'results/_s896'
PREREG = 'd7338160'
LOOK = 90
HOLD = 16
DROUGHTS = (30, 90, 180)
GEOS = {'G1': (1.272, 2.058), 'G2': (1.5, 2.25)}

TF_MIN = {'M1':1,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,
          'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H6':360,'H8':480,
          'H12':720,'D1':1440,'W1':10080,'MN1':43200}


def atr_series(df, n=21):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).rolling(n).mean().shift(1).values   # ATR[i-1] علّی
    return a


def record_edges(close):
    """لبهٔ تازهٔ رکورد سقف/کف ۹۰کندلی (فقط با اطلاعات <= i)."""
    s = pd.Series(close)
    pmax = s.rolling(LOOK).max().shift(1).values
    pmin = s.rolling(LOOK).min().shift(1).values
    nh = close > pmax
    nl = close < pmin
    nh = np.nan_to_num(nh, nan=False).astype(bool)
    nl = np.nan_to_num(nl, nan=False).astype(bool)
    eh = nh & ~np.roll(nh, 1); eh[0] = False
    el = nl & ~np.roll(nl, 1); el[0] = False
    return eh, el


def drought_mask(edge, D):
    """لبه‌هایی که پیش از آن‌ها >= D کندل هیچ لبهٔ هم‌جهت نبوده."""
    idx = np.flatnonzero(edge)
    out = np.zeros_like(edge)
    prev = -10**9
    for i in idx:
        if i - prev >= D:
            out[i] = True
        prev = i
    return out


def simulate(df, ls, ss, sl_arr, tp_arr):
    return se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset=ASSET,
                              max_hold=HOLD, allow_overlap=False)


def stats(tr):
    pnl = tr['pnl_pip'].values
    n = len(pnl); exp = float(pnl.mean()); sd = float(pnl.std(ddof=1))
    t = exp / sd * math.sqrt(n) if sd > 0 else 0.0
    wr = 100.0 * float((tr['outcome'] == 'win').mean())
    return n, exp, exp - COST_PIP, t, wr


def canonical_null(df, side, sl_arr, tp_arr, n_sig):
    N = len(df)
    lo, hi = LOOK + 25, N - HOLD - 2
    size = min(20000, N // HOLD)
    z = np.zeros(N, dtype=bool)
    unc_rows = []
    for seed in UNC_SEEDS:
        rng = np.random.default_rng(seed)
        pos = rng.choice(np.arange(lo, hi), size=min(size, hi - lo), replace=False)
        sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
        tr = simulate(df, sig if side == 'long' else z,
                      sig if side == 'short' else z, sl_arr, tp_arr)
        wr = 100.0 * float((tr['outcome'] == 'win').mean()) if len(tr) else None
        unc_rows.append((seed, wr, len(tr)))
        del tr; gc.collect()
    uncond_wr = max(r[1] for r in unc_rows if r[1] is not None)
    rng = np.random.default_rng(PERM_SEED)
    wrs = []
    for i in range(PERM_K):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
        tr = simulate(df, sig if side == 'long' else z,
                      sig if side == 'short' else z, sl_arr, tp_arr)
        if tr is not None and len(tr) >= 30:
            wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
        del tr
        if (i + 1) % 100 == 0:
            gc.collect(); print(f"  perm {i+1}/{PERM_K} …", flush=True)
    a = np.asarray(wrs, float)
    perm = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)),
                max=float(a.max()), k=int(len(a)))
    sd_ = dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
               perm_sd=perm['sd'], perm_max=perm['max'], perm_k=perm['k'])
    return {'long': dict(sd_), 'short': dict(sd_)}, unc_rows, perm


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f:
        json.dump(obj, f, indent=1, default=str)


def run_tf(tf):
    print('=' * 72)
    print(f"S896 Record-after-Drought · XAUUSD-{tf} (prereg {PREREG})")
    print('=' * 72, flush=True)
    if TF_MIN[tf] >= 10080:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE',
                       reason='90-bar record at >=W1 spans ~2y; n structurally < 100 (pre-declared)'))
        print("pre-declared INCOMPLETE"); return
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    if 'volume' in df.columns:
        df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df); split = int(N * 0.70)
    times = df['time'].values
    close = df['close'].values
    print(f"src={src}  bars={N}  split={split}", flush=True)

    atr_pip = atr_series(df, 21) / PIP
    atr_pip = np.nan_to_num(atr_pip, nan=np.nanmedian(atr_pip))
    eh, el = record_edges(close)
    z = np.zeros(N, dtype=bool)
    print(f"record edges: high={eh.sum()} low={el.sum()}  ATR21med={np.median(atr_pip):.1f}pip", flush=True)

    dfe = df.iloc[:split]
    n_ev = {}
    best = None
    diag_base = {}
    for gname, (ks, kt) in GEOS.items():
        sl_arr = ks * atr_pip; tp_arr = kt * atr_pip
        for side, edge in (('long', eh), ('short', el)):
            # P1 diagnostic base: D=0 (unconditioned record edge), IS only
            tr0 = simulate(dfe, edge[:split] if side == 'long' else z[:split],
                           edge[:split] if side == 'short' else z[:split],
                           sl_arr[:split], tp_arr[:split])
            if tr0 is not None and len(tr0) >= 30:
                n0, e0, _, _, w0 = stats(tr0)
                diag_base[f'{side}/{gname}'] = dict(n=n0, wr=round(w0, 2), exp=round(e0, 2))
            del tr0
            for D in DROUGHTS:
                sig = drought_mask(edge, D)
                key = f'{side}/D{D}'
                n_ev[key] = int(sig.sum())
                sig_e = sig[:split]
                if sig_e.sum() < 60:
                    continue
                tr = simulate(dfe, sig_e if side == 'long' else z[:split],
                              sig_e if side == 'short' else z[:split],
                              sl_arr[:split], tp_arr[:split])
                if tr is None or len(tr) < 100:
                    del tr; continue
                n, exp, exp2x, t, wr = stats(tr)
                eligible = exp2x > 0
                print(f"  {'ELIGIBLE' if eligible else '        '} {side:<5}/D{D:<3}/{gname} "
                      f"n={n:>4} WR={wr:5.2f} exp={exp:+8.2f} exp2x={exp2x:+8.2f} t={t:+.2f}", flush=True)
                if eligible and (best is None or t > best['t_pnl']):
                    best = dict(side=side, D=D, geo=gname, ks=ks, kt=kt, t_pnl=round(t, 3),
                                is_n=n, is_wr=round(wr, 2), is_exp=round(exp, 3),
                                is_exp2x=round(exp2x, 3))
                del tr; gc.collect()

    if best is None:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='UNPROVEN',
                       reason='no eligible config in discovery (n>=100 & exp@2x>0) - holdout untouched',
                       src=src, bars=N, split=split, events=n_ev, p1_base_is=diag_base))
        print("NO ELIGIBLE CONFIG → UNPROVEN (holdout untouched)"); return

    base = diag_base.get(f"{best['side']}/{best['geo']}", {})
    p1 = dict(base_is=base, locked_is_wr=best['is_wr'],
              passes=bool(base and best['is_wr'] > base['wr']))
    print(f"\nLOCKED: {best['side']}/D{best['D']}/{best['geo']} t={best['t_pnl']} "
          f"IS n={best['is_n']} WR={best['is_wr']} exp2x={best['is_exp2x']}  P1 base WR={base.get('wr')} → {p1['passes']}", flush=True)

    sl_arr = best['ks'] * atr_pip; tp_arr = best['kt'] * atr_pip
    sig = drought_mask(eh if best['side'] == 'long' else el, best['D'])
    n_sig = int(sig.sum())
    tr = simulate(df, sig if best['side'] == 'long' else z,
                  sig if best['side'] == 'short' else z, sl_arr, tp_arr)
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = float(np.median(tr['tp_pip'].values))
    null, unc_rows, perm = canonical_null(df, best['side'], sl_arr, tp_arr, n_sig)
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=times,
                          null=null, n_trials=N_TRIALS, split_bar=split, close=close)
    n_all, _, _, _, wr_all = stats(tr)
    hm = tr['entry_bar'].values >= split
    oos_n = int(hm.sum())
    oos_wr = 100.0 * float((tr.loc[hm, 'outcome'] == 'win').mean()) if oos_n else None
    ref = max(null['long']['uncond_wr'], null['long']['perm_mean'])
    print(f"\nFULL: n={n_all} WR={wr_all:.2f}  OOS: n={oos_n} WR={oos_wr}")
    print(f"geo-lift={wr_all-ref:+.2f}pp  VERDICT: {r.get('verdict')} score={r.get('rqs2_score')}")
    print(f"gates: {r.get('gates')}", flush=True)
    _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, src=src, bars=N, split=split,
                   events=n_ev, locked=best, p1=p1, sl_pip_med=round(sl_med, 2),
                   tp_pip_med=round(tp_med, 2), n=n_all, wr=round(wr_all, 2), n_sig=n_sig,
                   net_pip=round(float(tr['pnl_pip'].sum()), 1), oos_n=oos_n,
                   oos_wr=round(oos_wr, 2) if oos_wr else None, uncond_draws=unc_rows,
                   perm=perm, null=null, lift_geo_pp=round(wr_all - ref, 2), rqs2=r))
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


if __name__ == '__main__':
    run_tf(sys.argv[1])
