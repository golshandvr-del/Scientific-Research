#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S404 — گپ‌فیلِ M30 در پنجرهٔ مجازِ H2 + فیلترِ نوسان (حملهٔ چهارم به H8)
========================================================================
پیش‌ثبت: results/S404_PREREG_GAP_FILL_WINDOW.md (کامیت 644189e5، قبل از هر اجرا)
والدها:  S400(فقط-H8) · S401(6.46%) · S402(خنثی) · S403(REJECT 35.2: RR=1/k_sl و DD منتقل نمی‌شود)

اهرم‌های پیش‌ثبت‌شده (۱۲ ترکیب):
  k_sl∈{1.7,1.85,2.0} (درونِ پنجرهٔ RR≥0.5) · V∈{None,ATRq78} · cooldown∈{0,1}
فیلترِ V (علّی): ردِ روزِ سیگنال‌دار اگر ATR14 روزِ قبل > صدکِ ۷۸ رولینگ ۲۵۰روزه.
BE-trigger حذفِ دائم (S403: مضر). قاعدهٔ برنده (قفل): کمترین maxDD نیمهٔ اول به شرطِ
n≥100 · PF>1 · t≥2.5 · maxDD≤4.80% · wr_edge≥2pp · rec≥3.
حالت‌ها:
  python3 strategies/s404_gap_fill_window.py tune
  python3 strategies/s404_gap_fill_window.py verdict <k_sl> <V|None> <cd>
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se
from strategies.s400_gap_open import (build_days, daily_atr, thresholds_for_day,
                                      SPLIT_BAR, PIP, SPREAD_PIP, SEED)
from strategies.s401_gap_fill_riskguard import sim_trade_be

TF = 'M30'
BASE = dict(fam='QW', par=70, dow_drop=0)
N_TRIALS_CUM = 258                 # 246 + 12 (پیش‌ثبت §۵)
VOL_Q = 0.78                       # صدکِ فیلترِ نوسان (قفل در پیش‌ثبت)
VOL_ROLL = 250                     # پنجرهٔ رولینگِ علّی
CKPT = os.path.join(os.path.dirname(__file__), '..', 'results', '_s404_tune_ckpt.json')


def vol_flags(days, atr):
    """برای هر روزِ k: آیا ATR روزِ قبل بالای صدکِ ۷۸ٍ رولینگِ ۲۵۰روزهٔ *علّی* است؟
    فقط داده‌های < k استفاده می‌شود (بدونِ look-ahead)."""
    n = len(days)
    flags = np.zeros(n, dtype=bool)
    for k in range(n):
        if k < 1:
            continue
        a_prev = atr[k - 1]                       # ATR روزِ قبل (علّی)
        lo = max(0, k - VOL_ROLL)
        hist = atr[lo:k]
        hist = hist[np.isfinite(hist)]
        if not np.isfinite(a_prev) or len(hist) < 60:
            continue                              # دادهٔ ناکافی ⇒ فیلتر نمی‌بندد
        q = np.quantile(hist, VOL_Q)
        flags[k] = a_prev > q
    return flags


def run_layer(df, days, atr, k_sl, use_v, cooldown_d, vflags=None,
              lo_bar=None, hi_bar=None, no_thresh=False, no_dow=False):
    """اجرای S404. V جزوِ انتخابِ معامله است (در null اعمال نمی‌شود)."""
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    if use_v and vflags is None:
        vflags = vol_flags(days, atr)
    trades = []
    skip_left = 0
    for k, d in enumerate(days):
        if lo_bar is not None and d['fb'] < lo_bar:
            continue
        if hi_bar is not None and d['fb'] >= hi_bar:
            continue
        if not (d['gap'] < 0):
            continue
        if not no_thresh:
            th = thresholds_for_day(days, atr, k, BASE['fam'], BASE['par'])
            if not np.isfinite(th) or abs(d['gap']) <= th:
                continue
        if not no_dow and d['dow'] == BASE['dow_drop']:
            continue
        if use_v and vflags[k]:
            continue                              # فیلترِ نوسان: روزِ پرریسک رد
        if skip_left > 0:
            skip_left -= 1
            continue
        tr = sim_trade_be(arrays, d, k_sl, None)  # BE=None دائمی (پیش‌ثبت)
        if tr is None:
            continue
        trades.append(tr)
        if cooldown_d > 0 and tr['full_sl']:
            skip_left = cooldown_d
    return pd.DataFrame(trades)


