"""S771 — استخرِ اعضای قوی {W1, D1, H12} (الحاقیهٔ ۱، کامیت fa1c5779). آخرین آزمونِ S771.

قاعدهٔ عضویت (پیش‌ثبت‌شده): PF فردی >= 1.30 در داوریِ تک‌کارت.
پروتکل کلمه‌به‌کلمه S770-POOL2: pool_cards FIFO · blend_pool_null · holdout به کوانتیل ۶۰٪ زمانِ ورود ·
محورِ مرجعِ H1 با close برای H10 · n_trials=141.
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
from tools import s434_fast_data as fd                    # noqa: E402
from strategies.s771_amr_monthly_expansion import (       # noqa: E402
    load_card, build_features, geometry, build_null, SEED, SPLIT_FRAC, SCAN_DIR)
from strategies.s770_adr_expansion import signals_for     # noqa: E402
from strategies.s770_pool_adjudicate import blend_pool_null  # noqa: E402

N_TRIALS = 141
MEMBER_TFS = ('W1', 'D1', 'H12')   # PF فردی: W1 1.439 · D1 1.451 · H12 1.345 — منجمد


def member_for(tf, rng):
    """اجرای منجمدِ پیکربندیِ داوریِ تکی روی کارت + نولِ per-کارت. هیچ جستجویی نیست."""
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
    print(f'[member {tf}] θ={theta} hold={hold} n={n} lift={lift} src={src}', flush=True)
    vi = np.where(valid)[0]
    null = build_null(df, vi, sl_pip, tp_pip, n_long, n_short, hold, rng)
    return dict(card=f'XAUUSD_{tf}', tr=tr, dt=dt, lift=float(lift), null=null,
                sl_med=float(np.nanmedian(sl_pip)), tp_med=float(np.nanmedian(tp_pip)), src=src)


def main():
    rng = np.random.default_rng(SEED)
    members = [member_for(tf, rng) for tf in MEMBER_TFS]
    res = pool_cards(members)
    print(f"\n[pool selection] {json.dumps(res['selection'], ensure_ascii=False, default=str)}", flush=True)
    print(f"[pool] n_before={res['n_before']} n_after={res['n_after']}", flush=True)
    pool = res['pool']
    used_cards = {u['card'] for u in res['used']}
    members_used = [m for m in members if m['card'] in used_cards]
    null = blend_pool_null(members_used, pool)
    print(f'[pool null] {json.dumps(null, ensure_ascii=False, default=str)}', flush=True)

    dh = fd.load_fast('XAUUSD', 'H1')
    assert 'mt5_full' in dh['src'], 'E-16 guard'
    ref_t = (dh['time'].astype(np.int64) * 10**9)
    ref_c = dh['close'].astype(np.float64)
    pool = pool.sort_values('t_entry', kind='mergesort').reset_index(drop=True)
    pool['entry_bar'] = np.clip(np.searchsorted(ref_t, pool['t_entry'].values, 'left'), 0, len(ref_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(ref_t, pool['t_exit'].values, 'left'), 0, len(ref_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)
    bar_time = (ref_t / 10**9).astype('int64')

    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[split] boundary={np.datetime64(split_ns, "ns")} explore={int((~holdout).sum())} oos={int(holdout.sum())}', flush=True)

    sl_med = float(np.median([m['sl_med'] for m in members_used]))
    tp_med = float(np.median([m['tp_med'] for m in members_used]))
    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med, bar_time=bar_time,
                          null=null, close=ref_c, holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S771-POOL', r), flush=True)
    out = dict(members=[dict(card=u['card'], lift=u['lift'], n=u['n']) for u in res['used']],
               n_before=res['n_before'], n_after=res['n_after'],
               verdict=r['verdict'], score=r.get('rqs2_score'), gates=r.get('gates'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                        for k, v in r.get('metrics', {}).items()},
               notes=r.get('notes'))
    with open(os.path.join(SCAN_DIR, 'POOL_verdict.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n[POOL VERDICT] {r['verdict']} score={r.get('rqs2_score')}", flush=True)


if __name__ == '__main__':
    main()
