# -*- coding: utf-8 -*-
"""
s725_adjudicate.py — داوری نهایی S725 (Failed Shock) — دادهٔ کامل
================================================================================
طبق پیش‌ثبت `results/S725_PREREG_FAILED_SHOCK.md`:
  خانواده {H2,H3,H4,H6,H8} · θ=1.618×ATR21 · mode=with · rr=1.0 · mh=34 کندل
  GEOM لیترال منجمد (sl=tp: H2 94.8 · H3 119.3 · H4 140.7 · H6 174.8 · H8 208.0 — BUG-GEOMDRIFT)
  null سمت-کلیددار اثبات‌شده (null_for از s720_adjudicate) · N_PERM=500
  n_trials=594 · SEED=20260904 · split_bar=len//2 (مسیر C) · کامیت قبل از اجرا
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
from tools.s725_explore import failed_shock_signals         # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s725')
SEED = 20260904
N_PERM = 500
N_TRIALS = 594
THETA = 1.618
MODE = 'with'
MH = 34

# GEOM لیترال از پیش‌ثبت (S725_PREREG_FAILED_SHOCK.md) — بازمحاسبه ممنوع
GEOM = {
    'H2': dict(sl=94.8, tp=94.8),
    'H3': dict(sl=119.3, tp=119.3),
    'H4': dict(sl=140.7, tp=140.7),
    'H6': dict(sl=174.8, tp=174.8),
    'H8': dict(sl=208.0, tp=208.0),
}


def adjudicate(tf: str) -> dict:
    g = GEOM[tf]
    sl, tp = g['sl'], g['tp']
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    split = len(df) // 2

    ls, ss = failed_shock_signals(df, THETA, MODE)
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
        'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=MH, rr=1.0, theta=THETA),
        'mode': MODE,
        'n_signals': int(ls.sum() + ss.sum()),
        'split_bar': split, 'bars': len(df),
        'verdict': res.get('verdict'), 'rqs2_score': res.get('rqs2_score'),
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
            print(f"[S725 داوری] {r['card']} INVALID {r['note']}", flush=True)
            continue
        m = r['metrics']
        print(f"[S725 داوری] {r['card']} · n_trials={N_TRIALS} · {N_PERM} جای‌گشت/سمت / "
              f"n={m['n_trades']} WR={m['win_rate']} lift={m['skill_lift_pp']} "
              f"z={m['skill_z']} p_perm={m['skill_p_perm']} bar={m['z_luck_bound']} "
              f"PF={m['profit_factor']} net=${m['net_profit']} DD={m['max_dd_pct']}% "
              f"RQS2={r['rqs2_score']} → {r['verdict']} / شکسته={r['failed_gates']}",
              flush=True)
    print('[done]', flush=True)


if __name__ == '__main__':
    main()
