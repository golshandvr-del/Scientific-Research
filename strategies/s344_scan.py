# -*- coding: utf-8 -*-
"""
S344 — اسکنِ جامعِ مولتی-TF + گریدِ پارامتر + فیلترهای رژیمِ بانک.
هدف: یافتنِ ترکیبی که RQS+ ≥ ۸۰ روی حداقل یک (جفت‌ارز×TF) بدهد.
اجرا:  PYTHONPATH=. python3 strategies/s344_scan.py [asset] [tf]
"""
import sys
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib
from strategies.s344_brooks_trend_from_open import trend_from_open_signals, load_tf


# SL/TP پایهٔ غیررندِ per-TF (بر حسبِ pip طلا؛ برای EUR بازمقیاس می‌شود)
TF_TPSL = {
    'M5':  [(120, 180), (150, 225), (95, 165)],
    'M15': [(180, 270), (220, 340), (150, 240)],
    'M30': [(260, 400), (320, 500), (200, 320)],
    'H1':  [(360, 560), (450, 720), (280, 440)],
    'H4':  [(700, 1100), (900, 1500)],
    'D1':  [(1500, 2400)],
    'W1':  [(3000, 5000)],
}
TF_MAXHOLD = {'M5': 48, 'M15': 32, 'M30': 24, 'H1': 20, 'H4': 12, 'D1': 6, 'W1': 4}


def _regime_mask(df, kind):
    """ماسکِ فیلترِ رژیم از بانکِ اندیکاتور. None = بدونِ فیلتر."""
    if kind is None:
        return np.ones(len(df), bool)
    n = len(df)
    if kind == 'r2_34':
        v = ib.r2(df, p=34).to_numpy(); return (v >= 0.34) & np.isfinite(v)
    if kind == 'r2_55':
        v = ib.r2(df, p=55).to_numpy(); return (v >= 0.45) & np.isfinite(v)
    if kind == 'hurst_55':
        v = ib.hurst(df, p=55).to_numpy(); return (v >= 0.53) & np.isfinite(v)
    if kind == 'r2h':
        a = ib.r2(df, p=34).to_numpy(); b = ib.hurst(df, p=55).to_numpy()
        return (a >= 0.30) & (b >= 0.52) & np.isfinite(a) & np.isfinite(b)
    if kind == 'adx':
        try:
            a = ib.compute('adx', df).to_numpy()
            return (a >= 22) & np.isfinite(a)
        except Exception:
            return np.ones(n, bool)
    if kind == 'chop':
        try:
            a = ib.compute('chop_fib_21', df).to_numpy()
            return (a <= 45) & np.isfinite(a)   # chop پایین = روندی
        except Exception:
            return np.ones(n, bool)
    return np.ones(n, bool)


def scan_one(asset, tf, verbose=True):
    df = load_tf(asset, tf)
    scale = 1.0 if asset == 'XAUUSD' else (0.0001 / 0.10)  # pip طلا→EUR اگر لازم شد
    # برای EUR واحدِ pip فرق دارد؛ اما simulate از pip دارایی استفاده می‌کند، پس عددِ pip
    # را همان طلا نگه می‌داریم و برای EUR کوچک‌ترش می‌کنیم (دامنهٔ EUR بر حسبِ pip بسیار کوچک‌تر).
    tpsl_list = TF_TPSL.get(tf, [(150, 225)])
    maxhold = TF_MAXHOLD.get(tf, 24)

    best = None
    regimes = [None, 'r2_34', 'r2h', 'hurst_55', 'adx', 'chop']
    n_opens = [4, 6, 8] if tf in ('M5', 'M15', 'M30') else [3, 4, 6]
    f_ranges = [0.20, 0.25, 0.33]
    pull_maxs = [0.50, 0.62, 0.75]
    min_spikes = [0.20, 0.30, 0.45]

    results = []
    for side in ('long', 'short'):
        for n_open in n_opens:
            for f_range in f_ranges:
                for pull_max in pull_maxs:
                    for min_spike in min_spikes:
                        sig = trend_from_open_signals(df, tf, side, n_open=n_open,
                                                      f_range=f_range, pull_max=pull_max,
                                                      min_spike_frac=min_spike)
                        if sig.sum() < 30:
                            continue
                        for reg in regimes:
                            rmask = _regime_mask(df, reg)
                            fsig = sig & rmask
                            if fsig.sum() < 30:
                                continue
                            for (sl, tp) in tpsl_list:
                                sl_e = sl if asset == 'XAUUSD' else max(6, int(sl * 0.06))
                                tp_e = tp if asset == 'XAUUSD' else max(9, int(tp * 0.06))
                                long_sig = fsig if side == 'long' else np.zeros(len(df), bool)
                                short_sig = fsig if side == 'short' else np.zeros(len(df), bool)
                                tr = se.simulate_trades(df, long_sig, short_sig,
                                                        sl_pip=sl_e, tp_pip=tp_e, asset=asset,
                                                        max_hold=maxhold, allow_overlap=False)
                                if tr is None or len(tr) < 30:
                                    continue
                                r = rqs.compute_rqs(tr, asset, sl_pip=sl_e, tp_pip=tp_e)
                                m = r['metrics']
                                rec = dict(side=side, n_open=n_open, f_range=f_range,
                                           pull_max=pull_max, min_spike=min_spike, reg=reg,
                                           sl=sl_e, tp=tp_e, rqs=r['rqs_score'],
                                           passed=r['passed'], n=m['n_trades'],
                                           wr=m['win_rate'], pf=m['profit_factor'],
                                           gates=''.join('1' if r['gates'][g] else '0'
                                                         for g in ['G0','G1','G2','G3','G4','G5']))
                                results.append(rec)
                                if best is None or r['rqs_score'] > best['rqs']:
                                    best = rec
    results.sort(key=lambda x: x['rqs'], reverse=True)
    if verbose:
        print(f"\n===== {asset} {tf} — top 12 by RQS+ =====")
        for rec in results[:12]:
            print(f"RQS={rec['rqs']:5.1f} {'ACC' if rec['passed'] else 'rej'} "
                  f"G[{rec['gates']}] {rec['side']:5} nO={rec['n_open']} f={rec['f_range']} "
                  f"pull={rec['pull_max']} spk={rec['min_spike']} reg={str(rec['reg']):8} "
                  f"SL/TP={rec['sl']}/{rec['tp']} n={rec['n']} WR={rec['wr']} PF={rec['pf']}")
    return best, results


if __name__ == '__main__':
    if len(sys.argv) >= 3:
        asset, tf = sys.argv[1], sys.argv[2]
        scan_one(asset, tf)
    else:
        # پیش‌فرض: XAUUSD M5 (شروعِ اجباری)
        scan_one('XAUUSD', 'M5')
