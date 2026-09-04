# -*- coding: utf-8 -*-
"""
S966 — «ماندگاری کایل × هم‌راستایی درفت» (Kyle Permanence, Drift-Aligned)
================================================================================
پیش‌ثبت: `results/S966_PREREG_KYLE_PERMANENCE_DRIFT_ALIGNED.md`
(commit 61cbbd11 — پیش از اجرای هر آزمونی).

پایهٔ منجمد = فینالیست S965 (جست‌وجو نمی‌شود):
  شوک: high−low ≥ 2.618×ATR21[i−1]  و  ρ=|body|/range ≥ 0.618
  جهت follow با body؛ ورود open بعد؛ SL=1.272×ATR، TP=2.058×ATR؛ hold=16.

اهرم (تنها متغیر): گیتِ درفتِ علّی K-کندلی روی close (playbook S604):
  aligned: long فقط اگر close[i−1] > close[i−1−K]؛ short آینه‌ای.
  counter: بازوی قرینه (کنترل ابطال P2).
خانواده: gate{aligned,counter} × K{90,180,270} = ۶ عضو/کارت. کارت‌ها: H8، H6.
n_trials=620 (تجمعی صادقانه: ۶۰۸ از S965 + ۱۲ جدید). مسیر C. SEED=966.

P1: بهترین aligned روی نیمهٔ کشف باید lift بالاتر از پایهٔ بی‌گیت بدهد
(پایه در همان نیمه محاسبه و فقط گزارش می‌شود).

مدل صفر: عین S965 — K=500، سه تلهٔ s434، perm_k=تعداد جایگشت‌ها،
chunked uncond (CH=25k, UNC_CAP=250k).
"""
import sys
import os
import gc
import json
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2                        # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_scan_S966'
os.makedirs(OUT, exist_ok=True)

SEED = 966
K_PERM = 500
ATR_WIN = 21
COST_PIP = 3.3
WARM = 250
MAX_HOLD = 16

# ── پایهٔ منجمد S965 (فینالیست — جست‌وجو نمی‌شود) ─────────────────────
TH = 2.618
RHO = 0.618
K_SL, K_TP = 1.272, 2.058

# ── خانوادهٔ قفل‌شده (پیش‌ثبت §۳) — ۲×۳ = ۶ عضو ────────────────────────
GATES = ['aligned', 'counter']
K_LIST = [90, 180, 270]
N_TRIALS = 620

TFS = ['H8', 'H6']


def _views_df(d, end=None):
    sl = slice(None, end)
    return pd.DataFrame({'time': d['time'][sl], 'open': d['open'][sl],
                         'high': d['high'][sl], 'low': d['low'][sl],
                         'close': d['close'][sl], 'volume': d['volume'][sl]},
                        copy=False)


def _rollsum(x, w):
    n = len(x)
    cs = np.concatenate(([0.0], np.cumsum(x)))
    if w >= n:
        return cs[1:].copy()
    out = np.empty(n)
    out[:w - 1] = cs[1:w]
    out[w - 1:] = cs[w:] - cs[:n - w + 1]
    return out


def features(df):
    """رویداد پایهٔ منجمد S965 + درفت علّی. خروجی: ev_up, ev_dn, atr_prev, c."""
    o = np.asarray(df['open'].values, dtype=np.float64)
    h = np.asarray(df['high'].values, dtype=np.float64)
    l = np.asarray(df['low'].values, dtype=np.float64)
    c = np.asarray(df['close'].values, dtype=np.float64)
    n = len(c)

    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr = _rollsum(tr_arr, ATR_WIN) / ATR_WIN
    del tr_arr
    atr_prev = np.empty(n)
    atr_prev[0] = atr[0]
    atr_prev[1:] = atr[:-1]
    del atr

    rng = h - l
    shock = (rng >= TH * atr_prev) & (rng > 0) & (atr_prev > 1e-12)
    body = c - o
    rho = np.divide(np.abs(body), rng, out=np.zeros_like(rng), where=rng > 0)
    body_sgn = np.sign(body)

    idx = np.arange(n)
    ev = shock & (idx >= WARM) & (body_sgn != 0) & (rho >= RHO)
    ev_up = ev & (body_sgn > 0)
    ev_dn = ev & (body_sgn < 0)
    return ev_up, ev_dn, atr_prev, c


