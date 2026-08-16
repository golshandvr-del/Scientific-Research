#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S401 — گپ‌فیلِ M30 + نگهبانِ ریسک (حمله به تک‌دروازهٔ H8 والدِ S400-M30)
=======================================================================
پیش‌ثبت: results/S401_PREREG_GAP_FILL_RISKGUARD.md
والد:    S400-M30 REJECT(33.2) — فقط H8 (maxDD=13.35%>8%)؛ ده دروازهٔ دیگر ✓.

لایهٔ پایه (منجمد، از s400_gap_open): XAUUSD M30 · QW70 · X-FILL k_sl=1.5 · DOW!=0
دو اهرمِ پیش‌ثبت‌شده (۶ ترکیب):
  BE-trigger f∈{None,0.4,0.6}: پس از حرکتِ مطلوب ≥ f×(فاصلهٔ TP)، SL→ورود.
      قراردادِ ضدِ look-ahead عینِ موتور: BE فقط از بارِ *بعدِ* ورود اثر می‌کند
      و peak_favor بعد از چکِ exit همان بار به‌روز می‌شود.
  Cooldown d∈{0,1}: پس از باختِ کامل (برخوردِ SL)، d روزِ سیگنال‌دارِ بعدی رد می‌شود.

قاعدهٔ برنده (قفل): کمترین maxDD% نیمهٔ اول (run_capital داور) به شرطِ
n≥100 · PF>1 · t≥2.5 · maxDD≤6.4%. گره‌گشایی: t بزرگ‌تر.
حالت‌ها:
  python3 strategies/s401_gap_fill_riskguard.py tune     ← نیمهٔ اولِ M30
  python3 strategies/s401_gap_fill_riskguard.py verdict  ← آزمونِ یک‌بارهٔ رسمی
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se
from strategies.s400_gap_open import (build_days, daily_atr, thresholds_for_day,
                                      SPLIT_BAR, PIP, SPREAD_PIP, SEED)

TF = 'M30'
BASE = dict(fam='QW', par=70, k_sl=1.5, dow_drop=0)   # منجمد از S400
N_TRIALS_CUM = 222                                     # 216 + 6 (پیش‌ثبت §۳)
CKPT = os.path.join(os.path.dirname(__file__), '..', 'results', '_s401_tune_ckpt.json')


def sim_trade_be(arrays, day, k_sl, be_f):
    """X-FILL با BE-trigger اختیاری. قراردادها عینِ موتور:
    - چکِ exit با cur_sl تعیین‌شده از بارهای قبل؛ TP∧SL همزمان = باخت
    - peak_favor/BE فقط بعد از چکِ exit و فقط از بارِ بعدِ ورود"""
    o, h, l, c = arrays
    fb, last = day['fb'], day['last']
    entry = o[fb]
    agap = abs(day['gap'])
    if agap <= 0:
        return None
    sl_price = entry - k_sl * agap
    tp_price = day['prev_close']
    tp_dist = tp_price - entry

    outcome_price, exit_bar = None, None
    cur_sl = sl_price
    peak_favor = 0.0
    full_sl = False
    for j in range(fb, last + 1):
        hit_sl = l[j] <= cur_sl
        hit_tp = h[j] >= tp_price
        if hit_sl and hit_tp:
            outcome_price, exit_bar = cur_sl, j
            full_sl = (cur_sl <= sl_price)
            break
        elif hit_tp:
            outcome_price, exit_bar = tp_price, j; break
        elif hit_sl:
            outcome_price, exit_bar = cur_sl, j
            full_sl = (cur_sl <= sl_price)
            break
        if j == fb:
            continue                        # قراردادِ موتور: در بارِ ورود BE فعال نمی‌شود
        if be_f is not None:
            favor = h[j] - entry
            if favor > peak_favor:
                peak_favor = favor
            if peak_favor >= be_f * tp_dist:
                cur_sl = max(cur_sl, entry)
    if outcome_price is None:
        exit_bar = last
        outcome_price = c[last]

    pnl_pip = (outcome_price - entry) / PIP - SPREAD_PIP
    return {
        'signal_bar': fb - 1, 'entry_bar': fb, 'exit_bar': int(exit_bar),
        'direction': 'long', 'entry_price': float(entry),
        'exit_price': float(outcome_price),
        'outcome': 'win' if pnl_pip > 0 else 'loss',
        'pnl_pip': float(pnl_pip),
        'sl_pip': float((entry - sl_price) / PIP),
        'tp_pip': float(tp_dist / PIP),
        'bars_held': int(exit_bar - fb),
        'dow': day['dow'], 'full_sl': bool(full_sl),
    }


