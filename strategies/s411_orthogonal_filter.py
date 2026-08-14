# -*- coding: utf-8 -*-
"""
S411 — فیلترِ متعامدِ رژیمی روی خانوادهٔ کندلِ اولِ EURUSD (MISSION_2)
=====================================================================
پیش‌ثبت: results/S411_PREREG_ORTHOGONAL_FILTER.md (commit جداگانه، قبل از این فایل)

پایهٔ منجمد (از S410): لنگرِ کندلِ آخرِ روز & F3 & F1 · LONG · hold=1.5h · SL=18 · TP=10000
آزادیِ یگانه: یک اندیکاتور از ۱۶ سلولِ پیش‌ثبت‌شده (۸ اندیکاتور × ۲ جهت، آستانه=میانهٔ نیمهٔ اول).

فازها:
  --tune  : ۱۶ سلول فقط روی نیمهٔ اول.
  --final : آزمونِ یک‌ضربِ رسمی v2.6 (فقط اگر برنده‌ای طبق قاعدهٔ منجمد باشد).
"""
import os
import sys
import json

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                                # noqa: E402
from engine import indicator_bank as ib                              # noqa: E402
from strategies.s410_firstbar_eur import (anchor_signal, net_disp,   # noqa: E402
                                          bars_per_hour, cost_pip)

ASSET = 'EURUSD'
DATA_M15 = 'data/EURUSD_M15.csv'
OUT = 'results/_scan_S411'
os.makedirs(OUT, exist_ok=True)

SL_PIP = 18.0
TP_PIP = 10000.0     # «بدون TP» — سدِ واقعیِ دور (همان S410)
HOLD_H = 1.5
N_MIN = 200
N_TRIALS = 96        # تجمعی (پیش‌ثبت بندِ ۶)
INDICATORS = ('hurst', 'entropy', 'fdi', 'r2_fib_55',
              'laguerre_rsi', 'reflex', 'trendflex', 'cg_fib_55')


def base_signal(df):
    """پایهٔ منجمدِ S410: لنگر & F3 & F1 (همه علّی، روی کندلِ سیگنال)."""
    c = df['close'].values.astype(np.float64)
    o = df['open'].values.astype(np.float64)
    f1 = net_disp(c, 4) < 0.0
    f1[:4] = False
    f3 = c < o
    return anchor_signal(df) & f3 & f1


def eval_cell(df, sig, max_hold):
    tr = se.simulate_trades(df, sig, np.zeros(len(df), bool), SL_PIP, TP_PIP,
                            ASSET, max_hold=max_hold, allow_overlap=False)
    if tr is None or len(tr) == 0:
        return None
    pnl = tr['pnl_pip'].values
    n = len(tr)
    exp_net = float(np.mean(pnl))
    exp2c = exp_net - cost_pip(ASSET)
    sd = float(np.std(pnl, ddof=1)) if n > 1 else float('nan')
    t = exp_net / (sd / np.sqrt(n)) if n > 1 and sd > 0 else float('nan')
    return dict(n=n, wr=float((pnl > 0).mean() * 100.0),
                exp_net=exp_net, exp2c=exp2c, t=t)


def tune():
    df = se.load_data(DATA_M15)
    n = len(df)
    split = n // 2
    dfa = df.iloc[:split].reset_index(drop=True)   # نیمهٔ دوم لمس نمی‌شود
    bph = bars_per_hour(dfa)
    mh = int(round(HOLD_H * bph))
    base = base_signal(dfa)
    print(f"[S411 tune] bars(first half)={split:,} bars/h={bph:.2f} "
          f"max_hold={mh} base events={int(base.sum())} "
          f"cost={cost_pip(ASSET):.2f}pip", flush=True)

    r0 = eval_cell(dfa, base, mh)
    print(f"  BASE       | n={r0['n']:4d} wr={r0['wr']:5.1f} "
          f"exp={r0['exp_net']:+.3f} exp@2c={r0['exp2c']:+.3f} t={r0['t']:+.2f}",
          flush=True)

    rows = []
    for name in INDICATORS:
        v = ib.compute(name, dfa).values.astype(np.float64)
        med = float(np.nanmedian(v[:split]))     # آستانهٔ منجمد = میانهٔ نیمهٔ اول
        finite = np.isfinite(v)
        for direction, mask in (('below', finite & (v < med)),
                                ('above', finite & (v >= med))):
            sig = base & mask
            r = eval_cell(dfa, sig, mh)
            if r is None:
                print(f"  {name:14s} {direction:5s} | no trades", flush=True)
                continue
            r.update(indicator=name, direction=direction, median=med)
            rows.append(r)
            print(f"  {name:14s} {direction:5s} | n={r['n']:4d} "
                  f"wr={r['wr']:5.1f} exp={r['exp_net']:+.3f} "
                  f"exp@2c={r['exp2c']:+.3f} t={r['t']:+.2f}", flush=True)

    res = pd.DataFrame(rows)
    ok = res[(res['n'] >= N_MIN) & (res['exp2c'] > 0)]
    if len(ok) == 0:
        print("\n[SELECTION] هیچ سلولی exp@2c>0 با n>=200 ندارد ⇒ توقفِ کامل، "
              "REJECT-قبل-از-آزمون (holdout بکر می‌ماند).", flush=True)
        winner = None
    else:
        winner = ok.sort_values(['exp2c', 't'], ascending=False).iloc[0].to_dict()
        print(f"\n[WINNER] {json.dumps(winner, ensure_ascii=False, default=str)}",
              flush=True)

    out = dict(split_bar=split, bars_per_hour=bph, max_hold=mh,
               base=r0, cells=rows, winner=winner, n_trials=N_TRIALS)
    with open(os.path.join(OUT, 'tune.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print(f"[saved] {OUT}/tune.json", flush=True)


if __name__ == '__main__':
    if '--tune' in sys.argv:
        tune()
    else:
        print("usage: python strategies/s411_orthogonal_filter.py --tune",
              flush=True)
