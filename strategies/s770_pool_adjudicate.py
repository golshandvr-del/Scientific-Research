"""S770 — داوری استخر چندکارتی (الحاقیهٔ پیش‌ثبت ۱، کامیت 524339cd).

اعضا: کارت‌های lift>0 از داوری تک‌کارت با پیکربندی منجمد per-کارت.
انتخاب زیرمجموعه: engine/rqs2_pool.choose_homogeneous_subset (بدون دخالت).
نول استخر: ترکیب وزنی نول‌های per-کارت (الگوی blend_pool_null از S431).
یک داوری compute_rqs2 با n_trials=300.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                     # noqa: E402
from engine import rqs2                                    # noqa: E402
from engine.rqs2_pool import pool_cards                    # noqa: E402
from strategies.s770_adr_expansion import (                # noqa: E402
    load_card, build_features, signals_for, geometry, build_null,
    SEED, SPLIT_FRAC, SCAN_DIR)

N_TRIALS_POOL = 300
MEMBER_TFS = ('H1', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1')


def member_for(tf, rng):
    """اجرای منجمد لایه روی یک کارت + نول per-کارت. هیچ جستجویی نیست."""
    with open(os.path.join(SCAN_DIR, f'{tf}_verdict.json')) as f:
        v = json.load(f)
    theta, hold = v['theta'], v['hold']
    lift = v['metrics']['skill_lift_pp']
    df, src = load_card(tf)
    frac = build_features(df)
    sl_pip, tp_pip, atr = geometry(df)
    valid = np.isfinite(frac) & np.isfinite(sl_pip) & (sl_pip > 0)
    lsig, ssig = signals_for(frac, theta)
    lsig &= valid; ssig &= valid
    tr = se.simulate_trades(df, lsig, ssig, sl_pip, tp_pip, asset='XAUUSD',
                            max_hold=hold, allow_overlap=False)
    dt = pd.to_datetime(df['time'], unit='s').values
    n = len(tr)
    n_long = int((tr['direction'] == 'long').sum()) if n else 0
    n_short = n - n_long
    print(f'[member {tf}] θ={theta} hold={hold} n={n} lift={lift} src={src}',
          flush=True)
    vi = np.where(valid)[0]
    null = build_null(df, vi, sl_pip, tp_pip, n_long, n_short, hold, rng)
    return dict(card=f'XAUUSD_{tf}', tr=tr, dt=dt, lift=float(lift),
                null=null, sl_med=float(np.nanmedian(sl_pip)),
                tp_med=float(np.nanmedian(tp_pip)), src=src)


def blend_pool_null(members_used, pool_df):
    """ترکیب وزنی نول‌ها با وزن = سهم هر کارت در استخر نهایی (الگوی S431)."""
    w_by_card = pool_df['src_card'].value_counts().to_dict()
    out = {}
    for side in ('long', 'short'):
        num_u = num_m = num_s = den_u = den_p = 0.0
        kmin = None
        for m in members_used:
            w = float(w_by_card.get(m['card'], 0))
            if w <= 0:
                continue
            d = m['null'][side]
            if d.get('uncond_wr') is not None:
                num_u += d['uncond_wr'] * w; den_u += w
            if d.get('perm_mean') is not None and d.get('perm_sd') is not None:
                num_m += d['perm_mean'] * w
                num_s += (d['perm_sd'] ** 2) * (w ** 2)
                den_p += w
                k = d.get('perm_k')
                if k is not None:
                    kmin = k if kmin is None else min(kmin, k)
        out[side] = dict(
            uncond_wr=(num_u / den_u) if den_u > 0 else None,
            perm_mean=(num_m / den_p) if den_p > 0 else None,
            perm_sd=(float(np.sqrt(num_s)) / den_p) if den_p > 0 else None,
            perm_max=None, perm_k=kmin)
    return out


def main():
    rng = np.random.default_rng(SEED)
    members = []
    for tf in MEMBER_TFS:
        m = member_for(tf, rng)
        members.append(dict(card=m['card'], tr=m['tr'], dt=m['dt'],
                            lift=m['lift'], null=m['null'],
                            sl_med=m['sl_med'], tp_med=m['tp_med']))

    res = pool_cards(members)
    if res is None:
        print('[pool] هیچ عضو معتبری نماند ⇒ استخر ناممکن.', flush=True)
        return
    print(f"\n[pool selection] {json.dumps(res['selection'], ensure_ascii=False, default=str)}",
          flush=True)
    print(f"[pool] n_before={res['n_before']} n_after={res['n_after']} "
          f"used={[u['card'] for u in res['used']]} "
          f"dropped={[(d['card'], d['reason']) for d in res['dropped']]}", flush=True)

    pool = res['pool']
    used_cards = {u['card'] for u in res['used']}
    members_used = [m for m in members if m['card'] in used_cards]
    null = blend_pool_null(members_used, pool)
    print(f'[pool null] {json.dumps(null, ensure_ascii=False, default=str)}', flush=True)

    # split تقویمی در مرز ۶۰٪ زمان
    t0, t1 = pool['t_entry'].min(), pool['t_entry'].max()
    t_split = t0 + SPLIT_FRAC * (t1 - t0)
    # compute_rqs2 با split_bar بر اساس اندیس معامله در ترتیب زمانی کار می‌کند؛
    # bar_time را زمان ورود معاملات می‌دهیم و split_bar را اندیس مرز.
    pool = pool.sort_values('t_entry').reset_index(drop=True)
    bar_time = (pool['t_entry'].values / 1e9).astype('int64')  # ns→s
    split_idx = int((pool['t_entry'].values < t_split).sum())

    # هندسهٔ نماینده (میانهٔ وزنی اعضا) — فقط برای گزارش H2
    sl_med = float(np.median([m['sl_med'] for m in members_used]))
    tp_med = float(np.median([m['tp_med'] for m in members_used]))

    # entry_bar/exit_bar استخر باید یکتا و صعودی باشند تا H0 خراب نشود؛
    # از اندیس ترتیب زمانی استفاده می‌کنیم (concurrency=1 پس از FIFO).
    pool2 = pool.copy()
    pool2['entry_bar'] = np.arange(len(pool2))
    pool2['exit_bar'] = np.arange(len(pool2))

    r = rqs2.compute_rqs2(pool2, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null,
                          n_trials=N_TRIALS_POOL, split_bar=split_idx,
                          close=None)
    out = dict(pool_members=[u for u in res['used']],
               dropped=res['dropped'], n_before=res['n_before'],
               n_after=res['n_after'], split_idx=split_idx,
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating))
                            else str(v)) for k, v in r.get('metrics', {}).items()})
    with open(os.path.join(SCAN_DIR, 'POOL_verdict.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n[POOL VERDICT] {r['verdict']} score={r.get('rqs2_score')} "
          f"p_perm={r.get('metrics', {}).get('skill_p_perm')} "
          f"z={r.get('metrics', {}).get('skill_z')}", flush=True)
    print(f"gates={json.dumps(r.get('gates'), ensure_ascii=False)}", flush=True)


if __name__ == '__main__':
    main()
