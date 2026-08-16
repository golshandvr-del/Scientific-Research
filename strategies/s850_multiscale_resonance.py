# -*- coding: utf-8 -*-
"""
S850 — Multiscale Resonance (تشدیدِ چندمقیاسی) — XAUUSD فقط
================================================================================
پیش‌ثبت : results/S850_PREREG_MULTISCALE_RESONANCE.md  (commit a635acd7)
داور    : engine/rqs2.compute_rqs2 (حکمِ موتور عیناً گزارش می‌شود)
مسیرِ چندگانگی: C (holdout) — اکتشاف فقط روی ۶۰٪ نخست؛ یک قضاوت روی کلِ داده
                با split_bar. n_trials = 36 (۲ مجموعه‌مقیاس × ۳k × ۳rr × ۲سمت).

فرضیهٔ فراکتالی (ماندلبرو):
  وقتی علامتِ بازده در سه مقیاسِ کندلیِ بسیار دور از هم (فیبوناچی) هم‌جهت
  می‌شود، فرایندِ قیمت در «تشدیدِ بین‌مقیاسی» است. ادعا: این تشدید در لحظهٔ
  *تولدش* (اولین کندلِ هم‌ترازی) حاملِ اطلاعِ جهت‌دار است — نه در ادامه‌اش.
  مقیاس‌ها عمداً در فضای کندل تعریف شده‌اند: خودِ فرضیهٔ خودمتشابهی می‌گوید
  معنای قاعده با تغییرِ TF حفظ می‌شود (درسِ S139).

هندسهٔ منجمد (هیچ جست‌وجویی خارجِ این شبکه نیست):
  SL = k·ATR(34)  ,  k  ∈ {1.272, 1.618, 2.058}   (کفِ ۵ pip)
  TP = rr·SL      ,  rr ∈ {1.0, 1.272, 1.618}      (TP ≥ SL همیشه)
  max_hold = 34   —  قفلِ سه‌گانه: (2.058·1.618)² ≈ 11.1 ≤ 34 ✅

قانونِ «اندک اندک»: هر TF که تمام شود فوراً results/_scan_S850/<TF>.json
نوشته می‌شود.  EURUSD به استثنای صریحِ کاربر حذف است.
"""
import sys
import os
import json
import gc

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from engine import rqs2                                            # noqa: E402
from strategies.s348_rr_sweep import (queue_rr, trades_df,          # noqa: E402
                                      cost_pip)
from tools import s434_fast_data as fd                              # noqa: E402

# ==================== پارامترهای منجمدِ پیش‌ثبت‌شده ====================
ASSET = 'XAUUSD'
SCALE_SETS = ((8, 34, 144), (5, 21, 89))
K_SL = (1.272, 1.618, 2.058)
RRS = (1.0, 1.272, 1.618)
ATR_P = 34
MAX_HOLD = 34
SPLIT_FRAC = 0.60
N_TRIALS = 36                    # 2 × 3 × 3 × 2 سمت
N_PERM = 600                     # K ≥ 500
MAX_UNCOND = 50_000              # سقفِ نمونهٔ WR غیرشرطی (بهداشتِ حافظه؛ M1 با
                                 # 200k در سندباکسِ ۹۸۵MB به OOM-Kill خورد)
MAX_NULL_POOL = 1_000_000        # سقفِ استخرِ کندل‌های مجاز برای مدلِ صفر —
                                 # زیرمجموعهٔ تصادفی از تصادفی همچنان تصادفی
                                 # است؛ فقط قیدِ حافظه (M1: 5M→۱M اندیس)
SEED = 20260811
EXPLORE_MIN_N = 30
SL_FLOOR_PIP = 5.0
OUT = 'results/_scan_S850'


def atr_series(df, p=ATR_P):
    """ATR وایلدر (فضای قیمت) — با ewm پانداز (C-سرعت، بدونِ حلقهٔ پایتونی)."""
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    cp = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - cp), np.abs(l - cp)))
    atr = pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().values
    atr[:p] = np.nan                       # گرم‌شدنِ ناکامل = نامعتبر
    return atr


def resonance_signals(close, scales):
    """
    تولدِ هم‌ترازی: هر سه sign(close[i]−close[i−L]) هم‌جهت شوند و در کندلِ
    قبل هم‌جهت نبوده باشند. forward-safe: فقط از گذشته می‌خوانَد؛ ورود در i+1
    توسطِ queue_rr انجام می‌شود.
    """
    n = len(close)
    L1, L2, L3 = scales
    up = np.zeros(n, dtype=bool)
    dn = np.zeros(n, dtype=bool)
    s = np.ones(n, dtype=bool)   # همه +
    t = np.ones(n, dtype=bool)   # همه −
    for L in scales:
        d = np.full(n, np.nan)
        d[L:] = close[L:] - close[:-L]
        s &= (d > 0)
        t &= (d < 0)
    up[1:] = s[1:] & ~s[:-1]     # تولدِ هم‌ترازیِ صعودی
    dn[1:] = t[1:] & ~t[:-1]
    up[:L3 + 1] = False
    dn[:L3 + 1] = False
    return up, dn


