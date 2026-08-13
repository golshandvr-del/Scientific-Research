#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S740 — لایهٔ «تلاشِ بی‌ثمر» (Absorption / Effort-Without-Result) — وایکوف
================================================================================
پیش‌ثبت: results/S740_PREREG_ABSORPTION_PATH_C.md (commit 6d0a3bb7 — پیش از این کد)
معیار داوری: RQS2 v2.6 (docs/RQS2_SPEC.md) — gates_only
مسیر چندگانگی: C (اکتشاف روی ۶۰٪ نخست؛ یک آزمون نهایی که H7 روی ۴۰٪ پایانی داوری می‌کند)

مفهوم (منجمد در پیش‌ثبت):
  کندل با «تلاش» بزرگ (حجم tick > میانگین + K_VOL·σ در پنجرهٔ V_WIN)
  و «بی‌ثمری» (بازه < K_RNG·ATR) در کفِ پنجرهٔ LOC_WIN ⇒ جذبِ عرضه ⇒ LONG
  (و قرینه در سقف ⇒ SHORT). سیگنال رویدادمحور (لبهٔ بالا‌رونده).

هندسه: SL = K_SL·ATR(100) شناور (pip غیرِ رُند)، TP = RR·SL با RR≥1،
        HOLD = 16 ≥ (max k_sl·rr)² = 14.06 (قانونِ دسترس‌پذیریِ سد).

شبکهٔ منجمد: V_WIN∈{89,233} K_VOL∈{2,3} K_RNG∈{0.5,0.75} LOC_WIN∈{21,55}
             K_SL∈{1.5,2.5} RR∈{1.0,1.5}  ⇒ 64 پیکربندی ⇒ n_trials=64 برای H5.

داده: فقط data/mt5_full (از راهِ tools/s434_fast_data — گزارشِ src اجباری).
جفت‌ارز: فقط XAUUSD (استثنای صریح کاربر برای EURUSD).

