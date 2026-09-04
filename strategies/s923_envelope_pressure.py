# -*- coding: utf-8 -*-
"""S923 — «فشارِ پایدار بر پوشِ آماری» (Band-Walk Persistence) | XAUUSD | MTF

پیش‌ثبت: `results/S923_PREREG_SUSTAINED_ENVELOPE_PRESSURE.md` (commit 4876f7be — قبل از هر تست)

فرضیه (هایک + درسِ S965/S922)
--------------------------------------------------------------------------------
یک closeِ تکی بیرونِ پوشِ بولینگر ممکن است نویز باشد (درس S922: شکستِ خام ≈ درفت،
z≈1.4). اما «فشارِ پایدار» — M کندلِ متوالی بیرونِ پوش — امضایِ جریانِ سفارشِ مطلعِ
پیوسته است: دانشِ پراکنده سریع‌تر از تطبیقِ پوش در قیمت جذب می‌شود. شمارندهٔ M همان
فیلترِ کیفیتِ اطلاعات‌افزاست (درس S965: فیلترِ شکل باید lift را بالا ببرد، نه n را بسوزاند).

هارنس: کپیِ ساختاریِ s922 (Path C، نگهبانِ یک‌بار-لمس، null هندسی‌همتا).

فازها:
  python3 strategies/s923_envelope_pressure.py selftest
  python3 strategies/s923_envelope_pressure.py discover M1
  python3 strategies/s923_envelope_pressure.py final M1
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

OUT = os.path.join(ROOT, 'results', '_scan_S923')
SEED = 20260904
K_PERM = 2000
ATR_P = 21
BAND_K = 2.0                                   # منجمد در پیش‌ثبت
A_FROZEN = 1.618                               # منجمد در پیش‌ثبت

# ---------------- شبکهٔ قفل‌شدهٔ پیش‌ثبت ----------------
GRID_P = [20, 55]
GRID_M = [2, 3]
GRID_HOLD = [55, 144]
N_GRID = len(GRID_P) * len(GRID_M) * len(GRID_HOLD)   # 8
N_TRIALS = N_GRID * 3                                  # 24

TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1']


# ═══════════════ سیگنال (برداری، بدون look-ahead) ═══════════════

def bollinger(close: np.ndarray, p: int, k: float = BAND_K):
    """باند بولینگر استاندارد: پنجرهٔ p منتهی به t (شامل خودِ t).
    ورود در openِ کندل بعد ⇒ بدون look-ahead."""
    s = pd.Series(close)
    mid = s.rolling(p).mean().to_numpy()
    sd = s.rolling(p).std(ddof=0).to_numpy()
    return mid + k * sd, mid - k * sd


def streak(cond: np.ndarray) -> np.ndarray:
    """طولِ رشتهٔ متوالیِ True منتهی به t (شاملِ t). صفر اگر cond[t]=False."""
    n = len(cond)
    out = np.zeros(n, dtype=np.int64)
    run = 0
    for i in range(n):
        run = run + 1 if cond[i] else 0
        out[i] = run
    return out


def streak_fast(cond: np.ndarray) -> np.ndarray:
    """نسخهٔ برداریِ streak: run[t] = t - آخرین اندیسِ False قبل یا مساوی t."""
    n = len(cond)
    idx = np.arange(n)
    last_false = np.where(~cond, idx, -1)
    last_false = np.maximum.accumulate(last_false)
    return np.where(cond, idx - last_false, 0)


def build_events(close: np.ndarray, p: int, m: int):
    """رویدادِ لبهٔ تازه: رشتهٔ closeهای بیرونِ باند دقیقاً به m می‌رسد."""
    upper, lower = bollinger(close, p)
    with np.errstate(invalid='ignore'):
        above = close > upper
        below = close < lower
    above = np.where(np.isnan(upper), False, above)
    below = np.where(np.isnan(lower), False, below)
    ru = streak_fast(above)
    rd = streak_fast(below)
    long_ev = ru == m       # فقط لحظهٔ رسیدن به m — یک‌بار در هر رشته
    short_ev = rd == m
    return long_ev, short_ev, above, below


def atr_pip(df: pd.DataFrame, p=ATR_P, ps=0.1) -> np.ndarray:
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).ewm(alpha=1.0/p, adjust=False).mean().to_numpy()
    return a / ps


def selftest():
    """streak_fast علیه حلقهٔ ساده + نبودِ look-ahead در رویداد."""
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d).iloc[:5000].reset_index(drop=True)
    c = df['close'].to_numpy(float)
    upper, lower = bollinger(c, 20)
    above = np.where(np.isnan(upper), False, c > upper)
    s1 = streak(above)
    s2 = streak_fast(above)
    assert np.array_equal(s1, s2), 'streak_fast diverges from naive loop!'
    print(f'selftest streak: n={len(s1)} identical={np.array_equal(s1, s2)} '
          f'max_run={int(s1.max())}')
    # نبودِ look-ahead: تغییرِ close[t+1] نباید رویدادِ t را عوض کند
    le, se_, _, _ = build_events(c, 20, 2)
    c2 = c.copy(); c2[3001] += 500.0
    le2, se2, _, _ = build_events(c2, 20, 2)
    assert le[3000] == le2[3000] and se_[3000] == se2[3000], 'look-ahead detected!'
    # صحتِ باند: t جزوِ پنجره است (بولینگر استاندارد) — ورود کندلِ بعد
    ref_u = (pd.Series(c).rolling(20).mean()
             + BAND_K * pd.Series(c).rolling(20).std(ddof=0)).to_numpy()
    ok = np.isfinite(ref_u) & np.isfinite(upper)
    diff = float(np.abs(ref_u[ok] - upper[ok]).max())
    print(f'selftest bollinger: max_abs_diff={diff:.2e}')
    assert diff < 1e-9
    print('selftest PASSED — streak برداری صحیح، بدونِ look-ahead')


# ═══════════════════════════ ارزیابی (عینِ s922) ═══════════════════════════

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
    c = np.ascontiguousarray(df['close'].to_numpy(float))
    import gc; gc.collect()
    t0 = time.time()
    apip = atr_pip(df)
    atr_med = float(np.nanmedian(apip))
    spread = se.ASSETS['XAUUSD']['spread_pip']
    sl = round(A_FROZEN * atr_med, 2)
    tp = sl                                    # RR=1 قفلِ پیش‌ثبت
    be = 100.0 * (sl + spread) / (sl + tp)
    print(f'[{tf}] bars_all={n_all} half={half} src={d["src"]} '
          f'atr{ATR_P}_med={atr_med:.1f}pip sl=tp={sl}pip be={be:.2f}%', flush=True)

    results = []
    baselines = {}                              # تشخیصیِ F3: بازوی M=1 (فقط train، کارت نیست)
    for p in GRID_P:
        # پایهٔ M=1 برای داوریِ ابطال‌گر F3 — جزوِ trialها نیست
        le1, se1, _, _ = build_events(c, p, 1)
        wu = p + ATR_P + 20
        le1[:wu] = False; se1[:wu] = False
        tr1 = eval_config(df, le1, se1, sl, tp, GRID_HOLD[0], 'both')
        if tr1 is not None and len(tr1) >= 30:
            wr1 = 100.0 * float((tr1['pnl_pip'] > 0).mean())
            baselines[f'p{p}_M1_both_h{GRID_HOLD[0]}'] = dict(
                n=len(tr1), wr=round(wr1, 2), edge_pp=round(wr1 - be, 2))
        for m in GRID_M:
            long_ev, short_ev, _, _ = build_events(c, p, m)
            long_ev[:wu] = False; short_ev[:wu] = False
            nL, nS = int(long_ev.sum()), int(short_ev.sum())
            for hold in GRID_HOLD:
                for side in ('long', 'short', 'both'):
                    tr = eval_config(df, long_ev, short_ev, sl, tp, hold, side)
                    if tr is None or len(tr) < 30:      # کفِ پیش‌ثبت
                        continue
                    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                    nn = len(tr)
                    edge = wr - be
                    results.append(dict(
                        p=p, m=m, a=A_FROZEN, hold=hold, side=side,
                        sl_pip=sl, tp_pip=tp, be_wr=round(be, 2),
                        n=nn, wr=round(wr, 2), edge_pp=round(edge, 2),
                        score=round(edge * np.sqrt(nn), 1),
                        exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                        nL_ev=nL, nS_ev=nS))
            print(f'  p={p}: M-arms done {time.time()-t0:.0f}s', flush=True)

    results.sort(key=lambda r: r['score'], reverse=True)
    survivors = [r for r in results if r['edge_pp'] > 0]
    best = survivors[0] if survivors else None
    payload = dict(tf=tf, src=d['src'], n_all=n_all, half_idx=half,
                   atr_med_pip=atr_med, n_grid=N_GRID, n_trials=N_TRIALS,
                   m1_baselines=baselines,
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
    long_ev, short_ev, _, _ = build_events(c, best['p'], best['m'])
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
    print(R.format_rqs2(f'S923_{tf}', res), flush=True)
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
