#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S424 — Quiet-Trend Breakout (S423 + تأییدِ شکستِ هم‌جهت) · RQS2 v2.6
================================================================================
پیش‌ثبت: results/S424_PREREGISTRATION_QuietTrendBreakout.md (کامیت مستقل قبل از اجرا)

پایهٔ منجمد از قفلِ S423: qlow=0.30, m=0.0, hold=5 — تیون نمی‌شود.
اهرمِ جدید (تنها متغیر): B ∈ {3,5,10} — تأیید شکست:
  LONG : سیگنالِ S423-long  ∧ close_i > max(close[i-B:i])
  SHORT: سیگنالِ S423-short ∧ close_i < min(close[i-B:i])

قانونِ انتخاب: بیشینهٔ proxy مشروط exp>0 ∧ n≥30 ∧ WR>50 ∧ exp > expِ پایهٔ بدونِ فیلتر.
مرگِ زودهنگام: هیچ B واجد ⇒ پنجرهٔ بکر باز نمی‌شود.

اجرا:
  python3 strategies/s424_quiet_trend_breakout.py scan
  python3 strategies/s424_quiet_trend_breakout.py lock B=..
  python3 strategies/s424_quiet_trend_breakout.py confirm
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
    build_trading_days, daily_features, W)
from strategies.s423_quiet_trend import (                 # noqa: E402
    signal_days as s423_signal_days, run_trades, verify_no_bracket_hits,
    build_null, windows, _clean)

ASSET = 'XAUUSD'
DATA = 'data/XAUUSD_H1.csv'
# پایهٔ منجمد از S423 (پیش‌ثبت §2 — بدونِ تیون)
QLOW, M, HOLD = 0.30, 0.0, 5
GRID_B = (3, 5, 10)
N_TRIALS = 3
NULL_SEED = 42424
OUT_DIR = 'results/_scan_S420'
LOCK_PATH = os.path.join(OUT_DIR, 'S424_LOCKED_CONFIG.json')


def breakout_filter(days, sig, B):
    """فیلترِ شکستِ هم‌جهت — فقط رخدادهایی که close روزِ سیگنال از رکوردِ B روزِ قبل عبور کرده."""
    closes = np.array([d['close'] for d in days])
    out = []
    for i, side in sig:
        if i - B < 0:
            continue
        prior = closes[i - B:i]
        if side == 'long' and closes[i] > prior.max():
            out.append((i, side))
        elif side == 'short' and closes[i] < prior.min():
            out.append((i, side))
    return out


def run_combo(df, days, rets, trend, vol, B, lo, hi, filtered=True):
    sig = [(i, s) for i, s in s423_signal_days(days, rets, trend, vol, QLOW, M)
           if lo <= i < hi - HOLD - 1]
    if filtered:
        sig = breakout_filter(days, sig, B)
    trades = run_trades(df, days, sig, HOLD)
    if len(trades) == 0:
        return None, trades
    p = trades['pnl_pip'].values
    n = len(trades)
    n_long = int((trades['direction'] == 'long').sum())
    wr = float((p > 0).mean() * 100)
    exp = float(p.mean())
    sd = p.std(ddof=1)
    t = exp / (sd / np.sqrt(n)) if n > 2 and sd > 0 else 0.0
    return dict(B=(B if filtered else None), n=n, n_long=n_long, n_short=n - n_long,
                wr=wr, exp_pip=exp, t=float(t), net_pip=float(p.sum())), trades


def cmd_scan():
    df = se.load_data(DATA)
    days = build_trading_days(df)
    rets, trend, vol = daily_features(days)
    lo, hi = windows(days)['discover']
    print(f"[scan] discover window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    # خطِ پایهٔ بدونِ فیلتر (مرجعِ قانونِ انتخاب — خودش کاندید نیست)
    base, _ = run_combo(df, days, rets, trend, vol, 0, lo, hi, filtered=False)
    print(f"  BASE (no filter): n={base['n']:3d} WR={base['wr']:5.1f}% "
          f"exp={base['exp_pip']:+7.1f}pip net={base['net_pip']:+9.0f}")
    rows = [dict(base, role='baseline')]
    for B in GRID_B:
        r, trades = run_combo(df, days, rets, trend, vol, B, lo, hi)
        if r is None:
            print(f"  B={B}: no trades")
            continue
        r['proxy'] = (r['wr'] - 50.0) * np.sqrt(r['n'])
        r['bracket_hits'] = verify_no_bracket_hits(trades, df)
        r['beats_base'] = bool(r['exp_pip'] > base['exp_pip'])
        r['role'] = 'candidate'
        rows.append(r)
        print(f"  B={B:2d}: n={r['n']:3d} (L{r['n_long']}/S{r['n_short']}) "
              f"WR={r['wr']:5.1f}% exp={r['exp_pip']:+7.1f}pip t={r['t']:+5.2f} "
              f"net={r['net_pip']:+9.0f} proxy={r['proxy']:+6.1f} "
              f"beats_base={r['beats_base']} bh={r['bracket_hits']}")
    alive = [r for r in rows if r.get('role') == 'candidate'
             and r['exp_pip'] > 0 and r['n'] >= 30 and r['wr'] > 50.0
             and r['beats_base']]
    print(f"[scan] alive combos (exp>0 ∧ n≥30 ∧ WR>50 ∧ beats_base): {len(alive)}"
          + ("  → EARLY DEATH: virgin window stays closed" if not alive else ""))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'S424_scan_discover.json'), 'w') as f:
        json.dump(_clean(rows), f, indent=1, ensure_ascii=False)
    print("[scan] saved → results/_scan_S420/S424_scan_discover.json")