اجرا:  python3 strategies/s740_absorption.py M1 [--kperm 500]
چک‌پوینت: results/_scan_S740/<TF>.json (قانونِ اندک‌اندک — commit پس از هر TF)
"""
import sys
import os
import json
import time as _time
import argparse

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import s434_fast_data as fd                              # noqa: E402
from engine import scalp_engine as se                               # noqa: E402
from engine import rqs2                                             # noqa: E402
from strategies.s348_rr_sweep import queue_rr, trades_df, cost_pip  # noqa: E402
from strategies.s346_fast import barrier_outcomes, select_non_overlap  # noqa: E402

ASSET = 'XAUUSD'

# ---- شبکهٔ منجمدِ پیش‌ثبت‌شده (هیچ مقداری خارج از این‌ها آزموده نمی‌شود) ----
V_WIN_GRID = (89, 233)
K_VOL_GRID = (2.0, 3.0)
K_RNG_GRID = (0.5, 0.75)
LOC_WIN_GRID = (21, 55)
K_SL_GRID = (1.5, 2.5)
RR_GRID = (1.0, 1.5)
ATR_WIN = 100
HOLD = 16                     # ≥ (2.5·1.5)² = 14.06 — قانونِ دسترس‌پذیریِ سد
N_TRIALS = 64                 # کلِ شبکه — صادقانه، فارغ از تعدادِ گزارش‌شده
SPLIT_FRAC = 0.60
MIN_N_DISC = 30               # کفِ H0 در اکتشاف
MIN_PF_DISC = 1.3             # کفِ H1 در اکتشاف (قاعدهٔ انتخابِ پیش‌ثبت‌شده)
NULL_POOL_MAX = 400_000       # سقفِ استخرِ نال (ایمنیِ حافظهٔ M1 با ۵M کندل)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S740')


# ============================== اندیکاتورها (forward-safe) ==============================
def atr_plain(h, l, c, win=ATR_WIN):
    """ATR ساده (میانگینِ غلتانِ TR) — هم‌خانوادهٔ s351/s382، بدونِ look-ahead."""
    prev_c = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    return pd.Series(tr).rolling(win, min_periods=win).mean().values


def build_signals(df, atr, v_win, k_vol, k_rng, loc_win):
    """سیگنال‌های رویدادمحورِ جذب. خروجی: (sig_idx, is_long) — کندلِ سیگنال t، ورود t+1."""
    h = df['high'].values
    l = df['low'].values
    v = df['volume'].values

    vs = pd.Series(v)
    v_mu = vs.rolling(v_win, min_periods=v_win).mean().values
    v_sd = vs.rolling(v_win, min_periods=v_win).std(ddof=1).values

    rng = h - l
    lo_min = pd.Series(l).rolling(loc_win, min_periods=loc_win).min().values
    hi_max = pd.Series(h).rolling(loc_win, min_periods=loc_win).max().values

    effort = v > (v_mu + k_vol * v_sd)                    # تلاش
    no_result = rng < (k_rng * atr)                       # بی‌ثمری
    valid = np.isfinite(v_mu) & np.isfinite(v_sd) & np.isfinite(atr) & (atr > 0)

    base = effort & no_result & valid
    long_c = base & (l <= lo_min)                         # جذبِ عرضه در کف
    short_c = base & (h >= hi_max) & ~long_c              # جذبِ تقاضا در سقف (long مقدم)

    # رویدادمحوری: فقط لبهٔ بالا‌رونده (کندلِ قبلی شرط را نداشته باشد)
    def edge(m):
        prev = np.concatenate(([False], m[:-1]))
        return m & ~prev

    long_e, short_e = edge(long_c), edge(short_c)
    sig = np.where(long_e | short_e)[0]
    return sig, long_e[sig]


# ============================== اکتشاف (فقط ۶۰٪ نخست) ==============================
def discover(df, atr, split, c_pip):
    """جاروبِ ۶۴ پیکربندی روی پنجرهٔ اکتشاف. Holdout هرگز دیده نمی‌شود."""
    rows = []
    df_d = df.iloc[:split]
    atr_d = atr[:split]
    for v_win in V_WIN_GRID:
        for k_vol in K_VOL_GRID:
            for k_rng in K_RNG_GRID:
                for loc_win in LOC_WIN_GRID:
                    sig, is_long = build_signals(df_d, atr_d,
                                                 v_win, k_vol, k_rng, loc_win)
                    for k_sl in K_SL_GRID:
                        for rr in RR_GRID:
                            row = dict(v_win=v_win, k_vol=k_vol, k_rng=k_rng,
                                       loc_win=loc_win, k_sl=k_sl, rr=rr,
                                       n=0, wr=None, pf=None, z=None)
                            if len(sig) >= MIN_N_DISC:
                                st = queue_rr(df_d, sig, is_long,
                                              k_sl * atr_d[sig],
                                              ASSET, HOLD, rr)
                                if st is not None and st['n'] >= MIN_N_DISC:
                                    sl_med = float(np.median(st['sl_pip']))
                                    tp_med = float(np.median(st['tp_pip']))
                                    be = rqs2.breakeven_wr_cost(sl_med, tp_med,
                                                                c_pip)
                                    lift = st['wr'] - be
                                    p0 = be / 100.0
                                    sepc = 100.0 * np.sqrt(
                                        max(p0 * (1 - p0), 1e-9) / st['n'])
                                    row.update(n=st['n'], wr=round(st['wr'], 2),
                                               pf=round(st['pf'], 3),
                                               exp=round(st['exp'], 2),
                                               sl_med=round(sl_med, 2),
                                               tp_med=round(tp_med, 2),
                                               be=round(be, 2),
                                               lift=round(lift, 2),
                                               z=round(lift / sepc, 3)
                                               if sepc > 0 else None)
                            rows.append(row)
    # قاعدهٔ انتخابِ پیش‌ثبت‌شده: بیشترین z با n≥30 و PF≥1.3
    cand = [r for r in rows if r['z'] is not None
            and r['n'] >= MIN_N_DISC and (r['pf'] or 0) >= MIN_PF_DISC]
    winner = max(cand, key=lambda r: r['z']) if cand else None
    return rows, winner


# ============================== نالِ اندازه‌گیری‌شده ==============================
def build_null(df, atr, n_long, n_short, k_sl, rr, k_perm, rng):
    """
    نالِ هر سمت با همان هندسهٔ نامزد (SL=k_sl·ATR شناور، TP=rr·SL، HOLD).
    برای دادهٔ عظیم (M1) از استخرِ تصادفیِ ≤NULL_POOL_MAX کندلِ معتبر
    نمونه می‌گیریم — برآوردِ نااُریبِ همان جمعیت با SE ناچیز.
    """
    cfg = se.ASSETS[ASSET]
    pip, spread = cfg['pip'], cfg['spread_pip']
    slip = cfg.get('slip_pip', 0.0)
    valid = np.where(np.isfinite(atr) & (atr > 0))[0]
    valid = valid[valid + 1 + HOLD < len(df)]
    pool_note = f'full_valid={len(valid)}'
    if len(valid) > NULL_POOL_MAX:
        valid = np.sort(rng.choice(valid, size=NULL_POOL_MAX, replace=False))
        pool_note += f' pooled_to={NULL_POOL_MAX}'

    null = {}
    for side, flag, n_side in (('long', True, n_long), ('short', False, n_short)):
        d = dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                 perm_max=None, perm_k=None)
        if n_side >= 1 and len(valid) >= 2:
            sl_d = k_sl * atr[valid]
            tp_d = np.maximum(rr * sl_d, sl_d)
            fo = barrier_outcomes(df, valid, np.full(len(valid), flag),
                                  sl_d, tp_d, HOLD, pip, spread, slip)
            keep = select_non_overlap(fo['entry_bar'], fo['exit_off'])
            win_q = fo['win'][keep]                    # بی‌قید با صفِ اشغال
            if len(win_q) > 0:
                d['uncond_wr'] = float(win_q.mean() * 100.0)
            # جای‌گشت‌ها: زیرمجموعهٔ تصادفیِ هم‌اندازهٔ لایه + صفِ اشغال
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


# ============================== اجرای یک تایم‌فریم ==============================
def run_tf(tf, k_perm=500, seed=740):
    t0 = _time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f'{tf}.json')
    rng = np.random.default_rng(seed)

    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    n = len(df)
    split = int(SPLIT_FRAC * n)
    c_pip = cost_pip(ASSET)
    print(f"\n{'='*88}\n=== S740 ABSORPTION :: {ASSET}-{tf}  bars={n:,}  "
          f"src={d['src']}\n    span={d['first_utc']} → {d['last_utc']} "
          f"({d['span_years']:.2f}y) · split_bar={split} · cost={c_pip:.2f}pip "
          f"· N_TRIALS={N_TRIALS}", flush=True)

    out = dict(strategy='S740_Absorption', asset=ASSET, tf=tf, bars=n,
               src=d['src'], span_years=round(float(d['span_years']), 2),
               split_bar=split, n_trials=N_TRIALS, k_perm=k_perm,
               prereg='results/S740_PREREG_ABSORPTION_PATH_C.md')

    def _default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return str(o)

    def _save():
        json.dump(out, open(out_path, 'w'), ensure_ascii=False, indent=1,
                  default=_default)

    warmup = max(max(V_WIN_GRID), ATR_WIN, max(LOC_WIN_GRID)) + 1
    if n < warmup + 200:
        out['verdict'] = 'TOO_SHORT'
        _save()
        print('    TOO_SHORT — رد شد.', flush=True)
        return out

    atr = atr_plain(df['high'].values, df['low'].values, df['close'].values)

    # ---- ۱) اکتشاف (فقط ۶۰٪ نخست) ----
    grid, winner = discover(df, atr, split, c_pip)
    out['grid_summary'] = dict(
        tested=len(grid),
        with_trades=sum(1 for r in grid if r['n'] >= MIN_N_DISC),
        eligible=sum(1 for r in grid if r['z'] is not None
                     and r['n'] >= MIN_N_DISC and (r['pf'] or 0) >= MIN_PF_DISC))
    out['grid_top5'] = sorted([r for r in grid if r['z'] is not None],
                              key=lambda r: -r['z'])[:5]
    if winner is None:
        out['verdict'] = 'NO_CANDIDATE'
        _save()
        print(f"    هیچ نامزدی از دروازهٔ اکتشاف نگذشت "
              f"(eligible=0 از {len(grid)}).", flush=True)
        return out
    out['winner_params'] = {k: winner[k] for k in
                            ('v_win', 'k_vol', 'k_rng', 'loc_win', 'k_sl', 'rr')}
    out['winner_disc'] = {k: winner[k] for k in
                          ('n', 'wr', 'pf', 'exp', 'lift', 'z', 'sl_med', 'tp_med')}
    print(f"    نامزدِ اکتشاف: {out['winner_params']} → n={winner['n']} "
          f"wr={winner['wr']} pf={winner['pf']} z={winner['z']}", flush=True)

    # ---- ۲) آزمونِ نهایی: کلِ داده با پارامترهای منجمد (H7 روی ۴۰٪ پایانی) ----
    w = winner
    sig, is_long = build_signals(df, atr, w['v_win'], w['k_vol'],
                                 w['k_rng'], w['loc_win'])
    st = queue_rr(df, sig, is_long, w['k_sl'] * atr[sig], ASSET, HOLD, w['rr'])
    if st is None or st['n'] < 5:
        out['verdict'] = 'NO_TRADES_FULL'
        _save()
        return out
    tr = trades_df(st)
    n_long = int((tr['direction'] == 'long').sum())
    n_short = int(st['n'] - n_long)
    sl_med = float(np.median(st['sl_pip']))
    tp_med = float(np.median(st['tp_pip']))
    print(f"    کلِ داده: n={st['n']} (L={n_long}/S={n_short}) wr={st['wr']:.2f} "
          f"exp={st['exp']:.2f}pip pf={st['pf']:.3f} "
          f"sl_med={sl_med:.2f} tp_med={tp_med:.2f}", flush=True)

    # ---- ۳) نالِ اندازه‌گیری‌شده با همان هندسه ----
    null, pool_note = build_null(df, atr, n_long, n_short,
                                 w['k_sl'], w['rr'], k_perm, rng)
    out['null'] = null
    out['null_pool'] = pool_note

    # ---- ۴) داوریِ RQS2 با هر ۵ ورودیِ الزامی ----
    r = rqs2.compute_rqs2(tr, ASSET, sl_pip=sl_med, tp_pip=tp_med,
                          bar_time=d['time'], null=null, n_trials=N_TRIALS,
                          split_bar=split, close=d['close'],
                          allow_overlap=False)
    print('\n' + rqs2.format_rqs2(f'S740-{tf}', r), flush=True)

    out['verdict'] = r['verdict']
    out['rqs2_score'] = r.get('rqs2_score')
    out['gates'] = {k: (bool(v) if isinstance(v, (bool, np.bool_)) else v)
                    for k, v in (r.get('gates') or {}).items()}
    out['metrics'] = {k: v for k, v in (r.get('metrics') or {}).items()
                      if isinstance(v, (int, float, str, bool, np.integer,
                                        np.floating, np.bool_)) or v is None}
    out['full'] = dict(n=int(st['n']), n_long=n_long, n_short=n_short,
                       wr=round(float(st['wr']), 2),
                       exp_pip=round(float(st['exp']), 3),
                       pf=round(float(st['pf']), 3),
                       sl_med=round(sl_med, 2), tp_med=round(tp_med, 2))
    out['elapsed_s'] = round(_time.time() - t0, 1)
    _save()
    print(f"    ✔ checkpoint → {out_path} ({out['elapsed_s']}s)", flush=True)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('tf')
    ap.add_argument('--kperm', type=int, default=500)
    a = ap.parse_args()
    run_tf(a.tf.upper(), k_perm=a.kperm)
