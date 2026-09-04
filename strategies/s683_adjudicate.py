# -*- coding: utf-8 -*-
"""
s683_adjudicate.py — داوریِ یگانهٔ S683 per کارت (مسیرِ C)
================================================================================
پیش‌ثبت: results/S683_PREREG_LINEARITY_GRIND.md (d77b027).
اکتشاف: strategies/s683_linearity_explore.py — فقط نیمهٔ اول.

نامزدِ مکانیکی (پیش‌ثبت §۴): بیشینهٔ z_screen | n≥30، exp>0، **فلات الزامی**
(همسایه در L مجاور یا θ دیگر با همان بقیهٔ ابعاد، lift_be>0). بدونِ فلات ⇒
کارت واجد نیست (سخت‌تر از S682 که fallback داشت).
یک بار per کارت روی کلِ داده با split_bar=n_full//2. رد = مرگ.

گاردها: GEOMDRIFT (هندسه از JSONِ اکتشاف)، PIPGUESS، PERMK، NULLUNCOND،
SCOREKEY، ZBARAPPROX. نال: دو خطِ مبنا per سمت، K=500، سه تلهٔ کنترل بسته.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se                      # noqa: E402
from engine import rqs2                                    # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402
from strategies.s680_lagsat_adjudicate import build_null   # noqa: E402
from strategies.s683_linearity_explore import (            # noqa: E402
    rolling_linreg, LS, THETAS, OUT_DIR as EXPLORE_DIR)

OUT_DIR = os.path.join(ROOT, 'results', '_s683_adjudicate')
K_PERM = 500
N_TRIALS = 271           # پیش‌ثبت §۳ (247 + 24 تجمعیِ بلوک)
SEED = 20260827          # پیش‌ثبت §۵


def pick_candidate(cells: list[dict]) -> tuple[dict | None, str]:
    ok = [c for c in cells if 'skipped' not in c and c.get('n', 0) >= 30
          and c.get('exp_pip', -9) > 0]
    if not ok:
        return None, 'no_valid_cells'
    bykey = {(c['L'], c['th'], c['rr']): c for c in cells if 'skipped' not in c}

    def has_plateau(c):
        i = LS.index(c['L'])
        nbs = [(LS[j], c['th'], c['rr']) for j in (i - 1, i + 1)
               if 0 <= j < len(LS)]
        nbs += [(c['L'], t2, c['rr']) for t2 in THETAS if t2 != c['th']]
        return any(bykey.get(k, {}).get('lift_be', -99) > 0 for k in nbs)

    ok.sort(key=lambda c: c['z_screen'], reverse=True)
    for c in ok:
        if has_plateau(c):
            return c, 'plateau_ok'
    return None, 'no_plateau'          # پیش‌ثبت: بدونِ فلات ⇒ واجد نیست


def signals_for(df, L: int, th: float, warm: int = 100):
    c = df['close'].values.astype(np.float64)
    slope, r2 = rolling_linreg(c, L)
    lin = r2 >= th
    prev = np.concatenate(([False], lin[:-1]))
    edge = lin & ~prev
    long_sig = edge & (slope > 0)
    short_sig = edge & (slope < 0)
    long_sig[:warm] = False
    short_sig[:warm] = False
    return long_sig, short_sig


def adjudicate(tf: str, asset: str = 'XAUUSD', k_perm: int = K_PERM,
               verbose: bool = True) -> dict:
    t0 = time.time()
    ex = json.load(open(os.path.join(EXPLORE_DIR, f'explore_{tf}.json'),
                        encoding='utf-8'))
    cand, why = pick_candidate(ex['cells'])
    if cand is None:
        print(f'[{tf}] هیچ نامزدی — {why}', flush=True)
        return dict(tf=tf, verdict_engine=None, selection=why)

    sl = float(ex['sl_pip'])                 # BUG-GEOMDRIFT
    tp = round(float(cand['rr']) * sl, 1)
    mh = int(ex['max_hold'])
    warm = int(ex.get('warm', 100))
    if tp < sl:
        raise ValueError('TP<SL ممنوع')

    d = fd.load_fast(asset, tf)
    src = d['src']
    df = fd.as_dataframe(d)
    del d
    gc.collect()
    n_full = len(df)
    split = n_full // 2

    if verbose:
        print(f'\n═══ داوریِ S683 {asset}-{tf} ═══\n'
              f'  نامزد: L={cand["L"]} θ={cand["th"]} rr={cand["rr"]} ({why})\n'
              f'  هندسه: SL={sl} TP={tp} mh={mh} | src={src} '
              f'n_full={n_full:,} split={split:,}', flush=True)

    long_sig, short_sig = signals_for(df, int(cand['L']), float(cand['th']),
                                      warm)
    trades = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                                max_hold=mh, allow_overlap=False)
    if trades is None or len(trades) == 0:
        print('  معامله‌ای تولید نشد.', flush=True)
        return dict(tf=tf, verdict_engine=None, selection='no_trades_full')
    pnl = trades['pnl_pip'].values
    if verbose:
        print(f'  کلِ داده: n={len(trades):,} WR={100 * (pnl > 0).mean():.2f}% '
              f'exp={pnl.mean():+.2f}pip', flush=True)

    null = build_null(df, asset, long_sig, short_sig, sl, tp, mh,
                      k_perm=k_perm, seed=SEED, verbose=verbose)

    r = rqs2.compute_rqs2(trades, asset, sl_pip=sl, tp_pip=tp,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split,
                          close=df['close'].values)

    res = dict(layer='S683', tf=tf, asset=asset, src=src, n_full=n_full,
               split_bar=split, candidate=cand, selection=why,
               sl_pip=sl, tp_pip=tp, max_hold=mh,
               n_trades=int(len(trades)),
               wr_full=round(100 * float((pnl > 0).mean()), 2),
               exp_pip_full=round(float(pnl.mean()), 3),
               null=null, n_trials=N_TRIALS, k_perm=k_perm,
               rqs2=r, elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'adj_{tf}.json'), 'w',
              encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)

    v = r.get('verdict'); sc = r.get('rqs2_score')
    m = r.get('metrics') or {}
    print(f'\n  ⚖️ حکمِ موتور [{tf}]: {v} · score={sc} · '
          f'skill_p_perm={m.get("skill_p_perm")} · z={m.get("skill_z")} · '
          f'lift={m.get("skill_lift_pp")}pp · WR={m.get("win_rate")}',
          flush=True)
    gates = r.get('gates') or {}
    print('  گیت‌ها: ' + ' '.join(f'{k}={gates[k]}' for k in sorted(gates)),
          flush=True)
    del df, trades
    gc.collect()
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', required=True)
    ap.add_argument('--kperm', type=int, default=K_PERM)
    a = ap.parse_args()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            adjudicate(tf, k_perm=a.kperm)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f'!! {tf}: {type(e).__name__}: {e}', flush=True)
        gc.collect()
    print('\n[S683 adjudication done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
