# -*- coding: utf-8 -*-
"""
s723_adjudicate.py — داوری نهایی S723 (Vol-of-Vol Calm-Down) — دادهٔ کامل
================================================================================
طبق پیش‌ثبت `results/S723_PREREG_VOLOFVOL_CALMDOWN.md` (کامیت 7ba7bc38):
  خانواده {H6, H12} · thr=0.60 · mode=with · rr=2.0 · mh=55 کندل
  GEOM لیترال منجمد (بازمحاسبه ممنوع — BUG-GEOMDRIFT)
  null سمت-کلیددار اثبات‌شده (null_for از s720_adjudicate) · N_PERM=500
  n_trials=864 · SEED=20260828 · split_bar=len//2 (مسیر C)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se               # noqa: E402
from engine.rqs2 import compute_rqs2                # noqa: E402
from tools import s434_fast_data as fd              # noqa: E402
from tools.s720_adjudicate import null_for          # noqa: E402
from tools.s723_explore import calm_signals         # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s723')
SEED = 20260828
N_PERM = 500
N_TRIALS = 864
THR = 0.60
MODE = 'with'
MH = 55

# GEOM لیترال از پیش‌ثبت (7ba7bc38) — بازمحاسبه ممنوع
GEOM = {
    'H6':  dict(sl=174.9, tp=349.8),
    'H12': dict(sl=258.9, tp=517.8),
}


def adjudicate(tf: str) -> dict:
    g = GEOM[tf]
    sl, tp = g['sl'], g['tp']
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    split = len(df) // 2

    ls, ss = calm_signals(df, THR, MODE)
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=MH, allow_overlap=False)
    if len(tr) < 30:
        return dict(card=f'{ASSET}-{tf}', src=src, invalid=True,
                    n=len(tr), note='n<30')

    null = null_for(df, int(ls.sum()), int(ss.sum()), sl, tp, MH, ASSET,
                    n_perm=N_PERM, seed=SEED)
    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=df['time'], null=null,
                       n_trials=N_TRIALS, split_bar=split,
                       close=df['close'], initial_capital=10000.0,
                       allow_overlap=False)
    m = res['metrics']
    out = {
        'card': f'{ASSET}-{tf}', 'src': src,
        'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=MH, rr=2.0, thr=THR),
        'mode': MODE,
        'n_signals': int(ls.sum() + ss.sum()),
        'split_bar': split, 'bars': len(df),
        'verdict': res['verdict'], 'rqs2_score': res['score'],
        'gates': res['gates'],
        'failed_gates': sorted([k for k, v in res['gates'].items() if v is False]),
        'unknown_gates': sorted([k for k, v in res['gates'].items() if v is None]),
        'null': null, 'n_trials': N_TRIALS,
        'z_luck_bound': m.get('z_luck_bound'),
        'z_margin': m.get('z_margin'),
        'metrics': m,
        'notes': res.get('notes', []),
    }
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    tfs = sys.argv[1:] or list(GEOM)
    for tf in tfs:
        r = adjudicate(tf)
        with open(os.path.join(OUT, f'{ASSET}_{tf}_rqs2.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=1, default=str)
        if r.get('invalid'):
            print(f"[S723 داوری] {r['card']} INVALID {r['note']}", flush=True)
            continue
        m = r['metrics']
        print(f"[S723 داوری] {r['card']} · n_trials={N_TRIALS} · {N_PERM} جای‌گشت/سمت / "
              f"n={m['n_trades']} WR={m['win_rate']} lift={m['skill_lift_pp']} "
              f"z={m['skill_z']} p_perm={m['skill_p_perm']} bar={m['z_luck_bound']} "
              f"PF={m['profit_factor']} net=${m['net_profit']} DD={m['max_dd_pct']}% "
              f"RQS2={r['rqs2_score']} → {r['verdict']} / شکسته={r['failed_gates']}",
              flush=True)
    print('[done]', flush=True)


if __name__ == '__main__':
    main()
