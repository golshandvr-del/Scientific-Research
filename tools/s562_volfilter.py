# -*- coding: utf-8 -*-
"""
s562_volfilter.py — فیلتر نوسان علّی روی GapOpen (M15/H1 فقط) — مسیر C

پیش‌ثبت: results/S562_PREREG_GAPOPEN_VOLFILTER_XAUUSD.md (کامیت ec52aa25 —
قبل از هر تست). سیگنال و هندسه هر دو منجمد از S560:
  M15: cfg(q70,sw,hold1) · V-TIME SL=TP=50.9 mh=1
  H1 : cfg(q80,sw,hold2) · V-TIME SL=TP=101.4 mh=2

بازوی جدید فقط فیلتر V (الگوی S404): ردِ سیگنال اگر
  vol_ref(روزِ قبل از ورود) > چندک رولینگ 250-روزهٔ علّی (min 60)
vol_ref = میانگین دامنهٔ واقعی روزانهٔ 14 روزِ کامل‌شدهٔ قبل از ورود.
qv ∈ {70, 78, 85} → 6 بازو → n_trials انباشتهٔ خانواده = 415+6 = **421**.

گاردها: BUG-PERMK · BUG-NULLUNCOND · BUG-SCOREKEY · BUG-PIPGUESS ·
BUG-DATASETDRIFT · BUG-GEOMDRIFT (هندسه از قفل S560 خوانده می‌شود، نه محاسبهٔ
مجدد) · BUG-BRKTHRESH · قید ۲. M30 ممنوع (قلمرو S404) · M1/M5 ممنوع (ACCEPT).

اجرا:
  python3 tools/s562_volfilter.py lock  M15
  python3 tools/s562_volfilter.py judge M15
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2 import compute_rqs2, n_required_for_h3    # noqa: E402
from tools.s560_gapopen_explore import day_breaks, SPLIT_UTC  # noqa: E402
from tools.s560_adjudicate import build                    # noqa: E402
from tools.s561_h8revival import null_for as _null561      # noqa: E402

N_TRIALS = 421         # پیش‌ثبت S562 §۴ — انباشتهٔ صادقانهٔ خانواده
N_PERM = 500
SEED = 20260815
QVS = (70, 78, 85)
ALLOWED_TFS = ('M15', 'H1')     # M30=قلمرو S404 · M1/M5=ACCEPT قطعی
OUT = os.path.join(ROOT, 'results', '_s562_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
S560_LOCK = os.path.join(ROOT, 'results', '_s560_arms', 'locked_config.json')

VOL_N = 14        # روزهای میانگین دامنه
ROLL_D = 250      # پنجرهٔ رولینگ چندک
MIN_S = 60        # حداقل نمونه


def _check_tf(tf: str):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S562 (فقط M15/H1)')


def frozen_geometry(tf: str):
    """هندسهٔ V-TIME عیناً از قفل S560 — BUG-GEOMDRIFT."""
    s560 = json.load(open(S560_LOCK))
    g = s560[tf]['variants'][s560[tf]['picked']]
    assert s560[tf]['picked'] == 'V-TIME'
    return float(g['sl']), float(g['tp']), int(g['mh'])


def vol_filter_mask(d, tf, mask, qv):
    """فیلتر V علّی: برای هر سیگنال (روی آخرین کندل روز j)، vol_ref = میانگین
    دامنهٔ روزانهٔ 14 روز منتهی به j (همگی قبل از ورودِ روز j+1 کامل شده‌اند)؛
    آستانه = چندک qv از vol_refهای روزهای < j در پنجرهٔ 250 روز (min 60)."""
    t, h, l = d['time'], d['high'], d['low']
    n = len(t)
    brk = day_breaks(t, tf)
    starts = np.concatenate([[0], brk + 1])
    ends = np.concatenate([brk, [n - 1]])          # روز k: [starts[k], ends[k]]
    n_days = len(starts)
    rng_day = np.array([h[starts[k]:ends[k] + 1].max()
                        - l[starts[k]:ends[k] + 1].min()
                        for k in range(n_days)])
    # vol_ref[k] = میانگین 14 روز منتهی به k (شامل k) — در ورودِ روز k+1 علّی است
    vol_ref = np.full(n_days, np.nan)
    csum = np.concatenate([[0.0], np.cumsum(rng_day)])
    for k in range(VOL_N - 1, n_days):
        vol_ref[k] = (csum[k + 1] - csum[k + 1 - VOL_N]) / VOL_N
    # نگاشت اندیس آخرین کندل روز → شمارهٔ روز
    day_of_end = {int(ends[k]): k for k in range(n_days)}
    out = np.zeros(n, bool)
    sig_idx = np.flatnonzero(mask)
    n_hist_used = 0
    for i in sig_idx:
        k = day_of_end.get(int(i))
        if k is None or np.isnan(vol_ref[k]):
            continue                                  # بدون تاریخچه → رد محافظه‌کارانه
        lo = max(VOL_N - 1, k - ROLL_D)
        hist = vol_ref[lo:k]                          # فقط روزهای < k (اکیداً علّی)
        hist = hist[~np.isnan(hist)]
        if len(hist) < MIN_S:
            continue
        thr = np.percentile(hist, qv)
        if vol_ref[k] <= thr:                         # روز آرام → عبور
            out[i] = True
            n_hist_used += 1
    return out


def first_half_stats(tr, split_bar):
    m = tr[tr['exit_bar'] < split_bar]
    p = m['pnl_pip'].values.astype(float)
    if len(p) < 30:
        return None, len(p), None, None
    se_ = p.std(ddof=1) / np.sqrt(len(p))
    t = float(p.mean() / se_) if se_ > 0 else 0.0
    wr = round(float((p > 0).mean() * 100), 2)
    eq = 10000.0 + np.cumsum(p) * 10.0
    peak = np.maximum.accumulate(eq)
    dd = round(float(((peak - eq) / peak).max() * 100), 2)
    return t, len(p), wr, dd


def phase_lock(tf: str):
    _check_tf(tf)
    d, df, mask, split_bar, cfg = build(tf)
    s560 = json.load(open(S560_LOCK))
    assert s560[tf]['cfg'] == cfg, 'BUG-GEOMDRIFT: cfg ناهمسان با قفل S560'
    assert s560[tf]['n_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT'
    sl, tp, mh = frozen_geometry(tf)
    print(f"src={d['src']} base_signals={int(mask.sum())} geom sl=tp={sl} mh={mh}")
    scored = {}
    for qv in QVS:
        fm = vol_filter_mask(d, tf, mask, qv)
        z = np.zeros(len(df), bool)
        tr = se.simulate_trades(df, fm, z, sl, tp, 'XAUUSD',
                                max_hold=mh, allow_overlap=False)
        t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
        scored[f'V-q{qv}'] = dict(qv=qv, sl=sl, tp=tp, mh=mh,
                                  n_filtered=int(fm.sum()),
                                  t_first_half=t_fh, n_first_half=n_fh,
                                  wr_first_half=wr_fh, dd_first_half=dd_fh)
        print(f"  V-q{qv}: n_filt={int(fm.sum())}/{int(mask.sum())} "
              f"→ t={t_fh} n_fh={n_fh} WR={wr_fh} DD={dd_fh}%")
    cands = [k for k in scored if scored[k]['t_first_half'] is not None]
    pick = max(cands, key=lambda k: (round(scored[k]['t_first_half'], 2),
                                     -(scored[k]['dd_first_half'] or 99)),
               default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(cfg=cfg, arms=scored, picked=pick,
                    geometry=dict(sl=sl, tp=tp, mh=mh, src='S560 V-TIME frozen'),
                    split_bar=int(split_bar), split_utc=SPLIT_UTC,
                    src=d['src'], n_base_signals=int(mask.sum()))
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def phase_judge(tf: str):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    if tf not in lock or not lock[tf].get('picked'):
        raise SystemExit(f'{tf} قفل نشده — اول فاز lock')
    L = lock[tf]
    a = L['arms'][L['picked']]
    qv = int(a['qv'])
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    d, df, mask, split_bar, cfg = build(tf)
    assert L['n_base_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT'
    fm = vol_filter_mask(d, tf, mask, qv)
    assert int(fm.sum()) == a['n_filtered'], 'BUG-DATASETDRIFT: فیلتر ناهمسان با قفل'

    z0 = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, fm, z0, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n_tr = len(tr)
    print(f"src={d['src']} arm={L['picked']} sl={sl} tp={tp} mh={mh} n={n_tr}")
    if n_tr < 30:
        res_out = dict(tf=tf, error=f'n<30 (n={n_tr})', invalid=True)
    else:
        # null: استخر بدون فیلتر (فیلتر جزو مهارت — پیش‌ثبت §5 / الگوی S404)
        null = _null561(df, fm, sl, tp, mh, n_perm=N_PERM, seed=SEED)
        res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                           bar_time=df['time'].values,
                           close=df['close'].values,
                           null=null, n_trials=N_TRIALS, split_bar=split_bar,
                           initial_capital=10000.0, allow_overlap=False)
        gt = res.get('gates') or {}
        m = res.get('metrics') or {}
        lift = m.get('skill_lift_pp')
        p0 = (null['long']['uncond_wr'] or 50.0) / 100.0
        n_need = n_required_for_h3(lift, p0) if lift else float('inf')
        res_out = {
            'tf': tf, 'arm': L['picked'], 'qv': qv,
            'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                             rr=round(tp / sl, 3), rule='S560 V-TIME frozen'),
            'cfg': cfg, 'n_signals': int(fm.sum()),
            'n_base_signals': int(mask.sum()),
            'verdict': res.get('verdict'),
            'rqs2_score': res.get('rqs2_score'),
            'gates': {k: gt.get(k) for k in sorted(gt)},
            'failed_gates': sorted(k for k, v in gt.items() if v is False),
            'unknown_gates': sorted(k for k, v in gt.items() if v is None),
            'null': null['long'], 'n_trials': N_TRIALS,
            'n_required_for_h3': (None if n_need == float('inf')
                                  else round(float(n_need), 1)),
            'split_bar': split_bar, 'split_utc': SPLIT_UTC, 'src': d['src'],
            'metrics': {k: m.get(k) for k in (
                'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
                'profit_factor', 'net_profit', 'max_dd_pct',
                'max_consec_losses', 'mcl_allowed', 'recovery_factor',
                'skill_lift_pp', 'skill_z', 'null_ref_wr',
                'breakeven_wr_cost', 'rr', 'top_win_share', 'z_obs',
                'z_luck_bound', 'z_margin', 'skill_p_perm', 'p_emp',
                'p_adj_bonferroni', 'perm_k', 'perm_max')},
            'notes': [str(x) for x in (res.get('notes') or [])],
        }
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'judge_{tf}.json')
    json.dump(res_out, open(path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: res_out.get(k) for k in
                      ('verdict', 'rqs2_score', 'failed_gates',
                       'unknown_gates', 'n_required_for_h3')},
                     ensure_ascii=False))
    mm = res_out.get('metrics') or {}
    print(f"WR={mm.get('win_rate')} lift={mm.get('skill_lift_pp')} "
          f"z={mm.get('skill_z')} dd={mm.get('max_dd_pct')} "
          f"mcl={mm.get('max_consec_losses')}/{mm.get('mcl_allowed')} "
          f"rec={mm.get('recovery_factor')} "
          f"perm_k={(res_out.get('null') or {}).get('perm_k')}")
    print(f"saved → {path}")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    (phase_lock if phase == 'lock' else phase_judge)(tf)
