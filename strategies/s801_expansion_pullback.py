# -*- coding: utf-8 -*-
"""
S801 — ازسرگیریِ روند پس از پولبک در رژیمِ انبساطِ نوسان (ERPR)
================================================================================
پیش‌ثبت: `results/S801_PREREG_EXPANSION_PULLBACK_RESUMPTION_XAUUSD.md`
(کامیت 72d77c64 — قفل پیش از هر اندازه‌گیری). مسیر چندگانگی: **C (hold-out)**.
زیرساخت ضد-OOM و نولِ سدمحور عیناً از S800 (اثبات‌شده) بازاستفاده می‌شود.

خانواده (۲۱۶ ترکیب، قفل):
  qe∈{60,70,80} · D∈{55,89} · e∈{13,21} · k∈{1.272,1.618,2.058} ·
  RR∈{1.0,1.618} · hold∈{21,34,55}

قاعده:
  expa(t)  = atr_pct[t-1] ≥ qe
  drift(t) = close[t-1] − close[t-1-D]
  LONG : expa & drift>0 & close[t-1]≤EMA_e[t-1] & close[t]>EMA_e[t]
  SHORT: expa & drift<0 & close[t-1]≥EMA_e[t-1] & close[t]<EMA_e[t]
  SL = k·ATR21 (pip) · TP = RR·SL · allow_overlap=False

اجرا:
  python3 strategies/s801_expansion_pullback.py --tf H8 --phase explore
  python3 strategies/s801_expansion_pullback.py --tf H8 --phase judge
خروجی: results/_scan_S801/<TF>_explore.json / _locked.json / _judge.json
"""
import sys
import os
import gc
import json
import argparse
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se            # noqa: E402
from engine import rqs2                          # noqa: E402
from engine import indicator_bank as ib          # noqa: E402
from tools import s434_fast_data as fd           # noqa: E402

OUT = 'results/_scan_S801'
S800_OUT = 'results/_scan_S800'                   # بازاستفادهٔ .npy های M1
ASSET = 'XAUUSD'
SEED = 20260828                                   # بذرِ پیش‌ثبت‌شده
K_PERM = 500
POWER_MIN = 78.0
N_TRIALS_JUDGE = 1

# ---------------- خانوادهٔ قفل‌شده (۲۱۶) ----------------
QE   = [60.0, 70.0, 80.0]
DRIFT_D = [55, 89]
EMA_E = [13, 21]
SL_K = [1.272, 1.618, 2.058]
RR   = [1.0, 1.618]
HOLD = [21, 34, 55]
N_FAMILY = len(QE) * len(DRIFT_D) * len(EMA_E) * len(SL_K) * len(RR) * len(HOLD)
assert N_FAMILY == 216


def load(tf, hi=None):
    d = fd.load_fast(ASSET, tf)
    n_all = len(d['close'])
    hi = n_all if hi is None else min(hi, n_all)
    cols = {}
    for c in ('open', 'high', 'low', 'close'):
        cols[c] = np.ascontiguousarray(d[c][:hi], dtype=np.float32)
    cols['time'] = np.ascontiguousarray(d['time'][:hi])
    meta = dict(src=d['src'], n_all=n_all)
    del d
    gc.collect()
    df = pd.DataFrame(cols, copy=False)
    del cols
    gc.collect()
    return meta, df


def ind_path(tf, name):
    for root in (OUT, S800_OUT):
        p = f'{root}/{tf}_ind_{name}.npy'
        if os.path.exists(p):
            return p
    return f'{OUT}/{tf}_ind_{name}.npy'


def ema_np(x, span):
    """EMA بازگشتی (بیت‌به‌بیت با pandas ewm(adjust=False))، float64 داخلی."""
    a = 2.0 / (span + 1.0)
    out = np.empty(len(x), dtype=np.float64)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out.astype(np.float32)


