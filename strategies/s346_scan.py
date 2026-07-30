# -*- coding: utf-8 -*-
"""
S346 — اسکنِ مولتی‌تایم‌فریمِ «کانالِ ATR تطبیقی» با داوریِ RQS+
================================================================================
قانونِ MTF (قانونِ اولِ پروژه): هر لایه روی **هر** TF و **هر دو جفت‌ارز** جداگانه
تست و گزارش می‌شود. قانونِ «اندک اندک»: نتیجهٔ هر کارت به‌صورتِ JSON مستقل و
بلافاصله روی دیسک ذخیره می‌شود تا ریست‌شدنِ سندباکس کلِ پروسه را نبرد.

اجرا:
    python strategies/s346_scan.py XAUUSD-M5 XAUUSD-M15 ...
    python strategies/s346_scan.py ALL

هر کارت → `results/_scan_S346/<CARD>.json`
"""
import os
import sys
import json
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se          # noqa: E402
from engine import rqs                          # noqa: E402
from strategies.s346_adaptive_channel import build_signals  # noqa: E402

OUT_DIR = 'results/_scan_S346'
os.makedirs(OUT_DIR, exist_ok=True)

CARDS = {
    # card            : (asset,   csv,                     max_hold candidates (fib/lucas))
    'XAUUSD-M5':  ('XAUUSD', 'data/XAUUSD_M5.csv',  [21, 34, 55]),
    'XAUUSD-M15': ('XAUUSD', 'data/XAUUSD_M15.csv', [13, 21, 34]),
    'XAUUSD-M30': ('XAUUSD', 'data/XAUUSD_M30.csv', [13, 21, 34]),
    'XAUUSD-H1':  ('XAUUSD', 'data/XAUUSD_H1.csv',  [11, 18, 29]),
    'XAUUSD-H4':  ('XAUUSD', 'data/XAUUSD_H4.csv',  [7, 11, 18]),
    'XAUUSD-D1':  ('XAUUSD', 'data/XAUUSD_D1.csv',  [4, 7, 11]),
    'XAUUSD-W1':  ('XAUUSD', 'data/XAUUSD_W1.csv',  [4, 7]),
    'EURUSD-M1':  ('EURUSD', 'data/EURUSD_M1.csv',  [34, 55, 89]),
    'EURUSD-M5':  ('EURUSD', 'data/EURUSD_M5.csv',  [21, 34, 55]),
    'EURUSD-M15': ('EURUSD', 'data/EURUSD_M15.csv', [13, 21, 34]),
    'EURUSD-M30': ('EURUSD', 'data/EURUSD_M30.csv', [13, 21, 34]),
}

# --- شبکهٔ پارامترها: هیچ عددِ رندی (رفعِ اشتباهِ رایج #۷) ---
P_GRID    = [13, 21, 34, 55]                 # فیبوناچی
MULT_GRID = [1.272, 1.618, 2.058, 2.618]     # ریشه/توان‌های طلایی
ER_FADE   = [0.146, 0.191, 0.236, 0.309]     # آستانهٔ رژیمِ رنج
ER_BRK    = [0.309, 0.382, 0.472]            # آستانهٔ رژیمِ روندی
SL_GRID   = [1.272, 1.618, 2.058]            # ×ATR تطبیقی
RR_GRID   = [1.0, 1.272, 1.618]              # TP/SL (هرگز <۱ ⇒ رفعِ اشتباهِ #۸)


def eval_combo(df, asset, mode, p, mult, er_thr, sl_k, rr, max_hold,
               require_reentry=False, extra_gate=None, side=None):
    pip = se.ASSETS[asset]['pip']
    spread = se.ASSETS[asset]['spread_pip']
    tp_k = sl_k * rr
    ls, ss, slp, tpp, ch = build_signals(
        df, mode=mode, p=p, mult=mult, er_thr=er_thr, sl_k=sl_k, tp_k=tp_k,
        pip=pip, min_sl_pip=2.0 * spread, require_reentry=require_reentry,
        extra_gate=extra_gate)
    if side == 'long':
        ss = np.zeros(len(df), dtype=bool)
    elif side == 'short':
        ls = np.zeros(len(df), dtype=bool)
    if int(ls.sum() + ss.sum()) < 30:
        return None
    tr = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp, asset=asset,
                            max_hold=max_hold, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return None
    sig = np.where(ls | ss)[0]
    sl_med = float(np.median(slp[sig]))
    tp_med = float(np.median(tpp[sig]))
    r = rqs.compute_rqs(tr, asset, sl_pip=sl_med, tp_pip=tp_med)
    r['cfg'] = dict(mode=mode, p=p, mult=mult, er_thr=er_thr, sl_k=sl_k, rr=rr,
                    max_hold=max_hold, require_reentry=require_reentry,
                    side=side or 'both')
    return r


