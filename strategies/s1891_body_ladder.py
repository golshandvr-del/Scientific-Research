#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1891 — نردبانِ شوکِ بدنه (Body-Shock Ladder).

قرارداد: results/S1891_PREREG_BodyShockLadder_Xauusd_MTF.md (کامیت 5934782c)
  رویداد: |close-open| >= k*ATR21[i-1] ، k in {1.272,1.618,2.0} ؛ follow ؛ ورود open بعد
  SL 1.272 / TP 2.058 x ATR21[i-1] ، hold 16 ، no overlap
  مسیر C: k با بیشینهٔ t_pnl در 70% اول قفل (اهلیت n_IS>=150 & exp@2x>0) ⇒ یک compute_rqs2 با split_bar
  n_trials=15 ؛ نال کانونی uncond {1891,2891,3891} + perm K=500 seed 1891 هر جهت جدا
  P1: یکنوایی lift در k (IS) · P2: k قفل‌شده vs S965 (IS)
اجرا: python3 strategies/s1891_body_ladder.py H8
"""
import sys, os, json, gc, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'; PIP = 0.1; COST = 3.3
N_TRIALS = 15; PERM_K = 500; PERM_SEED = 1891; UNC_SEEDS = (1891, 2891, 3891)
OUT = 'results/_s1891'; PREREG = '5934782c'
K_SL = 1.272; K_TP = 2.058; HOLD = 16; KS = (1.272, 1.618, 2.0); MIN_IS = 150
TFS = ('H8', 'H6', 'H12', 'H4', 'D1')


def wr_of(tr): return 100.0 * float((tr['outcome'] == 'win').mean())


def stats(tr):
    p = tr['pnl_pip'].values; n = len(p); e = float(p.mean()); sd = float(p.std(ddof=1))
    return n, e, e - COST, (e / sd * math.sqrt(n) if sd > 0 else 0.0), wr_of(tr)


def run_tf(tf):
    print('=' * 72); print(f"S1891 Body-Shock Ladder · XAUUSD-{tf} (prereg {PREREG})"); print('=' * 72, flush=True)
    os.makedirs(OUT, exist_ok=True)
    if tf not in TFS:
        json.dump(dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE', reason='pre-declared: hold=16 has no session meaning below H4'),
                  open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w'), indent=1); print('pre-declared INCOMPLETE'); return
    d = fd.load_fast(ASSET, tf); df = fd.as_dataframe(d)
    if 'volume' in df.columns: df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df); split = int(N * 0.70); times = df['time'].values
    o, h, l, c = (df[k].values for k in ('open', 'high', 'low', 'close'))
    pc = np.roll(c, 1); pc[0] = c[0]
    atr = pd.Series(np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))).rolling(21).mean().shift(1).values
    atr_f = np.nan_to_num(atr, nan=np.nanmedian(atr)); sl_arr = K_SL * atr_f / PIP; tp_arr = K_TP * atr_f / PIP
    body = c - o; R = h - l
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(R > 0, np.abs(body) / R, 0.0)
    sgn = np.sign(body).astype(int); z = np.zeros(N, bool); isw = np.arange(N) < split
    sim = lambda a, b: se.simulate_trades(df, a, b, sl_arr, tp_arr, asset=ASSET, max_hold=HOLD, allow_overlap=False)
    print(f"src={src} bars={N} split={split}", flush=True)
    # discovery IS
    disc = {}; best = None
    for k in KS:
        ev = (np.abs(body) >= k * atr) & ~np.isnan(atr); ev[:25] = False
        n_ev = int(ev.sum())
        tr = sim(ev & (sgn > 0) & isw, ev & (sgn < 0) & isw)
        if tr is None or len(tr) < 30:
            disc[f'k{k}'] = dict(events=n_ev, n_is=0 if tr is None else len(tr), note='too few'); continue
        n, e, e2, t, wr = stats(tr)
        disc[f'k{k}'] = dict(events=n_ev, n_is=n, wr=round(wr, 2), exp=round(e, 2), exp2x=round(e2, 2), t=round(t, 3), eligible=bool(n >= MIN_IS and e2 > 0))
        print(f"  k={k}: events={n_ev} IS n={n} WR={wr:.2f} exp={e:+.2f} exp2x={e2:+.2f} t={t:+.2f} {'ELIGIBLE' if disc[f'k{k}']['eligible'] else ''}", flush=True)
        if disc[f'k{k}']['eligible'] and (best is None or t > best['t']): best = dict(k=k, t=round(t, 3), is_n=n, is_wr=round(wr, 2))
        del tr; gc.collect()
    # P2: S965 on same IS
    ev965 = (R >= 2.618 * atr) & (rho >= 0.618) & (sgn != 0) & ~np.isnan(atr); ev965[:25] = False
    tr9 = sim(ev965 & (sgn > 0) & isw, ev965 & (sgn < 0) & isw)
    p2 = dict(s965_is=dict(n=len(tr9), wr=round(wr_of(tr9), 2), exp=round(float(tr9['pnl_pip'].mean()), 2)) if len(tr9) >= 10 else None)
    del tr9
    wrs = [disc[f'k{k}'].get('wr') for k in KS]
    p1 = dict(wr_by_k=dict(zip([str(k) for k in KS], wrs)), monotone=all(wrs[i] is not None and wrs[i+1] is not None and wrs[i+1] >= wrs[i] for i in range(2)))
    print(f"P1 monotone={p1['monotone']} {p1['wr_by_k']}   P2 S965 IS={p2['s965_is']}", flush=True)
    if best is None:
        json.dump(dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='UNPROVEN', reason='no eligible k (n_IS>=150 & exp@2x>0) - holdout untouched', src=src, bars=N, split=split, discovery=disc, p1=p1, p2=p2),
                  open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w'), indent=1, default=str); print('UNPROVEN'); return
    k = best['k']; ev = (np.abs(body) >= k * atr) & ~np.isnan(atr); ev[:25] = False
    ls = ev & (sgn > 0); ss = ev & (sgn < 0)
    tr = sim(ls, ss); n_all = len(tr); wr_all = wr_of(tr)
    n_long = int((tr['direction'].astype(str) == 'long').sum()); n_short = n_all - n_long
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = sl_med * K_TP / K_SL
    print(f"LOCKED k={k}: trades n={n_all} (L{n_long}/S{n_short}) WR={wr_all:.2f} net={tr['pnl_pip'].sum():.0f}", flush=True)
    lo, hi = 30, N - HOLD - 2; null = {}; unc_all = {}; perm_all = {}
    for side, n_sig in (('long', n_long), ('short', n_short)):
        if n_sig < 5: null[side] = dict(uncond_wr=50.0, perm_mean=50.0, perm_sd=0.0, perm_max=50.0, perm_k=0); continue
        unc_rows = []
        for seed in UNC_SEEDS:
            rng = np.random.default_rng(seed); pos = rng.choice(np.arange(lo, hi), size=min(20000, (hi - lo) // HOLD), replace=False)
            s_ = np.zeros(N, bool); s_[np.sort(pos)] = True
            t_ = sim(s_ if side == 'long' else z, s_ if side == 'short' else z); unc_rows.append((seed, wr_of(t_), len(t_))); del t_; gc.collect()
        rng = np.random.default_rng(PERM_SEED); wrs_ = []
        for i in range(PERM_K):
            pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False); s_ = np.zeros(N, bool); s_[np.sort(pos)] = True
            t_ = sim(s_ if side == 'long' else z, s_ if side == 'short' else z)
            if t_ is not None and len(t_) >= 5: wrs_.append(wr_of(t_))
            del t_
            if (i + 1) % 100 == 0: gc.collect(); print(f"  perm[{side}] {i+1}/{PERM_K} …", flush=True)
        a = np.asarray(wrs_, float); perm = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()), k=int(len(a)))
        null[side] = dict(uncond_wr=max(r[1] for r in unc_rows), perm_mean=perm['mean'], perm_sd=perm['sd'], perm_max=perm['max'], perm_k=perm['k'])
        unc_all[side] = unc_rows; perm_all[side] = perm
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=times, null=null, n_trials=N_TRIALS, split_bar=split, close=c)
    hm = tr['entry_bar'].values >= split; oos_n = int(hm.sum()); oos_wr = wr_of(tr.loc[hm]) if oos_n else None
    side_wr = {s: round(wr_of(tr[tr['direction'].astype(str) == s]), 2) for s in ('long', 'short') if (tr['direction'].astype(str) == s).sum() > 0}
    m = r.get('metrics', {})
    print(f"OOS n={oos_n} WR={oos_wr} side={side_wr}")
    print(f"VERDICT: {r.get('verdict')} score={r.get('rqs2_score')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} PF={m.get('profit_factor')}")
    print(f"gates: {r.get('gates')} notes={r.get('notes')}", flush=True)
    json.dump(dict(card=f'XAUUSD-{tf}', prereg=PREREG, src=src, bars=N, split=split, discovery=disc, locked=best, p1=p1, p2=p2,
                   n=n_all, n_long=n_long, n_short=n_short, wr=round(wr_all, 2), side_wr=side_wr, oos_n=oos_n, oos_wr=round(oos_wr, 2) if oos_wr else None,
                   sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2), net_pip=round(float(tr['pnl_pip'].sum()), 1),
                   uncond_draws=unc_all, perm=perm_all, null=null, rqs2=r), open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w'), indent=1, default=str)
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


if __name__ == '__main__':
    run_tf(sys.argv[1])
