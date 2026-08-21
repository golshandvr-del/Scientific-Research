# -*- coding: utf-8 -*-
"""
S515 — رویداد انبساط نوسان M30 با خروج زمانی (V-TIME)
================================================================================
پیش‌ثبت: `results/S515_PREREG_M30_VOLEVENT_TIMEEXIT.md` (commit قبل از هر آزمون).
سیگنال منجمد: atr_fib_55 cross↑q90(کشف) / LONG. خروج: close[e+k] + براکت
متقارن نادر-فعال SL=TP=q98(|MFE_k|∪|MAE_k|) از کشف (الگوی S560).
خانواده: فقط k ∈ {2,4,8,16,32}. انتخاب: بیشترین t کشف. داوری: یک compute_rqs2.

شبیه‌ساز جدید ⇒ اثبات parity اجباری در برابر مرجع مستقل کند.

اجرا:  python3 strategies/s515_voltime.py --stage parity|sweep|null|judge
"""
import sys
import os
import json
import argparse

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import rqs2 as R                                        # noqa: E402
from engine import indicator_bank as ib                             # noqa: E402
from tools.s434_fast_data import as_dataframe                       # noqa: E402
from strategies.s511_gross_census import (                          # noqa: E402
    cross_above, load_card, SPLIT_FRAC, WARMUP, Q_HI, PIP, COST_PIP)

SEED = 20260821
K_PERM = 2000
N_TRIALS = 5009
TF = 'M30'
OUT = 'results/_scan_S515'
IND = 'atr_fib_55'
K_GRID = (2, 4, 8, 16, 32)
MIN_N = 100
Q_BRACKET = 0.98


# ── شبیه‌ساز V-TIME (numba) ────────────────────────────────────────────────
@njit(cache=True)
def _sim_vtime(high, low, close, sig_idx, hold_k, br_abs):
    """LONG: ورود close[e]؛ اسکن e+1..e+hold_k برای براکت متقارن (SL مقدم)؛
    وگرنه خروج close[e+hold_k]. non-overlap. حذف معاملهٔ باز در انتهای داده."""
    n = close.shape[0]
    m = sig_idx.shape[0]
    eb = np.empty(m, np.int64)
    xb = np.empty(m, np.int64)
    px = np.empty(m, np.float64)   # pnl absolute
    kind = np.empty(m, np.int64)   # 0=time, 1=tp, 2=sl
    cnt = 0
    busy_until = -1
    for i in range(m):
        e = sig_idx[i]
        if e <= busy_until:
            continue
        if e + hold_k >= n:
            continue                      # معاملهٔ باز در انتهای داده — حذف
        entry = close[e]
        sl_lvl = entry - br_abs
        tp_lvl = entry + br_abs
        exit_bar = e + hold_k
        pnl = close[e + hold_k] - entry
        knd = 0
        for b in range(e + 1, e + hold_k + 1):
            hit_sl = low[b] <= sl_lvl
            hit_tp = high[b] >= tp_lvl
            if hit_sl:                     # اولویت SL در کندل مبهم
                exit_bar = b
                pnl = -br_abs
                knd = 2
                break
            if hit_tp:
                exit_bar = b
                pnl = br_abs
                knd = 1
                break
        eb[cnt] = e
        xb[cnt] = exit_bar
        px[cnt] = pnl
        kind[cnt] = knd
        cnt += 1
        busy_until = exit_bar
    return eb[:cnt], xb[:cnt], px[:cnt], kind[:cnt]


def sim_vtime(d, sig_idx, hold_k, br_abs):
    eb, xb, px, kind = _sim_vtime(d['high'], d['low'], d['close'],
                                  np.asarray(sig_idx, np.int64),
                                  int(hold_k), float(br_abs))
    pnl_pip = px / PIP - COST_PIP
    return pd.DataFrame(dict(
        entry_bar=eb, exit_bar=xb, pnl_pip=pnl_pip,
        outcome=np.where(pnl_pip > 0, 'win', 'loss'),
        sl_pip=np.full(len(eb), br_abs / PIP),
        tp_pip=np.full(len(eb), br_abs / PIP),
        exit_kind=kind, direction='long'))


def sim_vtime_slow(d, sig_idx, hold_k, br_abs):
    """مرجع مستقل کند — پیاده‌سازی دوم برای اثبات parity."""
    high, low, close = d['high'], d['low'], d['close']
    n = len(close)
    rows = []
    busy = -1
    for e in sig_idx:
        if e <= busy:
            continue
        if e + hold_k >= n:
            continue
        entry = close[e]
        exit_bar, pnl = e + hold_k, close[e + hold_k] - entry
        for b in range(e + 1, e + hold_k + 1):
            if low[b] <= entry - br_abs:
                exit_bar, pnl = b, -br_abs
                break
            if high[b] >= entry + br_abs:
                exit_bar, pnl = b, br_abs
                break
        rows.append((e, exit_bar, pnl))
        busy = exit_bar
    return rows


