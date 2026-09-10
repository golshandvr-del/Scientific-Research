#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S899 — شوکِ مطلعِ لنگرِ سشن (Session-Anchored Informed Shock).

قرارداد: results/S899_PREREG_SessionAnchoredShock_Xauusd_MTF.md (کامیت 56d66817)
  - کندل 8h با آفست phi از H1 (data/mt5_full): گروه = day + floor(((hour-phi) mod 24)/8)
    (ساعت‌های < phi به روز قبل تعلق دارند تا کندل پیوسته باشد)
  - کندل با < 5 H1 حذف · شوک: R >= 2.618*ATR21[i-1] و rho >= 0.618 · follow
  - ورود open اولین H1 بعد از پایان کندل · SL 1.272 / TP 2.058 x ATR21[i-1] · hold 128 H1
  - phi=0 کنترل (=S965) · phi=4 حکم رسمی لایه · phi=2 اطلاعی · n_trials=3
  - نال کانونی uncond {899,1899,2899} + perm K=500 seed 899 هر جهت جدا (روی H1)

اجرا: python3 strategies/s899_session_anchor.py 4
"""
import sys, os, json, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'; PIP = 0.1
N_TRIALS = 3; PERM_K = 500; PERM_SEED = 899; UNC_SEEDS = (899, 1899, 2899)
OUT = 'results/_s899'; PREREG = '56d66817'
TH = 2.618; RHO = 0.618; K_SL = 1.272; K_TP = 2.058; HOLD = 128; MIN_H1 = 5


def build_bars(df, phi):
    t = pd.to_datetime(df['time'].values, unit='s')
    hour = t.hour.values
    # shifted clock: bars start at phi, phi+8, phi+16
    sh = (hour - phi) % 24
    day_shift = (hour < phi).astype(int)          # hours before phi belong to previous shifted day
    sday = (t.normalize() - pd.to_timedelta(day_shift, unit='D')).values.astype('datetime64[D]').astype(np.int64)
    slot = sh // 8
    gid = sday * 3 + slot
    # group boundaries
    change = np.r_[True, gid[1:] != gid[:-1]]
    starts = np.flatnonzero(change); ends = np.r_[starts[1:], len(df)]
    o, h, l, c = (df[k].values for k in ('open', 'high', 'low', 'close'))
    rows = []
    for s, e in zip(starts, ends):
        if e - s < MIN_H1:
            continue
        rows.append((s, e - 1, o[s], h[s:e].max(), l[s:e].min(), c[e - 1]))
    b = pd.DataFrame(rows, columns=['i0', 'i1', 'open', 'high', 'low', 'close'])
    return b


def run_phi(phi):
    phi = int(phi)
    print('=' * 72); print(f"S899 Session-Anchored Shock · phi={phi}h  (prereg {PREREG})"); print('=' * 72, flush=True)
    d = fd.load_fast(ASSET, 'H1'); df = fd.as_dataframe(d)
    if 'volume' in df.columns: df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df); split = int(N * 0.70); times = df['time'].values; close = df['close'].values
    b = build_bars(df, phi)
    nb = len(b)
    hrs = pd.to_datetime(times[b['i0'].values], unit='s').hour
    print(f"src={src} H1 bars={N} synthetic 8h bars={nb} start-hours={pd.Series(hrs).value_counts().sort_index().to_dict()}", flush=True)
    bo, bh, bl, bc = (b[k].values for k in ('open', 'high', 'low', 'close'))
    pc = np.roll(bc, 1); pc[0] = bc[0]
    tr_ = np.maximum(bh - bl, np.maximum(np.abs(bh - pc), np.abs(bl - pc)))
    atr = pd.Series(tr_).rolling(21).mean().shift(1).values
    R = bh - bl; body = bc - bo
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(R > 0, np.abs(body) / R, 0.0)
    shock = (R >= TH * atr) & (rho >= RHO) & (body != 0) & ~np.isnan(atr)
    shock[:25] = False
    # map to H1: signal bar = last H1 of the synthetic bar (entry = next H1 open)
    sig_idx = b['i1'].values[shock]
    sgn = np.sign(body[shock])
    atr_sig = atr[shock]
    ls = np.zeros(N, dtype=bool); ss = np.zeros(N, dtype=bool)
    ls[sig_idx[sgn > 0]] = True; ss[sig_idx[sgn < 0]] = True
    # floating brackets: ATR21[i-1] of the synthetic bar, assigned to its last H1; fill elsewhere w/ forward map for null
    atr_h1 = np.full(N, np.nan)
    atr_h1[b['i1'].values] = atr
    atr_h1 = pd.Series(atr_h1).ffill().bfill().values
    sl_arr = K_SL * atr_h1 / PIP; tp_arr = K_TP * atr_h1 / PIP
    print(f"shocks: long={ls.sum()} short={ss.sum()}  ATR21med={np.nanmedian(atr)/PIP:.1f}pip", flush=True)
    z = np.zeros(N, dtype=bool)
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset=ASSET, max_hold=HOLD, allow_overlap=False)
    n_all = len(tr); wr_all = 100.0 * float((tr['outcome'] == 'win').mean())
    n_long = int((tr['direction'].astype(str) == 'long').sum()); n_short = n_all - n_long
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = sl_med * K_TP / K_SL
    print(f"trades n={n_all} (L{n_long}/S{n_short}) WR={wr_all:.2f} net={tr['pnl_pip'].sum():.0f}pip", flush=True)
    # canonical null on H1 with same brackets/hold, per side
    lo, hi = 25 * 8, N - HOLD - 2
    null = {}; unc_all = {}; perm_all = {}
    for side, n_sig in (('long', n_long), ('short', n_short)):
        if n_sig < 5:
            null[side] = dict(uncond_wr=50.0, perm_mean=50.0, perm_sd=0.0, perm_max=50.0, perm_k=0); continue
        unc_rows = []
        for seed in UNC_SEEDS:
            rng = np.random.default_rng(seed)
            pos = rng.choice(np.arange(lo, hi), size=min(20000, (hi - lo) // HOLD), replace=False)
            sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
            t_ = se.simulate_trades(df, sig if side == 'long' else z, sig if side == 'short' else z, sl_arr, tp_arr, asset=ASSET, max_hold=HOLD, allow_overlap=False)
            unc_rows.append((seed, 100.0 * float((t_['outcome'] == 'win').mean()), len(t_))); del t_; gc.collect()
        rng = np.random.default_rng(PERM_SEED); wrs = []
        for i in range(PERM_K):
            pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
            sig = np.zeros(N, dtype=bool); sig[np.sort(pos)] = True
            t_ = se.simulate_trades(df, sig if side == 'long' else z, sig if side == 'short' else z, sl_arr, tp_arr, asset=ASSET, max_hold=HOLD, allow_overlap=False)
            if t_ is not None and len(t_) >= 5: wrs.append(100.0 * float((t_['outcome'] == 'win').mean()))
            del t_
            if (i + 1) % 100 == 0: gc.collect(); print(f"  perm[{side}] {i+1}/{PERM_K} …", flush=True)
        a = np.asarray(wrs, float)
        perm = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()), k=int(len(a)))
        null[side] = dict(uncond_wr=max(r[1] for r in unc_rows), perm_mean=perm['mean'], perm_sd=perm['sd'], perm_max=perm['max'], perm_k=perm['k'])
        unc_all[side] = unc_rows; perm_all[side] = perm
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=times, null=null, n_trials=N_TRIALS, split_bar=split, close=close)
    hm = tr['entry_bar'].values >= split; oos_n = int(hm.sum())
    oos_wr = 100.0 * float((tr.loc[hm, 'outcome'] == 'win').mean()) if oos_n else None
    m = r.get('metrics', {})
    print(f"OOS n={oos_n} WR={oos_wr}")
    print(f"VERDICT: {r.get('verdict')} score={r.get('rqs2_score')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} PF={m.get('profit_factor')}")
    print(f"gates: {r.get('gates')} notes={r.get('notes')}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/rqs2_XAUUSD-H1_phi{phi}.json', 'w') as f:
        json.dump(dict(card=f'XAUUSD-8h-phi{phi}', prereg=PREREG, src=src, h1_bars=N, split=split, synthetic_bars=nb,
                       phi=phi, n=n_all, n_long=n_long, n_short=n_short, wr=round(wr_all, 2), oos_n=oos_n,
                       oos_wr=round(oos_wr, 2) if oos_wr else None, sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
                       net_pip=round(float(tr['pnl_pip'].sum()), 1), uncond_draws=unc_all, perm=perm_all, null=null, rqs2=r),
                  f, indent=1, default=str)
    tr.to_csv(f'{OUT}/trades_XAUUSD-H1_phi{phi}.csv', index=False)


if __name__ == '__main__':
    run_phi(sys.argv[1])
