# -*- coding: utf-8 -*-
"""
S326 — احیای لایهٔ سوختهٔ S22 (Streak-Reversal / Mean-Reversion پس از رگهٔ کندلی)
با معیارِ رسمیِ جدیدِ RQS+ ≥ 80
================================================================================
مبنای سوختن: results/Streak_Reversal_MeanRev_58.md
  ایدهٔ پایه: کشفِ serial-dependence روی XAUUSD M15 — پس از N کندلِ نزولیِ متوالی،
  احتمالِ برگشتِ صعودیِ کندلِ بعد ≈ 53–54٪ (یک edge خامِ واقعی، نه تلهٔ RR).
  در عصرِ «WR>60٪ + exp>0 + ≥۳ معامله/روز به‌طور همزمان» رد شد (سقفِ WR فقط ۵۹.۵٪،
  و هر جا WR بالا بود فرکانس به ۰.۲۵/روز سقوط می‌کرد).

--------------------------------------------------------------------------------
تشخیصِ ریشه‌ایِ سوختن (کشفِ این نشست — نبوغ + تفکر غیرخطی):
--------------------------------------------------------------------------------
  (۱) معیارِ غلطِ عصرِ WR:  قیدِ «≥۳ معامله در روز» یک قیدِ فرکانسیِ خودسرانه بود که
      هیچ ربطی به کیفیتِ لبه ندارد. RQS+ فرکانس را گیت نمی‌کند؛ فقط پایداری/معناداری/دُم.
      پس همان نقطهٔ N=6/rsi<30 که در عصرِ WR «رد» شد چون ۰.۲۵ معامله/روز بود،
      از منظرِ RQS+ می‌تواند کاملاً معتبر باشد (اگر n≥30 و WF-4/4 پاس شود).
  (۲) TP/SL: در فایلِ قدیم TP=1.0×ATR و SL=1.5×ATR ⇒ TP<SL که خوب است، اما فیلترِ
      کیفیت نداشت و ATR-مضربِ رند بود؛ WR فقط ~۵۹٪ ماند (زیرِ ۶۰).
  (۳) هیچ فیلترِ کیفیتِ «رگه»ای نبود: عمقِ رگه، شتابِ رگه بر ATR، موقعیت نسبت به
      باندِ پایینیِ Bollinger، رژیمِ روندِ بالاتر — هیچ‌کدام آزموده نشد.

--------------------------------------------------------------------------------
تزِ نو (چرا این‌بار زنده می‌شود):
--------------------------------------------------------------------------------
  یک رگهٔ نزولیِ *کشیده و شتاب‌دار* = فروشِ هیجانیِ کوتاه‌مدت (capitulation) ⇒ بازگشتِ
  فوریِ mean-reversion. این ذاتاً WR-بالاست اگر هدف را کوچک و سریع بگیریم (TP<SL).
  درسِ صریحِ S324/S304: «تمرکزِ احیا روی fade/mean-reversion که ذاتاً WR بالا دارد».
  کلیدِ احیا = TP کوچکِ سریع (< SL) + فیلترِ کیفیتِ رگه ⇒ WR_breakeven پایین ⇒
  G0(WR≥60) + G1(p<0.05) با هم پاس.

--------------------------------------------------------------------------------
بهبودهای شناور (قانونِ «همه چیز شناور» + بی‌نهایت):
--------------------------------------------------------------------------------
  B1) طولِ رگه شناور  (streak_n ∈ {3,4,5,6})
  B2) شتابِ رگهٔ کل بر ATR شناور (run_min = |close0 - closeN| / ATR ≥ آستانه)
      ⇒ فقط رگه‌های «کشیده» (capitulation) نه رگه‌های آرام.
  B3) فیلترِ RSI اشباع فروش شناور (rsi_lo ∈ {OFF, 40, 35, 30})
  B4) فیلترِ رژیم/موقعیت شناور:
        - close < BB_lower×k  (خارج/نزدیکِ باندِ پایینی — کشِ کِش‌بند)
        - یا close > EMA200 (فقط bounce در روندِ صعودیِ کلان — با بایاسِ ساختاریِ طلا)
  B5) SL/TP نامتقارنِ ATR-محورِ *غیر-رند* شناور (TP<SL؛ tp_mult, sl_mult غیر-رند)
  B6) max_hold شناور (رگه‌بازگشت باید سریع باشد؛ اگر دیر شد ⇒ رگه ادامهٔ روند بوده)
  B7) مولتی‌تایم‌فریم اجباری: XAUUSD {M5,M15,M30,H1,H4} + EURUSD {M5,M15,M30}

⚠️ همه forward-safe: رگه از کندل‌های *بسته‌شده* شمرده می‌شود؛ سیگنال روی کندلِ si،
   ورود روی open[si+1] (خودِ simulate_trades این را رعایت می‌کند).
"""
import sys, os, time, itertools
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from engine import scalp_engine as se
from engine import indicators as ind
from engine import rqs
import warnings; warnings.filterwarnings('ignore')

