#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S405 — گپ‌فیلِ دوشنبه (گپ ویکند) · XAUUSD M30 — جمعیتِ مکملِ S404
==================================================================
پیش‌ثبت: results/S405_PREREG_GAP_FILL_MONDAY.md (commit قبل از هر اجرا)
والدها:  S400–S404 (S404: ACCEPT 96.8 روی dow!=0؛ دوشنبه‌ها هرگز با گپ‌فیل داوری نشده)

فضای پیش‌ثبت (۸ ترکیب): q∈{60,70} × k_sl∈{1.7,2.0} × V∈{None,ATRq78}
قاعدهٔ برنده (قفل): کمترین maxDD نیمهٔ اول به شرط
  n≥50 · PF>1 · t≥2.5 · maxDD≤4.80% · wr_edge≥2pp · rec≥3 ؛ گره‌گشایی: t بزرگ‌تر.
حالت‌ها:
  python3 strategies/s405_gap_fill_monday.py tune
  python3 strategies/s405_gap_fill_monday.py verdict <q> <k_sl> <V|None>
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se
from strategies.s400_gap_open import (build_days, daily_atr, thresholds_for_day,
                                      SPLIT_BAR, PIP, SPREAD_PIP)
from strategies.s401_gap_fill_riskguard import sim_trade_be
from strategies.s404_gap_fill_window import vol_flags, judge_stats

TF = 'M30'
SEED = 405
N_TRIALS_CUM = 266                 # 258 + 8 (پیش‌ثبت §۵)
CKPT = os.path.join(os.path.dirname(__file__), '..', 'results', '_s405_tune_ckpt.json')


def run_layer(df, days, atr, q, k_sl, use_v, vflags=None,
              lo_bar=None, hi_bar=None, no_thresh=False):
    """S405: فقط دوشنبه‌ها (dow==0) با گپ منفی. V جزو مهارت (در null اعمال نمی‌شود)."""
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    if use_v and vflags is None:
        vflags = vol_flags(days, atr)
    trades = []
    for k, d in enumerate(days):
        if lo_bar is not None and d['fb'] < lo_bar:
            continue
        if hi_bar is not None and d['fb'] >= hi_bar:
            continue
        if d['dow'] != 0:                 # جمعیت = فقط دوشنبه (تعریف رویداد، نه مهارت)
            continue
        if not (d['gap'] < 0):
            continue
        if not no_thresh:
            th = thresholds_for_day(days, atr, k, 'QW', q)
            if not np.isfinite(th) or abs(d['gap']) <= th:
                continue
        if use_v and vflags[k]:
            continue
        tr = sim_trade_be(arrays, d, k_sl, None)   # BE=None دائمی (پیش‌ثبت)
        if tr is None:
            continue
        trades.append(tr)
    return pd.DataFrame(trades)


def mode_tune():
    df = se.load_data(f'data/XAUUSD_{TF}.csv')
    days = build_days(df)
    atr = daily_atr(days)
    vflags = vol_flags(days, atr)
    split = SPLIT_BAR[TF]
    rows = []
    for q in (60, 70):
        for k_sl in (1.7, 2.0):
            for v in (False, True):
                tr = run_layer(df, days, atr, q, k_sl, v,
                               vflags=vflags, hi_bar=split)
                st = judge_stats(tr)
                st.update(q=q, k_sl=k_sl, V=('ATRq78' if v else 'None'))
                rows.append(st)
                print(f"q={q} k_sl={k_sl} V={st['V']:6s} | n={st['n']:4d} "
                      f"WR={st['wr']}% PF={st['pf']} t={st['t']} "
                      f"maxDD={st['maxdd']}% wr_edge={st['wr_edge']}pp rec={st['rec']}",
                      flush=True)
    with open(CKPT, 'w') as f:
        json.dump(rows, f, indent=1, default=str)
    ok = [r for r in rows if r['n'] >= 50 and r['pf'] > 1 and r['t'] >= 2.5
          and r['maxdd'] <= 4.80 and r['wr_edge'] >= 2 and r['rec'] >= 3]
    if not ok:
        print("\nNO COMBO PASSES LOCKED RULE → tuning-phase REJECT (holdout stays virgin)",
              flush=True)
        return 1
    win = sorted(ok, key=lambda r: (r['maxdd'], -r['t']))[0]
    print(f"\nWINNER: q={win['q']} k_sl={win['k_sl']} V={win['V']} "
          f"(maxDD={win['maxdd']}%, t={win['t']})", flush=True)
    return 0


