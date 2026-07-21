# -*- coding: utf-8 -*-
"""
s151_eurusd_h4_meanrev.py — «Mean-Reversion روی EURUSD تایم‌فریمِ H4»
=====================================================================
فرضیهٔ علمی (درسِ مستقیم از s150):
  s150 اثبات کرد mean-reversionِ یورو روی M15 یک لبهٔ خامِ واقعی (~0.3–1.0pip) دارد
  اما چون **کوچک‌تر از سدِّ هزینه (1.3pip + کمیسیون)** است، قابلِ استخراج نیست.
  درسِ صریحِ s150: «باید روی تایم‌فریمِ بالاتر رفت تا لبهٔ خام بزرگ‌تر از هزینه شود».

  تشخیصِ رو-به-جلو تأیید کرد: با بالا رفتنِ تایم‌فریم، لبهٔ خام بزرگ‌تر می‌شود:
    M30 ~0.1–0.3pip → H1 ~1.1–1.2pip → **H4 تا +5.7pip** (z2.5, h16).
  H4 برای اولین‌بار لبهٔ خام را از سدِّ هزینه (~2–3pip) عبور می‌دهد.

  ⚠️ ریسک: نمونهٔ H4 کوچک است (فقط ~۱۲٬۰۰۰ کندل، معاملاتِ z2.5 حدودِ ۲۰۰). پس
  گیت‌های both-halves و walk-forward اینجا حیاتی‌ترند (خطرِ overfit روی نمونهٔ کوچک).

منطق (فقط long — سمتِ short در s150 بی‌لبه بود):
  z = (close − SMA_n) / rolling_std_n  ;  z ≤ −zin ⇒ LONG.

موتور: engine/scalp_engine روی dataframeِ resample‌شدهٔ H4 (از EURUSD_M15).
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


def load_h4():
    """H4 از resampleِ M15 (بالاترین TFِ موجودِ یورو M30 است؛ H4 مصنوعی می‌سازیم)."""
    df = load_data(ASSETS[ASSET]['file'])  # M15 + dt
    h4 = (df.set_index('dt')
            .resample('4h')
            .agg({'time': 'first', 'open': 'first', 'high': 'max',
                  'low': 'min', 'close': 'last', 'volume': 'sum'})
            .dropna()
            .reset_index())
    return h4


def gen_meanrev_long(df, n_ma, zin, cooldown):
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
        if z <= -zin:
            long_sig[i] = True
            last = i
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
    if len(trd) < 20:
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
    print("=== s151 — Mean-Reversion (LONG) روی EURUSD H4 ===")
    df = load_h4()
    print(f"داده: {len(df)} کندلِ H4  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})\n")

    best = None
    winners = []
    combos = 0
    for n_ma in [30, 50, 100]:
        for zin in [1.8, 2.0, 2.5]:
            for cd in [2, 4, 8]:
                ls, ss = gen_meanrev_long(df, n_ma, zin, cd)
                if int(ls.sum()) < 20:
                    continue
                # روی H4، pipهای بزرگ‌تر: TP/SL بزرگ‌تر
                for sl, tp, be, trail, mh in [
                    (40, 80, None, None, 12),
                    (60, 120, 30, 25, 18),
                    (80, 200, 40, 35, 24),
                    (100, 300, 50, 45, 30),
                ]:
                    combos += 1
                    r = evalgates(df, ls, ss, sl, tp, be, trail, mh)
                    if r is None:
                        continue
                    both = r['h1'] > 0 and r['h2'] > 0
                    wf = all(f > 0 for f in r['folds'])
                    if r['total'] > 0 and both:
                        tag = (f"ma{n_ma} z{zin} cd{cd} SL{sl}/TP{tp}/be{be}/tr{trail}/mh{mh}")
                        winners.append((r['total'], wf, both, tag, r))
                    if best is None or r['total'] > best[0]:
                        best = (r['total'], n_ma, zin, cd, sl, tp, be, trail, mh, both, wf, r)
    print(f"ترکیب‌های آزموده‌شده: {combos}\n")

    print("--- بهترین ترکیب (بیشترین سودِ خالص) ---")
    if best:
        (tot, nm, z, cd, sl, tp, be, tr, mh, both, wf, r) = best
        print(f"ma{nm} z{z} cd{cd} SL{sl}/TP{tp}/be{be}/tr{tr}/mh{mh}")
        print(f"  net={tot:+.0f}$ n={r['n']} h1={r['h1']:+.0f} h2={r['h2']:+.0f} "
              f"both={'Y' if both else 'N'} wf={'Y' if wf else 'N'} "
              f"WF=[{','.join(f'{f:+.0f}' for f in r['folds'])}]")

    print(f"\n--- ترکیب‌های both-halves مثبت: {len(winners)} ---")
    winners.sort(reverse=True)
    for tot, wf, both, tag, r in winners[:15]:
        flag = "✅✅ (WF کامل)" if wf else "✅ (WF ناقص)"
        print(f"  net={tot:+8.0f}$ n={r['n']:4d} {flag}  {tag}  "
              f"WF=[{','.join(f'{f:+.0f}' for f in r['folds'])}]")
    if not winners:
        print("  هیچ ترکیبِ both-halves مثبتی یافت نشد.")
