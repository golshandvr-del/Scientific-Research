# -*- coding: utf-8 -*-
"""
s684_kalman_explore.py — اکتشافِ S684 فقط روی **نیمهٔ اول** (مسیرِ C)
================================================================================
پیش‌ثبت: results/S684_PREREG_KALMAN_INNOVATION_SHOCK.md (کامیت 521dc66 — قبل از اجرا).

سیگنال: فیلترِ کالمنِ روندِ خطیِ محلی؛ نوآوریِ استانداردشده |z_t| ≥ k و
sign(v_t) == sign(slope_pred) ⇒ ورود در جهتِ نوآوری.
گریدِ قفل: k∈{2.058,2.618} × q∈{0.001,0.01} × rr∈{1,1.5,2} = ۱۲ سلول.

غربالِ اصلاح‌شده (درسِ S683): لیفت نسبت به نالِ غیرشرطیِ ارزانِ نیمهٔ اول
(۲۰k بارِ تصادفی per سمت/RR با همان هندسه)، نه be_wr.
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

from engine import scalp_engine as se                    # noqa: E402
from tools import s434_fast_data as fd                   # noqa: E402

OUT_DIR = os.path.join(ROOT, 'results', '_s684_explore')

KS = (2.058, 2.618)
QS = (0.001, 0.01)
RRS = (1.0, 1.5, 2.0)
WARM = 400
R_ALPHA = 1.0 / 89
N_UNCOND = 20000
SEED = 20260828

MAX_HOLD = {'M1': 34, 'M3': 34, 'M4': 34, 'M5': 34, 'M6': 21, 'M10': 21,
            'M12': 21, 'M15': 21, 'M20': 21, 'M30': 21, 'H1': 13, 'H2': 13,
            'H3': 13, 'H6': 13, 'H8': 13, 'H12': 13, 'D1': 8, 'W1': 8,
            'MN1': 5}


def atr_wilder(h, l, c, per: int) -> np.ndarray:
    n = len(c)
    tr = np.empty(n)
    tr[0] = h[0] - l[0]
    pc = c[:-1]
    tr[1:] = np.maximum(h[1:] - l[1:],
                        np.maximum(np.abs(h[1:] - pc), np.abs(l[1:] - pc)))
    out = np.empty(n)
    out[0] = tr[0]
    a = 1.0 / per
    for i in range(1, n):
        out[i] = out[i - 1] + a * (tr[i] - out[i - 1])
    return out


def kalman_llt(c: np.ndarray, q: float, warm: int = WARM,
               r_alpha: float = R_ALPHA):
    """کالمنِ روندِ خطیِ محلی — علّی. برمی‌گرداند (z_innov, slope_pred).

    حالت x=[level, slope]; F=[[1,1],[0,1]]; H=[1,0].
    R_t = EWMA(v²) با α=r_alpha (فقط گذشته؛ به‌روزرسانی *بعد* از محاسبهٔ z_t).
    Q_t = diag(0, q·R_t).
    """
    n = len(c)
    z = np.zeros(n)
    sp = np.zeros(n)
    if n < warm + 2:
        return z, sp
    d0 = np.diff(c[:warm])
    R = float(np.var(d0)) if np.var(d0) > 0 else 1e-6
    # مقدارِ اولیهٔ حالت
    lvl = c[warm - 1]
    slp = float(np.mean(d0[-34:]))
    P00, P01, P11 = R, 0.0, R * 0.1
    for t in range(warm, n):
        # پیش‌بینی
        lp = lvl + slp
        sp_t = slp
        # P_pred = F P F' + Q
        p00 = P00 + 2 * P01 + P11
        p01 = P01 + P11
        p11 = P11 + q * R
        S = p00 + R
        v = c[t] - lp
        z[t] = v / np.sqrt(S) if S > 0 else 0.0
        sp[t] = sp_t
        # به‌روزرسانی
        k0 = p00 / S
        k1 = p01 / S
        lvl = lp + k0 * v
        slp = sp_t + k1 * v
        P00 = (1 - k0) * p00
        P01 = (1 - k0) * p01
        P11 = p11 - k1 * p01
        # R تطبیقی (بعد از استفاده)
        R = R + r_alpha * (v * v - R)
        if R < 1e-12:
            R = 1e-12
    return z, sp


def uncond_wr(df, asset, sl, tp, mh, rng, n_pick=N_UNCOND, warm=WARM):
    """نالِ غیرشرطیِ ارزان: WR ورودِ تصادفی per سمت با همان هندسه."""
    n = len(df)
    valid = np.arange(warm, n - mh - 2)
    k = min(n_pick, len(valid))
    idx = rng.choice(valid, size=k, replace=False)
    sig = np.zeros(n, bool)
    sig[idx] = True
    z0 = np.zeros(n, bool)
    out = {}
    for side in ('long', 'short'):
        if side == 'long':
            tr = se.simulate_trades(df, sig, z0, sl, tp, asset, max_hold=mh,
                                    allow_overlap=True)
        else:
            tr = se.simulate_trades(df, z0, sig, sl, tp, asset, max_hold=mh,
                                    allow_overlap=True)
        pnl = tr['pnl_pip'].values
        out[side] = dict(wr=round(100 * float((pnl > 0).mean()), 2),
                         exp=round(float(pnl.mean()), 3), n=int(len(pnl)))
    return out


def explore(tf: str, asset: str = 'XAUUSD') -> dict:
    t0 = time.time()
    d = fd.load_fast(asset, tf)
    src = d['src']
    df_full = fd.as_dataframe(d)
    del d
    gc.collect()
    n_full = len(df_full)
    n_half = n_full // 2
    df = df_full.iloc[:n_half].reset_index(drop=True)
    del df_full
    gc.collect()

    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    pip = se.ASSETS[asset]['pip']
    cost = se.ASSETS[asset]['spread_pip'] + 2 * se.ASSETS[asset]['slip_pip']
    a34 = atr_wilder(h, l, c, 34)
    sl = round(float(np.median(a34[100:]) / pip) * 1.618, 1)
    mh = MAX_HOLD[tf]
    rng = np.random.default_rng(SEED)

    if n_half < WARM + mh + 50:
        res = dict(asset=asset, tf=tf, src=src, n_full=n_full, n_half=n_half,
                   sl_pip=sl, max_hold=mh, degenerate='n_half<warm', cells=[])
        os.makedirs(OUT_DIR, exist_ok=True)
        json.dump(res, open(os.path.join(OUT_DIR, f'explore_{tf}.json'), 'w',
                            encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'[{tf}] degenerate', flush=True)
        return res

    # نالِ غیرشرطیِ ارزان per RR (یک بار per کارت)
    unc = {}
    for rr in RRS:
        tp = round(rr * sl, 1)
        unc[str(rr)] = uncond_wr(df, asset, sl, tp, mh, rng)
    print(f'[{tf}] uncond: ' + ' | '.join(
        f"rr{rr}: L{unc[str(rr)]['long']['wr']} S{unc[str(rr)]['short']['wr']}"
        for rr in RRS), flush=True)

    cells = []
    gate_stats = {}
    for q in QS:
        z, sp = kalman_llt(c, q)
        for k in KS:
            shock = np.abs(z) >= k
            aligned = shock & (np.sign(z) == np.sign(sp)) & (sp != 0)
            n_shock = int(shock[WARM:].sum())
            n_al = int(aligned[WARM:].sum())
            gate_stats[f'q{q}_k{k}'] = dict(n_shock=n_shock, n_aligned=n_al,
                                            pass_rate=round(n_al / n_shock, 3)
                                            if n_shock else None)
            long_sig = aligned & (z > 0)
            short_sig = aligned & (z < 0)
            long_sig[:WARM] = False
            short_sig[:WARM] = False
            nsig = int(long_sig.sum() + short_sig.sum())
            for rr in RRS:
                tp = round(rr * sl, 1)
                if nsig == 0:
                    cells.append(dict(k=k, q=q, rr=rr, n=0, skipped='no_sig'))
                    continue
                tr = se.simulate_trades(df, long_sig, short_sig, sl, tp,
                                        asset, max_hold=mh,
                                        allow_overlap=False)
                if tr is None or len(tr) == 0:
                    cells.append(dict(k=k, q=q, rr=rr, n=0,
                                      skipped='no_trades'))
                    continue
                pnl = tr['pnl_pip'].values
                dirv = tr['direction'].values
                isl = (dirv == 'long') if dirv.dtype.kind in 'OU' else (dirv > 0)
                n = len(pnl)
                nl = int(isl.sum())
                ns = n - nl
                wr = 100.0 * float((pnl > 0).mean())
                u = unc[str(rr)]
                ref = (nl * u['long']['wr'] + ns * u['short']['wr']) / n
                lift = wr - ref
                zsc = lift / max(1e-9, 100.0 * np.sqrt(ref / 100 * (1 - ref / 100) / n))
                be = 100.0 * (sl + cost) / (sl + tp)
                cells.append(dict(k=k, q=q, rr=rr, n=n, n_long=nl, n_sig=nsig,
                                  wr=round(wr, 2), uncond_ref=round(ref, 2),
                                  lift_uncond=round(lift, 2),
                                  be_wr=round(be, 2),
                                  lift_be=round(wr - be, 2),
                                  wr_long=round(100 * float((pnl[isl] > 0).mean()), 2) if nl else None,
                                  wr_short=round(100 * float((pnl[~isl] > 0).mean()), 2) if ns else None,
                                  exp_pip=round(float(pnl.mean()), 3),
                                  z_screen=round(float(zsc), 2)))
    res = dict(asset=asset, tf=tf, src=src, n_full=n_full, n_half=n_half,
               sl_pip=sl, atr_per=34, sl_mult=1.618, max_hold=mh,
               cost_pip=cost, warm=WARM, r_alpha=R_ALPHA, uncond=unc,
               n_uncond=N_UNCOND, gate_stats=gate_stats,
               grid_cells=len(KS) * len(QS) * len(RRS),
               cells=cells, elapsed_s=round(time.time() - t0, 1))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f'explore_{tf}.json'), 'w',
              encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    best = max([x for x in cells if 'skipped' not in x],
               key=lambda x: x['z_screen'], default=None)
    print(f'[{tf}] done {res["elapsed_s"]}s sl={sl} gates={gate_stats} '
          f'best={best}', flush=True)
    del df
    gc.collect()
    return res


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--tfs', required=True)
    a = ap.parse_args()
    for tf in [t.strip() for t in a.tfs.split(',') if t.strip()]:
        try:
            explore(tf)
        except Exception as e:  # noqa: BLE001
            import traceback; traceback.print_exc()
            print(f'!! {tf}: {type(e).__name__}: {e}', flush=True)
        gc.collect()
    print('[explore batch done]', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
