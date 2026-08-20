# -*- coding: utf-8 -*-
"""
s681_triage.py — مرحلهٔ اقتصادِ S681 (الحاقیهٔ پیش‌ثبت، کامیت 5b2b3cc2)
================================================================================
per کارت فقط **یک** شبیه‌سازیِ کاملِ داده با هندسهٔ قفل‌شده؛ ثبتِ
n / WR / exp_pip_full. هیچ پارامتری تغییر نمی‌کند، هیچ گزینشی نیست.
فقط کارت‌های exp_pip_full>0 بعداً به داوریِ گرانِ K=500 می‌روند.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se                        # noqa: E402
from tools import s434_fast_data as fd                       # noqa: E402
from strategies.s681_lagsat_union import (                   # noqa: E402
    union_signals, EXPLORE_DIR, RR)

OUT_DIR = os.path.join(ROOT, 'results', '_s681_triage')


def triage(tf: str, asset: str = 'XAUUSD') -> dict:
    t0 = time.time()
    ex = json.load(open(os.path.join(EXPLORE_DIR, f'explore_{tf}.json'),
                        encoding='utf-8'))
    sl = float(ex['sl_pip'])
    tp = round(RR * sl, 1)
    mh = int(ex['max_hold'])
    if tp < sl:
        raise ValueError('TP<SL ممنوع')

    d = fd.load_fast(asset, tf)
    src = d['src']
    df = fd.as_dataframe(d)
    del d
    gc.collect()
    n_full = len(df)

    long_sig, short_sig = union_signals(df['close'].values)
    gc.collect()
    print(f'[{tf}] n={n_full:,} sig L={int(long_sig.sum()):,} '
          f'S={int(short_sig.sum()):,} SL={sl} TP={tp} mh={mh}', flush=True)

    trades = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                                max_hold=mh, allow_overlap=False)
    if trades is None or len(trades) == 0:
        res = dict(tf=tf, n_full=n_full, src=src, sl_pip=sl, tp_pip=tp,
                   max_hold=mh, n_trades=0, wr=None, exp_pip=None,
                   eligible=False, elapsed_s=round(time.time() - t0, 1))
    else:
        pnl = trades['pnl_pip'].values
        res = dict(tf=tf, n_full=n_full, src=src, sl_pip=sl, tp_pip=tp,
                   max_hold=mh, n_trades=int(len(trades)),
                   n_long_sig=int(long_sig.sum()),
                   n_short_sig=int(short_sig.sum()),
                   wr=round(100 * float((pnl > 0).mean()), 2),
                   exp_pip=round(float(pnl.mean()), 3),
                   eligible=bool(pnl.mean() > 0),
                   elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'triage_{tf}.json'), 'w',
              encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f'[{tf}] n_trades={res["n_trades"]:,} WR={res["wr"]} '
          f'exp={res["exp_pip"]} eligible={res["eligible"]} '
          f'({res["elapsed_s"]}s)', flush=True)
    del df, trades, long_sig, short_sig
    gc.collect()
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', required=True)
    a = ap.parse_args()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            triage(tf)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f'!! {tf}: {type(e).__name__}: {e}', flush=True)
        gc.collect()
    print('[triage batch done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
