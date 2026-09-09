# -*- coding: utf-8 -*-
"""S986 — داورِ رسمیِ یک‌باره (طبق S986_ADDENDUM_FREEZE.md)
================================================================================
پیکربندیِ منجمد: XAUUSD-D1 · θ=1.618 · W=8 · mirror · SL_k=1.8 · RR=1.6
split_bar = n_all//2 · null = build_null_fast K=600 seed=20260806 · n_trials=608
حکم فقط از compute_rqs2 — هرگز دستی.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                    # noqa: E402
from engine import rqs2 as R                             # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402
from tools.audit_fast_null import build_null_fast        # noqa: E402
from strategies.s986_shock_extreme_break_scan import atr_arr, shock_candles, break_signals, ATR_SHOCK  # noqa: E402

ASSET, TF = 'XAUUSD', 'D1'
THETA, W, MODE = 1.618, 8, 'mirror'
SL_K, RR = 1.8, 1.6
MAX_HOLD = 32
N_TRIALS = 608
OUT = 'results/_s986'


def main():
    d = fd.load_fast(ASSET, TF)
    assert 'mt5_full' in d['src'], f"دادهٔ کامل نیست: {d['src']}"
    df = fd.as_dataframe(d)
    n_all = len(df)
    split_bar = n_all // 2
    print(f'src={d["src"]}  bars={n_all:,}  split_bar={split_bar:,}')

    c = df['close'].to_numpy(float)
    scan = json.load(open(f'{OUT}/scan_{TF}.json'))
    sl_base_pip = scan['sl_base_pip']                     # منجمد از نیمهٔ اول
    sl_pip = sl_base_pip * SL_K
    tp_pip = sl_pip * RR
    print(f'sl={sl_pip:.2f}pip tp={tp_pip:.2f}pip (از نیمهٔ اول منجمد)')

    atr21 = atr_arr(df, ATR_SHOCK)
    shock, body_sgn = shock_candles(df, atr21, THETA)
    lt, st, _, _, stats = break_signals(df, shock, body_sgn, W)
    print('event stats (full span):', stats)
    ls, ss = (lt, st) if MODE == 'main' else (st, lt)
    tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip, ASSET,
                            max_hold=MAX_HOLD, allow_overlap=False)
    print(f'total trades (full span) = {len(tr)}')

    n_long = int((tr['direction'] == 'long').sum())
    n_short = len(tr) - n_long
    null = {
        'long': build_null_fast(df, ASSET, sl_pip, tp_pip, MAX_HOLD, 'long',
                                max(n_long, 1), k=600, seed=20260806),
        'short': build_null_fast(df, ASSET, sl_pip, tp_pip, MAX_HOLD, 'short',
                                 max(n_short, 1), k=600, seed=20260806),
    }
    for side in ('long', 'short'):
        print(f'null {side}:', {k: round(v_, 4) if isinstance(v_, float) else v_
                                for k, v_ in (null[side] or {}).items()})

    bar_time = df['time'].to_numpy(float)
    res = R.compute_rqs2(tr, ASSET, sl_pip=sl_pip, tp_pip=tp_pip,
                         bar_time=bar_time, close=c, null=null,
                         n_trials=N_TRIALS, split_bar=split_bar)
    print()
    print(R.format_rqs2(f'S986_ShockExtremeBreak_{ASSET}-{TF}', res))
    with open(f'{OUT}/{TF}_rqs2_verdict.json', 'w') as f:
        json.dump(res, f, ensure_ascii=False, default=str)
    tr.to_csv(f'{OUT}/{TF}_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/{TF}_rqs2_verdict.json')


if __name__ == '__main__':
    main()
