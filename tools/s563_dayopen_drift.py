# -*- coding: utf-8 -*-
"""
s563_dayopen_drift.py — تداوم ساعت اول روز با دروازهٔ Drift — مسیر C

پیش‌ثبت: results/S563_PREREG_DAYOPEN_DRIFT_XAUUSD.md (کامیت a43ec405 —
قبل از هر تست). رویداد جدید: ورودِ بی‌قیدِ گپ در open هر روز معاملاتی،
مشروط به دروازه‌های پیش‌ثبت‌شده:
  NAKED  — هیچ فیلتر
  D      — drift: close(روز k-1) > close(روز k-91)   [تعریف S950، علّی]
  D+V78  — drift + فیلتر نوسان S562 با qv=78
  D+V85  — drift + فیلتر نوسان S562 با qv=85
× hold ∈ {60min, 120min} بر حسب کندل هر TF → ۸ بازو/TF · n_trials=40.

هندسه: V-TIME؛ SL=TP=q98(|MFE|∪|MAE|) نیمهٔ اولِ بازوی قفل‌شده؛ خروج زمانی.

گاردها: BUG-PERMK · BUG-NULLUNCOND · BUG-SCOREKEY · BUG-PIPGUESS ·
BUG-DATASETDRIFT · BUG-GEOMDRIFT · BUG-BRKTHRESH · قید ۲.

اجرا:
  python3 tools/s563_dayopen_drift.py lock  M5
  python3 tools/s563_dayopen_drift.py judge M5
"""
from __future__ import annotations

import calendar
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2 import compute_rqs2, n_required_for_h3    # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402
from tools.s560_gapopen_explore import day_breaks, SPLIT_UTC  # noqa: E402

N_TRIALS = 40
N_PERM = 500
SEED = 20260816
DRIFT_D = 90          # روز معاملاتی
VOL_N, ROLL_D, MIN_S = 14, 250, 60
HOLDS_MIN = (60, 120)
TF_MIN = {'M1': 1, 'M5': 5, 'M15': 15, 'M30': 30, 'H1': 60}
OUT = os.path.join(ROOT, 'results', '_s563_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')


def _pip(asset='XAUUSD'):
    spec = getattr(se, 'ASSETS', {}).get(asset, {})
    p = spec.get('pip') or spec.get('pip_size')
    if p is None:
        raise RuntimeError('pip not readable from engine')  # BUG-PIPGUESS
    return float(p)


def day_structs(d, tf):
    """روزها: starts/ends/کلوز روز/دامنهٔ روز/vol_ref/drift — همگی علّی."""
    t, h, l, c = d['time'], d['high'], d['low'], d['close']
    n = len(t)
    brk = day_breaks(t, tf)
    starts = np.concatenate([[0], brk + 1])
    ends = np.concatenate([brk, [n - 1]])
    n_days = len(starts)
    day_close = c[ends]
    rng_day = np.array([h[starts[k]:ends[k] + 1].max()
                        - l[starts[k]:ends[k] + 1].min()
                        for k in range(n_days)])
    vol_ref = np.full(n_days, np.nan)
    csum = np.concatenate([[0.0], np.cumsum(rng_day)])
    for k in range(VOL_N - 1, n_days):
        vol_ref[k] = (csum[k + 1] - csum[k + 1 - VOL_N]) / VOL_N
    # drift برای ورودِ روز k: کلوز روز k-1 > کلوز روز k-1-90
    drift = np.zeros(n_days, bool)
    for k in range(DRIFT_D + 1, n_days):
        drift[k] = day_close[k - 1] > day_close[k - 1 - DRIFT_D]
    return dict(starts=starts, ends=ends, n_days=n_days,
                vol_ref=vol_ref, drift=drift)


def vol_pass(ds, k, qv):
    """فیلتر V برای ورود روز k (عین منطق S562): vol_ref روز k-1 ≤ چندک علّی."""
    vr = ds['vol_ref']
    if k < 1 or np.isnan(vr[k - 1]):
        return False
    lo = max(VOL_N - 1, k - 1 - ROLL_D)
    hist = vr[lo:k - 1]
    hist = hist[~np.isnan(hist)]
    if len(hist) < MIN_S:
        return False
    return vr[k - 1] <= np.percentile(hist, qv)


def build_mask(d, tf, ds, filt):
    """ماسک روی آخرین کندل روز k-1 (ورود موتور در open روز k)."""
    n = len(d['time'])
    mask = np.zeros(n, bool)
    for k in range(1, ds['n_days']):
        if filt in ('D', 'DV78', 'DV85') and not ds['drift'][k]:
            continue
        if filt == 'DV78' and not vol_pass(ds, k, 78):
            continue
        if filt == 'DV85' and not vol_pass(ds, k, 85):
            continue
        mask[ds['ends'][k - 1]] = True
    return mask


