# -*- coding: utf-8 -*-
"""
S327 — ممیزیِ همپوشانیِ کمّی (قانونِ همپوشانیِ پروژه)
================================================================================
هدف: سنجشِ کمّیِ همپوشانیِ زمانیِ نقاطِ ورودِ S327 (Sell-Climax Exhaustion Reversal،
LONG، TP<SL) با نقاطِ ورودِ لایه‌های فعالِ فعلیِ موتورِ local-mobile روی همان TF/جفت‌ارز.

لایه‌های مقایسه (مهم‌ترین اول):
  L0) S326 Streak-Reversal  ← هر دو mean-reversion/contrarian ⇒ بالاترین ریسکِ همپوشانی
  L1) S132 Squeeze→Breakout (BB-squeeze + breakout، continuation، LONG)
  L2) Triple-SMA Stack-Pullback (SMA13/100/200، پولبک در روندِ صعودی، LONG)

روش (forward-safe، هم‌تراز با simulate_trades و ممیزیِ S326):
  - برای هر لایه سیگنالِ LONG per-bar می‌سازیم.
  - «همپوشانی» = کسری از bar-های سیگنالِ S327 که یک سیگنالِ لایهٔ دیگر در پنجرهٔ
    ±TOL کندل حضور دارد (هم‌زمانیِ عملیِ بازِ معامله).
  - چهار عدد: overlap با S326، Squeeze، Triple-SMA، و اجتماعِ کل.

قانونِ همپوشانی — سه‌گانه:
  (۱) دقیقاً با کدام لایه/چند درصد.
  (۲) حتی ۹۹٪ همپوشانی هم به‌خاطرِ آن ۱٪ متفاوت ارزشِ افزودن دارد.
  (۳) از بخشِ همپوشان می‌توان به‌عنوان فیلترِ بهبود استفاده کرد — اینجا صریحاً بررسی
      می‌کنیم آیا S327 (climax-exhaustion) با S326 (streak-reversal) هم‌پوشان است و
      اگر بله، آیا هرکدام روی نقاطِ منحصربه‌فردِ خود ارزشِ مستقل دارند.
"""
import sys, json
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import indicators as ind
import strategies.s327_sell_climax_reversal_rqs as S327
from strategies.s326_streak_reversal_revival import (
    load as s326_load, build_features as s326_build, make_signals as s326_sig)
import warnings; warnings.filterwarnings('ignore')

TOL = 2  # ±۲ کندل تحملِ هم‌زمانی

# کانفیگ‌های برندهٔ RQS+≥80 برای S327 (از _s327_sell_climax_*.json)
S327_WINNERS = {
    'XAUUSD_M5':  dict(k_body=1.6, br_min=0.6,  streak_n=2, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=24),
    'XAUUSD_M15': dict(k_body=2.5, br_min=0.45, streak_n=3, rsi_lo=35, regime='trend', sl_m=2.8, tp_m=1.0,  hold=16),
    'XAUUSD_M30': dict(k_body=2.5, br_min=0.45, streak_n=2, rsi_lo=35, regime='trend', sl_m=2.4, tp_m=1.0,  hold=16),
    'XAUUSD_H1':  dict(k_body=1.6, br_min=0.6,  streak_n=3, rsi_lo=42, regime='trend', sl_m=2.8, tp_m=1.0,  hold=48),
    'XAUUSD_H4':  dict(k_body=2.5, br_min=0.6,  streak_n=0, rsi_lo=35, regime='trend', sl_m=3.5, tp_m=1.3,  hold=24),
    'EURUSD_M15': dict(k_body=2.0, br_min=0.6,  streak_n=3, rsi_lo=30, regime='trend', sl_m=3.1, tp_m=1.15, hold=16),
    'EURUSD_M30': dict(k_body=1.6, br_min=0.6,  streak_n=2, rsi_lo=30, regime='trend', sl_m=2.0, tp_m=0.7,  hold=16),
}

# کانفیگ‌های فعالِ S326 (فقط جایی که S326 در موتور فعال است: XAU M5/M30 + EUR M15)
S326_WINNERS = {
    'XAUUSD_M5':  dict(streak_n=5, run_min=0.0, rsi_lo=30, regime='trend', sl_m=3.1, tp_m=1.15, hold=24),
    'XAUUSD_M30': dict(streak_n=5, run_min=2.5, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=48),
    'EURUSD_M15': dict(streak_n=4, run_min=0.0, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=48),
}


def squeeze_breakout_sig(df):
    """L1 — بازتولیدِ منطقِ S132: فشردگیِ BB سپس شکستِ صعودی (continuation LONG)."""
    close = df['close']
    lower, mid, upper = ind.bollinger(close, 20, 2.0)
    width = (upper.values - lower.values) / mid.values
    w = pd.Series(width)
    wq = w.rolling(100, min_periods=30).quantile(0.20).values
    squeeze = width <= wq
    prior_high = df['high'].rolling(6).max().shift(1).values
    breakout = df['close'].values > prior_high
    sig = squeeze & breakout & np.isfinite(width)
    return np.nan_to_num(sig, nan=False).astype(bool)


