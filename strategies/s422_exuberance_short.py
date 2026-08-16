#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S422 — Exuberance SHORT (سلولِ آینه: روندِ صعودی + Q4-vol + شتاب) · RQS2 v2.6
================================================================================
پیش‌ثبت: results/S422_PREREGISTRATION_ExuberanceShort.md (کامیت d5ae9986)

  سیگنال (روزِ i): trend_5d > 0 ∧ vol_5d ≥ q(علّی) ∧ |ret_i| ≥ a×mean(|ret| دو روزِ قبل)
  ⇒ SHORT در openِ اولین کندلِ H1 روزِ بعد؛ خروجِ فقط-زمانی پس از hold روز؛ بدونِ استاپ.

گرید: q∈{0.70,0.75} × a∈{1.0,1.5} × hold∈{5,8} = ۸ ⇒ n_trials=8
قاعدهٔ مرگِ زودهنگام: هیچ ترکیبی exp>0 ∧ n≥30 در کشف ⇒ پنجرهٔ بکر باز نمی‌شود.

اجرا:
  python3 strategies/s422_exuberance_short.py scan
  python3 strategies/s422_exuberance_short.py lock q=.. a=.. hold=..
  python3 strategies/s422_exuberance_short.py confirm
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
    build_trading_days, daily_features, W, MIN_BARS_PER_DAY)

ASSET = 'XAUUSD'
DATA = 'data/XAUUSD_H1.csv'
SPLIT_UTC = pd.Timestamp('2020-01-01 00:00:00')
VIRTUAL_BRACKET_PIP = 20000.0
GRID_Q = (0.70, 0.75)
GRID_A = (1.0, 1.5)
GRID_HOLD = (5, 8)
N_TRIALS = 8
NULL_K = 500
NULL_SEED = 42242
OUT_DIR = 'results/_scan_S420'
LOCK_PATH = os.path.join(OUT_DIR, 'S422_LOCKED_CONFIG.json')


def signal_days(days, rets, trend, vol, q, a):
    """روزهای سیگنالِ شیدایی (SHORT). چارکِ q علّی — همان قراردادِ S420."""
    sig = []
    for i in range(W + 2, len(days) - 1):
        hist = vol[W:i]
        hist = hist[np.isfinite(hist)]
        if len(hist) < 60:
            continue
        thr = np.quantile(hist, q)
        if not (np.isfinite(trend[i]) and np.isfinite(vol[i])):
            continue
        accel = abs(rets[i]) >= a * np.mean(np.abs(rets[i - 2:i]))
        if trend[i] > 0 and vol[i] >= thr and accel:
            sig.append(i)
    return sig


def run_trades(df, days, sig_idx, hold):
    """SHORT با max_hold به‌ازای هر سیگنال + صفِ بی‌همپوشانی (قرینهٔ S420)."""
    all_tr = []
    busy_until = -1
    for i in sig_idx:
        entry_day = i + 1
        entry_bar = days[entry_day]['first_bar']
        sig_bar = entry_bar - 1
        if entry_bar <= busy_until:
            continue
        exit_day = min(entry_day + hold - 1, len(days) - 1)
        max_hold = days[exit_day]['last_bar'] - entry_bar + 1
        if max_hold < 1:
            continue
        ls = np.zeros(len(df), dtype=bool)
        ss = np.zeros(len(df), dtype=bool)
        ss[sig_bar] = True
        tr = se.simulate_trades(df, ls, ss, VIRTUAL_BRACKET_PIP, VIRTUAL_BRACKET_PIP,
                                ASSET, max_hold=max_hold, allow_overlap=False)
        if len(tr) == 0:
            continue
        busy_until = int(tr.iloc[0]['exit_bar'])
        all_tr.append(tr)
    if not all_tr:
        return pd.DataFrame()
    return pd.concat(all_tr, ignore_index=True)


def verify_no_bracket_hits(trades, df):
    c = df['close'].values
    return sum(1 for _, r in trades.iterrows()
               if abs(float(r['exit_price']) - float(c[int(r['exit_bar'])])) > 1e-9)


def build_null(df, days, n_entries, hold, lo_day, hi_day, K=NULL_K, seed=NULL_SEED):
    """جای‌گشتِ زمانیِ SHORT: pnl = (fill − close_exit)/pip − spread (مسیرِ سریعِ
    هم‌ارزِ time-exit موتور؛ slip=0 برای XAUUSD)."""
    cfg = se.ASSETS[ASSET]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    o = df['open'].values
    c = df['close'].values
    rng = np.random.default_rng(seed)
    candidates = np.arange(lo_day, hi_day - hold - 1)
    wrs = []
    for _ in range(K):
        picks = np.sort(rng.choice(candidates, size=min(n_entries * 3, len(candidates)),
                                   replace=False))
        wins = tot = 0
        busy = -1
        for i in picks:
            if tot >= n_entries:
                break
            eb = days[i + 1]['first_bar']
            if eb <= busy:
                continue
            xd = min(i + 1 + hold - 1, len(days) - 1)
            xb = days[xd]['last_bar']
            fill = o[eb] - slip * pip                     # فروش: fill پایین‌تر
            pnl = (fill - (c[xb] + slip * pip)) / pip - spread
            wins += int(pnl > 0)
            tot += 1
            busy = xb
        if tot > 0:
            wrs.append(wins / tot * 100.0)
    wrs = np.array(wrs)
    side = dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=len(wrs))
    return {'long': dict(side), 'short': side}


