# -*- coding: utf-8 -*-
"""
S835 — لایه «ماندگاریِ بازدهِ درون‌روزیِ ۱۰ روزه (Intraday-Return Momentum, Symmetric)» XAUUSD-H1 — آزمون نهایی مسیر C
=====================================================================================================
پیش‌ثبت: results/S835_PREREG_INTRADAY_MOMENTUM_HOLDOUT.md (کامیت 4a7f3c7c — قبل از این آزمون)
هندسه‌ی منجمد (هیچ عددی قابل تغییر نیست):
    ID_d = close(last H1 of day) − open(first H1 of day) ; σ_d = median20(daily range)
    z_d = Σ_{10} ID / (σ_d·√10) ; رخداد |z|>0.5 پس از ۶۰ روز ; long z>0 / short z<0 (آینه‌ای)
    سیگنال روی آخرین کندلِ روز ⇒ ورود openِ کندلِ بعد ; SL=1.0×σ_d ، TP=1.3×SL ، hold=72
    no-overlap ، بدون trail/BE ، split_bar=54798 (2020-05-27)
فازها:
    --null  : نالِ جای‌گشتیِ جهت K=500 (seed=835835) روی کندل‌های سیگنالِ هولد‌اوت
    --judge : یک (۱) آزمون compute_rqs2 (n_trials=1) ⇒ S835_HOLDOUT_SPENT.lock
اجرا: python3 strategies/s835_er_lock_cont.py --null سپس --judge
"""
import sys, os, json, argparse
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

OUT_DIR = 'results/_scan_S835'
SPLIT_IDX = 54798
N_DAYS, K, WARM_D = 10, 0.5, 60
SLM, RR, HOLD = 1.0, 1.3, 72
N_PERM = 500
SEED = 835835
PREREG = '4a7f3c7c'


def build_features(df):
    t = df['time'].values.astype(np.int64)
    o = df['open'].values.astype(np.float64); c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64); l = df['low'].values.astype(np.float64)
    n = len(df)
    day = t // 86400
    first = np.concatenate([[True], day[1:] != day[:-1]])
    last = np.concatenate([day[1:] != day[:-1], [True]])
    fidx = np.where(first)[0]; lidx = np.where(last)[0]
    D = len(fidx)
    ID = c[lidx] - o[fidx]
    drange = np.array([h[a:b+1].max() - l[a:b+1].min() for a, b in zip(fidx, lidx)])
    sigma = pd.Series(drange).rolling(20).median().values
    z = pd.Series(ID).rolling(N_DAYS).sum().values / (sigma * np.sqrt(N_DAYS))
    ev = (np.abs(z) > K) & np.isfinite(z)
    ev[:WARM_D] = False
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    dl = np.where(ev & (z > 0))[0]; ds = np.where(ev & (z < 0))[0]
    dl = dl[dl < D - 1]; ds = ds[ds < D - 1]
    ls[lidx[dl]] = True; ss[lidx[ds]] = True
    sig_sigma = np.full(n, np.nan); sig_sigma[lidx] = sigma
    sl_pip = np.clip(np.nan_to_num(sig_sigma, nan=1.0) * SLM / se.ASSETS['XAUUSD']['pip'], 8, 5000)
    tp_pip = sl_pip * RR
    return ls, ss, sl_pip, tp_pip


def run_strategy(df, ls, ss, sl_pip, tp_pip):
    return se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                              asset='XAUUSD', max_hold=HOLD, allow_overlap=False)


