# -*- coding: utf-8 -*-
"""
s313c_directional_edge_probe.py — آزمونِ لبهٔ آماریِ خامِ Squeeze-Breakout

هدف: پیش از هر بهبودِ پیچیده‌ترِ TP/SL، به‌صورتِ علمی و مستقل از شبیه‌ساز
بسنجیم که آیا سیگنالِ «فشردگیِ بولینگر → شکستِ سقف در آپ‌ترند» اصلاً یک لبهٔ
جهت‌دارِ معنادار روی طلا دارد یا نه. اگر بازده آتیِ سیگنال از بازده رندومِ کلِ
بازار (در همان افق) به‌طورِ معنادار (t-stat) بالاتر نباشد، هیچ ترکیبی از TP/SL
نمی‌تواند آن را نجات دهد (قانونِ مرگِ ابدی → کاندیدای DEAD).

روش:
  - سیگنالِ خام: sqz_pct≤0.30، close>prior_high(10)، EMA50>EMA200.
  - بازده آتیِ H کندل (درصد) از close سیگنال.
  - مقایسه با توزیعِ بازده رندومِ H-کندلیِ کلِ بازار (baseline).
  - t-test تک‌نمونه‌ای: آیا mean(fwd) از mean(random) معنادار بالاتر است؟
  - همچنین آزمونِ جهتِ SHORT و آزمونِ mean-reversion (fade).
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
from engine import trade_simulator as TS
from engine import indicators as ind


def build_signal(df, sqz_pct=0.30, breakout_lb=10, sqz_lookback=100,
                 ema_fast=50, ema_slow=200, bb_period=20, bb_k=2.0):
    c = df['close']; cl = c.to_numpy(); h = df['high'].to_numpy()
    n = len(cl)
    mid = c.rolling(bb_period).mean()
    std = c.rolling(bb_period).std(ddof=0)
    bw = (2.0 * bb_k * std / mid).to_numpy()
    lb = sqz_lookback; win = lb + 1
    bw_pct = np.full(n, np.nan)
    if n >= win:
        sw = np.lib.stride_tricks.sliding_window_view(bw, win)
        last = sw[:, -1][:, None]; valid = ~np.isnan(sw)
        frac = ((sw <= last) & valid).sum(1) / np.maximum(valid.sum(1), 1)
        bw_pct[win - 1:] = frac
    ef = ind.ema(c, ema_fast).to_numpy(); es = ind.ema(c, ema_slow).to_numpy()
    prior_high = pd.Series(h).rolling(breakout_lb).max().shift(1).to_numpy()
    sqz_prev = np.concatenate([[np.nan], bw_pct[:-1]])
    sig = (sqz_prev <= sqz_pct) & (cl > prior_high) & (ef > es)
    sig = np.where(np.isnan(sig), False, sig)
    return np.asarray(sig, dtype=bool), cl


def tstat(sample, popmean):
    s = sample[np.isfinite(sample)]
    if len(s) < 5:
        return 0.0, 0.0, len(s)
    m = s.mean(); sd = s.std(ddof=1)
    se = sd / np.sqrt(len(s)) if sd > 0 else np.nan
    t = (m - popmean) / se if se and np.isfinite(se) and se > 0 else 0.0
    return m, t, len(s)


def main():
    tfs = ['XAUUSD_H1', 'XAUUSD_M30', 'XAUUSD_M15', 'XAUUSD_M5']
    print("#" * 74)
    print("# S313c — آزمونِ لبهٔ آماریِ خامِ Squeeze-Breakout (بازده آتی vs رندوم)")
    print("#" * 74)
    for tf in tfs:
        try:
            df = TS.load_data(tf)
        except Exception as e:
            print(f"{tf}: خطا در بارگذاری — {e}")
            continue
        sig, cl = build_signal(df)
        n = len(cl)
        idx = np.where(sig)[0]
        print(f"\n===== {tf} (rows={n}, signals={len(idx)}) =====")
        for H in [6, 12, 24, 48]:
            ii = idx[idx < n - H]
            if len(ii) < 10:
                print(f"  H={H:3d}: n<10, رد")
                continue
            fwd = (cl[ii + H] - cl[ii]) / cl[ii] * 100.0          # بازده LONG سیگنال
            rnd = (cl[H:] - cl[:-H]) / cl[:-H] * 100.0            # بازده رندومِ کل
            rnd_mean = rnd[np.isfinite(rnd)].mean()
            m, t, k = tstat(fwd, rnd_mean)                        # t نسبت به baseline
            pos = (fwd > 0).mean() * 100
            edge = m - rnd_mean
            verdict = "لبه‌دار✓" if abs(t) >= 2.0 else "بی‌لبه✗"
            print(f"  H={H:3d}: n={k:4d} fwd={m:+.3f}% pos={pos:4.1f}% | "
                  f"rnd={rnd_mean:+.3f}% edge={edge:+.3f}% t={t:+.2f} → {verdict}")
    print("\nنتیجه‌گیری: اگر برای هیچ H، |t|≥2 نشد ⇒ لبهٔ جهت‌دارِ معناداری وجود ندارد.")


if __name__ == '__main__':
    main()
