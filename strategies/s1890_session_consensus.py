#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S1890 — روزِ اجماعِ سه‌سشنی (Three-Session Consensus Day).

قرارداد: results/S1890_PREREG_SessionConsensusDay_Xauusd_MTF.md (کامیت ccfc6c95)
  H8: سه کندل 00/08/16 UTC یک روز، sign(body) یکسان و ناصفر ⇒ سیگنال روی کندل 16، follow
  H4: شش کندل روز (00..20) ، هر جفت هم‌سشن (00+04, 08+12, 16+20) جمعِ body هم‌علامت و سه سشن هم‌جهت
  D1: کندل روز با rho>=0.618 (پروکسی) ⇒ follow
  براکت SL 1.272 / TP 2.058 x ATR21[i-1] ، hold = «روز بعد» (H8:3, H4:6, D1:1) ، no overlap
  n_trials=3 · نال کانونی uncond {1890,2890,3890} + perm K=500 seed 1890 هر جهت جدا
  P1 (IS): اجماع vs غیراجماع با جابجایی >= میانهٔ اجماع
اجرا: python3 strategies/s1890_session_consensus.py H8
"""
import sys, os, json, gc
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine import rqs2
from engine import scalp_engine as se

ASSET = 'XAUUSD'; PIP = 0.1
N_TRIALS = 3; PERM_K = 500; PERM_SEED = 1890; UNC_SEEDS = (1890, 2890, 3890)
OUT = 'results/_s1890'; PREREG = 'ccfc6c95'
K_SL = 1.272; K_TP = 2.058
HOLD = {'H8': 3, 'H4': 6, 'D1': 1}


def atr_prev(o, h, l, c, n=21):
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().shift(1).values


def events(tf, times, o, h, l, c):
    """returns sig(bool), sgn(int), disp(abs displacement of the day in price), day_end_mask"""
    N = len(c); t = pd.to_datetime(times, unit='s'); hr = t.hour.values; day = t.normalize().values
    sgn_b = np.sign(c - o).astype(int)
    sig = np.zeros(N, bool); sgn = np.zeros(N, int); disp = np.full(N, np.nan); dend = np.zeros(N, bool)
    if tf == 'H8':
        for i in range(2, N):
            if hr[i] == 16 and hr[i-1] == 8 and hr[i-2] == 0 and day[i] == day[i-1] == day[i-2]:
                dend[i] = True; disp[i] = abs(c[i] - o[i-2])
                if sgn_b[i] == sgn_b[i-1] == sgn_b[i-2] != 0:
                    sig[i] = True; sgn[i] = sgn_b[i]
    elif tf == 'H4':
        for i in range(5, N):
            hs = hr[i-5:i+1]
            if list(hs) == [0, 4, 8, 12, 16, 20] and len(set(day[i-5:i+1])) == 1:
                dend[i] = True; disp[i] = abs(c[i] - o[i-5])
                s1 = np.sign((c[i-5]-o[i-5]) + (c[i-4]-o[i-4])); s2 = np.sign((c[i-3]-o[i-3]) + (c[i-2]-o[i-2])); s3 = np.sign((c[i-1]-o[i-1]) + (c[i]-o[i]))
                if s1 == s2 == s3 != 0:
                    sig[i] = True; sgn[i] = int(s1)
    elif tf == 'D1':
        R = h - l
        with np.errstate(divide='ignore', invalid='ignore'):
            rho = np.where(R > 0, np.abs(c - o) / R, 0.0)
        dend[:] = True; disp[:] = np.abs(c - o)
        sig = (rho >= 0.618) & (sgn_b != 0); sgn = np.where(sig, sgn_b, 0)
    return sig, sgn, disp, dend


def wr_of(tr): return 100.0 * float((tr['outcome'] == 'win').mean())


def run_tf(tf):
    print('=' * 72); print(f"S1890 Session-Consensus Day · XAUUSD-{tf} (prereg {PREREG})"); print('=' * 72, flush=True)
    if tf not in HOLD:
        os.makedirs(OUT, exist_ok=True)
        json.dump(dict(card=f'XAUUSD-{tf}', prereg=PREREG, verdict='INCOMPLETE', reason='pre-declared: session-day event undefined on this TF'),
                  open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w'), indent=1)
        print('pre-declared INCOMPLETE'); return
    hold = HOLD[tf]
    d = fd.load_fast(ASSET, tf); df = fd.as_dataframe(d)
    if 'volume' in df.columns: df = df.drop(columns=['volume'])
    src = d.get('src', '?'); del d; gc.collect()
    N = len(df); split = int(N * 0.70); times = df['time'].values
    o, h, l, c = (df[k].values for k in ('open', 'high', 'low', 'close'))
    atr = atr_prev(o, h, l, c); atr_f = np.nan_to_num(atr, nan=np.nanmedian(atr))
    sl_arr = K_SL * atr_f / PIP; tp_arr = K_TP * atr_f / PIP
    sig, sgn, disp, dend = events(tf, times, o, h, l, c)
    sig[:25] = False
    ls = sig & (sgn > 0); ss = sig & (sgn < 0)
    print(f"src={src} bars={N} split={split} day-ends={dend.sum()} consensus={sig.sum()} (L{ls.sum()}/S{ss.sum()})", flush=True)
    z = np.zeros(N, bool)
    sim = lambda a, b: se.simulate_trades(df, a, b, sl_arr, tp_arr, asset=ASSET, max_hold=hold, allow_overlap=False)
    # P1 (IS only): consensus vs non-consensus days with displacement >= median consensus displacement
    med_disp = float(np.nanmedian(disp[sig & (np.arange(N) < split)]))
    comp = dend & ~sig & (disp >= med_disp) & (np.arange(N) < split) & (np.sign(c - o) != 0)
    comp[:25] = False
    sgn_c = np.sign(c - o).astype(int)
    tr_c = sim((comp & (sgn_c > 0)), (comp & (sgn_c < 0)))
    tr_s = sim(ls & (np.arange(N) < split), ss & (np.arange(N) < split))
    p1 = dict(median_disp_pip=round(med_disp / PIP, 1), consensus_is=dict(n=len(tr_s), wr=round(wr_of(tr_s), 2), exp=round(float(tr_s['pnl_pip'].mean()), 2)),
              comparison_is=dict(n=len(tr_c), wr=round(wr_of(tr_c), 2), exp=round(float(tr_c['pnl_pip'].mean()), 2)))
    p1['passes'] = p1['consensus_is']['wr'] > p1['comparison_is']['wr']
    print(f"P1 IS: consensus {p1['consensus_is']}  vs non-consensus-big-disp {p1['comparison_is']}  -> {p1['passes']}", flush=True)
    del tr_c, tr_s; gc.collect()
    tr = sim(ls, ss)
    n_all = len(tr); wr_all = wr_of(tr)
    n_long = int((tr['direction'].astype(str) == 'long').sum()); n_short = n_all - n_long
    sl_med = float(np.median(tr['sl_pip'].values)); tp_med = sl_med * K_TP / K_SL
    print(f"trades n={n_all} (L{n_long}/S{n_short}) WR={wr_all:.2f} net={tr['pnl_pip'].sum():.0f}pip", flush=True)
    lo, hi = 30, N - hold - 2; null = {}; unc_all = {}; perm_all = {}
    for side, n_sig in (('long', n_long), ('short', n_short)):
        if n_sig < 5:
            null[side] = dict(uncond_wr=50.0, perm_mean=50.0, perm_sd=0.0, perm_max=50.0, perm_k=0); continue
        unc_rows = []
        for seed in UNC_SEEDS:
            rng = np.random.default_rng(seed)
            pos = rng.choice(np.arange(lo, hi), size=min(20000, (hi - lo) // hold), replace=False)
            s_ = np.zeros(N, bool); s_[np.sort(pos)] = True
            t_ = sim(s_ if side == 'long' else z, s_ if side == 'short' else z)
            unc_rows.append((seed, wr_of(t_), len(t_))); del t_; gc.collect()
        rng = np.random.default_rng(PERM_SEED); wrs = []
        for i in range(PERM_K):
            pos = rng.choice(np.arange(lo, hi), size=n_sig, replace=False)
            s_ = np.zeros(N, bool); s_[np.sort(pos)] = True
            t_ = sim(s_ if side == 'long' else z, s_ if side == 'short' else z)
            if t_ is not None and len(t_) >= 5: wrs.append(wr_of(t_))
            del t_
            if (i + 1) % 100 == 0: gc.collect(); print(f"  perm[{side}] {i+1}/{PERM_K} …", flush=True)
        a = np.asarray(wrs, float)
        perm = dict(mean=float(a.mean()), sd=float(a.std(ddof=1)), max=float(a.max()), k=int(len(a)))
        null[side] = dict(uncond_wr=max(r[1] for r in unc_rows), perm_mean=perm['mean'], perm_sd=perm['sd'], perm_max=perm['max'], perm_k=perm['k'])
        unc_all[side] = unc_rows; perm_all[side] = perm
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=times, null=null, n_trials=N_TRIALS, split_bar=split, close=c)
    hm = tr['entry_bar'].values >= split; oos_n = int(hm.sum()); oos_wr = wr_of(tr.loc[hm]) if oos_n else None
    side_wr = {s: round(wr_of(tr[tr['direction'].astype(str) == s]), 2) for s in ('long', 'short') if (tr['direction'].astype(str) == s).sum() > 0}
    m = r.get('metrics', {})
    print(f"OOS n={oos_n} WR={oos_wr}  side WR={side_wr}")
    print(f"VERDICT: {r.get('verdict')} score={r.get('rqs2_score')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} PF={m.get('profit_factor')}")
    print(f"gates: {r.get('gates')} notes={r.get('notes')}", flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(card=f'XAUUSD-{tf}', prereg=PREREG, src=src, bars=N, split=split, hold=hold, day_ends=int(dend.sum()),
                   consensus_events=int(sig.sum()), n=n_all, n_long=n_long, n_short=n_short, wr=round(wr_all, 2), side_wr=side_wr,
                   oos_n=oos_n, oos_wr=round(oos_wr, 2) if oos_wr else None, p1=p1, sl_pip_med=round(sl_med, 2), tp_pip_med=round(tp_med, 2),
                   net_pip=round(float(tr['pnl_pip'].sum()), 1), uncond_draws=unc_all, perm=perm_all, null=null, rqs2=r),
              open(f'{OUT}/rqs2_XAUUSD-{tf}.json', 'w'), indent=1, default=str)
    tr.to_csv(f'{OUT}/trades_XAUUSD-{tf}.csv', index=False)


if __name__ == '__main__':
    run_tf(sys.argv[1])
