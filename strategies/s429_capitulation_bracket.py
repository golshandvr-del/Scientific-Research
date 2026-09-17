#!/usr/bin/env python3
"""S429 — Capitulation Bracket Harvest · XAUUSD-H1.

پیش‌ثبت: results/S429_PREREGISTRATION_CapitulationBracket.md (کامیت 0ae4bdeb — قبل از این فایل).
سیگنال: بیت‌به‌بیتِ قفلِ S420 (q=0.75, d=1.5, W=5) — LONG در open روزِ بعد.
هندسه: SL = TP = k·ATR_d14[i] (pip) ؛ خروجِ زمانیِ پشتیبان close روزِ i+10 ؛ k ∈ {1.0, 1.5}.
داده: data/mt5_full/XAUUSD_H1.csv.gz

  python3 strategies/s429_capitulation_bracket.py scan
  python3 strategies/s429_capitulation_bracket.py lock k=..
  python3 strategies/s429_capitulation_bracket.py confirm
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                     # noqa: E402
from engine import rqs2 as rq                             # noqa: E402
from strategies.s420_capitulation_decel import (          # noqa: E402
    build_trading_days, daily_features, signal_days, windows, W)
from strategies.s423_quiet_trend import _clean, ASSET     # noqa: E402
from strategies.s425_quiet_trend_body import day_ohlc     # noqa: E402

DATA = 'data/mt5_full/XAUUSD_H1.csv.gz'
assert 'mt5_full' in DATA
Q, D, HOLD = 0.75, 1.5, 10          # قفلِ S420 — جست‌وجو نمی‌شود
ATR_N = 14
GRID_K = (1.0, 1.5)
N_TRIALS = 10                       # 8 (شبکهٔ S420) + 2 (k)
NULL_K = 500
NULL_SEED = 42929
EFDR_MULT = 6
OUT_DIR = 'results/_scan_S420'
LOCK_PATH = os.path.join(OUT_DIR, 'S429_LOCKED_CONFIG.json')


def daily_atr(ohlc):
    """ATR_d[i] = میانگینِ TR روزانهٔ روزهای [i−13..i] (قیمت). علّی."""
    n = len(ohlc)
    tr = np.full(n, np.nan)
    for i in range(1, n):
        o, h, l, c = ohlc[i]
        cp = ohlc[i - 1][3]
        tr[i] = max(h - l, abs(h - cp), abs(l - cp))
    atr = np.full(n, np.nan)
    for i in range(ATR_N, n):
        w = tr[i - ATR_N + 1:i + 1]
        if not np.isnan(w).any():
            atr[i] = w.mean()
    return atr


def run_trades(df, days, sig_idx, atr, k):
    """براکتِ k·ATR_d روی کندلِ سیگنال (last_bar روزِ i)، ورودِ open کندلِ بعد، hold تا پایانِ روزِ i+HOLD."""
    pip = se.ASSETS[ASSET]['pip']
    all_tr = []
    busy_until = -1
    for i in sig_idx:
        if np.isnan(atr[i]):
            continue
        sig_bar = days[i]['last_bar']
        entry_bar = sig_bar + 1
        if entry_bar <= busy_until or entry_bar >= len(df):
            continue
        exit_day = min(i + HOLD, len(days) - 1)
        max_hold = days[exit_day]['last_bar'] - entry_bar + 1
        if max_hold < 1:
            continue
        br = k * atr[i] / pip
        ls = np.zeros(len(df), dtype=bool)
        ls[sig_bar] = True
        tr = se.simulate_trades(df, ls, np.zeros(len(df), dtype=bool), br, br, ASSET,
                                max_hold=max_hold, allow_overlap=False)
        if len(tr) == 0:
            continue
        tr['sig_day'] = i
        tr['atr_pip'] = atr[i] / pip
        busy_until = int(tr.iloc[0]['exit_bar'])
        all_tr.append(tr)
    if not all_tr:
        return pd.DataFrame()
    return pd.concat(all_tr, ignore_index=True)


def fast_pnl(df, days, i, atr, k):
    """مسیرِ سریعِ هم‌ارزِ موتور برای یک ورودِ LONG روزِ i (برای نول). برمی‌گرداند (pnl_pip, exit_bar)."""
    cfg = se.ASSETS[ASSET]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    o, h, l, c = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    eb = days[i]['last_bar'] + 1
    xd = min(i + HOLD, len(days) - 1)
    end = min(days[xd]['last_bar'] + 1, len(df))
    fill = o[eb] + slip * pip
    br = k * atr[i]
    sl_p, tp_p = fill - br, fill + br
    for j in range(eb, end):
        hit_sl = l[j] <= sl_p
        hit_tp = h[j] >= tp_p
        if hit_sl:                       # sl∧tp ⇒ loss (ابهام = بدترین) — همان موتور
            return (sl_p - slip * pip - fill) / pip - spread, j
        if hit_tp:
            return (tp_p - slip * pip - fill) / pip - spread, j
    return (c[end - 1] - slip * pip - fill) / pip - spread, end - 1


def selftest(df, days, trades, atr, k):
    mx = 0.0
    for _, r in trades.iterrows():
        p, xb = fast_pnl(df, days, int(r['sig_day']), atr, k)
        mx = max(mx, abs(p - float(r['pnl_pip'])))
        assert xb == int(r['exit_bar']), (r['sig_day'], xb, r['exit_bar'])
    return mx


def build_null(df, days, n_entries, atr, k, lo, hi, seed):
    rng = np.random.default_rng(seed)
    cand = np.array([i for i in range(lo + ATR_N, hi - HOLD - 1) if not np.isnan(atr[i])])
    wrs, exps = [], []
    for _ in range(NULL_K):
        picks = np.sort(rng.choice(cand, size=min(n_entries * 3, len(cand)), replace=False))
        wins = tot = 0
        pn = 0.0
        busy = -1
        for i in picks:
            if tot >= n_entries:
                break
            eb = days[i]['last_bar'] + 1
            if eb <= busy:
                continue
            p, xb = fast_pnl(df, days, i, atr, k)
            wins += int(p > 0)
            pn += p
            tot += 1
            busy = xb
        if tot:
            wrs.append(wins / tot * 100)
            exps.append(pn / tot)
    wrs = np.array(wrs)
    side = dict(uncond_wr=float(wrs.mean()), perm_mean=float(wrs.mean()), perm_sd=float(wrs.std()),
                perm_max=float(wrs.max()), perm_k=len(wrs), perm_exp_mean=float(np.mean(exps)))
    return {'long': side, 'short': dict(side)}


def breakeven_wr(trades):
    """سربه‌سرِ هزینه‌دار برای SL=TP: WR* = (SL+spread)/(2·SL) با SL میانه."""
    spread = se.ASSETS[ASSET]['spread_pip']
    sl = float(np.median(trades['sl_pip'].values))
    return (sl + spread) / (2 * sl) * 100, sl


def _load():
    df = se.load_data(DATA)
    days = build_trading_days(df)
    rets, trend, vol = daily_features(days)
    ohlc = day_ohlc(df, days)
    atr = daily_atr(ohlc)
    return df, days, rets, trend, vol, atr


def run_k(df, days, rets, trend, vol, atr, k, lo, hi):
    sig = [i for i in signal_days(days, rets, trend, vol, Q, D) if lo <= i < hi - HOLD - 1]
    trades = run_trades(df, days, sig, atr, k)
    if len(trades) == 0:
        return None, trades
    p = trades['pnl_pip'].values
    n = len(trades)
    be, sl_med = breakeven_wr(trades)
    wr = float((p > 0).mean() * 100)
    exp = float(p.mean())
    sd = p.std(ddof=1)
    t = exp / (sd / np.sqrt(n)) if n > 2 and sd > 0 else 0.0
    return dict(k=k, n=n, n_signals=len(sig), wr=wr, be_wr=float(be), sl_pip_med=sl_med, exp_pip=exp,
                t=float(t), net_pip=float(p.sum()),
                outcomes=trades['outcome'].value_counts().to_dict(),
                proxy=float((wr - be) * np.sqrt(n))), trades


def cmd_scan():
    df, days, rets, trend, vol, atr = _load()
    lo, hi = windows(days)['discover']
    print(f"[scan] data={DATA} bars={len(df)} last={df['dt'].iloc[-1]}")
    print(f"[scan] discover window: days[{lo}:{hi}] ({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    rows = []
    for k in GRID_K:
        r, trades = run_k(df, days, rets, trend, vol, atr, k, lo, hi)
        if r is None:
            print(f"  k={k}: no trades")
            continue
        r['selftest_max_abs_diff'] = float(selftest(df, days, trades, atr, k))
        assert r['selftest_max_abs_diff'] < 1e-6
        r['alive'] = bool(r['exp_pip'] > 0 and r['n'] >= 30 and r['wr'] > r['be_wr'])
        rows.append(r)
        print(f"  k={k}: n={r['n']} WR={r['wr']:.1f}% BE={r['be_wr']:.1f}% SLmed={r['sl_pip_med']:.0f}pip "
              f"exp={r['exp_pip']:+.1f} t={r['t']:+.2f} net={r['net_pip']:+.0f} proxy={r['proxy']:+.1f} "
              f"outcomes={r['outcomes']} selftest={r['selftest_max_abs_diff']:.2e} alive={r['alive']}")
    alive = [r for r in rows if r['alive']]
    print(f"[scan] alive (exp>0 ∧ n≥30 ∧ WR>BE): {len(alive)}"
          + ("  → EARLY DEATH: virgin window stays closed" if not alive else ""))
    if alive:
        best = max(alive, key=lambda r: r['proxy'])
        print(f"[scan] best by proxy: k={best['k']}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'S429_scan_discover.json'), 'w') as f:
        json.dump(_clean(rows), f, indent=1, ensure_ascii=False)
    print("[scan] saved → results/_scan_S420/S429_scan_discover.json")


def cmd_lock(k):
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = dict(strategy='S429_CapitulationBracket', asset=ASSET, data=DATA, q=Q, d=D, W=W, hold=HOLD,
               atr_n=ATR_N, k=k, geometry='SL=TP=k*ATR_d', direction='long_only',
               n_trials=N_TRIALS, efdr_mult=EFDR_MULT,
               prereg='results/S429_PREREGISTRATION_CapitulationBracket.md')
    with open(LOCK_PATH, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    print(f"[lock] frozen → {LOCK_PATH}")
    print(json.dumps(cfg, indent=1, ensure_ascii=False))


def cmd_confirm():
    with open(LOCK_PATH) as f:
        k = json.load(f)['k']
    df, days, rets, trend, vol, atr = _load()
    lo, hi = windows(days)['confirm']
    print(f"[confirm] data={DATA}")
    print(f"[confirm] SEMI-VIRGIN window: days[{lo}:{hi}] ({days[lo]['date'].date()} → {days[hi-1]['date'].date()}) k={k}")
    r, trades = run_k(df, days, rets, trend, vol, atr, k, lo, hi)
    if r is None:
        print("[confirm] NO TRADES")
        return
    st = selftest(df, days, trades, atr, k)
    assert st < 1e-6
    print(f"[confirm] n={r['n']} WR={r['wr']:.1f}% BE={r['be_wr']:.1f}% SLmed={r['sl_pip_med']:.0f}pip "
          f"exp={r['exp_pip']:+.1f} t={r['t']:+.2f} net={r['net_pip']:+.0f} outcomes={r['outcomes']} selftest={st:.2e}")
    null = build_null(df, days, r['n'], atr, k, lo, hi, NULL_SEED)
    print(f"[confirm] null: mean={null['long']['perm_mean']:.2f}% sd={null['long']['perm_sd']:.2f} "
          f"max={null['long']['perm_max']:.2f} exp={null['long']['perm_exp_mean']:+.1f} k={null['long']['perm_k']}")
    split_bar = days[lo + int((hi - lo) * 0.60)]['first_bar']
    res = rq.compute_rqs2(trades, ASSET, sl_pip=r['sl_pip_med'], tp_pip=r['sl_pip_med'],
                          bar_time=df['time'].values, null=null, n_trials=N_TRIALS,
                          split_bar=split_bar, close=df['close'].values)
    p_emp = res['metrics'].get('skill_p_perm')
    if p_emp is not None:
        res['metrics']['efdr_cross_hypotheses'] = float(p_emp) * EFDR_MULT
    with open(os.path.join(OUT_DIR, 'S429_confirm_virgin_rqs2.json'), 'w') as f:
        json.dump(_clean(dict(result=res, headline=r, null=null)), f, indent=1, ensure_ascii=False)
    print(f"[confirm] verdict = {res['verdict']}  score = {res['rqs2_score']}")
    print(f"[confirm] gates: {res['gates']}")
    print("[confirm] saved → results/_scan_S420/S429_confirm_virgin_rqs2.json")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    if mode == 'scan':
        cmd_scan()
    elif mode == 'lock':
        kv = dict(x.split('=') for x in sys.argv[2:])
        cmd_lock(float(kv['k']))
    elif mode == 'confirm':
        cmd_confirm()
    else:
        raise SystemExit(f"unknown mode {mode!r}")
