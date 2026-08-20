# -*- coding: utf-8 -*-
"""
s681_lagsat_union.py — اجرای S681: LAGSAT-UNION (وارثِ S680)
================================================================================

پیش‌ثبت: results/S681_PREREG_LAGSAT_FAMILY_UNION.md (کامیت cfc84f75 — قبل از اجرا).

فرضیهٔ واحد (قفل‌شده، بدونِ گزینشِ عضو):
  سیگنال = OR روی ۹ سلولِ از-پیش-موجودِ گریدِ S680:
    per ∈ {7, 11, 18} × D ∈ {3, 5, 8} × hi = 76 (lo = 24)
  تریگرِ لبه‌ای runlen==D (همان S680) — ورودِ هم‌جهت با اشباع.

هندسه عیناً ارثِ S680 (BUG-GEOMDRIFT — از JSONِ اکتشاف):
  SL = sl_pip از explore_<TF>.json، TP = 2.0×SL (پیش‌ثبت §۲؛ TP≥SL)،
  max_hold همان جدول. allow_overlap=False.

داوری یگانه per کارت: کلِ داده، split_bar=n//2 (H7 رسمی)،
نالِ کانونی K=500 (دو خطِ مبنا، سه تلهٔ کنترل بسته)، n_trials=429.

حکم عیناً از موتور. هیچ بازتنظیمی مجاز نیست.
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

from engine import scalp_engine as se                        # noqa: E402
from engine import rqs2                                      # noqa: E402
from engine.indicator_bank import _laguerre_levels           # noqa: E402
from tools import s434_fast_data as fd                       # noqa: E402
from strategies.s680_lagsat_explore import runlen_true       # noqa: E402
from strategies.s680_lagsat_adjudicate import build_null     # noqa: E402

EXPLORE_DIR = os.path.join(ROOT, 'results', '_s680_explore')
OUT_DIR = os.path.join(ROOT, 'results', '_s681_adjudicate')

# ── خانوادهٔ قفل‌شده (پیش‌ثبت §۱ — هیچ عضوی حذف/اضافه نمی‌شود) ──
UNION_PERS = (7, 11, 18)
UNION_DS = (3, 5, 8)
UNION_HI = 76.0
RR = 2.0                 # پیش‌ثبت §۲ — TP = 2.0×SL

K_PERM = 500             # درسِ S435 — زیرِ ۵۰۰ حکمِ H3 نوسانی است
N_TRIALS = 429           # پیش‌ثبت §۳ — بودجهٔ تجمعیِ خانوادهٔ LAGSAT
SEED = 20260815          # همان بذرِ S680 (بازتولیدپذیری)


def union_signals(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """OR روی ۹ عضو؛ لِوِل‌های لاگر فقط یک‌بار per «per» محاسبه می‌شوند."""
    n = len(close)
    long_u = np.zeros(n, bool)
    short_u = np.zeros(n, bool)
    lo = 100.0 - UNION_HI
    x = close.astype(np.float64)
    for per in UNION_PERS:
        g = 1.0 - 2.0 / (per + 1)
        L0, L1, L2, L3 = _laguerre_levels(x, g)
        cu = np.zeros_like(L0); cd = np.zeros_like(L0)
        for a, b in ((L0, L1), (L1, L2), (L2, L3)):
            up = a >= b
            cu += np.where(up, a - b, 0.0)
            cd += np.where(~up, b - a, 0.0)
        tot = cu + cd
        lrsi = np.where(tot != 0, 100.0 * cu / tot, 50.0)
        rl_hi = runlen_true(lrsi > UNION_HI)
        rl_lo = runlen_true(lrsi < lo)
        for D in UNION_DS:
            long_u |= (rl_hi == D)      # هم‌جهت با اشباع (فرضیهٔ S680)
            short_u |= (rl_lo == D)
        del L0, L1, L2, L3, cu, cd, tot, lrsi, rl_hi, rl_lo
    return long_u, short_u


def adjudicate(tf: str, asset: str = 'XAUUSD', k_perm: int = K_PERM,
               verbose: bool = True) -> dict:
    t0 = time.time()
    ex = json.load(open(os.path.join(EXPLORE_DIR, f'explore_{tf}.json'),
                        encoding='utf-8'))
    sl = float(ex['sl_pip'])            # BUG-GEOMDRIFT: عیناً از JSONِ S680
    tp = round(RR * sl, 1)
    mh = int(ex['max_hold'])
    if tp < sl:
        raise ValueError('TP<SL ممنوع (قانونِ حفظِ بودجه)')

    d = fd.load_fast(asset, tf)
    src = d['src']
    df = fd.as_dataframe(d)
    del d
    gc.collect()
    n_full = len(df)
    split = n_full // 2

    if verbose:
        print(f'\n═══ S681 UNION {asset}-{tf} ═══\n'
              f'  اجتماع: per∈{UNION_PERS} × D∈{UNION_DS} × hi={UNION_HI}\n'
              f'  هندسه: SL={sl} TP={tp} mh={mh} | src={src} '
              f'n_full={n_full:,} split={split:,}', flush=True)

    long_sig, short_sig = union_signals(df['close'].values)
    if verbose:
        print(f'  سیگنالِ اجتماع: long={int(long_sig.sum()):,} '
              f'short={int(short_sig.sum()):,}', flush=True)

    trades = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                                max_hold=mh, allow_overlap=False)
    if trades is None or len(trades) == 0:
        res = dict(tf=tf, verdict_engine=None, note='no_trades_full')
        print('  معامله‌ای تولید نشد.', flush=True)
        return res
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

    res = dict(layer='S681', tf=tf, asset=asset, src=src, n_full=n_full,
               split_bar=split,
               union=dict(pers=list(UNION_PERS), Ds=list(UNION_DS),
                          hi=UNION_HI, rr=RR),
               sl_pip=sl, tp_pip=tp, max_hold=mh,
               n_trades=int(len(trades)),
               n_long_sig=int(long_sig.sum()), n_short_sig=int(short_sig.sum()),
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

    del df, trades, long_sig, short_sig
    gc.collect()
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', default='M1')
    ap.add_argument('--kperm', type=int, default=K_PERM)
    a = ap.parse_args()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            adjudicate(tf, k_perm=a.kperm)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f'!! {tf}: {type(e).__name__}: {e}', flush=True)
        gc.collect()
    print('\n[S681 adjudication done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
