"""
S908 — Displacement Pool H4·H6·H8 · XAUUSD · RQS2 v2.6 · Path C
==================================================================
رویداد منجمد از S906: شوک range ≥ 2.058·ATR21[i−1] پس از ۳۴ کندل بدون شوک؛
جهت = بدنهٔ شوک. سه TF همجوار {H4,H6,H8} هر یک مستقل شبیه‌سازی و روی محور
زمان تقویمی با FIFO کانونی (`engine/rqs2_pool._fifo_calendar`) ادغام می‌شوند.

⚠️ تفاوت عمدی با `pool_cards`: آن تابع اعضای lift≤0 یا «رقیق‌کننده» را حذف
می‌کند (انتخاب زیرمجموعه). پیش‌ثبت S908 اعضا را **ثابت** اعلام کرده تا
cherry-pick ممکن نباشد؛ پس ادغام با هر سه عضو انجام می‌شود و خروجیِ
`pool_cards` فقط به‌عنوان تشخیصی (P1/P2) گزارش می‌شود.

پیش‌ثبت: results/S908_PREREGISTRATION.md (کامیت d29d73b9، قبل از هر آزمون).
گرید منجمد: k_sl∈{1.272,2.058} × hold∈{13,34} ⇒ N_eff=4؛ n_trials تجمعی=52.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import rqs2                            # noqa: E402
from engine import rqs2_pool as rp                 # noqa: E402
from tools import s434_fast_data as fd             # noqa: E402
import importlib.util                              # noqa: E402

_spec = importlib.util.spec_from_file_location(
    's906', os.path.join(ROOT, 'strategies', 's906_tranquility_break.py'))
s906 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s906)

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s908')
MEMBERS = ('H4', 'H6', 'H8')          # ثابت — انتخاب زیرمجموعه ممنوع
THETA, L_DROUGHT, RR = 2.058, 34, 1.618   # قفل S906
GRID_KSL = (1.272, 2.058)
GRID_HOLD = (13, 34)
N_EFF = 4
N_TRIALS_CUM = 52                     # 3×16 (S906 H4/H6/H8) + 4
SPLIT_FRAC = 0.60
K_PERM = 1000
SEED = 908


def member_trades(tf, k_sl, hold, t_lo=None, t_hi=None):
    """شبیه‌سازی مستقل یک عضو؛ اگر t_lo/t_hi داده شود فقط سیگنال‌های در بازه."""
    d = fd.load_fast(ASSET, tf)
    atr = s906.atr_pip(d)
    atr_prev = s906.build_features(d)
    ls, ss = s906.build_signals(d, L_DROUGHT, THETA, atr_prev)
    t = d['time']
    if t_lo is not None:
        m = t >= t_lo; ls &= m; ss &= m
    if t_hi is not None:
        m = t < t_hi; ls &= m; ss &= m
    sl = np.nan_to_num(np.clip(k_sl * atr, 5.0, None), nan=5.0)
    tp = RR * sl
    tr = s906.sim_chunked(d, ls, ss, sl, tp, hold)
    return d, ls, ss, tr


def lift_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return float((tr['pnl_pip'] > 0).mean() * 100.0 - 50.0)


def pool_all(members):
    """ادغام همهٔ اعضا (بدون فیلتر) روی زمان تقویمی + FIFO کانونی."""
    frames = []
    for m in members:
        if m['tr'] is None or len(m['tr']) == 0:
            continue
        cal = rp._to_calendar(m['tr'], m['dt'])
        cal['src_card'] = m['card']
        frames.append(cal)
    if not frames:
        return None, 0
    merged = pd.concat(frames, ignore_index=True)
    return rp._fifo_calendar(merged), len(merged)


def blend_pool_null(members, pool_df):
    """وزن = سهم هر عضو در استخر نهایی؛ sd با Σw·sd (کران بالای محافظه‌کار)."""
    w_by = pool_df['src_card'].value_counts().to_dict()
    tot = float(sum(w_by.values()))
    out = {}
    for side in ('long', 'short'):
        ref = sd = mx = 0.0; kmin = None; wsum = 0.0
        for m in members:
            w = float(w_by.get(m['card'], 0)) / tot
            if w <= 0 or m['null'] is None:
                continue
            nd = m['null'][side]
            ref += w * nd['perm_mean']; sd += w * nd['perm_sd']
            mx += w * nd['perm_max']; wsum += w
            kmin = nd['perm_k'] if kmin is None else min(kmin, nd['perm_k'])
        if wsum <= 0:
            return None
        out[side] = dict(uncond_wr=ref / wsum, perm_mean=ref / wsum,
                         perm_sd=sd / wsum, perm_max=mx / wsum, perm_k=kmin)
    return out


def phase_discover():
    os.makedirs(OUT, exist_ok=True)
    d8 = fd.load_fast(ASSET, 'H8')
    t_split = int(d8['time'][int(d8['n_bars'] * SPLIT_FRAC)])
    print(f"t_split={t_split} ({pd.to_datetime(t_split, unit='s')}) src_H8={d8['src']}", flush=True)
    del d8
    results = {}
    t0 = time.time()
    for k_sl in GRID_KSL:
        for hold in GRID_HOLD:
            key = f'k{k_sl}_h{hold}'
            members = []
            for tf in MEMBERS:
                d, ls, ss, tr = member_trades(tf, k_sl, hold, t_hi=t_split)
                members.append(dict(card=tf, tr=tr, dt=pd.to_datetime(d['time'], unit='s').values,
                                    lift=lift_of(tr), n=int(len(tr)) if tr is not None else 0))
            pool, n_before = pool_all(members)
            if pool is None or len(pool) == 0:
                results[key] = dict(n=0); continue
            wr = float((pool['pnl_pip'] > 0).mean() * 100.0)
            net = float(pool['pnl_pip'].sum())
            results[key] = dict(n=int(len(pool)), n_before=n_before, wr=round(wr, 3),
                                net=round(net, 1),
                                members={m['card']: dict(n=m['n'], lift=None if m['lift'] is None else round(m['lift'], 2))
                                         for m in members})
            print(f'[{key}] pool n={len(pool)} (pre-FIFO {n_before}) wr={wr:.2f} net={net:.0f} '
                  f'members={results[key]["members"]} ({time.time()-t0:.0f}s)', flush=True)
    with open(os.path.join(OUT, 'discover_POOL.json'), 'w') as f:
        json.dump(dict(t_split=t_split, combos=results), f, indent=1)
    best_key, best_score = None, -1e18
    for key, r in results.items():
        if r.get('n', 0) < 150:
            continue
        sc = r['wr'] + 0.001 * r['net']
        if sc > best_score:
            best_key, best_score = key, sc
    locked = dict(t_split=t_split, members=list(MEMBERS), theta=THETA, L=L_DROUGHT, rr=RR,
                  n_eff=N_EFF, n_trials_cum=N_TRIALS_CUM, criterion='wr+0.001*net', min_n=150,
                  best_key=best_key, best=results.get(best_key) if best_key else None)
    with open(os.path.join(OUT, 'locked_POOL.json'), 'w') as f:
        json.dump(locked, f, indent=1)
    print(json.dumps(locked, indent=1))


def phase_final():
    with open(os.path.join(OUT, 'locked_POOL.json')) as f:
        locked = json.load(f)
    if not locked['best_key']:
        print('NO LOCKED CONFIG — no test to run.'); return
    k_sl = float(locked['best_key'].split('_')[0][1:])
    hold = int(locked['best_key'].split('_')[1][1:])
    t_split = int(locked['t_split'])
    print(f"FINAL S908 POOL · locked={locked['best_key']} · n_trials={N_TRIALS_CUM} · t_split={t_split}", flush=True)
    members = []
    for idx, tf in enumerate(MEMBERS):
        d, ls, ss, tr = member_trades(tf, k_sl, hold)
        null = s906.build_null_perm(d, ls, ss, hold, K=K_PERM, seed=SEED + idx)
        sl_med = float(np.median(tr['sl_pip'].values)) if len(tr) else None
        members.append(dict(card=tf, tr=tr, dt=pd.to_datetime(d['time'], unit='s').values,
                            lift=lift_of(tr), n=int(len(tr)), null=null, sl_med=sl_med, src=d['src'],
                            is_lift=lift_of(tr[tr['signal_bar'] < np.searchsorted(d['time'], t_split)]),
                            oos_lift=lift_of(tr[tr['signal_bar'] >= np.searchsorted(d['time'], t_split)])))
        print(f"  member {tf}: n={len(tr)} lift={members[-1]['lift']:.2f} IS={members[-1]['is_lift']} OOS={members[-1]['oos_lift']} src={d['src']}", flush=True)
    pool, n_before = pool_all(members)
    pool = pool.sort_values('t_entry', kind='mergesort').reset_index(drop=True)
    print(f'pool n={len(pool)} (pre-FIFO {n_before}) by card={pool["src_card"].value_counts().to_dict()}', flush=True)
    null = blend_pool_null(members, pool)
    bar_time = (pool['t_entry'].values / 1e9).astype('int64')
    split_idx = int((bar_time < t_split).sum())
    sl_med = float(np.median(pool['sl_pip'].values)); tp_med = RR * sl_med
    pool2 = pool.copy()
    pool2['entry_bar'] = np.arange(len(pool2)); pool2['exit_bar'] = np.arange(len(pool2))
    r = rqs2.compute_rqs2(pool2, ASSET, sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                          null=null, n_trials=N_TRIALS_CUM, split_bar=split_idx, close=None)
    # تشخیصی P2: pool_cards کانونی (با فیلتر) — فقط گزارش
    diag = rp.pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'], lift=m['lift']) for m in members])
    diag_out = None if diag is None else dict(used=diag['used'], dropped=diag['dropped'],
                                              n_after=diag['n_after'])
    out = dict(locked_key=locked['best_key'], members=[{k: v for k, v in m.items() if k not in ('tr', 'dt', 'null')} for m in members],
               n_pool=int(len(pool)), n_before_fifo=n_before, split_idx=split_idx,
               sl_med=round(sl_med, 1), tp_med=round(tp_med, 1), null=null,
               verdict=r['verdict'], score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                        for k, v in r.get('metrics', {}).items()},
               notes=r.get('notes'), canonical_pool_cards_diag=diag_out)
    with open(os.path.join(OUT, 'final_POOL.json'), 'w') as f:
        json.dump(out, f, indent=1, default=str)
    print(f"\nVERDICT={r['verdict']} score={r.get('rqs2_score')}")
    print(f"gates={json.dumps(r.get('gates'))}")
    m = r.get('metrics', {})
    print(f"n={m.get('n_trades')} wr={m.get('win_rate')} lift={m.get('skill_lift_pp')} z={m.get('skill_z')} p={m.get('skill_p_perm')} PF={m.get('profit_factor')}")
    print(f"notes={r.get('notes')}")
    print(f"canonical pool_cards diag={diag_out}")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['discover', 'final'], required=True)
    a = ap.parse_args()
    (phase_discover if a.phase == 'discover' else phase_final)()
