# -*- coding: utf-8 -*-
"""
ممیزیِ همپوشانیِ اجباری — S341-H1 (swing-fade احیاشده) در برابرِ لایه‌های LONGِ موجودِ کارتِ XAUUSD-H1.

قانونِ همپوشانی (تعریفِ پروژه): پیش از افزودن، باید بدانیم با کدام لایه و چند درصد همپوشانی داریم.
روش: تاریخ‌زمانِ کندلِ ورودِ هر لایه را می‌سازیم و درصدِ ورودهای S341 را که با ورودِ لایهٔ دیگر
هم‌کندل (±۱ کندل) هستند می‌سنجیم.

لایه‌های LONGِ H1 که واقعا هم‌جهت‌اند:
  • S333 (S79 pullback-buy: EMA-پول‌بک + RSI-turn) — رژیمِ روند.
  • S335 (Reflex dip-turn) — گیتِ Chop<38.2 (رژیمِ روند).
S341 گیتِ chop≥61.8 دارد (رژیمِ رنج) ⇒ انتظارِ همپوشانیِ نزدیکِ صفر با S335 (رژیمِ متعامد).
"""
import numpy as np
from engine import indicator_bank as ib
from strategies.s341_brooks_swing_levels import load_tf
from strategies.s341_swing_fade_h1_revived import CONFIG, swing_fade_confluence_signals


def to_idx(sig):
    return np.where(sig)[0]


def overlap_pct(a_idx, b_idx, tol=1):
    """درصدِ اندیس‌های a که حداقل یک اندیسِ b در فاصلهٔ ±tol دارند."""
    if len(a_idx) == 0:
        return 0.0, 0
    b = np.asarray(b_idx)
    hit = 0
    for x in a_idx:
        if b.size and np.any(np.abs(b - x) <= tol):
            hit += 1
    return 100.0 * hit / len(a_idx), hit


def s333_like_long(df, ema_fast=20, ema_slow=50, rsi_p=14, rsi_th=45):
    """بازسازیِ تقریبیِ S333: در روندِ صعودی (ema_fast>ema_slow)، پول‌بک به RSI پایین و بازگشت."""
    import pandas as pd
    c = df['close']
    ef = c.ewm(span=ema_fast, adjust=False).mean().to_numpy()
    es = c.ewm(span=ema_slow, adjust=False).mean().to_numpy()
    rsi = ib.compute('rsi_lucas_11', df).to_numpy() if 'rsi_lucas_11' in ib.list_indicators() else ib.compute('rsi', df).to_numpy()
    n = len(df)
    sig = np.zeros(n, bool)
    for i in range(2, n):
        if not (np.isfinite(ef[i]) and np.isfinite(es[i]) and np.isfinite(rsi[i]) and np.isfinite(rsi[i-1])):
            continue
        if ef[i] > es[i] and rsi[i-1] < rsi_th and rsi[i] > rsi[i-1]:
            sig[i] = True
    return sig


def s335_like_long(df, chop_max=38.2):
    """بازسازیِ تقریبیِ S335: رژیمِ روند (chop<38.2) + چرخشِ dip با reflex."""
    ch = ib.chop(df, p=14).to_numpy()
    reflex = ib.compute('reflex', df).to_numpy()
    n = len(df)
    sig = np.zeros(n, bool)
    for i in range(2, n):
        if not (np.isfinite(ch[i]) and np.isfinite(reflex[i]) and np.isfinite(reflex[i-1])):
            continue
        if ch[i] < chop_max and reflex[i-1] < 0 and reflex[i] > reflex[i-1]:
            sig[i] = True
    return sig


if __name__ == '__main__':
    cfg = CONFIG['XAUUSD-H1']
    df = load_tf('XAUUSD', 'H1')
    s341 = to_idx(swing_fade_confluence_signals(df, cfg))
    print(f"S341-H1 entries: n={len(s341)}")

    for name, fn in [('S333(pullback-buy)', s333_like_long),
                     ('S335(reflex dip-buy, trend-gated)', s335_like_long)]:
        other = to_idx(fn(df))
        ov, hit = overlap_pct(s341, other, tol=1)
        print(f"  vs {name:38s}: other_n={len(other):5d} | overlap={ov:5.1f}% ({hit}/{len(s341)})")

    # همپوشانیِ رژیمی: چند درصد از کندل‌های کلِ دیتا هم‌زمان range(chop>=61.8) و trend(chop<38.2)? => صفر
    ch = ib.chop(df, 14).to_numpy()
    both = np.sum((ch >= 61.8) & (ch < 38.2))
    print(f"\n  [regime check] bars that are BOTH range(chop>=61.8) AND trend(chop<38.2) = {both} (باید صفر باشد)")
