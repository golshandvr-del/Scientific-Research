# -*- coding: utf-8 -*-
"""S555 re-adjudication — HARNESS FIX ONLY (no signal/geometry/null change).
The first pass called compute_rqs2 with tp_pip=None; per engine docstring that
disables H2 and applies legacy floors (H1 WR>=60, H7 OOS WR>=57) and can never
ACCEPT. Here sl_pip/tp_pip = median of the SAME trades (RR=1.5 frozen). Trades,
null and split are read back from the checkpoint files — nothing recomputed."""
import json, sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import rqs2
from tools import s434_fast_data as fd
OUT = 'results/_scan_S555'
for card in (sys.argv[1:] or ['H8', 'H6', 'H12', 'D1']):
    d = json.load(open(f'{OUT}/{card}.json'))
    tr = pd.read_csv(f'{OUT}/{card}_trades.csv')
    dd = fd.load_fast('XAUUSD', card); assert 'mt5_full' in dd['src']
    t64 = dd['time'].astype('datetime64[s]').astype('datetime64[ns]')
    te = t64[tr['entry_bar'].to_numpy(int)].astype(np.int64)
    holdout = te >= int(d['split_ns'])
    null = {k: {kk: vv for kk, vv in v.items() if kk != 'uncond_n'} for k, v in d['null'].items()}
    sl = float(np.median(tr['sl_pip'])); tp = float(np.median(tr['tp_pip']))
    res = rqs2.compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp, bar_time=t64,
                            close=dd['close'].astype(float), null=null,
                            n_trials=d['n_trials'], holdout_mask=holdout, allow_overlap=False)
    print(rqs2.format_rqs2(f'S555_{card}_tpfix', res))
    m = res['metrics']; print('   be_cost=', m.get('breakeven_wr_cost'), 'oos=', m.get('oos'),
          'notes=', res.get('notes'))
    d['tpfix'] = dict(sl_pip=sl, tp_pip=tp, verdict=res['verdict'], rqs2_score=res['rqs2_score'],
                      gates=res['gates'], metrics=m, notes=res['notes'])
    json.dump(d, open(f'{OUT}/{card}.json', 'w'), ensure_ascii=False, default=str, indent=1)
