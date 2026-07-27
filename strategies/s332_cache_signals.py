# -*- coding: utf-8 -*-
"""
S332 — پیش‌محاسبه و کشِ سیگنالِ squeeze + اندیکاتورها برای هر (sym,tf)
================================================================================
build_squeeze_signal روی ۱۵۰k کندل (حلقهٔ پایتونی) کند است و تکرارِ آن در هر اسکن
سندباکس را کند می‌کند. این ماژول یک‌بار محاسبه و در .npz کش می‌کند.
اجرا:  python3 strategies/s332_cache_signals.py --sym XAUUSD --tf H1 --sqz 0.25 --brk 6
"""
import os
import sys
import argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import strategies.s332_squeeze_rqs_revival as S

CACHE = os.path.join(ROOT, 'strategies', '_s332_cache')
os.makedirs(CACHE, exist_ok=True)


def cache_path(sym, tf, sqz, brk):
    return os.path.join(CACHE, f"{sym}_{tf}_sqz{int(sqz*100)}_brk{brk}.npz")


def build_and_cache(sym, tf, sqz=0.25, brk=6):
    df = S.load_tf(sym, tf)
    if df is None:
        print(f"no data {sym} {tf}")
        return None
    c = df['close'].values.astype(float)
    sig = S.build_squeeze_signal(df, sqz_pct=sqz, breakout_lookback=brk)
    adx_, pdi, mdi = S.adx(df, 14)
    r14 = S.rsi(c, 14)
    e20 = S.ema(c, 20); e50 = S.ema(c, 50); e100 = S.ema(c, 100)
    atr_ = S.atr(df, 14)
    p = cache_path(sym, tf, sqz, brk)
    np.savez_compressed(p, sig=sig, adx=adx_, pdi=pdi, mdi=mdi, rsi=r14,
                        e20=e20, e50=e50, e100=e100, atr=atr_)
    print(f"cached {p} | signals={int(sig.sum())} candles={len(df)}")
    return p


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--sym', default='XAUUSD')
    ap.add_argument('--tf', default='H1')
    ap.add_argument('--sqz', type=float, default=0.25)
    ap.add_argument('--brk', type=int, default=6)
    a = ap.parse_args()
    build_and_cache(a.sym, a.tf, a.sqz, a.brk)
