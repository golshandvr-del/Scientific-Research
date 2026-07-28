# -*- coding: utf-8 -*-
"""
S333 — ممیزیِ همپوشانیِ کمّی (قانونِ همپوشانیِ پروژه)
================================================================================
هدف: سنجشِ همپوشانیِ زمانیِ نقاطِ ورودِ S333 (Trend-Pullback دقت‌محور، LONG) با
لایه‌های فعالِ LONGِ موتورِ فعلی روی همان TF.

روش (forward-safe، هم‌تراز با simulate_trades و ممیزی‌های S326/S327):
  «همپوشانی» = کسری از bar-های سیگنالِ S333 که یک سیگنالِ لایهٔ دیگر در پنجرهٔ
  ±TOL کندل حضور دارد (هم‌زمانیِ عملیِ ورود).

لایه‌های مقایسه (LONG، مظنونِ همپوشانی):
  L0) Triple-SMA Stack-Pullback  ← هر دو pullback-در-روندِ صعودی ⇒ بالاترین ریسک
  L1) Squeeze→Breakout (S132/S313/S332 هسته: BB-squeeze + breakout LONG)
  L2) SellClimax-Reversal proxy (S327: RSI پایین در روند، LONG) — رژیمِ مشابه

قانونِ همپوشانی سه‌گانه: (۱) با کدام/چند٪  (۲) حتی ۹۹٪ هم ۱٪ ارزش دارد
  (۳) بخشِ همپوشان را می‌توان فیلترِ بهبود کرد.
اجرا:  python strategies/s333_overlap_audit.py > /tmp/s333_overlap.txt
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import indicators as ind
from engine import scalp_engine as SE
from strategies import s333_s79_pullback_revival as S
import warnings; warnings.filterwarnings('ignore')

TOL = 2  # ±۲ کندل تحملِ هم‌زمانی
TFS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1']


def triple_sma_pullback(df):
    """L0 — پولبک در روندِ صعودیِ SMA13/100/200 (LONG). نزدیک‌ترین همتای S333."""
    c = df['close']
    s13 = c.rolling(13).mean(); s100 = c.rolling(100).mean(); s200 = c.rolling(200).mean()
    up = (s13 > s100) & (s100 > s200)
    pull = c < s13                       # پولبک زیرِ SMA کوتاه
    return np.nan_to_num((up & pull).values).astype(bool)


def squeeze_breakout(df):
    """L1 — فشردگیِ BB سپس شکستِ صعودی (continuation LONG)."""
    c = df['close']
    lo, mid, up = ind.bollinger(c, 20, 2.0)
    bw = (up - lo) / mid
    sq = bw < bw.rolling(120).quantile(0.25)
    brk = c > up
    sig = sq.shift(1).fillna(False) & brk
    return np.nan_to_num(sig.values).astype(bool)


def rsi_low_long(df):
    """L2 — RSI پایین در روندِ صعودی (proxyِ S327 climate). رژیمِ مشابهِ S333."""
    c = df['close'].values
    ef = S.ema(c, 20); es = S.ema(c, 100); r = S.rsi(c, 14)
    return np.nan_to_num((ef > es) & (r < 30)).astype(bool)


def overlap_pct(a_idx, b_sig, tol=TOL):
    """کسری از سیگنال‌های a که در ±tol کندل یک سیگنالِ b دارند."""
    if len(a_idx) == 0:
        return 0.0
    b_where = np.where(b_sig)[0]
    if len(b_where) == 0:
        return 0.0
    hits = 0
    for i in a_idx:
        j = np.searchsorted(b_where, i)
        near = False
        for k in (j - 1, j):
            if 0 <= k < len(b_where) and abs(b_where[k] - i) <= tol:
                near = True; break
        hits += near
    return 100.0 * hits / len(a_idx)


def main():
    print('S333 OVERLAP AUDIT (±%d bars). همپوشانی = %% از ورودهای S333 که لایهٔ دیگر همزمان دارد.' % TOL)
    print('=' * 88)
    for tf in TFS:
        cfg = S.BEST_CFG.get(tf)
        if cfg is None:
            continue
        df = SE.load_data(SE.ASSETS[tf]['file'])
        s333 = S.build_layer(df, cfg)
        idx = np.where(s333)[0]
        o_tri = overlap_pct(idx, triple_sma_pullback(df))
        o_sqz = overlap_pct(idx, squeeze_breakout(df))
        o_rsi = overlap_pct(idx, rsi_low_long(df))
        union = triple_sma_pullback(df) | squeeze_breakout(df) | rsi_low_long(df)
        o_all = overlap_pct(idx, union)
        print('%-12s n_S333=%4d | TripleSMA=%5.1f%%  Squeeze=%5.1f%%  RSIlowLong=%5.1f%%  UNION=%5.1f%%'
              % (tf, len(idx), o_tri, o_sqz, o_rsi, o_all))
    print('=' * 88)
    print('تفسیر: UNION<50% ⇒ لایهٔ عمدتاً مستقل. UNION بالا ⇒ بخشِ همپوشان را فیلترِ بهبود کن.')


if __name__ == '__main__':
    main()
