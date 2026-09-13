# -*- coding: utf-8 -*-
"""S926 — «شوکِ نظمِ جوان» (Young-Order Shock: absolute c2c shock × drift-age) | XAUUSD | MTF

پیش‌ثبت: `results/S926_PREREG_YOUNG_ORDER_SHOCK.md` (commit ef0dfac5 — قبل از هر تست)

فرضیه (هایک ۱۹۴۵/۱۹۶۸)
--------------------------------------------------------------------------------
نظمِ خودجوش در لحظهٔ زایش بیشترین اطلاعات را دارد؛ دیرتر، شوک‌های هم‌راستا بیشتر تقلیدند.
رویداد: |Δclose| ≥ θ·ATR21[t-1] (مقیاسِ مطلق — درس L-S925-1)، هم‌راستا با درفتِ ۶۰-روزه (S604).
بازویِ فرضیه: سنِ درفت (طولِ رشتهٔ علامتِ D تا t-1) ≤ K/2 («young») در برابرِ «any».

هارنس: کپیِ ساختاریِ s925 (Path C، نگهبانِ یک‌بار-لمس، null هندسی‌همتا، K=2000، F3-holdout report-only).
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from engine import rqs2 as R                   # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = os.path.join(ROOT, 'results', '_scan_S926')
SEED = 20260907
K_PERM = 2000
ATR_P = 21
HOLD = 55                                      # منجمد در پیش‌ثبت
MIN_SPAN_YEARS = 14.0                          # E-16 guard (mt5_full M1 = 5,000,000 bars = 14.34y — MT5 export cap; the short trap files are 2.8y/6.4y)

# ---------------- شبکهٔ قفل‌شدهٔ پیش‌ثبت ----------------
GRID_THETA = [1.618, 2.618]
GRID_AGE = ['young', 'any']
GRID_A = [1.618, 2.058]
N_GRID = len(GRID_THETA) * len(GRID_AGE) * len(GRID_A)  # 8
DRIFT_DAYS = 60                                        # قراردادِ S604
TF_MIN = {'M1': 1, 'M3': 3, 'M4': 4, 'M5': 5, 'M6': 6, 'M10': 10, 'M12': 12, 'M15': 15,
          'M20': 20, 'M30': 30, 'H1': 60, 'H2': 120, 'H3': 180, 'H4': 240, 'H6': 360,
          'H8': 480, 'H12': 720, 'D1': 1440, 'W1': 10080}


def drift_K(tf: str) -> int:
    if tf == 'W1':
        return 9
    return int(round(DRIFT_DAYS * 24 * 60 / TF_MIN[tf]))
N_TRIALS = N_GRID * 3                                   # 24

TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1']


# ═══════════════ سیگنال (برداری، بدون look-ahead) ═══════════════

def atr_raw(df: pd.DataFrame, p=ATR_P) -> np.ndarray:
    """ATR ویلدر (ewm α=1/p) در واحدِ قیمت، روی کندلِ t (بدونِ lag)."""
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0/p, adjust=False).mean().to_numpy()


def atr_pip(df: pd.DataFrame, p=ATR_P, ps=0.1) -> np.ndarray:
    return atr_raw(df, p) / ps


def run_length_same_sign(sgn: np.ndarray) -> np.ndarray:
    """طولِ رشتهٔ علامتِ یکسان منتهی به t (شاملِ t). صفر برای NaN/0."""
    n = len(sgn)
    idx = np.arange(n)
    prev = np.concatenate([[np.nan], sgn[:-1]])
    with np.errstate(invalid='ignore'):
        brk = (sgn != prev) | ~np.isfinite(sgn) | (sgn == 0)
    last_brk = np.maximum.accumulate(np.where(brk, idx, -1))
    out = idx - last_brk + 1
    out[~np.isfinite(sgn) | (sgn == 0)] = 0
    return out


def build_events(df: pd.DataFrame, theta: float, age_mode: str, K: int):
    """شوکِ مطلقِ close-to-close، هم‌راستا با درفتِ K-کندلی؛ فیلترِ سنِ درفت."""
    c = df['close'].to_numpy(float)
    atr = atr_raw(df)
    atr_lag = np.concatenate([[np.nan], atr[:-1]])                 # ATR21[t-1]
    dc = np.diff(c, prepend=np.nan)                                 # close[t]-close[t-1]
    with np.errstate(invalid='ignore'):
        shock = np.abs(dc) >= theta * atr_lag
    shock &= np.isfinite(atr_lag) & np.isfinite(dc)
    # درفت D[t] = close[t-1] - close[t-1-K]
    prev_c = np.concatenate([[np.nan], c[:-1]])
    lag_c = np.concatenate([np.full(K + 1, np.nan), c[:-(K + 1)]])
    D = prev_c - lag_c
    with np.errstate(invalid='ignore'):
        sgnD = np.sign(D)
    sgnD = np.where(np.isfinite(D), sgnD, np.nan)
    long_ev = shock & (dc > 0) & (sgnD == 1)
    short_ev = shock & (dc < 0) & (sgnD == -1)
    if age_mode == 'young':
        # سنِ درفت تا t-1: رشتهٔ علامتِ D که خودِ D[t] از close[t-1] ساخته شده ⇒ run تا t علّی است
        age = run_length_same_sign(sgnD)
        young = age <= (K // 2)
        long_ev &= young; short_ev &= young
    return long_ev, short_ev


def selftest():
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d).iloc[:8000].reset_index(drop=True)
    c = df['close'].to_numpy(float)
    K = drift_K('H1')
    # run_length: مقایسه با حلقهٔ ساده
    x = np.sign(np.random.default_rng(1).normal(size=3000)); x[100:110] = np.nan; x[500] = 0
    rl = run_length_same_sign(x)
    ref = np.zeros(3000, int); run = 0; prev = None
    for i in range(3000):
        if not np.isfinite(x[i]) or x[i] == 0: run = 0; prev = None
        elif prev is not None and x[i] == prev: run += 1
        else: run = 1
        prev = x[i] if (np.isfinite(x[i]) and x[i] != 0) else None
        ref[i] = run
    assert np.array_equal(rl, ref), 'run_length mismatch'
    print('selftest run_length: identical=True')
    # شوک: بدون look-ahead — تغییرِ کندل t+1 رویدادهای ≤t را عوض نکند
    le, sh = build_events(df, 1.618, 'any', K)
    df2 = df.copy(); df2.loc[6001, ['open','high','low','close']] *= 1.05
    le2, sh2 = build_events(df2, 1.618, 'any', K)
    assert np.array_equal(le[:6001], le2[:6001]) and np.array_equal(sh[:6001], sh2[:6001]), 'look-ahead!'
    assert not np.any(le & sh)
    ly, sy = build_events(df, 1.618, 'young', K)
    assert ly.sum() <= le.sum() and sy.sum() <= sh.sum()
    # ATR lag: شوک با ATR[t-1] سنجیده شود — کندلِ شوک خودش ATR را بالا نبرد
    atr = atr_raw(df); t = int(np.where(le)[0][5]); assert abs(c[t]-c[t-1]) >= 1.618*atr[t-1]
    print(f'selftest events θ=1.618 H1: any L={int(le.sum())} S={int(sh.sum())} | young L={int(ly.sum())} S={int(sy.sum())} | K={K} A_max={K//2}')
    print('selftest PASSED — شوکِ مطلق و سنِ درفت صحیح، بدونِ look-ahead')


# ═══════════════════════════ ارزیابی (عینِ s923) ═══════════════════════════

def eval_config(df, long_ev, short_ev, sl_pip, tp_pip, hold, side):
    ls = pd.Series(long_ev if side in ('long', 'both') else np.zeros(len(df), bool))
    ss = pd.Series(short_ev if side in ('short', 'both') else np.zeros(len(df), bool))
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset='XAUUSD', max_hold=hold, allow_overlap=False)
    return tr


def measured_null(df, n_long, n_short, sl_pip, tp_pip, hold, k=K_PERM, seed=SEED,
                  warmup=200):
    n = len(df)
    rng = np.random.default_rng(seed)
    valid = np.arange(warmup, n - 2)
    out = {}
    stride = max(1, len(valid) // 20000)
    for side, cnt in (('long', n_long), ('short', n_short)):
        if cnt <= 0:
            out[side] = None
            continue
        sig_u = pd.Series(np.zeros(n, bool)); sig_u.iloc[valid[::stride]] = True
        z = pd.Series(np.zeros(n, bool))
        tru = se.simulate_trades(df, sig_u if side == 'long' else z,
                                 z if side == 'long' else sig_u,
                                 sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                 max_hold=hold, allow_overlap=False)
        uncond = 100.0 * float((tru['pnl_pip'] > 0).mean()) if len(tru) else None
        wrs = []
        for _ in range(k):
            pick = np.sort(rng.choice(valid, size=min(cnt * 3, len(valid)),
                                      replace=False))
            sig = pd.Series(np.zeros(n, bool)); sig.iloc[pick] = True
            trp = se.simulate_trades(df, sig if side == 'long' else z,
                                     z if side == 'long' else sig,
                                     sl_pip=sl_pip, tp_pip=tp_pip, asset='XAUUSD',
                                     max_hold=hold, allow_overlap=False)
            if len(trp) > cnt:
                trp = trp.iloc[:cnt]
            if len(trp):
                wrs.append(100.0 * float((trp['pnl_pip'] > 0).mean()))
        wrs = np.array(wrs)
        out[side] = dict(uncond_wr=uncond,
                         perm_mean=float(wrs.mean()), perm_sd=float(wrs.std(ddof=1)),
                         perm_max=float(wrs.max()), perm_k=int(len(wrs)))
    return out


def prep(tf, lo=None, hi=None):
    d = fd.load_fast('XAUUSD', tf)
    n_all = int(d['n_bars']) if 'n_bars' in d else len(d['close'])
    t = np.asarray(d['time'], dtype=float)
    span_y = (t[-1] - t[0]) / (365.25 * 86400)
    if span_y < MIN_SPAN_YEARS or 'mt5_full' not in d['src']:
        raise RuntimeError(f'E-16 guard: {tf} src={d["src"]} span={span_y:.2f}y (need >={MIN_SPAN_YEARS}y AND data/mt5_full)')
    sl_ = slice(lo, hi)
    df = pd.DataFrame({k: d[k][sl_] for k in
                       ('time', 'open', 'high', 'low', 'close', 'volume')},
                      copy=False)
    meta = dict(src=d['src'], n_all=n_all, span_years=round(span_y, 2))
    return meta, df


def discover(tf):
    os.makedirs(OUT, exist_ok=True)
    d, df = prep(tf)
    n_all = d['n_all']
    half = n_all // 2
    df = df.iloc[:half]
    c = np.ascontiguousarray(df['close'].to_numpy(float))
    import gc; gc.collect()
    t0 = time.time()
    apip = atr_pip(df)
    atr_med = float(np.nanmedian(apip))
    spread = se.ASSETS['XAUUSD']['spread_pip']
    print(f'[{tf}] bars_all={n_all} half={half} src={d["src"]} span={d["span_years"]}y '
          f'atr{ATR_P}_med={atr_med:.1f}pip', flush=True)

    results = []
    K = drift_K(tf)
    df_half = df
    for theta in GRID_THETA:
        wu = K + 60
        for age_mode in GRID_AGE:
            long_ev, short_ev = build_events(df_half, theta, age_mode, K)
            long_ev[:wu] = False; short_ev[:wu] = False
            nL, nS = int(long_ev.sum()), int(short_ev.sum())
            for a in GRID_A:
                sl = round(a * atr_med, 2); tp = sl          # RR=1 قفلِ پیش‌ثبت
                be = 100.0 * (sl + spread) / (sl + tp)
                for side in ('long', 'short', 'both'):
                    tr = eval_config(df_half, long_ev, short_ev, sl, tp, HOLD, side)
                    if tr is None or len(tr) < 30:           # کفِ پیش‌ثبت
                        continue
                    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                    nn = len(tr); edge = wr - be
                    results.append(dict(
                        theta=theta, age=age_mode, K=K, A_max=K // 2, a=a, hold=HOLD, side=side,
                        sl_pip=sl, tp_pip=tp, be_wr=round(be, 2),
                        n=nn, wr=round(wr, 2), edge_pp=round(edge, 2),
                        score=round(edge * np.sqrt(nn), 1),
                        exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                        nL_ev=nL, nS_ev=nS))
        print(f'  θ={theta}: arms done {time.time()-t0:.0f}s', flush=True)

    results.sort(key=lambda r: r['score'], reverse=True)
    survivors = [r for r in results if r['edge_pp'] > 0]
    best = survivors[0] if survivors else None
    payload = dict(tf=tf, src=d['src'], n_all=n_all, half_idx=half,
                   span_years=d['span_years'],
                   atr_med_pip=atr_med, n_grid=N_GRID, n_trials=N_TRIALS,
                   drift_K=drift_K(tf),
                   grid_results=results[:60], best=best,
                   phase='discover', ts=time.time())
    path = f'{OUT}/{tf}_discover.json'
    with open(path, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    if best:
        print(f'[{tf}] BEST(train): {best}', flush=True)
    else:
        print(f'[{tf}] NO-SURVIVOR در نیمهٔ اول', flush=True)
    print(f'saved -> {path}', flush=True)
    return payload


def final(tf):
    dis_path = f'{OUT}/{tf}_discover.json'
    if not os.path.exists(dis_path):
        print(f'[{tf}] discover اول اجرا شود'); return None
    with open(dis_path) as f:
        dis = json.load(f)
    best = dis.get('best')
    if not best:
        print(f'[{tf}] NO-SURVIVOR — آزمونِ نهایی موضوعیت ندارد'); return None

    guard = f'{OUT}/{tf}_final.json'
    if os.path.exists(guard):
        print(f'[{tf}] ⛔ نیمهٔ دوم قبلاً لمس شده')
        with open(guard) as f:
            return json.load(f)

    d, df = prep(tf)
    n_all = d['n_all']
    half = n_all // 2
    c = df['close'].to_numpy(float)
    long_ev, short_ev = build_events(df, best['theta'], best['age'], best['K'])
    long_ev[:half] = False
    short_ev[:half] = False
    sl, tp, hold, side = best['sl_pip'], best['tp_pip'], best['hold'], best['side']

    tr = eval_config(df, long_ev, short_ev, sl, tp, hold, side)
    print(f'[{tf}] FINAL trades={len(tr)}', flush=True)
    if tr is None or len(tr) < 5:
        payload = dict(tf=tf, phase='final', verdict='NO-TRADES', best=best,
                       n=0 if tr is None else len(tr), src=d['src'])
        with open(guard, 'w') as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        return payload

    nL = int((tr['direction'] == 'long').sum()); nS = len(tr) - nL
    df2 = df.iloc[half:].reset_index(drop=True)
    null = measured_null(df2, nL, nS, sl, tp, hold)

    bar_time = df['time'].to_numpy()
    res = R.compute_rqs2(tr, 'XAUUSD', sl_pip=sl, tp_pip=tp,
                         bar_time=bar_time, close=c, null=null,
                         n_trials=N_TRIALS, split_bar=half)
    print(R.format_rqs2(f'S926_{tf}', res), flush=True)
    # F3-holdout (report-only، اعلام‌شده در پیش‌ثبت §4): بازویِ گیتِ مقابل با همان W/a/side
    other = 'any' if best['age'] == 'young' else 'young'
    lo2, so2 = build_events(df, best['theta'], other, best['K'])
    lo2[:half] = False; so2[:half] = False
    tr2 = eval_config(df, lo2, so2, sl, tp, hold, side)
    f3 = None
    if tr2 is not None and len(tr2) >= 5:
        wr2 = 100.0 * float((tr2['pnl_pip'] > 0).mean())
        f3 = dict(other_age=other, n=len(tr2), wr=round(wr2, 2),
                  exp_pip=round(float(tr2['pnl_pip'].mean()), 2),
                  official_wr=round(100.0 * float((tr['pnl_pip'] > 0).mean()), 2),
                  note='report-only holdout diagnostic; no verdict, no card')
        print(f'[{tf}] F3-holdout: official({best["age"]}) WR={f3["official_wr"]} n={len(tr)} | {other} WR={wr2:.2f} n={len(tr2)}', flush=True)
    payload = dict(tf=tf, phase='final', src=d['src'], best=best, f3_holdout=f3,
                   n=len(tr), verdict=res['verdict'], score=res.get('rqs2_score'),
                   gates=res.get('gates'), metrics=res.get('metrics'),
                   null=null, n_trials=N_TRIALS, ts=time.time())
    with open(guard, 'w') as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    print(f'saved -> {guard}', flush=True)
    return payload


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'selftest'
    if cmd == 'selftest':
        selftest()
    elif cmd == 'discover':
        discover(sys.argv[2])
    elif cmd == 'final':
        final(sys.argv[2])
    else:
        print('usage: selftest | discover TF | final TF')
