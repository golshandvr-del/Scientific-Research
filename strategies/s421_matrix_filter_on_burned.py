#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S421 — فیلترِ «ماتریسِ روند×نوسان» روی لایهٔ سوختهٔ LONG (پلِ مأموریت ۳ → ۴)
==============================================================================
وظیفهٔ ۵ سندِ مأموریت ۳: «فیلتر ماتریس روند×نوسان را به‌عنوان بهبود روی لایه‌های
سوختهٔ long موجود تست کن.»

میزبان: S167 RSI-21 Mean-Reversion (REJECT, score 15) — بهترین واریانتِ LONG:
  lo=25, hi=75, SL=150, TP=225, max_hold=16, XAUUSD-M15, n≈243.
انتخابِ میزبان **پیش از دیدنِ هر نتیجهٔ فیلترشده** و صرفاً بر اساسِ اندازهٔ نمونه
(بزرگ‌ترین n در بینِ REJECTهای LONGِ بازتولیدپذیر) انجام شد.

فیلتر (از ماتریسِ نامتقارنِ تأییدشدهٔ فاز ۱۹/۲۰ — همان DNA لایهٔ S420):
  رژیمِ روزِ معاملاتیِ *قبل* (کاملاً علّی):
    BUY-cell : trend_5d < 0  ∧  vol_5d ≥ q75(علّی)   ← فیلترِ اصلی
    BAD-cell : trend_5d > 0  ∧  vol_5d ≥ q75(علّی)   ← کنترل (باید بدتر شود)
سه بازو: بدونِ فیلتر (مبنا) · BUY-cell فقط · BAD-cell فقط.

⚠️ داده M15 فقط ۲۰۲۰–۲۰۲۶ دارد (بازهٔ سوخته) ⇒ این آزمون «بهبودسنجیِ اکتشافی»
است، نه ادعای skill؛ اگر بهبودِ معنادار دید، مسیرِ رسمیِ مأموریت ۴ (S430+) با
پیش‌ثبتِ خودش بازش می‌کند. خروجی فقط گزارش می‌شود.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se               # noqa: E402
from engine import indicators as ind                # noqa: E402
from strategies.s420_capitulation_decel import (    # noqa: E402
    build_trading_days, daily_features, W)

DATA = 'data/XAUUSD_M15.csv'
ASSET = 'XAUUSD'
HOST = dict(lo=25, hi=75, sl=150.0, tp=225.0, mh=16)   # S167 بهترین LONG — منجمد
Q = 0.75
OUT = os.path.join(ROOT, 'results', '_scan_S420', 'S421_matrix_filter_s167.json')


def host_long_signals(df):
    """سیگنالِ LONGِ دقیقِ S167 (cross-back از oversold، shift-safe)."""
    rsi = ind.rsi(df['close'], 21)
    rsi_prev = rsi.shift(1)
    long_raw = (rsi_prev < HOST['lo']) & (rsi >= HOST['lo'])
    return long_raw.shift(1).fillna(False).to_numpy()


def regime_mask_per_bar(df, days):
    """برچسبِ رژیمِ هر کندلِ M15 از روی روزِ معاملاتیِ *قبل* (علّی).

    خروجی: buy_ok[bar], bad_ok[bar] — bool
    """
    rets, trend, vol = daily_features(days)
    n_days = len(days)
    # آستانهٔ q علّی برای هر روز (تا روزِ i-1)
    thr = np.full(n_days, np.nan)
    for i in range(W, n_days):
        hist = vol[W:i]
        hist = hist[np.isfinite(hist)]
        if len(hist) >= 60:
            thr[i] = np.quantile(hist, Q)
    # رژیمِ خودِ روزِ i (کامل‌شده در پایانِ روزِ i)
    buy_day = (trend < 0) & (vol >= thr)
    bad_day = (trend > 0) & (vol >= thr)

    buy_ok = np.zeros(len(df), dtype=bool)
    bad_ok = np.zeros(len(df), dtype=bool)
    for i in range(1, n_days):
        a, b = days[i]['first_bar'], days[i]['last_bar']
        if np.isfinite(thr[i - 1]):
            # کندل‌های روزِ i از رژیمِ روزِ i-1 (کامل‌شده) استفاده می‌کنند — علّی
            buy_ok[a:b + 1] = bool(buy_day[i - 1])
            bad_ok[a:b + 1] = bool(bad_day[i - 1])
    return buy_ok, bad_ok


def run_arm(df, ls, name):
    ss = np.zeros(len(df), dtype=bool)
    tr = se.simulate_trades(df, ls, ss, HOST['sl'], HOST['tp'], ASSET,
                            max_hold=HOST['mh'], allow_overlap=False)
    if len(tr) == 0:
        print(f"  {name:28s}: no trades")
        return dict(name=name, n=0)
    p = tr['pnl_pip'].values
    n = len(tr)
    wr = float((p > 0).mean() * 100)
    exp = float(p.mean())
    sd = p.std(ddof=1)
    t = exp / (sd / np.sqrt(n)) if n > 2 and sd > 0 else 0.0
    cap, _ = se.run_capital(tr, ASSET)
    r = dict(name=name, n=n, wr=wr, exp_pip=exp, t=float(t),
             net_pip=float(p.sum()), net_usd=float(cap['net_profit']),
             pf=float(cap['profit_factor']))
    print(f"  {name:28s}: n={n:3d} WR={wr:5.1f}% exp={exp:+7.2f}pip "
          f"t={t:+5.2f} net={r['net_usd']:+9.2f}$ PF={r['pf']:.2f}")
    return r


def main():
    print("S421 · matrix filter (trend×vol) on burned S167-long · XAUUSD-M15")
    print("⚠ exploratory improvement test on burned 2020-2026 window — no skill claim")
    df = se.load_data(DATA)
    days = build_trading_days(df)
    print(f"bars={len(df)}  trading_days={len(days)}  "
          f"({days[0]['date'].date()} → {days[-1]['date'].date()})")
    ls0 = host_long_signals(df)
    buy_ok, bad_ok = regime_mask_per_bar(df, days)
    print(f"host long signals: {int(ls0.sum())}  |  "
          f"bars in BUY-cell: {int(buy_ok.sum())} ({buy_ok.mean()*100:.1f}%)  "
          f"BAD-cell: {int(bad_ok.sum())} ({bad_ok.mean()*100:.1f}%)")
    rows = [
        run_arm(df, ls0, 'baseline (no filter)'),
        run_arm(df, ls0 & buy_ok, 'BUY-cell (down+Q4vol)'),
        run_arm(df, ls0 & bad_ok, 'BAD-cell control (up+Q4vol)'),
        run_arm(df, ls0 & ~(buy_ok | bad_ok), 'complement (rest)'),
    ]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    print(f"saved → {OUT}")


if __name__ == '__main__':
    main()
