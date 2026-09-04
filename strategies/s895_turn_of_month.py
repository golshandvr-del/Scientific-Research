#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S895 — جریانِ نهادیِ گردشِ ماه (Turn-of-Month Flow) · مسیر C · نالِ کانونی.

قرارداد: results/S895_PREREG_TurnOfMonthFlow_Xauusd_MTF.md (کامیت ee86cd6c)
  - رویداد: اولین کندلِ روزِ معاملاتیِ عضوِ پنجرهٔ TOM.
    شکستِ روز: gap_sec > max(1800, 1.5×TF_sec) — ضدِ DST (رویهٔ S560).
    برچسب: TD0=آخرین روزِ معاملاتیِ ماه، TD−1=یکی‌مانده‌به‌آخر، TD+1..TD+3=سه روزِ اول.
  - پنجرهٔ روز: FULL={−1,0,+1,+2,+3} · LATE={−1,0,+1} · EARLY={+1,+2,+3}
  - زمینهٔ ساعت: ALL (اولین کندلِ روز) · ASIA (اولین کندلِ ساعت∈[1..12] همان روز)
  - هندسه: SL=TP=k×ATR(100)med، k∈{1.0,1.5,2.058} · فقط LONG
  - hold: خروجِ زمانی، سقف = bars(24h)
  - اهلیت: n_IS≥100 و exp@2×cost_IS>0 · قفل با t_pnl · بدونِ اهل ⇒ UNPROVEN
  - n_trials=288 · نالِ کانونی: uncond {895,1895,2895} + perm K=500 seed=895

اجرا:  python3 strategies/s895_turn_of_month.py H2
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
N_TRIALS = 288
PERM_K = 500
PERM_SEED = 895
UNC_SEEDS = (895, 1895, 2895)
OUT = 'results/_s895'
PREREG = 'ee86cd6c'

TF_MIN = {'M1':1,'M3':3,'M4':4,'M5':5,'M6':6,'M10':10,'M12':12,'M15':15,
          'M20':20,'M30':30,'H1':60,'H2':120,'H3':180,'H6':360,'H8':480,
          'H12':720,'D1':1440,'W1':10080,'MN1':43200}

WINDOWS = {'FULL': {-1, 0, 1, 2, 3},
           'LATE': {-1, 0, 1},
           'EARLY': {1, 2, 3}}
KS = (1.0, 1.5, 2.058)


def atr_series(df, n=100):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean()


def trading_days(times, tf):
    """شناسهٔ روزِ معاملاتی + برچسبِ TOM هر روز.

    شکستِ روز: gap_sec > max(1800, 1.5×TF_sec)  (S560 anti-DST).
    """
    tf_sec = TF_MIN[tf] * 60
    gap = np.diff(times, prepend=times[0])
    day_start = gap > max(1800, 1.5 * tf_sec)
    day_start[0] = True
    first_idx = np.flatnonzero(day_start)
    dts = pd.to_datetime(times[first_idx], unit='s')
    mkey = dts.year.values * 12 + dts.month.values
    n_days = len(first_idx)
    tag = {}
    d = 0
    while d < n_days:
        m = mkey[d]
        e = d
        while e < n_days and mkey[e] == m:
            e += 1
        month_days = list(range(d, e))
        L = len(month_days)
        for j, td in enumerate(month_days[:3]):   # TD+1..TD+3
            tag[td] = j + 1
        if L >= 5:
            tag[month_days[-1]] = 0               # TD0
            tag[month_days[-2]] = -1              # TD−1
        elif L == 4:
            tag[month_days[-1]] = 0
        d = e
    return tag, first_idx


def build_signals(times, tf):
    """ماسک‌های سیگنال برای ۳ پنجرهٔ روز × ۲ زمینهٔ ساعت."""
    N = len(times)
    tag, first_idx = trading_days(times, tf)
    hrs = pd.to_datetime(times, unit='s').hour.values
    n_days = len(first_idx)
    day_end = np.append(first_idx[1:], N)
    asia_ok = (hrs >= 1) & (hrs <= 12)
    asia_first = np.full(n_days, -1, dtype=np.int64)
    for d in range(n_days):
        s, e = first_idx[d], day_end[d]
        w = np.flatnonzero(asia_ok[s:e])
        if len(w):
            asia_first[d] = s + w[0]
    sigs = {}
    for wname, wset in WINDOWS.items():
        days_in = [d for d in range(n_days) if tag.get(d) in wset]
        m_all = np.zeros(N, dtype=bool)
        m_asia = np.zeros(N, dtype=bool)
        for d in days_in:
            m_all[first_idx[d]] = True
            if asia_first[d] >= 0:
                m_asia[asia_first[d]] = True
        sigs[(wname, 'ALL')] = m_all
        sigs[(wname, 'ASIA')] = m_asia
    return sigs


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


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w') as f:
        json.dump(obj, f, indent=1, default=str)


