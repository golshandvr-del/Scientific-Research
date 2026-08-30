# -*- coding: utf-8 -*-
"""S921 — «ازسرگیریِ انتشارِ دانش»: خروجِ STC از اشباعِ خلاف‌روند × روندِ EMA | XAUUSD | MTF

پیش‌ثبت: `results/S921_PREREG_KNOWLEDGE_DIFFUSION_RESUMPTION.md` (commit bd8a8123)

فرضیه (هایک ۱۹۴۵ — «استفاده از دانش در جامعه»)
--------------------------------------------------------------------------------
انتشارِ دانش در قیمت تدریجی است؛ پول‌بک در روندِ مستقر مکثِ انتشار است نه پایانِ آن.
خروجِ Schaff Trend Cycle از اشباعِ خلاف‌روند، هم‌جهت با EMA بلندمدت = ازسرگیریِ
انتشار → ادامهٔ روند. صریحاً مومنتوم-همسو (درسِ S950-ACCEPT و S920-REJECT).

هارنس: کپیِ ساختاریِ s920 (Path C، نگهبانِ یک‌بار-لمس، null هندسی‌همتا)؛ فقط
سیگنال/شبکه عوض شده. STC برداری‌شده و در selftest علیه بانک راستی‌آزمایی می‌شود.

فازها:
  python3 strategies/s921_knowledge_diffusion.py selftest
  python3 strategies/s921_knowledge_diffusion.py discover M1     # فقط نیمهٔ اول
  python3 strategies/s921_knowledge_diffusion.py final M1        # یک‌بار، نیمهٔ دوم
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

OUT = os.path.join(ROOT, 'results', '_scan_S921')
SEED = 20260828
K_PERM = 2000
ATR_P = 89

# ---------------- شبکهٔ قفل‌شدهٔ پیش‌ثبت (بیرونش جست‌وجو ممنوع) ----------------
GRID_LO = [10, 25]
GRID_PT = [144, 377]
GRID_A = [1.618, 2.058]      # SL = a×ATR89 ؛ RR=1 ثابت (درسِ S950)
GRID_HOLD = [55, 144]
N_GRID = len(GRID_LO) * len(GRID_PT) * len(GRID_A) * len(GRID_HOLD)   # 16
N_TRIALS = N_GRID * 3        # ×۳ تصمیمِ جهت — 48 (مطابق پیش‌ثبت §۳)

TF_ORDER = ['M1', 'M3', 'M4', 'M5', 'M6', 'M10', 'M12', 'M15', 'M20',
            'M30', 'H1', 'H2', 'H3', 'H4', 'H6', 'H8', 'H12', 'D1', 'W1']


# ═══════════════ اندیکاتورهای برداری‌شده (تعریفِ عینِ بانک) ═══════════════

def _ema(x: np.ndarray, p: int) -> np.ndarray:
    """EMA با span=p (عینِ ema_s بانک: ewm(span=p, adjust=False))."""
    a = 2.0 / (p + 1.0)
    out = np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i-1] + a * (x[i] - out[i-1])
    return out


def _stoch_norm(x: np.ndarray, cycle: int) -> np.ndarray:
    """100*(x-min)/(max-min) روی پنجرهٔ rolling=cycle؛ NaN→50 (عینِ بانک،
    که rolling با min_periods=cycle است و fillna(50))."""
    n = len(x)
    out = np.full(n, 50.0)
    from numpy.lib.stride_tricks import sliding_window_view
    if n < cycle:
        return out
    W = sliding_window_view(x, cycle)          # ردیف j ⇔ i = cycle-1+j
    hh = W.max(axis=1); ll = W.min(axis=1)
    rng = hh - ll
    with np.errstate(divide='ignore', invalid='ignore'):
        st = 100.0 * (x[cycle-1:] - ll) / rng
    st = np.where(np.isfinite(st), st, 50.0)   # rng==0 → NaN → 50 (بانک: replace(0,nan)→fillna(50))
    out[cycle-1:] = st
    # بانک: rolling(min_periods=cycle) → قبل از cycle-1 مقدار NaN→50 است؛ همین‌جا 50 گذاشتیم
    return out


def stc_fast(close: np.ndarray, fast=23, slow=50, cycle=10) -> np.ndarray:
    """Schaff Trend Cycle — عینِ engine/indicator_bank.stc (selftest پایین)."""
    macd = _ema(close, fast) - _ema(close, slow)
    st1 = _stoch_norm(macd, cycle)
    d1 = _ema(st1, max(2, cycle // 2))
    st2 = _stoch_norm(d1, cycle)
    return _ema(st2, max(2, cycle // 2))


def ema_fast(close: np.ndarray, p: int) -> np.ndarray:
    return _ema(close, p)


def atr_pip(df: pd.DataFrame, p=ATR_P, ps=0.1) -> np.ndarray:
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    a = pd.Series(tr).ewm(alpha=1.0/p, adjust=False).mean().to_numpy()
    return a / ps


def selftest():
    """راستی‌آزماییِ stc_fast علیه بانک روی نمونهٔ کوچک."""
    from engine import indicator_bank as ib
    d = fd.load_fast('XAUUSD', 'H1')
    df = fd.as_dataframe(d).iloc[:4000].reset_index(drop=True)
    c = df['close'].to_numpy(float)
    fast = stc_fast(c)
    ref = ib.compute('stc', df).to_numpy()
    ok = np.isfinite(ref) & np.isfinite(fast)
    # بانک قبل از cycle-1 مقدار خاص خودش را دارد؛ مقایسه از اندیس امنِ 100 به بعد
    sl_ = slice(100, None)
    diff = float(np.abs(ref[sl_][ok[sl_]] - fast[sl_][ok[sl_]]).max())
    print(f'selftest stc: n={int(ok[sl_].sum())} max_abs_diff={diff:.2e}')
    assert diff < 1e-6, 'stc diverges from bank!'
    # EMA هم چک شود
    ref_e = df['close'].astype('float64').ewm(span=144, adjust=False).mean().to_numpy()
    diff_e = float(np.abs(ref_e - ema_fast(c, 144)).max())
    print(f'selftest ema144: max_abs_diff={diff_e:.2e}')
    assert diff_e < 1e-9
    print('selftest PASSED — نسخه‌های برداری عینِ بانک‌اند')


# ═══════════════════════════ سیگنال و ارزیابی ═══════════════════════════

def build_events(S, E, close, lo):
    """خروج STC از اشباعِ خلاف‌روند، مشروط به هم‌جهتی با EMA بلندمدت."""
    hi = 100.0 - lo
    n = len(S)
    long_ev = np.zeros(n, bool)
    short_ev = np.zeros(n, bool)
    prev, cur = S[:-1], S[1:]
    with np.errstate(invalid='ignore'):
        long_ev[1:] = (prev <= lo) & (cur > lo) & (close[1:] > E[1:])
        short_ev[1:] = (prev >= hi) & (cur < hi) & (close[1:] < E[1:])
    return long_ev, short_ev


def eval_config(df, long_ev, short_ev, sl_pip, tp_pip, hold, side):
    ls = pd.Series(long_ev if side in ('long', 'both') else np.zeros(len(df), bool))
    ss = pd.Series(short_ev if side in ('short', 'both') else np.zeros(len(df), bool))
    tr = se.simulate_trades(df, ls, ss, sl_pip=sl_pip, tp_pip=tp_pip,
                            asset='XAUUSD', max_hold=hold, allow_overlap=False)
    return tr


def measured_null(df, n_long, n_short, sl_pip, tp_pip, hold, k=K_PERM, seed=SEED,
                  warmup=400):
    """مدلِ صفرِ اندازه‌گیری‌شده per-side — عینِ s920 (همان شبیه‌ساز، زمانِ تصادفی)."""
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
    """بارگذاریِ کم-حافظه (درسِ گامِ ۴۸ — کپیِ دوم روی M1 سندباکس را می‌کُشد)."""
    d = fd.load_fast('XAUUSD', tf)
    n_all = int(d['n_bars']) if 'n_bars' in d else len(d['close'])
    sl_ = slice(lo, hi)
    df = pd.DataFrame({k: d[k][sl_] for k in
                       ('time', 'open', 'high', 'low', 'close', 'volume')},
                      copy=False)
    meta = dict(src=d['src'], n_all=n_all)
    return meta, df


def discover(tf):
    """فاز ۱ — جست‌وجوی شبکهٔ ۱۶تایی فقط روی نیمهٔ اول."""
    os.makedirs(OUT, exist_ok=True)
    d, df = prep(tf)
    n_all = d['n_all']
    half = n_all // 2
    df = df.iloc[:half]
    c = np.ascontiguousarray(df['close'].to_numpy(float))
    import gc; gc.collect()
    t0 = time.time()
    S = stc_fast(c)
    apip = atr_pip(df)
    atr_med = float(np.nanmedian(apip))
    spread = se.ASSETS['XAUUSD']['spread_pip']
    print(f'[{tf}] bars_all={n_all} half={half} src={d["src"]} '
          f'atr{ATR_P}_med={atr_med:.1f}pip  ind={time.time()-t0:.0f}s', flush=True)

    results = []
    for pt in GRID_PT:
        E = ema_fast(c, pt)
        for lo_thr in GRID_LO:
            long_ev, short_ev = build_events(S, E, c, lo_thr)
            # warmup: قبل از max(pt, slow=50)+cycle رویداد معتبر نیست
            wu = pt + 60
            long_ev[:wu] = False; short_ev[:wu] = False
            nL, nS = int(long_ev.sum()), int(short_ev.sum())
            for a in GRID_A:
                sl = round(a * atr_med, 2)
                tp = sl                                   # RR=1 ثابتِ پیش‌ثبت
                be = 100.0 * (sl + spread) / (sl + tp)
                for hold in GRID_HOLD:
                    for side in ('long', 'short', 'both'):
                        tr = eval_config(df, long_ev, short_ev, sl, tp, hold, side)
                        if tr is None or len(tr) < 30:    # کفِ پیش‌ثبت §۴
                            continue
                        wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                        nn = len(tr)
                        edge = wr - be
                        results.append(dict(
                            lo=lo_thr, pt=pt, a=a, hold=hold, side=side,
                            sl_pip=sl, tp_pip=tp, be_wr=round(be, 2),
                            n=nn, wr=round(wr, 2), edge_pp=round(edge, 2),
                            score=round(edge * np.sqrt(nn), 1),
                            exp_pip=round(float(tr['pnl_pip'].mean()), 2),
                            nL_ev=nL, nS_ev=nS))
            print(f'  pt={pt} lo={lo_thr}: events L={nL} S={nS} '
                  f'done {time.time()-t0:.0f}s', flush=True)

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
    """فاز ۲ — یک آزمونِ یگانه روی نیمهٔ دوم با پیکربندیِ قفل‌شدهٔ train."""
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
        print(f'[{tf}] ⛔ نیمهٔ دوم قبلاً لمس شده — مسیرِ C اجازهٔ تکرار نمی‌دهد')
        with open(guard) as f:
            return json.load(f)

    d, df = prep(tf)
    n_all = d['n_all']
    half = n_all // 2
    c = df['close'].to_numpy(float)
    S = stc_fast(c)
    E = ema_fast(c, best['pt'])
    long_ev, short_ev = build_events(S, E, c, best['lo'])
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
    print(R.format_rqs2(f'S921_{tf}', res), flush=True)
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
