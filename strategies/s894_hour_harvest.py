#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S894 — برداشتِ لبهٔ تقویمیِ ساعتِ پایانی (مسیرِ C، نالِ کانونی).

قرارداد: results/S894_PREREG_CalendarHourHarvest_Xauusd_MTF.md (کامیت e083e7ec)
  - رویداد: اولین کندلِ ساعتِ H∈{21,22,23}؛ فقط لانگ.
  - هندسه: A(1.5ATR/RR1.5) · B(SL=TP=3ATR) · C(TP=1ATR,SL=2.058ATR)؛ hold=4h.
  - فیلتر: none · drift(24h) · calm(q70 رولینگِ علّیِ ATR100) · drift+calm.
  - اهلیت: n_IS≥100 و exp@2×cost_IS>0؛ قفل با t_pnl. بدونِ اهل ⇒ UNPROVEN.
  - n_trials=1488 · نالِ کانونی: ۳ قرعهٔ uncond {894,1894,2894} + perm K=500 seed=894.

اجرا:  python3 strategies/s894_hour_harvest.py H2
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
HOLD_HOURS = 4
HOURS = (21, 22, 23)
N_TRIALS = 1488
PERM_K = 500
PERM_SEED = 894
UNC_SEEDS = (894, 1894, 2894)
OUT = 'results/_s894'
PREREG = 'e083e7ec'

TF_MIN = {'M1':1,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,
          'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H6':360,'H8':480,
          'H12':720,'D1':1440,'W1':10080,'MN1':43200}


def atr_series(df, n=100):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean()


def hour_first_mask(times, H):
    hrs = pd.to_datetime(times, unit='s').hour.values
    is_h = hrs == H
    prev = np.roll(is_h, 1); prev[0] = False
    return is_h & ~prev


def build_filters(df, tf, atr):
    """فیلترهای علّی — همه با مقادیرِ تا t−1."""
    N = len(df)
    c = df['close'].values
    b24 = max(2, int(1440 / TF_MIN[tf]))
    # drift: close[t−1] > close[t−1−b24]
    c1 = np.roll(c, 1)
    cb = np.roll(c, 1 + b24)
    drift = c1 > cb
    drift[:1 + b24] = False
    # calm: ATR100[t−1] < چندکِ q70 رولینگِ علّی روی 5000 کندل (min 500)
    a1 = atr.shift(1)
    q70 = a1.rolling(5000, min_periods=500).quantile(0.70)
    calm = (a1 < q70).values
    calm[np.isnan(a1.values) | np.isnan(q70.values)] = False
    return {'none': np.ones(N, dtype=bool), 'drift': drift,
            'calm': calm, 'drift+calm': drift & calm}


def geometries(atr_med_pip):
    return {
        'A': dict(sl=1.5 * atr_med_pip, tp=2.25 * atr_med_pip),
        'B': dict(sl=3.0 * atr_med_pip, tp=3.0 * atr_med_pip),
        'C': dict(sl=2.058 * atr_med_pip, tp=1.0 * atr_med_pip),
    }


def simulate(df, ls, sl_pip, tp_pip, hold):
    z = np.zeros(len(df), dtype=bool)
    return se.simulate_trades(df, ls, z, sl_pip=sl_pip, tp_pip=tp_pip,
                              asset=ASSET, max_hold=hold, allow_overlap=False)


def canonical_null(df, sl_pip, tp_pip, hold, n_sig):
    """نالِ کانونیِ هندسه-همتا (قانونِ دهه از S893) — فقط لانگ."""
    N = len(df)
    lo, hi = 200, N - hold - 2
    size = min(20000, N // max(hold, 1))
    unc_rows = []
    for seed in UNC_SEEDS:
        rng = np.random.default_rng(seed)
        pos = rng.choice(np.arange(lo, hi), size=min(size, hi - lo), replace=False)
        sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
        tr = simulate(df, sig, sl_pip, tp_pip, hold)
        wr = 100.0 * float((tr['outcome'] == 'win').mean()) if len(tr) else None
        unc_rows.append((seed, wr, len(tr)))
        del tr; gc.collect()
    uncond_wr = max(r[1] for r in unc_rows if r[1] is not None)
    rng = np.random.default_rng(PERM_SEED)
    wrs = []
    for i in range(PERM_K):
        pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
        sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
        tr = simulate(df, sig, sl_pip, tp_pip, hold)
        if tr is not None and len(tr) >= 30:
            wrs.append(100.0 * float((tr['outcome'] == 'win').mean()))
        del tr
        if (i + 1) % 100 == 0:
            gc.collect(); print(f"  perm {i+1}/{PERM_K} …", flush=True)
    a = np.asarray(wrs, float)
    perm = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)),
                max=float(a.max()), k=int(len(a)))
    side = dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
                perm_sd=perm['sd'], perm_max=perm['max'], perm_k=perm['k'])
    return {'long': dict(side), 'short': dict(side)}, unc_rows, perm


