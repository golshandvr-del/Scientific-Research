# -*- coding: utf-8 -*-
"""
ممیزیِ همپوشانیِ اجباریِ چند-تایم‌فریمی — S341 (swing-fade در رنج) روی XAUUSD M5/M15/M30/H1
================================================================================
قانونِ همپوشانیِ پروژه: پیش از افزودنِ هر لایه باید بدانیم با کدام لایه و چند درصد همپوشان است،
و اگر همپوشان بود، امکانِ استفاده به‌عنوان فیلتر بررسی شود.

لایه‌های LONGِ هم‌جهتِ موجود روی این کارت‌ها:
  • S333 (S79 pullback-buy: روندِ صعودی + پول‌بکِ RSI) — رژیمِ روند.
  • S335 (Reflex dip-turn: چرخشِ کفِ چرخهٔ اِهلرز) — گیتِ رژیمِ روند (chop پایین).
S341 گیتِ رنج (chop≥58..61.8) دارد ⇒ ساختاراً از رژیمِ این دو لایه متعامد است ⇒ انتظارِ همپوشانیِ ~صفر.

روش: تاریخ‌زمانِ کندلِ ورودِ هر لایه ساخته و درصدِ ورودهای S341 که با ورودِ لایهٔ دیگر
هم‌کندل (±۱ کندل) هستند سنجیده می‌شود. (این همان روشِ ممیزیِ S340/S341-H1 است.)
"""
import numpy as np
from engine import indicator_bank as ib
from strategies.s341_brooks_swing_levels import load_tf
from strategies.s341_swing_fade_h1_revived import CONFIG, swing_fade_confluence_signals


def to_idx(sig):
    return np.where(sig)[0]


def overlap_pct(a_idx, b_idx, tol=1):
    if len(a_idx) == 0:
        return 0.0, 0
    b = np.asarray(b_idx)
    hit = 0
    for x in a_idx:
        if b.size and np.any(np.abs(b - x) <= tol):
            hit += 1
    return 100.0 * hit / len(a_idx), hit


def s333_like_long(df, ema_fast=20, ema_slow=50, rsi_th=45):
    """بازسازیِ تقریبیِ S333: روندِ صعودی (ema_fast>ema_slow) + پول‌بکِ RSI و بازگشت."""
    c = df['close']
    ef = c.ewm(span=ema_fast, adjust=False).mean().to_numpy()
    es = c.ewm(span=ema_slow, adjust=False).mean().to_numpy()
    rname = 'rsi_lucas_11' if 'rsi_lucas_11' in ib.list_indicators() else 'rsi'
    rsi = ib.compute(rname, df).to_numpy()
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


def audit_card(card):
    cfg = CONFIG[card]
    asset, tf = card.split('-')
    df = load_tf(asset, tf)
    s341 = to_idx(swing_fade_confluence_signals(df, cfg))
    print(f"\n=== {card} ===  S341 entries: n={len(s341)}  (رژیم: chop≥{cfg['chop_min']})")
    worst = 0.0
    for name, fn in [('S333(pullback-buy, trend)', s333_like_long),
                     ('S335(reflex dip-buy, trend)', s335_like_long)]:
        other = to_idx(fn(df))
        ov, hit = overlap_pct(s341, other, tol=1)
        worst = max(worst, ov)
        print(f"  vs {name:32s}: other_n={len(other):6d} | overlap={ov:5.1f}% ({hit}/{len(s341)})")
    # چکِ رژیمی: هم‌زمان range و trend ممکن نیست
    ch = ib.chop(df, 14).to_numpy()
    both = int(np.sum((ch >= cfg['chop_min']) & (ch < 38.2)))
    print(f"  [regime check] bars BOTH range(chop≥{cfg['chop_min']}) & trend(chop<38.2) = {both} (باید ۰)")
    verdict = 'لبهٔ مستقل (نه فیلتر)' if worst < 15 else 'بررسیِ استفاده به‌عنوان فیلتر لازم'
    print(f"  ⇒ بیشینه‌همپوشانی = {worst:.1f}%  ⇒ {verdict}")
    return worst


if __name__ == '__main__':
    import sys
    cards = sys.argv[1:] or ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1']
    for card in cards:
        audit_card(card)
