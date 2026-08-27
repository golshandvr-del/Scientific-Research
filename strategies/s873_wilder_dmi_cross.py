#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S873 — «تقاطع DMI وایلدر» · XAUUSD چند-TF
پیاده‌سازی دقیق پیش‌ثبت results/S873_PREREG_WILDER_DMI_CROSS.md

قرارداد (منجمد):
  DMI کلاسیک P=14 (وایلدر 1978) · رویداد = کراس +DI/−DI روی کندل بسته
  گونه‌ها: {plain,gated(ADX≥20)} × {follow,fade} = ۴ (n_trials=4)
  هندسه: SL=1.5×ATR(100) آرایه‌ای · TP=1.5×SL · max_hold=56 · overlap ممنوع
  مسیر C: IS نیمه اول، نال K=200، گیت z_IS≥2.0؛ داوری کل دوره K=1000
  SEED=20260824 (IS) / 20260825 (داوری)
"""
import os, sys, json, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se
from engine import rqs2 as R
from tools import s434_fast_data as fd

SEED = 20260824
K_PERM = 1000
K_IS = 200
N_TRIALS = 4
Z_IS_MIN = 2.0
ATR_P = 100
SL_K = 1.5
RR = 1.5
P_DMI = 14
ADX_GATE = 20.0
MAX_HOLD = 56
ASSET = 'XAUUSD'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'results', '_s873')

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1']

VARIANTS = [('plain', 'follow'), ('plain', 'fade'),
            ('gated', 'follow'), ('gated', 'fade')]


def atr(df, p=ATR_P):
    h = df['high'].astype(float); l = df['low'].astype(float)
    c = df['close'].astype(float); pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / p, adjust=False).mean()


def dmi(df, p=P_DMI):
    h = df['high'].astype(float); l = df['low'].astype(float)
    c = df['close'].astype(float); pc = c.shift(1)
    up = h.diff(); dn = -l.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    a = 1.0 / p
    s_pdm = pd.Series(plus_dm, index=df.index).ewm(alpha=a, adjust=False).mean()
    s_mdm = pd.Series(minus_dm, index=df.index).ewm(alpha=a, adjust=False).mean()
    s_tr = tr.ewm(alpha=a, adjust=False).mean()
    pdi = 100.0 * s_pdm / s_tr.replace(0, np.nan)
    mdi = 100.0 * s_mdm / s_tr.replace(0, np.nan)
    dx = 100.0 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    adx = dx.ewm(alpha=a, adjust=False).mean()
    return pdi.to_numpy(float), mdi.to_numpy(float), adx.to_numpy(float)


def detect_events(df):
    """کراس +DI/−DI. خروجی: idx, dir(+1 up-cross / −1 down-cross), adx[idx]"""
    pdi, mdi, adx = dmi(df)
    diff = pdi - mdi
    prev = np.roll(diff, 1); prev[0] = np.nan
    warm = np.arange(len(df)) >= (P_DMI * 3)  # دوره‌ی گرم‌شدن هموارسازی
    up = warm & np.isfinite(diff) & np.isfinite(prev) & (prev <= 0) & (diff > 0)
    dn = warm & np.isfinite(diff) & np.isfinite(prev) & (prev >= 0) & (diff < 0)
    idx = np.nonzero(up | dn)[0]
    dr = np.where(up[idx], 1, -1)
    return idx, dr, adx[idx]


def sim(df, ev_idx, sides, sl_arr, tp_arr):
    n = len(df)
    ls = np.zeros(n, dtype=bool); ss = np.zeros(n, dtype=bool)
    sd = np.asarray(sides)
    ls[ev_idx[sd > 0]] = True; ss[ev_idx[sd < 0]] = True
    ls[-1] = False; ss[-1] = False
    return se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=tp_arr,
                              asset=ASSET, max_hold=MAX_HOLD, allow_overlap=False)


def wr_of(tr):
    if tr is None or len(tr) == 0:
        return np.nan, 0
    return 100.0 * (tr['pnl_pip'] > 0).mean(), len(tr)


def variant_events(idx, dr, adxv, gate, mode):
    m = adxv >= ADX_GATE if gate == 'gated' else np.ones(len(idx), bool)
    sel, sdr = idx[m], dr[m]
    sides = sdr if mode == 'follow' else -sdr
    return sel, sides


def process_tf(tf):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d); src = d.get('src')
    n = len(df)
    close = df['close'].to_numpy(float)
    a = atr(df).to_numpy(float)
    sl_arr = np.maximum(SL_K * a / 0.1, 1e-9)
    tp_arr = sl_arr * RR
    split = n // 2

    idx, dr, adxv = detect_events(df)
    out = dict(tf=tf, src=src, bars=n, split_bar=split, max_hold=MAX_HOLD,
               n_events=int(len(idx)),
               n_events_gated=int((adxv >= ADX_GATE).sum()),
               sl_median_pip=float(np.nanmedian(sl_arr)))
    if len(idx) < 120:
        out['verdict'] = 'NO_EVENTS'
        return out

    # ---- IS ----
    rng = np.random.default_rng(SEED)
    rows = []
    null_cache = {}
    for gate, mode in VARIANTS:
        sel_all, sides_all = variant_events(idx, dr, adxv, gate, mode)
        m = sel_all < split
        sel, sides = sel_all[m], np.asarray(sides_all)[m]
        if len(sel) < 60:
            rows.append(dict(gate=gate, mode=mode, n=int(len(sel)), wr=np.nan,
                             lift=np.nan, z_is=np.nan, note='n<60 in IS'))
            continue
        key = gate  # نال به mode بستگی ندارد (جهت تصادفی)
        if key not in null_cache:
            wrs = []
            for j in range(K_IS):
                rd = rng.choice([-1, 1], size=len(sel))
                tr = sim(df, sel, rd, sl_arr, tp_arr)
                if len(tr):
                    wrs.append(100.0 * (tr['pnl_pip'] > 0).mean())
            null_cache[key] = (np.mean(wrs), np.std(wrs, ddof=1)) if wrs else (np.nan, np.nan)
        mu, sd = null_cache[key]
        tr = sim(df, sel, sides, sl_arr, tp_arr)
        wr, cnt = wr_of(tr)
        z = (wr - mu) / sd if (sd and sd > 0 and np.isfinite(wr)) else np.nan
        rows.append(dict(gate=gate, mode=mode, n=cnt, wr=wr,
                         lift=(wr - mu) if np.isfinite(wr) else np.nan, z_is=z,
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
    gate, mode = winner['gate'], winner['mode']
    sel_full, sides_full = variant_events(idx, dr, adxv, gate, mode)
    tr_full = sim(df, sel_full, sides_full, sl_arr, tp_arr)

    rng2 = np.random.default_rng(SEED + 1)
    wrs = []; wl = []; ws = []
    for j in range(K_PERM):
        rd = rng2.choice([-1, 1], size=len(sel_full))
        tr = sim(df, sel_full, rd, sl_arr, tp_arr)
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
              f"winner={w.get('gate')}/{w.get('mode')} z_is={w.get('z_is')} "
              f"({out.get('elapsed_s')}s)", flush=True)


if __name__ == '__main__':
    main()
