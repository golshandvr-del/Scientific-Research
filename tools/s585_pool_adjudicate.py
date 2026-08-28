# -*- coding: utf-8 -*-
"""
s585_pool_adjudicate.py — داورِ استخرِ S585: {H8, H12, D1} سیگنالِ فریزِ
RVI(14) cross 70/30 (S584) با هندسهٔ مطلقِ فریز از results/_s584_explore.json.

پیش‌ثبت: results/S585_PREREG_RVI_POOL_H8H12D1.md (کامیت 39e29a3a / push 4304ac37)
الگوی ساختاری: tools/s540_pool_adjudicate.py (استخر) + tools/s580_adjudicate.py (نال).

گاردهای ارثی:
  BUG-GEOMDRIFT   — SL/TP/mh فقط از آرتیفکتِ _s584_explore.json خوانده می‌شود.
  BUG-DATASETDRIFT— assert بازه>12y + ثبتِ src/rows/span هر کارت.
  BUG-NULLUNCOND  — نالِ هر کارت در فضای همان کارت و همان هندسه.
  BUG-PERMK       — perm_k = اندازهٔ آرایهٔ جای‌گشت‌ها.
  BUG-SPLITDIR    — hold-out = صدکِ ۶۰٪ «زمانِ ورودِ» معاملاتِ استخر.
  BUG-SCOREKEY/ZBARNEST — نگاشتِ خروجی عیناً از s580.
  قید n≥30 هر کارت؛ قید C5 سهم≤۵۰٪؛ قاعدهٔ توقف: <۲ عضو ⇒ استخر تشکیل نمی‌شود.
حکم فقط از compute_rqs2 (n_trials=17). هیچ حکمِ دستی.
"""
from __future__ import annotations

import json
import os
import sys
import time as _time

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
from engine.rqs2_pool import pool_cards               # noqa: E402
from tools import s434_fast_data as fd                # noqa: E402

OUT = 'results/_s585'
SEED = 20260826
K_PERM = 500          # هر سمت، هر کارت (پیش‌ثبت §۶)
N_TRIALS = 17         # 16 (اکتشاف S584) + 1 (این آزمون)
SPLIT_FRAC = 0.60
C5_MAX_SHARE = 0.50
STEP_NS = 3600 * 1_000_000_000   # گریدِ ۱ساعته — ریزتر از ریزترین عضو H8
WARMUP = 250
RVI_P, UP, DN = 14, 70.0, 30.0
ARTIFACT = 'results/_s584_explore.json'


def frozen_geometry() -> dict:
    """گاردِ BUG-GEOMDRIFT — هندسه فقط از آرتیفکتِ رسمیِ S584 خوانده می‌شود."""
    with open(ARTIFACT, encoding='utf-8') as f:
        j = json.load(f)
    grid = j['grid']
    want = {'H8': dict(rr=1.618, mh=21),
            'H12': dict(rr=1.618, mh=34),
            'D1': dict(rr=1.618, mh=34)}
    out = {}
    for tf, sel in want.items():
        rows = [r for r in grid
                if r['tf'] == tf and r['rr'] == sel['rr'] and r['mh'] == sel['mh']]
        assert len(rows) == 1, f'آرتیفکت: نقطهٔ {tf}/{sel} یکتا نیست!'
        r = rows[0]
        out[tf] = dict(sl=float(r['sl']), tp=float(r['tp']), mh=int(sel['mh']))
    return out


def load_card(tf: str):
    d = fd.load_fast('XAUUSD', tf)
    df = fd.as_dataframe(d)
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s')
    span_y = (df['dt'].iloc[-1] - df['dt'].iloc[0]).days / 365.25
    assert span_y > 12.0, f'BUG-DATASETDRIFT {tf}: {span_y:.1f}y'
    prov = {'src': d['src'], 'rows': int(len(df)),
            'span': f"{df['dt'].iloc[0]} → {df['dt'].iloc[-1]}",
            'span_y': round(span_y, 2)}
    print(f"  [داده] {tf}: {prov['rows']:,} کندل · {prov['span']} · "
          f"src={prov['src']}", flush=True)
    return df, prov


