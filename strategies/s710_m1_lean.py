# -*- coding: utf-8 -*-
"""
S710 — کارتِ M1 با محاسبهٔ کم‌حافظه (lean) — همان ثابت‌های منجمدِ پیش‌ثبت
==========================================================================
چرا این فایل؟ اجرای s710_compression_expansion روی M1 (۵ میلیون کندل) دو بار
با OOM کشته شد (سندباکس ۹۸۵MB). علت: مسیرِ pandas (ib.compute + concat در
_tr + ewm) چند نسخهٔ میانیِ ۴۰MB می‌سازد و مجموع از ۶۸۰MB می‌گذرد.

این فایل **هیچ پارامتری را تغییر نمی‌دهد** — همان قاعدهٔ پیش‌ثبت را با
عملیاتِ numpy/scipy/numba بازمی‌نویسد و برابریِ عددی با بانکِ رسمی را
پیش از داوری، روی یک برشِ ۲۰۰هزار کندلی **اثبات** می‌کند (parity gate).
اگر برابری شکست بخورد، اسکریپت می‌ایستد و داوری نمی‌کند.

داوری، مدلِ صفر، K_PERM=500، seed و split دقیقاً همان s710 است.
"""
import gc
import json
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
from scipy.ndimage import maximum_filter1d, minimum_filter1d
from numba import njit

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from tools import s434_fast_data as fd                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr                      # noqa: E402
from strategies.s710_compression_expansion import (                # noqa: E402
    ASSET, CHOP_TH, BRK_N, ATR_P, SL_K, RR, WARMUP, SEED, N_TRIALS,
    SPLIT_FRAC, OUT, build_null, git_checkpoint)

CHOP_P = 55
TF = 'M1'
K_PERM_M1 = 500


