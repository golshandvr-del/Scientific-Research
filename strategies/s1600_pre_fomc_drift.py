# -*- coding: utf-8 -*-
"""
S1600 — رانشِ پیش‌ازاعلانِ FOMC در طلا (Lucca–Moench 2015) — XAUUSD، ۷ کارت
===========================================================================
پیش‌ثبت: results/S1600_PREREG_PRE_FOMC_DRIFT.md (ebfd66e8 — قبل از هر محاسبه).
تقویم منجمد: results/_s1600/fomc_dates.json (۱۲۷ روزِ تصمیم، برنامه‌ریزی‌شده).

  · سیگنال: اولین کندل با close >= T_ann − 24h؛ ورود در close، LONG.
  · خروج: زمانی در open اولین کندل >= T_ann (پیش از خبر)؛ SL/TP فعال.
  · هندسه (S547): SL=1.5×ATR100 (میانه)، TP=1.5×SL.
  · نول per-card: uncond (پنجره‌ی ۲۴h از هر کندل، stride 1/3/7) + perm K=2000
    (۱۲۷ پنجره‌ی ۲۴h تصادفی، همان خروجِ زمانی/قید).
  · داوری rqs2 v2.6، split_bar=70%، n_trials=7 (+تنش 50)، SEED=20260826.
  · P-D: پنجره‌ی پس‌اعلان (T_ann → +24h) فقط لیفت.
داده: data/mt5_full (assert). اجرا: python3 strategies/s1600_pre_fomc_drift.py
"""
from __future__ import annotations

import json
import os
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, '.')
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from engine import rqs2 as R
from tools import s434_fast_data as fd

import warnings
warnings.filterwarnings('ignore')

SESSION = 'S1600'
PREREG = 'results/S1600_PREREG_PRE_FOMC_DRIFT.md'
CAL = 'results/_s1600/fomc_dates.json'
OUT = 'results/_s1600'
ASSET = 'XAUUSD'
CARDS = ['H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1']
WINDOW_H = 24
ATR_P, SL_K, RR = 100, 1.5, 1.5          # S547 (به ارث)
K_PERM = 2000
SEED = 20260826
N_TRIALS, N_TRIALS_STRESS = 7, 50
SPLIT_FRAC = 0.70
PIP = 0.1
COST_PIP = 3.3
NY = ZoneInfo('America/New_York')


def ann_times_utc():
    d = json.load(open(CAL))
    ts = [pd.Timestamp(f'{x} 14:00', tz=NY).tz_convert('UTC').tz_localize(None)
          for x in d['dates']]
    return np.array(sorted(ts), dtype='datetime64[ns]'), d['n']


def atr_wilder(h, l, c, p=ATR_P):
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def load(tf):
    d = fd.load_fast(ASSET, tf)
    src = d.get('src', '')
    assert 'mt5_full' in str(src), f'BUG-DATASET: {src}'
    t = np.asarray(d['time'], dtype=np.int64)                    # epoch s
    o, h, l, c = (np.asarray(d[k], float) for k in ('open', 'high', 'low', 'close'))
    dt = (t * 1_000_000_000).astype('datetime64[ns]')
    span = (dt[-1] - dt[0]) / np.timedelta64(365, 'D')
    assert span > 14.0, f'BUG-DATASETDRIFT span={span:.2f}'
    return dict(tf=tf, t=t, dt=dt, o=o, h=h, l=l, c=c, atr=atr_wilder(h, l, c),
                src=src, span=float(span))