def signals(df: pd.DataFrame):
    """سیگنالِ فریزِ S584 — بازنویسی صفر (همان کدِ tools/s584_explore.py)."""
    rvi = ib.rvi_vol(df, RVI_P).to_numpy()
    atr = ib.atr_s(df, 21).to_numpy()
    valid = np.isfinite(rvi) & np.isfinite(atr) & (atr > 0)
    prev = np.roll(rvi, 1)
    prev[0] = np.nan
    lsig = (rvi > UP) & (prev <= UP) & valid & np.isfinite(prev)
    ssig = (rvi < DN) & (prev >= DN) & valid & np.isfinite(prev)
    return lsig, ssig


def _wr(t):
    if t is None or len(t) == 0:
        return None
    return 100.0 * float((t['pnl_pip'].values > 0).mean())


def null_two_sided(df, n_long, n_short, sl, tp, mh, rng):
    """نالِ اندازه‌گیری‌شده در فضای همان کارت — دو سمت جدا (پیش‌ثبت §۵.۳)."""
    n = len(df)
    z = np.zeros(n, bool)
    valid = np.zeros(n, bool)
    valid[WARMUP:n - mh - 1] = True
    vidx = np.flatnonzero(valid)

    out = {}
    for side, k in (('long', n_long), ('short', n_short)):
        # uncond همان سمت — نمونهٔ بزرگ با overlap (الگوی s580)
        pick = rng.choice(vidx, size=min(50000, len(vidx)), replace=False)
        um = np.zeros(n, bool)
        um[pick] = True
        args = (um, z) if side == 'long' else (z, um)
        tu = se.simulate_trades(df, args[0], args[1], sl, tp, 'XAUUSD',
                                max_hold=mh, allow_overlap=True)
        wr_unc = _wr(tu)
        perm = []
        if k > 0:
            for _ in range(K_PERM):
                p = rng.choice(vidx, size=min(k, len(vidx)), replace=False)
                pm = np.zeros(n, bool)
                pm[p] = True
                pargs = (pm, z) if side == 'long' else (z, pm)
                t = se.simulate_trades(df, pargs[0], pargs[1], sl, tp,
                                       'XAUUSD', max_hold=mh,
                                       allow_overlap=False)
                w = _wr(t)
                if w is not None:
                    perm.append(w)
        pa = np.array(perm, float)
        out[side] = dict(
            uncond_wr=wr_unc,
            perm_mean=float(pa.mean()) if pa.size else None,
            perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
            perm_max=float(pa.max()) if pa.size else None,
            perm_k=int(pa.size))                      # گاردِ BUG-PERMK
    return out


def build_member(tf: str, geo: dict):
    df, prov = load_card(tf)
    lsig, ssig = signals(df)
    sl, tp, mh = geo['sl'], geo['tp'], geo['mh']
    tr = se.simulate_trades(df, lsig, ssig, sl, tp, 'XAUUSD',
                            max_hold=mh, allow_overlap=False)
    n = 0 if tr is None else len(tr)
    if n < 30:
        print(f'  ⛔ {tf}: n={n}<30 — MEASUREMENT-LIMITED، حذف از استخر', flush=True)
        return None
    nL = int((tr['direction'].values == 1).sum()) if 'direction' in tr else None
    nS = n - nL if nL is not None else None
    # seed قطعیِ هر کارت (hash() تصادفیِ هر-اجرا است — ضدبازتولید!)
    card_off = {'H8': 1, 'H12': 2, 'D1': 3}[tf]
    rng = np.random.default_rng(SEED + card_off)
    null = null_two_sided(df, int(lsig.sum()), int(ssig.sum()), sl, tp, mh, rng)
    wr_obs = _wr(tr)
    # lift = WR مشاهده‌شده − perm_mean وزنی به سهمِ تریدهای هر سمت
    wL = (nL / n) if nL is not None else 0.5
    pmL = null['long']['perm_mean']
    pmS = null['short']['perm_mean']
    perm_ref = (wL * (pmL if pmL is not None else 0.0) +
                (1 - wL) * (pmS if pmS is not None else 0.0))
    lift = wr_obs - perm_ref
    print(f"  {tf}: n={n} (L{nL}/S{nS}) WR={wr_obs:.2f} "
          f"perm_ref={perm_ref:.2f} lift={lift:+.2f}pp "
          f"sl={sl} tp={tp} mh={mh}", flush=True)
    return dict(card=f'XAUUSD_{tf}', tf=tf, tr=tr, dt=df['dt'].values,
                lift=float(lift), n=n, null=null, sl_pip=sl, tp_pip=tp,
                wr_obs=wr_obs, prov=prov)


