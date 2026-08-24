# -*- coding: utf-8 -*-
"""
s722_adjudicate.py — داور S722: «لنگرِ بازشدنِ هفتگی» روی طلا

پیش‌ثبت: results/S722_PREREG_WEEKLY_OPEN_ANCHOR.md (commit 338eaa01)
مسیر C: اکتشاف روی نیمهٔ اول انجام شد؛ این داور روی **دادهٔ کامل** اجرا و
split_bar = len(df)//2 به موتور داده می‌شود تا H7 نیمهٔ دوم دست‌نخورده را بسنجد.

پارامترها/هندسه/thr از پیش‌ثبت **literal** (ضد BUG-GEOMDRIFT — حتی thr_pip از
ATRِ نیمهٔ اول منجمد شده، نه بازمحاسبه روی دادهٔ کامل).
گاردهای موروثی S437/S720/S721 عیناً حفظ شده‌اند.
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

from engine import scalp_engine as se                 # noqa: E402
from engine.rqs2 import compute_rqs2                  # noqa: E402
from tools import s434_fast_data as fd                # noqa: E402
from tools.s722_explore import weekly_anchor_signals  # noqa: E402  # همان تعریف اکتشاف
from tools.s720_adjudicate import null_for            # noqa: E402  # نال سمت-کلیددار آزموده

ASSET = 'XAUUSD'
MODE = 'cont'
N_TRIALS = 820           # پیش‌ثبت §۴ (شمارش صادقانه)
N_PERM = 500
SEED = 20260824

# هندسه/آستانه/max_hold منجمد از پیش‌ثبت §۲ — literal (ضد BUG-GEOMDRIFT)
GEOM = {
    'H2': dict(thr_pip=45.1, sl=153.5, tp=307.0, mh=36),
    'H3': dict(thr_pip=56.8, sl=193.2, tp=386.4, mh=24),
    'H4': dict(thr_pip=67.0, sl=227.8, tp=455.6, mh=18),
    'H6': dict(thr_pip=83.3, sl=283.1, tp=566.2, mh=12),
    'H8': dict(thr_pip=99.1, sl=336.8, tp=673.6, mh=9),
}

OUT = os.path.join(ROOT, 'results', '_s722')


def adjudicate(tf: str) -> dict:
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    g = GEOM[tf]
    sl, tp, mh, thr_pip = g['sl'], g['tp'], g['mh'], g['thr_pip']

    ls, ss = weekly_anchor_signals(df, thr_pip)   # cont: up⇒LONG, dn⇒SHORT
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return dict(card=f'{ASSET}-{tf}', src=src, invalid=True,
                    error=f'n<30 (n={0 if tr is None else len(tr)})',
                    n_signals=int(ls.sum() + ss.sum()))

    null = null_for(df, int(ls.sum()), int(ss.sum()), sl, tp, mh, ASSET,
                    n_perm=N_PERM, seed=SEED)
    split_bar = len(df) // 2

    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(float),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)
    gg = res.get('gates') or {}
    m = res.get('metrics') or {}
    return {
        'card': f'{ASSET}-{tf}', 'src': src,
        'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                         rr=round(tp / sl, 3), thr_pip=thr_pip),
        'mode': MODE,
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
    ap.add_argument('--tfs', default='H2,H3,H4,H6,H8')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for tf in [x.strip() for x in a.tfs.split(',') if x.strip()]:
        print(f'[S722 داوری] {ASSET}-{tf} · n_trials={N_TRIALS} · '
              f'{N_PERM} جای‌گشت/سمت', flush=True)
        out = adjudicate(tf)
        path = os.path.join(OUT, f'{ASSET}_{tf}_rqs2.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=str)
        if out.get('invalid'):
            print(f'  ⛔ نامعتبر: {out["error"]}', flush=True)
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
