# -*- coding: utf-8 -*-
"""S924 — «نسبتِ سیگنال به نویزِ دانش» (Volatility-Scaled Momentum Threshold Cross) | XAUUSD | MTF

پیش‌ثبت: `results/S924_PREREG_KNOWLEDGE_SIGNAL_TO_NOISE.md` (commit 686a5649 — قبل از هر تست)

فرضیه (هایک)
--------------------------------------------------------------------------------
قیمت یک سامانهٔ مخابراتی است که دانشِ پراکنده را فشرده می‌کند. درفتِ K-کندلی «پیام» است و
نوسانِ تحقق‌یافتهٔ K-کندلی «نویزِ کانال». محتوایِ اطلاعاتیِ پیام، نسبتِ سیگنال به نویز است، نه
اندازهٔ خامِ درفت. رویداد: SNR[t] = drift_K/noise_K برای اولین بار از θ می‌گذرد (state-cross).

هارنس: کپیِ ساختاریِ s923 (Path C، نگهبانِ یک‌بار-لمس، null هندسی‌همتا، K=2000).

فازها:
  python3 strategies/s924_signal_to_noise.py selftest
  python3 strategies/s924_signal_to_noise.py discover H8
  python3 strategies/s924_signal_to_noise.py final H8
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

OUT = os.path.join(ROOT, 'results', '_scan_S924')
SEED = 20260905
K_PERM = 2000
ATR_P = 21
HOLD = 55                                      # منجمد در پیش‌ثبت
MIN_SPAN_YEARS = 14.0                          # E-16 guard (mt5_full M1 = 5,000,000 bars = 14.34y — MT5 export cap; the short trap files are 2.8y/6.4y)

# ---------------- شبکهٔ قفل‌شدهٔ پیش‌ثبت ----------------
GRID_K = [55, 144]
GRID_THETA = [1.0, 1.618]
GRID_A = [1.618, 2.058]
N_GRID = len(GRID_K) * len(GRID_THETA) * len(GRID_A)   # 8
N_TRIALS = N_GRID * 3                                   # 24

TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1']


# ═══════════════ سیگنال (برداری، بدون look-ahead) ═══════════════

def snr(close: np.ndarray, K: int) -> np.ndarray:
    """SNR[t] = ln(c[t]/c[t-K]) / (std(r[t-K+1..t]) * sqrt(K)); NaN در warmup."""
    lc = np.log(close)
    r = np.diff(lc, prepend=np.nan)
    drift = lc - np.concatenate([np.full(K, np.nan), lc[:-K]])
    sd = pd.Series(r).rolling(K).std(ddof=0).to_numpy() * np.sqrt(K)
    with np.errstate(invalid='ignore', divide='ignore'):
        out = drift / sd
    out[~np.isfinite(out)] = np.nan
    return out


def snr_naive(close: np.ndarray, K: int, t: int) -> float:
    lc = np.log(close)
    r = np.diff(lc[t - K:t + 1])          # K بازده منتهی به t
    d = lc[t] - lc[t - K]
    s = r.std(ddof=0) * np.sqrt(K)
    return d / s if s > 0 else np.nan


def threshold_cross(x: np.ndarray, theta: float):
    """long: x[t]>=θ و x[t-1]<θ ؛ short: آینه. NaN ⇒ بدون رویداد."""
    prev = np.concatenate([[np.nan], x[:-1]])
    with np.errstate(invalid='ignore'):
        long_ev = (x >= theta) & (prev < theta)
        short_ev = (x <= -theta) & (prev > -theta)
    long_ev &= np.isfinite(x) & np.isfinite(prev)
    short_ev &= np.isfinite(x) & np.isfinite(prev)
    return long_ev, short_ev


def build_events(close: np.ndarray, K: int, theta: float):
    return threshold_cross(snr(close, K), theta)


def build_raw_drift_baseline(close: np.ndarray, K: int):
    """تشخیصیِ F3: تغییرِ علامتِ درفتِ خام (θ=0 روی drift) — TSM ساده."""
    lc = np.log(close)
    drift = lc - np.concatenate([np.full(K, np.nan), lc[:-K]])
    return threshold_cross(drift, 0.0)


def atr_pip(df: pd.DataFrame, p=ATR_P, ps=0.1) -> np.ndarray:
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).ewm(alpha=1.0/p, adjust=False).mean().to_numpy()
    return a / ps


def selftest():
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d).iloc[:5000].reset_index(drop=True)
    c = df['close'].to_numpy(float)
    x = snr(c, 55)
    # مقایسه با محاسبهٔ حلقه‌ای در ۲۰۰ نقطه
    idx = np.arange(200, 5000, 24)
    diffs = [abs(x[t] - snr_naive(c, 55, t)) for t in idx if np.isfinite(x[t])]
    md = max(diffs)
    print(f'selftest snr: pts={len(diffs)} max_abs_diff={md:.2e}')
    assert md < 1e-9
    assert np.all(np.isnan(x[:55])), 'warmup must be NaN'
    # نبودِ look-ahead: تغییرِ close[t+1] رویدادِ t را عوض نکند ولی t+1 را بتواند
    le, sh = build_events(c, 55, 1.0)
    c2 = c.copy(); c2[3001] *= 1.05
    le2, sh2 = build_events(c2, 55, 1.0)
    assert le[3000] == le2[3000] and sh[3000] == sh2[3000], 'look-ahead detected!'
    assert np.array_equal(le[:3001], le2[:3001]), 'past events changed by future bar!'
    # هر رویداد یک‌بار در هر عبور
    assert not np.any(le & sh), 'long & short on same bar'
    print(f'selftest events: long={int(le.sum())} short={int(sh.sum())} '
          f'SNR range=[{np.nanmin(x):.2f},{np.nanmax(x):.2f}]')
    print('selftest PASSED — SNR صحیح، بدونِ look-ahead')


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
    if span_y < MIN_SPAN_YEARS:
        raise RuntimeError(f'E-16 guard: {tf} src={d["src"]} span={span_y:.2f}y < {MIN_SPAN_YEARS}y')
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
    baselines = {}                              # تشخیصیِ F3 (فقط train، کارت نیست)
    for K in GRID_K:
        wu = K + 60
        # پایهٔ درفتِ خام (TSM sign flip) با a=GRID_A[0]
        sl0 = round(GRID_A[0] * atr_med, 2); be0 = 100.0 * (sl0 + spread) / (2 * sl0)
        lb, sb = build_raw_drift_baseline(c, K)
        lb[:wu] = False; sb[:wu] = False
        for side in ('long', 'short', 'both'):
            tr0 = eval_config(df, lb, sb, sl0, sl0, HOLD, side)
            if tr0 is not None and len(tr0) >= 30:
                wr0 = 100.0 * float((tr0['pnl_pip'] > 0).mean())
                baselines[f'K{K}_rawdrift_{side}_a{GRID_A[0]}'] = dict(
                    n=len(tr0), wr=round(wr0, 2), edge_pp=round(wr0 - be0, 2))
        for theta in GRID_THETA:
            long_ev, short_ev = build_events(c, K, theta)
            long_ev[:wu] = False; short_ev[:wu] = False
            nL, nS = int(long_ev.sum()), int(short_ev.sum())
            for a in GRID_A:
                sl = round(a * atr_med, 2); tp = sl          # RR=1 قفلِ پیش‌ثبت
                be = 100.0 * (sl + spread) / (sl + tp)
                for side in ('long', 'short', 'both'):
                    tr = eval_config(df, long_ev, short_ev, sl, tp, HOLD, side)
                    if tr is None or len(tr) < 30:           # کفِ پیش‌ثبت
                        continue
                    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                    nn = len(tr); edge = wr - be
                    results.append(dict(
                        K=K, theta=theta, a=a, hold=HOLD, side=side,
                        sl_pip=sl, tp_pip=tp, be_wr=round(be, 2),
                        n=nn, wr=round(wr, 2), edge_pp=round(edge, 2),
                        score=round(edge * np.sqrt(nn), 1),
                        exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                        nL_ev=nL, nS_ev=nS))
        print(f'  K={K}: arms done {time.time()-t0:.0f}s', flush=True)

    results.sort(key=lambda r: r['score'], reverse=True)
    survivors = [r for r in results if r['edge_pp'] > 0]
    best = survivors[0] if survivors else None
    payload = dict(tf=tf, src=d['src'], n_all=n_all, half_idx=half,
                   span_years=d['span_years'],
                   atr_med_pip=atr_med, n_grid=N_GRID, n_trials=N_TRIALS,
                   rawdrift_baselines=baselines,
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
    long_ev, short_ev = build_events(c, best['K'], best['theta'])
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
    print(R.format_rqs2(f'S924_{tf}', res), flush=True)
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
