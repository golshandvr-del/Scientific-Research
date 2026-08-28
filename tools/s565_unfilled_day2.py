# -*- coding: utf-8 -*-
"""
s565_unfilled_day2.py — واریز تأخیری: LONG بامداد روز دوم پس از گپ منفی پرنشده
(M15/H1) — مسیر C

پیش‌ثبت: results/S565_PREREG_GAPOPEN_UNFILLED_DAY2_XAUUSD.md (کامیت da266684 —
قبل از هر تست).

رویداد: ماسک پایهٔ S560 روی آخرین کندل روز g−1 (گپ منفی بزرگ در بازگشایی روز g)
∧ کلوز روز g < کلوز روز g−1 (پرنشده) ⇒ سیگنال روی آخرین کندل روز g ⇒
ورود LONG در open اولین کندل روز g+1.

هندسه: V-TIME قاعدهٔ ثابت خانواده SL=TP=q98(|MFE|∪|MAE|) نیمهٔ اول،
hold = hold قفل S560 همان TF. بازوها: BARE / V-locked (qv قفل S562 روی روز g).

قواعد توقف (پیش‌ثبت §2): n_fh<30 ⇒ NO-VERDICT · lift_fh<+4pp ⇒ STOPPED_DEAD.
null: لانگ غیرشرطی (null_for از s561). n_trials=429.

گاردها: BUG-PERMK · BUG-NULLUNCOND · BUG-SCOREKEY · BUG-PIPGUESS ·
BUG-DATASETDRIFT · BUG-GEOMDRIFT · BUG-BRKTHRESH · قید ۲.
M30 ممنوع (S404) · M1/M5 ممنوع (ACCEPT) · EURUSD ممنوع (کاربر).

اجرا:
  python3 tools/s565_unfilled_day2.py lock  M15
  python3 tools/s565_unfilled_day2.py stop  M15
  python3 tools/s565_unfilled_day2.py judge M15
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
from tools.s560_adjudicate import build, _pip              # noqa: E402
from tools.s561_h8revival import null_for                  # noqa: E402
from tools.s562_volfilter import vol_filter_mask           # noqa: E402

N_TRIALS = 429          # پیش‌ثبت S565 §1 — انباشتهٔ صادقانهٔ خانواده
N_PERM = 500
SEED = 20260827
ALLOWED_TFS = ('M15', 'H1')
QV_LOCKED = {'M15': 85, 'H1': 78}     # عیناً قفل S562
OUT = os.path.join(ROOT, 'results', '_s565_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
S560_LOCK = os.path.join(ROOT, 'results', '_s560_arms', 'locked_config.json')
LIFT_STOP = 4.0


def _check_tf(tf: str):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S565 (فقط M15/H1)')


def day2_mask(d, tf, base_mask):
    """سیگنال S565: از هر سیگنال پایهٔ S560 (روی آخرین کندل روز g−1)،
    اگر کلوز روز g < کلوز روز g−1 ⇒ سیگنال روی آخرین کندل روز g."""
    t, c = d['time'], d['close']
    n = len(t)
    brk = day_breaks(t, tf)
    ends = np.concatenate([brk, [n - 1]])          # آخرین کندل هر روز
    n_days = len(ends)
    end_to_day = {int(ends[k]): k for k in range(n_days)}
    out = np.zeros(n, bool)
    n_events = n_unfilled = 0
    for i in np.flatnonzero(base_mask):
        k = end_to_day.get(int(i))                 # i = آخرین کندل روز g−1 ⇒ k=g−1
        if k is None or k + 1 >= n_days:
            continue
        n_events += 1
        close_gm1 = c[ends[k]]                     # کلوز روز g−1
        close_g = c[ends[k + 1]]                   # کلوز روز g
        if close_g < close_gm1:                    # پرنشده
            n_unfilled += 1
            j = int(ends[k + 1])                   # سیگنال روی آخرین کندل روز g
            if j + 1 < n:
                out[j] = True
    return out, n_events, n_unfilled


def geometry_vtime(d, mask, mh, split_bar):
    """SL=TP=q98(|MFE|∪|MAE|) فقط نیمهٔ اول — قاعدهٔ ثابت خانواده (V-TIME)."""
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
    d, df, base_mask, split_bar, cfg = build(tf)
    s560 = json.load(open(S560_LOCK))
    assert s560[tf]['cfg'] == cfg, 'BUG-GEOMDRIFT: cfg ناهمسان با قفل S560'
    assert s560[tf]['n_signals'] == int(base_mask.sum()), 'BUG-DATASETDRIFT'
    mh = int(s560[tf]['variants']['V-TIME']['mh'])
    m565, n_ev, n_unf = day2_mask(d, tf, base_mask)
    print(f"src={d['src']} base_events={n_ev} unfilled={n_unf} "
          f"({100.0 * n_unf / max(n_ev, 1):.1f}%) signals={int(m565.sum())} mh={mh}")
    scored = {}
    for arm_name, use_v in (('BARE', False), ('V', True)):
        mm = m565.copy()
        if use_v:
            mm = vol_filter_mask(d, tf, mm, QV_LOCKED[tf])
        g = geometry_vtime(d, mm, mh, split_bar)
        if g is None:
            scored[arm_name] = dict(mh=mh, sl=None, tp=None,
                                    n_signals=int(mm.sum()),
                                    t_first_half=None, n_first_half=0,
                                    wr_first_half=None, dd_first_half=None)
            continue
        zl = np.zeros(len(df), bool)
        tr = se.simulate_trades(df, mm, zl, g, g, 'XAUUSD',
                                max_hold=mh, allow_overlap=False)
        t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
        scored[arm_name] = dict(mh=mh, sl=g, tp=g, qv=QV_LOCKED[tf] if use_v else None,
                                n_signals=int(mm.sum()),
                                t_first_half=t_fh, n_first_half=n_fh,
                                wr_first_half=wr_fh, dd_first_half=dd_fh)
        print(f"  {arm_name}: n_sig={int(mm.sum())} sl=tp={g} → t={t_fh} "
              f"n_fh={n_fh} WR={wr_fh} DD={dd_fh}%")
    cands = [k for k in scored if scored[k]['t_first_half'] is not None]
    pick = max(cands, key=lambda k: round(scored[k]['t_first_half'], 2),
               default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(cfg=cfg, arms=scored, picked=pick,
                    n_base_events=n_ev, n_unfilled=n_unf,
                    split_bar=int(split_bar), split_utc=SPLIT_UTC,
                    src=d['src'], n_base_signals=int(base_mask.sum()))
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def rebuild_mask(d, tf, base_mask, arm_name):
    mm, _, _ = day2_mask(d, tf, base_mask)
    if arm_name == 'V':
        mm = vol_filter_mask(d, tf, mm, QV_LOCKED[tf])
    return mm


def stop_check(tf: str):
    """سد توقف پیش‌ثبت: lift نیمهٔ اول < +4pp ⇒ STOPPED_DEAD (نیمهٔ دوم باکره)."""
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    if not L.get('picked'):
        print(f"{tf}: NO-VERDICT (هیچ بازویی n_fh>=30 نداشت)")
        L['stop_check'] = dict(no_verdict=True)
        lock[tf] = L
        json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
        return
    a = L['arms'][L['picked']]
    d, df, base_mask, split_bar, cfg = build(tf)
    mm = rebuild_mask(d, tf, base_mask, L['picked'])
    assert int(mm.sum()) == a['n_signals'], 'BUG-DATASETDRIFT'
    df_fh = df.iloc[:split_bar].reset_index(drop=True)
    mm_fh = mm[:split_bar]
    nl = null_for(df_fh, mm_fh, a['sl'], a['tp'], a['mh'], n_perm=200, seed=SEED)
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
    if sc.get('no_verdict'):
        raise SystemExit(f'{tf} NO-VERDICT — داوری ممنوع')
    if sc.get('stopped_dead'):
        raise SystemExit(f'{tf} STOPPED_DEAD — داوری ممنوع (پیش‌ثبت §2)')
    if 'stopped_dead' not in sc:
        raise SystemExit(f'{tf}: اول فاز stop')
    a = L['arms'][L['picked']]
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    d, df, base_mask, split_bar, cfg = build(tf)
    assert L['n_base_signals'] == int(base_mask.sum()), 'BUG-DATASETDRIFT'
    mm = rebuild_mask(d, tf, base_mask, L['picked'])
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
            'cfg': cfg, 'n_signals': int(mm.sum()),
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