def cmd_lock(B):
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = dict(strategy='S424_QuietTrendBreakout', asset=ASSET, data=DATA, W=W,
               qlow=QLOW, m=M, hold=HOLD, B=B, direction='both_symmetric',
               base_inherited_from='results/_scan_S420/S423_LOCKED_CONFIG.json',
               bracket_pip=20000.0, n_trials=N_TRIALS,
               split_utc='2020-01-01 00:00:00',
               prereg='results/S424_PREREGISTRATION_QuietTrendBreakout.md')
    with open(LOCK_PATH, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    print(f"[lock] frozen → {LOCK_PATH}")
    print(json.dumps(cfg, indent=1, ensure_ascii=False))


def cmd_confirm():
    with open(LOCK_PATH) as f:
        cfg = json.load(f)
    B = cfg['B']
    df = se.load_data(DATA)
    days = build_trading_days(df)
    rets, trend, vol = daily_features(days)
    lo, hi = windows(days)['confirm']
    print(f"[confirm] VIRGIN window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    print(f"[confirm] locked: base(qlow={QLOW},m={M},hold={HOLD}) + B={B}")
    r, trades = run_combo(df, days, rets, trend, vol, B, lo, hi)
    if r is None:
        print("[confirm] NO TRADES")
        return
    hits = verify_no_bracket_hits(trades, df)
    print(f"[confirm] filtered: n={r['n']} (L{r['n_long']}/S{r['n_short']}) "
          f"WR={r['wr']:.1f}% exp={r['exp_pip']:+.1f}pip t={r['t']:+.2f} "
          f"net={r['net_pip']:+.0f}pip bracket_hits={hits}")
    assert hits == 0
    # مقایسهٔ جفتیِ الزامیِ پیش‌ثبت §4: زیرمجموعهٔ فیلترشده در برابرِ مکمل
    sig_all = [(i, s) for i, s in s423_signal_days(days, rets, trend, vol, QLOW, M)
               if lo <= i < hi - HOLD - 1]
    sig_f = set(breakout_filter(days, sig_all, B))
    sig_c = [x for x in sig_all if x not in sig_f]
    comp_trades = run_trades(df, days, sig_c, HOLD)
    comp = None
    if len(comp_trades):
        pc = comp_trades['pnl_pip'].values
        comp = dict(n=len(comp_trades), wr=float((pc > 0).mean() * 100),
                    exp_pip=float(pc.mean()), net_pip=float(pc.sum()))
        print(f"[confirm] complement (non-breakout): n={comp['n']} "
              f"WR={comp['wr']:.1f}% exp={comp['exp_pip']:+.1f}pip "
              f"net={comp['net_pip']:+.0f}pip")
    null = build_null(df, days, r['n_long'], r['n_short'], HOLD, lo, hi,
                      seed=NULL_SEED)
    print(f"[confirm] null: long mean={null['long']['perm_mean']:.2f}% "
          f"sd={null['long']['perm_sd']:.2f} | "
          f"short mean={null['short']['perm_mean']:.2f}% "
          f"sd={null['short']['perm_sd']:.2f} k={null['short']['perm_k']}")
    split_bar = days[lo + int((hi - lo) * 0.60)]['first_bar']
    res = rq.compute_rqs2(
        trades, ASSET,
        sl_pip=20000.0, tp_pip=20000.0,
        bar_time=df['time'].values, null=null, n_trials=N_TRIALS,
        split_bar=split_bar, close=df['close'].values,
    )
    p_emp = res['metrics'].get('skill_p_perm')
    if p_emp is not None:
        # جریمهٔ داوطلبانهٔ بین-فرضیه‌ای (پیش‌ثبت §4): چهارمین فرضیه روی این پنجره
        res['metrics']['efdr_cross_hypotheses'] = float(p_emp) * 4
    with open(os.path.join(OUT_DIR, 'S424_confirm_virgin_rqs2.json'), 'w') as f:
        json.dump(_clean(dict(result=res, headline=r, complement=comp, null=null)),
                  f, indent=1, ensure_ascii=False)
    print(f"[confirm] verdict = {res['verdict']}  score = {res['rqs2_score']}")
    print(f"[confirm] gates: {res['gates']}")
    print("[confirm] saved → results/_scan_S420/S424_confirm_virgin_rqs2.json")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    if mode == 'scan':
        cmd_scan()
    elif mode == 'lock':
        kv = dict(x.split('=') for x in sys.argv[2:])
        cmd_lock(int(kv['B']))
    elif mode == 'confirm':
        cmd_confirm()
    else:
        raise SystemExit(f"unknown mode {mode!r}")
