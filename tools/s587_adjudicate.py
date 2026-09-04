# -*- coding: utf-8 -*-
"""
s587_adjudicate.py — داورِ S587: احیای کارتِ RVI-H12 با گیتِ دریفتِ TSM.

پیش‌ثبت: results/S587_PREREG_RVI_H12_DRIFT_REVIVAL.md (کامیت 0735c991)

قاعدهٔ فریز:
  سیگنال: RVI(14) cross 70/30 دوسویه (عیناً S584/S585).
  گیت علّی: K=120 کندل H12 (=60 روز). LONG اگر close[t-1]>close[t-1-120]؛
            SHORT اگر close[t-1]<close[t-1-120].
  هندسه: sl=151.09 tp=244.46 mh=34 — فقط از results/_s584_explore.json.

نال شرطی در فضای گیت (S523/S525): جای‌گشتِ هر سمت فقط روی کندل‌های
مجازِ همان سمت. گاردها: GEOMDRIFT/DATASETDRIFT/NULLUNCOND/PERMK/SPLITDIR/
SCOREKEY/ZBARNEST/PIPGUESS/DIRSTR. حکم: یک compute_rqs2 با n_trials=18.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT)

from engine import scalp_engine as se                 # noqa: E402
from engine import indicator_bank as ib               # noqa: E402
from engine.rqs2 import compute_rqs2, format_rqs2     # noqa: E402
from tools import s434_fast_data as fd                # noqa: E402

OUT = 'results/_s587'
SEED = 20260828
K_PERM = 500
N_TRIALS = 18          # 16 (S584) + 1 (S585) + 1 (این آزمون)
SPLIT_FRAC = 0.60
K_DRIFT = 120          # کندل H12 = 60 روز تقویمی
WARMUP = 250
RVI_P, UPT, DNT = 14, 70.0, 30.0
ARTIFACT = 'results/_s584_explore.json'


def frozen_geometry():
    """BUG-GEOMDRIFT — فقط از آرتیفکتِ S584."""
    with open(ARTIFACT, encoding='utf-8') as f:
        j = json.load(f)
    rows = [r for r in j['grid']
            if r['tf'] == 'H12' and r['rr'] == 1.618 and r['mh'] == 34]
    assert len(rows) == 1
    r = rows[0]
    return float(r['sl']), float(r['tp']), 34


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def main():
    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    sl, tp, mh = frozen_geometry()
    print(f'[S587] هندسهٔ فریز: sl={sl} tp={tp} mh={mh} · K_DRIFT={K_DRIFT} '
          f'· SEED={SEED} · n_trials={N_TRIALS}', flush=True)

    d = fd.load_fast('XAUUSD', 'H12')
    df = fd.as_dataframe(d)
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s')
    span_y = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    assert span_y > 12.0, f'BUG-DATASETDRIFT: {span_y:.1f}y'
    prov = {'src': d['src'], 'rows': int(len(df)),
            'span': f"{df['dt'].iloc[0]} → {df['dt'].iloc[-1]}"}
    print(f"  [داده] {prov['rows']:,} کندل · {prov['span']}", flush=True)

    n = len(df)
    close = df['close'].to_numpy(float)

    # سیگنال فریز (عیناً S584/S585)
    rvi = ib.rvi_vol(df, RVI_P).to_numpy()
    atr = ib.atr_s(df, 21).to_numpy()
    prev = np.roll(rvi, 1); prev[0] = np.nan
    valid = np.isfinite(rvi) & np.isfinite(prev) & np.isfinite(atr) & (atr > 0)
    lsig_raw = (rvi > UPT) & (prev <= UPT) & valid
    ssig_raw = (rvi < DNT) & (prev >= DNT) & valid

    # گیت دریفت علّی: close[t-1] در برابر close[t-1-K]
    c1 = np.roll(close, 1)
    cK = np.roll(close, 1 + K_DRIFT)
    gate_ok = np.arange(n) >= (1 + K_DRIFT)
    gate_up = (c1 > cK) & gate_ok
    gate_dn = (c1 < cK) & gate_ok

    lsig = lsig_raw & gate_up
    ssig = ssig_raw & gate_dn
    print(f'  سیگنال خام L{int(lsig_raw.sum())}/S{int(ssig_raw.sum())} → '
          f'گیت‌خورده L{int(lsig.sum())}/S{int(ssig.sum())}', flush=True)

    tr = se.simulate_trades(df, lsig, ssig, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    nt = 0 if tr is None else len(tr)
    if nt < 30:
        print(f'⛔ n={nt}<30 — MEASUREMENT-LIMITED؛ موتور فراخوانی نمی‌شود.',
              flush=True)
        with open(f'{OUT}/verdict.json', 'w') as f:
            json.dump(dict(error=f'n<30 (n={nt})', invalid=True), f)
        return
    nL = int((tr['direction'].values == 'long').sum())   # BUG-DIRSTR
    nS = nt - nL
    print(f'  معاملات: n={nt} (L{nL}/S{nS}) WR={_wr(tr):.2f}', flush=True)

    # نال شرطی در فضای گیت (S523/S525) — هر سمت روی کندل‌های مجاز خودش
    rng = np.random.default_rng(SEED)
    z = np.zeros(n, bool)
    base_valid = np.zeros(n, bool)
    base_valid[WARMUP:n - mh - 1] = True
    null = {}
    for side, gate, k_side in (('long', gate_up, int(lsig.sum())),
                               ('short', gate_dn, int(ssig.sum()))):
        vidx = np.flatnonzero(base_valid & gate)
        pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
        um = np.zeros(n, bool); um[pick] = True
        args = (um, z) if side == 'long' else (z, um)
        tu = se.simulate_trades(df, args[0], args[1], sl, tp, 'XAUUSD',
                                max_hold=mh, allow_overlap=True)
        wr_unc = _wr(tu)
        perm = []
        for _ in range(K_PERM):
            p = rng.choice(vidx, size=min(k_side, len(vidx)), replace=False)
            pm = np.zeros(n, bool); pm[p] = True
            pargs = (pm, z) if side == 'long' else (z, pm)
            t = se.simulate_trades(df, pargs[0], pargs[1], sl, tp, 'XAUUSD',
                                   max_hold=mh, allow_overlap=False)
            w = _wr(t)
            if w is not None:
                perm.append(w)
        pa = np.array(perm, float)
        null[side] = dict(uncond_wr=wr_unc,
                          perm_mean=float(pa.mean()) if pa.size else None,
                          perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                          perm_max=float(pa.max()) if pa.size else None,
                          perm_k=int(pa.size))          # BUG-PERMK
        print(f"  [نال {side}] vidx={len(vidx)} unc={wr_unc:.2f} "
              f"perm_mean={null[side]['perm_mean']:.2f} "
              f"sd={null[side]['perm_sd']:.2f}", flush=True)

    # F1 گزارش: lift گیت‌خورده در برابر مرجع بی‌گیتِ S585 (+7.95)
    wL = nL / nt
    perm_ref = wL * null['long']['perm_mean'] + (1 - wL) * null['short']['perm_mean']
    lift_gated = _wr(tr) - perm_ref
    print(f'  [F1] lift گیت‌خورده = {lift_gated:+.2f}pp '
          f'(مرجع بی‌گیت S585: +7.95pp)', flush=True)

    # split: صدک ۶۰٪ زمانِ ورود (BUG-SPLITDIR)
    entry_bars = tr['entry_bar'].to_numpy(int)
    t_entry = df['time'].to_numpy()[entry_bars]
    split_t = np.quantile(t_entry, SPLIT_FRAC)
    holdout = t_entry >= split_t
    print(f'  [تقسیم] مرز={pd.to_datetime(split_t, unit="s")} · '
          f'اکتشاف={int((~holdout).sum())} · OOS={int(holdout.sum())}',
          flush=True)

    r = compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                     bar_time=pd.to_numeric(df['time']).to_numpy(),
                     close=close, null=null, n_trials=N_TRIALS,
                     holdout_mask=holdout, initial_capital=10000.0,
                     allow_overlap=False)
    print('\n' + format_rqs2('S587-RVI-H12-DRIFT', r), flush=True)

    g = r.get('gates') or {}
    m = r.get('metrics') or {}
    out = dict(
        prereg='results/S587_PREREG_RVI_H12_DRIFT_REVIVAL.md',
        provenance=prov, seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS,
        geometry=dict(sl_pip=sl, tp_pip=tp, mh=mh, rr=round(tp / sl, 3)),
        k_drift_bars=K_DRIFT,
        n_raw=dict(L=int(lsig_raw.sum()), S=int(ssig_raw.sum())),
        n_gated=dict(L=int(lsig.sum()), S=int(ssig.sum())),
        n_trades=nt, n_long=nL, n_short=nS,
        lift_gated_pp=round(float(lift_gated), 3),
        lift_ungated_ref_pp=7.95,
        null=null,
        verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
        gates={k: g.get(k) for k in sorted(g)},
        failed_gates=sorted(k for k, v in g.items() if v is False),
        z_luck_bound=m.get('z_luck_bound'),      # BUG-ZBARNEST
        z_margin=m.get('z_margin'),
        metrics={k: m.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share',
            'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm',
            'p_emp', 'p_adj_bonferroni', 'perm_k', 'perm_max')},
        notes=[str(x) for x in (r.get('notes') or [])])
    with open(f'{OUT}/verdict.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f'\nsaved -> {OUT}/verdict.json', flush=True)


if __name__ == '__main__':
    main()
