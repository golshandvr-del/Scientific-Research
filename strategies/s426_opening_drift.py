#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S426 — Opening-Session Drift (ادامهٔ رانشِ K کندلِ اولِ روز تا پایانِ روز) · RQS2 v2.6
================================================================================
پیش‌ثبت: results/S426_PREREGISTRATION_OpeningDrift.md (کامیت مستقل قبل از اجرا)

  drift = close[fb+K−1] − open[fb]، نرمال با ATR_d (میانگینِ high−lowِ روزانهٔ ۲۰ روزِ قبل)
  |ndrift| ≥ θ ⇒ ورود هم‌جهت در openِ بارِ fb+K؛ خروج فقط-زمانی closeِ آخرین بارِ روز.
  حداکثر یک معامله در روز؛ خروج همان روز ⇒ هم‌پوشانی بین‌روزی ذاتاً صفر.

گرید: K∈{3,4} × θ∈{0.15,0.25} ⇒ n_trials=4
انتخاب: بیشینهٔ proxy مشروط exp>0 ∧ n≥100 ∧ WR>50.
مرگِ زودهنگام: هیچ ترکیب واجد ⇒ بکر باز نمی‌شود.

اجرا:
  python3 strategies/s426_opening_drift.py scan
  python3 strategies/s426_opening_drift.py lock K=.. theta=..
  python3 strategies/s426_opening_drift.py confirm
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                     # noqa: E402
from engine import rqs2 as rq                             # noqa: E402
from strategies.s420_capitulation_decel import (          # noqa: E402
    build_trading_days)
from strategies.s423_quiet_trend import windows, _clean   # noqa: E402

ASSET = 'XAUUSD'
DATA = 'data/XAUUSD_H1.csv'
VIRTUAL_BRACKET_PIP = 20000.0
GRID_K = (3, 4)
GRID_TH = (0.15, 0.25)
N_TRIALS = 4
ATR_D_WIN = 20
MIN_N = 100
NULL_K = 500
NULL_SEED = 42626
OUT_DIR = 'results/_scan_S420'
LOCK_PATH = os.path.join(OUT_DIR, 'S426_LOCKED_CONFIG.json')


def day_ranges(df, days):
    """دامنهٔ (high−low) هر روز — برای ATR روزانهٔ علّی."""
    h = df['high'].values
    l_ = df['low'].values
    return np.array([float(h[d['first_bar']:d['last_bar'] + 1].max() -
                           l_[d['first_bar']:d['last_bar'] + 1].min())
                     for d in days])


def signals(df, days, ranges, K, theta, lo, hi):
    """سیگنال‌های رانشِ آغازین در days[lo:hi] ⇒ (day_idx, side, entry_bar, exit_bar)."""
    o = df['open'].values
    c = df['close'].values
    out = []
    for i in range(max(lo, ATR_D_WIN), hi):
        d = days[i]
        if d['n_bars'] < K + 3:
            continue
        atr_d = ranges[i - ATR_D_WIN:i].mean()          # فقط روزهای قبل — علّی
        if atr_d <= 0:
            continue
        fb = d['first_bar']
        drift = c[fb + K - 1] - o[fb]
        if abs(drift) / atr_d < theta:
            continue
        side = 'long' if drift > 0 else 'short'
        entry_bar = fb + K
        exit_bar = d['last_bar']
        if exit_bar <= entry_bar:
            continue
        out.append((i, side, entry_bar, exit_bar))
    return out


def run_trades(df, sig):
    """هر سیگنال یک معامله؛ خروج پایانِ همان روز (per-signal max_hold)."""
    all_tr = []
    for _, side, eb, xb in sig:
        ls = np.zeros(len(df), dtype=bool)
        ss = np.zeros(len(df), dtype=bool)
        (ls if side == 'long' else ss)[eb - 1] = True    # ورود در openِ بارِ eb
        max_hold = xb - eb + 1
        tr = se.simulate_trades(df, ls, ss, VIRTUAL_BRACKET_PIP, VIRTUAL_BRACKET_PIP,
                                ASSET, max_hold=max_hold, allow_overlap=False)
        if len(tr):
            all_tr.append(tr)
    if not all_tr:
        return pd.DataFrame()
    return pd.concat(all_tr, ignore_index=True)


