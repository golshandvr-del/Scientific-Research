#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S871 — «رانشِ فصلیِ ماهِ سال» · XAUUSD چند-TF
پیاده‌سازیِ دقیقِ پیش‌ثبتِ results/S871_PREREG_MONTH_SEASONAL_DRIFT.md

قرارداد (منجمد):
  رویداد   : نخستین کندلِ روز با hour==1 UTC، مشروط به month==m
  ورود     : openِ کندلِ بعد (قراردادِ موتور) · حداکثر ۱ ورود/روز
  گونه‌ها  : month ∈ {1..12} × جهت ∈ {long,short} = ۲۴ (n_trials=24)
  هندسه    : SL = TP = 1.5×ATR(100) آرایه‌ای (RR=1، متقارن — الگوی تقویمیِ ACCEPT)
  max_hold : ساختاری ≈ ۱ روزِ معاملاتی per-TF
  مسیرِ C  : جست‌وجو فقط نیمهٔ اول (z_IS از صفرِ K=200)؛ آستانهٔ z_IS≥2.0
  داوری    : compute_rqs2 کلِ دوره، null اندازه‌گیری‌شده K=1000، split_bar=n//2
  SEED=20260815
"""
import os, sys, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import rqs2 as R
from tools import s434_fast_data as fd

SEED = 20260815
K_PERM = 1000
K_IS = 200
N_TRIALS = 24
Z_IS_MIN = 2.0
ATR_P = 100
SL_K = 1.5
RR = 1.0
ASSET = 'XAUUSD'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s871')

MAX_HOLD = {'M1': 1440, 'M3': 480, 'M4': 360, 'M5': 288, 'M6': 240,
            'M10': 144, 'M12': 120, 'M15': 96, 'M20': 72, 'M30': 48,
            'H1': 24, 'H2': 12, 'H3': 8, 'H4': 6, 'H6': 4, 'H8': 3,
            'H12': 2, 'D1': 1}

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1']


def atr(df, p=ATR_P):
    h = df['high'].astype(float); l = df['low'].astype(float)
    c = df['close'].astype(float); pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def load_tf(tf):
    try:
        d = fd.load_fast(ASSET, tf)
        return fd.as_dataframe(d), d.get('src')
    except Exception:
        if tf == 'H4':
            d = fd.load_fast(ASSET, 'H1')
            df = fd.as_dataframe(d)
            t = pd.to_datetime(df['time'], unit='s')
            g = df.set_index(t).resample('4h').agg(
                open=('open', 'first'), high=('high', 'max'),
                low=('low', 'min'), close=('close', 'last')).dropna()
            g['time'] = g.index.astype('int64') // 10**9
            return g.reset_index(drop=True), d.get('src') + ' [resampled H1->H4]'
        raise


def day_anchor_events(tsec):
    """اندیسِ نخستین کندلِ هر روز با hour==1 UTC (حداکثر یکی در روز)."""
    t = pd.to_datetime(tsec, unit='s')
    hour = t.hour.values
    day = (tsec // 86400).astype(np.int64)
    is_h1 = hour == 1
    idx = np.nonzero(is_h1)[0]
    if len(idx) == 0:
        return idx, np.array([], dtype=int)
    # اولین کندلِ ساعت ۱ در هر روز
    d = day[idx]
    first = np.ones(len(idx), dtype=bool)
    first[1:] = d[1:] != d[:-1]
    ev = idx[first]
    months = t[ev].month.values
    return ev, months


def sim(df, ev_idx, side, sl_arr, tp_arr, mh):
    n = len(df)
    ls = np.zeros(n, dtype=bool); ss = np.zeros(n, dtype=bool)
    (ls if side == 'long' else ss)[ev_idx] = True
    ls[-1] = False; ss[-1] = False
    return se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                              asset=ASSET, max_hold=mh, allow_overlap=False)


def sim_random(df, ev_idx, rd, sl_arr, tp_arr, mh):
    n = len(df)
    ls = np.zeros(n, dtype=bool); ss = np.zeros(n, dtype=bool)
    ls[ev_idx[rd > 0]] = True; ss[ev_idx[rd < 0]] = True
    ls[-1] = False; ss[-1] = False
    return se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                              asset=ASSET, max_hold=mh, allow_overlap=False)


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return np.nan, 0
    return 100.0 * (tr['pnl_pip'] > 0).mean(), len(tr)


def process_tf(tf):
    t0 = time.time()
    df, src = load_tf(tf)
    n = len(df)
    mh = MAX_HOLD[tf]
    tsec = df['time'].to_numpy(np.int64)
    close = df['close'].to_numpy(float)
    a = atr(df).to_numpy(float)
    sl_arr = np.maximum(SL_K * a / 0.1, 1e-9)
    tp_arr = sl_arr * RR
    split = n // 2

    ev_all, mon_all = day_anchor_events(tsec)
    out = dict(tf=tf, src=src, bars=n, split_bar=split, max_hold=mh,
               n_day_anchors=int(len(ev_all)),
               sl_median_pip=float(np.nanmedian(sl_arr)))
    if len(ev_all) < 60:
        out['verdict'] = 'NO_EVENTS'
        return out

    # ---- IS: نیمهٔ اول ----
    is_mask = ev_all < split
    rows = []
    rng = np.random.default_rng(SEED)
    # صفرِ IS: به‌ازای هر ماه یک صفرِ K=200 روی رویدادهای همان ماهِ IS
    for m in range(1, 13):
        sel = ev_all[is_mask & (mon_all == m)]
        if len(sel) < 30:
            for side in ('long', 'short'):
                rows.append(dict(month=m, side=side, n=int(len(sel)),
                                 wr=np.nan, lift=np.nan, z_is=np.nan,
                                 note='n<30 in IS'))
            continue
        wrs = []
        for j in range(K_IS):
            rd = rng.choice([-1, 1], size=len(sel))
            tr = sim_random(df, sel, rd, sl_arr, tp_arr, mh)
            if len(tr):
                wrs.append(100.0 * (tr['pnl_pip'] > 0).mean())
        mu, sd = (np.mean(wrs), np.std(wrs, ddof=1)) if wrs else (np.nan, np.nan)
        for side in ('long', 'short'):
            tr = sim(df, sel, side, sl_arr, tp_arr, mh)
            wr, cnt = wr_of(tr)
            z = (wr - mu) / sd if (sd and sd > 0 and np.isfinite(wr)) else np.nan
            rows.append(dict(month=m, side=side, n=cnt, wr=wr,
                             lift=(wr - mu) if np.isfinite(wr) else np.nan,
                             z_is=z,
                             pnl_pip=float(tr['pnl_pip'].sum()) if cnt else 0.0))
    out['is_grid'] = rows
    valid = [r for r in rows if np.isfinite(r.get('z_is', np.nan))]
    winner = max(valid, key=lambda r: r['z_is']) if valid else None
    out['winner'] = winner
    if winner is None or winner['z_is'] < Z_IS_MIN:
        out['verdict'] = 'DEAD_IS'
        out['elapsed_s'] = round(time.time() - t0, 1)
        return out

    # ---- داوریِ کامل ----
    m, side = winner['month'], winner['side']
    sel_full = ev_all[mon_all == m]
    tr_full = sim(df, sel_full, side, sl_arr, tp_arr, mh)

    rng2 = np.random.default_rng(SEED + 1)
    wrs = []; wl = []; ws = []
    for j in range(K_PERM):
        rd = rng2.choice([-1, 1], size=len(sel_full))
        tr = sim_random(df, sel_full, rd, sl_arr, tp_arr, mh)
        if len(tr):
            wrs.append(100.0 * (tr['pnl_pip'] > 0).mean())
            for s, acc in (('long', wl), ('short', ws)):
                mm = tr['direction'] == s
                if mm.any():
                    acc.append(100.0 * (tr.loc[mm, 'pnl_pip'] > 0).mean())

    def blk(arr):
        arr = np.asarray(arr if arr else wrs, float)
        return dict(uncond_wr=float(arr.mean()), perm_mean=float(arr.mean()),
                    perm_sd=float(arr.std(ddof=1)), perm_max=float(arr.max()),
                    perm_k=int(len(arr)))
    null_ps = {'long': blk(wl), 'short': blk(ws)}

    sl_eff = float(tr_full['sl_pip'].mean()) if len(tr_full) else float(np.nanmedian(sl_arr))
    res = R.compute_rqs2(tr_full, ASSET, sl_pip=sl_eff, tp_pip=sl_eff * RR,
                         bar_time=df['time'].to_numpy(), close=close,
                         null=null_ps, n_trials=N_TRIALS, split_bar=split)
    out['full'] = dict(n=len(tr_full), wr=wr_of(tr_full)[0],
                       pnl_pip=float(tr_full['pnl_pip'].sum()),
                       null_flat=dict(mean=float(np.mean(wrs)),
                                      sd=float(np.std(wrs, ddof=1)),
                                      k=len(wrs)))
    out['rqs2'] = {k: res.get(k) for k in ('verdict', 'rqs2_score', 'gates')}
    out['rqs2_metrics'] = res.get('metrics')
    out['verdict'] = res.get('verdict')
    out['score'] = res.get('rqs2_score')
    out['elapsed_s'] = round(time.time() - t0, 1)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        ck = os.path.join(OUT, f'checkpoint_{tf}.json')
        if os.path.exists(ck):
            print(f'[skip] {tf}', flush=True)
            continue
        print(f'[run ] {tf} ...', flush=True)
        try:
            out = process_tf(tf)
        except Exception as e:
            import traceback; traceback.print_exc()
            out = dict(tf=tf, error=str(e))
        with open(ck, 'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        w = out.get('winner') or {}
        print(f"[done] {tf}: verdict={out.get('verdict')} score={out.get('score')} "
              f"winner=m{w.get('month')}/{w.get('side')} z_is={w.get('z_is')} "
              f"({out.get('elapsed_s')}s)", flush=True)


if __name__ == '__main__':
    main()
