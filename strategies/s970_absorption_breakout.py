#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S970 — شکستِ پس از جذب (Absorption Breakout) — لایهٔ نو، دریچهٔ Hasbrouck
================================================================================
پیش‌ثبت:  results/S970_PREREG_absorption_breakout.md          (commit f62c2f5b)
الحاقیه:  results/S970_PREREG_ADDENDUM_family_debt.md         (commit 495fb540)
معیار:    RQS2 v2.6 gates_only — حکم هرچه موتور گفت، همان.
مسیرِ چندگانگی: B — **یک** تعریفِ منجمد، هیچ جست‌وجویی. n_trials=168 (بدهیِ
موروثیِ خانوادهٔ جذب: 64 S740 + 64 S741 + 40 S970).

تعریفِ منجمد (بندِ ۲ پیش‌ثبت — تغییرِ هر عدد = تقلب):
  کندلِ جذب A:  vol ≥ Q80(vol,500)  و  (high−low) ≤ Q40(rng,500)   [رولینگ، shift(1)]
  پنجرهٔ تأیید ۵ کندل: اولین B که close>high[A] ⇒ LONG روی B؛ close<low[A] ⇒ SHORT.
  اگر دامنهٔ B هر دو سرِ A را رد کند (h>high[A] و l<low[A]) ⇒ ابهام ⇒ بی‌سیگنال.
  ورود: openِ کندلِ بعد از B (موتورِ forward-safe).

هندسهٔ منجمد (بندِ ۳): SL = 1.0×median(ATR14) همان TF (pip)، TP = 1.5×SL،
  max_hold = round(6h × bars_per_hour)، کفِ ۴ کندل، allow_overlap=False.

مدلِ صفر (بندِ ۴): جای‌گشتِ مکانِ ورود، همان تعداد/سمت/هندسه، K=2000، بذر 20260814.
split_bar = 0.70×n برای H7.

قیدِ الحاقیه: حکمِ M1 و M5 اگر ACCEPT شود، **UNPROVEN** اعلام می‌شود (آلودگیِ
یافتهٔ جانبیِ S740). حکمِ موتور دست‌کاری نمی‌شود؛ فقط «اعلامِ» نهایی فروکاسته است.

داده: فقط data/mt5_full از راهِ tools/s434_fast_data (گزارشِ src اجباری).
H4 در آرشیو نیست ⇒ از H1 بازنمونه‌گیری می‌شود (قانونِ دادهٔ کامل).
فقط XAUUSD — صفر ثانیه EURUSD (دستورِ کاربر).

