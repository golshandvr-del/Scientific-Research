# -*- coding: utf-8 -*-
"""
s720_adjudicate.py — داور S720: «تشدید کشش چندمقیاسی، ادامه‌دهنده» روی طلا

پیش‌ثبت: results/S720_PREREG_MULTISCALE_STRETCH_CONTINUATION.md (commit 8b723ca3)
مسیر C: اکتشاف روی نیمهٔ اول انجام شد؛ این داور روی **دادهٔ کامل** اجرا و
split_bar = len(df)//2 به موتور داده می‌شود تا H7 نیمهٔ دوم دست‌نخورده را بسنجد.

پارامترها/هندسه از پیش‌ثبت **literal** خوانده می‌شوند (ضد BUG-GEOMDRIFT).
گاردهای موروثی S437 (BUG-PERMK/NULLUNCOND/SCOREKEY/ZBARAPPROX/PIPGUESS/n≥30)
عیناً حفظ شده‌اند.
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
from tools.s720_explore import stretch_signals      # noqa: E402  # همان تعریف اکتشاف

ASSET = 'XAUUSD'
THR = 2.5
MODE = 'cont'
MH = 55
N_TRIALS = 2100          # پیش‌ثبت §۴
N_PERM = 500             # درس S435
SEED = 20260816

# هندسهٔ منجمد از پیش‌ثبت §۲ — literal، نه بازمحاسبه (ضد BUG-GEOMDRIFT)
GEOM = {
    'M15': dict(sl=51.4,  tp=102.8),
    'M20': dict(sl=60.2,  tp=120.4),
    'M30': dict(sl=74.6,  tp=149.2),
    'H1':  dict(sl=107.8, tp=215.6),
    'H2':  dict(sl=153.5, tp=307.0),
    'H3':  dict(sl=193.2, tp=386.4),
}

OUT = os.path.join(ROOT, 'results', '_s720')


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def null_for(df, n_long_sig, n_short_sig, sl, tp, mh, asset,
             n_perm=N_PERM, seed=SEED):
    """نال اندازه‌گیری‌شده با هندسهٔ خود همان کارت، هر سمت جدا.

    ساختار کانونی سمت-کلیددار (long/short) — عیناً الگوی s437_adjudicate،
    گسترش‌یافته برای لایهٔ دوطرفه: جای‌گشتِ هر سمت با همان تعداد سیگنال
    واقعی همان سمت ساخته می‌شود.
    """
    n = len(df)
    z = np.zeros(n, bool)
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)

    out = {}
    for side, k_sig in (('long', n_long_sig), ('short', n_short_sig)):
        if k_sig <= 0:
            out[side] = {}
            continue
        # مبنای غیرشرطی همان سمت
        pick = rng.choice(vidx, size=min(20000, len(vidx)), replace=False)
        um = np.zeros(n, bool)
        um[pick] = True
        if side == 'long':
            tu = se.simulate_trades(df, um, z, sl, tp, asset, max_hold=mh,
                                    allow_overlap=True)
        else:
            tu = se.simulate_trades(df, z, um, sl, tp, asset, max_hold=mh,
                                    allow_overlap=True)
        wr_unc = _wr(tu)

        perm = []
        for _ in range(n_perm):
            p = rng.choice(vidx, size=min(k_sig, len(vidx)), replace=False)
            pm = np.zeros(n, bool)
            pm[p] = True
            if side == 'long':
                t = se.simulate_trades(df, pm, z, sl, tp, asset, max_hold=mh,
                                       allow_overlap=False)
            else:
                t = se.simulate_trades(df, z, pm, sl, tp, asset, max_hold=mh,
                                       allow_overlap=False)
            w = _wr(t)
            if w is not None:
                perm.append(w)
        pa = np.array(perm, float) if perm else np.array([])
        out[side] = dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=int(pa.size))          # گارد BUG-PERMK
    return out


def adjudicate(tf: str) -> dict:
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    g = GEOM[tf]
    sl, tp = g['sl'], g['tp']

    c = df['close'].to_numpy(float)
    ls, ss = stretch_signals(c, THR, MODE)
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=MH, allow_overlap=False)
    if tr is None or len(tr) < 30:
        return dict(card=f'{ASSET}-{tf}', src=src, invalid=True,
                    error=f'n<30 (n={0 if tr is None else len(tr)})',
                    n_signals=int(ls.sum() + ss.sum()))

    null = null_for(df, int(ls.sum()), int(ss.sum()), sl, tp, MH, ASSET)
    split_bar = len(df) // 2      # مرز اکتشاف/OOS مسیر C — پیش‌ثبت §۵

    res = compute_rqs2(tr, ASSET, sl_pip=sl, tp_pip=tp,
                       bar_time=pd.to_numeric(df['time']).to_numpy(),
                       close=df['close'].to_numpy(float),
                       null=null, n_trials=N_TRIALS, split_bar=split_bar,
                       initial_capital=10000.0, allow_overlap=False)
    gg = res.get('gates') or {}
    m = res.get('metrics') or {}
    # گارد BUG-SCOREKEY: کلید rqs2_score؛ failed/unknown از gates مشتق می‌شوند
    return {
        'card': f'{ASSET}-{tf}', 'src': src,
        'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=MH,
                         rr=round(tp / sl, 3)),
        'thr': THR, 'mode': MODE, 'windows': [21, 55, 89],
        'n_signals': int(ls.sum() + ss.sum()),
        'split_bar': split_bar, 'bars': len(df),
        'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: gg.get(k) for k in sorted(gg)},
        'failed_gates': sorted(k for k, v in gg.items() if v is False),
        'unknown_gates': sorted(k for k, v in gg.items() if v is None),
        'null': null,
        'n_trials': N_TRIALS,
        'z_luck_bound': m.get('z_luck_bound'),   # گارد BUG-ZBARAPPROX
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
    ap.add_argument('--tfs', default='M15,M20,M30,H1,H2,H3')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    for tf in [x.strip() for x in a.tfs.split(',') if x.strip()]:
        print(f'[S720 داوری] {ASSET}-{tf} · n_trials={N_TRIALS} · '
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
        # assert صریح — درس BUG-DATASETDRIFT: موتور بی‌صدا تحمل می‌کند، داور نباید
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
