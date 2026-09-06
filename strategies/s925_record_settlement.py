# -*- coding: utf-8 -*-
"""S925 — «جهشِ رکوردیِ تسویه» (Record Settlement Jump, Drift-Aligned) | XAUUSD | MTF

پیش‌ثبت: `results/S925_PREREG_RECORD_SETTLEMENT_JUMP.md` (commit aba8546b — قبل از هر تست)

فرضیه (هایک + شجرهٔ S604/S950/S965/S919/S749)
--------------------------------------------------------------------------------
فقط قیمتِ تسویه (close) دانش را منتقل می‌کند؛ مسیرِ درون‌کندلی نویزِ چانه‌زنی است. رویداد:
|ln(c[t]/c[t-1])| رکوردِ رتبه‌ایِ W کندلِ اخیر (بدون آستانهٔ توزیعی، بدون ATR/z). جهت follow.
گیتِ درفت ۶۰-روزه (قراردادِ S604) به‌عنوان بازوی grid؛ F3 روی holdout مقایسه می‌شود (درس L-S924-2).

هارنس: کپیِ ساختاریِ s924 (Path C، نگهبانِ یک‌بار-لمس، null هندسی‌همتا، K=2000).

فازها:
  python3 strategies/s925_record_settlement.py selftest
  python3 strategies/s925_record_settlement.py discover H8
  python3 strategies/s925_record_settlement.py final H8
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

OUT = os.path.join(ROOT, 'results', '_scan_S925')
SEED = 20260906
K_PERM = 2000
ATR_P = 21
HOLD = 55                                      # منجمد در پیش‌ثبت
MIN_SPAN_YEARS = 14.0                          # E-16 guard (mt5_full M1 = 5,000,000 bars = 14.34y — MT5 export cap; the short trap files are 2.8y/6.4y)

# ---------------- شبکهٔ قفل‌شدهٔ پیش‌ثبت ----------------
GRID_W = [34, 89]
GRID_GATE = ['ungated', 'gated']
GRID_A = [1.618, 2.058]
N_GRID = len(GRID_W) * len(GRID_GATE) * len(GRID_A)    # 8
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

def abs_ret(close: np.ndarray) -> np.ndarray:
    lc = np.log(close)
    r = np.diff(lc, prepend=np.nan)
    return r, np.abs(r)


def rolling_prev_max(x: np.ndarray, W: int) -> np.ndarray:
    """max(x[t-W..t-1]) — پنجرهٔ W کندلِ قبل، بدونِ خودِ t. NaN در warmup."""
    m = pd.Series(x).rolling(W).max().to_numpy()      # max(x[t-W+1..t])
    out = np.full_like(x, np.nan)
    out[W:] = m[W - 1:-1]                              # shift +1 ⇒ max(x[t-W..t-1])
    return out


def build_events(close: np.ndarray, W: int, gate: str, K: int):
    """رکوردِ رتبه‌ایِ |r[t]| نسبت به W کندلِ قبل؛ جهت = علامتِ r[t]؛ گیتِ درفتِ ۶۰ روزه."""
    r, R = abs_ret(close)
    prev_max = rolling_prev_max(R, W)
    with np.errstate(invalid='ignore'):
        rec = (R > prev_max) & np.isfinite(prev_max) & np.isfinite(R)
        long_ev = rec & (r > 0)
        short_ev = rec & (r < 0)
    if gate == 'gated':
        n = len(close)
        prev_c = np.concatenate([[np.nan], close[:-1]])                 # close[t-1]
        lag_c = np.concatenate([np.full(K + 1, np.nan), close[:-(K + 1)]])  # close[t-1-K]
        with np.errstate(invalid='ignore'):
            up = prev_c > lag_c
            dn = prev_c < lag_c
        up = np.where(np.isfinite(lag_c), up, False)
        dn = np.where(np.isfinite(lag_c), dn, False)
        long_ev = long_ev & up
        short_ev = short_ev & dn
    return long_ev, short_ev


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
    r, R = abs_ret(c)
    pm = rolling_prev_max(R, 34)
    # مقایسه با حلقهٔ ساده
    bad = 0
    for t in range(40, 5000, 17):
        ref = R[t - 34:t].max()
        if abs(pm[t] - ref) > 1e-12: bad += 1
    print(f'selftest prev_max: checked={len(range(40,5000,17))} mismatches={bad}')
    assert bad == 0
    assert np.all(np.isnan(pm[:34]))
    # رکورد: خودِ t در پنجره نیست — اسپایک در t نباید رکوردِ t را «خنثی» کند
    le, sh = build_events(c, 34, 'ungated', drift_K('H1'))
    c2 = c.copy(); c2[3001] *= 1.03
    le2, sh2 = build_events(c2, 34, 'ungated', drift_K('H1'))
    assert np.array_equal(le[:3001], le2[:3001]) and np.array_equal(sh[:3001], sh2[:3001]), 'look-ahead!'
    assert le2[3001] and not sh2[3001], 'spike up at 3001 must be a long record event'
    assert not np.any(le & sh)
    # گیت: با درفت مثبت فقط long باقی می‌ماند
    lg, sg = build_events(c, 34, 'gated', drift_K('H1'))
    assert lg.sum() <= le.sum() and sg.sum() <= sh.sum()
    print(f'selftest events W=34: ungated L={int(le.sum())} S={int(sh.sum())} | gated L={int(lg.sum())} S={int(sg.sum())} | K_H1={drift_K("H1")}')
    print('selftest PASSED — رکوردِ رتبه‌ای صحیح، بدونِ look-ahead')


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
    for W in GRID_W:
        wu = max(W, K) + 60
        for gate in GRID_GATE:
            long_ev, short_ev = build_events(c, W, gate, K)
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
                        W=W, gate=gate, K=K, a=a, hold=HOLD, side=side,
                        sl_pip=sl, tp_pip=tp, be_wr=round(be, 2),
                        n=nn, wr=round(wr, 2), edge_pp=round(edge, 2),
                        score=round(edge * np.sqrt(nn), 1),
                        exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                        nL_ev=nL, nS_ev=nS))
        print(f'  W={W}: arms done {time.time()-t0:.0f}s', flush=True)

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
    long_ev, short_ev = build_events(c, best['W'], best['gate'], best['K'])
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
    print(R.format_rqs2(f'S925_{tf}', res), flush=True)
    # F3-holdout (report-only، اعلام‌شده در پیش‌ثبت §4): بازویِ گیتِ مقابل با همان W/a/side
    other = 'gated' if best['gate'] == 'ungated' else 'ungated'
    lo2, so2 = build_events(c, best['W'], other, best['K'])
    lo2[:half] = False; so2[:half] = False
    tr2 = eval_config(df, lo2, so2, sl, tp, hold, side)
    f3 = None
    if tr2 is not None and len(tr2) >= 5:
        wr2 = 100.0 * float((tr2['pnl_pip'] > 0).mean())
        f3 = dict(other_gate=other, n=len(tr2), wr=round(wr2, 2),
                  exp_pip=round(float(tr2['pnl_pip'].mean()), 2),
                  official_wr=round(100.0 * float((tr['pnl_pip'] > 0).mean()), 2),
                  note='report-only holdout diagnostic; no verdict, no card')
        print(f'[{tf}] F3-holdout: official({best["gate"]}) WR={f3["official_wr"]} n={len(tr)} | {other} WR={wr2:.2f} n={len(tr2)}', flush=True)
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
