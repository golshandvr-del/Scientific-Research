"""S770 — استخر نهایی اعضای قوی {D1, H8} (الحاقیهٔ ۲). آخرین آزمون S770.

معیار عضویت (پیش‌ثبت‌شده): PF فردی >= 1.2 در داوری تک‌کارت.
H10 این بار داوری می‌شود: محور مرجع H1 با close.
n_trials=301.
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
from strategies.s770_pool_adjudicate import (              # noqa: E402
    member_for, blend_pool_null)

N_TRIALS = 301
MEMBER_TFS = ('D1', 'H8')   # PF فردی >= 1.2 (D1:1.287, H8:1.209) — منجمد


def main():
    rng = np.random.default_rng(SEED)
    members = []
    for tf in MEMBER_TFS:
        m = member_for(tf, rng)
        members.append(m)

    res = pool_cards(members)
    print(f"\n[pool2 selection] {json.dumps(res['selection'], ensure_ascii=False, default=str)}",
          flush=True)
    print(f"[pool2] n_before={res['n_before']} n_after={res['n_after']}", flush=True)

    pool = res['pool']
    used_cards = {u['card'] for u in res['used']}
    members_used = [m for m in members if m['card'] in used_cards]
    null = blend_pool_null(members_used, pool)
    print(f'[pool2 null] {json.dumps(null, ensure_ascii=False, default=str)}', flush=True)

    # ---- محور مرجع H1 برای bar_time/close (پروتکل S431 — رفع H10) ----
    d_h1, src_h1 = None, None
    from tools import s434_fast_data as fd
    dh = fd.load_fast('XAUUSD', 'H1')
    assert 'mt5_full' in dh['src'], 'E-16 guard'
    ref_t = (dh['time'].astype(np.int64) * 10**9)   # s → ns
    ref_c = dh['close'].astype(np.float64)

    pool = pool.sort_values('t_entry', kind='mergesort').reset_index(drop=True)
    pool['entry_bar'] = np.clip(np.searchsorted(ref_t, pool['t_entry'].values, 'left'),
                                0, len(ref_t) - 1)
    pool['exit_bar'] = np.clip(np.searchsorted(ref_t, pool['t_exit'].values, 'left'),
                               0, len(ref_t) - 1)
    pool['exit_bar'] = np.maximum(pool['exit_bar'], pool['entry_bar'])
    pool = pool.sort_values('exit_bar', kind='mergesort').reset_index(drop=True)

    bar_time = (ref_t / 10**9).astype('int64')  # epoch seconds axis

    # ---- holdout: صدک ۶۰٪ زمانِ ورود معاملات (درس BUG-SPLITDIR از S431) ----
    te_all = pool['t_entry'].values.astype(np.int64)
    split_ns = int(np.quantile(te_all, SPLIT_FRAC))
    holdout = te_all >= split_ns
    print(f'[split] boundary={np.datetime64(split_ns, "ns")} explore={int((~holdout).sum())} '
          f'oos={int(holdout.sum())}', flush=True)

    sl_med = float(np.median([m['sl_med'] for m in members_used]))
    tp_med = float(np.median([m['tp_med'] for m in members_used]))

    r = rqs2.compute_rqs2(pool, 'XAUUSD', sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null, close=ref_c,
                          holdout_mask=holdout, n_trials=N_TRIALS,
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2('S770-POOL2', r), flush=True)

    out = dict(members=[dict(card=u['card'], lift=u['lift'], n=u['n'])
                        for u in res['used']],
               n_before=res['n_before'], n_after=res['n_after'],
               verdict=r['verdict'], score=r.get('rqs2_score'),
               gates=r.get('gates'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating))
                            else str(v)) for k, v in r.get('metrics', {}).items()},
               notes=r.get('notes'))
    with open(os.path.join(SCAN_DIR, 'POOL2_verdict.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n[POOL2 VERDICT] {r['verdict']} score={r.get('rqs2_score')}", flush=True)


if __name__ == '__main__':
    main()