def verify_no_bracket_hits(trades, df):
    c = df['close'].values
    return sum(1 for _, r in trades.iterrows()
               if abs(float(r['exit_price']) - float(c[int(r['exit_bar'])])) > 1e-9)


def _null_side(df, days, n_entries, K, lo, hi, side, rng):
    """نال: روزهای تصادفی، همان ورود fb+K و خروج پایانِ روز، سمتِ ثابتِ side."""
    cfg = se.ASSETS[ASSET]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    o = df['open'].values
    c = df['close'].values
    valid = [i for i in range(max(lo, ATR_D_WIN), hi)
             if days[i]['n_bars'] >= K + 3 and days[i]['last_bar'] > days[i]['first_bar'] + K]
    wrs = []
    for _ in range(NULL_K):
        picks = rng.choice(valid, size=min(n_entries, len(valid)), replace=False)
        wins = tot = 0
        for i in picks:
            fb = days[i]['first_bar']
            eb, xb = fb + K, days[i]['last_bar']
            if side == 'long':
                pnl = ((c[xb] - slip * pip) - (o[eb] + slip * pip)) / pip - spread
            else:
                pnl = ((o[eb] - slip * pip) - (c[xb] + slip * pip)) / pip - spread
            wins += int(pnl > 0)
            tot += 1
        if tot > 0:
            wrs.append(wins / tot * 100.0)
    wrs = np.array(wrs)
    return dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=len(wrs))


def build_null(df, days, n_long, n_short, K, lo, hi, seed=NULL_SEED):
    rng = np.random.default_rng(seed)
    return {'long': _null_side(df, days, max(n_long, 5), K, lo, hi, 'long', rng),
            'short': _null_side(df, days, max(n_short, 5), K, lo, hi, 'short', rng)}


def run_combo(df, days, ranges, K, theta, lo, hi):
    sig = signals(df, days, ranges, K, theta, lo, hi)
    trades = run_trades(df, sig)
    if len(trades) == 0:
        return None, trades
    p = trades['pnl_pip'].values
    n = len(trades)
    n_long = int((trades['direction'] == 'long').sum())
    wr = float((p > 0).mean() * 100)
    exp = float(p.mean())
    sd = p.std(ddof=1)
    t = exp / (sd / np.sqrt(n)) if n > 2 and sd > 0 else 0.0
    return dict(K=K, theta=theta, n=n, n_long=n_long, n_short=n - n_long,
                wr=wr, exp_pip=exp, t=float(t), net_pip=float(p.sum())), trades


def cmd_scan():
    df = se.load_data(DATA)
    days = build_trading_days(df)
    ranges = day_ranges(df, days)
    lo, hi = windows(days)['discover']
    print(f"[scan] discover window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    rows = []
    for K in GRID_K:
        for th in GRID_TH:
            r, trades = run_combo(df, days, ranges, K, th, lo, hi)
            if r is None:
                print(f"  K={K} th={th}: no trades")
                continue
            r['proxy'] = (r['wr'] - 50.0) * np.sqrt(r['n'])
            r['bracket_hits'] = verify_no_bracket_hits(trades, df)
            rows.append(r)
            print(f"  K={K} th={th}: n={r['n']:4d} (L{r['n_long']}/S{r['n_short']}) "
                  f"WR={r['wr']:5.1f}% exp={r['exp_pip']:+7.1f}pip t={r['t']:+5.2f} "
                  f"net={r['net_pip']:+9.0f} proxy={r['proxy']:+7.1f} "
                  f"bh={r['bracket_hits']}")
    alive = [r for r in rows
             if r['exp_pip'] > 0 and r['n'] >= MIN_N and r['wr'] > 50.0]
    print(f"[scan] alive combos (exp>0 ∧ n≥{MIN_N} ∧ WR>50): {len(alive)}"
          + ("  → EARLY DEATH: virgin stays closed" if not alive else ""))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'S426_scan_discover.json'), 'w') as f:
        json.dump(_clean(rows), f, indent=1, ensure_ascii=False)
    print("[scan] saved → results/_scan_S420/S426_scan_discover.json")


