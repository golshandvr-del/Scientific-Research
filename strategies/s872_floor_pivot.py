#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S872 — «تعامل با پیوت‌های کلاسیک» · XAUUSD چند-TF
پیاده‌سازی دقیق پیش‌ثبت results/S872_PREREG_FLOOR_PIVOT_INTERACTION.md

قرارداد (منجمد):
  روز       : مرز روز = gap زمانی > max(1800s, 1.5×TF_sec)  (قاعده‌ی S560، DST-safe)
  سطوح      : P=(H+L+C)/3 · R1=2P−L · S1=2P−H  از روزِ قبل (علّی)
  رویداد    : کراسِ close از سطح (بالا/پایین)، نخستین کراسِ هر سطح در روز
  گونه‌ها   : {P,R1,S1} × {follow,fade} = ۶ (n_trials=6)
  هندسه     : SL=1.5×ATR(100) آرایه‌ای · TP=1.5×SL (RR=1.5) · max_hold ≈ ۱ روز
  مسیر C    : جست‌وجو نیمه‌ی اول (نال K=200)؛ گیت z_IS≥2.0؛ داوری کل دوره K=1000
  SEED=20260820 (IS) / 20260821 (داوری)
"""
import os, sys, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import rqs2 as R
from tools import s434_fast_data as fd

SEED = 20260820
K_PERM = 1000
K_IS = 200
N_TRIALS = 6
Z_IS_MIN = 2.0
ATR_P = 100
SL_K = 1.5
RR = 1.5
ASSET = 'XAUUSD'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s872')

MAX_HOLD = {'M1': 1440, 'M3': 480, 'M4': 360, 'M5': 288, 'M6': 240,
            'M10': 144, 'M12': 120, 'M15': 96, 'M20': 72, 'M30': 48,
            'H1': 24, 'H2': 12, 'H3': 8, 'H4': 6, 'H6': 4, 'H8': 3, 'H12': 2}

TF_SEC = {'M1': 60, 'M3': 180, 'M4': 240, 'M5': 300, 'M6': 360, 'M10': 600,
          'M12': 720, 'M15': 900, 'M20': 1200, 'M30': 1800, 'H1': 3600,
          'H2': 7200, 'H3': 10800, 'H4': 14400, 'H6': 21600, 'H8': 28800,
          'H12': 43200}

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12']

LEVELS = ('P', 'R1', 'S1')


def atr(df, p=ATR_P):
    h = df['high'].astype(float); l = df['low'].astype(float)
    c = df['close'].astype(float); pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def load_tf(tf):
    d = fd.load_fast(ASSET, tf)
    return fd.as_dataframe(d), d.get('src')


def detect_events(df, tf):
    """رویدادهای کراسِ سطوحِ پیوت. خروجی: dict level -> (idx_array, dir_array +1/-1)"""
    tsec = df['time'].to_numpy(np.int64)
    o = df['open'].to_numpy(float); h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    n = len(df)
    gap_thr = max(1800, int(1.5 * TF_SEC[tf]))
    # شناسه‌ی روز: افزایش هنگام gap
    dt = np.diff(tsec, prepend=tsec[0])
    new_day = dt > gap_thr
    day_id = np.cumsum(new_day)  # روز 0..D
    D = day_id[-1] + 1
    # های/لو/کلوزِ هر روز
    dayH = np.full(D, -np.inf); dayL = np.full(D, np.inf); dayC = np.full(D, np.nan)
    np.maximum.at(dayH, day_id, h)
    np.minimum.at(dayL, day_id, l)
    # close آخر هر روز
    for i in range(n):
        dayC[day_id[i]] = c[i]
    # سطوح روز d از روز d−1
    P = (dayH + dayL + dayC) / 3.0
    R1 = 2 * P - dayL
    S1 = 2 * P - dayH
    lv = {'P': P, 'R1': R1, 'S1': S1}
    ev = {}
    prev_c = np.roll(c, 1); prev_c[0] = np.nan
    prev_day = np.roll(day_id, 1); prev_day[0] = -1
    same_day = (day_id == prev_day)
    for name, arr in lv.items():
        # سطحِ فعال در بار i = arr[day_id[i]−1]
        lvl = np.full(n, np.nan)
        m = day_id >= 1
        lvl[m] = arr[day_id[m] - 1]
        up = same_day & np.isfinite(lvl) & (prev_c < lvl) & (c >= lvl)
        dn = same_day & np.isfinite(lvl) & (prev_c > lvl) & (c <= lvl)
        idx = np.nonzero(up | dn)[0]
        dr = np.where(up[idx], 1, -1)
        # debounce: نخستین کراسِ این سطح در هر روز
        if len(idx):
            dsel = day_id[idx]
            first = np.ones(len(idx), dtype=bool)
            first[1:] = dsel[1:] != dsel[:-1]
            idx = idx[first]; dr = dr[first]
        ev[name] = (idx, dr)
    return ev


def sim(df, ev_idx, sides, sl_arr, tp_arr, mh):
    """sides: array of 'long'/'short' یا +1/-1"""
    n = len(df)
    ls = np.zeros(n, dtype=bool); ss = np.zeros(n, dtype=bool)
    sd = np.asarray(sides)
    if sd.dtype.kind in 'iu' or sd.dtype.kind == 'f':
        ls[ev_idx[sd > 0]] = True; ss[ev_idx[sd < 0]] = True
    else:
        ls[ev_idx[sd == 'long']] = True; ss[ev_idx[sd == 'short']] = True
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
    close = df['close'].to_numpy(float)
    a = atr(df).to_numpy(float)
    sl_arr = np.maximum(SL_K * a / 0.1, 1e-9)
    tp_arr = sl_arr * RR
    split = n // 2

    ev = detect_events(df, tf)
    out = dict(tf=tf, src=src, bars=n, split_bar=split, max_hold=mh,
               sl_median_pip=float(np.nanmedian(sl_arr)),
               n_events={k: int(len(v[0])) for k, v in ev.items()})
    if sum(len(v[0]) for v in ev.values()) < 120:
        out['verdict'] = 'NO_EVENTS'
        return out

    # ---- IS ----
    rng = np.random.default_rng(SEED)
    rows = []
    for name in LEVELS:
        idx, dr = ev[name]
        m = idx < split
        sel, sdr = idx[m], dr[m]
        if len(sel) < 60:
            for mode in ('follow', 'fade'):
                rows.append(dict(level=name, mode=mode, n=int(len(sel)),
                                 wr=np.nan, lift=np.nan, z_is=np.nan,
                                 note='n<60 in IS'))
            continue
        # نال IS: جهت تصادفی روی همان رویدادها
        wrs = []
        for j in range(K_IS):
            rd = rng.choice([-1, 1], size=len(sel))
            tr = sim(df, sel, rd, sl_arr, tp_arr, mh)
            if len(tr):
                wrs.append(100.0 * (tr['pnl_pip'] > 0).mean())
        mu, sd = (np.mean(wrs), np.std(wrs, ddof=1)) if wrs else (np.nan, np.nan)
        for mode in ('follow', 'fade'):
            sides = sdr if mode == 'follow' else -sdr
            tr = sim(df, sel, sides, sl_arr, tp_arr, mh)
            wr, cnt = wr_of(tr)
            z = (wr - mu) / sd if (sd and sd > 0 and np.isfinite(wr)) else np.nan
            rows.append(dict(level=name, mode=mode, n=cnt, wr=wr,
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

    # ---- داوری کامل ----
    name, mode = winner['level'], winner['mode']
    idx, dr = ev[name]
    sides = dr if mode == 'follow' else -dr
    tr_full = sim(df, idx, sides, sl_arr, tp_arr, mh)

    rng2 = np.random.default_rng(SEED + 1)
    wrs = []; wl = []; ws = []
    for j in range(K_PERM):
        rd = rng2.choice([-1, 1], size=len(idx))
        tr = sim(df, idx, rd, sl_arr, tp_arr, mh)
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
                                      sd=float(np.std(wrs, ddof=1)), k=len(wrs)))
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
              f"winner={w.get('level')}/{w.get('mode')} z_is={w.get('z_is')} "
              f"({out.get('elapsed_s')}s)", flush=True)


if __name__ == '__main__':
    main()