def base_arrays(df, tf=None):
    pip = se.ASSETS[ASSET]['pip']

    def get(name):
        p = ind_path(tf, name)
        if os.path.exists(p):
            return np.load(p, mmap_mode='r')
        return np.asarray(ib.compute(name, df), dtype=np.float32)

    atr21 = np.asarray(get('atr_fib_21'), dtype=np.float32)
    gc.collect()
    atr_pct = np.asarray(get('atr_pct'), dtype=np.float32)
    gc.collect()
    # رژیم با تأخیر ۱ کندل
    expa_raw = np.empty_like(atr_pct)
    expa_raw[0] = np.nan
    expa_raw[1:] = atr_pct[:-1]
    del atr_pct
    gc.collect()
    sl_pip_arr = (atr21 / pip).astype(np.float32)
    del atr21
    gc.collect()
    close = df['close'].values.astype(np.float64)
    emas = {e: ema_np(close, e) for e in EMA_E}
    drifts = {}
    for D in DRIFT_D:
        d = np.full(len(close), np.nan, dtype=np.float32)
        # drift(t) = close[t-1] − close[t-1-D]
        d[D + 1:] = (close[D:-1] - close[:-D - 1]).astype(np.float32)
        drifts[D] = d
    return dict(pip=pip, sl_pip=sl_pip_arr, expa=expa_raw, emas=emas,
                drifts=drifts, close=close.astype(np.float32))


def signals(base, qe, D, e):
    c = base['close']
    em = base['emas'][e]
    dr = base['drifts'][D]
    n = len(c)
    ls = np.zeros(n, dtype=bool)
    ss = np.zeros(n, dtype=bool)
    expa = base['expa'] >= qe
    expa &= np.isfinite(base['expa'])
    c_prev = c[:-1]
    em_prev = em[:-1]
    c_now = c[1:]
    em_now = em[1:]
    up = (c_prev <= em_prev) & (c_now > em_now)
    dn = (c_prev >= em_prev) & (c_now < em_now)
    ls[1:] = up & expa[1:] & (dr[1:] > 0)
    ss[1:] = dn & expa[1:] & (dr[1:] < 0)
    warm = max(D + 1, 3 * e, 120)
    ls[:warm] = False
    ss[:warm] = False
    return ls, ss


def run_cfg(df, base, cfg, sig_cache=None):
    key = (cfg['qe'], cfg['D'], cfg['e'])
    if sig_cache is not None and key in sig_cache:
        ls0, ss0 = sig_cache[key]
    else:
        ls0, ss0 = signals(base, *key)
        if sig_cache is not None:
            sig_cache[key] = (ls0, ss0)
    valid_sl = np.isfinite(base['sl_pip']) & (base['sl_pip'] > 0)
    ls = ls0 & valid_sl
    ss = ss0 & valid_sl
    sl = np.where(valid_sl, base['sl_pip'] * cfg['k'], 1.0)
    tp = sl * cfg['rr']
    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                            max_hold=cfg['hold'], allow_overlap=False)
    return tr, ls, ss, sl, tp


def summarize(tr, cost_pip):
    if tr is None or len(tr) == 0:
        return None
    n = len(tr)
    wins = int((tr['outcome'] == 'win').sum())
    wr = wins / n * 100.0
    pnl = tr['pnl_pip'].values.astype(np.float64)
    exp_pip = float(np.mean(pnl))
    gp = float(pnl[pnl > 0].sum())
    gl = float(-pnl[pnl < 0].sum())
    pf = gp / gl if gl > 0 else float('inf')
    sl_m = float(np.mean(tr['sl_pip'].values))
    return dict(n=n, wr=wr, exp_pip=exp_pip, pf=pf, sl_med=sl_m)


