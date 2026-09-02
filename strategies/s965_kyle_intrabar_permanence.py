# -*- coding: utf-8 -*-
"""
S965 — «ماندگاریِ درون-کندلیِ اثر قیمتی» (Kyle Intra-Bar Impact Permanence)
================================================================================
پیش‌ثبت: `results/S965_PREREG_KYLE_INTRABAR_PERMANENCE.md`
(commit 5886028c — پیش از اجرای هر آزمونی، مسیر C).

فرضیه (Kyle 1985): جریانِ مطلع اثرِ قیمتیِ دائمی می‌گذارد (کندلِ شوک با
retention بالا = ماروبوزو-گونه) ⇒ ادامه؛ جریانِ نویز اثرِ گذرا دارد
(retention پایین = سایه‌های بلند) ⇒ بازوی قرینه.

سیگنال (کندل i — causal، ورود در openِ i+1):
  rng_i = high_i − low_i ؛ شوک: rng_i ≥ θ×ATR21_{i−1}
  ρ_i = |close_i − open_i| / rng_i
  بازو hi: ρ≥R ؛ بازو lo: ρ≤1−R ؛ جهتِ پایه sign(close−open)
  mode=follow همان جهت، mode=against خلاف.

خانواده: θ∈{1.618,2.618} × arm∈{hi,lo} × R∈{0.618,0.75} ×
mode∈{follow,against} × geom∈{(1.0,1.618),(1.272,2.058)} = ۳۲ عضو/کارت.
max_hold=16 (منجمد). n_trials=608. مسیر C. SEED=965.

P1 (ضدِ سوزاندنِ توان — درس S603/S964): پایه‌ی θ-only (شوک بدون شرط ρ،
follow، بهترین geom) per θ محاسبه و «فقط گزارش» می‌شود — عضو خانواده نیست.

مدل صفر: K=500، سه تله‌ی s434، perm_k=تعدادِ جایگشت‌ها (درس S960)،
برآوردگرِ chunked بی‌قید (CH=25k, UNC_CAP=250k — S961).
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

OUT = 'results/_scan_S965'
os.makedirs(OUT, exist_ok=True)

SEED = 965
K_PERM = 500
ATR_WIN = 21
COST_PIP = 3.3
WARM = 250
MAX_HOLD = 16                                  # منجمد (پیش‌ثبت §۳)

# ── خانواده‌ی قفل‌شده (پیش‌ثبت §۳) — ۲×۲×۲×۲×۲ = ۳۲ عضو ──────────────
TH_LIST = [1.618, 2.618]
ARMS = ['hi', 'lo']
R_LIST = [0.618, 0.75]
MODES = ['follow', 'against']
GEOMS = [(1.0, 1.618), (1.272, 2.058)]
N_TRIALS = 608

TFS = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20', 'M30',
       'H1', 'H2', 'H3', 'H6', 'H8', 'H12', 'D1', 'W1', 'MN1']


def _views_df(d, end=None):
    """DataFrame با ارجاع (copy=False) — ضدِ OOM (درسِ S960)."""
    sl = slice(None, end)
    return pd.DataFrame({'time': d['time'][sl], 'open': d['open'][sl],
                         'high': d['high'][sl], 'low': d['low'][sl],
                         'close': d['close'][sl], 'volume': d['volume'][sl]},
                        copy=False)


def _rollsum(x, w):
    """مجموعِ پنجره‌ای با cumsum (ضدِ OOM؛ پوششِ لبه‌ی w>=n از S962)."""
    n = len(x)
    cs = np.concatenate(([0.0], np.cumsum(x)))
    if w >= n:
        return cs[1:].copy()
    out = np.empty(n)
    out[:w - 1] = cs[1:w]
    out[w - 1:] = cs[w:] - cs[:n - w + 1]
    return out


def features(df, th):
    """شوکِ رنج نسبت به ATR21_{i−1} (علّی)، ρ retention، جهتِ body، atr_prev.
    خروجی: shock (bool)، rho، body_sgn، atr_prev (برای هندسه)."""
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
    # ATR علّی: مقدارِ تا کندلِ i−1 (شوکِ خودِ i آن را آلوده نکند)
    atr_prev = np.empty(n)
    atr_prev[0] = atr[0]
    atr_prev[1:] = atr[:-1]
    del atr

    rng = h - l
    shock = (rng >= th * atr_prev) & (rng > 0) & (atr_prev > 1e-12)
    body = c - o
    rho = np.divide(np.abs(body), rng, out=np.zeros_like(rng),
                    where=rng > 0)
    body_sgn = np.sign(body)
    return shock, rho, body_sgn, atr_prev


def member_signals(shock, rho, body_sgn, arm, R, mode, warm):
    n = len(shock)
    idx = np.arange(n)
    valid = idx >= warm
    ev = shock & valid & (body_sgn != 0)
    if arm == 'hi':
        ev = ev & (rho >= R)
    else:
        ev = ev & (rho <= 1.0 - R)
    up = ev & (body_sgn > 0)
    dn = ev & (body_sgn < 0)
    if mode == 'follow':
        return up, dn
    return dn, up


def baseline_signals(shock, body_sgn, warm):
    """پایه‌ی P1: شوک بدون شرط ρ، follow."""
    n = len(shock)
    idx = np.arange(n)
    ev = shock & (idx >= warm) & (body_sgn != 0)
    return ev & (body_sgn > 0), ev & (body_sgn < 0)


def _run(df, ls, ss, atr_prev, k_sl, k_tp, asset, pip):
    sl_arr = np.maximum(k_sl * atr_prev / pip, 1e-9)
    tp_arr = np.maximum(k_tp * atr_prev / pip, 1e-9)
    tr = se.simulate_trades(df, ls, ss, sl_arr, tp_arr, asset,
                            max_hold=MAX_HOLD, allow_overlap=False)
    return tr, sl_arr, tp_arr


def run_member(df, shock, rho, body_sgn, atr_prev, arm, R, mode,
               k_sl, k_tp, asset, pip):
    ls, ss = member_signals(shock, rho, body_sgn, arm, R, mode, WARM)
    tr, sl_arr, tp_arr = _run(df, ls, ss, atr_prev, k_sl, k_tp, asset, pip)
    return tr, ls, ss, sl_arr, tp_arr


def discovery_stat(tr, rr):
    """آمارِ کشف: lift_robust·√n؛ غربال n>=30 و expectancy>0."""
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


def baseline_stat(df, shock, body_sgn, atr_prev, asset, pip):
    """P1: بهترین آمارِ پایه‌ی θ-only روی دو geom (فقط گزارش)."""
    ls, ss = baseline_signals(shock, body_sgn, WARM)
    best = None
    for (k_sl, k_tp) in GEOMS:
        tr, _, _ = _run(df, ls, ss, atr_prev, k_sl, k_tp, asset, pip)
        st = discovery_stat(tr, k_tp / k_sl)
        del tr
        if st is not None and (best is None or st['lift'] > best['lift']):
            best = dict(k_sl=k_sl, k_tp=k_tp,
                        n=st['n'], wr=round(st['wr'], 2),
                        lift=round(st['lift'], 3))
    return best


def _wr_of(tr):
    if tr is None or len(tr) == 0:
        return None
    return float((tr['outcome'] == 'win').mean() * 100.0)


def build_null(df, ls, ss, sl_arr, tp_arr, mh, asset, seed=SEED, K=K_PERM):
    """مدلِ صفر — سه تله‌ی s434؛ perm_k=تعدادِ جایگشت‌ها؛ chunked/capped."""
    n = len(df)
    sig_n = int((ls | ss).sum())
    if sig_n < 30:
        return None
    warmup = WARM
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


def _discover_th(df1, th, asset, pip):
    """کشفِ یک θ روی نیمه‌ی اول: بهترین عضو + پایه‌ی P1."""
    shock, rho, body_sgn, atr_prev = features(df1, th)
    best = None
    for arm in ARMS:
        for R in R_LIST:
            for mode in MODES:
                for (k_sl, k_tp) in GEOMS:
                    tr, *_ = run_member(df1, shock, rho, body_sgn, atr_prev,
                                        arm, R, mode, k_sl, k_tp, asset, pip)
                    st = discovery_stat(tr, k_tp / k_sl)
                    del tr
                    gc.collect()
                    if st is None:
                        continue
                    if best is None or st['stat'] > best['stat']:
                        best = dict(th=th, arm=arm, R=R, mode=mode,
                                    k_sl=k_sl, k_tp=k_tp, **st)
    base = baseline_stat(df1, shock, body_sgn, atr_prev, asset, pip)
    del shock, rho, body_sgn, atr_prev
    gc.collect()
    return best, base


def discover_one_th(tf, th):
    """کشفِ یک θ در پردازه‌ی جدا (M1 ضدِ OOM)."""
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    t_arr = np.asarray(d['time'], dtype=np.int64)
    t_mid = (int(t_arr[0]) + int(t_arr[-1])) // 2
    split = int(np.searchsorted(t_arr, t_mid))
    df1 = _views_df(d, end=split)
    pip = se.ASSETS['XAUUSD']['pip']
    best, base = _discover_th(df1, th, 'XAUUSD', pip)
    out = dict(tf=tf, th=th, split_bar=split, best=best, p1_baseline=base)
    json.dump(out, open(f'{OUT}/partial_{tf}_th{th}.json', 'w'),
              ensure_ascii=False, indent=1)
    print(f'[{tf} th={th}] best={None if best is None else round(best["stat"],1)}'
          f' base={base}', flush=True)


def adjudicate_from_partials(tf):
    """داوریِ نهایی از partialها (holdout یک بار)."""
    t0 = time.time()
    bests, bases = [], {}
    split = None
    for th in TH_LIST:
        fp = f'{OUT}/partial_{tf}_th{th}.json'
        if not os.path.exists(fp):
            raise RuntimeError(f'partial missing: {fp}')
        rec = json.load(open(fp))
        split = rec['split_bar']
        if rec['best'] is not None:
            bests.append(rec['best'])
        bases[str(th)] = rec.get('p1_baseline')
    d = fd.load_fast('XAUUSD', tf)
    for _k in ('hour', 'minute', 'dow'):
        d.pop(_k, None)
    src = d['src']
    n_bars = len(d['close'])
    if not bests:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
                   verdict='NO-SURVIVOR', p1_baseline=bases,
                   note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec
    best = max(bests, key=lambda b: b['stat'])
    return _final_judge(tf, d, src, n_bars, split, best, bases, t0)


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
    best = None
    bases = {}
    for th in TH_LIST:
        b, base = _discover_th(df1, th, asset, pip)
        bases[str(th)] = base
        if b is not None and (best is None or b['stat'] > best['stat']):
            best = b
    if best is None:
        rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
                   verdict='NO-SURVIVOR', p1_baseline=bases,
                   note='هیچ عضوی غربالِ کشف (n>=30 و expectancy>0) را نگذراند',
                   sec=round(time.time() - t0, 1))
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    return _final_judge(tf, d, src, n_bars, split, best, bases, t0)


def _final_judge(tf, d, src, n_bars, split, best, bases, t0):
    """داوریِ یک‌باره روی کلِ داده (holdout یک بار لمس می‌شود)."""
    asset = 'XAUUSD'
    pip = se.ASSETS[asset]['pip']
    df = _views_df(d)
    th, arm, R = best['th'], best['arm'], best['R']
    mode, k_sl, k_tp = best['mode'], best['k_sl'], best['k_tp']
    shock, rho, body_sgn, atr_prev = features(df, th)
    tr, ls, ss, sl_arr, tp_arr = run_member(df, shock, rho, body_sgn,
                                            atr_prev, arm, R, mode,
                                            k_sl, k_tp, asset, pip)
    if tr is None or len(tr) == 0:
        rec = dict(tf=tf, src=src, verdict='NO-TRADES', best=best,
                   n_bars=n_bars, split_bar=split)
        json.dump(rec, open(f'{OUT}/{tf}.json', 'w'), ensure_ascii=False, indent=1)
        return rec

    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * (k_tp / k_sl)
    null = build_null(df, ls, ss, sl_arr, tp_arr, MAX_HOLD, asset)
    res = rqs2.compute_rqs2(tr, asset, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=df['time'].values, null=null,
                            n_trials=N_TRIALS, split_bar=split,
                            close=df['close'].values)
    mt = res['metrics']
    rec = dict(tf=tf, src=src, n_bars=n_bars, split_bar=split,
               member=dict(th=th, arm=arm, R=R, mode=mode, k_sl=k_sl,
                           k_tp=k_tp, max_hold=MAX_HOLD,
                           sl_pip_med=round(sl_med, 2),
                           tp_pip_med=round(tp_med, 2)),
               discovery={k: (round(v, 3) if isinstance(v, float) else v)
                          for k, v in best.items()},
               p1_baseline=bases,
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
    if len(sys.argv) >= 3 and sys.argv[1] == 'discover':
        discover_one_th(sys.argv[2], float(sys.argv[3]))
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