def sim_windows(m, starts, sl_abs, tp_abs, win_ns):
    """معامله‌ی LONG از close[e] تا open اولین کندل >= dt[e]+win (یا SL/TP).
    starts: اندیس‌های کندلِ ورود (مرتب). قیدِ عدمِ هم‌پوشانی."""
    dt, o, h, l, c = m['dt'], m['o'], m['h'], m['l'], m['c']
    n = len(c)
    rows, busy = [], -1
    for e in starts:
        e = int(e)
        if e <= busy or e + 1 >= n:
            continue
        entry = c[e]
        sl_lvl, tp_lvl = entry - sl_abs, entry + tp_abs
        t_end = dt[e] + win_ns
        j_end = int(np.searchsorted(dt, t_end, 'left'))          # اولین کندل >= t_end
        out = None
        for j in range(e + 1, min(j_end, n)):
            if l[j] <= sl_lvl:
                out = ('loss', j, -sl_abs / PIP); break
            if h[j] >= tp_lvl:
                out = ('win', j, tp_abs / PIP); break
        if out is None:
            if j_end >= n:
                break                                            # معامله‌ی بازِ پایانِ داده
            pnl = (o[j_end] - entry) / PIP
            out = ('win' if pnl > 0 else 'loss', j_end, pnl)
        rows.append(dict(entry_bar=e, exit_bar=out[1], outcome=out[0],
                         pnl_pip=out[2], sl_pip=sl_abs / PIP, tp_pip=tp_abs / PIP,
                         direction='long'))
        busy = out[1]
    return pd.DataFrame(rows)


def signal_starts(m, anns, offset_h):
    """اولین کندل با close >= T_ann + offset_h (offset −24 → پیش‌اعلان؛ 0 → پس‌اعلان)."""
    dt = m['dt']
    bar_ns = np.median(np.diff(dt[:1000]))
    close_t = dt + bar_ns                                         # زمانِ بستنِ کندل
    targets = anns + np.timedelta64(offset_h, 'h')
    idx = np.searchsorted(close_t, targets, 'left')
    idx = idx[(idx > ATR_P) & (idx < len(dt) - 1)]
    return np.unique(idx)


def wr(tr):
    return 100.0 * float((tr['outcome'] == 'win').mean()) if len(tr) else float('nan')


