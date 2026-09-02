# -*- coding: utf-8 -*-
"""S922 — «تداومِ کشفِ قیمت»: شکستِ کانالِ دانچین به‌مثابهٔ رویدادِ کشفِ قیمت | XAUUSD | MTF

پیش‌ثبت: `results/S922_PREREG_PRICE_DISCOVERY_CONTINUATION.md` (commit 6ce73510 — قبل از هر تست)

فرضیه (هایک — رقابت به‌مثابهٔ رویهٔ اکتشاف)
--------------------------------------------------------------------------------
قیمتِ تازه (گذرِ close از بیشینه/کمینهٔ P کندلِ قبل) = بازار در حالِ کشفِ اطلاعاتِ
هنوز-منتشرنشده. ورودِ هم‌جهت با شکست. بدونِ هیچ پیش‌شرطِ فشردگی/شوک — عملگرِ بکر
(متمایز از S900/S800/S883/خانوادهٔ انگل؛ ممیزی در پیش‌ثبت).

هارنس: کپیِ ساختاریِ s921 (Path C، نگهبانِ یک‌بار-لمس، null هندسی‌همتا).

فازها:
  python3 strategies/s922_price_discovery.py selftest
  python3 strategies/s922_price_discovery.py discover M1
  python3 strategies/s922_price_discovery.py final M1
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

OUT = os.path.join(ROOT, 'results', '_scan_S922')
SEED = 20260830
K_PERM = 2000
ATR_P = 89

# ---------------- شبکهٔ قفل‌شدهٔ پیش‌ثبت ----------------
GRID_P = [55, 144]
GRID_A = [1.618, 2.058]
GRID_HOLD = [55, 144]
N_GRID = len(GRID_P) * len(GRID_A) * len(GRID_HOLD)   # 8
N_TRIALS = N_GRID * 3                                  # 24

TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1']


# ═══════════════ سیگنال (برداری، بدون look-ahead) ═══════════════

def rolling_extreme(x: np.ndarray, p: int, mode: str) -> np.ndarray:
    """بیشینه/کمینهٔ p کندلِ *قبل* از t — پنجرهٔ [t-p, t-1]؛ کندلِ جاری بیرون."""
    n = len(x)
    out = np.full(n, np.nan)
    from numpy.lib.stride_tricks import sliding_window_view
    if n <= p:
        return out
    W = sliding_window_view(x, p)                 # ردیف j = x[j .. j+p-1]
    agg = W.max(axis=1) if mode == 'max' else W.min(axis=1)
    out[p:] = agg[:n - p]                         # out[t] = agg روی [t-p, t-1]
    return out


def build_events(high, low, close, p):
    HH = rolling_extreme(high, p, 'max')
    LL = rolling_extreme(low, p, 'min')
    n = len(close)
    long_ev = np.zeros(n, bool)
    short_ev = np.zeros(n, bool)
    with np.errstate(invalid='ignore'):
        up_now = close > HH
        dn_now = close < LL
    up_now = np.where(np.isnan(HH), False, up_now)
    dn_now = np.where(np.isnan(LL), False, dn_now)
    # رویدادِ گذر: الان شکسته، کندلِ قبل نشکسته بود
    long_ev[1:] = up_now[1:] & ~up_now[:-1]
    short_ev[1:] = dn_now[1:] & ~dn_now[:-1]
    return long_ev, short_ev


def atr_pip(df: pd.DataFrame, p=ATR_P, ps=0.1) -> np.ndarray:
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).ewm(alpha=1.0/p, adjust=False).mean().to_numpy()
    return a / ps


def selftest():
    """راستی‌آزماییِ rolling_extreme علیه pandas + بررسیِ نبودِ look-ahead."""
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d).iloc[:5000].reset_index(drop=True)
    h = df['high'].to_numpy(float)
    p = 55
    fast = rolling_extreme(h, p, 'max')
    ref = df['high'].rolling(p).max().shift(1).to_numpy()   # پنجرهٔ p منتهی به t-1
    ok = np.isfinite(ref) & np.isfinite(fast)
    diff = float(np.abs(ref[ok] - fast[ok]).max())
    print(f'selftest rollmax(shifted): n={int(ok.sum())} max_abs_diff={diff:.2e}')
    assert diff == 0.0, 'rolling_extreme diverges from pandas!'
    # نبودِ look-ahead: HH[t] نباید به high[t] وابسته باشد
    h2 = h.copy(); h2[3000] += 1000.0
    f2 = rolling_extreme(h2, p, 'max')
    assert f2[3000] == fast[3000], 'look-ahead detected!'
    assert f2[3001] != fast[3001], 'window shift wrong!'
    print('selftest PASSED — بدونِ look-ahead، عینِ pandas')


# ═══════════════════════════ ارزیابی (عینِ s921) ═══════════════════════════

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
    sl_ = slice(lo, hi)
    df = pd.DataFrame({k: d[k][sl_] for k in
                       ('time', 'open', 'high', 'low', 'close', 'volume')},
                      copy=False)
    meta = dict(src=d['src'], n_all=n_all)
    return meta, df


def discover(tf):
    os.makedirs(OUT, exist_ok=True)
    d, df = prep(tf)
    n_all = d['n_all']
    half = n_all // 2
    df = df.iloc[:half]
    h = np.ascontiguousarray(df['high'].to_numpy(float))
    l = np.ascontiguousarray(df['low'].to_numpy(float))
    c = np.ascontiguousarray(df['close'].to_numpy(float))
    import gc; gc.collect()
    t0 = time.time()
    apip = atr_pip(df)
    atr_med = float(np.nanmedian(apip))
    spread = se.ASSETS['XAUUSD']['spread_pip']
    print(f'[{tf}] bars_all={n_all} half={half} src={d["src"]} '
          f'atr{ATR_P}_med={atr_med:.1f}pip', flush=True)

    results = []
    for p in GRID_P:
        long_ev, short_ev = build_events(h, l, c, p)
        wu = p + 89                     # warmup: کانال + ATR
        long_ev[:wu] = False; short_ev[:wu] = False
        nL, nS = int(long_ev.sum()), int(short_ev.sum())
        for a in GRID_A:
            sl = round(a * atr_med, 2)
            tp = sl                     # RR=1 قفلِ پیش‌ثبت
            be = 100.0 * (sl + spread) / (sl + tp)
            for hold in GRID_HOLD:
                for side in ('long', 'short', 'both'):
                    tr = eval_config(df, long_ev, short_ev, sl, tp, hold, side)
                    if tr is None or len(tr) < 30:      # کفِ پیش‌ثبت
                        continue
                    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                    nn = len(tr)
                    edge = wr - be
                    results.append(dict(
                        p=p, a=a, hold=hold, side=side,
                        sl_pip=sl, tp_pip=tp, be_wr=round(be, 2),
                        n=nn, wr=round(wr, 2), edge_pp=round(edge, 2),
                        score=round(edge * np.sqrt(nn), 1),
                        exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                        nL_ev=nL, nS_ev=nS))
        print(f'  p={p}: events L={nL} S={nS} done {time.time()-t0:.0f}s', flush=True)

    results.sort(key=lambda r: r['score'], reverse=True)
    survivors = [r for r in results if r['edge_pp'] > 0]
    best = survivors[0] if survivors else None
    payload = dict(tf=tf, src=d['src'], n_all=n_all, half_idx=half,
                   atr_med_pip=atr_med, n_grid=N_GRID, n_trials=N_TRIALS,
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
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    long_ev, short_ev = build_events(h, l, c, best['p'])
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
    print(R.format_rqs2(f'S922_{tf}', res), flush=True)
    payload = dict(tf=tf, phase='final', src=d['src'], best=best,
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
