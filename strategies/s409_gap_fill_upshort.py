#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S409 — گپ‌فیلِ گپ مثبت / سمت Sell با V ثابت · XAUUSD M30 · دادهٔ کامل ۱۵.۶ ساله
================================================================================
پیش‌ثبت: results/S409_PREREG_GAP_FILL_UPSHORT.md (commit قبل از هر اجرا)
آینهٔ S404 (ACCEPT 96.8، گپ منفی/Buy). می‌بندد: «گپ بالا لبه ندارد» — با حکم رسمی موتور.

فضای پیش‌ثبت (۶ ترکیب): q∈{60,70,80} × k_sl∈{1.7,2.0} · V=ATRq78 ثابت · dow≠0 · gap>0 · Sell
قاعدهٔ برنده (قفل): کمترین maxDD نیمهٔ اول به شرط
  n≥50 · PF>1 · t≥2.5 · maxDD≤4.80% · wr_edge≥2pp · rec≥3 · گره‌گشایی: t.
حالت‌ها:
  python3 strategies/s409_gap_fill_upshort.py selftest
  python3 strategies/s409_gap_fill_upshort.py tune
  python3 strategies/s409_gap_fill_upshort.py verdict <q> <k_sl>
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from engine import scalp_engine as se
from strategies.s400_gap_open import (build_days, daily_atr, thresholds_for_day,
                                      PIP, SPREAD_PIP)
from strategies.s401_gap_fill_riskguard import sim_trade_be
from strategies.s404_gap_fill_window import vol_flags, judge_stats

TF = 'M30'
SEED = 409
N_TRIALS_CUM = 292                 # 286 + 6 (پیش‌ثبت §۶)
DATA = 'data/mt5_full/XAUUSD_M30.csv'
SPLIT_FULL = 90691                 # اولین کندل ≥ 2018-10-25 11:30 UTC (= split قفل S400/S404)
EXPECT = dict(n=182145, first='2011-01-03 00:00:00', last='2026-08-07 23:30:00')
CKPT = os.path.join(os.path.dirname(__file__), '..', 'results', '_s409_tune_ckpt.json')


def load_full():
    df = se.load_data(DATA)
    first, last = str(df['dt'].iloc[0]), str(df['dt'].iloc[-1])
    print(f"DATA {DATA}: bars={len(df)} first={first} last={last}", flush=True)
    assert len(df) == EXPECT['n'] and first == EXPECT['first'] and last == EXPECT['last'], \
        "data span mismatch vs prereg — STOP"
    assert str(df['dt'].iloc[SPLIT_FULL]) == '2018-10-25 11:30:00', "split bar mismatch"
    return df


def sim_trade_short(arrays, day, k_sl):
    """آینهٔ خط‌به‌خط sim_trade_be(be_f=None) برای Sell روی گپ مثبت.
    قراردادهای موتور: TP∧SL همزمان = باخت؛ خروج اجباری close آخرین کندل روز."""
    o, h, l, c = arrays
    fb, last = day['fb'], day['last']
    entry = o[fb]
    agap = abs(day['gap'])
    if agap <= 0:
        return None
    sl_price = entry + k_sl * agap
    tp_price = day['prev_close']
    tp_dist = entry - tp_price
    outcome_price, exit_bar, full_sl = None, None, False
    for j in range(fb, last + 1):
        hit_sl = h[j] >= sl_price
        hit_tp = l[j] <= tp_price
        if hit_sl and hit_tp:
            outcome_price, exit_bar, full_sl = sl_price, j, True; break
        elif hit_tp:
            outcome_price, exit_bar = tp_price, j; break
        elif hit_sl:
            outcome_price, exit_bar, full_sl = sl_price, j, True; break
    if outcome_price is None:
        exit_bar = last
        outcome_price = c[last]
    pnl_pip = (entry - outcome_price) / PIP - SPREAD_PIP
    return {
        'signal_bar': fb - 1, 'entry_bar': fb, 'exit_bar': int(exit_bar),
        'direction': 'short', 'entry_price': float(entry),
        'exit_price': float(outcome_price),
        'outcome': 'win' if pnl_pip > 0 else 'loss',
        'pnl_pip': float(pnl_pip),
        'sl_pip': float((sl_price - entry) / PIP),
        'tp_pip': float(tp_dist / PIP),
        'bars_held': int(exit_bar - fb),
        'dow': day['dow'], 'full_sl': bool(full_sl),
    }


def run_layer(df, days, atr, q, k_sl, use_v, vflags=None,
              lo_bar=None, hi_bar=None, no_thresh=False, no_dow=False):
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    if use_v and vflags is None:
        vflags = vol_flags(days, atr)
    trades = []
    for k, d in enumerate(days):
        if lo_bar is not None and d['fb'] < lo_bar:
            continue
        if hi_bar is not None and d['fb'] >= hi_bar:
            continue
        if not (d['gap'] > 0):                    # گپ مثبت
            continue
        if not no_thresh:
            th = thresholds_for_day(days, atr, k, 'QW', q)
            if not np.isfinite(th) or abs(d['gap']) <= th:
                continue
        if not no_dow and d['dow'] == 0:
            continue
        if use_v and vflags[k]:
            continue
        tr = sim_trade_short(arrays, d, k_sl)
        if tr is None:
            continue
        trades.append(tr)
    return pd.DataFrame(trades)