def run_tf(tf):
    print('=' * 72)
    print(f"S895 Turn-of-Month Flow · XAUUSD-{tf} (prereg {PREREG})")
    print('=' * 72, flush=True)
    if TF_MIN[tf] >= 1440:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE',
                       reason='intraday TOM day-entry undefined at >=D1 per prereg'))
        print("intraday structure undefined → INCOMPLETE"); return
    hold = max(2, int(round(1440 / TF_MIN[tf])))  # bars(24h) cap
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
    del atr; gc.collect()
    geos = {f'k{k}': dict(sl=k * atr_med_pip, tp=k * atr_med_pip) for k in KS}
    print(f"ATRmed={atr_med_pip:.2f}pip  " +
          " ".join(f"{g}(SL=TP={v['sl']:.1f})" for g, v in geos.items()), flush=True)

    sigs = build_signals(times, tf)
    n_ev = {f"{w}/{h}": int(v.sum()) for (w, h), v in sigs.items()}
    print("events: " + " ".join(f"{k}={n}" for k, n in n_ev.items()), flush=True)
    dfe = df.iloc[:split]

    # ---------- کشف: فقط ۷۰٪ اول ----------
    best = None
    for (wname, hname), sig in sigs.items():
        sig_e = sig[:split]
        if sig_e.sum() < 60:
            continue
        for gname, g in geos.items():
            tr = simulate(dfe, sig_e, g['sl'], g['tp'], hold)
            if tr is None or len(tr) < 100:
                del tr; continue
            pnl = tr['pnl_pip'].values
            n = len(pnl); exp = float(pnl.mean())
            exp2x = exp - COST_PIP
            sd = float(pnl.std(ddof=1))
            t = exp / sd * math.sqrt(n) if sd > 0 else 0.0
            eligible = exp2x > 0
            tag_s = 'ELIGIBLE' if eligible else '        '
            print(f"  {tag_s} {wname:<5}/{hname:<4}/{gname:<7} n={n:>4} "
                  f"exp={exp:+8.2f} exp2x={exp2x:+8.2f} t={t:+.2f}", flush=True)
            if eligible and (best is None or t > best['t_pnl']):
                best = dict(window=wname, hour=hname, geo=gname, t_pnl=round(t, 3),
                            is_n=n, is_wr=round(100 * float((pnl > 0).mean()), 2),
                            is_exp=round(exp, 3), is_exp2x=round(exp2x, 3),
                            sl=g['sl'], tp=g['tp'])
            del tr; gc.collect()

    if best is None:
        _save(tf, dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='UNPROVEN',
                       reason='no eligible config in discovery (n>=100 & exp@2x>0) '
                              '- holdout untouched per prereg stop rule', src=src,
                       bars=N, split=split, hold=hold, events=n_ev,
                       atr_med_pip=round(atr_med_pip, 2)))
        print("NO ELIGIBLE CONFIG → UNPROVEN (holdout untouched)"); return

    print(f"\nLOCKED: {best['window']}/{best['hour']}/{best['geo']} "
          f"t={best['t_pnl']}  IS: n={best['is_n']} WR={best['is_wr']} "
          f"exp2x={best['is_exp2x']}", flush=True)

    # ---------- شلیکِ نهایی: یک بار، کل داده ----------
    sig = sigs[(best['window'], best['hour'])]
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
                   events=n_ev, locked=best, n=n_all, wr=round(wr_all, 2),
                   n_sig=n_sig, net_pip=round(float(tr['pnl_pip'].sum()), 1),
                   oos_n=oos_n, oos_wr=round(oos_wr, 2) if oos_wr else None,
                   uncond_draws=unc_rows, perm=perm, null=null,
                   lift_geo_pp=round(wr_all - ref, 2), rqs2=r))
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


if __name__ == '__main__':
    run_tf(sys.argv[1])
