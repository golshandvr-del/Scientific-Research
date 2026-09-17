# -*- coding: utf-8 -*-
"""
s1560_gap_sigma_vs_v.py — گپِ منفی S560 × σ-CALM در برابر V روی M15/H1 — مسیر C

پیش‌ثبت: results/S1560_PREREG_GAPOPEN_SIGMA_VS_V_M15H1_XAUUSD.md (کامیت 633e51d6 — قبل از هر تست).

پایه/هندسه: عیناً S560 (build + locked V-TIME). V: qv قفل S562 (M15=85, H1=78) — فقط مرجع.
σ: عیناً tools.s569_gap_calm_fine.sigma_calm_flags (import). بازوهای داوری: SIGMA, DUAL.
n_trials=443. SEED=20260909. فقط اکتشاف — هیچ استقراری.

اجرا: python3 tools/s1560_gap_sigma_vs_v.py {lock|stop|judge|overlap} {M15|H1}
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
from tools.s560_adjudicate import build                    # noqa: E402
from tools.s560_gapopen_explore import SPLIT_UTC           # noqa: E402
from tools.s561_h8revival import null_for                  # noqa: E402
from tools.s562_volfilter import vol_filter_mask           # noqa: E402
from tools.s569_gap_calm_fine import (                     # noqa: E402
    sigma_calm_flags, first_half_stats)

N_TRIALS = 443
N_PERM = 500
SEED = 20260909
ALLOWED_TFS = ('M15', 'H1')
DEAD_GATE_PASS = 90.0
LIFT_STOP = 4.0
JUDGED = ('SIGMA', 'DUAL')
OUT = os.path.join(ROOT, 'results', '_s1560_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
S560_LOCK = os.path.join(ROOT, 'results', '_s560_arms', 'locked_config.json')
S562_LOCK = os.path.join(ROOT, 'results', '_s562_arms', 'locked_config.json')


def _check_tf(tf):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S1560 (فقط M15/H1)')


def frozen(tf):
    s560 = json.load(open(S560_LOCK))[tf]
    assert s560['picked'] == 'V-TIME'
    g = s560['variants']['V-TIME']
    s562 = json.load(open(S562_LOCK))[tf]
    qv = int(s562['arms'][s562['picked']]['qv'])
    return float(g['sl']), float(g['tp']), int(g['mh']), qv, int(s562['arms'][s562['picked']]['n_filtered'])


def base(tf):
    d, df, mask, split_bar, cfg = build(tf)
    assert 'mt5_full' in d['src'], f"داده باید data/mt5_full باشد: {d['src']}"
    return d, df, mask, split_bar, cfg


def gate_masks(d, tf, mask, qv):
    v = vol_filter_mask(d, tf, mask, qv)
    s = mask & sigma_calm_flags(d)
    return {'V': v, 'SIGMA': s, 'DUAL': v & s}


def phase_lock(tf):
    _check_tf(tf)
    d, df, mask, split_bar, cfg = base(tf)
    sl, tp, mh, qv, n562 = frozen(tf)
    gm = gate_masks(d, tf, mask, qv)
    assert int(gm['V'].sum()) == n562, f"BUG-DATASETDRIFT S562 reproduction: {int(gm['V'].sum())} != {n562}"
    print(f"base S560 {tf}: n={int(mask.sum())} cfg={cfg} sl=tp={sl} mh={mh} | V qv={qv} n={n562} (S562 reproduced)")
    fh = mask.copy(); fh[split_bar:] = False
    nb = int(fh.sum())
    dens = {}
    for g in ('V', 'SIGMA', 'DUAL'):
        npass = int((gm[g] & fh).sum())
        dens[g] = dict(n_pass_total=int(gm[g].sum()), n_pass_fh=npass,
                       pass_rate_fh=round(100.0 * npass / max(nb, 1), 1))
    pv, ps, pd_ = (dens[g]['pass_rate_fh'] / 100 for g in ('V', 'SIGMA', 'DUAL'))
    collin = round(pd_ / (pv * ps), 3) if pv * ps > 0 else None
    print(f"densities fh (base n={nb}): {dens}  collinearity V×σ={collin}")
    zl = np.zeros(len(df), bool)
    scored = {}
    for g, m in (('BASE', mask), ('V', gm['V']), ('SIGMA', gm['SIGMA']), ('DUAL', gm['DUAL'])):
        tr = se.simulate_trades(df, m, zl, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
        t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
        dead = g in JUDGED and dens[g]['pass_rate_fh'] > DEAD_GATE_PASS
        scored[g] = dict(gate=g, sl=sl, tp=tp, mh=mh, n_signals=int(m.sum()), t_first_half=t_fh,
                         n_first_half=n_fh, wr_first_half=wr_fh, dd_first_half=dd_fh,
                         judged=(g in JUDGED), dead_gate=bool(dead))
        print(f"  {g:6s}: n_sig={int(m.sum())} t={t_fh} n_fh={n_fh} WR={wr_fh} DD={dd_fh}%"
              f"{'  [REF only]' if g not in JUDGED else ''}{'  [DEAD]' if dead else ''}")
    # پاسخ H_scale/H_self با نیمهٔ اول
    tv, ts = scored['V']['t_first_half'], scored['SIGMA']['t_first_half']
    h_answer = None
    if tv is not None and ts is not None:
        h_answer = 'H_scale (V >= SIGMA)' if tv >= ts else 'H_self (SIGMA > V)'
    print(f"  first-half answer {tf}: {h_answer}  (t_V={tv}, t_SIGMA={ts})")
    cands = [k for k in JUDGED if scored[k]['t_first_half'] is not None and not scored[k]['dead_gate']]
    pick = max(cands, key=lambda k: round(scored[k]['t_first_half'], 2), default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(arms=scored, picked=pick, densities=dens, collinearity_v_sigma=collin,
                    first_half_answer=h_answer, qv_frozen=qv,
                    geometry=dict(sl=sl, tp=tp, mh=mh, src='S560 V-TIME frozen'),
                    n_base=int(mask.sum()), split_bar=int(split_bar), split_utc=SPLIT_UTC, src=d['src'])
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def _rebuild(L, tf):
    d, df, mask, split_bar, _ = base(tf)
    assert int(mask.sum()) == L['n_base'], 'BUG-DATASETDRIFT base'
    gm = gate_masks(d, tf, mask, L['qv_frozen'])
    a = L['arms'][L['picked']]
    m = gm[L['picked']]
    assert int(m.sum()) == a['n_signals'], 'BUG-DATASETDRIFT arm'
    return d, df, mask, gm, m, split_bar, a


def stop_check(tf):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    if not L.get('picked'):
        L['stop_check'] = dict(no_verdict=True)
        lock[tf] = L
        json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
        print(f"{tf}: NO-VERDICT"); return
    d, df, _, _, m, split_bar, a = _rebuild(L, tf)
    df_fh = df.iloc[:split_bar].reset_index(drop=True)
    nl = null_for(df_fh, m[:split_bar], a['sl'], a['tp'], a['mh'], n_perm=200, seed=SEED)
    lift = (a['wr_first_half'] or 0) - (nl['long']['uncond_wr'] or 50.0)
    dead = lift < LIFT_STOP
    L['stop_check'] = dict(lift_fh_pp=round(lift, 2), null_uncond_wr_fh=nl['long']['uncond_wr'],
                           threshold=LIFT_STOP, stopped_dead=bool(dead))
    lock[tf] = L
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"{tf}: lift_fh={lift:+.2f}pp → {'STOPPED_DEAD' if dead else 'PROCEED to judge'}")


def phase_judge(tf):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    sc = L.get('stop_check') or {}
    if sc.get('no_verdict') or sc.get('stopped_dead'):
        raise SystemExit(f'{tf} متوقف — داوری ممنوع')
    if 'stopped_dead' not in sc:
        raise SystemExit(f'{tf}: اول فاز stop')
    d, df, _, _, m, split_bar, a = _rebuild(L, tf)
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    zl = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, m, zl, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
    print(f"src={d['src']} arm={L['picked']} sl={sl} tp={tp} mh={mh} n={len(tr)}")
    null = null_for(df, m, sl, tp, mh, n_perm=N_PERM, seed=SEED)
    res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp, bar_time=df['time'].values,
                       close=df['close'].values, null=null, n_trials=N_TRIALS,
                       split_bar=split_bar, initial_capital=10000.0, allow_overlap=False)
    gt = res.get('gates') or {}
    mm = res.get('metrics') or {}
    lift = mm.get('skill_lift_pp')
    p0 = (null['long']['uncond_wr'] or 50.0) / 100.0
    n_need = n_required_for_h3(lift, p0) if lift else float('inf')
    out = {
        'tf': tf, 'arm': L['picked'], 'direction': 'LONG', 'n_signals': int(m.sum()),
        'geometry': dict(sl_pip=sl, tp_pip=tp, max_hold=mh, rule='S560 V-TIME frozen'),
        'verdict': res.get('verdict'), 'rqs2_score': res.get('rqs2_score'),
        'gates': {k: gt.get(k) for k in sorted(gt)},
        'failed_gates': sorted(k for k, v in gt.items() if v is False),
        'null': null['long'], 'n_trials': N_TRIALS,
        'n_required_for_h3': None if n_need == float('inf') else round(float(n_need), 1),
        'metrics': {k: mm.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip', 'profit_factor',
            'net_profit', 'max_dd_pct', 'max_consec_losses', 'mcl_allowed', 'recovery_factor',
            'skill_lift_pp', 'skill_z', 'null_ref_wr', 'breakeven_wr_cost', 'rr',
            'top_win_share', 'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm', 'p_emp',
            'p_adj_bonferroni', 'perm_k', 'perm_max')},
        'notes': [str(x) for x in (res.get('notes') or [])],
        'split_bar': int(split_bar), 'split_utc': SPLIT_UTC, 'src': d['src'],
    }
    path = os.path.join(OUT, f'judge_{tf}.json')
    json.dump(out, open(path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: out[k] for k in ('verdict', 'rqs2_score', 'failed_gates')}, ensure_ascii=False))
    print(f"WR={mm.get('win_rate')} lift={mm.get('skill_lift_pp')} z={mm.get('skill_z')} "
          f"dd={mm.get('max_dd_pct')} PF={mm.get('profit_factor')} net={mm.get('net_profit')} "
          f"rec={mm.get('recovery_factor')} mcl={mm.get('max_consec_losses')}/{mm.get('mcl_allowed')}")
    print(f"saved → {path}")


def phase_overlap(tf):
    _check_tf(tf)
    L = json.load(open(LOCK_PATH))[tf]
    d, df, mask, gm, m, split_bar, a = _rebuild(L, tf)
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    zl = np.zeros(len(df), bool)
    out = {}
    sets = (('kept', m), ('removed_vs_base', mask & ~m), ('S560_base', mask),
            ('S562_V_ref', gm['V']), ('kept_not_in_V', m & ~gm['V']), ('V_not_in_kept', gm['V'] & ~m))
    for tag, mk in sets:
        tr = se.simulate_trades(df, mk, zl, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
        p = tr['pnl_pip'].values.astype(float)
        if len(p) == 0:
            out[tag] = dict(n=0); continue
        eq = 10000.0 + np.cumsum(p) * 10.0
        peak = np.maximum.accumulate(eq)
        out[tag] = dict(n=len(p), wr=round(100 * float((p > 0).mean()), 2), mean_pip=round(float(p.mean()), 2),
                        dd_pct=round(float(((peak - eq) / peak).max() * 100), 2), sum_pip=round(float(p.sum()), 1))
    out['share_of_base_kept_pct'] = round(100.0 * m.sum() / max(mask.sum(), 1), 1)
    out['jaccard_with_V'] = round(float((m & gm['V']).sum() / max((m | gm['V']).sum(), 1)), 3)
    path = os.path.join(OUT, f'overlap_{tf}.json')
    json.dump(out, open(path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    {'lock': phase_lock, 'stop': stop_check, 'judge': phase_judge, 'overlap': phase_overlap}[phase](tf)