def mode_selftest():
    """تقارن: قیمت‌ها را حول یک ثابت وارونه کن ⇒ گپ منفی→مثبت؛ pnl باید عیناً برابر sim_trade_be باشد."""
    df = load_full()
    days = build_days(df)
    o, h, l, c = (df[x].values.astype('float64') for x in ('open', 'high', 'low', 'close'))
    K = 2.0 * float(np.nanmean(c))
    mo, mh, ml, mc = K - o, K - l, K - h, K - c          # high/low جابه‌جا می‌شوند
    n_chk, max_err = 0, 0.0
    for d in days:
        if d['gap'] < 0:
            long_tr = sim_trade_be((o, h, l, c), d, 2.0, None)
            md = dict(d); md['gap'] = -d['gap']; md['prev_close'] = K - d['prev_close']
            short_tr = sim_trade_short((mo, mh, ml, mc), md, 2.0)
            if long_tr is None or short_tr is None:
                continue
            max_err = max(max_err, abs(long_tr['pnl_pip'] - short_tr['pnl_pip']))
            assert long_tr['exit_bar'] == short_tr['exit_bar']
            n_chk += 1
    print(f"selftest: {n_chk} mirrored trades, max |pnl diff| = {max_err:.6f} pip", flush=True)
    assert max_err < 1e-6, "mirror mismatch"
    return 0


def mode_tune():
    df = load_full()
    days = build_days(df); atr = daily_atr(days); vflags = vol_flags(days, atr)
    rows = []
    for q in (60, 70, 80):
        for k_sl in (1.7, 2.0):
            tr = run_layer(df, days, atr, q, k_sl, True, vflags=vflags, hi_bar=SPLIT_FULL)
            st = judge_stats(tr); st.update(q=q, k_sl=k_sl, V='ATRq78')
            rows.append(st)
            print(f"q={q} k_sl={k_sl} V=ATRq78 | n={st['n']:4d} WR={st['wr']}% PF={st['pf']} "
                  f"t={st['t']} maxDD={st['maxdd']}% wr_edge={st['wr_edge']}pp rec={st['rec']}",
                  flush=True)
    with open(CKPT, 'w') as f:
        json.dump(rows, f, indent=1, default=str)
    ok = [r for r in rows if r['n'] >= 50 and r['pf'] > 1 and r['t'] >= 2.5
          and r['maxdd'] <= 4.80 and r['wr_edge'] >= 2 and r['rec'] >= 3]
    if not ok:
        print("\nNO COMBO PASSES LOCKED RULE → tuning-phase REJECT (holdout stays virgin)", flush=True)
        return 1
    win = sorted(ok, key=lambda r: (r['maxdd'], -r['t']))[0]
    print(f"\nWINNER: q={win['q']} k_sl={win['k_sl']} (maxDD={win['maxdd']}%, t={win['t']})", flush=True)
    return 0


def mode_verdict(q, k_sl):
    from engine import rqs2
    df = load_full()
    days = build_days(df); atr = daily_atr(days); vflags = vol_flags(days, atr)
    bar_time = df['dt'].values
    close = df['close'].values.astype('float64')
    strat = run_layer(df, days, atr, q, k_sl, True, vflags=vflags)
    n_str = len(strat)
    print(f"strategy trades n={n_str} · holdout n={int((strat['entry_bar'] >= SPLIT_FULL).sum())}", flush=True)
    pool_df = run_layer(df, days, atr, q, k_sl, False, no_thresh=True, no_dow=True)
    pool = pool_df['pnl_pip'].values.astype('float64')
    uncond_wr = float((pool > 0).mean() * 100.0)
    print(f"null pool = {len(pool)} uncond gap-UP SELL entries (same k_sl) · uncond_wr={uncond_wr:.2f}%", flush=True)
    rng = np.random.default_rng(SEED); K = 500; wrs = np.empty(K)
    for i in range(K):
        pick = rng.choice(len(pool), size=n_str, replace=False)
        wrs[i] = (pool[pick] > 0).mean() * 100.0
    null = {'short': dict(uncond_wr=uncond_wr, perm_mean=float(wrs.mean()),
                          perm_sd=float(wrs.std(ddof=1)), perm_max=float(wrs.max()), perm_k=int(K)),
            'long': dict(uncond_wr=None, perm_mean=None, perm_sd=None, perm_max=None, perm_k=None)}
    print(f"perm(K={K}): mean={wrs.mean():.2f} sd={wrs.std(ddof=1):.3f} max={wrs.max():.2f}", flush=True)
    tp_meas = float(np.median(strat['tp_pip'].values)); sl_meas = float(np.median(strat['sl_pip'].values))
    print(f"judge geometry: sl_pip={sl_meas:.1f} tp_pip={tp_meas:.1f} rr={tp_meas/sl_meas:.3f}", flush=True)
    r = rqs2.compute_rqs2(strat, 'XAUUSD', sl_pip=sl_meas, tp_pip=tp_meas, bar_time=bar_time,
                          null=null, n_trials=N_TRIALS_CUM, split_bar=SPLIT_FULL, close=close)
    print(rqs2.format_rqs2(f'S409 {TF} gapUP-SELL q={q}/k_sl={k_sl}/V=fixed', r), flush=True)
    outp = os.path.join(os.path.dirname(__file__), '..', 'results', '_s409_verdict.json')
    with open(outp, 'w') as f:
        json.dump(r, f, indent=1, default=str)
    print(f"saved → {outp}", flush=True)
    return 0


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'tune'
    if mode == 'selftest':
        sys.exit(mode_selftest())
    elif mode == 'tune':
        sys.exit(mode_tune())
    elif mode == 'verdict':
        sys.exit(mode_verdict(int(sys.argv[2]), float(sys.argv[3])))
    else:
        print(__doc__); sys.exit(2)
