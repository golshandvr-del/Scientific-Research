#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S583 explorer — London PM Fix drift/reversion, first-half-only per prereg
results/S583_PREREG_LONDON_PM_FIX_DRIFT.md (commit a2c25cfb).
Grid locked: 2 events x mh{1,2,4} = 6 points, SL=TP=2.058*ATR(34), XAUUSD-H1.
E1: signal on 16:00 server bar => SHORT (entry next bar open = 17:00, into/at fix)
E2: signal on 17:00 server bar => LONG  (entry next bar open = 18:00, post-fix)
Second half never enters the grid. Includes locked winner rule + power precondition.
"""
import json, sys, gc, time
import numpy as np
import pandas as pd

sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import indicator_bank as ib

SEED = 20260821
GEO_K = 2.058
ATR_P = 34
MHS = [1, 2, 4]
PIP = se.ASSETS['XAUUSD']['pip']
COST = se.ASSETS['XAUUSD']['spread_pip']
MIN_YEARS = 12.0


def main():
    t0 = time.time()
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d)
    span_y = (df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 24 * 3600)
    assert span_y > MIN_YEARS, f'BUG-DATASETDRIFT: span {span_y:.2f}y'
    n = len(df)
    split = n // 2
    fh = df.iloc[:split].copy()
    del df; gc.collect()

    hours = pd.to_datetime(fh['time'], unit='s').dt.hour.to_numpy()
    atr = ib.atr_s(fh, ATR_P).to_numpy()
    valid = np.isfinite(atr) & (atr > 0)

    e1 = (hours == 16) & valid   # SHORT into fix
    e2 = (hours == 17) & valid   # LONG post fix
    zeros = np.zeros(split, dtype=bool)

    med1 = float(np.median(atr[e1]) / PIP) if e1.sum() else float('nan')
    med2 = float(np.median(atr[e2]) / PIP) if e2.sum() else float('nan')

    out = {'mission': 'S583', 'stage': 'explore_first_half', 'seed': SEED,
           'src': d['src'], 'n_total': n, 'split': split, 'span_y': round(span_y, 2),
           'n_e1': int(e1.sum()), 'n_e2': int(e2.sum()),
           'med_sl_pip_e1': round(med1, 2), 'med_sl_pip_e2': round(med2, 2),
           'grid': [], 'winner': None, 'power_check': None}
    print(f'H1 fh={split} E1(short@16h)={out["n_e1"]} E2(long@17h)={out["n_e2"]} '
          f'medSL e1={med1:.1f} e2={med2:.1f} src={d["src"]}', flush=True)

    for ev, name, lsig, ssig, sl_pip in (
            ('E1', 'short_into_fix', zeros, e1, round(med1, 2)),
            ('E2', 'long_post_fix', e2, zeros, round(med2, 2))):
        tp_pip = sl_pip  # V-TIME symmetric per prereg
        for mh in MHS:
            tr = se.simulate_trades(fh, lsig, ssig, sl_pip, tp_pip, 'XAUUSD', mh, False)
            if tr is None or len(tr) == 0:
                continue
            pnl = np.asarray(tr['pnl_pip'], dtype=float)
            nt = pnl.size
            row = {'ev': ev, 'name': name, 'mh': mh, 'sl': sl_pip, 'tp': tp_pip,
                   'n': nt, 'wr': round(float((pnl > 0).mean() * 100), 2),
                   'exp_pip': round(float(pnl.mean()), 3),
                   'net_pip': round(float(pnl.sum()), 1),
                   'score': round(float(pnl.mean()) * np.sqrt(nt), 2)}
            out['grid'].append(row)
            print('  ', row, flush=True)

    cands = [r for r in out['grid'] if r['n'] >= 150 and r['net_pip'] > 0]
    if not cands:
        print('\n❌ هیچ نقطه‌ای n≥150 و net>0 نداشت — مرگ صادقانه در اکتشاف؛ '
              'آزمون تأییدی اجرا نمی‌شود.', flush=True)
    else:
        cands.sort(key=lambda r: (r['score'], r['n'], -r['mh']), reverse=True)
        w = cands[0]
        out['winner'] = w
        print('\n🏆 winner:', w, flush=True)
        # power precondition: uncond same-geometry same-side baseline + cost breakeven
        sl, tp, mh = w['sl'], w['tp'], w['mh']
        be = (sl + COST) / (sl + tp) * 100
        ones = np.ones(split, dtype=bool)
        if w['ev'] == 'E1':
            tru = se.simulate_trades(fh, zeros, ones, sl, tp, 'XAUUSD', mh, False)
        else:
            tru = se.simulate_trades(fh, ones, zeros, sl, tp, 'XAUUSD', mh, False)
        wru = float((np.asarray(tru['pnl_pip']) > 0).mean() * 100)
        base = max(be, wru)
        lift = w['wr'] - base
        req = max(4.0, 309 * 0.497 / np.sqrt(w['n']))
        out['power_check'] = {'be_wr': round(be, 2), 'unc_wr': round(wru, 2),
                              'wr_obs': w['wr'], 'lift': round(lift, 2),
                              'lift_required': round(req, 2),
                              'precondition': 'PASS' if lift >= req else 'FAIL'}
        print('power_check:', out['power_check'], flush=True)

    out['elapsed_s'] = round(time.time() - t0, 1)
    path = '/home/user/webapp/results/_s583_explore.json'
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('✅ ذخیره:', path, flush=True)


if __name__ == '__main__':
    main()
