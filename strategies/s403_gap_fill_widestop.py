#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S403 — گپ‌فیلِ M30 + استاپِ پهن (حملهٔ سوم به تک‌دروازهٔ H8)
=============================================================
پیش‌ثبت: results/S403_PREREG_GAP_FILL_WIDESTOP.md
والدها:  S400-M30 REJECT فقط-H8 · S401 REJECT (6.46%) · S402 REJECT (time-stop خنثی).

لایهٔ پایه (منجمد به‌جز k_sl، از s400): XAUUSD M30 · QW70 · X-FILL · DOW!=0
سه اهرمِ پیش‌ثبت‌شده (۱۲ ترکیب):
  k_sl∈{2.2,2.7,3.3} · BE-trigger f∈{None,0.4} · cooldown d∈{0,1}
قاعدهٔ برنده (قفل): کمترین maxDD% نیمهٔ اول (run_capital داور) به شرطِ
n≥100 · PF>1 · t≥2.5 · maxDD≤6.40% · WR≥breakeven+2pp · net/maxDD$ ≥ 3.
هیچ ترکیبی واجد نشد ⇒ REJECT بدونِ بازکردنِ holdout.
حالت‌ها:
  python3 strategies/s403_gap_fill_widestop.py tune
  python3 strategies/s403_gap_fill_widestop.py verdict <k_sl> <be_f|None> <cd>
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se
from strategies.s400_gap_open import (build_days, daily_atr, thresholds_for_day,
                                      SPLIT_BAR, PIP, SPREAD_PIP, SEED)
from strategies.s401_gap_fill_riskguard import sim_trade_be   # همان قراردادها؛ k_sl پارامتری

TF = 'M30'
BASE = dict(fam='QW', par=70, dow_drop=0)   # منجمد از S400 (k_sl حالا اهرم است)
N_TRIALS_CUM = 246                           # 234 + 12 (پیش‌ثبت §۵)
CKPT = os.path.join(os.path.dirname(__file__), '..', 'results', '_s403_tune_ckpt.json')


def run_layer(df, days, atr, k_sl, be_f, cooldown_d, lo_bar=None, hi_bar=None,
              no_thresh=False, no_dow=False):
    """اجرای S403 (عینِ run_layer در S401 اما k_sl پارامتری)."""
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
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
        if skip_left > 0:
            skip_left -= 1
            continue
        tr = sim_trade_be(arrays, d, k_sl, be_f)
        if tr is None:
            continue
        trades.append(tr)
        if cooldown_d > 0 and tr['full_sl']:
            skip_left = cooldown_d
    return pd.DataFrame(trades)


def judge_stats(tr):
    """آمارِ فازِ تنظیم با حسابداریِ خودِ داور + نگهبان‌های H2/recovery پیش‌ثبت‌شده."""
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
    # maxDD دلاری: از منحنیِ سرمایهٔ داور — تقریبِ محافظه‌کار: dd% × سرمایهٔ اولیه
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
    split = SPLIT_BAR[TF]
    rows = []
    for k_sl in (2.2, 2.7, 3.3):
        for be_f in (None, 0.4):
            for cd in (0, 1):
                tr = run_layer(df, days, atr, k_sl, be_f, cd, hi_bar=split)
                s = judge_stats(tr)
                s.update(k_sl=k_sl, be_f=be_f, cooldown=cd)
                rows.append(s)
    out = pd.DataFrame(rows)
    out.to_json(CKPT, orient='records', indent=1)
    print(f"=== S403 tune {TF} (first half, 12 combos, judge accounting + guards) ===")
    print(out.to_string(index=False))
    ok = out[(out['n'] >= 100) & (out['pf'] > 1) & (out['t'] >= 2.5) &
             (out['maxdd'] <= 6.4) & (out['wr_edge'] >= 2.0) & (out['rec'] >= 3.0)]
    if len(ok) == 0:
        print("\n❌ NO COMBO QUALIFIES ⇒ prereg: REJECT بدونِ بازکردنِ holdout")
    else:
        w = ok.sort_values(['maxdd', 't'], ascending=[True, False]).iloc[0]
        print(f"\n🏆 WINNER (prereg: min maxDD): k_sl={w['k_sl']} be_f={w['be_f']} cd={w['cooldown']}"
              f" · n={w['n']} maxdd={w['maxdd']}% t={w['t']} pf={w['pf']}"
              f" wr_edge={w['wr_edge']}pp rec={w['rec']}")
    return 0


def mode_verdict(k_sl, be_f, cooldown_d):
    from engine import rqs2
    df = se.load_data(f'data/XAUUSD_{TF}.csv')
    days = build_days(df)
    atr = daily_atr(days)
    split = SPLIT_BAR[TF]
    bar_time = df['dt'].values
    close = df['close'].values.astype('float64')

    strat = run_layer(df, days, atr, k_sl, be_f, cooldown_d)
    n_str = len(strat)
    print(f"strategy trades n={n_str} · holdout n={int((strat['entry_bar'] >= split).sum())}", flush=True)

    pool_df = run_layer(df, days, atr, k_sl, be_f, cooldown_d, no_thresh=True, no_dow=True)
    pool = pool_df['pnl_pip'].values.astype('float64')
    uncond_wr = float((pool > 0).mean() * 100.0)
    print(f"null pool = {len(pool)} uncond gap-DOWN entries (same levers) · "
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
    print(f"judge geometry: sl_pip={sl_meas:.1f} tp_pip={tp_meas:.1f}", flush=True)

    r = rqs2.compute_rqs2(strat, 'XAUUSD', sl_pip=sl_meas, tp_pip=tp_meas,
                          bar_time=bar_time, null=null,
                          n_trials=N_TRIALS_CUM, split_bar=split, close=close)
    print(rqs2.format_rqs2(f'S403 {TF} k_sl={k_sl}/be={be_f}/cd={cooldown_d}', r), flush=True)
    outp = os.path.join(os.path.dirname(__file__), '..', 'results', '_s403_verdict.json')
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
        be = sys.argv[3] if len(sys.argv) > 3 else None
        be_f = None if be in (None, 'None') else float(be)
        cd = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        sys.exit(mode_verdict(k_sl, be_f, cd))
    else:
        print(__doc__); sys.exit(2)