def run_layer(df, days, atr, be_f, cooldown_d, lo_bar=None, hi_bar=None,
              no_thresh=False, no_dow=False):
    """اجرای S401. cooldown روی *روزهای سیگنال‌دار* پس از باختِ کامل اعمال می‌شود.
    no_thresh/no_dow برای ساختِ استخرِ null بازو-همتا."""
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
        # این روز سیگنال دارد — cooldown مصرف می‌شود حتی اگر رد شود
        if skip_left > 0:
            skip_left -= 1
            continue
        tr = sim_trade_be(arrays, d, BASE['k_sl'], be_f)
        if tr is None:
            continue
        trades.append(tr)
        if cooldown_d > 0 and tr['full_sl']:
            skip_left = cooldown_d
    return pd.DataFrame(trades)


def judge_stats(tr, first_half_only=True):
    """آمارِ فازِ تنظیم با *حسابداریِ خودِ داور* (run_capital)."""
    if len(tr) == 0:
        return dict(n=0, wr=np.nan, pf=np.nan, t=np.nan, maxdd=np.nan, net=np.nan)
    cap, _ = se.run_capital(tr, 'XAUUSD')
    p = tr['pnl_pip'].values * PIP
    sd = p.std(ddof=1) if len(p) > 1 else 0.0
    t = float(p.mean() / (sd / np.sqrt(len(p)))) if sd > 0 else 0.0
    return dict(n=int(len(tr)), wr=round(float((p > 0).mean()), 4),
                pf=round(float(cap['profit_factor']), 3),
                t=round(t, 3), maxdd=round(abs(float(cap['max_dd_pct'])), 2),
                net=round(float(cap['net_profit']), 1))


def mode_tune():
    df = se.load_data(f'data/XAUUSD_{TF}.csv')
    days = build_days(df)
    atr = daily_atr(days)
    split = SPLIT_BAR[TF]
    rows = []
    for be_f in (None, 0.4, 0.6):
        for cd in (0, 1):
            tr = run_layer(df, days, atr, be_f, cd, hi_bar=split)
            s = judge_stats(tr)
            s.update(be_f=be_f, cooldown=cd)
            rows.append(s)
    out = pd.DataFrame(rows)
    out.to_json(CKPT, orient='records', indent=1)
    print(f"=== S401 tune {TF} (first half, 6 combos, judge accounting) ===")
    print(out.to_string(index=False))
    ok = out[(out['n'] >= 100) & (out['pf'] > 1) & (out['t'] >= 2.5) & (out['maxdd'] <= 6.4)]
    if len(ok) == 0:
        print("\n❌ NO COMBO QUALIFIES ⇒ prereg: REJECT بدونِ بازکردنِ holdout")
    else:
        w = ok.sort_values(['maxdd', 't'], ascending=[True, False]).iloc[0]
        print(f"\n🏆 WINNER (prereg: min maxDD): be_f={w['be_f']} cooldown={w['cooldown']}"
              f" · n={w['n']} maxdd={w['maxdd']}% t={w['t']} pf={w['pf']}")
    return 0


def mode_verdict(be_f, cooldown_d):
    from engine import rqs2
    df = se.load_data(f'data/XAUUSD_{TF}.csv')
    days = build_days(df)
    atr = daily_atr(days)
    split = SPLIT_BAR[TF]
    bar_time = df['dt'].values
    close = df['close'].values.astype('float64')

    strat = run_layer(df, days, atr, be_f, cooldown_d)
    n_str = len(strat)
    print(f"strategy trades n={n_str} · holdout n={int((strat['entry_bar'] >= split).sum())}", flush=True)

    # null بازو-همتا: همهٔ روزهای gap-DOWN بی‌قید (بدونِ آستانه/DOW) با همان
    # اهرم‌های be_f/cooldown — تا lift فقط ارزشِ آستانه+فیلتر باشد.
    pool_df = run_layer(df, days, atr, be_f, cooldown_d, no_thresh=True, no_dow=True)
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
    print(rqs2.format_rqs2(f'S401 {TF} be={be_f}/cd={cooldown_d}', r), flush=True)
    outp = os.path.join(os.path.dirname(__file__), '..', 'results', '_s401_verdict.json')
    with open(outp, 'w') as f:
        json.dump(r, f, indent=1, default=str)
    print(f"saved → {outp}", flush=True)
    return 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'tune'
    if mode == 'tune':
        sys.exit(mode_tune())
    elif mode == 'verdict':
        be = sys.argv[2] if len(sys.argv) > 2 else None
        be_f = None if be in (None, 'None') else float(be)
        cd = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        sys.exit(mode_verdict(be_f, cd))
    else:
        print(__doc__); sys.exit(2)
