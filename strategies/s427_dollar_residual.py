#!/usr/bin/env python3
"""S427 — Dollar-Residual Divergence Reversion · XAUUSD-H1.

پیش‌ثبت: results/S427_PREREGISTRATION_DollarResidual.md (کامیت 501bc035 — قبل از این فایل).
داده: data/mt5_full/XAUUSD_H1.csv.gz (کامل ۱۵.۶ ساله — دستور مأموریت) + data/EURUSD_H1.csv (ورودیِ سیگنال).

سیگنال روزانه (علّی):
  r_g, r_e  = بازدهٔ log روزانهٔ طلا و EURUSD (کلوزِ EUR هم‌زمان‌شده با آخرین کندلِ روزِ طلا)
  β[i]      = cov/var روی روزهای [i-B, i-1]
  res[k]    = r_g[k] − β[i]·r_e[k]        ;  R5[i] = Σ res[i-4..i]
  z[i]      = R5[i] / sd(R5[i-B..i-1])
  z ≤ −θ ⇒ LONG · z ≥ +θ ⇒ SHORT   (ورود open روزِ i+1، خروج زمانی close روزِ i+hold)

اجرا:
  python3 strategies/s427_dollar_residual.py scan
  python3 strategies/s427_dollar_residual.py lock theta=.. hold=..
  python3 strategies/s427_dollar_residual.py confirm
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                     # noqa: E402
from engine import rqs2 as rq                             # noqa: E402
from strategies.s420_capitulation_decel import build_trading_days  # noqa: E402
from strategies.s423_quiet_trend import (                 # noqa: E402
    run_trades, verify_no_bracket_hits, build_null, windows, _clean,
    ASSET, VIRTUAL_BRACKET_PIP)

DATA = 'data/mt5_full/XAUUSD_H1.csv.gz'
assert 'mt5_full' in DATA
EUR_DATA = 'data/EURUSD_H1.csv'
W = 5
B = 60
GRID_THETA = (1.5, 2.0)
GRID_HOLD = (3, 5)
N_TRIALS = 4
NULL_SEED = 42727
EFDR_MULT = 5
OUT_DIR = 'results/_scan_S420'
LOCK_PATH = os.path.join(OUT_DIR, 'S427_LOCKED_CONFIG.json')


def eur_daily_close(df_g, days, df_e):
    """کلوزِ EUR برای هر روزِ طلا = آخرین کندلِ EUR با time ≤ time(last_bar روز). علّی."""
    te = df_e['time'].values
    ce = df_e['close'].values
    tg = df_g['time'].values
    out = np.full(len(days), np.nan)
    for i, d in enumerate(days):
        t_last = tg[d['last_bar']]
        j = np.searchsorted(te, t_last, side='right') - 1
        if j >= 0 and t_last - te[j] <= 3 * 3600:      # حداکثر ۳ ساعت کهنگی
            out[i] = ce[j]
    return out


def residual_z(days, eur_close, lo):
    """z[i] برای i در پنجره؛ همهٔ تاریخچه‌ها از ابتدای همان پنجره (lo) — ضدِ نشت."""
    cg = np.array([d['close'] for d in days])
    n = len(days)
    rg = np.full(n, np.nan)
    re_ = np.full(n, np.nan)
    rg[1:] = np.log(cg[1:] / cg[:-1])
    re_[1:] = np.log(eur_close[1:] / eur_close[:-1])
    z = np.full(n, np.nan)
    r5 = np.full(n, np.nan)
    beta = np.full(n, np.nan)
    for i in range(lo + B + W, n):
        a = rg[i - B:i]
        b = re_[i - B:i]
        ok = ~(np.isnan(a) | np.isnan(b))
        if ok.sum() < B * 0.8 or np.isnan(rg[i]) or np.isnan(re_[i]):
            continue
        vb = np.var(b[ok])
        if vb <= 0:
            continue
        bt = np.cov(a[ok], b[ok], ddof=0)[0, 1] / vb
        beta[i] = bt
        win_g = rg[i - W + 1:i + 1]
        win_e = re_[i - W + 1:i + 1]
        if np.isnan(win_g).any() or np.isnan(win_e).any():
            continue
        r5[i] = float(np.sum(win_g - bt * win_e))
    for i in range(lo + B + W, n):
        hist = r5[i - B:i]
        hist = hist[~np.isnan(hist)]
        if len(hist) < 30 or np.isnan(r5[i]):
            continue
        sd = hist.std()
        if sd > 0:
            z[i] = r5[i] / sd
    return z, r5, beta


def signal_days(z, theta, lo, hi, hold):
    sig = []
    for i in range(lo, hi - hold - 1):
        if np.isnan(z[i]):
            continue
        if z[i] <= -theta:
            sig.append((i, 'long'))
        elif z[i] >= theta:
            sig.append((i, 'short'))
    return sig


def run_combo(df, days, z, theta, hold, lo, hi):
    sig = signal_days(z, theta, lo, hi, hold)
    trades = run_trades(df, days, sig, hold)
    if len(trades) == 0:
        return None, trades
    p = trades['pnl_pip'].values
    n = len(trades)
    n_long = int((trades['direction'] == 'long').sum())
    pl = trades.loc[trades['direction'] == 'long', 'pnl_pip'].values
    ps = trades.loc[trades['direction'] == 'short', 'pnl_pip'].values
    wr = float((p > 0).mean() * 100)
    exp = float(p.mean())
    sd = p.std(ddof=1)
    t = exp / (sd / np.sqrt(n)) if n > 2 and sd > 0 else 0.0
    return dict(theta=theta, hold=hold, n=n, n_long=n_long, n_short=n - n_long,
                n_signals=len(sig),
                wr=wr, exp_pip=exp, t=float(t), net_pip=float(p.sum()),
                wr_long=float((pl > 0).mean() * 100) if len(pl) else None,
                exp_long=float(pl.mean()) if len(pl) else None,
                wr_short=float((ps > 0).mean() * 100) if len(ps) else None,
                exp_short=float(ps.mean()) if len(ps) else None), trades


def _load():
    df = se.load_data(DATA)
    dfe = se.load_data(EUR_DATA)
    days = build_trading_days(df)
    eur = eur_daily_close(df, days, dfe)
    return df, days, eur


def _fmt(x):
    return 'NA' if x is None else f"{x:+.1f}"


def cmd_scan():
    df, days, eur = _load()
    lo, hi = windows(days)['discover']
    print(f"[scan] data={DATA} bars={len(df)} last={df['dt'].iloc[-1]}")
    print(f"[scan] discover window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})  "
          f"EUR-missing days in window: {int(np.isnan(eur[lo:hi]).sum())}")
    z, r5, beta = residual_z(days, eur, lo)
    zz = z[lo:hi]
    zz = zz[~np.isnan(zz)]
    print(f"[scan] z stats: n={len(zz)} mean={zz.mean():+.2f} sd={zz.std():.2f} "
          f"|z|>=1.5: {(np.abs(zz)>=1.5).mean()*100:.1f}%  |z|>=2: {(np.abs(zz)>=2).mean()*100:.1f}%  "
          f"beta median={np.nanmedian(beta[lo:hi]):+.2f}")
    rows = []
    for theta in GRID_THETA:
        for hold in GRID_HOLD:
            r, trades = run_combo(df, days, z, theta, hold, lo, hi)
            if r is None:
                print(f"  theta={theta} hold={hold}: no trades")
                continue
            r['proxy'] = (r['wr'] - 50.0) * np.sqrt(r['n'])
            r['bracket_hits'] = verify_no_bracket_hits(trades, df)
            rows.append(r)
            print(f"  theta={theta} hold={hold}: n={r['n']:3d} (L{r['n_long']}/S{r['n_short']}) "
                  f"WR={r['wr']:5.1f}% exp={r['exp_pip']:+7.1f}pip t={r['t']:+5.2f} "
                  f"net={r['net_pip']:+9.0f} proxy={r['proxy']:+6.1f} bh={r['bracket_hits']} | "
                  f"L: WR={_fmt(r['wr_long'])} exp={_fmt(r['exp_long'])} | "
                  f"S: WR={_fmt(r['wr_short'])} exp={_fmt(r['exp_short'])}")
    alive = [r for r in rows if r['exp_pip'] > 0 and r['n'] >= 30 and r['wr'] > 50.0]
    print(f"[scan] alive combos (exp>0 ∧ n≥30 ∧ WR>50): {len(alive)}"
          + ("  → EARLY DEATH: virgin window stays closed" if not alive else ""))
    if alive:
        best = max(alive, key=lambda r: r['proxy'])
        print(f"[scan] best by proxy: theta={best['theta']} hold={best['hold']} proxy={best['proxy']:+.1f}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'S427_scan_discover.json'), 'w') as f:
        json.dump(_clean(rows), f, indent=1, ensure_ascii=False)
    print("[scan] saved → results/_scan_S420/S427_scan_discover.json")


def cmd_lock(theta, hold):
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = dict(strategy='S427_DollarResidual', asset=ASSET, data=DATA, eur_data=EUR_DATA,
               W=W, B=B, theta=theta, hold=hold, direction='both_symmetric',
               bracket_pip=VIRTUAL_BRACKET_PIP, n_trials=N_TRIALS, efdr_mult=EFDR_MULT,
               prereg='results/S427_PREREGISTRATION_DollarResidual.md')
    with open(LOCK_PATH, 'w') as f:
        json.dump(cfg, f, indent=1, ensure_ascii=False)
    print(f"[lock] frozen → {LOCK_PATH}")
    print(json.dumps(cfg, indent=1, ensure_ascii=False))


def cmd_confirm():
    with open(LOCK_PATH) as f:
        cfg = json.load(f)
    theta, hold = cfg['theta'], cfg['hold']
    df, days, eur = _load()
    lo, hi = windows(days)['confirm']
    print(f"[confirm] data={DATA}")
    print(f"[confirm] VIRGIN window: days[{lo}:{hi}]  "
          f"({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    print(f"[confirm] locked: theta={theta} hold={hold} (both sides)")
    z, r5, beta = residual_z(days, eur, lo)
    r, trades = run_combo(df, days, z, theta, hold, lo, hi)
    if r is None:
        print("[confirm] NO TRADES")
        return
    hits = verify_no_bracket_hits(trades, df)
    print(f"[confirm] n={r['n']} (L{r['n_long']}/S{r['n_short']}) WR={r['wr']:.1f}% "
          f"exp={r['exp_pip']:+.1f}pip t={r['t']:+.2f} net={r['net_pip']:+.0f}pip bracket_hits={hits}")
    print(f"[confirm] long: WR={_fmt(r['wr_long'])} exp={_fmt(r['exp_long'])} | "
          f"short: WR={_fmt(r['wr_short'])} exp={_fmt(r['exp_short'])}")
    assert hits == 0
    null = build_null(df, days, r['n_long'], r['n_short'], hold, lo, hi, seed=NULL_SEED)
    print(f"[confirm] null: long mean={null['long']['perm_mean']:.2f}% sd={null['long']['perm_sd']:.2f} | "
          f"short mean={null['short']['perm_mean']:.2f}% sd={null['short']['perm_sd']:.2f} k={null['short']['perm_k']}")
    split_bar = days[lo + int((hi - lo) * 0.60)]['first_bar']
    res = rq.compute_rqs2(
        trades, ASSET,
        sl_pip=VIRTUAL_BRACKET_PIP, tp_pip=VIRTUAL_BRACKET_PIP,
        bar_time=df['time'].values, null=null, n_trials=N_TRIALS,
        split_bar=split_bar, close=df['close'].values,
    )
    p_emp = res['metrics'].get('skill_p_perm')
    if p_emp is not None:
        res['metrics']['efdr_cross_hypotheses'] = float(p_emp) * EFDR_MULT
    with open(os.path.join(OUT_DIR, 'S427_confirm_virgin_rqs2.json'), 'w') as f:
        json.dump(_clean(dict(result=res, headline=r, null=null)), f, indent=1, ensure_ascii=False)
    print(f"[confirm] verdict = {res['verdict']}  score = {res['rqs2_score']}")
    print(f"[confirm] gates: {res['gates']}")
    print("[confirm] saved → results/_scan_S420/S427_confirm_virgin_rqs2.json")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'scan'
    if mode == 'scan':
        cmd_scan()
    elif mode == 'lock':
        kv = dict(x.split('=') for x in sys.argv[2:])
        cmd_lock(float(kv['theta']), int(kv['hold']))
    elif mode == 'confirm':
        cmd_confirm()
    else:
        raise SystemExit(f"unknown mode {mode!r}")