DATA = {
    'XAUUSD': ['M5', 'M15', 'M30', 'H1', 'H4'],
    'EURUSD': ['M5', 'M15', 'M30'],
}


def load(asset, tf):
    path = f'data/{asset}_{tf}.csv'
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    for col in ('open', 'high', 'low', 'close'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.dropna(subset=['open', 'high', 'low', 'close']).reset_index(drop=True)


def build_features(df, asset):
    """اندیکاتورهای forward-safe (همه از گذشته)."""
    o = df['open'].values.astype(float)
    c = df['close'].values.astype(float)
    n = len(df)
    atr = ind.atr(df, 14).values
    rsi = ind.rsi(df['close'], 14).values
    ema200 = ind.ema(df['close'], 200).values
    lower, mid, upper = ind.bollinger(df['close'], 20, 2.0)
    bb_lower = lower.values
    # رگهٔ نزولیِ متوالی تا کندلِ t (شاملِ t): تعداد کندل‌های پیاپی با close<open
    down = (c < o).astype(int)
    streak = np.zeros(n, dtype=int)
    run = 0
    for i in range(n):
        if down[i]:
            run += 1
        else:
            run = 0
        streak[i] = run
    return dict(o=o, c=c, atr=atr, rsi=rsi, ema200=ema200,
                bb_lower=bb_lower, streak=streak, n=n)


def make_signals(feat, streak_n, run_min, rsi_lo, regime, atr, c):
    """سیگنالِ LONG: پایانِ رگهٔ نزولیِ کشیده + فیلترهای کیفیت."""
    n = feat['n']
    sig = (feat['streak'] >= streak_n)
    # B2 — شتابِ رگهٔ کل بر ATR: |close(t-streak) - close(t)| باید کشیده باشد
    if run_min > 0:
        run_amp = np.zeros(n)
        st = feat['streak']
        cc = feat['c']
        for i in range(n):
            k = st[i]
            if k >= 1 and i - k >= 0 and atr[i] > 0:
                run_amp[i] = (cc[i - k] - cc[i]) / atr[i]  # نزولی ⇒ مثبت
        sig = sig & (run_amp >= run_min)
    # B3 — RSI اشباع فروش
    if rsi_lo is not None:
        sig = sig & (feat['rsi'] <= rsi_lo)
    # B4 — رژیم/موقعیت
    if regime == 'bb':      # کشِ کِش‌بند: زیرِ باندِ پایینی
        sig = sig & (c < feat['bb_lower'])
    elif regime == 'trend': # فقط bounce در روندِ صعودیِ کلان
        sig = sig & (c > feat['ema200'])
    # NaN امن
    sig = sig & np.isfinite(atr) & (atr > 0)
    return sig


def scan(asset, tf, verbose=False):
    df = load(asset, tf)
    feat = build_features(df, asset)
    atr = feat['atr']
    c = feat['c']
    pip = se.ASSETS[asset]['pip']
    n = feat['n']

    best = None
    grid_streak = [3, 4, 5, 6]
    grid_run    = [0.0, 1.2, 1.8, 2.5]          # شتابِ رگه بر ATR (غیر-رند)
    grid_rsi    = [None, 42, 35, 30]
    grid_regime = [None, 'bb', 'trend']
    # SL/TP نامتقارنِ *غیر-رند* (TP<SL برای WR-بالا) — به pip از ATR
    grid_sltp   = [(2.4, 0.8), (2.8, 1.0), (3.1, 1.15), (2.0, 0.7), (3.5, 1.3)]
    grid_hold   = [24, 48]

    evals = 0
    for streak_n, run_min, rsi_lo, regime in itertools.product(
            grid_streak, grid_run, grid_rsi, grid_regime):
        sig = make_signals(feat, streak_n, run_min, rsi_lo, regime, atr, c)
        if sig.sum() < 30:
            continue
        long_sig = sig
        short_sig = np.zeros(n, dtype=bool)
        for (sl_m, tp_m), hold in itertools.product(grid_sltp, grid_hold):
            # SL/TP شناورِ per-bar بر پایهٔ ATR (به pip)
            atr_pip = np.where(atr > 0, atr / pip, np.nan)
            sl_pip = sl_m * atr_pip
            tp_pip = tp_m * atr_pip
            valid = np.isfinite(sl_pip) & (sl_pip > 0)
            if valid.sum() < 30:
                continue
            sl_pip = np.where(valid, sl_pip, 1.0)
            tp_pip = np.where(valid, tp_pip, 1.0)
            tr = se.simulate_trades(df, long_sig & valid, short_sig,
                                    sl_pip, tp_pip, asset,
                                    max_hold=hold, allow_overlap=False)
            evals += 1
            if tr is None or len(tr) < 30:
                continue
            r = rqs.compute_rqs(tr, asset)
            score = r['rqs_score']
            cfg = dict(streak_n=streak_n, run_min=run_min, rsi_lo=rsi_lo,
                       regime=regime, sl_m=sl_m, tp_m=tp_m, hold=hold)
            if best is None or score > best[0]:
                best = (score, r, cfg)
                if verbose and r['passed']:
                    print(f"  [{asset} {tf}] {rqs.format_report('S326', r)}  cfg={cfg}")
    return best, evals


if __name__ == '__main__':
    t0 = time.time()
    print("=" * 100)
    print("S326 — احیای S22 Streak-Reversal با RQS+ | مولتی‌تایم‌فریم اجباری (از XAUUSD M5)")
    print("=" * 100)
    results = {}
    for asset in ['XAUUSD', 'EURUSD']:
        for tf in DATA[asset]:
            key = f"{asset}_{tf}"
            best, evals = scan(asset, tf, verbose=True)
            results[key] = best
            if best is None:
                print(f"{key:14s} | NO CANDIDATE (n<30 everywhere)  [{evals} evals]")
            else:
                score, r, cfg = best
                print(f"{key:14s} | {rqs.format_report('best', r)}")
                print(f"{'':14s}   cfg={cfg}  [{evals} evals]")
    print("-" * 100)
    print(f"⏱ {time.time()-t0:.1f}s")

    # خلاصهٔ پاس‌شده‌ها
    print("\n=== لایه‌های گیت-پاسِ RQS+≥80 ===")
    any_pass = False
    for k, b in results.items():
        if b and b[1]['passed'] and b[0] >= 80:
            any_pass = True
            print(f"  ✅ {k}: RQS+={b[0]}  cfg={b[2]}")
    if not any_pass:
        print("  (هیچ ترکیبی هنوز RQS+≥80 نداد — نیاز به بهبودِ بیشتر یا DEAD)")