def blend_pool_null(members_used, pool_df):
    """عیناً منطقِ S431/S520/S540: ترکیبِ وزنی با سهمِ پس-از-FIFO."""
    share = pool_df['src_card'].value_counts(normalize=True).to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u, den_u = 0.0, 0.0
        num_m, num_s, den_p, kmin = 0.0, 0.0, 0.0, None
        for m in members_used:
            w = float(share.get(m['card'], 0.0))
            if w <= 0:
                continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * w
                den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w
                num_s += (d['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = d.get('perm_k')
                kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def main():
    t0 = _time.time()
    os.makedirs(os.path.join(ROOT, OUT), exist_ok=True)
    geo = frozen_geometry()
    print(f'[S585-POOL] هندسهٔ فریز از {ARTIFACT}: '
          f'{json.dumps(geo, ensure_ascii=False)}', flush=True)
    print(f'  SEED={SEED} K={K_PERM}/side/card n_trials={N_TRIALS}', flush=True)

    members = []
    for tf in ('H8', 'H12', 'D1'):
        m = build_member(tf, geo[tf])
        if m is not None:
            members.append(m)

    res = pool_cards([dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                           lift=m['lift']) for m in members])
    if res is None or len(res['used']) < 2:
        used = [] if res is None else [u['card'] for u in res['used']]
        print(f'\n⛔ قاعدهٔ توقف: <۲ عضوِ هم‌جهتِ معتبر (used={used}) — '
              f'استخر تشکیل نمی‌شود؛ حکمِ رسمی INCOMPLETE (rqs2=0، موتور '
              f'فراخوانی نشد).', flush=True)
        with open(f'{OUT}/POOL_stopped.json', 'w') as f:
            json.dump(dict(members=[dict(card=m['card'], n=m['n'],
                                         lift=m['lift'], wr=m['wr_obs'])
                                    for m in members],
                           used=used,
                           dropped=None if res is None else res['dropped'],
                           reason='fewer_than_2_codirectional_members'),
                      f, ensure_ascii=False, default=str)
        return

    pool = res['pool']
    print(f"\n[انتخاب] used={[u['card'] for u in res['used']]} "
          f"dropped={[(d['card'], d['reason']) for d in res['dropped']]}",
          flush=True)
    print(f"[FIFO] n_before={res['n_before']} n_after={res['n_after']}",
          flush=True)

    # C5: سهمِ اعضا پس از FIFO
    share = pool['src_card'].value_counts(normalize=True)
    print(f"[C5 سهم] {share.round(3).to_dict()}", flush=True)
    if float(share.max()) > C5_MAX_SHARE:
        print(f"[C5 نقض] {share.idxmax()} سهم {share.max():.1%} > 50٪ ⇒ توقف "
              f"(پیش‌ثبت §۵.۶ — بدون دستکاری).", flush=True)
        with open(f'{OUT}/POOL_c5_violation.json', 'w') as f:
            json.dump(dict(share=share.to_dict()), f, ensure_ascii=False)
        return

    used_members = [m for m in members
                    if m['card'] in {u['card'] for u in res['used']}]
    null = blend_pool_null(used_members, pool)
    print(f"[نولِ استخر] {json.dumps(null, ensure_ascii=False)}", flush=True)

    # محورِ مشترکِ ۱ساعته + close از H1 کامل (پیش‌ثبت §۵.۷ — الگوی S540)
    t_lo = int(pool['t_entry'].values.astype(np.int64).min())
    t_hi = int(pool['t_exit'].values.astype(np.int64).max())
    axis_t = np.arange(t_lo - STEP_NS, t_hi + 2 * STEP_NS, STEP_NS,
                       dtype=np.int64)
    axis_dt = axis_t.astype('datetime64[ns]')
    ref_d = fd.load_fast('XAUUSD', 'H1')
    ref = fd.as_dataframe(ref_d)
    if 'dt' not in ref.columns:
        ref['dt'] = pd.to_datetime(ref['time'], unit='s')
    ref_t = ref['dt'].values.astype('datetime64[ns]').astype(np.int64)
    ref_c = ref['close'].to_numpy(float)
    pos = np.clip(np.searchsorted(ref_t, axis_t, 'right') - 1, 0,
                  len(ref_c) - 1)
    axis_close = ref_c[pos]
    print(f"[محور] 1h grid · {axis_dt[0]} → {axis_dt[-1]} · "
          f"{len(axis_t):,} سطل · close از {ref_d['src']}", flush=True)

    pool = pool.copy()
    pool['entry_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_entry'].values, 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.clip(
        np.searchsorted(axis_t, pool['t_exit'].values, 'left'),
        0, len(axis_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    # هندسهٔ استخر: میانگینِ وزنی به سهمِ پس-از-FIFO (الگوی S540)
    shares = pool['src_card'].value_counts(normalize=True).to_dict()
    by_card = {m['card']: m for m in used_members}
    sl_med = float(sum(by_card[c]['sl_pip'] * w for c, w in shares.items()))
    tp_med = float(sum(by_card[c]['tp_pip'] * w for c, w in shares.items()))
    print(f"[هندسه] sl_med={sl_med:.1f} tp_med={tp_med:.1f} pip "
          f"(rr={tp_med/sl_med:.3f})", flush=True)

    # تقسیم: صدکِ ۶۰٪ زمانِ ورود (گاردِ BUG-SPLITDIR)
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f"[تقسیم] مرز={np.datetime64(split_ns, 'ns')} · "
          f"اکتشاف={int((~holdout).sum())} · OOS={int(holdout.sum())}",
          flush=True)

    r = compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                     bar_time=axis_dt, null=null, close=axis_close,
                     holdout_mask=holdout, n_trials=N_TRIALS,
                     allow_overlap=False)
    print('\n' + format_rqs2('S585-POOL', r), flush=True)

    g = r.get('gates') or {}
    m_ = r.get('metrics') or {}
    out = dict(
        prereg='results/S585_PREREG_RVI_POOL_H8H12D1.md',
        seed=SEED, k_perm=K_PERM, n_trials=N_TRIALS,
        geometry_frozen=geo,
        members=[dict(card=m['card'], n=m['n'], lift=round(m['lift'], 3),
                      wr=round(m['wr_obs'], 2), sl=m['sl_pip'], tp=m['tp_pip'],
                      prov=m['prov']) for m in members],
        used=[u['card'] for u in res['used']], dropped=res['dropped'],
        selection=res['selection'],
        n_before=res['n_before'], n_after=res['n_after'],
        member_share=share.to_dict(),
        pool_null=null, sl_pip_med=sl_med, tp_pip_med=tp_med,
        split_frac=SPLIT_FRAC,
        verdict=r.get('verdict'), rqs2_score=r.get('rqs2_score'),
        gates={k: g.get(k) for k in sorted(g)},
        failed_gates=sorted(k for k, v in g.items() if v is False),
        z_luck_bound=m_.get('z_luck_bound'),   # گاردِ BUG-ZBARNEST — از metrics
        z_margin=m_.get('z_margin'),
        metrics={k: m_.get(k) for k in (
            'n_trades', 'n_wins', 'win_rate', 'expectancy_pip', 'cost_pip',
            'profit_factor', 'net_profit', 'max_dd_pct', 'max_consec_losses',
            'mcl_allowed', 'recovery_factor', 'skill_lift_pp', 'skill_z',
            'null_ref_wr', 'breakeven_wr_cost', 'rr', 'top_win_share',
            'z_obs', 'z_luck_bound', 'z_margin', 'skill_p_perm',
            'p_emp', 'p_adj_bonferroni', 'perm_k', 'perm_max')},
        notes=[str(x) for x in (r.get('notes') or [])],
        elapsed_s=round(_time.time() - t0, 1))
    with open(f'{OUT}/POOL_verdict.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    pool.to_csv(f'{OUT}/POOL_trades.csv', index=False)
    print(f'\nsaved -> {OUT}/POOL_verdict.json + POOL_trades.csv '
          f'[{out["elapsed_s"]}s]', flush=True)


if __name__ == '__main__':
    main()