def triple_sma_pullback_sig(df):
    """L2 — Triple-SMA Stack-Pullback: SMA13>SMA100>SMA200 + پولبک به SMA13."""
    c = df['close']
    s13 = ind.sma(c, 13).values
    s100 = ind.sma(c, 100).values
    s200 = ind.sma(c, 200).values
    cc = c.values
    stacked = (s13 > s100) & (s100 > s200)
    low = df['low'].values
    pullback = (low <= s13) & (cc > s13)
    sig = stacked & pullback
    return np.nan_to_num(sig, nan=False).astype(bool)


def s327_signal(asset, tf, cfg):
    df = S327.load(asset, tf)
    feat = S327.build_features(df, asset)
    sig = S327.make_signals(feat, cfg['k_body'], cfg['br_min'], cfg['streak_n'],
                            cfg['rsi_lo'], cfg['regime'], feat['atr'], feat['c'])
    return df, np.nan_to_num(sig, nan=False).astype(bool)


def s326_signal(asset, tf):
    """سیگنالِ S326 روی همان جفت‌ارز/TF؛ اگر S326 آنجا فعال نیست ⇒ None."""
    key = f'{asset}_{tf}'
    if key not in S326_WINNERS:
        return None
    cfg = S326_WINNERS[key]
    df = s326_load(asset, tf)
    feat = s326_build(df, asset)
    sig = s326_sig(feat, cfg['streak_n'], cfg['run_min'], cfg['rsi_lo'],
                   cfg['regime'], feat['atr'], feat['c'])
    return np.nan_to_num(sig, nan=False).astype(bool)


def overlap_pct(sig_a, sig_b, tol=TOL):
    """کسری از bar-های sig_a که یک True در sig_b در پنجرهٔ ±tol دارند."""
    idx_a = np.where(sig_a)[0]
    if len(idx_a) == 0:
        return 0.0, 0
    idx_b = np.where(sig_b)[0]
    if len(idx_b) == 0:
        return 0.0, len(idx_a)
    hits = 0
    for i in idx_a:
        if np.any(np.abs(idx_b - i) <= tol):
            hits += 1
    return hits / len(idx_a) * 100.0, len(idx_a)


def main():
    print("=" * 96)
    print("S327 — ممیزیِ همپوشانیِ کمّی با لایه‌های فعالِ موتور (±%d کندل)" % TOL)
    print("=" * 96)
    report = {}
    for key, cfg in S327_WINNERS.items():
        asset, tf = key.split('_')
        df, s327 = s327_signal(asset, tf, cfg)
        sq = squeeze_breakout_sig(df)
        tsma = triple_sma_pullback_sig(df)
        s326 = s326_signal(asset, tf)

        ov_sq, n327 = overlap_pct(s327, sq)
        ov_tsma, _ = overlap_pct(s327, tsma)
        parts = [sq, tsma]
        ov_326 = None
        if s326 is not None:
            ov_326, _ = overlap_pct(s327, s326)
            parts.append(s326)
        union = np.zeros(len(df), dtype=bool)
        for p in parts:
            union = union | p
        ov_union, _ = overlap_pct(s327, union)

        print(f"\n[{key}]  S327 signals={n327}")
        if ov_326 is not None:
            print(f"   ↔ S326 Streak-Reversal (reversion) : {ov_326:5.1f}%   ← هم‌خانواده")
        else:
            print(f"   ↔ S326 Streak-Reversal             :   n/a (S326 روی این TF فعال نیست)")
        print(f"   ↔ Squeeze→Breakout (S132)          : {ov_sq:5.1f}%")
        print(f"   ↔ Triple-SMA Pullback              : {ov_tsma:5.1f}%")
        print(f"   ↔ اجتماعِ کلِّ لایه‌ها                : {ov_union:5.1f}%  ⇒ ناهمپوشان={100-ov_union:5.1f}%")
        report[key] = dict(n_signals=int(n327),
                           overlap_s326_streak=(round(ov_326, 1) if ov_326 is not None else None),
                           overlap_squeeze=round(ov_sq, 1),
                           overlap_triple_sma=round(ov_tsma, 1),
                           overlap_union=round(ov_union, 1),
                           non_overlap=round(100 - ov_union, 1))
    json.dump(report, open('results/_s327_overlap_audit.json', 'w'),
              ensure_ascii=False, indent=1)
    print("\nsaved results/_s327_overlap_audit.json")


if __name__ == '__main__':
    main()
