# -*- coding: utf-8 -*-
"""S983 — داورِ رسمیِ یک‌باره (طبق الحاقیهٔ انجماد، کامیت d60535e1)
================================================================================
پیکربندیِ منجمد: XAUUSD-H8 · W=34 · θ=0.9 · main · SL_k=1.2 · RR=1.6
split_bar = n_all//2 · null = build_null_fast K=600 seed=20260806 · n_trials=912
حکم فقط از compute_rqs2 — هرگز دستی.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                    # noqa: E402
from engine import rqs2 as R                             # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402
from tools.audit_fast_null import build_null_fast        # noqa: E402
from strategies.s983_tsm_cross_scan import atr_arr, tsm_cross_signals  # noqa: E402

ASSET, TF = 'XAUUSD', 'H8'
W, THETA, SL_K, RR = 34, 0.9, 1.2, 1.6
MAX_HOLD = 64
N_TRIALS = 912
OUT = 'results/_s983'


def main():
    d = fd.load_fast(ASSET, TF)
    assert 'mt5_full' in d['src'], f"دادهٔ کامل نیست: {d['src']}"
    df = fd.as_dataframe(d)
    n_all = len(df)
    split_bar = n_all // 2
    print(f'src={d["src"]}  bars={n_all:,}  split_bar={split_bar:,}')

    a = atr_arr(df)
    c = df['close'].to_numpy(float)
    pip = se.ASSETS[ASSET]['pip']
    # sl_base منجمد از اسکنِ نیمهٔ اول (عینِ الحاقیه)
    scan = json.load(open(f'{OUT}/scan_{TF}.json'))
    sl_base_pip = scan['sl_base_pip']
    sl_pip = sl_base_pip * SL_K
    tp_pip = sl_pip * RR
    print(f'sl={sl_pip:.2f}pip tp={tp_pip:.2f}pip (از نیمهٔ اول منجمد)')

    cu, cd = tsm_cross_signals(c, a, W, THETA)
    tr = se.simulate_trades(df, cu, cd, sl_pip, tp_pip, ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
    print(f'total trades (full span) = {len(tr)}')

    # مدلِ صفر — هر دو سمت، روی کلِ داده
    n_long = int((tr['direction'] == 'long').sum())
    n_short = len(tr) - n_long
    null = {
        'long': build_null_fast(df, ASSET, sl_pip, tp_pip, MAX_HOLD, 'long',
                                max(n_long, 1), k=600, seed=20260806),
        'short': build_null_fast(df, ASSET, sl_pip, tp_pip, MAX_HOLD, 'short',
                                 max(n_short, 1), k=600, seed=20260806),
    }
    print('null long:', {k: round(v, 4) if isinstance(v, float) else v
                         for k, v in (null['long'] or {}).items()})
    print('null short:', {k: round(v, 4) if isinstance(v, float) else v
                          for k, v in (null['short'] or {}).items()})

    bar_time = df['time'].to_numpy(float)
    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=bar_time, close=c, null=null,
                         n_trials=N_TRIALS, split_bar=split_bar)
    print()
    print(R.format_rqs2('S983_TsmCross_XAUUSD-H8', res))
    with open(f'{OUT}/H8_rqs2_verdict.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/H8_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/H8_rqs2_verdict.json')


if __name__ == '__main__':
    main()