def build_null_barrier(df, ls, ss, sl, tp, hold, K=K_PERM, seed=SEED):
    """نولِ سدمحور (عین S800): خروجی واقعی SL/TP هر دو جهت + K جای‌گشت جهت."""
    sig = ls | ss
    if int(sig.sum()) < 30:
        return None
    trL = se.simulate_trades(df, sig, np.zeros_like(sig), sl, tp, ASSET,
                             max_hold=hold, allow_overlap=True)
    trS = se.simulate_trades(df, np.zeros_like(sig), sig, sl, tp, ASSET,
                             max_hold=hold, allow_overlap=True)
    mL = {int(b): (o == 'win') for b, o in zip(trL['entry_bar'], trL['outcome'])}
    mS = {int(b): (o == 'win') for b, o in zip(trS['entry_bar'], trS['outcome'])}
    bars = sorted(set(mL) & set(mS))
    m = len(bars)
    if m < 30:
        return None
    wl = np.array([mL[b] for b in bars], dtype=bool)
    ws = np.array([mS[b] for b in bars], dtype=bool)
    rng = np.random.default_rng(seed)
    wrs = np.empty(K)
    for i in range(K):
        pick = rng.integers(0, 2, size=m).astype(bool)
        wrs[i] = np.where(pick, wl, ws).mean() * 100.0
    ref = float(np.mean(wrs))
    side = dict(uncond_wr=ref, perm_mean=ref, perm_sd=float(np.std(wrs)),
                perm_max=float(np.max(wrs)), perm_k=K)
    return {'long': dict(side), 'short': dict(side)}


def phase_explore(tf):
    os.makedirs(OUT, exist_ok=True)
    probe = fd.load_fast(ASSET, tf)
    n = len(probe['close'])
    src = probe['src']
    del probe
    gc.collect()
    split = n // 2
    cost = se.ASSETS[ASSET]['spread_pip']
    print(f"[S801/{tf}] explore  src={src}  bars={n}  split={split}", flush=True)
    meta, df = load(tf, hi=split)
    base = base_arrays(df, tf=tf)
    for k in ('sl_pip', 'expa'):
        if len(base[k]) > split:
            base[k] = np.ascontiguousarray(base[k][:split])
    gc.collect()
    sig_cache = {}
    rows = []
    t0 = time.time()
    done = 0
    for qe in QE:
        for D in DRIFT_D:
            for e in EMA_E:
                for k in SL_K:
                    for rr in RR:
                        for hold in HOLD:
                            cfg = dict(qe=qe, D=D, e=e, k=k, rr=rr, hold=hold)
                            tr, *_ = run_cfg(df, base, cfg, sig_cache)
                            s = summarize(tr, cost)
                            done += 1
                            if s is None or s['n'] < 30:
                                continue
                            be = ((s['sl_med'] + cost)
                                  / (s['sl_med'] * (1 + rr)) * 100.0)
                            lift_be = s['wr'] - be
                            score = lift_be * np.sqrt(s['n'])
                            rows.append(dict(cfg=cfg, **s, be_wr=be,
                                             lift_be=lift_be, score=score))
                            if done % 36 == 0:
                                print(f"  … {done}/{N_FAMILY} ({time.time()-t0:.0f}s) "
                                      f"valid={len(rows)}", flush=True)
                                with open(f'{OUT}/{tf}_explore.json', 'w') as f:
                                    json.dump(dict(tf=tf, done=done, rows=rows), f)
    rows.sort(key=lambda r: -r['score'])
    with open(f'{OUT}/{tf}_explore.json', 'w') as f:
        json.dump(dict(tf=tf, done=done, split=split, bars=n, src=src,
                       rows=rows[:50]), f, indent=1)
    if not rows:
        print(f"[S801/{tf}] هیچ ترکیب معتبری (n≥30) روی نیمهٔ اول ⇒ UNPROVEN",
              flush=True)
        with open(f'{OUT}/{tf}_locked.json', 'w') as f:
            json.dump(dict(tf=tf, cfg=None, power_ok=False, reason='no_valid',
                           split=split, bars=n, src=src, seed=SEED), f, indent=1)
        return
    best = rows[0]
    print(f"[S801/{tf}] برندهٔ نیمهٔ اول: {best['cfg']}  n={best['n']}  "
          f"wr={best['wr']:.1f}  lift_be={best['lift_be']:.2f}pp  "
          f"score={best['score']:.1f}", flush=True)
    cfg = best['cfg']
    tr, ls, ss, sl, tp = run_cfg(df, base, cfg, sig_cache)
    null = build_null_barrier(df, ls, ss, sl, tp, cfg['hold'])
    if null is None:
        print(f"[S801/{tf}] نول ساخته نشد ⇒ POWER-LIMITED", flush=True)
        with open(f'{OUT}/{tf}_locked.json', 'w') as f:
            json.dump(dict(tf=tf, cfg=cfg, power_ok=False, reason='no_null',
                           explore=best, split=split, bars=n, src=src,
                           seed=SEED), f, indent=1)
        return
    s = summarize(tr, cost)
    lift = s['wr'] - null['long']['perm_mean']
    power = lift * np.sqrt(s['n'])
    ok = bool(power >= POWER_MIN)
    locked = dict(tf=tf, cfg=cfg, explore=dict(**s), null_explore=null,
                  lift_vs_null=lift, power=power, power_ok=ok,
                  split=split, bars=n, src=src, seed=SEED)
    with open(f'{OUT}/{tf}_locked.json', 'w') as f:
        json.dump(locked, f, indent=1)
    print(f"[S801/{tf}] lift(null)={lift:.2f}pp  n={s['n']}  lift·√n={power:.1f}  "
          f"(آستانه {POWER_MIN})  "
          f"{'✓ مجوز آزمون نهایی' if ok else '✗ توان ناکافی — judge اجرا نمی‌شود'}",
          flush=True)