def run_card(tf, anns):
    m = load(tf)
    sl_abs = float(np.nanmedian(m['atr'])) * SL_K
    tp_abs = sl_abs * RR
    win_ns = np.timedelta64(WINDOW_H, 'h')
    print(f"--- {tf}: src={m['src']} bars={len(m['c'])} span={m['span']:.2f}y "
          f"SL={sl_abs/PIP:.1f}pip TP={tp_abs/PIP:.1f}pip", flush=True)

    starts = signal_starts(m, anns, -WINDOW_H)
    tr = sim_windows(m, starts, sl_abs, tp_abs, win_ns)
    n_sig = len(starts)
    if len(tr) < 30:
        return dict(card=tf, n_signals=n_sig, n_trades=len(tr), verdict='TOO_FEW_TRADES')

    # ضدِ آزمون P-D: پس‌اعلان
    post = sim_windows(m, signal_starts(m, anns, 0), sl_abs, tp_abs, win_ns)

    # نول: uncond (هر کندل با stride) + perm (n_sig پنجره‌ی تصادفی)
    rng = np.random.default_rng(SEED)
    lo, hi = ATR_P + 1, len(m['c']) - 2
    unc = max(wr(sim_windows(m, np.arange(lo, hi, s), sl_abs, tp_abs, win_ns))
              for s in (1, 3, 7))
    wrs = []
    for _ in range(K_PERM):
        pos = np.sort(rng.choice(np.arange(lo, hi), size=n_sig, replace=False))
        t = sim_windows(m, pos, sl_abs, tp_abs, win_ns)
        if len(t) >= 30:
            wrs.append(wr(t))
    a = np.asarray(wrs)
    null = {'long': dict(uncond_wr=unc, perm_mean=float(a.mean()),
                         perm_sd=float(a.std(ddof=1)), perm_max=float(a.max()),
                         perm_k=int(len(a))),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    ref = max(unc, float(a.mean()))
    common = dict(sl_pip=sl_abs / PIP, tp_pip=tp_abs / PIP, bar_time=m['t'],
                  close=m['c'], null=null, split_bar=int(SPLIT_FRAC * len(m['c'])))
    res = R.compute_rqs2(tr, ASSET, n_trials=N_TRIALS, **common)
    res_st = R.compute_rqs2(tr, ASSET, n_trials=N_TRIALS_STRESS, **common)
    print(R.format_rqs2(f'{SESSION}-{tf} PRE  n_trials={N_TRIALS}', res), flush=True)
    print(R.format_rqs2(f'{SESSION}-{tf} PRE  STRESS({N_TRIALS_STRESS})', res_st), flush=True)
    print(f"   null: uncond={unc:.2f} perm_mean={a.mean():.2f} sd={a.std(ddof=1):.2f} "
          f"max={a.max():.2f} | lift_vs_ref={wr(tr)-ref:+.2f}pp | "
          f"P-D post: n={len(post)} WR={wr(post):.2f} lift={wr(post)-ref:+.2f}pp | "
          f"exp_pre={tr['pnl_pip'].mean():+.2f} exp_post={post['pnl_pip'].mean():+.2f} pip",
          flush=True)
    slim = lambda r: dict(verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
                          gates=r.get('gates'), notes=r.get('notes'),
                          metrics={k: v for k, v in (r.get('metrics') or {}).items()
                                   if isinstance(v, (int, float, str, bool, type(None)))})
    return dict(card=tf, src=m['src'], span_years=round(m['span'], 2), n_signals=n_sig,
                n_trades=len(tr), wr=round(wr(tr), 2), lift_vs_ref=round(wr(tr) - ref, 2),
                exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                sl_pip=round(sl_abs / PIP, 2), tp_pip=round(tp_abs / PIP, 2),
                null=null, post_window=dict(n=len(post), wr=round(wr(post), 2),
                                            lift_vs_ref=round(wr(post) - ref, 2),
                                            exp_pip=round(float(post['pnl_pip'].mean()), 2)),
                official=slim(res), stress=slim(res_st),
                verdict=res.get('verdict'), rqs2_score=res.get('rqs2_score'))


def main():
    os.makedirs(OUT, exist_ok=True)
    anns, n_cal = ann_times_utc()
    print(f'== {SESSION} Pre-FOMC drift · {n_cal} announcements · window={WINDOW_H}h · '
          f'seed={SEED} n_trials={N_TRIALS} K={K_PERM} ==', flush=True)
    out = {}
    for tf in CARDS:
        try:
            out[tf] = run_card(tf, anns)
        except Exception as e:
            out[tf] = dict(card=tf, verdict='ERROR', error=str(e))
            print(f'{tf}: ERROR {e}', flush=True)
        json.dump(out, open(f'{OUT}/verdict.json', 'w'), ensure_ascii=False,
                  indent=1, default=str)
    lifts = {tf: r.get('lift_vs_ref') for tf, r in out.items() if r.get('lift_vs_ref') is not None}
    acc = [tf for tf, r in out.items() if r.get('verdict') == 'ACCEPT']
    pa = any(r.get('verdict') == 'ACCEPT' and r.get('lift_vs_ref', 0) > 8 for r in out.values()) \
        and sum(v > 0 for v in lifts.values()) >= 5
    pb = all(-4 <= v <= 4 for v in lifts.values())
    pc = sum(v < -4 for v in lifts.values()) >= 4
    best = max(out.values(), key=lambda r: (r.get('rqs2_score') or 0))
    print(f'\n[P-A اثر] {pa} | [P-B بی‌اثر] {pb} | [P-C معکوس] {pc} | lifts={lifts}')
    print(f'[بهترین کارت] {best["card"]} {best.get("verdict")} {best.get("rqs2_score")} | ACCEPTs={acc}',
          flush=True)
    out['_summary'] = dict(P_A=bool(pa), P_B=bool(pb), P_C=bool(pc), lifts=lifts,
                           best_card=best['card'], best_verdict=best.get('verdict'),
                           best_score=best.get('rqs2_score'), accepts=acc)
    json.dump(out, open(f'{OUT}/verdict.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print('FINISHED', flush=True)


if __name__ == '__main__':
    main()
