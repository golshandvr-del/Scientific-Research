# -*- coding: utf-8 -*-
"""
s149_eurusd_ma_pullback.py — «MA-Pullback دوطرفه روی EURUSD» (الگوی بصریِ ۱+۲)
==============================================================================
انگیزه (از دفترچهٔ مشاهداتِ بصری + درسِ s147/s148):
  الگوی بصریِ «پولبک به MA در جهتِ روند» پرتکرارترین الگوی چارت بود. اما روی طلا
  فقط سمتِ long کار می‌کند (رژیمِ صعودیِ ساختاری) و آن هم با پرتفویِ long موجود
  همبسته است (corr≈0.4). درسِ کلیدی: برای سودِ خالصِ **افزایشی** باید سراغِ
  داراییِ کم‌اشباع رفت. **EURUSD** رژیمِ صعودیِ یک‌طرفهٔ طلا را ندارد ⇒ هم long و هم
  short پایدارند و corr با پرتفویِ طلا ذاتاً پایین است.

منطقِ ورود (قرینهٔ s148، اما دوطرفهٔ متعادل روی EURUSD):
  رژیم = علامتِ (EMA_fast − EMA_slow).
  • صعودی: پولبک به EMA_fast (low≤EMA_fast+k·ATR) + کندلِ تأییدِ صعودی ⇒ LONG.
  • نزولی: رالی به EMA_fast (high≥EMA_fast−k·ATR) + کندلِ تأییدِ نزولی ⇒ SHORT.

موتور: `engine/scalp_engine.simulate_trades` + `run_capital` (همان موتورِ کالیبرهٔ
پروژه؛ EURUSD: pip=0.0001، contract=100k، spread=1.0pip، comm=7$/لات، slip=0.3pip).

قانونِ شمارهٔ ۱: معیار فقط **سودِ خالص** (XAUUSD + EURUSD). WR ملاک نیست.
"""
import os
import sys
import numpy as np
import pandas as pd

ROOT = '/home/user/webapp'
sys.path.insert(0, ROOT)

from engine.scalp_engine import ASSETS, load_data, simulate_trades, run_capital

ASSET = 'EURUSD'
PIP = ASSETS[ASSET]['pip']


def load_eur():
    df = load_data(ASSETS[ASSET]['file'])
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df


def atr_pips(df, period=14):
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().values
    return atr / PIP  # به pip


def _ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values


def gen_ma_pullback(df, ema_fast=20, ema_slow=50, cooldown=8, touch_atr=0.3,
                    direction='both'):
    o = df['open'].values; c = df['close'].values
    h = df['high'].values; l = df['low'].values
    n = len(df)
    ef = _ema(c, ema_fast); es = _ema(c, ema_slow)
    atr_p = atr_pips(df, 14)
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    last = -10**9
    start = ema_slow + 2
    for i in range(start, n - 1):
        if i - last < cooldown:
            continue
        a = atr_p[i]
        if not np.isfinite(a) or a <= 0:
            continue
        near = touch_atr * a * PIP
        up = ef[i] > es[i]; dn = ef[i] < es[i]
        if up and direction in ('both', 'long'):
            if l[i] <= ef[i] + near and c[i] > es[i] and c[i] > o[i]:
                long_sig[i] = True; last = i; continue
        if dn and direction in ('both', 'short'):
            if h[i] >= ef[i] - near and c[i] < es[i] and c[i] < o[i]:
                short_sig[i] = True; last = i; continue
    return long_sig, short_sig


def evaluate(df, long_sig, short_sig, sl_pip, tp_pip, be_trig, trail_pip, max_hold):
    trd = simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, ASSET,
                          max_hold=max_hold, be_trigger_pip=be_trig, trail_pip=trail_pip)
    if len(trd) == 0:
        return None, None
    cap = run_capital(trd, ASSET)
    return trd, cap


def net_of(cap):
    """سودِ خالصِ نهایی از خروجیِ run_capital.
    run_capital یک tuple برمی‌گرداند: (stats_dict, equity_curve[, pertrade]).
    stats_dict شاملِ کلیدِ 'net_profit' است."""
    if cap is None:
        return 0.0
    # unpack tuple خروجیِ run_capital
    if isinstance(cap, tuple):
        stats = cap[0]
    else:
        stats = cap
    if isinstance(stats, dict):
        for k in ('net_profit', 'total_pnl', 'final_pnl', 'profit'):
            if k in stats:
                return float(stats[k])
    return 0.0


def half_wf(df, long_sig, short_sig, sl_pip, tp_pip, be_trig, trail_pip, max_hold):
    """both-halves + walk-forward (۴ پنجره) بر اساسِ signal_bar."""
    n = len(df)
    trd = simulate_trades(df, long_sig, short_sig, sl_pip, tp_pip, ASSET,
                          max_hold=max_hold, be_trigger_pip=be_trig, trail_pip=trail_pip)
    if len(trd) == 0:
        return None
    sb = trd['signal_bar'].values
    mid = n // 2
    def cap_net(mask):
        sub = trd[mask]
        if len(sub) == 0:
            return 0.0
        return net_of(run_capital(sub.reset_index(drop=True), ASSET))
    h1 = cap_net(sb < mid); h2 = cap_net(sb >= mid)
    edges = [int(n * j / 4) for j in range(5)]
    folds = [cap_net((sb >= edges[j]) & (sb < edges[j + 1])) for j in range(4)]
    total = net_of(run_capital(trd, ASSET))
    return dict(total=total, h1=h1, h2=h2, folds=folds, n=len(trd), trd=trd)


if __name__ == '__main__':
    print("=== s149 — MA-Pullback دوطرفه روی EURUSD (الگوی بصریِ ۱+۲) ===")
    cfg = ASSETS[ASSET]
    print(f"EURUSD: pip={cfg['pip']} contract={cfg['contract']:.0f} "
          f"spread={cfg['spread_pip']}pip comm={cfg['comm']}$ slip={cfg['slip_pip']}pip")
    df = load_eur()
    print(f"داده: {len(df)} کندلِ M15  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})")

    print("\n--- اکتشافِ اولیه: هر جهت جداگانه ---")
    for d in ('long', 'short', 'both'):
        ls, ss = gen_ma_pullback(df, direction=d)
        res = half_wf(df, ls, ss, 20.0, 60.0, 10.0, 25.0, 96)
        if res is None:
            print(f"{d}: no trades"); continue
        both = res['h1'] > 0 and res['h2'] > 0
        wf = all(f > 0 for f in res['folds'])
        flag = "✅✅" if (both and wf) else ("✅" if both else "")
        print(f"{d:5s}: net={res['total']:+.0f}$ n={res['n']} "
              f"h1={res['h1']:+.0f} h2={res['h2']:+.0f} "
              f"WF=[{','.join(f'{f:+.0f}' for f in res['folds'])}] {flag}")