def phase_judge(tf):
    path = f'{OUT}/{tf}_locked.json'
    if not os.path.exists(path):
        print(f"[S801/{tf}] فایل قفل یافت نشد — ابتدا explore.", flush=True)
        return
    locked = json.load(open(path))
    if not locked.get('power_ok'):
        print(f"[S801/{tf}] پیش‌شرط توان برآورده نشده — judge اجرا نمی‌شود.",
              flush=True)
        return
    meta, df = load(tf)
    base = base_arrays(df, tf=tf)
    cfg = locked['cfg']
    split = locked['split']
    cost = se.ASSETS[ASSET]['spread_pip']
    tr, ls, ss, sl, tp = run_cfg(df, base, cfg)
    null = build_null_barrier(df, ls, ss, sl, tp, cfg['hold'])
    s = summarize(tr, cost)
    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = sl_med * cfg['rr']
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS_JUDGE, split_bar=split,
                          close=df['close'].values)
    out = dict(tf=tf, cfg=cfg, src=meta['src'], bars=len(df), split=split,
               n=s['n'], wr=s['wr'], exp_pip=s['exp_pip'], pf=s['pf'],
               sl_med=sl_med, tp_med=tp_med,
               verdict=r['verdict'], score=r['rqs2_score'],
               gates={k: (None if v is None else bool(v))
                      for k, v in r['gates'].items()},
               skill_p_perm=r['metrics'].get('skill_p_perm'),
               metrics={k: (float(v) if isinstance(v, (int, float, np.floating))
                            else str(v)) for k, v in r['metrics'].items()})
    with open(f'{OUT}/{tf}_judge.json', 'w') as f:
        json.dump(out, f, indent=1, default=str)
    print(rqs2.format_rqs2(f'S801 {tf} ', r), flush=True)
    print(f"[S801/{tf}] verdict={r['verdict']}  score={r['rqs2_score']:.1f}  "
          f"skill_p_perm={r['metrics'].get('skill_p_perm')}", flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', required=True)
    ap.add_argument('--phase', choices=['explore', 'judge', 'both'], default='both')
    a = ap.parse_args()
    if a.phase in ('explore', 'both'):
        phase_explore(a.tf)
    if a.phase in ('judge', 'both'):
        phase_judge(a.tf)