def windows(days):
    split_day = next(i for i, d in enumerate(days) if d['date'] >= SPLIT_UTC)
    return dict(confirm=(0, split_day), discover=(split_day, len(days)))


def run_combo(df, days, rets, trend, vol, q, a, hold, lo, hi):
    sig = [i for i in signal_days(days, rets, trend, vol, q, a)
           if lo <= i < hi - hold - 1]
    trades = run_trades(df, days, sig, hold)
    if len(trades) == 0:
        return None, trades
    p = trades['pnl_pip'].values
    n = len(trades)
    wr = float((p > 0).mean() * 100)
    exp = float(p.mean())
    sd = p.std(ddof=1)
    t = exp / (sd / np.sqrt(n)) if n > 2 and sd > 0 else 0.0
    return dict(q=q, a=a, hold=hold, n=n, wr=wr, exp_pip=exp, t=float(t),
                net_pip=float(p.sum())), trades


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def cmd_scan():
    df = se.load_data(DATA)
    days = build_trading_days(df)
    rets, trend, vol = daily_features(days)
    lo, hi = windows(days)['discover']
    print(f"[scan] discover window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    rows = []
    for q in GRID_Q:
        for a in GRID_A:
            for hold in GRID_HOLD:
                r, trades = run_combo(df, days, rets, trend, vol, q, a, hold, lo, hi)
                if r is None:
                    print(f"  q={q} a={a} hold={hold}: no trades")
                    continue
                r['proxy'] = (r['wr'] - 50.0) * np.sqrt(r['n'])
                r['bracket_hits'] = verify_no_bracket_hits(trades, df)
                rows.append(r)
                print(f"  q={q} a={a} hold={hold}: n={r['n']:3d} WR={r['wr']:5.1f}% "
                      f"exp={r['exp_pip']:+7.1f}pip t={r['t']:+5.2f} "
                      f"net={r['net_pip']:+9.0f} proxy={r['proxy']:+6.1f} "
                      f"bh={r['bracket_hits']}")
    alive = [r for r in rows if r['exp_pip'] > 0 and r['n'] >= 30]
    print(f"[scan] alive combos (exp>0 ∧ n≥30): {len(alive)}"
          + ("  → EARLY DEATH: virgin window stays closed" if not alive else ""))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'S422_scan_discover.json'), 'w') as f:
        json.dump(_clean(rows), f, indent=1, ensure_ascii=False)
    print("[scan] saved → results/_scan_S420/S422_scan_discover.json")


def cmd_lock(q, a, hold):
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = dict(strategy='S422_ExuberanceShort', asset=ASSET, data=DATA, W=W,
               q=q, a=a, hold=hold, direction='short_only',
               bracket_pip=VIRTUAL_BRACKET_PIP, n_trials=N_TRIALS,
               split_utc=str(SPLIT_UTC),
               prereg='results/S422_PREREGISTRATION_ExuberanceShort.md')
    with open(LOCK_PATH, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    print(f"[lock] frozen → {LOCK_PATH}")
    print(json.dumps(cfg, indent=1, ensure_ascii=False))


def cmd_confirm():
    with open(LOCK_PATH) as f:
        cfg = json.load(f)
    q, a, hold = cfg['q'], cfg['a'], cfg['hold']
    df = se.load_data(DATA)
    days = build_trading_days(df)
    rets, trend, vol = daily_features(days)
    lo, hi = windows(days)['confirm']
    print(f"[confirm] VIRGIN window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    print(f"[confirm] locked: q={q} a={a} hold={hold} (SHORT)")
    r, trades = run_combo(df, days, rets, trend, vol, q, a, hold, lo, hi)
    if r is None:
        print("[confirm] NO TRADES")
        return
    hits = verify_no_bracket_hits(trades, df)
    print(f"[confirm] n={r['n']} WR={r['wr']:.1f}% exp={r['exp_pip']:+.1f}pip "
          f"t={r['t']:+.2f} net={r['net_pip']:+.0f}pip bracket_hits={hits}")
    assert hits == 0
    null = build_null(df, days, r['n'], hold, lo, hi)
    print(f"[confirm] null(short): mean={null['short']['perm_mean']:.2f}% "
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
        # جریمهٔ داوطلبانهٔ بین-فرضیه‌ای (پیش‌ثبت): دومین فرضیه روی همین پنجره
        res['metrics']['efdr_cross_hypotheses'] = float(p_emp) * 2
    with open(os.path.join(OUT_DIR, 'S422_confirm_virgin_rqs2.json'), 'w') as f:
        json.dump(_clean(dict(result=res, headline=r, null=null)), f,
                  indent=1, ensure_ascii=False)
    print(f"[confirm] verdict = {res['verdict']}  score = {res['rqs2_score']}")
    print(f"[confirm] gates: {res['gates']}")
    print("[confirm] saved → results/_scan_S420/S422_confirm_virgin_rqs2.json")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    if mode == 'scan':
        cmd_scan()
    elif mode == 'lock':
        kv = dict(x.split('=') for x in sys.argv[2:])
        cmd_lock(float(kv['q']), float(kv['a']), int(kv['hold']))
    elif mode == 'confirm':
        cmd_confirm()
    else:
        raise SystemExit(f"unknown mode {mode!r}")