def build_context():
    d = load_card(TF)
    n = d['n_bars']
    split = int(SPLIT_FRAC * n)
    df_full = as_dataframe({k: d[k] for k in
                            ('time', 'open', 'high', 'low', 'close', 'volume')})
    x = ib.compute(IND, df_full).to_numpy()
    x[:WARMUP] = np.nan
    thr = float(np.nanquantile(x[:split], Q_HI))
    sig_bool = np.nan_to_num(cross_above(x, thr), nan=False).astype(bool)
    sig_bool[:WARMUP] = False
    return dict(d=d, n=n, split=split, half=split // 2, thr=thr,
                sig_bool=sig_bool)


def bracket_from_discovery(d, sig_idx_disc, hold_k, split):
    """SL=TP=q98(|MFE_k| ∪ |MAE_k|) فقط از پنجرهٔ کشف (بدون براکت)."""
    high, low, close = d['high'], d['low'], d['close']
    exts = []
    for e in sig_idx_disc:
        if e + hold_k >= split:
            continue
        entry = close[e]
        seg_h = high[e + 1:e + hold_k + 1].max()
        seg_l = low[e + 1:e + hold_k + 1].min()
        exts.append(abs(seg_h - entry))
        exts.append(abs(entry - seg_l))
    return float(np.quantile(np.asarray(exts), Q_BRACKET))


def stage_parity():
    ctx = build_context()
    d, split = ctx['d'], ctx['split']
    sig_idx = np.flatnonzero(ctx['sig_bool'][:split])
    report = {}
    ok = True
    for hold_k, br in ((4, 3.0), (16, 8.0)):        # دو پیکربندی
        fast = sim_vtime({k: d[k][:split] for k in ('high', 'low', 'close')},
                         sig_idx, hold_k, br)
        slow = sim_vtime_slow({k: d[k][:split] for k in
                               ('high', 'low', 'close')}, sig_idx, hold_k, br)
        same = (len(fast) == len(slow))
        if same:
            for i, (e, x, p) in enumerate(slow):
                if fast['entry_bar'].iat[i] != e or \
                   fast['exit_bar'].iat[i] != x or \
                   abs((fast['pnl_pip'].iat[i] + COST_PIP) * PIP - p) > 1e-9:
                    same = False
                    break
        report[f'k{hold_k}_br{br}'] = dict(n_fast=len(fast), n_slow=len(slow),
                                           identical=bool(same))
        ok = ok and same
        print(f'  parity k={hold_k} br={br}: n={len(fast)}/{len(slow)} '
              f'{"IDENTICAL" if same else "MISMATCH"}', flush=True)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/parity.json', 'w') as f:
        json.dump(dict(passed=ok, cases=report), f, ensure_ascii=False)
    print(f'[PARITY] {"PASSED" if ok else "FAILED"} -> {OUT}/parity.json')
    if not ok:
        raise SystemExit(1)


def t_stat(pnl):
    if len(pnl) < 2:
        return float('nan')
    return float(pnl.mean() / (pnl.std(ddof=1) / np.sqrt(len(pnl))))


def stage_sweep():
    with open(f'{OUT}/parity.json') as f:
        if not json.load(f)['passed']:
            raise SystemExit('parity FAILED — sweep ممنوع')
    ctx = build_context()
    d, split, half = ctx['d'], ctx['split'], ctx['half']
    d_disc = {k: d[k][:split] for k in ('high', 'low', 'close')}
    sig_idx = np.flatnonzero(ctx['sig_bool'][:split])
    print(f"[SWEEP] thr={ctx['thr']:.5g} n_sig_disc={len(sig_idx)}", flush=True)

    rows = []
    for hold_k in K_GRID:
        br = bracket_from_discovery(d, sig_idx, hold_k, split)
        tr = sim_vtime(d_disc, sig_idx, hold_k, br)
        pnl = tr['pnl_pip'].to_numpy()
        m1 = tr['entry_bar'].to_numpy() < half
        n1p = float(pnl[m1].mean()) if m1.any() else None
        n2p = float(pnl[~m1].mean()) if (~m1).any() else None
        row = dict(k=hold_k, br_abs=br, br_pip=br / PIP, n=len(tr),
                   net=float(pnl.mean()), t=t_stat(pnl),
                   net1=n1p, net2=n2p,
                   wr=100.0 * float((tr['outcome'] == 'win').mean()),
                   time_exit_pct=100.0 * float((tr['exit_kind'] == 0).mean()),
                   valid=bool(len(tr) >= MIN_N and n1p is not None
                              and n2p is not None and n1p > 0 and n2p > 0))
        rows.append(row)
        print(f"  k={hold_k:2d}: br={row['br_pip']:.1f}pip n={row['n']} "
              f"wr={row['wr']:.2f}% net={row['net']:+.3f} t={row['t']:+.2f} "
              f"time_exit={row['time_exit_pct']:.0f}% "
              f"{'VALID' if row['valid'] else '-'}", flush=True)

    valid = [r for r in rows if r['valid']]
    valid.sort(key=lambda r: -r['t'])
    winner = valid[0] if valid else None
    with open(f'{OUT}/sweep.json', 'w') as f:
        json.dump(dict(thr=ctx['thr'], split=split, rows=rows,
                       n_valid=len(valid), winner=winner, seed=SEED),
                  f, ensure_ascii=False)
    if winner:
        print(f"[SWEEP] WINNER: k={winner['k']} t={winner['t']:+.2f} "
              f"n={winner['n']} net={winner['net']:+.3f}", flush=True)
    else:
        print('[SWEEP] هیچ بازوی معتبری نیست ⇒ REJECT-by-rule', flush=True)
    print(f'saved -> {OUT}/sweep.json')


