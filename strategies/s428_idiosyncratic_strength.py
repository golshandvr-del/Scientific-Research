#!/usr/bin/env python3
"""S428 — Idiosyncratic-Strength Continuation · XAUUSD-H1 · LONG-only.

پیش‌ثبت: results/S428_PREREGISTRATION_IdiosyncraticStrength.md (کامیت 16973dfd — قبل از این فایل).
سیگنال بیت‌به‌بیتِ S427 (پسماندِ دلاریِ ۵روزه، β علّیِ ۶۰روزه) — فقط z ≥ +θ ⇒ LONG.
نولِ رسمی: شرطی — ورودهای LONG تصادفی فقط از روزهایی با بازدهٔ خامِ ۵روزهٔ طلا > 0.

  python3 strategies/s428_idiosyncratic_strength.py scan
  python3 strategies/s428_idiosyncratic_strength.py lock theta=.. hold=..
  python3 strategies/s428_idiosyncratic_strength.py confirm
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se                     # noqa: E402
from engine import rqs2 as rq                             # noqa: E402
from strategies.s423_quiet_trend import (                 # noqa: E402
    run_trades, verify_no_bracket_hits, build_null, windows, _clean,
    ASSET, VIRTUAL_BRACKET_PIP)
from strategies.s427_dollar_residual import (             # noqa: E402
    DATA, EUR_DATA, W, B, residual_z, _load, _fmt)

assert 'mt5_full' in DATA
GRID_THETA = (1.5, 2.0)
GRID_HOLD = (3, 5)
N_TRIALS = 8                 # 4 ارثِ S427 + 4 این لایه
NULL_K = 500
NULL_SEED = 42828
EFDR_MULT = 5
OUT_DIR = 'results/_scan_S420'
LOCK_PATH = os.path.join(OUT_DIR, 'S428_LOCKED_CONFIG.json')


def signal_days(z, theta, lo, hi, hold):
    return [(i, 'long') for i in range(lo, hi - hold - 1)
            if not np.isnan(z[i]) and z[i] >= theta]


def raw_up_days(days, lo, hi, hold):
    """روزهای i در پنجره با بازدهٔ خامِ ۵روزهٔ طلا > 0 (فضایِ نولِ شرطی)."""
    cg = np.array([d['close'] for d in days])
    out = []
    for i in range(max(lo + W, lo), hi - hold - 1):
        if cg[i] > cg[i - W]:
            out.append(i)
    return np.array(out)


def cond_null_long(df, days, n_entries, hold, pool, seed):
    """WRهای K قرعهٔ n ورودِ LONG از استخرِ pool (هم‌hold، هم‌صف، هم‌هزینه)."""
    cfg = se.ASSETS[ASSET]
    pip, spread, slip = cfg['pip'], cfg['spread_pip'], cfg['slip_pip']
    o = df['open'].values
    c = df['close'].values
    rng = np.random.default_rng(seed)
    wrs = []
    exps = []
    for _ in range(NULL_K):
        picks = np.sort(rng.choice(pool, size=min(n_entries * 3, len(pool)), replace=False))
        wins = tot = 0
        pn = 0.0
        busy = -1
        for i in picks:
            if tot >= n_entries:
                break
            eb = days[i + 1]['first_bar']
            if eb <= busy:
                continue
            xd = min(i + 1 + hold - 1, len(days) - 1)
            xb = days[xd]['last_bar']
            fill = o[eb] + slip * pip
            pnl = ((c[xb] - slip * pip) - fill) / pip - spread
            wins += int(pnl > 0)
            pn += pnl
            tot += 1
            busy = xb
        if tot > 0:
            wrs.append(wins / tot * 100.0)
            exps.append(pn / tot)
    wrs = np.array(wrs)
    return dict(uncond_wr=float(np.mean(wrs)), perm_mean=float(np.mean(wrs)),
                perm_sd=float(np.std(wrs)), perm_max=float(np.max(wrs)),
                perm_k=len(wrs), perm_exp_mean=float(np.mean(exps)),
                pool_size=int(len(pool)))


def run_combo(df, days, z, theta, hold, lo, hi):
    sig = signal_days(z, theta, lo, hi, hold)
    trades = run_trades(df, days, sig, hold)
    if len(trades) == 0:
        return None, trades
    p = trades['pnl_pip'].values
    n = len(trades)
    wr = float((p > 0).mean() * 100)
    exp = float(p.mean())
    sd = p.std(ddof=1)
    t = exp / (sd / np.sqrt(n)) if n > 2 and sd > 0 else 0.0
    return dict(theta=theta, hold=hold, n=n, n_signals=len(sig), wr=wr, exp_pip=exp,
                t=float(t), net_pip=float(p.sum())), trades


def cmd_scan():
    df, days, eur = _load()
    lo, hi = windows(days)['discover']
    print(f"[scan] data={DATA} bars={len(df)} last={df['dt'].iloc[-1]}")
    print(f"[scan] discover window: days[{lo}:{hi}] ({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    z, r5, beta = residual_z(days, eur, lo)
    rows = []
    for theta in GRID_THETA:
        for hold in GRID_HOLD:
            r, trades = run_combo(df, days, z, theta, hold, lo, hi)
            if r is None:
                print(f"  theta={theta} hold={hold}: no trades")
                continue
            r['proxy'] = (r['wr'] - 50.0) * np.sqrt(r['n'])
            r['bracket_hits'] = verify_no_bracket_hits(trades, df)
            pool = raw_up_days(days, lo, hi, hold)
            cn = cond_null_long(df, days, r['n'], hold, pool, NULL_SEED + hold)
            r['cond_null'] = cn
            r['beats_cond'] = bool(r['wr'] > cn['perm_mean'])
            r['cond_z'] = float((r['wr'] - cn['perm_mean']) / cn['perm_sd']) if cn['perm_sd'] > 0 else None
            r['alive'] = bool(r['exp_pip'] > 0 and r['n'] >= 30 and r['wr'] > 50 and r['beats_cond'])
            rows.append(r)
            print(f"  theta={theta} hold={hold}: n={r['n']:3d} WR={r['wr']:5.1f}% exp={r['exp_pip']:+7.1f}pip "
                  f"t={r['t']:+5.2f} net={r['net_pip']:+8.0f} proxy={r['proxy']:+6.1f} bh={r['bracket_hits']} | "
                  f"cond-null: mean={cn['perm_mean']:.1f} sd={cn['perm_sd']:.1f} max={cn['perm_max']:.1f} "
                  f"exp={cn['perm_exp_mean']:+.1f} pool={cn['pool_size']} | cond_z={_fmt(r['cond_z'])} "
                  f"alive={r['alive']}")
    alive = [r for r in rows if r['alive']]
    print(f"[scan] alive combos (exp>0 ∧ n≥30 ∧ WR>50 ∧ beats cond-null): {len(alive)}"
          + ("  → EARLY DEATH: virgin window stays closed" if not alive else ""))
    if alive:
        best = max(alive, key=lambda r: r['proxy'])
        print(f"[scan] best by proxy: theta={best['theta']} hold={best['hold']} proxy={best['proxy']:+.1f}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'S428_scan_discover.json'), 'w') as f:
        json.dump(_clean(rows), f, indent=1, ensure_ascii=False)
    print("[scan] saved → results/_scan_S420/S428_scan_discover.json")


def cmd_lock(theta, hold):
    os.makedirs(OUT_DIR, exist_ok=True)
    cfg = dict(strategy='S428_IdiosyncraticStrength', asset=ASSET, data=DATA, eur_data=EUR_DATA,
               W=W, B=B, theta=theta, hold=hold, direction='long_only',
               null='conditional_raw5d_up', bracket_pip=VIRTUAL_BRACKET_PIP,
               n_trials=N_TRIALS, efdr_mult=EFDR_MULT,
               prereg='results/S428_PREREGISTRATION_IdiosyncraticStrength.md')
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
    print(f"[confirm] VIRGIN window: days[{lo}:{hi}] ({days[lo]['date'].date()} → {days[hi-1]['date'].date()})")
    print(f"[confirm] locked: theta={theta} hold={hold} LONG-only")
    z, r5, beta = residual_z(days, eur, lo)
    r, trades = run_combo(df, days, z, theta, hold, lo, hi)
    if r is None:
        print("[confirm] NO TRADES")
        return
    hits = verify_no_bracket_hits(trades, df)
    print(f"[confirm] n={r['n']} WR={r['wr']:.1f}% exp={r['exp_pip']:+.1f}pip t={r['t']:+.2f} "
          f"net={r['net_pip']:+.0f}pip bracket_hits={hits}")
    assert hits == 0
    pool = raw_up_days(days, lo, hi, hold)
    cond = cond_null_long(df, days, r['n'], hold, pool, NULL_SEED)
    uncond = build_null(df, days, r['n'], 0, hold, lo, hi, seed=NULL_SEED)
    print(f"[confirm] COND null (raw 5d up, pool={cond['pool_size']}): mean={cond['perm_mean']:.2f}% "
          f"sd={cond['perm_sd']:.2f} max={cond['perm_max']:.2f} exp={cond['perm_exp_mean']:+.1f}")
    print(f"[confirm] UNCOND null (reported only): mean={uncond['long']['perm_mean']:.2f}% sd={uncond['long']['perm_sd']:.2f}")
    null = {'long': cond, 'short': uncond['short']}
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
    with open(os.path.join(OUT_DIR, 'S428_confirm_virgin_rqs2.json'), 'w') as f:
        json.dump(_clean(dict(result=res, headline=r, null_cond=cond, null_uncond=uncond)), f,
                  indent=1, ensure_ascii=False)
    print(f"[confirm] verdict = {res['verdict']}  score = {res['rqs2_score']}")
    print(f"[confirm] gates: {res['gates']}")
    print("[confirm] saved → results/_scan_S420/S428_confirm_virgin_rqs2.json")


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
