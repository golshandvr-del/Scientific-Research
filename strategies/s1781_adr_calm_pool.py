# -*- coding: utf-8 -*-
"""
S1781 — انبساط ADR (S770 منجمد) × رژیم آرام σ (S606) · استخر {D1,H8} · ابن هیثم
طبق results/S1781_PREREG_AdrExpansionCalmRegime.md (کامیت d9fa0946). فقط اکتشاف.
import از s770_adr_expansion (بلوک دیگری — فقط خوانده می‌شود، هیچ تغییری).
usage: python3 strategies/s1781_adr_calm_pool.py
"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import rqs2
from engine.rqs2_pool import pool_cards
from strategies.s770_adr_expansion import (load_card, build_features, signals_for,
                                           geometry, build_null)

SEED = 1781
THETA, HOLD = 0.65, 16          # منجمد S770 (D1_verdict.json / H8_verdict.json)
CARDS = ('D1', 'H8')
LAM, W_CALM = 0.94, 233         # منجمد S606/S1911/S955
N_TRIALS = 302
SPLIT_FRAC = 0.60
OUT = os.path.join(ROOT, 'results', '_s1781'); os.makedirs(OUT, exist_ok=True)


def calm_regime(close):
    """reg_t = σ_t / median(σ_{t-233..t-1}); σ² RiskMetrics λ=0.94 روی r_{t-1} (علّی)."""
    c = np.asarray(close, float)
    r = np.diff(np.log(c), prepend=np.log(c[0]))
    v = np.full(len(c), np.nan)
    warm = 30
    v[warm] = np.var(r[1:warm + 1])
    for t in range(warm + 1, len(c)):
        v[t] = LAM * v[t - 1] + (1 - LAM) * r[t - 1] * r[t - 1]
    sig = np.sqrt(v)
    med = pd.Series(sig).shift(1).rolling(W_CALM, min_periods=W_CALM).median().values
    return sig / med


def member(tf, arm, rng):
    df, src = load_card(tf)
    assert 'mt5_full' in src, src
    frac = build_features(df)
    sl_pip, tp_pip, atr = geometry(df)
    reg = calm_regime(df['close'].values)
    valid = np.isfinite(frac) & np.isfinite(sl_pip) & (sl_pip > 0) & np.isfinite(reg)
    lsig, ssig = signals_for(frac, THETA)
    lsig &= valid; ssig &= valid
    n_raw = int(lsig.sum() + ssig.sum())
    if arm == 'calm':
        gate = reg <= 1.0
    elif arm == 'storm':
        gate = reg > 1.0
    else:
        gate = np.ones(len(df), bool)
    lsig &= gate; ssig &= gate
    pass_rate = (lsig.sum() + ssig.sum()) / max(n_raw, 1)
    tr = se.simulate_trades(df, lsig, ssig, sl_pip, tp_pip, asset='XAUUSD',
                            max_hold=HOLD, allow_overlap=False)
    n = len(tr); nL = int((tr['direction'] == 'long').sum()) if n else 0
    # نول در همان فضای گیت (نول شرطی — سخت‌ترین؛ قانون S523/S606)
    vi = np.where(valid & gate)[0]
    null = build_null(df, vi, sl_pip, tp_pip, nL, n - nL, HOLD, rng)
    # lift تقریبی برای انتخاب همگنی استخر (فقط برای pool_cards؛ حکم از موتور)
    wr = float((tr['pnl_pip'] > 0).mean() * 100) if n else np.nan
    u = [null[s]['uncond_wr'] for s in ('long', 'short') if null[s]['uncond_wr'] is not None]
    lift = wr - float(np.mean(u)) if u else 0.0
    print(f'[{arm} {tf}] src={src} n_raw_sig={n_raw} pass={pass_rate:.2f} n={n} WR={wr:.1f} lift~{lift:+.1f}', flush=True)
    dt = pd.to_datetime(df['time'], unit='s').values
    return dict(card=f'XAUUSD_{tf}', tr=tr, dt=dt, lift=float(lift), null=null,
                sl_med=float(np.nanmedian(sl_pip)), tp_med=float(np.nanmedian(tp_pip)),
                pass_rate=float(pass_rate), n=n, wr=wr, src=src,
                bar_time=df['time'].values, split=int(len(df) * SPLIT_FRAC),
                close=df['close'].values)


def blend_null(members_used, pool_df):
    w_by = pool_df['src_card'].value_counts().to_dict(); out = {}
    for side in ('long', 'short'):
        nu = nm = ns = du = dp = 0.0; kmin = None
        for m in members_used:
            w = float(w_by.get(m['card'], 0)); d = m['null'][side]
            if w <= 0: continue
            if d.get('uncond_wr') is not None: nu += d['uncond_wr'] * w; du += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                nm += d['perm_mean'] * w; ns += (d['perm_sd'] ** 2) * w ** 2; dp += w
                k = d.get('perm_k'); kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(uncond_wr=nu / du if du else None, perm_mean=nm / dp if dp else None,
                         perm_sd=float(np.sqrt(ns)) / dp if dp else None, perm_max=None, perm_k=kmin)
    return out


def judge_pool(arm, members):
    res = pool_cards(members)
    if res is None:
        print(f'[{arm}] pool impossible'); return None
    pool = res['pool'].sort_values('t_entry').reset_index(drop=True)
    used = {u['card'] for u in res['used']}
    mu = [m for m in members if m['card'] in used]
    null = blend_null(mu, pool)
    t0, t1 = pool['t_entry'].min(), pool['t_entry'].max()
    split_idx = int((pool['t_entry'].values < t0 + SPLIT_FRAC * (t1 - t0)).sum())
    bar_time = (pool['t_entry'].values / 1e9).astype('int64')
    p2 = pool.copy(); p2['entry_bar'] = np.arange(len(p2)); p2['exit_bar'] = np.arange(len(p2))
    sl = float(np.median([m['sl_med'] for m in mu])); tp = float(np.median([m['tp_med'] for m in mu]))
    r = rqs2.compute_rqs2(p2, 'XAUUSD', sl_pip=sl, tp_pip=tp, bar_time=bar_time, null=null,
                          n_trials=N_TRIALS, split_bar=split_idx, close=None)
    m = r['metrics']
    line = (f"S1781-POOL-{arm.upper()} | {r['verdict']} RQS2={r['rqs2_score']} | n={len(p2)} "
            f"WR={m.get('win_rate')} PF={m.get('profit_factor')} lift={m.get('skill_lift_pp')} "
            f"z={m.get('skill_z')} p={m.get('skill_p_perm')} | used={sorted(used)} dropped={[(d['card'], d['reason']) for d in res['dropped']]}")
    gates = ' '.join(f"H{i}{'✓' if r['gates'][f'H{i}'] else '✗'}" for i in range(11))
    print(line); print('  ' + gates); print('  oos:', m.get('oos'))
    out = dict(arm=arm, verdict=r['verdict'], score=r['rqs2_score'], gates=r['gates'], n=len(p2),
               used=res['used'], dropped=res['dropped'], null=null, n_trials=N_TRIALS, split_idx=split_idx,
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in m.items()},
               notes=r['notes'], line=line, gates_str=gates)
    json.dump(out, open(os.path.join(OUT, f'POOL_{arm}.json'), 'w'), ensure_ascii=False, indent=1, default=str)
    p2.to_csv(os.path.join(OUT, f'POOL_{arm}_trades.csv'), index=False)
    return out


def judge_card(arm, m):
    r = rqs2.compute_rqs2(m['tr'], 'XAUUSD', sl_pip=m['sl_med'], tp_pip=m['tp_med'], bar_time=m['bar_time'],
                          null=m['null'], n_trials=N_TRIALS, split_bar=m['split'], close=m['close'])
    mm = r['metrics']
    line = (f"S1781-{m['card']}-{arm.upper()} | {r['verdict']} RQS2={r['rqs2_score']} | n={m['n']} WR={mm.get('win_rate')} "
            f"PF={mm.get('profit_factor')} lift={mm.get('skill_lift_pp')} z={mm.get('skill_z')} p={mm.get('skill_p_perm')} pass={m['pass_rate']:.2f}")
    print(line)
    json.dump(dict(line=line, verdict=r['verdict'], score=r['rqs2_score'], gates=r['gates'],
                   metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v)) for k, v in mm.items()}),
              open(os.path.join(OUT, f"{m['card']}_{arm}.json"), 'w'), ensure_ascii=False, indent=1, default=str)
    return line


if __name__ == '__main__':
    summary = {}
    for arm in ('raw', 'calm', 'storm'):
        rng = np.random.default_rng(SEED)
        mems = [member(tf, arm, rng) for tf in CARDS]
        cards = [judge_card(arm, m) for m in mems]
        pool = judge_pool(arm, [dict(card=m['card'], tr=m['tr'], dt=m['dt'], lift=m['lift'], null=m['null'],
                                    sl_med=m['sl_med'], tp_med=m['tp_med']) for m in mems])
        summary[arm] = dict(cards=cards, pool=pool['line'] if pool else None,
                            pool_gates=pool['gates_str'] if pool else None,
                            pass_rates={m['card']: m['pass_rate'] for m in mems})
    json.dump(summary, open(os.path.join(OUT, 'SUMMARY.json'), 'w'), ensure_ascii=False, indent=1, default=str)
    print('\n===== SUMMARY =====')
    for arm, s in summary.items():
        print(arm, '::', s['pool']); print('   ', s['pool_gates']); [print('   ', c) for c in s['cards']]