def stage_null():
    with open(f'{OUT}/sweep.json') as f:
        S = json.load(f)
    w = S['winner']
    if not w:
        raise SystemExit('no winner')
    ctx = build_context()
    d, n = ctx['d'], ctx['n']
    hold_k, br = int(w['k']), float(w['br_abs'])
    sig_idx = np.flatnonzero(ctx['sig_bool'])
    tr = sim_vtime(d, sig_idx, hold_k, br)
    obs_wr = 100.0 * float((tr['outcome'] == 'win').mean())
    print(f'[NULL] k={hold_k} br={br/PIP:.1f}pip: n_sig={len(sig_idx)} '
          f'n_tr={len(tr)} wr={obs_wr:.2f}%', flush=True)

    uncond_rows = []
    for stride in (1, 3, 7):
        idx = np.arange(WARMUP, n - hold_k - 1, stride, dtype=np.int64)
        t0 = sim_vtime(d, idx, hold_k, br)
        wr0 = 100.0 * float((t0['outcome'] == 'win').mean()) if len(t0) else None
        uncond_rows.append((stride, wr0, len(t0)))
        print(f'  uncond stride={stride}: n={len(t0)} wr={wr0:.2f}%', flush=True)
    uncond_wr = max(r[1] for r in uncond_rows if r[1] is not None)

    rng = np.random.default_rng(SEED)
    space = np.arange(WARMUP, n - hold_k - 1, dtype=np.int64)
    wrs = []
    for k in range(K_PERM):
        pos = np.sort(rng.choice(space, size=min(len(sig_idx), len(space)),
                                 replace=False))
        tp_ = sim_vtime(d, pos, hold_k, br)
        if len(tp_) >= 30:
            wrs.append(100.0 * float((tp_['outcome'] == 'win').mean()))
        if (k + 1) % 400 == 0:
            print(f'  perm {k+1}/{K_PERM}', flush=True)
    arr = np.asarray(wrs, float)
    perm = dict(mean=float(arr.mean()), sd=float(arr.std(ddof=1)),
                max=float(arr.max()), k=int(len(arr)))
    z = (obs_wr - perm['mean']) / perm['sd'] if perm['sd'] > 0 else float('nan')
    p_exact = float((arr >= obs_wr - 1e-9).mean())
    print(f"  perm: mean={perm['mean']:.2f} sd={perm['sd']:.2f} "
          f"max={perm['max']:.2f}  z={z:.2f}  P(perm>=obs)={p_exact:.4f}",
          flush=True)

    side_null = dict(uncond_wr=uncond_wr, perm_mean=perm['mean'],
                     perm_sd=perm['sd'], perm_max=perm['max'],
                     perm_k=perm['k'])
    empty = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
    with open(f'{OUT}/null.json', 'w') as f:
        json.dump(dict(winner=w, obs_wr=obs_wr, n_trades=len(tr),
                       uncond=uncond_rows, perm=perm, p_exact=p_exact,
                       null={'long': side_null, 'short': empty},
                       seed=SEED, k=K_PERM, z_preview=z),
                  f, ensure_ascii=False)
    print(f'saved -> {OUT}/null.json')


def stage_judge():
    with open(f'{OUT}/null.json') as f:
        nm = json.load(f)
    w = nm['winner']
    ctx = build_context()
    d, split = ctx['d'], ctx['split']
    hold_k, br = int(w['k']), float(w['br_abs'])
    tr = sim_vtime(d, np.flatnonzero(ctx['sig_bool']), hold_k, br)
    tr2 = tr.drop(columns=['exit_kind'])

    res = R.compute_rqs2(tr2, 'XAUUSD', sl_pip=br / PIP, tp_pip=br / PIP,
                         bar_time=d['time'], close=d['close'],
                         null=nm['null'], n_trials=N_TRIALS, split_bar=split)
    tag = f'S515_M30_{IND}_vtime_k{hold_k}'
    print(R.format_rqs2(tag, res))
    with open(f'{OUT}/rqs2.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/trades.csv', index=False)
    print(f'saved -> {OUT}/rqs2.json + trades.csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', required=True,
                    choices=['parity', 'sweep', 'null', 'judge'])
    args = ap.parse_args()
    {'parity': stage_parity, 'sweep': stage_sweep,
     'null': stage_null, 'judge': stage_judge}[args.stage]()