def drift_up(c, K):
    """درفت علّی: close[i−1] > close[i−1−K] (بدون لمس کندل i)."""
    n = len(c)
    du = np.zeros(n, bool)
    if n > K + 1:
        du[K + 1:] = c[K:-1] > c[:-(K + 1)]
    return du


def member_signals(ev_up, ev_dn, c, K, gate):
    du = drift_up(c, K)
    dn_drift = np.zeros_like(du)
    n = len(c)
    if n > K + 1:
        dn_drift[K + 1:] = c[K:-1] < c[:-(K + 1)]
    if gate == 'aligned':
        return ev_up & du, ev_dn & dn_drift
    return ev_up & dn_drift, ev_dn & du


def _run(df, ls, ss, atr_prev, asset, pip):
    sl_arr = np.maximum(K_SL * atr_prev / pip, 1e-9)
    tp_arr = np.maximum(K_TP * atr_prev / pip, 1e-9)
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset,
                            max_hold=MAX_HOLD, allow_overlap=False)
    return tr, sl_arr, tp_arr


def discovery_stat(tr):
    if tr is None or len(tr) < 30:
        return None
    n = len(tr)
    exp_pip = float(tr['pnl_pip'].mean())
    if exp_pip <= 0:
        return None
    wr = float((tr['outcome'] == 'win').mean())
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (K_TP / K_SL)
    be_rob = (sl_med + 2 * COST_PIP) / (sl_med + tp_med)
    lift = (wr - be_rob) * 100.0
    return dict(stat=lift * np.sqrt(n), n=n, wr=wr * 100,
                be_rob=be_rob * 100, lift=lift, exp_pip=exp_pip,
                sl_med=sl_med, tp_med=tp_med)


def _wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return float((tr['outcome'] == 'win').mean() * 100.0)


def build_null(df, ls, ss, sl_arr, tp_arr, mh, asset, seed=SEED, K=K_PERM):
    n = len(df)
    sig_n = int((ls | ss).sum())
    if sig_n < 30:
        return None
    valid = np.zeros(n, bool)
    valid[WARM:n - mh - 1] = True
    z = np.zeros(n, bool)

    UNC_CAP = 250_000
    rng = np.random.default_rng(seed)
    vidx_all = np.flatnonzero(valid)
    if len(vidx_all) == 0:
        return None
    if len(vidx_all) > UNC_CAP:
        unc_idx = np.sort(rng.choice(vidx_all, size=UNC_CAP, replace=False))
    else:
        unc_idx = vidx_all
    unc_wins = 0
    unc_n = 0
    CH = 25_000
    for s0 in range(0, len(unc_idx), CH):
        pm = np.zeros(n, bool)
        pm[unc_idx[s0:s0 + CH]] = True
        tr_c = se.simulate_trades(df, pm, z, sl_arr, tp_arr, asset,
                                  max_hold=mh, allow_overlap=True)
        if tr_c is not None and len(tr_c):
            unc_wins += int((tr_c['outcome'] == 'win').sum())
            unc_n += int(len(tr_c))
        del tr_c, pm
        gc.collect()
    wr_unc = (unc_wins / unc_n * 100.0) if unc_n else None
    del unc_idx

    vidx = vidx_all
    k = min(sig_n, len(vidx))
    perm_wrs = []
    for _ in range(K):
        pick = rng.choice(vidx, size=k, replace=False)
        pm = np.zeros(n, bool)
        pm[pick] = True
        tr_p = se.simulate_trades(df, pm, z, sl_arr, tp_arr, asset,
                                  max_hold=mh, allow_overlap=False)
        w = _wr_of(tr_p)
        del tr_p, pm
        if w is not None:
            perm_wrs.append(w)
    pa = np.array(perm_wrs, float)
    side = dict(uncond_wr=wr_unc,
                perm_mean=float(pa.mean()) if pa.size else None,
                perm_sd=float(pa.std(ddof=1)) if pa.size > 1 else None,
                perm_max=float(pa.max()) if pa.size else None,
                perm_k=int(pa.size))
    return {'long': dict(side), 'short': dict(side),
            '_meta': {'n_perm': int(pa.size), 'draw_size': int(k),
                      'uncond_n': unc_n}}


