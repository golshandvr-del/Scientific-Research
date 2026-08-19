# -*- coding: utf-8 -*-
"""
s721_adjudicate.py — داور S721: «فشارِ ردِ جهت‌دارِ سایه‌ها» روی طلا

پیش‌ثبت: results/S721_PREREG_WICK_REJECTION_PRESSURE.md (commit db3072ac)
مسیر C: اکتشاف روی نیمهٔ اول انجام شد؛ این داور روی **دادهٔ کامل** اجرا و
split_bar = len(df)//2 به موتور داده می‌شود تا H7 نیمهٔ دوم دست‌نخورده را بسنجد.

پارامترها/هندسه از پیش‌ثبت **literal** خوانده می‌شوند (ضد BUG-GEOMDRIFT).
گاردهای موروثی S437 (BUG-PERMK/NULLUNCOND/SCOREKEY/ZBARAPPROX/PIPGUESS/n≥30)
عیناً از داور S720 حفظ شده‌اند.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se               # noqa: E402
from engine.rqs2 import compute_rqs2                # noqa: E402
from tools import s434_fast_data as fd              # noqa: E402
from tools.s721_explore import rejection_signals    # noqa: E402  # همان تعریف اکتشاف
from tools.s720_adjudicate import null_for          # noqa: E402  # نال سمت-کلیددار آزموده

ASSET = 'XAUUSD'
W = 13
THR = 0.35
MODE = 'cont'
MH = 13                  # هم‌مقیاس با W — پیش‌ثبت §۲
N_TRIALS = 2650          # پیش‌ثبت §۴ (شمارش صادقانه)
N_PERM = 500
SEED = 20260819

# هندسهٔ منجمد از پیش‌ثبت §۲ — literal، نه بازمحاسبه (ضد BUG-GEOMDRIFT)
GEOM = {
    'H2': dict(sl=153.5, tp=307.0),
    'H4': dict(sl=227.8, tp=455.6),
    'H6': dict(sl=283.1, tp=566.2),
}

OUT = os.path.join(ROOT, 'results', '_s721')


def adjudicate(tf: str) -> dict:
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    g = GEOM[tf]
    sl, tp = g['sl'], g['tp']

    ls, ss = rejection_signals(df, W, THR, MODE)
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=MH, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return dict(card=f'{ASSET}-{tf}', src=src, invalid=True,
                    error=f'n<30 (n={0 if tr is None else len(tr)})',
                    n_signals=int(ls.sum() + ss.sum()))

    null = null_for(df, int(ls.sum()), int(ss.sum()), sl, tp, MH, ASSET,
                    n_perm=N_PERM, seed=SEED)
    split_bar = len(df) // 2      # مرز اکتشاف/OOS مسیر C

    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(float),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)
    gg = res.get('gates') or {}
    m = res.get('metrics') or {}
    return {
        'card': f'{ASSET}-{tf}', 'src': src,
        'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=MH,
                         rr=round(tp / sl, 3)),
        'w': W, 'thr': THR, 'mode': MODE,
        'n_signals': int(ls.sum() + ss.sum()),
        'split_bar': split_bar, 'bars': len(df),
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: gg.get(k) for k in sorted(gg)},
        'failed_gates': sorted(k for k, v in gg.items() if v is False),
        'unknown_gates': sorted(k for k, v in gg.items() if v is None),
        'null': null,
        'n_trials': N_TRIALS,
        'z_luck_bound': m.get('z_luck_bound'),
        'z_margin': m.get('z_margin'),
        'metrics': {k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share',
            'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm',
            'p_emp', 'p_adj_bonferroni', 'perm_k', 'perm_max')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', default='H2,H4,H6')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for tf in [x.strip() for x in a.tfs.split(',') if x.strip()]:
        print(f'[S721 داوری] {ASSET}-{tf} · n_trials={N_TRIALS} · '
              f'{N_PERM} جای‌گشت/سمت', flush=True)
        out = adjudicate(tf)
        path = os.path.join(OUT, f'{ASSET}_{tf}_rqs2.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        if out.get('invalid'):
            print(f'  ⛔ نامعتبر: {out["error"]} (سیگنال={out.get("n_signals")})',
                  flush=True)
            continue
        m = out['metrics']
        assert m['win_rate'] is not None and m['skill_lift_pp'] is not None, \
            'metrics None — ورودی ناقص به موتور'
        print(f"  n={m['n_trades']} WR={m['win_rate']} lift={m['skill_lift_pp']} "
              f"z={m['skill_z']} p_perm={m['skill_p_perm']} bar={out['z_luck_bound']} "
              f"PF={m['profit_factor']} net=${m['net_profit']} DD={m['max_dd_pct']}% "
              f"RQS2={out['rqs2_score']} → {out['verdict']}", flush=True)
        print(f"  شکسته={out['failed_gates']} نامعلوم={out['unknown_gates']}",
              flush=True)
    print('[done]', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