def roll_max_past(a, p):
    """معادلِ بیت‌به‌بیتِ pandas: rolling(p).max() — پنجرهٔ گذشته‌نگر.

    ⚠️ origin باید **مثبت** باشد (+(p-1)//2) تا پنجره [i-p+1, i] شود؛
    علامتِ منفی فیلتر را آینده‌نگر می‌کند = look-ahead. دروازهٔ برابری
    این خطا را در نخستین اجرا گرفت و متوقف کرد — دقیقاً وظیفه‌اش."""
    out = maximum_filter1d(a, size=p, mode='nearest', origin=(p - 1) // 2)
    out[:p - 1] = np.nan
    return out


def roll_min_past(a, p):
    out = minimum_filter1d(a, size=p, mode='nearest', origin=(p - 1) // 2)
    out[:p - 1] = np.nan
    return out


def roll_sum_past(a, p):
    cs = np.concatenate(([0.0], np.cumsum(a)))
    out = np.full(len(a), np.nan)
    out[p - 1:] = cs[p:] - cs[:-p]
    return out


@njit(cache=True)
def wilder_rma(x, p):
    """ewm(alpha=1/p, adjust=False).mean() — همان ATR بانک/‌s710."""
    n = len(x)
    out = np.empty(n)
    a = 1.0 / p
    prev = x[0]
    out[0] = prev
    for i in range(1, n):
        prev = a * x[i] + (1.0 - a) * prev
        out[i] = prev
    return out


def true_range(h, l, c):
    pc = np.empty_like(c)
    pc[0] = np.nan
    pc[1:] = c[:-1]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]   # pandas max با skipna روی سطرِ اول همین را می‌دهد
    return tr


def lean_layers(h, l, c):
    """chop55، کانالِ 13 و ATR21 — همه با حافظهٔ کمینه."""
    tr = true_range(h, l, c)
    sum_tr = roll_sum_past(tr, CHOP_P)
    hh55 = roll_max_past(h, CHOP_P)
    ll55 = roll_min_past(l, CHOP_P)
    rng = hh55 - ll55
    rng[rng == 0] = np.nan
    chop = 100.0 * np.log10(sum_tr / rng) / np.log10(CHOP_P)
    del sum_tr, hh55, ll55, rng
    gc.collect()

    hh13 = roll_max_past(h, BRK_N)
    ll13 = roll_min_past(l, BRK_N)
    # shift(1)
    hh13s = np.empty_like(hh13); hh13s[0] = np.nan; hh13s[1:] = hh13[:-1]
    ll13s = np.empty_like(ll13); ll13s[0] = np.nan; ll13s[1:] = ll13[:-1]
    del hh13, ll13

    atr = wilder_rma(tr, ATR_P)
    del tr
    gc.collect()

    comp = chop >= CHOP_TH
    long_sig = comp & (c > hh13s)
    short_sig = comp & (c < ll13s)
    long_sig[:WARMUP] = False
    short_sig[:WARMUP] = False
    return long_sig, short_sig, atr


def parity_gate():
    """اثباتِ برابری با بانکِ رسمی روی برشِ M15 (سبک) — پیش از هر داوری."""
    from engine import indicator_bank as ib
    d = fd.load_fast(ASSET, 'M15')
    df = fd.as_dataframe(d).iloc[:200_000].reset_index(drop=True)
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)

    ref_chop = ib.compute('chop_fib_55', df).to_numpy()
    ref_hh = df['high'].rolling(BRK_N).max().shift(1).to_numpy()
    ref_ll = df['low'].rolling(BRK_N).min().shift(1).to_numpy()
    pc = df['close'].shift(1)
    ref_tr = pd.concat([(df['high'] - df['low']),
                        (df['high'] - pc).abs(),
                        (df['low'] - pc).abs()], axis=1).max(axis=1)
    ref_atr = ref_tr.ewm(alpha=1.0 / ATR_P, adjust=False).mean().to_numpy()

    ls, ss, atr = lean_layers(h, l, c)
    tr_l = true_range(h, l, c)
    sum_tr = roll_sum_past(tr_l, CHOP_P)
    hh55 = roll_max_past(h, CHOP_P); ll55 = roll_min_past(l, CHOP_P)
    rng = hh55 - ll55; rng[rng == 0] = np.nan
    my_chop = 100.0 * np.log10(sum_tr / rng) / np.log10(CHOP_P)
    hh13 = roll_max_past(h, BRK_N)
    my_hh = np.empty_like(hh13); my_hh[0] = np.nan; my_hh[1:] = hh13[:-1]
    ll13 = roll_min_past(l, BRK_N)
    my_ll = np.empty_like(ll13); my_ll[0] = np.nan; my_ll[1:] = ll13[:-1]

    def close_eq(a, b, tol=1e-9):
        m = np.isfinite(a) & np.isfinite(b)
        return np.allclose(a[m], b[m], atol=tol, rtol=0), int(m.sum())

    ok1, n1 = close_eq(my_chop, ref_chop)
    ok2, n2 = close_eq(my_hh, ref_hh)
    ok3, n3 = close_eq(my_ll, ref_ll)
    ok4, n4 = close_eq(atr, ref_atr, tol=1e-7)
    # سیگنال‌های مرجع
    comp = ref_chop >= CHOP_TH
    ref_ls = comp & (c > ref_hh); ref_ls[:WARMUP] = False
    ref_ss = comp & (c < ref_ll); ref_ss[:WARMUP] = False
    sig_eq = bool(np.array_equal(np.nan_to_num(ls), np.nan_to_num(ref_ls)) and
                  np.array_equal(np.nan_to_num(ss), np.nan_to_num(ref_ss)))
    print(f'parity: chop={ok1}({n1}) hh13={ok2}({n2}) ll13={ok3}({n3}) '
          f'atr={ok4}({n4}) signals_identical={sig_eq}', flush=True)
    if not (ok1 and ok2 and ok3 and ok4 and sig_eq):
        raise RuntimeError('PARITY FAILED — داوری متوقف شد؛ ریاضیات یکی نیست.')
    print('parity gate PASSED — lean == official bank\n', flush=True)


