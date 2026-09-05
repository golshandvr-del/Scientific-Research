#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S588 explorer — PGO(14) breakout ±3.0 (Mark Johnson canonical), first-half-only
per prereg results/S588_PREREG_PGO_BREAKOUT.md (commit 6b68cad1).
Grid: 4TF{H4,H6,H8,H12} x RR{1.0,1.618} x mh{21,34} = 16 points,
SL=1.272*ATR(21) median-at-signal. Both sides in one call.
Locked winner rule + S782 power precondition + F1 shock-overlap falsifier
(share of winner signals on S965-style shock bars: range >= 2.618*ATR21).
Structural copy of tools/s586_explore.py (signal block + F1 added).
"""
import json, sys, gc, time
import numpy as np
import pandas as pd

sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import indicator_bank as ib

SEED = 20260829
TFS = ['H4', 'H6', 'H8', 'H12']
RRS = [1.0, 1.618]
MHS = [21, 34]
SL_K = 1.272
ATR_P = 21
PGO_P = 14
PGO_TH = 3.0
SHOCK_K = 2.618          # F1: S965-style shock bar definition
PIP = se.ASSETS['XAUUSD']['pip']
COST = se.ASSETS['XAUUSD']['spread_pip']
MIN_YEARS = 12.0


def pgo_signals(fh):
    g = ib.pgo(fh, PGO_P).to_numpy(dtype=float)
    atr = ib.atr_s(fh, ATR_P).to_numpy(dtype=float)
    prev = np.roll(g, 1); prev[0] = np.nan
    valid = np.isfinite(g) & np.isfinite(prev) & np.isfinite(atr) & (atr > 0)
    lsig = (g > PGO_TH) & (prev <= PGO_TH) & valid
    ssig = (g < -PGO_TH) & (prev >= -PGO_TH) & valid
    return lsig, ssig, atr


def main():
    t0 = time.time()
    out = {'mission': 'S588', 'stage': 'explore_first_half', 'seed': SEED,
           'signal': f'PGO({PGO_P}) cross +-{PGO_TH}', 'cards': {}, 'grid': [],
           'winner': None, 'power_check': None, 'f1_shock_overlap': None}
    for tf in TFS:
        d = fd.load_fast('XAUUSD', tf)
        df = fd.as_dataframe(d)
        assert 'mt5_full' in str(d['src']) or tf == 'H4', f'BUG-DATASETDRIFT src {d["src"]}'
        span_y = (df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 24 * 3600)
        assert span_y > MIN_YEARS, f'BUG-DATASETDRIFT {tf}: {span_y:.2f}y'
        n = len(df)
        split = n // 2
        fh = df.iloc[:split].copy()
        del df; gc.collect()

        lsig, ssig, atr = pgo_signals(fh)
        sig = lsig | ssig
        nsig = int(sig.sum())
        med_sl = float(np.median(atr[sig]) * SL_K / PIP) if nsig else float('nan')
        # F1 shock share (per TF, signal bars only)
        rng_bar = (fh['high'] - fh['low']).to_numpy(dtype=float)
        shock = rng_bar >= SHOCK_K * atr
        shock_share = float(shock[sig].mean() * 100) if nsig else float('nan')
        out['cards'][tf] = {'src': str(d['src']), 'n_total': n, 'split': split,
                            'span_y': round(span_y, 2), 'n_sig_fh': nsig,
                            'n_long': int(lsig.sum()), 'n_short': int(ssig.sum()),
                            'med_sl_pip': round(med_sl, 2),
                            'shock_share_pct': round(shock_share, 1)}
        print(f'--- {tf}: fh={split} sig={nsig} (L{int(lsig.sum())}/S{int(ssig.sum())}) '
              f'medSL={med_sl:.1f} shock%={shock_share:.1f} src={d["src"]}', flush=True)
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
        del fh, atr; gc.collect()

    cands = [r for r in out['grid'] if r['n'] >= 150 and r['net_pip'] > 0]
    if not cands:
        print('\n❌ هیچ نقطه‌ای n≥150 و net>0 نداشت — مرگ صادقانه در اکتشاف؛ '
              'آزمون تأییدی اجرا نمی‌شود.', flush=True)
    else:
        cands.sort(key=lambda r: (r['score'], r['n'], -r['mh']), reverse=True)
        w = cands[0]
        out['winner'] = w
        out['f1_shock_overlap'] = out['cards'][w['tf']]['shock_share_pct']
        print('\n🏆 winner:', w, '| F1 shock share %:', out['f1_shock_overlap'], flush=True)
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
    path = '/home/user/webapp/results/_s588_explore.json'
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('✅ ذخیره:', path, flush=True)


if __name__ == '__main__':
    main()