def judge_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    src = d['src']
    asset = 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    n_bars = len(d['close'])
    t_arr = np.asarray(d['time'], dtype=np.int64)
    t_mid = (int(t_arr[0]) + int(t_arr[-1])) // 2
    split = int(np.searchsorted(t_arr, t_mid))

    # ---------- کشف: فقط نیمه‌ی اولِ زمان ----------
    df1 = _views_df(d, end=split)
    ev_up, ev_dn, atr_prev, c1 = features(df1)

    # پایهٔ بی‌گیت (P1 — فقط گزارش)
    tr_b, _, _ = _run(df1, ev_up, ev_dn, atr_prev, asset, pip)
    st_b = discovery_stat(tr_b)
    base = None if st_b is None else dict(n=st_b['n'], wr=round(st_b['wr'], 2),
                                          lift=round(st_b['lift'], 3))
    del tr_b

    best = None
    for gate in GATES:
        for K in K_LIST:
            ls, ss = member_signals(ev_up, ev_dn, c1, K, gate)
            tr, _, _ = _run(df1, ls, ss, atr_prev, asset, pip)
            st = discovery_stat(tr)
            del tr, ls, ss
            gc.collect()
            if st is None:
                continue
            if best is None or st['stat'] > best['stat']:
                best = dict(gate=gate, K=K, **st)
    del ev_up, ev_dn, atr_prev, c1, df1
    gc.collect()

    if best is None:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
                   verdict='NO-SURVIVOR', p1_baseline=base,
                   note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    # P1: بهترین aligned باید از پایه بهتر باشد (داوری در MD؛ اینجا ثبت)
    p1_pass = None
    if base is not None and best['gate'] == 'aligned':
        p1_pass = bool(best['lift'] > base['lift'])

    # ---------- داوری یک‌باره روی کل داده ----------
    df = _views_df(d)
    ev_up, ev_dn, atr_prev, c = features(df)
    ls, ss = member_signals(ev_up, ev_dn, c, best['K'], best['gate'])
    tr, sl_arr, tp_arr = _run(df, ls, ss, atr_prev, asset, pip)
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best,
                   n_bars=n_bars, split_bar=split)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (K_TP / K_SL)
    null = build_null(df, ls, ss, sl_arr, tp_arr, MAX_HOLD, asset)
    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split,
                            close=df['close'].values)
    mt = res['metrics']
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               member=dict(gate=best['gate'], K=best['K'], th=TH, rho=RHO,
                           k_sl=K_SL, k_tp=K_TP, max_hold=MAX_HOLD,
                           sl_pip_med=round(sl_med, 2),
                           tp_pip_med=round(tp_med, 2)),
               discovery={k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in best.items()},
               p1_baseline=base, p1_pass=p1_pass,
               null_meta=(null or {}).get('_meta'),
               verdict=res['verdict'], score=res['rqs2_score'],
               gates={g: (None if v is None else bool(v))
                      for g, v in res['gates'].items()},
               n=int(mt.get('n_trades', 0)), wr=mt.get('win_rate'),
               pf=mt.get('profit_factor'), net=mt.get('net_profit'),
               lift=mt.get('skill_lift_pp'), z=mt.get('skill_z'),
               p_perm=mt.get('skill_p_perm'),
               notes=res['notes'][:8], sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1,
              default=str)
    return rec


def main():
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        try:
            rec = judge_tf(tf)
            print(f"[{tf}] verdict={rec.get('verdict')} score={rec.get('score')} "
                  f"n={rec.get('n')} wr={rec.get('wr')} lift={rec.get('lift')} "
                  f"z={rec.get('z')} p1={rec.get('p1_pass')} "
                  f"({rec.get('sec')}s)", flush=True)
        except Exception as e:                                     # noqa: BLE001
            print(f"[{tf}] ERROR {e!r}", flush=True)
            json.dump(dict(tf=tf, error=repr(e)),
                      open(f'{OUT}/{tf}.json', 'w'))
        gc.collect()


if __name__ == '__main__':
    main()
