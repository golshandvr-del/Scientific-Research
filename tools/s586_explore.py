#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S586 explorer — Elder Impulse flip continuation, first-half-only per prereg
results/S586_PREREG_ELDER_IMPULSE_FLIP.md (commit af450982). Grid: 4TF x
RR{1.0,1.618} x mh{21,34} = 16 points, SL=1.272*ATR(21) median-at-signal.
Both sides in one call. Locked winner rule + S782 power precondition.
Structural copy of tools/s584_explore.py (only signal block replaced).
"""
import json, sys, gc, time
import numpy as np
import pandas as pd

sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import indicator_bank as ib

SEED = 20260827
TFS = ['H6', 'H8', 'H12', 'D1']
RRS = [1.0, 1.618]
MHS = [21, 34]
SL_K = 1.272
ATR_P = 21
PIP = se.ASSETS['XAUUSD']['pip']
COST = se.ASSETS['XAUUSD']['spread_pip']
MIN_YEARS = 12.0


def main():
    t0 = time.time()
    out = {'mission': 'S586', 'stage': 'explore_first_half', 'seed': SEED,
           'cards': {}, 'grid': [], 'winner': None, 'power_check': None}
    for tf in TFS:
        d = fd.load_fast('XAUUSD', tf)
        df = fd.as_dataframe(d)
        span_y = (df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 24 * 3600)
        assert span_y > MIN_YEARS, f'BUG-DATASETDRIFT {tf}: {span_y:.2f}y'
        n = len(df)
        split = n // 2
        fh = df.iloc[:split].copy()
        del df; gc.collect()

        # سیگنال فریز: فلیپ Elder Impulse (پیش‌ثبت §۳)
        imp = ib.elder_impulse(fh, 13, 12, 26, 9).to_numpy()
        atr = ib.atr_s(fh, ATR_P).to_numpy()
        prev = np.roll(imp, 1); prev[0] = np.nan
        valid = np.isfinite(imp) & np.isfinite(prev) & np.isfinite(atr) & (atr > 0)
        lsig = (imp == 1.0) & (prev != 1.0) & valid
        ssig = (imp == -1.0) & (prev != -1.0) & valid
        sig = lsig | ssig
        nsig = int(sig.sum())
        med_sl = float(np.median(atr[sig]) * SL_K / PIP) if nsig else float('nan')
        out['cards'][tf] = {'src': d['src'], 'n_total': n, 'split': split,
                            'span_y': round(span_y, 2), 'n_sig_fh': nsig,
                            'n_long': int(lsig.sum()), 'n_short': int(ssig.sum()),
                            'med_sl_pip': round(med_sl, 2)}
        print(f'--- {tf}: fh={split} sig={nsig} (L{int(lsig.sum())}/S{int(ssig.sum())}) '
              f'medSL={med_sl:.1f} src={d["src"]}', flush=True)
        if nsig < 30:
            print(f'    {tf}: n<30 — MEASUREMENT-LIMITED, skip', flush=True)
            continue
        for rr in RRS:
            sl_pip = round(med_sl, 2)
            tp_pip = round(rr * sl_pip, 2)
            for mh in MHS:
                tr = se.simulate_trades(fh, lsig, ssig, sl_pip, tp_pip,
                                        'XAUUSD', mh, False)
                if tr is None or len(tr) == 0:
                    continue
                pnl = np.asarray(tr['pnl_pip'], dtype=float)
                nt = pnl.size
                nL = int((tr['direction'].values == 'long').sum())  # BUG-DIRSTR
                row = {'tf': tf, 'rr': rr, 'mh': mh, 'sl': sl_pip, 'tp': tp_pip,
                       'n': nt, 'n_long': nL, 'n_short': nt - nL,
                       'wr': round(float((pnl > 0).mean() * 100), 2),
                       'exp_pip': round(float(pnl.mean()), 3),
                       'net_pip': round(float(pnl.sum()), 1),
                       'score': round(float(pnl.mean()) * np.sqrt(nt), 2)}
                out['grid'].append(row)
                print('   ', row, flush=True)
        del fh, imp, atr; gc.collect()

    cands = [r for r in out['grid'] if r['n'] >= 150 and r['net_pip'] > 0]
    if not cands:
        print('\n❌ هیچ نقطه‌ای n≥150 و net>0 نداشت — مرگ صادقانه در اکتشاف؛ '
              'آزمون تأییدی اجرا نمی‌شود.', flush=True)
    else:
        cands.sort(key=lambda r: (r['score'], r['n'], -r['mh']), reverse=True)
        w = cands[0]
        out['winner'] = w
        print('\n🏆 winner:', w, flush=True)
        # پیش‌شرط توان S782 روی کارت برنده، فقط نیمهٔ اول
        d = fd.load_fast('XAUUSD', w['tf'])
        df = fd.as_dataframe(d)
        split = len(df) // 2
        fh = df.iloc[:split]
        be = (w['sl'] + COST) / (w['sl'] + w['tp']) * 100
        ones = np.ones(split, dtype=bool)
        zeros = np.zeros(split, dtype=bool)
        trL = se.simulate_trades(fh, ones, zeros, w['sl'], w['tp'], 'XAUUSD', w['mh'], False)
        trS = se.simulate_trades(fh, zeros, ones, w['sl'], w['tp'], 'XAUUSD', w['mh'], False)
        wrL = float((np.asarray(trL['pnl_pip']) > 0).mean() * 100)
        wrS = float((np.asarray(trS['pnl_pip']) > 0).mean() * 100)
        base = max(be, wrL, wrS)
        lift = w['wr'] - base
        req = max(4.0, 309 * 0.497 / np.sqrt(w['n']))
        out['power_check'] = {'be_wr': round(be, 2), 'unc_long': round(wrL, 2),
                              'unc_short': round(wrS, 2), 'wr_obs': w['wr'],
                              'lift': round(lift, 2), 'lift_required': round(req, 2),
                              'precondition': 'PASS' if lift >= req else 'FAIL'}
        print('power_check:', out['power_check'], flush=True)

    out['elapsed_s'] = round(time.time() - t0, 1)
    path = '/home/user/webapp/results/_s586_explore.json'
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('✅ ذخیره:', path, flush=True)


if __name__ == '__main__':
    main()
