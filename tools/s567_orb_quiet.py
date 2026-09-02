# -*- coding: utf-8 -*-
"""
s567_orb_quiet.py — ORB ساعت اول در روزهای آرام (M5/M15) — مسیر C

پیش‌ثبت: results/S567_PREREG_ORB_QUIET_XAUUSD.md (کامیت d555d253 — قبل از هر تست).

رویداد: OR = high/low کندل‌های 0..K−1 روز (K: M5→12, M15→4 = ۶۰ دقیقه).
سیگنال = اولین j در [K, K+W) با close[j] > OR_high (W: M5→24, M15→8).
ورود LONG در open کندل j+1. بازوها: {BARE,V78} × hold {1h,2h}.
هندسه: V-TIME q98 نیمهٔ اول. سدها: n_fh<30 ⇒ NO-VERDICT · lift_fh<+4pp ⇒
STOPPED_DEAD. null: لانگ غیرشرطی (s561). n_trials=48. SEED=20260829.

اجرا:
  python3 tools/s567_orb_quiet.py lock  M5
  python3 tools/s567_orb_quiet.py stop  M5
  python3 tools/s567_orb_quiet.py judge M5
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
from tools.s560_adjudicate import _pip                     # noqa: E402
from tools.s561_h8revival import null_for                  # noqa: E402
from tools.s434_fast_data import load_fast, as_dataframe   # noqa: E402

N_TRIALS = 48
N_PERM = 500
SEED = 20260829
ALLOWED_TFS = ('M5', 'M15')
K_OR = {'M5': 12, 'M15': 4}       # ۶۰ دقیقه
W_WIN = {'M5': 24, 'M15': 8}      # تا پایان ساعت سوم
HOLDS = {'M5': (12, 24), 'M15': (4, 8)}   # ۱ و ۲ ساعت
QV = 78                            # منجمد (S404/S562 پیشینه)
VOL_N, ROLL_D, MIN_S = 14, 250, 60
OUT = os.path.join(ROOT, 'results', '_s567_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
LIFT_STOP = 4.0


def _check_tf(tf):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S567 (فقط M5/M15)')


def _split_bar(t):
    import calendar
    return int(np.searchsorted(t, calendar.timegm((2018, 10, 20, 0, 0, 0))))


def day_structs(d, tf):
    t = d['time']
    n = len(t)
    brk = day_breaks(t, tf)
    starts = np.concatenate([[0], brk + 1])
    ends = np.concatenate([brk, [n - 1]])
    return starts, ends


def quiet_day_flags(d, tf):
    """روز k آرام است اگر vol_ref[k−1] ≤ چندک QV تاریخچهٔ علّی (منطق S562)."""
    h, l = d['high'], d['low']
    starts, ends = day_structs(d, tf)
    n_days = len(starts)
    rng_day = np.array([h[starts[k]:ends[k] + 1].max()
                        - l[starts[k]:ends[k] + 1].min()
                        for k in range(n_days)])
    vol_ref = np.full(n_days, np.nan)
    csum = np.concatenate([[0.0], np.cumsum(rng_day)])
    for k in range(VOL_N - 1, n_days):
        vol_ref[k] = (csum[k + 1] - csum[k + 1 - VOL_N]) / VOL_N
    quiet = np.zeros(n_days, bool)
    known = np.zeros(n_days, bool)     # تاریخچهٔ کافی؟
    for k in range(1, n_days):
        v = vol_ref[k - 1]             # روزِ قبل، کامل‌شده — علّی
        if np.isnan(v):
            continue
        lo = max(VOL_N - 1, k - 1 - ROLL_D)
        hist = vol_ref[lo:k - 1]
        hist = hist[~np.isnan(hist)]
        if len(hist) < MIN_S:
            continue
        known[k] = True
        if v <= np.percentile(hist, QV):
            quiet[k] = True
    return quiet, known


def orb_mask(d, tf, use_v):
    """سیگنال ORB: اولین close بالای OR_high در پنجره؛ فقط روزهای با کندل کافی."""
    c, h = d['close'], d['high']
    n = len(c)
    starts, ends = day_structs(d, tf)
    n_days = len(starts)
    K, W = K_OR[tf], W_WIN[tf]
    quiet, known = quiet_day_flags(d, tf)
    out = np.zeros(n, bool)
    n_days_eligible = n_days_event = 0
    for k in range(n_days):
        s0, e0 = starts[k], ends[k]
        if e0 - s0 + 1 < K + 2:        # روز خیلی کوتاه
            continue
        if use_v and not (known[k] and quiet[k]):
            continue
        n_days_eligible += 1
        or_high = h[s0:s0 + K].max()
        j_hi = min(s0 + K + W, e0)     # سیگنال باید داخل روز بماند (ورود j+1)
        seg = c[s0 + K:j_hi]
        hits = np.flatnonzero(seg > or_high)
        if hits.size:
            j = s0 + K + int(hits[0])
            if j + 1 < n:
                out[j] = True
                n_days_event += 1
    return out, n_days_eligible, n_days_event


def geometry_vtime(d, mask, mh, split_bar):
    pip = _pip('XAUUSD')
    h, l, o = d['high'], d['low'], d['open']
    n = len(o)
    idx = np.flatnonzero(mask)
    idx = idx[idx + 1 + mh < min(split_bar, n)]
    mfes, maes = [], []
    for i in idx:
        e = i + 1
        j1 = min(e + mh, n)
        entry = o[e]
        mfes.append((h[e:j1].max() - entry) / pip)
        maes.append((entry - l[e:j1].min()) / pip)
    if not mfes:
        return None
    allm = np.concatenate([np.array(mfes), np.array(maes)])
    return round(float(np.percentile(allm, 98)), 1)


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
    d = load_fast('XAUUSD', tf)
    df = as_dataframe(d)
    split_bar = _split_bar(d['time'])
    scored = {}
    dens = {}
    for filt, use_v in (('BARE', False), ('V78', True)):
        mm, n_elig, n_ev = orb_mask(d, tf, use_v)
        dens[filt] = dict(days_eligible=n_elig, days_event=n_ev,
                          event_rate=round(100.0 * n_ev / max(n_elig, 1), 1))
        for mh in HOLDS[tf]:
            g = geometry_vtime(d, mm, mh, split_bar)
            if g is None:
                continue
            zl = np.zeros(len(df), bool)
            tr = se.simulate_trades(df, mm, zl, g, g, 'XAUUSD',
                                    max_hold=mh, allow_overlap=False)
            t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
            name = f'{filt}-h{mh}'
            scored[name] = dict(filt=filt, mh=mh, sl=g, tp=g,
                                n_signals=int(mm.sum()),
                                t_first_half=t_fh, n_first_half=n_fh,
                                wr_first_half=wr_fh, dd_first_half=dd_fh)
            print(f"  {name}: n_sig={int(mm.sum())} sl=tp={g} → t={t_fh} "
                  f"n_fh={n_fh} WR={wr_fh} DD={dd_fh}%")
    print(f"densities: {dens}")
    cands = [k for k in scored if scored[k]['t_first_half'] is not None]
    pick = max(cands, key=lambda k: round(scored[k]['t_first_half'], 2),
               default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(arms=scored, picked=pick, densities=dens,
                    split_bar=int(split_bar), split_utc=SPLIT_UTC,
                    src=d['src'])
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def stop_check(tf: str):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    if not L.get('picked'):
        print(f"{tf}: NO-VERDICT (n_fh<30)")
        L['stop_check'] = dict(no_verdict=True)
        lock[tf] = L
        json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
        return
    a = L['arms'][L['picked']]
    d = load_fast('XAUUSD', tf)
    df = as_dataframe(d)
    split_bar = _split_bar(d['time'])
    mm, _, _ = orb_mask(d, tf, a['filt'] == 'V78')
    assert int(mm.sum()) == a['n_signals'], 'BUG-DATASETDRIFT'
    df_fh = df.iloc[:split_bar].reset_index(drop=True)
    nl = null_for(df_fh, mm[:split_bar], a['sl'], a['tp'], a['mh'],
                  n_perm=200, seed=SEED)
    lift = (a['wr_first_half'] or 0) - (nl['long']['uncond_wr'] or 50.0)
    dead = lift < LIFT_STOP
    L['stop_check'] = dict(lift_fh_pp=round(lift, 2),
                           null_uncond_wr_fh=nl['long']['uncond_wr'],
                           threshold=LIFT_STOP, stopped_dead=bool(dead))
    lock[tf] = L
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"{tf}: lift_fh={lift:+.2f}pp vs stop {LIFT_STOP}pp → "
          f"{'STOPPED_DEAD' if dead else 'PROCEED to judge'}")


def phase_judge(tf: str):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    sc = L.get('stop_check') or {}
    if sc.get('no_verdict') or sc.get('stopped_dead'):
        raise SystemExit(f'{tf} متوقف — داوری ممنوع (پیش‌ثبت §2)')
    if 'stopped_dead' not in sc:
        raise SystemExit(f'{tf}: اول فاز stop')
    a = L['arms'][L['picked']]
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    d = load_fast('XAUUSD', tf)
    df = as_dataframe(d)
    split_bar = _split_bar(d['time'])
    mm, _, _ = orb_mask(d, tf, a['filt'] == 'V78')
    assert int(mm.sum()) == a['n_signals'], 'BUG-DATASETDRIFT'
    zl = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mm, zl, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n_tr = len(tr)
    print(f"src={d['src']} arm={L['picked']} sl={sl} tp={tp} mh={mh} n={n_tr}")
    if n_tr < 30:
        res_out = dict(tf=tf, error=f'n<30 (n={n_tr})', invalid=True)
    else:
        null = null_for(df, mm, sl, tp, mh, n_perm=N_PERM, seed=SEED)
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
            'tf': tf, 'arm': L['picked'], 'direction': 'LONG',
            'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh,
                             rr=round(tp / sl, 3), rule='V-TIME q98 first-half'),
            'n_signals': int(mm.sum()),
            'verdict': res.get('verdict'),
            'rqs2_score': res.get('rqs2_score'),
            'gates': {k: gt.get(k) for k in sorted(gt)},
            'failed_gates': sorted(k for k, v in gt.items() if v is False),
            'unknown_gates': sorted(k for k, v in gt.items() if v is None),
            'null': null['long'], 'n_trials': N_TRIALS,
            'n_required_for_h3': (None if n_need == float('inf')
                                  else round(float(n_need), 1)),
            'split_bar': int(split_bar), 'split_utc': SPLIT_UTC, 'src': d['src'],
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
                       'n_required_for_h3')}, ensure_ascii=False))
    mm2 = res_out.get('metrics') or {}
    print(f"WR={mm2.get('win_rate')} lift={mm2.get('skill_lift_pp')} "
          f"z={mm2.get('skill_z')} dd={mm2.get('max_dd_pct')} "
          f"mcl={mm2.get('max_consec_losses')}/{mm2.get('mcl_allowed')} "
          f"rec={mm2.get('recovery_factor')}")
    print(f"saved → {path}")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    {'lock': phase_lock, 'stop': stop_check, 'judge': phase_judge}[phase](tf)