def cmd_lock(K, theta):
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = dict(strategy='S426_OpeningDrift', asset=ASSET, data=DATA,
               K=K, theta=theta, atr_d_win=ATR_D_WIN,
               direction='both_symmetric_intraday',
               bracket_pip=VIRTUAL_BRACKET_PIP, n_trials=N_TRIALS,
               split_utc='2020-01-01 00:00:00',
               prereg='results/S426_PREREGISTRATION_OpeningDrift.md')
    with open(LOCK_PATH, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    print(f"[lock] frozen → {LOCK_PATH}")
    print(json.dumps(cfg, indent=1, ensure_ascii=False))


def cmd_confirm():
    with open(LOCK_PATH) as f:
        cfg = json.load(f)
    K, theta = cfg['K'], cfg['theta']
    df = se.load_data(DATA)
    days = build_trading_days(df)
    ranges = day_ranges(df, days)
    lo, hi = windows(days)['confirm']
    print(f"[confirm] VIRGIN window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    print(f"[confirm] locked: K={K} theta={theta}")
    r, trades = run_combo(df, days, ranges, K, theta, lo, hi)
    if r is None:
        print("[confirm] NO TRADES")
        return
    hits = verify_no_bracket_hits(trades, df)
    print(f"[confirm] n={r['n']} (L{r['n_long']}/S{r['n_short']}) WR={r['wr']:.1f}% "
          f"exp={r['exp_pip']:+.1f}pip t={r['t']:+.2f} "
          f"net={r['net_pip']:+.0f}pip bracket_hits={hits}")
    assert hits == 0
    null = build_null(df, days, r['n_long'], r['n_short'], K, lo, hi)
    print(f"[confirm] null: long mean={null['long']['perm_mean']:.2f}% "
          f"sd={null['long']['perm_sd']:.2f} | "
          f"short mean={null['short']['perm_mean']:.2f}% "
          f"sd={null['short']['perm_sd']:.2f} k={null['short']['perm_k']}")
    split_bar = days[lo + int((hi - lo) * 0.60)]['first_bar']
    res = rq.compute_rqs2(
        trades, ASSET,
        sl_pip=VIRTUAL_BRACKET_PIP, tp_pip=VIRTUAL_BRACKET_PIP,
        bar_time=df['time'].values, null=null, n_trials=N_TRIALS,
        split_bar=split_bar, close=df['close'].values,
    )
    p_emp = res['metrics'].get('skill_p_perm')
    if p_emp is not None:
        # جریمهٔ داوطلبانهٔ بین-فرضیه‌ای: پنجمین فرضیه روی این پنجره
        res['metrics']['efdr_cross_hypotheses'] = float(p_emp) * 5
    with open(os.path.join(OUT_DIR, 'S426_confirm_virgin_rqs2.json'), 'w') as f:
        json.dump(_clean(dict(result=res, headline=r, null=null)), f,
                  indent=1, ensure_ascii=False)
    print(f"[confirm] verdict = {res['verdict']}  score = {res['rqs2_score']}")
    print(f"[confirm] gates: {res['gates']}")
    print("[confirm] saved → results/_scan_S420/S426_confirm_virgin_rqs2.json")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    if mode == 'scan':
        cmd_scan()
    elif mode == 'lock':
        kv = dict(x.split('=') for x in sys.argv[2:])
        cmd_lock(int(kv['K']), float(kv['theta']))
    elif mode == 'confirm':
        cmd_confirm()
    else:
        raise SystemExit(f"unknown mode {mode!r}")
