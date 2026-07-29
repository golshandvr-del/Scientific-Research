# -*- coding: utf-8 -*-
"""
S345 — اسکنِ جامعِ مولتی-TF + گریدِ پارامتر + فیلترهای رژیمِ بانک.
هدف: یافتنِ ترکیبی که RQS+ ≥ ۸۰ روی حداقل یک (جفت‌ارز×TF) بدهد.

اجرا:
  یک TF:      PYTHONPATH=. python3 strategies/s345_scan.py XAUUSD M5
  همهٔ TFها:  PYTHONPATH=. python3 strategies/s345_scan.py ALL

قانونِ «اندک اندک»: نتایجِ هر TF در results/_scan_S345/<asset>_<tf>.json ذخیره می‌شود
(مقاوم به ریستِ سندباکس). کشِ ماسکِ رژیم یک‌بار به‌ازای هر TF محاسبه می‌شود.
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
from strategies.s345_brooks_reversal_day import reversal_day_signals, load_tf


OUT_DIR = 'results/_scan_S345'

# SL/TP پایهٔ غیررندِ per-TF (بر حسبِ pip طلا؛ برای EUR بازمقیاس می‌شود).
# reversal ذاتاً به SL مناسب و TP روندی (measured-move) نیاز دارد.
TF_TPSL = {
    'M1':  [(70, 110), (95, 150)],
    'M5':  [(120, 200), (150, 260), (95, 175)],
    'M15': [(190, 320), (240, 400), (150, 270)],
    'M30': [(270, 460), (340, 560), (210, 360)],
    'H1':  [(370, 620), (470, 800), (300, 500)],
    'H4':  [(720, 1200), (950, 1600)],
    'D1':  [(1600, 2600)],
    'W1':  [(3200, 5400)],
}
TF_MAXHOLD = {'M1': 90, 'M5': 60, 'M15': 40, 'M30': 28, 'H1': 22, 'H4': 12, 'D1': 6, 'W1': 4}

ASSET_TFS = {
    'XAUUSD': ['M5', 'M15', 'M30', 'H1', 'H4', 'D1', 'W1'],
    'EURUSD': ['M1', 'M5', 'M15', 'M30'],
}


def _build_regime_cache(df):
    """ماسک‌های رژیم/کیفیت — یک‌بار برای کلِ TF (جعبه‌ابزارِ بانک، رفعِ اشتباه #۳)."""
    n = len(df)
    cache = {None: np.ones(n, bool)}

    def safe(name, fn):
        try:
            cache[name] = fn()
        except Exception:
            cache[name] = np.ones(n, bool)

    # reversal معمولاً در رنج/چرخش بهتر است ⇒ فیلترهای رنج و کیفیتِ چرخش
    safe('chop_hi', lambda: (lambda a: (a >= 45) & np.isfinite(a))(ib.compute('chop_fib_21', df).to_numpy()))
    safe('r2_lo', lambda: (lambda v: (v <= 0.55) & np.isfinite(v))(ib.r2(df, p=34).to_numpy()))
    safe('adx_hi', lambda: (lambda a: (a >= 25) & np.isfinite(a))(ib.compute('adx', df).to_numpy()))
    safe('hurst_lo', lambda: (lambda v: (v <= 0.50) & np.isfinite(v))(ib.hurst(df, p=55).to_numpy()))
    # کشش از EMA (مغناطیسِ بازگشت — چرخش پس از کش‌آمدگی)
    safe('ema_stretch', lambda: (lambda v: (np.abs(v) >= 0.7) & np.isfinite(v))(ib.compute('ema_dist_atr', df).to_numpy()))
    return cache


def scan_one(asset, tf, verbose=True, save=True):
    t0 = time.time()
    df = load_tf(asset, tf)
    tpsl_list = TF_TPSL.get(tf, [(150, 260)])
    maxhold = TF_MAXHOLD.get(tf, 24)

    reg_cache = _build_regime_cache(df)
    regimes = list(reg_cache.keys())

    n_opens = [4, 6, 8] if tf in ('M1', 'M5', 'M15', 'M30') else [3, 4, 6]
    k_spikes = [0.8, 1.1, 1.5]
    slope_mins = [0.05, 0.10, 0.18]
    # پنجرهٔ ورود: چرخشِ میانه/اواخرِ روز
    windows = [(0.25, 0.90), (0.40, 0.95), (0.30, 0.75)]

    best = None
    results = []
    for side in ('long', 'short'):
        for n_open in n_opens:
            for k_spike in k_spikes:
                for slope_min in slope_mins:
                    for (wf, wt) in windows:
                        sig = reversal_day_signals(df, tf, side, n_open=n_open,
                                                   k_spike=k_spike, slope_min_frac=slope_min,
                                                   entry_from_frac=wf, entry_to_frac=wt)
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
                                rec = dict(side=side, n_open=n_open, k_spike=k_spike,
                                           slope_min=slope_min, win=(wf, wt), reg=reg,
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
                       'best': best, 'top': results[:25]}, f, ensure_ascii=False, indent=1)

    if verbose:
        print(f"\n===== {asset} {tf} — top 12 by RQS+ (elapsed {elapsed:.0f}s) =====", flush=True)
        if not results:
            print("  (هیچ ترکیبی حداقلِ ۳۰ معامله نساخت)")
        for rec in results[:12]:
            print(f"RQS={rec['rqs']:5.1f} {'ACC' if rec['passed'] else 'rej'} "
                  f"G[{rec['gates']}] {rec['side']:5} nO={rec['n_open']} k={rec['k_spike']} "
                  f"sl_m={rec['slope_min']} win={rec['win']} reg={str(rec['reg']):11} "
                  f"SL/TP={rec['sl']}/{rec['tp']} n={rec['n']} WR={rec['wr']} PF={rec['pf']}", flush=True)
    return best, results


def scan_all():
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