def judge_stats(tr):
    if len(tr) == 0:
        return dict(n=0, wr=np.nan, pf=np.nan, t=np.nan, maxdd=np.nan, net=np.nan,
                    breakeven=np.nan, wr_edge=np.nan, rec=np.nan)
    cap, _ = se.run_capital(tr, 'XAUUSD')
    p = tr['pnl_pip'].values * PIP
    sd = p.std(ddof=1) if len(p) > 1 else 0.0
    t = float(p.mean() / (sd / np.sqrt(len(p)))) if sd > 0 else 0.0
    sl_m = float(np.median(tr['sl_pip'].values))
    tp_m = float(np.median(tr['tp_pip'].values))
    breakeven = (sl_m + SPREAD_PIP) / (sl_m + tp_m) * 100.0
    wr = float((p > 0).mean()) * 100.0
    net = float(cap['net_profit'])
    maxdd_pct = abs(float(cap['max_dd_pct']))
    maxdd_dollar = maxdd_pct / 100.0 * 10000.0
    rec = net / maxdd_dollar if maxdd_dollar > 0 else np.inf
    return dict(n=int(len(tr)), wr=round(wr, 2), pf=round(float(cap['profit_factor']), 3),
                t=round(t, 3), maxdd=round(maxdd_pct, 2), net=round(net, 1),
                breakeven=round(breakeven, 2), wr_edge=round(wr - breakeven, 2),
                rec=round(rec, 2))


def mode_tune():
    df = se.load_data(f'data/XAUUSD_{TF}.csv')
    days = build_days(df)
    atr = daily_atr(days)
    vflags = vol_flags(days, atr)
    split = SPLIT_BAR[TF]
    rows = []
    for k_sl in (1.7, 1.85, 2.0):
        for use_v in (False, True):
            for cd in (0, 1):
                tr = run_layer(df, days, atr, k_sl, use_v, cd, vflags=vflags, hi_bar=split)
                s = judge_stats(tr)
                s.update(k_sl=k_sl, V=('ATRq78' if use_v else None), cooldown=cd)
                rows.append(s)
    out = pd.DataFrame(rows)
    out.to_json(CKPT, orient='records', indent=1)
    print(f"=== S404 tune {TF} (first half, 12 combos, judge accounting + guards) ===")
    print(out.to_string(index=False))
    ok = out[(out['n'] >= 100) & (out['pf'] > 1) & (out['t'] >= 2.5) &
             (out['maxdd'] <= 4.8) & (out['wr_edge'] >= 2.0) & (out['rec'] >= 3.0)]
    if len(ok) == 0:
        print("\n❌ NO COMBO QUALIFIES ⇒ prereg: REJECT بدونِ بازکردنِ holdout")
    else:
        w = ok.sort_values(['maxdd', 't'], ascending=[True, False]).iloc[0]
        print(f"\n🏆 WINNER (prereg: min maxDD): k_sl={w['k_sl']} V={w['V']} cd={w['cooldown']}"
              f" · n={w['n']} maxdd={w['maxdd']}% t={w['t']} pf={w['pf']}"
              f" wr_edge={w['wr_edge']}pp rec={w['rec']}")
    return 0


def mode_verdict(k_sl, use_v, cooldown_d):
    from engine import rqs2
    df = se.load_data(f'data/XAUUSD_{TF}.csv')
    days = build_days(df)
    atr = daily_atr(days)
    vflags = vol_flags(days, atr)
    split = SPLIT_BAR[TF]
    bar_time = df['dt'].values
    close = df['close'].values.astype('float64')

    strat = run_layer(df, days, atr, k_sl, use_v, cooldown_d, vflags=vflags)
    n_str = len(strat)
    print(f"strategy trades n={n_str} · holdout n={int((strat['entry_bar'] >= split).sum())}", flush=True)

    # null بازو-همتا: بدونِ آستانه/DOW/فیلترV — V جزوِ مهارت است (پیش‌ثبت §۶)
    pool_df = run_layer(df, days, atr, k_sl, False, cooldown_d,
                        no_thresh=True, no_dow=True)
    pool = pool_df['pnl_pip'].values.astype('float64')
    uncond_wr = float((pool > 0).mean() * 100.0)
    print(f"null pool = {len(pool)} uncond gap-DOWN entries (same k_sl/cd) · "
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
    print(f"perm(K={K}): mean={wrs.mean():.2f} sd={wrs.std(ddof=1):.3f} max={wrs.max():.2f}", flush=True)

    tp_meas = float(np.median(strat['tp_pip'].values))
    sl_meas = float(np.median(strat['sl_pip'].values))
    print(f"judge geometry: sl_pip={sl_meas:.1f} tp_pip={tp_meas:.1f} rr={tp_meas/sl_meas:.3f}", flush=True)

    r = rqs2.compute_rqs2(strat, 'XAUUSD', sl_pip=sl_meas, tp_pip=tp_meas,
                          bar_time=bar_time, null=null,
                          n_trials=N_TRIALS_CUM, split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S404 {TF} k_sl={k_sl}/V={use_v}/cd={cooldown_d}', r), flush=True)
    outp = os.path.join(os.path.dirname(__file__), '..', 'results', '_s404_verdict.json')
    with open(outp, 'w') as f:
        json.dump(r, f, indent=1, default=str)
    print(f"saved → {outp}", flush=True)
    return 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'tune'
    if mode == 'tune':
        sys.exit(mode_tune())
    elif mode == 'verdict':
        k_sl = float(sys.argv[2])
        v = sys.argv[3] if len(sys.argv) > 3 else 'None'
        use_v = v not in ('None', 'none', None)
        cd = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        sys.exit(mode_verdict(k_sl, use_v, cd))
    else:
        print(__doc__); sys.exit(2)
