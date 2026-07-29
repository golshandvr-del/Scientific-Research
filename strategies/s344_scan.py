# -*- coding: utf-8 -*-
"""
S344 — اسکنِ جامعِ مولتی-TF + گریدِ پارامتر + فیلترهای رژیمِ بانک.
هدف: یافتنِ ترکیبی که RQS+ ≥ ۸۰ روی حداقل یک (جفت‌ارز×TF) بدهد.

اجرا:
  یک TF:      PYTHONPATH=. python3 strategies/s344_scan.py XAUUSD M5
  همهٔ TFها:  PYTHONPATH=. python3 strategies/s344_scan.py ALL

بهبودها نسبت به نسخهٔ قبل (رفعِ timeout):
  1) کشِ ماسکِ رژیم — hurst/r2/adx فقط یک‌بار به‌ازای هر TF محاسبه می‌شوند.
  2) ذخیرهٔ تدریجیِ نتایج در results/_scan_S344/<asset>_<tf>.json پس از هر TF
     (قانونِ «اندک اندک» — مقاوم به ریستِ سندباکس).
  3) گریدِ کنترل‌شده و غیررند، per-TF.
"""
import sys
import os
import json
import time
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib
from strategies.s344_brooks_trend_from_open import trend_from_open_signals, load_tf


OUT_DIR = 'results/_scan_S344'

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

# TFهای هر جفت‌ارز (طبقِ فایل‌های موجود در data/)
ASSET_TFS = {
    'XAUUSD': ['M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1'],
    'EURUSD': ['M1', 'M5', 'M15', 'M30'],
}


def _build_regime_cache(df):
    """همهٔ ماسک‌های رژیم را یک‌بار محاسبه و کش می‌کند (رفعِ گلوگاهِ hurst/r2)."""
    n = len(df)
    cache = {None: np.ones(n, bool)}

    def safe(name, fn):
        try:
            cache[name] = fn()
        except Exception:
            cache[name] = np.ones(n, bool)

    safe('r2_34', lambda: (lambda v: (v >= 0.34) & np.isfinite(v))(ib.r2(df, p=34).to_numpy()))
    safe('r2h', lambda: (lambda a, b: (a >= 0.30) & (b >= 0.52) & np.isfinite(a) & np.isfinite(b))(
        ib.r2(df, p=34).to_numpy(), ib.hurst(df, p=55).to_numpy()))
    safe('hurst_55', lambda: (lambda v: (v >= 0.53) & np.isfinite(v))(ib.hurst(df, p=55).to_numpy()))
    safe('adx', lambda: (lambda a: (a >= 22) & np.isfinite(a))(ib.compute('adx', df).to_numpy()))
    safe('chop', lambda: (lambda a: (a <= 45) & np.isfinite(a))(ib.compute('chop_fib_21', df).to_numpy()))
    return cache


def scan_one(asset, tf, verbose=True, save=True):
    t0 = time.time()
    df = load_tf(asset, tf)
    tpsl_list = TF_TPSL.get(tf, [(150, 225)])
    maxhold = TF_MAXHOLD.get(tf, 24)

    # کشِ ماسکِ رژیم — یک‌بار برای کلِ TF
    reg_cache = _build_regime_cache(df)
    regimes = list(reg_cache.keys())

    n_opens = [4, 6, 8] if tf in ('M5', 'M15', 'M30') else [3, 4, 6]
    f_ranges = [0.20, 0.25, 0.33]
    pull_maxs = [0.50, 0.62, 0.75]
    min_spikes = [0.20, 0.30, 0.45]

    best = None
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
                            fsig = sig & reg_cache[reg]
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
                                           sl=sl_e, tp=tp_e, rqs=round(r['rqs_score'], 2),
                                           passed=bool(r['passed']), n=int(m['n_trades']),
                                           wr=round(m['win_rate'], 3), pf=round(m['profit_factor'], 3),
                                           gates=''.join('1' if r['gates'][g] else '0'
                                                         for g in ['G0', 'G1', 'G2', 'G3', 'G4', 'G5']))
                                results.append(rec)
                                if best is None or rec['rqs'] > best['rqs']:
                                    best = rec
    results.sort(key=lambda x: x['rqs'], reverse=True)
    elapsed = time.time() - t0

    if save:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(f'{OUT_DIR}/{asset}_{tf}.json', 'w') as f:
            json.dump({'asset': asset, 'tf': tf, 'elapsed_s': round(elapsed, 1),
                       'best': best, 'top': results[:20]}, f, ensure_ascii=False, indent=1)

    if verbose:
        print(f"\n===== {asset} {tf} — top 12 by RQS+ (elapsed {elapsed:.0f}s) =====")
        if not results:
            print("  (هیچ ترکیبی حداقلِ ۳۰ معامله نساخت)")
        for rec in results[:12]:
            print(f"RQS={rec['rqs']:5.1f} {'ACC' if rec['passed'] else 'rej'} "
                  f"G[{rec['gates']}] {rec['side']:5} nO={rec['n_open']} f={rec['f_range']} "
                  f"pull={rec['pull_max']} spk={rec['min_spike']} reg={str(rec['reg']):8} "
                  f"SL/TP={rec['sl']}/{rec['tp']} n={rec['n']} WR={rec['wr']} PF={rec['pf']}")
    return best, results


def scan_all():
    """اسکنِ همهٔ (جفت‌ارز × TF) با ذخیرهٔ تدریجی پس از هر TF."""
    for asset, tfs in ASSET_TFS.items():
        for tf in tfs:
            print(f"\n######## SCANNING {asset} {tf} ########", flush=True)
            try:
                best, _ = scan_one(asset, tf, verbose=True, save=True)
                if best:
                    print(f">>> BEST {asset} {tf}: RQS={best['rqs']} "
                          f"{'ACCEPT' if best['passed'] else 'reject'} "
                          f"side={best['side']} reg={best['reg']} "
                          f"WR={best['wr']} PF={best['pf']} n={best['n']}", flush=True)
            except Exception as e:
                print(f"!!! ERROR {asset} {tf}: {e}", flush=True)


if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1].upper() == 'ALL':
        scan_all()
    elif len(sys.argv) >= 3:
        scan_one(sys.argv[1], sys.argv[2])
    else:
        scan_one('XAUUSD', 'M5')