def combo_trades(df, up, dn, atr, k, rr, lo, hi, pip):
    """معاملاتِ یک ترکیب روی بازهٔ سیگنالِ [lo, hi)؛ خروجی st یا None."""
    sig_mask = (up | dn)
    idx = np.where(sig_mask)[0]
    idx = idx[(idx >= lo) & (idx < hi)]
    a = atr[idx]
    ok = np.isfinite(a) & (a > 0)
    idx, a = idx[ok], a[ok]
    if len(idx) == 0:
        return None
    is_long = up[idx]
    sl_dist = np.maximum(k * a, SL_FLOOR_PIP * pip)
    return queue_rr(df, idx, is_long, sl_dist, ASSET, MAX_HOLD, rr)


def build_null(df, atr, k, rr, n_long, n_short, warmup, pip, rng,
               verbose=True):
    """
    مبنای اندازه‌گیری‌شدهٔ هر سمت — ورودهای تصادفی با *همان* هندسهٔ منجمدِ
    ترکیبِ برنده (k·ATR کف‌دار، rr، hold=34). K=600 برای هر سمت.
    """
    n = len(df)
    valid = np.arange(warmup, n - MAX_HOLD - 2)
    a = atr[valid]
    ok = np.isfinite(a) & (a > 0)
    valid, a = valid[ok], a[ok]
    if len(valid) > MAX_NULL_POOL:       # بهداشتِ حافظه (M1)
        sub = np.sort(rng.choice(len(valid), size=MAX_NULL_POOL,
                                 replace=False))
        valid, a = valid[sub], a[sub]
    sl_all = np.maximum(k * a, SL_FLOOR_PIP * pip)
    null = {}
    for side, is_long_flag, n_side in (('long', True, n_long),
                                       ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) > n_side:
            # WR غیرشرطی: نمونهٔ بزرگِ یک‌باره (سقف = MAX_UNCOND، بهداشتِ حافظه)
            m = min(len(valid), MAX_UNCOND)
            pick0 = np.sort(rng.choice(len(valid), size=m, replace=False))
            s_all = queue_rr(df, valid[pick0],
                             np.full(m, is_long_flag),
                             sl_all[pick0], ASSET, MAX_HOLD, rr)
            if s_all:
                d['uncond_wr'] = s_all['wr']
            wrs = []
            for it in range(N_PERM):
                pick = np.sort(rng.choice(len(valid), size=n_side,
                                          replace=False))
                s_p = queue_rr(df, valid[pick],
                               np.full(n_side, is_long_flag),
                               sl_all[pick], ASSET, MAX_HOLD, rr)
                if s_p:
                    wrs.append(s_p['wr'])
                if verbose and (it + 1) % 150 == 0:
                    print(f'      null {side}: perm {it+1}/{N_PERM}',
                          flush=True)
                if (it + 1) % 50 == 0:
                    gc.collect()
            if wrs:
                w = np.asarray(wrs, dtype='float64')
                d.update(perm_mean=float(w.mean()),
                         perm_sd=float(w.std(ddof=1)),
                         perm_max=float(w.max()), perm_k=int(len(w)))
        null[side] = d
        if verbose:
            print(f"      null {side:<5} uncond={d['uncond_wr']} "
                  f"perm_mean={d['perm_mean']} sd={d['perm_sd']}", flush=True)
    return null


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return (None if not np.isfinite(x) else float(x))
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return None
    if isinstance(x, float) and not np.isfinite(x):
        return None
    return x


def _save(tf, obj):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(_jsonable(obj), f, indent=1, ensure_ascii=False)
    print(f'  ✓ checkpoint saved: {path}', flush=True)


