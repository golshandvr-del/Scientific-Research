# -*- coding: utf-8 -*-
"""
S362-PARITY (سمتِ پایتون) — تولیدِ اندیس‌های آزمون و **مقایسهٔ بیت‌به‌بیت** با TS.

گردشِ کار:
  1) `--emit CARD`   → ماسک‌های پایتون را می‌سازد و فایلِ اندیس‌ها را می‌نویسد
                       (همهٔ `active`های پایتون + نمونهٔ تصادفیِ قطعی).
  2) `node strategies/s362_parity_masks.mjs CARD`  → تصمیمِ TS در همان اندیس‌ها.
  3) `--check CARD`  → مقایسه، و **خروجِ ناموفق** اگر حتی یک اختلاف باشد.

نتیجه در `results/_scan_S362/parity_CARD.json` ذخیره می‌شود تا سندِ نهایی به یک
عددِ اندازه‌گیری‌شده ارجاع دهد، نه به یک ادعا.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                                    # noqa: E402
from strategies import s362_cocard_masks as M                            # noqa: E402

TMP = '.tmp_logs'
OUT = 'results/_scan_S362'
RNG_SEED = 20250801
N_RANDOM = 400
MAX_POS_PER_LAYER = 600     # سقفِ اندیس‌های مثبت در هر لایه (هزینهٔ TS خطی است)


def load(card):
    asset, tf = card.split('-')
    p = os.path.join('data', f'{asset}_{tf}.csv')
    if not os.path.exists(p):
        return None, None
    return se.load_data(p), asset


def emit(card):
    df, _ = load(card)
    if df is None:
        print(f'{card}: NO_DATA', flush=True)
        return
    n = len(df)
    src, missing = M.build_sources(df, card)
    idx = set()
    counts = {}
    for name in ('S326', 'S327', 'S333', 'S335'):
        if name not in src:
            counts[name] = None
            continue
        pos = np.flatnonzero(src[name])
        counts[name] = int(pos.size)
        # اگر مثبت‌ها زیاد بودند، نمونهٔ **قطعیِ** یکنواخت از سراسرِ سری (نه ۶۰۰
        # تایِ اول) تا سوگیریِ زمانی وارد نشود.
        if pos.size > MAX_POS_PER_LAYER:
            pos = pos[np.linspace(0, pos.size - 1, MAX_POS_PER_LAYER).astype(int)]
        idx.update(int(i) for i in pos)
    rng = np.random.default_rng(RNG_SEED)
    lo = int(n * 0.35)
    idx.update(int(i) for i in rng.integers(lo, n, size=N_RANDOM))
    order = sorted(idx)
    os.makedirs(TMP, exist_ok=True)
    with open(os.path.join(TMP, f'parity_idx_{card}.json'), 'w') as f:
        json.dump(dict(card=card, indices=order), f)
    print(f'{card}: emitted {len(order)} test indices | python active counts: '
          f'{counts} | missing sources: {missing}', flush=True)


def check(card):
    df, _ = load(card)
    if df is None:
        print(f'{card}: NO_DATA', flush=True)
        return True
    ts_path = os.path.join(TMP, f'parity_ts_{card}.json')
    if not os.path.exists(ts_path):
        print(f'{card}: TS output missing — run the node step first', flush=True)
        return False
    ts = json.load(open(ts_path))
    sample = np.asarray(ts['sample'], dtype=int)
    src, missing = M.build_sources(df, card)

    rec = dict(card=card, n_bars=len(df), n_compared=int(sample.size),
               missing_sources=missing, layers={})
    all_ok = True
    for name in ('S326', 'S327', 'S333', 'S335'):
        tsv = ts['layers'].get(name)
        if tsv is None:
            rec['layers'][name] = dict(status='NO_DEPLOYED_CFG')
            continue
        a = np.asarray(tsv, dtype=bool)
        b = src[name][sample]
        dis = np.flatnonzero(a != b)
        ok = dis.size == 0
        all_ok &= ok
        rec['layers'][name] = dict(
            status='PARITY_OK' if ok else 'PARITY_FAIL',
            ts_active=int(a.sum()), py_active=int(b.sum()),
            n_compared=int(sample.size), n_disagree=int(dis.size),
            py_true_ts_false=int(np.sum(b & ~a)),
            ts_true_py_false=int(np.sum(a & ~b)),
            first_disagreements=[int(sample[i]) for i in dis[:10]])
        print(f"  {name}: {'OK ' if ok else 'FAIL'} compared={sample.size} "
              f"ts_active={int(a.sum())} py_active={int(b.sum())} "
              f"disagree={dis.size}", flush=True)

    rec['all_parity_ok'] = bool(all_ok)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f'parity_{card}.json'), 'w') as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(f'{card}: ALL_PARITY_OK={all_ok}', flush=True)
    return all_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--emit')
    ap.add_argument('--check')
    a = ap.parse_args()
    if a.emit:
        emit(a.emit)
    elif a.check:
        sys.exit(0 if check(a.check) else 1)


if __name__ == '__main__':
    main()
