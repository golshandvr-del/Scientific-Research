#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S582 explorer — TD Sequential Setup-9, first-half-only search per prereg
results/S582_PREREG_TDSEQ_SETUP9_EXHAUSTION.md (commit e4f6a26a).
Grid locked: 7 TFs x RR{1.5,2.058} x mh{21,55} = 28 points, SL=1.618*ATR(34).
Second half NEVER touched here. Winner rule + power precondition embedded.
"""
import json, sys, gc, time
import numpy as np
import pandas as pd

sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import indicator_bank as ib

SEED = 20260820
TFS = ['M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8']
RRS = [1.5, 2.058]
MHS = [21, 55]
SL_K = 1.618
ATR_P = 34
PIP = se.ASSETS['XAUUSD']['pip']            # BUG-PIPGUESS: read from engine
COST_PIP = se.ASSETS['XAUUSD']['spread_pip']  # 3.3

MIN_YEARS = 12.0


def load_first_half(tf):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    span_y = (df['time'].iloc[-1] - df['time'].iloc[0]) / (365.25 * 24 * 3600)
    assert span_y > MIN_YEARS, f'BUG-DATASETDRIFT: span {span_y:.2f}y <= {MIN_YEARS}y for {tf}'
    n = len(df)
    split = n // 2
    fh = df.iloc[:split].copy()
    del df; gc.collect()
    return fh, d['src'], n, split, span_y


def td_setup9(close):
    """TD Buy/Sell Setup-9 (frozen, zero free params). Returns (long_sig, short_sig)."""
    c = np.asarray(close, dtype=np.float64)
    n = c.size
    buy_c = np.zeros(n, dtype=bool)
    sell_c = np.zeros(n, dtype=bool)
    buy_c[4:] = c[4:] < c[:-4]
    sell_c[4:] = c[4:] > c[:-4]
    # run length of consecutive True ending at i
    def run9(x):
        run = np.zeros(n, dtype=np.int32)
        r = 0
        for i in range(n):
            r = r + 1 if x[i] else 0
            run[i] = r
        return run == 9   # fires exactly on the 9th bar (not 10th+ per DeMark: setup completes at 9)
    return run9(buy_c), run9(sell_c)


def explore():
    out = {'mission': 'S582', 'stage': 'explore_first_half', 'seed': SEED,
           'cards': {}, 'grid': [], 'winner': None, 'power_check': None}
    t0 = time.time()
    for tf in TFS:
        fh, src, n_total, split, span_y = load_first_half(tf)
        atr = ib.atr_s(fh, ATR_P).to_numpy()
        lsig, ssig = td_setup9(fh['close'].to_numpy())
        # need valid ATR at signal bar
        valid = np.isfinite(atr) & (atr > 0)
        lsig &= valid; ssig &= valid
        sl_abs = SL_K * atr  # price units at each bar
        # per-signal-bar SL in pips -> use median over signal bars for the frozen bracket
        sig_any = lsig | ssig
        n_sigs = int(sig_any.sum())
        med_sl_pip = float(np.median(sl_abs[sig_any]) / PIP) if n_sigs else float('nan')
        out['cards'][tf] = {'src': src, 'n_total': n_total, 'split': split,
                            'span_y': round(span_y, 2), 'n_signals_fh': n_sigs,
                            'n_long_fh': int(lsig.sum()), 'n_short_fh': int(ssig.sum()),
                            'median_sl_pip': round(med_sl_pip, 2)}
        print(f'--- {tf}: n_fh={split} sigs={n_sigs} (L{int(lsig.sum())}/S{int(ssig.sum())}) '
              f'medSL={med_sl_pip:.1f}pip src={src}', flush=True)
        if n_sigs < 30:
            print(f'    {tf}: n<30 — MEASUREMENT-LIMITED, skip grid', flush=True)
            continue
        for rr in RRS:
            sl_pip = round(med_sl_pip, 2)
            tp_pip = round(rr * sl_pip, 2)
            for mh in MHS:
                tr = se.simulate_trades(fh, lsig, ssig, sl_pip, tp_pip,
                                        'XAUUSD', mh, False)
                if tr is None or len(tr) == 0:
                    continue
                pnl = np.asarray(tr['pnl_pip'] if 'pnl_pip' in tr else tr['pnl'], dtype=float)
                nt = pnl.size
                wr = float((pnl > 0).mean() * 100)
                expp = float(pnl.mean())
                net = float(pnl.sum())
                score = expp * np.sqrt(nt)
                row = {'tf': tf, 'rr': rr, 'mh': mh, 'sl': sl_pip, 'tp': tp_pip,
                       'n': nt, 'wr': round(wr, 2), 'exp_pip': round(expp, 3),
                       'net_pip': round(net, 1), 'score': round(score, 2)}
                out['grid'].append(row)
                print('   ', row, flush=True)
        del fh, atr, lsig, ssig; gc.collect()

    # locked winner rule
    cands = [r for r in out['grid'] if r['n'] >= 150 and r['net_pip'] > 0]
    if not cands:
        out['winner'] = None
        print('\n❌ هیچ نقطه‌ای n≥150 و net>0 نداشت — مرگ صادقانه در اکتشاف؛ '
              'آزمون تأییدی طبق پیش‌ثبت اجرا نمی‌شود.', flush=True)
    else:
        cands.sort(key=lambda r: (r['score'], r['n'], -r['sl']), reverse=True)
        w = cands[0]
        out['winner'] = w
        print('\n🏆 winner (locked rule):', w, flush=True)
    out['elapsed_s'] = round(time.time() - t0, 1)
    path = '/home/user/webapp/results/_s582_explore.json'
    with open(path, 'w') as f:
        json.dump(out, f, indent=1)
    print('✅ ذخیره:', path, flush=True)


if __name__ == '__main__':
    explore()