def run_tf(tf, verbose=True):
    print(f"\n{'='*90}\n=== S850 Multiscale Resonance :: XAUUSD-{tf} ===",
          flush=True)
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    src = d['src']
    n = len(df)
    close = df['close'].values.astype(np.float64)
    bar_time = d['time']
    # بهداشتِ حافظه: ستون‌هایی که S850 لازم ندارد آزاد شوند (M1: هر آرایه ~40MB)
    for _k in ('hour', 'dow', 'volume'):
        d.pop(_k, None)
    gc.collect()
    pip = se.ASSETS[ASSET]['pip']
    c_pip = cost_pip(ASSET)
    warmup = max(max(max(s) for s in SCALE_SETS) + 2, ATR_P + 2)
    split = int(n * SPLIT_FRAC)
    print(f'    src={src}', flush=True)
    print(f'    bars={n:,}  split(60%)={split:,}  warmup={warmup}  '
          f'cost={c_pip:.2f}pip', flush=True)

    if n < warmup + 500 or split <= warmup + 100:
        out = dict(tf=tf, src=src, bars=n, verdict='TOO_SHORT')
        _save(tf, out)
        return out

    atr = atr_series(df)

    # ---------- ۱) اکتشاف: فقط ۶۰٪ نخست؛ هدف = امیدِ ریاضی، n≥30 ----------
    sigs = {sc: resonance_signals(close, sc) for sc in SCALE_SETS}
    grid = []
    hi_explore = split - MAX_HOLD - 2       # هیچ معامله‌ای واردِ holdout نشود
    for sc in SCALE_SETS:
        up, dn = sigs[sc]
        for k in K_SL:
            for rr in RRS:
                st = combo_trades(df, up, dn, atr, k, rr,
                                  warmup, hi_explore, pip)
                row = dict(scales=list(sc), k=k, rr=rr,
                           n=(st['n'] if st else 0),
                           exp=(round(st['exp'], 4) if st else None),
                           wr=(round(st['wr'], 2) if st else None),
                           pf=(round(st['pf'], 3) if st else None))
                grid.append(row)
                if verbose:
                    print(f"    explore {sc} k={k:<5} rr={rr:<5} "
                          f"n={row['n']:<6} exp={row['exp']} "
                          f"wr={row['wr']} pf={row['pf']}", flush=True)
    elig = [g for g in grid if g['n'] >= EXPLORE_MIN_N and g['exp'] is not None]
    if not elig:
        out = dict(tf=tf, src=src, bars=n, grid=grid,
                   verdict='NO_ELIGIBLE_COMBO',
                   note=f'no combo with n>={EXPLORE_MIN_N} in exploration')
        _save(tf, out)
        return out
    # قاعدهٔ پیش‌ثبت‌شده: بیشترین امیدِ ریاضی؛ گره‌گشایی با n بزرگ‌تر
    elig.sort(key=lambda g: (g['exp'], g['n']), reverse=True)
    win = elig[0]
    sc_w, k_w, rr_w = tuple(win['scales']), win['k'], win['rr']
    # بهداشتِ حافظه: سیگنال‌های مجموعه‌مقیاسِ بازنده آزاد شوند
    for sc in list(sigs.keys()):
        if tuple(sc) != sc_w:
            del sigs[sc]
    gc.collect()
    print(f"\n    ★ winner (exploration only): scales={sc_w} k={k_w} "
          f"rr={rr_w}  exp={win['exp']}pip n={win['n']}", flush=True)

    # ---------- ۲) قضاوت: یک بار، کلِ داده، split_bar → RQS2 ----------
    up, dn = sigs[sc_w]
    st = combo_trades(df, up, dn, atr, k_w, rr_w, warmup, n - MAX_HOLD - 2,
                      pip)
    if st is None or st['n'] < 5:
        out = dict(tf=tf, src=src, bars=n, grid=grid, winner=win,
                   verdict='NO_TRADES_FULL')
        _save(tf, out)
        return out
    # بهداشتِ حافظه: سیگنال‌ها دیگر لازم نیستند (معاملاتِ کامل گرفته شد)
    del sigs, up, dn
    gc.collect()
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(len(tr) - n_long)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    print(f"    full-data trades n={st['n']} (L={n_long}/S={n_short}) "
          f"wr={st['wr']:.2f} exp={st['exp']:.3f}pip "
          f"sl_med={sl_med:.1f} tp_med={tp_med:.1f}", flush=True)

    rng = np.random.default_rng(SEED)
    null = build_null(df, atr, k_w, rr_w, n_long, n_short, warmup, pip, rng,
                      verbose=verbose)

    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=bar_time, null=null, n_trials=N_TRIALS,
                          split_bar=split, close=close)
    print(f"\n    ═══ RQS2 verdict [{tf}]: {r['verdict']}  "
          f"score={r['rqs2_score']}", flush=True)
    print(f"    gates: {r['gates']}", flush=True)

    out = dict(tf=tf, src=src, bars=n, split_bar=split,
               grid=grid, winner=win,
               judged=dict(scales=list(sc_w), k=k_w, rr=rr_w,
                           n=int(st['n']), n_long=n_long, n_short=n_short,
                           wr=round(st['wr'], 2), exp=round(st['exp'], 4),
                           pf=round(st['pf'], 3),
                           sl_med=round(sl_med, 2), tp_med=round(tp_med, 2)),
               null=null,
               gates=r['gates'], metrics=r['metrics'],
               verdict=r['verdict'], rqs2_score=r['rqs2_score'],
               notes=r['notes'])
    _save(tf, out)
    del df, d, atr
    gc.collect()
    return out


if __name__ == '__main__':
    tfs = sys.argv[1:] if len(sys.argv) > 1 else ['M1']
    for tf in tfs:
        try:
            run_tf(tf)
        except Exception as e:
            import traceback
            traceback.print_exc()
            _save(tf, dict(tf=tf, verdict='ERROR', error=str(e)))
    print('\nS850 scan done.', flush=True)
