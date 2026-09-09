# -*- coding: utf-8 -*-
"""
s569_gap_calm_fine.py — گپِ منفی S560 × گیتِ رژیمِ آرام روی TF ریز (M5/M1) — مسیر C

پیش‌ثبت: results/S569_PREREG_GAPOPEN_CALM_FINE_TF_XAUUSD.md (کامیت 520cb705 — قبل از هر تست).

پایه: ماسک و هندسهٔ V-TIME عیناً از S560 (build + locked_config — BUG-GEOMDRIFT).
گیت‌ها: V78 (s562.vol_filter_mask، qv منجمد 78) · SIGMA (σ RiskMetrics λ=0.94 از
s840.ewma_z، calm = σ_i ≤ median(σ_{i−233..i−1}) روی کندل سیگنال) · DUAL = V78 ∧ SIGMA.
گیت مرده: نرخ عبور > 90٪ ⇒ حذف از انتخاب (قانون S603).
سدها: n_fh<30 ⇒ NO-VERDICT · lift_fh<+4pp ⇒ STOPPED_DEAD. n_trials=439. SEED=20260905.

اجرا:
  python3 tools/s569_gap_calm_fine.py lock  M5
  python3 tools/s569_gap_calm_fine.py stop  M5
  python3 tools/s569_gap_calm_fine.py judge M5
  python3 tools/s569_gap_calm_fine.py overlap M5   (فقط پس از حکم)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from engine.rqs2 import compute_rqs2, n_required_for_h3    # noqa: E402
from tools.s560_adjudicate import build                    # noqa: E402
from tools.s560_gapopen_explore import SPLIT_UTC           # noqa: E402
from tools.s561_h8revival import null_for                  # noqa: E402
from tools.s562_volfilter import vol_filter_mask           # noqa: E402
from strategies.s840_engle_shock import ewma_z, LAMBDA     # noqa: E402

N_TRIALS = 439
N_PERM = 500
SEED = 20260905
ALLOWED_TFS = ('M5', 'M1')
QV = 78
W_SIGMA = 233
DEAD_GATE_PASS = 90.0
LIFT_STOP = 4.0
GATES = ('V78', 'SIGMA', 'DUAL')
OUT = os.path.join(ROOT, 'results', '_s569_arms')
LOCK_PATH = os.path.join(OUT, 'locked_config.json')
S560_LOCK = os.path.join(ROOT, 'results', '_s560_arms', 'locked_config.json')


def _check_tf(tf):
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ پیش‌ثبت S569 (فقط M5/M1)')


def frozen_geometry(tf):
    s560 = json.load(open(S560_LOCK))
    L = s560[tf]
    assert L['picked'] == 'V-TIME'
    g = L['variants']['V-TIME']
    return float(g['sl']), float(g['tp']), int(g['mh'])


def base(tf):
    d, df, mask, split_bar, cfg = build(tf)
    assert 'mt5_full' in d['src'], f"داده باید data/mt5_full باشد: {d['src']}"
    return d, df, mask, split_bar, cfg


def sigma_calm_flags(d):
    """calm[i] = σ_i ≤ median(σ_{i−W..i−1}) — علّی (پنجرهٔ بستهٔ گذشته)، تعریف S606/S1911."""
    z, r = ewma_z(d['close'], lam=LAMBDA)
    with np.errstate(divide='ignore', invalid='ignore'):
        sig = np.where(z != 0, r / z, np.nan)
    # بازسازی σ برای کندل‌های r=0 (z=0): همان فرمول
    var = np.full(len(sig), np.nan)
    c = d['close']
    k0 = min(50, len(c) - 1)
    v = float(np.var(r[1:k0 + 1]))
    v = v if v > 0 else 1e-12
    var[k0] = v
    for t in range(k0 + 1, len(c)):
        v = LAMBDA * v + (1.0 - LAMBDA) * r[t - 1] * r[t - 1]
        var[t] = v
    sig_full = np.sqrt(var)
    ok = np.isfinite(sig)
    assert np.nanmax(np.abs(sig[ok] - sig_full[ok])) < 1e-9, 'σ reconstruction mismatch'
    s = pd.Series(sig_full)
    med = s.shift(1).rolling(W_SIGMA, min_periods=W_SIGMA).median().values
    with np.errstate(invalid='ignore'):
        calm = np.isfinite(med) & np.isfinite(sig_full) & (sig_full <= med)
    return calm


def gate_masks(d, tf, mask):
    v = vol_filter_mask(d, tf, mask, QV)
    calm = sigma_calm_flags(d)
    s = mask & calm
    return {'V78': v, 'SIGMA': s, 'DUAL': v & s}


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


def phase_lock(tf):
    _check_tf(tf)
    d, df, mask, split_bar, cfg = base(tf)
    sl, tp, mh = frozen_geometry(tf)
    s560 = json.load(open(S560_LOCK))[tf]
    n_base = int(mask.sum())
    print(f"base S560 {tf}: n_signals={n_base} cfg={cfg} geometry sl=tp={sl} mh={mh} src={d['src']}")
    gm = gate_masks(d, tf, mask)
    fh = mask.copy(); fh[split_bar:] = False
    nb_fh = int(fh.sum())
    dens = {}
    for g in GATES:
        n_fh_pass = int((gm[g] & fh).sum())
        dens[g] = dict(n_pass_total=int(gm[g].sum()),
                       pass_rate_fh=round(100.0 * n_fh_pass / max(nb_fh, 1), 1),
                       n_pass_fh=n_fh_pass)
    pv = dens['V78']['pass_rate_fh'] / 100
    ps = dens['SIGMA']['pass_rate_fh'] / 100
    pd_ = dens['DUAL']['pass_rate_fh'] / 100
    collin = round(pd_ / (pv * ps), 3) if pv * ps > 0 else None
    print(f"densities (first half, base n={nb_fh}): {dens}  collinearity V×σ = {collin}")
    # پایهٔ S560 نیمهٔ اول برای مقایسه
    zl = np.zeros(len(df), bool)
    tr0 = se.simulate_trades(df, mask, zl, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
    t0, n0, wr0, dd0 = first_half_stats(tr0, split_bar)
    print(f"  BASE(S560): n_fh={n0} WR={wr0} t={t0} DD={dd0}%")
    scored = {}
    for g in GATES:
        tr = se.simulate_trades(df, gm[g], zl, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
        t_fh, n_fh, wr_fh, dd_fh = first_half_stats(tr, split_bar)
        dead = dens[g]['pass_rate_fh'] > DEAD_GATE_PASS
        scored[g] = dict(gate=g, sl=sl, tp=tp, mh=mh, n_signals=int(gm[g].sum()),
                         t_first_half=t_fh, n_first_half=n_fh, wr_first_half=wr_fh,
                         dd_first_half=dd_fh, dead_gate=bool(dead))
        print(f"  {g}: n_sig={int(gm[g].sum())} → t={t_fh} n_fh={n_fh} WR={wr_fh} DD={dd_fh}%"
              f"{'  [DEAD GATE >90%]' if dead else ''}")
    cands = [k for k in scored if scored[k]['t_first_half'] is not None and not scored[k]['dead_gate']]
    pick = max(cands, key=lambda k: round(scored[k]['t_first_half'], 2), default=None)
    os.makedirs(OUT, exist_ok=True)
    lock = json.load(open(LOCK_PATH)) if os.path.exists(LOCK_PATH) else {}
    lock[tf] = dict(arms=scored, picked=pick, densities=dens, collinearity_v_sigma=collin,
                    base=dict(n_signals=n_base, n_fh=n0, wr_fh=wr0, t_fh=t0, dd_fh=dd0,
                              s560_cfg=cfg, s560_judge_ref='results/_s560_arms/judge_%s.json' % tf),
                    geometry=dict(sl=sl, tp=tp, mh=mh, src='S560 V-TIME frozen'),
                    split_bar=int(split_bar), split_utc=SPLIT_UTC, src=d['src'])
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"LOCKED {tf} → {pick}  ({LOCK_PATH})")


def _rebuild(L, tf):
    d, df, mask, split_bar, _ = base(tf)
    assert int(mask.sum()) == L['base']['n_signals'], 'BUG-DATASETDRIFT base'
    gm = gate_masks(d, tf, mask)
    a = L['arms'][L['picked']]
    m = gm[L['picked']]
    assert int(m.sum()) == a['n_signals'], 'BUG-DATASETDRIFT arm'
    return d, df, mask, m, split_bar, a


def stop_check(tf):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    if not L.get('picked'):
        print(f"{tf}: NO-VERDICT (n_fh<30 یا همهٔ گیت‌ها مرده)")
        L['stop_check'] = dict(no_verdict=True)
        lock[tf] = L
        json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
        return
    d, df, _, m, split_bar, a = _rebuild(L, tf)
    df_fh = df.iloc[:split_bar].reset_index(drop=True)
    nl = null_for(df_fh, m[:split_bar], a['sl'], a['tp'], a['mh'], n_perm=200, seed=SEED)
    lift = (a['wr_first_half'] or 0) - (nl['long']['uncond_wr'] or 50.0)
    dead = lift < LIFT_STOP
    L['stop_check'] = dict(lift_fh_pp=round(lift, 2), null_uncond_wr_fh=nl['long']['uncond_wr'],
                           threshold=LIFT_STOP, stopped_dead=bool(dead))
    lock[tf] = L
    json.dump(lock, open(LOCK_PATH, 'w'), ensure_ascii=False, indent=1)
    print(f"{tf}: lift_fh={lift:+.2f}pp vs stop {LIFT_STOP}pp → "
          f"{'STOPPED_DEAD' if dead else 'PROCEED to judge'}")


def _judge_mask(tf, df, m, sl, tp, mh, split_bar, tag):
    zl = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, m, zl, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
    if len(tr) < 30:
        return dict(tag=tag, error=f'n<30 (n={len(tr)})', invalid=True)
    null = null_for(df, m, sl, tp, mh, n_perm=N_PERM, seed=SEED)
    res = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp, bar_time=df['time'].values,
                       close=df['close'].values, null=null, n_trials=N_TRIALS,
                       split_bar=split_bar, initial_capital=10000.0, allow_overlap=False)
    gt = res.get('gates') or {}
    mm = res.get('metrics') or {}
    lift = mm.get('skill_lift_pp')
    p0 = (null['long']['uncond_wr'] or 50.0) / 100.0
    n_need = n_required_for_h3(lift, p0) if lift else float('inf')
    return {
        'tag': tag, 'n_signals': int(m.sum()), 'verdict': res.get('verdict'),
        'rqs2_score': res.get('rqs2_score'),
        'gates': {k: gt.get(k) for k in sorted(gt)},
        'failed_gates': sorted(k for k, v in gt.items() if v is False),
        'unknown_gates': sorted(k for k, v in gt.items() if v is None),
        'null': null['long'], 'n_trials': N_TRIALS,
        'n_required_for_h3': None if n_need == float('inf') else round(float(n_need), 1),
        'metrics': {k: mm.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip', 'profit_factor',
            'net_profit', 'max_dd_pct', 'max_consec_losses', 'mcl_allowed', 'recovery_factor',
            'skill_lift_pp', 'skill_z', 'null_ref_wr', 'breakeven_wr_cost', 'rr',
            'top_win_share', 'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm', 'p_emp',
            'p_adj_bonferroni', 'perm_k', 'perm_max')},
        'notes': [str(x) for x in (res.get('notes') or [])],
    }


def phase_judge(tf):
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    sc = L.get('stop_check') or {}
    if sc.get('no_verdict') or sc.get('stopped_dead'):
        raise SystemExit(f'{tf} متوقف — داوری ممنوع (پیش‌ثبت §3-2)')
    if 'stopped_dead' not in sc:
        raise SystemExit(f'{tf}: اول فاز stop')
    d, df, base_mask, m, split_bar, a = _rebuild(L, tf)
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    print(f"src={d['src']} arm={L['picked']} sl={sl} tp={tp} mh={mh} n_sig={int(m.sum())}")
    res_out = _judge_mask(tf, df, m, sl, tp, mh, split_bar, tag=L['picked'])
    res_out.update(tf=tf, arm=L['picked'], direction='LONG',
                   geometry=dict(sl_pip=sl, tp_pip=tp, max_hold=mh, rr=round(tp / sl, 3),
                                 rule='S560 V-TIME frozen'),
                   split_bar=int(split_bar), split_utc=SPLIT_UTC, src=d['src'])
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'judge_{tf}.json')
    json.dump(res_out, open(path, 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: res_out.get(k) for k in ('verdict', 'rqs2_score', 'failed_gates',
                                                   'n_required_for_h3')}, ensure_ascii=False))
    mm2 = res_out.get('metrics') or {}
    print(f"WR={mm2.get('win_rate')} lift={mm2.get('skill_lift_pp')} z={mm2.get('skill_z')} "
          f"dd={mm2.get('max_dd_pct')} PF={mm2.get('profit_factor')} net={mm2.get('net_profit')} "
          f"mcl={mm2.get('max_consec_losses')}/{mm2.get('mcl_allowed')} rec={mm2.get('recovery_factor')}")
    print(f"saved → {path}")


def phase_overlap(tf):
    """ممیزی پس از حکم (§3-4): complement = سیگنال‌های S560 که گیت حذف کرد — چه بود؟"""
    _check_tf(tf)
    lock = json.load(open(LOCK_PATH))
    L = lock[tf]
    d, df, base_mask, m, split_bar, a = _rebuild(L, tf)
    sl, tp, mh = float(a['sl']), float(a['tp']), int(a['mh'])
    comp = base_mask & ~m
    zl = np.zeros(len(df), bool)
    out = {}
    for tag, mk in (('S569_gated', m), ('complement_removed', comp), ('S560_base', base_mask)):
        tr = se.simulate_trades(df, mk, zl, sl, tp, 'XAUUSD', max_hold=mh, allow_overlap=False)
        p = tr['pnl_pip'].values.astype(float)
        eq = 10000.0 + np.cumsum(p) * 10.0
        peak = np.maximum.accumulate(eq)
        out[tag] = dict(n=len(p), wr=round(100 * float((p > 0).mean()), 2) if len(p) else None,
                        mean_pip=round(float(p.mean()), 2) if len(p) else None,
                        dd_pct=round(float(((peak - eq) / peak).max() * 100), 2) if len(p) else None,
                        sum_pip=round(float(p.sum()), 1))
    out['share_of_base_kept_pct'] = round(100.0 * m.sum() / max(base_mask.sum(), 1), 1)
    path = os.path.join(OUT, f'overlap_{tf}.json')
    json.dump(out, open(path, 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    phase, tf = sys.argv[1], sys.argv[2]
    {'lock': phase_lock, 'stop': stop_check, 'judge': phase_judge,
     'overlap': phase_overlap}[phase](tf)