def mode_verdict(q, k_sl, use_v):
    from engine import rqs2
    df = se.load_data(f'data/XAUUSD_{TF}.csv')
    days = build_days(df)
    atr = daily_atr(days)
    vflags = vol_flags(days, atr)
    split = SPLIT_BAR[TF]
    bar_time = df['dt'].values
    close = df['close'].values.astype('float64')

    strat = run_layer(df, days, atr, q, k_sl, use_v, vflags=vflags)
    n_str = len(strat)
    print(f"strategy trades n={n_str} · holdout n={int((strat['entry_bar'] >= split).sum())}",
          flush=True)

    # null بازو-همتا: هر دوشنبهٔ گپ-منفی بدون آستانه/V (پیش‌ثبت §۴)
    pool_df = run_layer(df, days, atr, q, k_sl, False, no_thresh=True)
    pool = pool_df['pnl_pip'].values.astype('float64')
    uncond_wr = float((pool > 0).mean() * 100.0)
    print(f"null pool = {len(pool)} uncond Monday gap-DOWN entries (same k_sl) · "
          f"uncond_wr={uncond_wr:.2f}%", flush=True)

    rng = np.random.default_rng(SEED)
    K = 500
    wrs = np.empty(K)
    for i in range(K):
        pick = rng.choice(len(pool), size=n_str, replace=False)
        wrs[i] = (pool[pick] > 0).mean() * 100.0
    null = {'long': dict(uncond_wr=uncond_wr, perm_mean=float(wrs.mean()),
                         perm_sd=float(wrs.std(ddof=1)), perm_max=float(wrs.max()),
                         perm_k=int(K)),
            'short': dict(uncond_wr=None, perm_mean=None, perm_sd=None,
                          perm_max=None, perm_k=None)}
    print(f"perm(K={K}): mean={wrs.mean():.2f} sd={wrs.std(ddof=1):.3f} "
          f"max={wrs.max():.2f}", flush=True)

    tp_meas = float(np.median(strat['tp_pip'].values))
    sl_meas = float(np.median(strat['sl_pip'].values))
    print(f"judge geometry: sl_pip={sl_meas:.1f} tp_pip={tp_meas:.1f} "
          f"rr={tp_meas/sl_meas:.3f}", flush=True)

    r = rqs2.compute_rqs2(strat, 'XAUUSD', sl_pip=sl_meas, tp_pip=tp_meas,
                          bar_time=bar_time, null=null,
                          n_trials=N_TRIALS_CUM, split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S405 {TF} q={q}/k_sl={k_sl}/V={use_v}', r), flush=True)
    outp = os.path.join(os.path.dirname(__file__), '..', 'results', '_s405_verdict.json')
    with open(outp, 'w') as f:
        json.dump(r, f, indent=1, default=str)
    print(f"saved → {outp}", flush=True)
    return 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'tune'
    if mode == 'tune':
        sys.exit(mode_tune())
    elif mode == 'verdict':
        q = int(sys.argv[2]); k_sl = float(sys.argv[3])
        v = sys.argv[4] if len(sys.argv) > 4 else 'None'
        sys.exit(mode_verdict(q, k_sl, v not in ('None', 'none')))
    else:
        print(__doc__); sys.exit(2)
