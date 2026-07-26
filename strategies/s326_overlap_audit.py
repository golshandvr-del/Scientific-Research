# -*- coding: utf-8 -*-
"""
S326 — ممیزیِ همپوشانی (قانونِ همپوشانیِ پروژه)
================================================================================
هدف: سنجشِ کمّیِ همپوشانیِ زمانیِ نقاطِ ورودِ S326 (Streak-Reversal / reversion، TP<SL)
با نقاطِ ورودِ لایه‌های فعالِ فعلیِ موتورِ local-mobile روی همان TF/جفت‌ارز:
  L1) S132 Squeeze→Breakout  (BB-squeeze + breakout، continuation، LONG)
  L2) Triple-SMA Stack-Pullback (SMA13/100/200، پولبک در روندِ صعودی، LONG)

روش (forward-safe، هم‌تراز با simulate_trades):
  - برای هر لایه سیگنالِ LONG per-bar می‌سازیم.
  - «همپوشانی» = کسری از bar-های سیگنالِ S326 که یک سیگنالِ لایهٔ فعال در پنجرهٔ
    ±TOL کندل حضور دارد (هم‌زمانیِ عملی برای بازِ معامله).
  - سه عدد گزارش می‌شود: overlap با Squeeze، با Triple-SMA، و اجتماع (کل).

قانونِ همپوشانی — سه‌گانه:
  (۱) دقیقاً با کدام لایه/چند درصد.
  (۲) حتی اگر ۹۹٪ همپوشانی، آن ۱٪ متفاوت ارزشِ افزودن دارد.
  (۳) از بخشِ همپوشان می‌توان به‌عنوان فیلترِ بهبود استفاده کرد (اینجا معکوس:
      بررسی می‌کنیم آیا S326 می‌تواند فیلترِ ضدِّ لایه‌های continuation باشد).
"""
import sys, json
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import indicators as ind
from strategies.s326_streak_reversal_revival import load, build_features, make_signals
import warnings; warnings.filterwarnings('ignore')

TOL = 2  # ±۲ کندل تحملِ هم‌زمانی

# کانفیگ‌های برندهٔ RQS+≥80 (از _s326_streak_reversal_multitf.json)
WINNERS = {
    'XAUUSD_M5':  dict(streak_n=5, run_min=0.0, rsi_lo=30, regime='trend', sl_m=3.1, tp_m=1.15, hold=24),
    'XAUUSD_M30': dict(streak_n=5, run_min=2.5, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=48),
    'EURUSD_M15': dict(streak_n=4, run_min=0.0, rsi_lo=30, regime='trend', sl_m=3.5, tp_m=1.3,  hold=48),
}


def squeeze_breakout_sig(df):
    """L1 — بازتولیدِ منطقِ S132: فشردگیِ BB سپس شکستِ صعودی (continuation LONG)."""
    close = df['close']
    lower, mid, upper = ind.bollinger(close, 20, 2.0)
    width = (upper.values - lower.values) / mid.values
    n = len(df)
    # فشردگی: پهنای BB در پایین‌ترین ۲۰٪ تاریخیِ ۱۰۰ کندلِ اخیر
    w = pd.Series(width)
    wq = w.rolling(100, min_periods=30).quantile(0.20).values
    squeeze = width <= wq
    # شکستِ صعودی: close از سقفِ ۶ کندلِ اخیر بالاتر
    prior_high = df['high'].rolling(6).max().shift(1).values
    breakout = df['close'].values > prior_high
    sig = squeeze & breakout & np.isfinite(width)
    return np.nan_to_num(sig, nan=False).astype(bool)


def triple_sma_pullback_sig(df):
    """L2 — Triple-SMA Stack-Pullback: SMA13>SMA100>SMA200 (روندِ صعودی) + پولبک به SMA13."""
    c = df['close']
    s13 = ind.sma(c, 13).values
    s100 = ind.sma(c, 100).values
    s200 = ind.sma(c, 200).values
    cc = c.values
    stacked = (s13 > s100) & (s100 > s200)          # روندِ صعودیِ چیده‌شده
    low = df['low'].values
    pullback = (low <= s13) & (cc > s13)            # لمسِ SMA13 و بستنِ بالای آن
    sig = stacked & pullback
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
    print("=" * 90)
    print("S326 — ممیزیِ همپوشانیِ کمّی با لایه‌های فعالِ موتور (±%d کندل)" % TOL)
    print("=" * 90)
    report = {}
    for key, cfg in WINNERS.items():
        asset, tf = key.split('_')
        df = load(asset, tf)
        feat = build_features(df, asset)
        s326 = make_signals(feat, cfg['streak_n'], cfg['run_min'], cfg['rsi_lo'],
                            cfg['regime'], feat['atr'], feat['c'])
        sq = squeeze_breakout_sig(df)
        tsma = triple_sma_pullback_sig(df)
        union = sq | tsma
        ov_sq, n326 = overlap_pct(s326, sq)
        ov_tsma, _ = overlap_pct(s326, tsma)
        ov_union, _ = overlap_pct(s326, union)
        print(f"\n[{key}]  S326 signals={n326}")
        print(f"   ↔ Squeeze→Breakout (S132)   : {ov_sq:5.1f}%")
        print(f"   ↔ Triple-SMA Pullback        : {ov_tsma:5.1f}%")
        print(f"   ↔ اجتماعِ کلِّ لایه‌های فعال   : {ov_union:5.1f}%  ⇒ ناهمپوشان={100-ov_union:5.1f}%")
        report[key] = dict(n_signals=int(n326), overlap_squeeze=round(ov_sq, 1),
                           overlap_triple_sma=round(ov_tsma, 1),
                           overlap_union=round(ov_union, 1),
                           non_overlap=round(100 - ov_union, 1))
    json.dump(report, open('results/_s326_overlap_audit.json', 'w'),
              ensure_ascii=False, indent=1)
    print("\nsaved results/_s326_overlap_audit.json")


if __name__ == '__main__':
    main()