def main():
    parity_gate()
    gc.collect()

    t0 = time.time()
    print(f'================ S710 · {ASSET} · {TF} (lean) ================',
          flush=True)
    d = fd.load_fast(ASSET, TF)
    src = d['src']
    assert 'mt5_full' in src, f'E-16 guard: src={src}'
    h = d['high'].astype(np.float64, copy=False)
    l = d['low'].astype(np.float64, copy=False)
    c = d['close'].astype(np.float64, copy=False)
    n = len(c)
    print(f'  src={src}  bars={n:,}  years={d["span_years"]:.2f}', flush=True)

    hold = fd.hold_bars_for(TF)               # 1440 = ۲۴ ساعتِ واقعی
    pip = se.ASSETS[ASSET]['pip']

    long_sig, short_sig, atr = lean_layers(h, l, c)
    n_sig = int(long_sig.sum() + short_sig.sum())
    print(f'  signals={n_sig} (L={int(long_sig.sum())} '
          f'S={int(short_sig.sum())})  hold={hold}', flush=True)

    df = fd.as_dataframe(d)                   # copy=False — ارجاع، نه کپی
    sl_pip_arr = SL_K * atr / pip
    tp_pip_arr = RR * sl_pip_arr
    tr = se.simulate_trades(df, long_sig, short_sig, sl_pip_arr, tp_pip_arr,
                            ASSET, max_hold=hold, allow_overlap=False)
    del long_sig, short_sig, tp_pip_arr
    gc.collect()
    print(f'  trades={len(tr)}  wr={100 * (tr["pnl_pip"] > 0).mean():.2f}%  '
          f'exp={tr["pnl_pip"].mean():.2f} pip  [{time.time() - t0:.0f}s]',
          flush=True)

    valid = np.arange(WARMUP, n - hold - 1)
    nL = int((tr['direction'] == 'long').sum())
    nS = int(len(tr) - nL)
    rng_ = np.random.default_rng(SEED)
    sl_dist_arr = SL_K * atr
    print(f'  building measured null: k={K_PERM_M1} …', flush=True)
    null = build_null(df, valid, sl_dist_arr, nL, nS, hold, K_PERM_M1, rng_)

    sl_med = float(np.median(tr['sl_pip'].values))
    tp_med = float(RR * sl_med)
    split_bar = int(SPLIT_FRAC * n)
    res = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                            bar_time=d['time'], close=c,
                            null={k: {kk: vv for kk, vv in v.items()
                                      if kk != 'uncond_pool'}
                                  for k, v in null.items()},
                            n_trials=N_TRIALS, split_bar=split_bar)
    print('', flush=True)
    print(rqs2.format_rqs2(f'S710_CompExp_{TF}', res), flush=True)

    os.makedirs(OUT, exist_ok=True)
    payload = dict(tf=TF, src=src, is_full=True, family=True,
                   n_bars=int(n), span_years=float(d['span_years']),
                   hold=int(hold), n_signals=n_sig,
                   n_trades=int(len(tr)), n_long=nL, n_short=nS,
                   sl_pip_med=sl_med, tp_pip_med=tp_med,
                   wr=float(100 * (tr['pnl_pip'] > 0).mean()),
                   exp_pip=float(tr['pnl_pip'].mean()),
                   null=null, rqs2=res, k_perm=K_PERM_M1,
                   n_trials=N_TRIALS, split_bar=split_bar, seed=SEED,
                   lean=True, elapsed_s=round(time.time() - t0, 1))
    with open(f'{OUT}/{TF}.json', 'w') as f:
        json.dump(payload, f, ensure_ascii=False, default=str, indent=1)
    tr.to_csv(f'{OUT}/{TF}_trades.csv', index=False)
    print(f'  saved -> {OUT}/{TF}.json  [{time.time() - t0:.0f}s]', flush=True)
    git_checkpoint(TF)


if __name__ == '__main__':
    main()
