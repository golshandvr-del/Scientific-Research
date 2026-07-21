# -*- coding: utf-8 -*-
"""
s150_eurusd_meanrev.py — «Mean-Reversion روی EURUSD» (Bollinger/Z-Score بازگشتی)
================================================================================
فرضیهٔ علمی (درسِ مستقیم از s149):
  s149 اثبات کرد الگوی *trend-continuation* (MA-pullback) روی EURUSD در ۱۴۴ ترکیب
  کاملاً ضررده است. علتِ ریشه‌ای: EURUSD برخلافِ طلا رژیمِ صعودیِ ساختاری ندارد و
  رفتارش عمدتاً **range-bound / mean-reverting** است. پس فرضیهٔ درست باید *قرینهٔ*
  فرضیهٔ طلا باشد: **وقتی قیمت بیش‌ازحد از میانگین دور شد، در جهتِ بازگشت معامله کن.**

منطقِ ورود (Z-Score بازگشتی):
  z = (close − SMA_n) / rolling_std_n
  • z ≤ −zin  ⇒  LONG  (قیمت خیلی پایین‌تر از میانگین ⇒ انتظارِ بازگشت به بالا)
  • z ≥ +zin  ⇒  SHORT (قیمت خیلی بالاتر از میانگین ⇒ انتظارِ بازگشت به پایین)
  خروج: TP/SL کوچک (بازگشت‌ها کوچک‌اند) + max_hold کوتاه.

موتور: engine/scalp_engine (کالیبرهٔ واقعیِ EURUSD).
قانونِ ۱: فقط سودِ خالص (XAUUSD+EURUSD). WR ملاک نیست.
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
    return load_data(ASSETS[ASSET]['file'])


def gen_meanrev(df, n_ma, zin, cooldown, direction):
    c = df['close'].values
    N = len(c)
    s = pd.Series(c)
    ma = s.rolling(n_ma).mean().values
    sd = s.rolling(n_ma).std().values
    long_sig = np.zeros(N, dtype=bool)
    short_sig = np.zeros(N, dtype=bool)
    last = -10**9
    start = n_ma + 2
    for i in range(start, N - 1):
        if i - last < cooldown:
            continue
        if not np.isfinite(sd[i]) or sd[i] <= 0:
            continue
        z = (c[i] - ma[i]) / sd[i]
        if direction in ('both', 'long') and z <= -zin:
            long_sig[i] = True; last = i; continue
        if direction in ('both', 'short') and z >= zin:
            short_sig[i] = True; last = i; continue
    return long_sig, short_sig


def net_of(cap):
    if cap is None:
        return 0.0
    stats = cap[0] if isinstance(cap, tuple) else cap
    return float(stats.get('net_profit', 0.0)) if isinstance(stats, dict) else 0.0


def evalgates(df, ls, ss, sl, tp, be, trail, mh):
    N = len(df)
    trd = simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=mh,
                          be_trigger_pip=be, trail_pip=trail)
    if len(trd) < 30:
        return None
    sb = trd['signal_bar'].values
    mid = N // 2
    def cn(mask):
        sub = trd[mask]
        if len(sub) == 0:
            return 0.0
        return net_of(run_capital(sub.reset_index(drop=True), ASSET))
    total = net_of(run_capital(trd, ASSET))
    h1 = cn(sb < mid); h2 = cn(sb >= mid)
    edges = [int(N * j / 4) for j in range(5)]
    folds = [cn((sb >= edges[j]) & (sb < edges[j + 1])) for j in range(4)]
    return dict(total=total, h1=h1, h2=h2, folds=folds, n=len(trd))


if __name__ == '__main__':
    print("=== s150 — Mean-Reversion (Z-Score بازگشتی) روی EURUSD ===")
    df = load_eur()
    print(f"داده: {len(df)} کندلِ M15  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})\n")

    best = None
    winners = []
    combos = 0
    for direction in ('long', 'short', 'both'):
        for n_ma in [20, 50, 100]:
            for zin in [1.5, 2.0, 2.5]:
                for cd in [8, 16]:
                    ls, ss = gen_meanrev(df, n_ma, zin, cd, direction)
                    if int(ls.sum() + ss.sum()) < 30:
                        continue
                    # TP/SL کوچک — بازگشت به میانگین حرکتِ کوچکی است
                    for sl, tp, be, trail, mh in [
                        (20, 20, None, None, 32),
                        (25, 30, 12, 10, 48),
                        (30, 40, 15, 12, 64),
                        (40, 60, 20, 15, 96),
                    ]:
                        combos += 1
                        r = evalgates(df, ls, ss, sl, tp, be, trail, mh)
                        if r is None:
                            continue
                        both = r['h1'] > 0 and r['h2'] > 0
                        wf = all(f > 0 for f in r['folds'])
                        if r['total'] > 0 and both:
                            tag = (f"{direction} ma{n_ma} z{zin} cd{cd} "
                                   f"SL{sl}/TP{tp}/be{be}/tr{trail}/mh{mh}")
                            winners.append((r['total'], wf, tag, r))
                        if best is None or r['total'] > best[0]:
                            best = (r['total'], direction, n_ma, zin, cd,
                                    sl, tp, be, trail, mh, both, wf, r)
    print(f"ترکیب‌های آزموده‌شده: {combos}\n")

    print("--- بهترین ترکیب (بیشترین سودِ خالص) ---")
    if best:
        (tot, d, nm, z, cd, sl, tp, be, tr, mh, both, wf, r) = best
        print(f"{d} ma{nm} z{z} cd{cd} SL{sl}/TP{tp}/be{be}/tr{tr}/mh{mh}")
        print(f"  net={tot:+.0f}$ n={r['n']} h1={r['h1']:+.0f} h2={r['h2']:+.0f} "
              f"both={'Y' if both else 'N'} wf={'Y' if wf else 'N'} "
              f"WF=[{','.join(f'{f:+.0f}' for f in r['folds'])}]")

    print(f"\n--- ترکیب‌های سوددهِ both-halves مثبت: {len(winners)} ---")
    winners.sort(reverse=True)
    for tot, wf, tag, r in winners[:15]:
        flag = "✅✅" if wf else "✅"
        print(f"  net={tot:+8.0f}$ n={r['n']:4d} {flag}  {tag}")
    if not winners:
        print("  هیچ ترکیبِ سوددهِ both-halves مثبتی یافت نشد.")