اجرا:      python3 strategies/s970_absorption_breakout.py M1 [--kperm 2000]
چک‌پوینت:  results/_scan_S970/<TF>.json  (قانونِ اندک‌اندک — commit پس از هر TF)
"""
import sys
import os
import json
import time as _time
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import s434_fast_data as fd                                # noqa: E402
from engine import scalp_engine as se                                 # noqa: E402
from engine import rqs2                                               # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip    # noqa: E402
from strategies.s346_fast import barrier_outcomes, select_non_overlap  # noqa: E402

ASSET = 'XAUUSD'

# ---- ثابت‌های منجمدِ پیش‌ثبت (بندهای ۲–۵) — هیچ مقدارِ دیگری آزموده نمی‌شود ----
LOOKBACK = 500
VOL_Q = 0.80
RNG_Q = 0.40
CONFIRM_WIN = 5
ATR_WIN = 14
SL_K = 1.0            # SL = 1.0 × median(ATR14)
RR = 1.5              # TP = 1.5 × SL  (TP > SL — سپرِ اشتباهِ رایجِ ۸)
HOLD_HOURS = 6.0
HOLD_MIN_BARS = 4
N_TRIALS = 168        # بدهیِ موروثیِ خانوادهٔ جذب (الحاقیه، بندِ ۳.۱)
SPLIT_FRAC = 0.70
K_PERM = 2000
SEED = 20260814
NULL_POOL_MAX = 400_000   # سقفِ استخرِ نال (ایمنیِ حافظه روی M1 — الگوی S740)
TAINTED_TFS = {'M1', 'M5'}  # الحاقیه: سقفِ اعلامِ ACCEPT ⇒ UNPROVEN

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S970')


# ============================== داده ==============================
def load_tf(tf):
    """بارگذاریِ رسمی؛ H4 در آرشیو نیست ⇒ بازنمونه‌گیری از H1 (اعلام در src)."""
    if tf != 'H4':
        d = fd.load_fast(ASSET, tf)
        return fd.as_dataframe(d), d
    d1 = fd.load_fast(ASSET, 'H1')
    df1 = fd.as_dataframe(d1)
    t = df1['time'].values.astype(np.int64)
    grp = t // (4 * 3600)
    df = df1.groupby(grp).agg(
        time=('time', 'first'), open=('open', 'first'), high=('high', 'max'),
        low=('low', 'min'), close=('close', 'last'), volume=('volume', 'sum'),
    ).reset_index(drop=True)
    d = dict(d1)
    d['src'] = str(d1['src']) + '  [resampled H1->H4]'
    d['time'] = df['time'].values
    d['close'] = df['close'].values
    return df, d


def bars_per_hour(df):
    """گامِ زمانیِ واقعیِ داده (علاجِ BUG-TFM) — از خودِ داده، نه فرض."""
    dt = np.median(np.diff(df['time'].values.astype(np.float64)))
    return 3600.0 / dt if dt > 0 else 1.0


def atr_plain(h, l, c, win=ATR_WIN):
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return pd.Series(tr).rolling(win, min_periods=win).mean().values


# ============================== سیگنال (forward-safe) ==============================
def build_signals(df):
    """
    خروجی: (sig_idx, is_long) — سیگنال روی کندلِ تأییدِ B ثبت می‌شود؛ موتور در
    openِ کندلِ بعد وارد می‌شود.

    forward-safe: کوانتایل‌ها رولینگ با shift(1)اند (فقط گذشته)؛ رویدادِ A روی
    کندلِ بسته‌شده تعریف می‌شود و تأییدِ B با closeِ بسته‌شده.
    """
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    c = df['close'].values.astype(np.float64)
    v = df['volume'].values.astype(np.float64)
    n = len(df)
    rng_ = h - l

    vq = pd.Series(v).rolling(LOOKBACK, min_periods=LOOKBACK)\
        .quantile(VOL_Q).shift(1).values
    rq = pd.Series(rng_).rolling(LOOKBACK, min_periods=LOOKBACK)\
        .quantile(RNG_Q).shift(1).values

    ev = (v >= vq) & (rng_ <= rq) & np.isfinite(vq) & np.isfinite(rq)
    ev_idx = np.flatnonzero(ev)

    sig, isl = [], []
    for a in ev_idx:
        hi_a, lo_a = h[a], l[a]
        end = min(a + CONFIRM_WIN, n - 1)
        for b in range(a + 1, end + 1):
            up = c[b] > hi_a
            dn = c[b] < lo_a
            if not (up or dn):
                continue
            # ابهام: دامنهٔ B هر دو سرِ A را رد کرده ⇒ بی‌سیگنال (پیش‌ثبت، بندِ ۲)
            if h[b] > hi_a and l[b] < lo_a:
                break
            sig.append(b)
            isl.append(bool(up))
            break
    if not sig:
        return np.array([], dtype=np.int64), np.array([], dtype=bool)
    sig = np.asarray(sig, dtype=np.int64)
    isl = np.asarray(isl, dtype=bool)
    # یک کندل ممکن است تأییدِ چند رویدادِ A باشد ⇒ یکتا (اولین جهت مقدم)
    uniq, first = np.unique(sig, return_index=True)
    return uniq, isl[first]


# ============================== نالِ اندازه‌گیری‌شده ==============================
def build_null(df, sl_pip_scalar, hold, n_long, n_short, k_perm, rng, warmup):
    """نالِ هر سمت با همان هندسهٔ منجمد — الگوی تأییدشدهٔ S740."""
    cfg = se.ASSETS[ASSET]
    pip, spread = float(cfg['pip']), float(cfg['spread_pip'])
    slip = float(cfg.get('slip_pip', 0.0))
    n = len(df)
    valid = np.arange(warmup, n - hold - 1)
    pool_note = f'full_valid={len(valid)}'
    if len(valid) > NULL_POOL_MAX:
        valid = np.sort(rng.choice(valid, size=NULL_POOL_MAX, replace=False))
        pool_note += f' pooled_to={NULL_POOL_MAX}'

    sl_d = np.full(len(valid), sl_pip_scalar * pip)
    tp_d = np.maximum(RR * sl_d, sl_d)

    null = {}
    for side, flag, n_side in (('long', True, n_long), ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            fo = barrier_outcomes(df, valid, np.full(len(valid), flag),
                                  sl_d, tp_d, hold, pip, spread, slip)
            keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
            w_all = fo['win'][keep]
            if len(w_all):
                d['uncond_wr'] = float(w_all.mean() * 100.0)
            m = len(fo['entry_bar'])
            if m > n_side:
                wrs = []
                for _ in range(k_perm):
                    pick = np.sort(rng.choice(m, size=n_side, replace=False))
                    kp = select_non_overlap(fo['entry_bar'][pick],
                                            fo['exit_off'][pick])
                    w = fo['win'][pick][kp]
                    if len(w):
                        wrs.append(float(w.mean() * 100.0))
                if wrs:
                    a = np.asarray(wrs)
                    d.update(perm_mean=float(a.mean()),
                             perm_sd=float(a.std(ddof=1)),
                             perm_max=float(a.max()), perm_k=int(len(a)))
        null[side] = d
        print(f"    null {side:<5} uncond={d['uncond_wr']} "
              f"perm_mean={d['perm_mean']} sd={d['perm_sd']} k={d['perm_k']}",
              flush=True)
    return null, pool_note


# ============================== اجرای یک TF ==============================
def run_tf(tf, k_perm=K_PERM, seed=SEED):
    t0 = _time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f'{tf}.json')
    rng = np.random.default_rng(seed)

    df, d = load_tf(tf)
    n = len(df)
    split = int(SPLIT_FRAC * n)
    c_pip = cost_pip(ASSET)
    bph = bars_per_hour(df)
    hold = max(HOLD_MIN_BARS, int(round(HOLD_HOURS * bph)))
    print(f"\n{'='*88}\n=== S970 ABSORPTION-BREAKOUT :: {ASSET}-{tf}  bars={n:,}  "
          f"src={d['src']}\n    span={d.get('first_utc','?')} → "
          f"{d.get('last_utc','?')} ({float(d.get('span_years',0)):.2f}y) · "
          f"split_bar={split} · hold={hold} bars (~{HOLD_HOURS}h) · "
          f"cost={c_pip:.2f}pip · N_TRIALS={N_TRIALS} · K={k_perm}", flush=True)

    out = dict(strategy='S970_AbsorptionBreakout', asset=ASSET, tf=tf, bars=n,
               src=str(d['src']), span_years=round(float(d.get('span_years', 0)), 2),
               split_bar=split, hold=hold, n_trials=N_TRIALS, k_perm=k_perm,
               seed=seed, tainted=tf in TAINTED_TFS,
               prereg='results/S970_PREREG_absorption_breakout.md',
               addendum='results/S970_PREREG_ADDENDUM_family_debt.md')

    def _default(o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return str(o)

    def _save():
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=1,
                  default=_default)

    warmup = LOOKBACK + CONFIRM_WIN + ATR_WIN + 1
    if n < warmup + 200:
        out['verdict'] = 'TOO_SHORT'
        _save()
        print('    TOO_SHORT — داده برای warmup کافی نیست.', flush=True)
        return out

    # ---- هندسهٔ منجمد ----
    atr = atr_plain(df['high'].values, df['low'].values, df['close'].values)
    pip = float(se.ASSETS[ASSET]['pip'])
    sl_pip_scalar = float(np.nanmedian(atr)) * SL_K / pip
    tp_pip_scalar = sl_pip_scalar * RR
    out['sl_pip'] = round(sl_pip_scalar, 3)
    out['tp_pip'] = round(tp_pip_scalar, 3)
    print(f"    SL={sl_pip_scalar:.2f}pip TP={tp_pip_scalar:.2f}pip (RR={RR})",
          flush=True)

    # ---- سیگنال ----
    sig, is_long = build_signals(df)
    out['n_signals'] = int(len(sig))
    print(f"    سیگنالِ تأییدشده: {len(sig):,} "
          f"(L={int(is_long.sum()):,}/S={int((~is_long).sum()):,})", flush=True)
    if len(sig) < 5:
        out['verdict'] = 'NO_TRADES_FULL'
        _save()
        return out

    # ---- شبیه‌سازی روی کلِ داده (هندسهٔ منجمد؛ H7 با split_bar داوری می‌شود) ----
    sl_dist = np.full(len(sig), sl_pip_scalar * pip)
    st = queue_rr(df, sig, is_long, sl_dist, ASSET, hold, RR)
    if st is None or st['n'] < 5:
        out['verdict'] = 'NO_TRADES_FULL'
        _save()
        return out
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(st['n'] - n_long)
    print(f"    کلِ داده: n={st['n']:,} (L={n_long:,}/S={n_short:,}) "
          f"wr={st['wr']:.2f}% exp={st['exp']:.3f}pip pf={st['pf']:.3f}",
          flush=True)

    # ---- نالِ اندازه‌گیری‌شده ----
    null, pool_note = build_null(df, sl_pip_scalar, hold, n_long, n_short,
                                 k_perm, rng, warmup)
    out['null'] = null
    out['null_pool'] = pool_note

    # ---- داوریِ RQS2 با هر ۵ ورودیِ الزامی ----
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_pip_scalar, tp_pip=tp_pip_scalar,
                          bar_time=df['time'].values, null=null,
                          n_trials=N_TRIALS, split_bar=split,
                          close=df['close'].values, allow_overlap=False)
    print('\n' + rqs2.format_rqs2(f'S970-{tf}', r), flush=True)

    verdict = r['verdict']
    out['verdict_engine'] = verdict
    # الحاقیه: فروکاستِ اعلامی روی TFهای آلوده — حکمِ موتور دست نمی‌خورد.
    if tf in TAINTED_TFS and verdict == 'ACCEPT':
        out['verdict'] = 'UNPROVEN'
        out['downgrade_note'] = 'ACCEPT->UNPROVEN per addendum (S740 taint on M1/M5)'
    else:
        out['verdict'] = verdict
    out['rqs2_score'] = r.get('rqs2_score')
    out['gates'] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                    for k, v in (r.get('gates') or {}).items()}
    out['metrics'] = {k: v for k, v in (r.get('metrics') or {}).items()
                      if isinstance(v, (int, float, str, bool, np.integer,
                                        np.floating, np.bool_)) or v is None}
    out['full'] = dict(n=int(st['n']), n_long=n_long, n_short=n_short,
                       wr=round(float(st['wr']), 2),
                       exp_pip=round(float(st['exp']), 3),
                       pf=round(float(st['pf']), 3))
    out['elapsed_s'] = round(_time.time() - t0, 1)
    _save()
    print(f"    ✔ checkpoint → {out_path} ({out['elapsed_s']}s)", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tf')
    ap.add_argument('--kperm', type=int, default=K_PERM)
    a = ap.parse_args()
    run_tf(a.tf.upper(), k_perm=a.kperm)
