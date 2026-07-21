# -*- coding: utf-8 -*-
"""
s149b_eurusd_sweep.py — جاروبِ پارامتریِ MA-Pullback روی EURUSD
================================================================
هدف: پاسخِ صادقانه به این پرسش که «آیا *هیچ* ناحیهٔ سوددهِ پایدار (both-halves +
walk-forward مثبت) برای الگوی MA-Pullback روی EURUSD وجود دارد؟»
نسخهٔ پایه (s149) با پارامترهای پیش‌فرض ضررده بود؛ اینجا فضای پارامتر را جاروب
می‌کنیم تا ببینیم لبهٔ واقعی هست یا نه. WR ملاک نیست — فقط سودِ خالص (قانونِ ۱).

⚠️ نکتهٔ کلیدیِ هزینه: EURUSD اسپرد ۱.۰pip + slip ۰.۳pip + کمیسیون ۷$/لات دارد؛
برای TPهای کوچک این هزینه کشنده است. پس TP باید به‌قدرِ کافی بزرگ باشد که
هزینه را بپوشاند، و cooldown بزرگ تعدادِ معامله (و هزینهٔ تجمعی) را کم کند.
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


def atr_pips(df, period=14):
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    atr = pd.Series(tr).rolling(period).mean().values
    return atr / PIP


def _ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values


def gen(df, ema_fast, ema_slow, cooldown, touch_atr, direction):
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


def net_of(cap):
    if cap is None:
        return 0.0
    stats = cap[0] if isinstance(cap, tuple) else cap
    return float(stats.get('net_profit', 0.0)) if isinstance(stats, dict) else 0.0


def evalgates(df, ls, ss, sl, tp, be, trail, mh):
    n = len(df)
    trd = simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=mh,
                          be_trigger_pip=be, trail_pip=trail)
    if len(trd) < 30:
        return None
    sb = trd['signal_bar'].values
    mid = n // 2
    def cn(mask):
        sub = trd[mask]
        if len(sub) == 0:
            return 0.0
        return net_of(run_capital(sub.reset_index(drop=True), ASSET))
    total = net_of(run_capital(trd, ASSET))
    h1 = cn(sb < mid); h2 = cn(sb >= mid)
    edges = [int(n * j / 4) for j in range(5)]
    folds = [cn((sb >= edges[j]) & (sb < edges[j + 1])) for j in range(4)]
    return dict(total=total, h1=h1, h2=h2, folds=folds, n=len(trd))


if __name__ == '__main__':
    print("=== s149b — جاروبِ پارامتریِ MA-Pullback روی EURUSD ===")
    df = load_eur()
    print(f"داده: {len(df)} کندلِ M15  ({df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()})\n")

    # فضای پارامتر: TP بزرگ‌تر (پوششِ هزینه)، cooldown بزرگ (هزینهٔ کمتر)
    best = None
    winners = []
    combos = 0
    for direction in ('long', 'short'):
        for ef, es in [(20, 50), (20, 100), (50, 200)]:
            for cd in [16, 32, 48]:
                for touch in [0.2, 0.4]:
                    ls, ss = gen(df, ef, es, cd, touch, direction)
                    nsig = int(ls.sum() + ss.sum())
                    if nsig < 30:
                        continue
                    for sl, tp, be, trail, mh in [
                        (15, 45, 8, 12, 64),
                        (20, 80, 10, 20, 96),
                        (25, 120, 12, 25, 128),
                        (30, 200, 15, 30, 192),
                    ]:
                        combos += 1
                        r = evalgates(df, ls, ss, sl, tp, be, trail, mh)
                        if r is None:
                            continue
                        both = r['h1'] > 0 and r['h2'] > 0
                        wf = all(f > 0 for f in r['folds'])
                        if r['total'] > 0 and both:
                            tag = (f"{direction} ef{ef}/es{es} cd{cd} t{touch} "
                                   f"SL{sl}/TP{tp}/be{be}/tr{trail}/mh{mh}")
                            winners.append((r['total'], both, wf, tag, r))
                        if best is None or r['total'] > best[0]:
                            best = (r['total'], direction, ef, es, cd, touch,
                                    sl, tp, be, trail, mh, both, wf, r)
    print(f"ترکیب‌های آزموده‌شده: {combos}\n")

    print("--- بهترین ترکیب (بیشترین سودِ خالص) ---")
    if best:
        (tot, d, ef, es, cd, t, sl, tp, be, tr, mh, both, wf, r) = best
        print(f"{d} ef{ef}/es{es} cd{cd} touch{t} SL{sl}/TP{tp}/be{be}/tr{tr}/mh{mh}")
        print(f"  net={tot:+.0f}$ n={r['n']} h1={r['h1']:+.0f} h2={r['h2']:+.0f} "
              f"both={'Y' if both else 'N'} wf={'Y' if wf else 'N'} "
              f"WF=[{','.join(f'{f:+.0f}' for f in r['folds'])}]")

    print(f"\n--- ترکیب‌های سوددهِ both-halves مثبت: {len(winners)} ---")
    winners.sort(reverse=True)
    for tot, both, wf, tag, r in winners[:15]:
        flag = "✅✅" if wf else "✅"
        print(f"  net={tot:+8.0f}$ n={r['n']:4d} {flag}  {tag}")
    if not winners:
        print("  هیچ ترکیبِ سوددهِ both-halves مثبتی یافت نشد.")
