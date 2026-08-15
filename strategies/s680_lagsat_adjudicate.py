# -*- coding: utf-8 -*-
"""
s680_lagsat_adjudicate.py — داوریِ **یگانهٔ** S680 per کارت (مسیرِ C)
================================================================================

پیش‌ثبت: results/S680_PREREG_LAGSAT_SATURATION_DURATION.md (a43a26af).
اکتشاف: strategies/s680_lagsat_explore.py — فقط نیمهٔ اول را دید.

این فایل **یک بار** per کارت اجرا می‌شود: نامزدِ قفل‌شده روی **کلِ** داده،
با `split_bar = n_full // 2` تا نیمهٔ دوم (که هرگز در جست‌وجو دیده نشد)
hold-outِ رسمیِ H7 باشد. رد شد = مرده؛ بازتنظیم ممنوع.

قاعدهٔ گزینشِ نامزد (مکانیکی، بدونِ دخالتِ سلیقه):
  از سلول‌های نیمهٔ اول با n≥30 و exp_pip>0، بیشینهٔ z_screen؛
  به‌شرطِ «فلات»: دستِ‌کم یک همسایهٔ per (مجاور در دنبالهٔ لوکاس) با همان
  hi/D/rr باید lift_be>0 داشته باشد (درسِ variants.md — قلهٔ تیزِ تکی = رد).
  اگر فلات نداشت، سلولِ بعدی. اگر هیچ سلولِ exp>0 نبود، بهترین z_screen
  صرفِ‌نظر از exp داوری می‌شود تا حکم را **موتور** بدهد نه من.

گاردهای موروثی:
  BUG-GEOMDRIFT — هندسه/سلول از JSONِ اکتشاف خوانده می‌شود، بازمحاسبه نمی‌شود.
  BUG-PIPGUESS  — pip/spread از ASSETS موتور.
  BUG-PERMK     — perm_k = تعدادِ جای‌گشت‌ها (K=500)، نه اندازهٔ نمونه.
  BUG-NULLUNCOND— هر دو خطِ مبنا با هندسه/hold/overlapِ خودِ نامزد.
  BUG-SCOREKEY  — کلیدِ نمره `rqs2_score`؛ حکم عیناً از `verdict` موتور.
  سه تلهٔ کنترل — k جای‌گشت = تعدادِ سیگنالِ نهایی؛ فقط کندل‌های واجد؛
                  هندسهٔ یکسان (اینجا trail/BE نداریم ⇒ تلهٔ ۲ خودکار بسته).

خروجی: results/_s680_adjudicate/adj_<TF>.json + چاپِ حکم.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se                    # noqa: E402
from engine import rqs2                                  # noqa: E402
from engine.indicator_bank import _laguerre_levels       # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402
from strategies.s680_lagsat_explore import (             # noqa: E402
    runlen_true, LUCAS_PERS, MAX_HOLD, OUT_DIR as EXPLORE_DIR)

OUT_DIR = os.path.join(ROOT, 'results', '_s680_adjudicate')
K_PERM = 500          # درسِ S435 گام ۸۷ — زیرِ ۵۰۰ حکمِ H3 نوسانی است
N_TRIALS = 405        # پیش‌ثبت §۲ — گریدِ ۴۰۵ سلولی per کارت
SEED = 20260815


def pick_candidate(cells: list[dict]) -> tuple[dict | None, str]:
    """گزینشِ مکانیکیِ نامزد طبقِ قاعدهٔ سرآیند."""
    ok = [c for c in cells if 'skipped' not in c and c.get('n', 0) >= 30]
    if not ok:
        return None, 'no_valid_cells'
    by_key = {(c['per'], c['hi'], c['D'], c['rr']): c for c in ok}

    def has_plateau(c):
        i = LUCAS_PERS.index(c['per'])
        for j in (i - 1, i + 1):
            if 0 <= j < len(LUCAS_PERS):
                nb = by_key.get((LUCAS_PERS[j], c['hi'], c['D'], c['rr']))
                if nb is not None and nb.get('lift_be', -99) > 0:
                    return True
        return False

    pos = sorted([c for c in ok if c.get('exp_pip', -99) > 0],
                 key=lambda c: c['z_screen'], reverse=True)
    for c in pos:
        if has_plateau(c):
            return c, 'plateau_ok'
    if pos:
        return pos[0], 'no_plateau_fallback'  # صادقانه علامت می‌خورد
    # هیچ سلولِ exp>0 — حکم را موتور بدهد
    best = max(ok, key=lambda c: c['z_screen'])
    return best, 'exp_negative_best_z'


def signals_for(close: np.ndarray, per: int, hi: float, D: int):
    g = 1.0 - 2.0 / (per + 1)
    L0, L1, L2, L3 = _laguerre_levels(close.astype(np.float64), g)
    cu = np.zeros_like(L0); cd = np.zeros_like(L0)
    for a, b in ((L0, L1), (L1, L2), (L2, L3)):
        up = a >= b
        cu += np.where(up, a - b, 0.0)
        cd += np.where(~up, b - a, 0.0)
    tot = cu + cd
    lrsi = np.where(tot != 0, 100.0 * cu / tot, 50.0)
    lo = 100.0 - hi
    return runlen_true(lrsi > hi) == D, runlen_true(lrsi < lo) == D


def build_null(df, asset, long_sig, short_sig, sl, tp, mh,
               k_perm=K_PERM, seed=SEED, verbose=True) -> dict:
    """مدلِ صفرِ کانونی — دو خطِ مبنا per سمت، سه تلهٔ کنترل بسته."""
    n = len(df)
    warmup = 400          # اشباعِ D-کندلی + گرم‌شدنِ فیلترِ بازگشتی
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    z = np.zeros(n, bool)
    rng = np.random.default_rng(seed)

    out = {}
    for side, sig in (('long', long_sig), ('short', short_sig)):
        k = int(sig.sum())
        if k == 0:
            out[side] = {}
            continue
        # خطِ مبنای ۱: بی‌قید — allow_overlap=True (تعریفِ بی‌قید)
        if side == 'long':
            tr_u = se.simulate_trades(df, valid, z, sl, tp, asset,
                                      max_hold=mh, allow_overlap=True)
        else:
            tr_u = se.simulate_trades(df, z, valid, sl, tp, asset,
                                      max_hold=mh, allow_overlap=True)
        pnl_u = tr_u['pnl_pip'].values if tr_u is not None and len(tr_u) else None
        wr_u = (100.0 * float((pnl_u > 0).sum()) / len(pnl_u)) \
            if pnl_u is not None else None

        # خطِ مبنای ۲: جای‌گشتِ زمانی — k = سیگنالِ نهاییِ همان سمت
        kk = min(k, len(vidx))
        wrs = []
        t0 = time.time()
        for i in range(k_perm):
            pm = np.zeros(n, bool)
            pm[rng.choice(vidx, size=kk, replace=False)] = True
            if side == 'long':
                tr_p = se.simulate_trades(df, pm, z, sl, tp, asset,
                                          max_hold=mh, allow_overlap=False)
            else:
                tr_p = se.simulate_trades(df, z, pm, sl, tp, asset,
                                          max_hold=mh, allow_overlap=False)
            if tr_p is not None and len(tr_p):
                p = tr_p['pnl_pip'].values
                wrs.append(100.0 * float((p > 0).sum()) / len(p))
            if verbose and (i + 1) % 100 == 0:
                print(f'    [{side}] جای‌گشت {i + 1}/{k_perm} '
                      f'({time.time() - t0:.0f}s)', flush=True)
        pa = np.array(wrs, float)
        out[side] = dict(
            uncond_wr=wr_u,
            perm_mean=float(pa.mean()) if pa.size else None,
            perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
            perm_max=float(pa.max()) if pa.size else None,
            perm_k=int(pa.size),          # BUG-PERMK: تعدادِ جای‌گشت‌ها
        )
        if verbose:
            print(f'  [{side}] null: uncond={wr_u} '
                  f'perm_mean={out[side]["perm_mean"]} '
                  f'sd={out[side]["perm_sd"]} K={pa.size}', flush=True)
    return out


def adjudicate(tf: str, asset: str = 'XAUUSD', k_perm: int = K_PERM,
               verbose: bool = True) -> dict:
    t0 = time.time()
    exp_fp = os.path.join(EXPLORE_DIR, f'explore_{tf}.json')
    ex = json.load(open(exp_fp, encoding='utf-8'))
    cand, why = pick_candidate(ex['cells'])
    if cand is None:
        res = dict(tf=tf, verdict_engine=None, selection=why)
        print(f'[{asset}-{tf}] هیچ نامزدی — {why}', flush=True)
        return res

    sl = float(ex['sl_pip'])                    # BUG-GEOMDRIFT: از JSON
    tp = round(float(cand['rr']) * sl, 1)
    mh = int(ex['max_hold'])
    if tp < sl:
        raise ValueError('TP<SL ممنوع (قانونِ حفظِ بودجه)')

    d = fd.load_fast(asset, tf)
    df = fd.as_dataframe(d)
    n_full = len(df)
    split = n_full // 2

    if verbose:
        print(f'\n═══ داوریِ S680 {asset}-{tf} ═══\n'
              f'  نامزد: per={cand["per"]} hi={cand["hi"]} D={cand["D"]} '
              f'rr={cand["rr"]} ({why})\n'
              f'  هندسه: SL={sl} TP={tp} mh={mh} | src={d["src"]} '
              f'n_full={n_full:,} split={split:,}', flush=True)

    long_sig, short_sig = signals_for(df['close'].values, int(cand['per']),
                                      float(cand['hi']), int(cand['D']))
    trades = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                                max_hold=mh, allow_overlap=False)
    if trades is None or len(trades) == 0:
        print('  معامله‌ای تولید نشد.', flush=True)
        return dict(tf=tf, verdict_engine=None, selection='no_trades_full')
    if verbose:
        pnl = trades['pnl_pip'].values
        print(f'  کلِ داده: n={len(trades):,} WR={100 * (pnl > 0).mean():.2f}% '
              f'exp={pnl.mean():+.2f}pip', flush=True)

    null = build_null(df, asset, long_sig, short_sig, sl, tp, mh,
                      k_perm=k_perm, verbose=verbose)

    r = rqs2.compute_rqs2(trades, asset, sl_pip=sl, tp_pip=tp,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split,
                          close=df['close'].values)

    res = dict(tf=tf, asset=asset, src=d['src'], n_full=n_full,
               split_bar=split, candidate=cand, selection=why,
               sl_pip=sl, tp_pip=tp, max_hold=mh,
               n_trades=int(len(trades)), null=null,
               n_trials=N_TRIALS, k_perm=k_perm,
               rqs2=r, elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'adj_{tf}.json'), 'w',
              encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=str)

    v = r.get('verdict'); sc = r.get('rqs2_score')
    m = r.get('metrics') or {}
    print(f'\n  ⚖️ حکمِ موتور: {v} · score={sc} · '
          f'skill_p_perm={m.get("skill_p_perm")} · z={m.get("skill_z")}',
          flush=True)
    gates = r.get('gates') or {}
    for gk in sorted(gates):
        print(f'    {gk}: {gates[gk]}', flush=True)
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', default='H3')
    ap.add_argument('--kperm', type=int, default=K_PERM)
    a = ap.parse_args()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            adjudicate(tf, k_perm=a.kperm)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f'!! {tf}: {type(e).__name__}: {e}', flush=True)
    print('\n[adjudication done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