def scan_card(card, verbose=True):
    asset, path, mh_grid = CARDS[card]
    df = se.load_data(path)
    n_bars = len(df)
    print(f"\n=== {card} | bars={n_bars} | {df['dt'].iloc[0]} → {df['dt'].iloc[-1]}", flush=True)
    results = []

    # ---------- مرحلهٔ A: هندسه (p, mult, er_thr) با SL/TP و holdِ میانی ----------
    for mode, er_grid in (('fade', ER_FADE), ('breakout', ER_BRK)):
        sl0, rr0, mh0 = 1.618, 1.272, mh_grid[1]
        stageA = []
        for p, mult, er_thr in itertools.product(P_GRID, MULT_GRID, er_grid):
            r = eval_combo(df, asset, mode, p, mult, er_thr, sl0, rr0, mh0)
            if r is None:
                continue
            stageA.append(r)
            if verbose:
                m = r['metrics']
                print(f"  A {mode:8s} p={p:2d} m={mult:5.3f} er={er_thr:5.3f} "
                      f"| n={m['n_trades']:5d} WR={m['win_rate']:5.1f} PF={m['profit_factor']:5.2f} "
                      f"RQS={r['rqs_score']:5.1f} {'ACC' if r['passed'] else '   '}", flush=True)
        results.extend(stageA)
        if not stageA:
            continue

        # ---------- مرحلهٔ B: پالایشِ SL/RR/hold روی ۳ هندسهٔ برتر ----------
        # رتبه‌بندی: اول RQS، بعد n (تعدادِ معامله — خواستهٔ User Note)
        stageA.sort(key=lambda r: (r['rqs_score'], r['metrics']['n_trades']), reverse=True)
        top = stageA[:3]
        for base in top:
            cb = base['cfg']
            for sl_k, rr, mh in itertools.product(SL_GRID, RR_GRID, mh_grid):
                if (sl_k, rr, mh) == (sl0, rr0, mh0):
                    continue
                r = eval_combo(df, asset, mode, cb['p'], cb['mult'], cb['er_thr'],
                               sl_k, rr, mh)
                if r is None:
                    continue
                results.append(r)
                if verbose and r['rqs_score'] >= 70:
                    m = r['metrics']
                    print(f"  B {mode:8s} p={cb['p']:2d} m={cb['mult']:5.3f} er={cb['er_thr']:5.3f} "
                          f"sl={sl_k:5.3f} rr={rr:5.3f} mh={mh:3d} | n={m['n_trades']:5d} "
                          f"WR={m['win_rate']:5.1f} PF={m['profit_factor']:5.2f} "
                          f"RQS={r['rqs_score']:5.1f} {'ACC' if r['passed'] else '   '}", flush=True)

    # ---------- مرحلهٔ C: تفکیکِ سمت (long/short) روی ۵ نتیجهٔ برتر ----------
    results.sort(key=lambda r: (r['rqs_score'], r['metrics']['n_trades']), reverse=True)
    for base in results[:5]:
        cb = base['cfg']
        for side in ('long', 'short'):
            r = eval_combo(df, asset, cb['mode'], cb['p'], cb['mult'], cb['er_thr'],
                           cb['sl_k'], cb['rr'], cb['max_hold'], side=side)
            if r is None:
                continue
            results.append(r)
            if verbose and r['rqs_score'] >= 70:
                m = r['metrics']
                print(f"  C {cb['mode']:8s} side={side:5s} | n={m['n_trades']:5d} "
                      f"WR={m['win_rate']:5.1f} PF={m['profit_factor']:5.2f} "
                      f"RQS={r['rqs_score']:5.1f} {'ACC' if r['passed'] else '   '}", flush=True)

    results.sort(key=lambda r: (r['rqs_score'], r['metrics']['n_trades']), reverse=True)
    payload = dict(card=card, asset=asset, bars=n_bars,
                   n_combos=len(results),
                   best=results[0] if results else None,
                   accepted=[r for r in results if r['passed']],
                   top20=results[:20])
    with open(f'{OUT_DIR}/{card}.json', 'w') as f:
        json.dump(payload, f, indent=1, default=float)
    if results:
        b = results[0]
        m = b['metrics']
        print(f">>> {card} BEST: RQS={b['rqs_score']} {b['verdict']} n={m['n_trades']} "
              f"WR={m['win_rate']} PF={m['profit_factor']} cfg={b['cfg']}", flush=True)
        print(f">>> {card} accepted_combos={len(payload['accepted'])}", flush=True)
    else:
        print(f">>> {card} no valid combo (n<30)", flush=True)
    return payload


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] == 'ALL':
        args = list(CARDS.keys())
    for card in args:
        scan_card(card)