def phase_null(df, ls, ss, sl_pip, tp_pip):
    tr = run_strategy(df, ls, ss, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX]
    sig_bars = hold['signal_bar'].values.astype(int)
    n = len(sig_bars)
    print(f'[null] holdout signal bars: n={n}', flush=True)
    rng = np.random.default_rng(SEED)
    wrs = []
    for kk in range(N_PERM):
        dirs = rng.integers(0, 2, size=n).astype(bool)
        lmask = np.zeros(len(df), bool); lmask[sig_bars[dirs]] = True
        smask = np.zeros(len(df), bool); smask[sig_bars[~dirs]] = True
        ptr = se.simulate_trades(df, lmask, smask, sl_pip=sl_pip, tp_pip=tp_pip,
                                 asset='XAUUSD', max_hold=HOLD, allow_overlap=False)
        if len(ptr) > 0:
            wrs.append(float((ptr['pnl_pip'].values > 0).mean() * 100))
        if (kk + 1) % 100 == 0:
            print(f'  [null] perm {kk+1}/{N_PERM}', flush=True)
    wrs = np.array(wrs)
    side = dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=int(len(wrs)))
    null = {'long': dict(side), 'short': dict(side)}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 's835_null_holdout.json'), 'w') as f:
        json.dump(null, f, indent=1)
    print(f'[null] mean={side["perm_mean"]:.2f}% sd={side["perm_sd"]:.2f} '
          f'max={side["perm_max"]:.2f}% k={side["perm_k"]}', flush=True)
    return null


def phase_judge(df, ls, ss, sl_pip, tp_pip):
    lock = os.path.join(OUT_DIR, 'S835_HOLDOUT_SPENT.lock')
    if os.path.exists(lock):
        print('⛔ هولد‌اوت S835 قبلاً مصرف شده — آزمون دوم ممنوع است (مسیر C).')
        return None
    with open(os.path.join(OUT_DIR, 's835_null_holdout.json')) as f:
        null = json.load(f)
    tr = run_strategy(df, ls, ss, sl_pip, tp_pip)
    hold = tr[tr['entry_bar'].values >= SPLIT_IDX].reset_index(drop=True)
    pnl = hold['pnl_pip'].values
    wr = float((pnl > 0).mean() * 100)
    w = pnl[pnl > 0].sum(); lo = -pnl[pnl < 0].sum()
    pf = float(w / lo) if lo > 0 else float('inf')
    nl = int((hold['direction'].values == 'long').sum())
    print(f'[judge] holdout trades={len(hold)} (L={nl} S={len(hold)-nl})  '
          f'WR={wr:.2f}%  PF={pf:.3f}  exp={pnl.mean():+.2f}pip  '
          f'perm_mean={null["long"]["perm_mean"]:.2f}%  '
          f'lift={wr - null["long"]["perm_mean"]:+.2f}pp', flush=True)
    med_sl = float(np.median(hold['sl_pip'].values))
    med_tp = med_sl * RR
    r = rqs2.compute_rqs2(
        hold, 'XAUUSD',
        sl_pip=med_sl, tp_pip=med_tp,
        bar_time=df['time'].values, null=null, n_trials=1,
        split_bar=SPLIT_IDX, close=df['close'].values)
    with open(lock, 'w') as f:
        f.write(f'S835 holdout spent — one test only (path C), prereg {PREREG}\n')
    res = dict(layer='S835', card='XAUUSD-H1', prereg=PREREG,
               geometry=dict(n_days=N_DAYS, k=K, slm_sigma_d=SLM, rr=RR, hold=HOLD),
               n_holdout=len(hold), n_long=nl, n_short=len(hold)-nl,
               wr_holdout=wr, pf_holdout=pf, exp_pip=float(pnl.mean()),
               verdict=r['verdict'], score=r['rqs2_score'], gates=r['gates'],
               notes=r.get('notes'))
    with open(os.path.join(OUT_DIR, 's835_judgment_h1.json'), 'w') as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--null', action='store_true')
    ap.add_argument('--judge', action='store_true')
    a = ap.parse_args()
    d = fd.load_fast('XAUUSD', 'H1')
    assert 'mt5_full' in d['src'], f'E-16 trap: {d["src"]}'
    df = fd.as_dataframe(d)
    print('src:', d['src'])
    assert len(df) > SPLIT_IDX
    ls, ss, sl_pip, tp_pip = build_features(df)
    print(f'events: total L={int(ls.sum())} S={int(ss.sum())} | '
          f'explore L={int(ls[:SPLIT_IDX].sum())} S={int(ss[:SPLIT_IDX].sum())} | '
          f'holdout L={int(ls[SPLIT_IDX:].sum())} S={int(ss[SPLIT_IDX:].sum())}', flush=True)
    if a.null:
        phase_null(df, ls, ss, sl_pip, tp_pip)
    if a.judge:
        phase_judge(df, ls, ss, sl_pip, tp_pip)


if __name__ == '__main__':
    main()
