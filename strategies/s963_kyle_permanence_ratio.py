# -*- coding: utf-8 -*-
"""
S963 — «نسبتِ پایداریِ اثر کایل» (Kyle Permanence Ratio) · XAUUSD
================================================================================
پیش‌ثبت: `results/S963_PREREG_KYLE_PERMANENCE_RATIO.md`
(commit b34d52df — پیش از اجرای هر آزمونی، مسیر C).

فرضیه (Kyle 1985 + Parkinson 1980): اثرِ قیمتیِ معامله‌ی مطلع دائمی است؛
نویز گذرا. PR = V_cc/V_parkinson روی پنجره‌ی p بالا برود ⇒ رژیمِ اثرِ
دائمی ⇒ driftِ جاری اطلاعاتی است (follow) یا overshoot برمی‌گردد (against).

سنجه (کندل i، پنجره p — causal، ورود در openِ i+1):
  r = ln(c/c₋₁) ، hl = ln(h/l)
  V_cc = Σr² ، V_pk = Σhl²/(4·ln2) ، PR = V_cc/max(V_pk,ε)
  رویداد: PR ≥ θ و drift=sign(c_i−c_{i−p}) ≠ 0
  gate=state: هر کندلِ داخلِ رژیم ؛ gate=fresh: فقط کندلِ ورود به رژیم

خانواده‌ی منجمد: p∈{21,55,89,144} × θ∈{1.272,1.618} × gate∈{state,fresh} ×
mode∈{follow,against} × geom∈{(1.0,1.618),(1.272,2.058)} = ۶۴ عضو/کارت.
max_hold=3p. n_trials = 64×19 = **1216**. مسیر C.

مدل صفر: K=500، سه تله‌ی s434، perm_k=تعدادِ جایگشت‌ها (درس S960)،
برآوردگرِ chunked بی‌قید (CH=25k, UNC_CAP=250k — S961). SEED=963.
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

OUT = 'results/_scan_S963'
os.makedirs(OUT, exist_ok=True)

SEED = 963
K_PERM = 500
ATR_WIN = 21
COST_PIP = 3.3

# ── خانواده‌ی قفل‌شده (پیش‌ثبت §۳) — ۴×۲×۲×۲×۲ = ۶۴ عضو ──────────────
P_LIST = [21, 55, 89, 144]
TH_LIST = [1.272, 1.618]
GATES = ['state', 'fresh']
MODES = ['follow', 'against']
GEOMS = [(1.0, 1.618), (1.272, 2.058)]
N_TRIALS = 1216

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']

FOUR_LN2 = 4.0 * np.log(2.0)


def _views_df(d, end=None):
    """DataFrame با ارجاع (copy=False) — ضدِ OOM (درسِ S960)."""
    sl = slice(None, end)
    return pd.DataFrame({'time': d['time'][sl], 'open': d['open'][sl],
                         'high': d['high'][sl], 'low': d['low'][sl],
                         'close': d['close'][sl], 'volume': d['volume'][sl]},
                        copy=False)


def _rollsum(x, w):
    """مجموعِ پنجره‌ایِ w-تاییِ انتهایی تا اندیسِ i — با cumsum (ضدِ OOM).
    حالتِ w >= n پوشش داده شد (درسِ لبه‌ی MN1 از S962)."""
    n = len(x)
    cs = np.concatenate(([0.0], np.cumsum(x)))
    if w >= n:
        return cs[1:].copy()
    out = np.empty(n)
    out[:w - 1] = cs[1:w]
    out[w - 1:] = cs[w:] - cs[:n - w + 1]
    return out


def features(df, p):
    """PR(p)، drift(p)، ATR21 — همگی causal تا closeِ i."""
    h = np.asarray(df['high'].values, dtype=np.float64)
    l = np.asarray(df['low'].values, dtype=np.float64)
    c = np.asarray(df['close'].values, dtype=np.float64)
    n = len(c)

    r2 = np.zeros(n)
    r2[1:] = np.log(c[1:] / c[:-1]) ** 2
    v_cc = _rollsum(r2, p)
    del r2
    hl2 = (np.log(np.maximum(h, 1e-12) / np.maximum(l, 1e-12)) ** 2) / FOUR_LN2
    v_pk = _rollsum(hl2, p)
    del hl2
    pr = v_cc / np.maximum(v_pk, 1e-18)
    del v_cc, v_pk

    drift = np.zeros(n)
    drift[p:] = np.sign(c[p:] - c[:-p])

    tr_arr = np.zeros(n)
    tr_arr[1:] = np.maximum.reduce([h[1:] - l[1:],
                                    np.abs(h[1:] - c[:-1]),
                                    np.abs(l[1:] - c[:-1])])
    atr = _rollsum(tr_arr, ATR_WIN) / ATR_WIN
    del tr_arr
    return pr, drift, atr


def member_signals(pr, drift, th, gate, mode, warm):
    n = len(pr)
    valid = np.arange(n) >= warm
    inreg = pr >= th
    if gate == 'fresh':
        ev = np.zeros(n, bool)
        ev[1:] = inreg[1:] & ~inreg[:-1]          # فقط کندلِ ورود به رژیم
    else:
        ev = inreg.copy()
    ev = ev & valid & (drift != 0)
    up = ev & (drift > 0)
    dn = ev & (drift < 0)
    if mode == 'follow':
        return up, dn
    return dn, up


def run_member(df, pr, drift, atr, th, gate, mode, k_sl, k_tp, p, asset, pip):
    warm = max(250, p + 1)
    ls, ss = member_signals(pr, drift, th, gate, mode, warm)
    sl_arr = np.maximum(k_sl * atr / pip, 1e-9)
    tp_arr = np.maximum(k_tp * atr / pip, 1e-9)
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset,
                            max_hold=3 * p, allow_overlap=False)
    return tr, ls, ss, sl_arr, tp_arr


def discovery_stat(tr, rr):
    """آمارِ کشف (نیمه‌ی اول): lift_robust·√n؛ غربال n>=30 و expectancy>0."""
    if tr is None or len(tr) < 30:
        return None
    n = len(tr)
    exp_pip = float(tr['pnl_pip'].mean())
    if exp_pip <= 0:
        return None
    wr = float((tr['outcome'] == 'win').mean())
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * rr
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
    """مدلِ صفر — سه تله‌ی s434 بسته؛ perm_k = تعدادِ جایگشت‌ها (درسِ S960)؛
    برآوردگرِ chunked/capped بی‌قید (درس‌های ۳ و ۴ S961، bit-exact)."""
    n = len(df)
    sig_n = int((ls | ss).sum())
    if sig_n < 30:
        return None
    warmup = max(250, max(P_LIST) + 2)
    valid = np.zeros(n, bool)
    valid[warmup:n - mh - 1] = True
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


def discover_one_p(tf, p):
    """کشفِ یک p در پردازه‌ی جدا (درسِ سومِ S961). خروجی: partial JSON."""
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    t_arr = np.asarray(d['time'], dtype=np.int64)
    t_mid = (int(t_arr[0]) + int(t_arr[-1])) // 2
    split = int(np.searchsorted(t_arr, t_mid))
    df1 = _views_df(d, end=split)
    pip = se.ASSETS['XAUUSD']['pip']
    pr1, dr1, atr1 = features(df1, p)
    best = None
    for th in TH_LIST:
        for gate in GATES:
            for mode in MODES:
                for (k_sl, k_tp) in GEOMS:
                    tr, *_ = run_member(df1, pr1, dr1, atr1,
                                        th, gate, mode, k_sl, k_tp,
                                        p, 'XAUUSD', pip)
                    st = discovery_stat(tr, k_tp / k_sl)
                    del tr
                    gc.collect()
                    if st is None:
                        continue
                    if best is None or st['stat'] > best['stat']:
                        best = dict(p=p, th=th, gate=gate, mode=mode,
                                    k_sl=k_sl, k_tp=k_tp, **st)
    out = dict(tf=tf, p=p, split_bar=split, best=best)
    json.dump(out, open(f'{OUT}/partial_{tf}_p{p}.json', 'w'),
              ensure_ascii=False, indent=1)
    print(f'[{tf} p={p}] best={None if best is None else round(best["stat"],1)}',
          flush=True)


def adjudicate_from_partials(tf):
    """داوریِ نهایی از partialها (holdout یک بار — پروتکلِ مسیر C)."""
    t0 = time.time()
    bests = []
    split = None
    for p in P_LIST:
        fp = f'{OUT}/partial_{tf}_p{p}.json'
        if not os.path.exists(fp):
            raise RuntimeError(f'partial missing: {fp}')
        rec = json.load(open(fp))
        split = rec['split_bar']
        if rec['best'] is not None:
            bests.append(rec['best'])
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    src = d['src']
    n_bars = len(d['close'])
    if not bests:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
                   verdict='NO-SURVIVOR',
                   note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec
    best = max(bests, key=lambda b: b['stat'])
    return _final_judge(tf, d, src, n_bars, split, best, t0)


def judge_tf(tf):
    t0 = time.time()
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    df = _views_df(d)
    src = d['src']
    asset = 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    n_bars = len(df)
    t_arr = np.asarray(d['time'], dtype=np.int64)
    t_mid = (int(t_arr[0]) + int(t_arr[-1])) // 2
    split = int(np.searchsorted(t_arr, t_mid))

    # ---------- کشف: فقط نیمه‌ی اولِ زمان ----------
    df1 = _views_df(d, end=split)
    best = None
    for p in P_LIST:
        pr1, dr1, atr1 = features(df1, p)
        for th in TH_LIST:
            for gate in GATES:
                for mode in MODES:
                    for (k_sl, k_tp) in GEOMS:
                        tr, *_ = run_member(df1, pr1, dr1, atr1,
                                            th, gate, mode, k_sl, k_tp,
                                            p, asset, pip)
                        st = discovery_stat(tr, k_tp / k_sl)
                        del tr
                        if st is None:
                            continue
                        if best is None or st['stat'] > best['stat']:
                            best = dict(p=p, th=th, gate=gate, mode=mode,
                                        k_sl=k_sl, k_tp=k_tp, **st)
        del pr1, dr1, atr1
        gc.collect()
    if best is None:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
                   verdict='NO-SURVIVOR',
                   note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    return _final_judge(tf, d, src, n_bars, split, best, t0)


def _final_judge(tf, d, src, n_bars, split, best, t0):
    """داوریِ یک‌باره روی کلِ داده (holdout یک بار لمس می‌شود)."""
    asset = 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    df = _views_df(d)
    p, th, gate = best['p'], best['th'], best['gate']
    mode, k_sl, k_tp = best['mode'], best['k_sl'], best['k_tp']
    mh = 3 * p
    pr, drift, atr = features(df, p)
    tr, ls, ss, sl_arr, tp_arr = run_member(df, pr, drift, atr, th, gate,
                                            mode, k_sl, k_tp, p, asset, pip)
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best,
                   n_bars=n_bars, split_bar=split)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (k_tp / k_sl)
    null = build_null(df, ls, ss, sl_arr, tp_arr, mh, asset)
    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split,
                            close=df['close'].values)
    m = res['metrics']
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               member=dict(p=p, th=th, gate=gate, mode=mode, k_sl=k_sl,
                           k_tp=k_tp, max_hold=mh, sl_pip_med=round(sl_med, 2),
                           tp_pip_med=round(tp_med, 2)),
               discovery={k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in best.items()},
               null_meta=(null or {}).get('_meta'),
               verdict=res['verdict'], score=res['rqs2_score'],
               gates={g: (None if v is None else bool(v))
                      for g, v in res['gates'].items()},
               n=int(m.get('n_trades', 0)), wr=m.get('win_rate'),
               pf=m.get('profit_factor'), net=m.get('net_profit'),
               lift=m.get('skill_lift_pp'), z=m.get('skill_z'),
               p_perm=m.get('skill_p_perm'),
               notes=res['notes'][:8], sec=round(time.time() - t0, 1))
    json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1,
              default=str)
    return rec


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == 'discover':
        discover_one_p(sys.argv[2], int(sys.argv[3]))
        return
    if len(sys.argv) >= 2 and sys.argv[1] == 'adjudicate':
        tf = sys.argv[2]
        rec = adjudicate_from_partials(tf)
        print(f"[{tf}] verdict={rec.get('verdict')} score={rec.get('score')} "
              f"n={rec.get('n')} wr={rec.get('wr')} lift={rec.get('lift')} "
              f"z={rec.get('z')} ({rec.get('sec')}s)", flush=True)
        return
    only = sys.argv[1:] if len(sys.argv) > 1 else TFS
    for tf in only:
        try:
            rec = judge_tf(tf)
            print(f"[{tf}] verdict={rec.get('verdict')} score={rec.get('score')} "
                  f"n={rec.get('n')} wr={rec.get('wr')} lift={rec.get('lift')} "
                  f"z={rec.get('z')} ({rec.get('sec')}s)", flush=True)
        except Exception as e:                                     # noqa: BLE001
            print(f"[{tf}] ERROR {e!r}", flush=True)
            json.dump(dict(tf=tf, error=repr(e)),
                      open(f'{OUT}/{tf}.json', 'w'))
        gc.collect()


if __name__ == '__main__':
    main()