def run_tf(tf):
    print('=' * 72)
    print(f"S894 Calendar-Hour Harvest · XAUUSD-{tf} (prereg {PREREG})")
    print('=' * 72, flush=True)
    if TF_MIN[tf] >= 1440:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE',
                       reason='hour-of-day concept undefined at >=D1'))
        print("no hour structure → INCOMPLETE"); return
    hold = max(2, math.ceil(HOLD_HOURS * 60 / TF_MIN[tf]))
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    if 'volume' in df.columns:
        df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df)
    split = int(N * 0.70)
    times = df['time'].values
    print(f"src={src}  bars={N}  split={split}  hold={hold}", flush=True)

    atr = atr_series(df, 100)
    atr_med_pip = float(np.nanmedian(atr.values[:split])) / PIP
    geos = geometries(atr_med_pip)
    filts = build_filters(df, tf, atr)
    del atr; gc.collect()
    print(f"ATRmed={atr_med_pip:.2f}pip  geos: " +
          " ".join(f"{k}(SL={v['sl']:.1f},TP={v['tp']:.1f})" for k, v in geos.items()),
          flush=True)

    ev_by_H = {H: hour_first_mask(times, H) for H in HOURS}
    dfe = df.iloc[:split]

    # ---------- کشف: فقط ۷۰٪ اول ----------
    best = None
    for H in HOURS:
        for gname, g in geos.items():
            for fname, fmask in filts.items():
                sig = ev_by_H[H] & fmask
                sig_e = sig[:split]
                if sig_e.sum() < 60:
                    continue
                tr = simulate(dfe, sig_e, g['sl'], g['tp'], hold)
                if tr is None or len(tr) < 100:
                    del tr; continue
                pnl = tr['pnl_pip'].values
                n = len(pnl); exp = float(pnl.mean())
                exp2x = exp - COST_PIP
                sd = float(pnl.std(ddof=1))
                t = exp / sd * math.sqrt(n) if sd > 0 else 0.0
                eligible = exp2x > 0
                tag = 'ELIGIBLE' if eligible else '        '
                if eligible and (best is None or t > best['t_pnl']):
                    best = dict(H=H, geo=gname, filt=fname, t_pnl=round(t, 3),
                                is_n=n, is_wr=round(100 * float((pnl > 0).mean()), 2),
                                is_exp=round(exp, 3), is_exp2x=round(exp2x, 3),
                                sl=g['sl'], tp=g['tp'])
                    print(f"  {tag} H={H} {gname}/{fname:<10} n={n:>5} "
                          f"exp={exp:+7.2f} exp2x={exp2x:+7.2f} t={t:+.2f}  ← best",
                          flush=True)
                del tr; gc.collect()

    if best is None:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='UNPROVEN',
                       reason='no eligible config in discovery (n>=100 & exp@2x>0) '
                              '- holdout untouched per prereg stop rule', src=src,
                       bars=N, split=split, hold=hold,
                       atr_med_pip=round(atr_med_pip, 2)))
        print("NO ELIGIBLE CONFIG → UNPROVEN (holdout untouched)"); return

    print(f"\nLOCKED: H={best['H']} geo={best['geo']} filt={best['filt']} "
          f"t={best['t_pnl']}  IS: n={best['is_n']} WR={best['is_wr']} "
          f"exp2x={best['is_exp2x']}", flush=True)

    # ---------- شلیکِ نهایی: یک بار، کل داده ----------
    sig = ev_by_H[best['H']] & filts[best['filt']]
    n_sig = int(sig.sum())
    tr = simulate(df, sig, best['sl'], best['tp'], hold)
    null, unc_rows, perm = canonical_null(df, best['sl'], best['tp'], hold, n_sig)
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=best['sl'], tp_pip=best['tp'],
                          bar_time=times, null=null, n_trials=N_TRIALS,
                          split_bar=split, close=df['close'].values)
    n_all = len(tr); wr_all = 100.0 * float((tr['outcome'] == 'win').mean())
    hm = tr['entry_bar'].values >= split
    oos_n = int(hm.sum())
    oos_wr = (100.0 * float((tr.loc[hm, 'outcome'] == 'win').mean())
              if oos_n else None)
    ref = max(null['long']['uncond_wr'], null['long']['perm_mean'])
    print(f"\nFULL: n={n_all} WR={wr_all:.2f}  OOS: n={oos_n} WR={oos_wr}")
    print(f"geo-lift={wr_all-ref:+.2f}pp  VERDICT: {r.get('verdict')} "
          f"score={r.get('rqs2_score')}")
    print(f"gates: {r.get('gates')}", flush=True)

    _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, src=src, bars=N,
                   split=split, hold=hold, atr_med_pip=round(atr_med_pip, 2),
                   locked=best, n=n_all, wr=round(wr_all, 2), n_sig=n_sig,
                   net_pip=round(float(tr['pnl_pip'].sum()), 1),
                   oos_n=oos_n, oos_wr=round(oos_wr, 2) if oos_wr else None,
                   uncond_draws=unc_rows, perm=perm, null=null,
                   lift_geo_pp=round(wr_all - ref, 2), rqs2=r))
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


def _save(tf, res):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)
    print(f"saved → {OUT}/rqs2_XAUUSD-{tf}.json", flush=True)


if __name__ == '__main__':
    run_tf(sys.argv[1] if len(sys.argv) > 1 else 'H2')