def geom_vtime(d, mask, hold, split_bar):
    """SL=TP=q98(|MFE|∪|MAE|) نیمهٔ اول — عین قاعدهٔ S560."""
    pip = _pip()
    h, l, o = d['high'], d['low'], d['open']
    n = len(o)
    idx = np.flatnonzero(mask)
    idx = idx[idx + 1 + hold < min(split_bar, n)]
    vals = []
    for i in idx:
        e = i + 1
        j1 = min(e + hold, n)
        entry = o[e]
        vals.append((h[e:j1].max() - entry) / pip)
        vals.append((entry - l[e:j1].min()) / pip)
    if not vals:
        return None
    return max(round(float(np.percentile(np.array(vals), 98)), 1), 1.0)


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


def load(tf):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    split_ts = calendar.timegm((2018, 10, 20, 0, 0, 0))
    split_bar = int(np.searchsorted(d['time'], split_ts))
    return d, df, split_bar


def phase_lock(tf: str):
    d, df, split_bar = load(tf)
    ds = day_structs(d, tf)
    print(f"src={d['src']} n_days={ds['n_days']} split_bar={split_bar}")
    scored = {}
    for filt in ('NAKED', 'D', 'DV78', 'DV85'):
        mask = build_mask(d, tf, ds, filt)
        for hm in HOLDS_MIN:
            hold = max(1, hm // TF_MIN[tf])
            w = geom_vtime(d, mask, hold, split_bar)
            if w is None:
                continue
            z = np.zeros(len(df), bool)
            tr = se.simulate_trades(df, mask, z, w, w, 'XAUUSD',
                                    max_hold=hold, allow_overlap=False)
            t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
            key = f'{filt}-h{hm}'
            scored[key] = dict(filt=filt, hold=hold, hold_min=hm, sl=w, tp=w,
                               n_signals=int(mask.sum()),
                               t_first_half=t_fh, n_first_half=n_fh,
                               wr_first_half=wr_fh, dd_first_half=dd_fh)
            print(f"  {key}: n_sig={int(mask.sum())} sl=tp={w} hold={hold} "
                  f"→ t={t_fh} n_fh={n_fh} WR={wr_fh} DD={dd_fh}%")
    cands = [k for k in scored if scored[k]['t_first_half'] is not None]
    pick = max(cands, key=lambda k: (round(scored[k]['t_first_half'], 2),
                                     -(scored[k]['dd_first_half'] or 99)),
               default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(arms=scored, picked=pick, split_bar=int(split_bar),
                    split_utc=SPLIT_UTC, src=d['src'])
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """نال اختصاصی بازو — عیناً الگوی s437/s560/s562."""
    n = len(df)
    z = np.zeros(n, bool)
    warmup = 250
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    rng = np.random.default_rng(seed)
    pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
    um = np.zeros(n, bool)
    um[pick] = True
    tu = se.simulate_trades(df, um, z, sl, tp, 'XAUUSD', max_hold=mh,
                            allow_overlap=True)
    wr_unc = 100.0 * float((tu['pnl_pip'].values > 0).mean()) if len(tu) else None
    k = int(mask.sum())
    perm = []
    for _ in range(n_perm):
        p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
        pm = np.zeros(n, bool)
        pm[p] = True
        t = se.simulate_trades(df, pm, z, sl, tp, 'XAUUSD', max_hold=mh,
                               allow_overlap=False)
        if len(t):
            perm.append(100.0 * float((t['pnl_pip'].values > 0).mean()))
    pa = np.array(perm, float)
    return {'long': dict(uncond_wr=wr_unc,
                         perm_mean=float(pa.mean()) if pa.size else None,
                         perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                         perm_max=float(pa.max()) if pa.size else None,
                         perm_k=int(pa.size)),
            'short': {}}


def phase_judge(tf: str):
    lock = json.load(open(LOCK_PATH))
    if tf not in lock or not lock[tf].get('picked'):
        raise SystemExit(f'{tf} قفل نشده — اول فاز lock')
    L = lock[tf]
    a = L['arms'][L['picked']]
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['hold'])
    d, df, split_bar = load(tf)
    ds = day_structs(d, tf)
    mask = build_mask(d, tf, ds, a['filt'])
    assert a['n_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT'

    z0 = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z0, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n_tr = len(tr)
    print(f"src={d['src']} arm={L['picked']} sl={sl} tp={tp} mh={mh} n={n_tr}")
    if n_tr < 30:
        res_out = dict(tf=tf, error=f'n<30 (n={n_tr})', invalid=True)
    else:
        null = null_for(df, mask, sl, tp, mh)
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
            'tf': tf, 'arm': L['picked'],
            'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                             rr=round(tp / sl, 3),
                             rule='SL=TP=q98(|MFE|∪|MAE|) [first half] — time exit'),
            'n_signals': int(mask.sum()),
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
          f"perm_k={(res_out.get('null') or {}).get('perm_k')}")
    print(f"saved → {path}")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    (phase_lock if phase == 'lock' else phase_judge)(tf)
