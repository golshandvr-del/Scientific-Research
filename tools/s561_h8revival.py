# -*- coding: utf-8 -*-
"""
s561_h8revival.py — احیای H8 لایهٔ GapOpen در M15/M30/H1 — مسیر C

پیش‌ثبت: results/S561_PREREG_GAPOPEN_H8REVIVAL_XAUUSD.md (کامیت dddac874 —
قبل از هر تست). سیگنال عیناً منجمد از S560 (locked_config.json — cfg هر TF)؛
فقط هندسهٔ خروج بازوی جدید دارد:

  بازوهای متقارن : SL=TP=qX(|MFE|∪|MAE|)، X ∈ {85, 90, 95}
  بازوهای نامتقارن: SL=qX(|MAE|)، TP=q98(|MFE|)، X ∈ {85, 90}
  hold: عیناً قفل S560 (M15:1، M30:1، H1:2)

n_arms=5×3TF=15 → n_trials انباشتهٔ خانواده = 400 (S560) + 15 = 415.

دو فاز:
  lock  — فقط نیمهٔ اول: 5 بازو شبیه‌سازی، انتخاب با t نیمهٔ اول
          (تساوی → DD نیمهٔ اول کمتر)، قفل در JSON. (BUG-GEOMDRIFT)
  judge — تک‌لمس کل داده: null بازو-محور K=500 seed=20260814 +
          compute_rqs2 با هر پنج ورودی + split_bar (H7). M1/M5 ممنوع.

گاردها: BUG-PERMK · BUG-NULLUNCOND · BUG-SCOREKEY · BUG-PIPGUESS ·
BUG-DATASETDRIFT · BUG-GEOMDRIFT · BUG-BRKTHRESH · قید ۲ (n<30 حکم ندارد).

اجرا:
  python3 tools/s561_h8revival.py lock  M15
  python3 tools/s561_h8revival.py judge M15
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
from tools.s560_gapopen_explore import SPLIT_UTC           # noqa: E402
from tools.s560_adjudicate import build, _pip              # noqa: E402

N_TRIALS = 415        # پیش‌ثبت S561 §۴ — انباشتهٔ صادقانهٔ خانواده (400+15)
N_PERM = 500
SEED = 20260814
ALLOWED_TFS = ('M15', 'M30', 'H1')      # M1/M5 ممنوع — ACCEPT قطعی S560
OUT = os.path.join(ROOT, 'results', '_s561_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
S560_LOCK = os.path.join(ROOT, 'results', '_s560_arms', 'locked_config.json')


def _check_tf(tf: str):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S561 (فقط M15/M30/H1)')


def _mfe_mae_first_half(d, mask, hold, split_bar, asset='XAUUSD'):
    """چندک‌های MFE/MAE فقط از نیمهٔ اول (همان روش S560)."""
    pip = _pip(asset)
    h, l, o = d['high'], d['low'], d['open']
    n = len(o)
    idx = np.flatnonzero(mask)
    idx = idx[idx + 1 + hold < min(split_bar, n)]
    mfes, maes = [], []
    for i in idx:
        e = i + 1
        j1 = min(e + hold, n)
        entry = o[e]
        mfes.append((h[e:j1].max() - entry) / pip)
        maes.append((entry - l[e:j1].min()) / pip)
    return np.array(mfes), np.array(maes)


def arm_variants(d, mask, hold, split_bar):
    """۵ بازوی پیش‌ثبت‌شدهٔ S561 — چندک‌ها فقط از نیمهٔ اول."""
    mfes, maes = _mfe_mae_first_half(d, mask, hold, split_bar)
    both = np.concatenate([mfes, maes])
    q = lambda a, x: round(float(np.percentile(a, x)), 1)  # noqa: E731
    arms = {}
    for x in (85, 90, 95):
        w = max(q(both, x), 1.0)
        arms[f'SYM-q{x}'] = dict(sl=w, tp=w, mh=hold,
                                 rule=f'SL=TP=q{x}(|MFE|∪|MAE|) [first half]')
    tp98 = max(q(mfes, 98), 1.0)
    for x in (85, 90):
        arms[f'ASYM-sl{x}'] = dict(sl=max(q(maes, x), 1.0), tp=tp98, mh=hold,
                                   rule=f'SL=q{x}(|MAE|)·TP=q98(|MFE|) [first half]')
    return arms


def first_half_stats(tr, split_bar):
    """t، n، WR و maxDD کسری روی نیمهٔ اول (DD فقط تای‌بریکر قفل)."""
    m = tr[tr['exit_bar'] < split_bar]
    p = m['pnl_pip'].values.astype(float)
    if len(p) < 30:
        return None, len(p), None, None
    se_ = p.std(ddof=1) / np.sqrt(len(p))
    t = float(p.mean() / se_) if se_ > 0 else 0.0
    wr = round(float((p > 0).mean() * 100), 2)
    eq = 10000.0 + np.cumsum(p) * 10.0      # مقیاس ثابت — فقط برای مقایسه
    peak = np.maximum.accumulate(eq)
    dd = round(float(((peak - eq) / peak).max() * 100), 2)
    return t, len(p), wr, dd


def phase_lock(tf: str):
    _check_tf(tf)
    d, df, mask, split_bar, cfg = build(tf)   # سیگنال منجمد S560 (BEST همان)
    s560 = json.load(open(S560_LOCK))
    assert s560[tf]['cfg'] == cfg, 'BUG-GEOMDRIFT: cfg ناهمسان با قفل S560'
    assert s560[tf]['n_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT'
    print(f"src={d['src']}  signals={int(mask.sum())}  split_bar={split_bar}")
    arms = arm_variants(d, mask, cfg['hold'], split_bar)
    scored = {}
    for name, g in arms.items():
        z = np.zeros(len(df), bool)
        tr = se.simulate_trades(df, mask, z, g['sl'], g['tp'], 'XAUUSD',
                                max_hold=g['mh'], allow_overlap=False)
        t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
        scored[name] = dict(**g, t_first_half=t_fh, n_first_half=n_fh,
                            wr_first_half=wr_fh, dd_first_half=dd_fh)
        print(f"  {name}: sl={g['sl']} tp={g['tp']} mh={g['mh']} "
              f"→ t={t_fh} n={n_fh} WR={wr_fh} DD={dd_fh}%")
    cands = [k for k in scored if scored[k]['t_first_half'] is not None]
    # معیار پیش‌ثبت: t بیشینه؛ تساوی (اختلاف<0.01) → DD کمتر
    pick = max(cands, key=lambda k: (round(scored[k]['t_first_half'], 2),
                                     -(scored[k]['dd_first_half'] or 99)),
               default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(cfg=cfg, variants=scored, picked=pick,
                    split_bar=int(split_bar), split_utc=SPLIT_UTC,
                    src=d['src'], n_signals=int(mask.sum()))
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def null_for(df, mask, sl, tp, mh, n_perm=N_PERM, seed=SEED):
    """نال اختصاصی همین بازو — عیناً الگوی s437/s560."""
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
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    if tf not in lock or not lock[tf].get('picked'):
        raise SystemExit(f'{tf} قفل نشده — اول فاز lock')
    L = lock[tf]
    g = L['variants'][L['picked']]
    sl, tp, mh = float(g['sl']), float(g['tp']), int(g['mh'])
    d, df, mask, split_bar, cfg = build(tf)
    assert L['n_signals'] == int(mask.sum()), 'BUG-DATASETDRIFT'

    z0 = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, mask, z0, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n_tr = len(tr)
    print(f"src={d['src']}  arm={L['picked']} sl={sl} tp={tp} mh={mh} n={n_tr}")
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
                             rr=round(tp / sl, 3), rule=g['rule']),
            'cfg': cfg, 'n_signals': int(mask.sum()),
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
          f"rec={mm.get('recovery_factor')} perm_k={(res_out.get('null') or {}).get('perm_k')}")
    print(f"saved → {path}")


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    (phase_lock if phase == 'lock' else phase_judge)(tf)
