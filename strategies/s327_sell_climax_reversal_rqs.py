# -*- coding: utf-8 -*-
"""
S327 — احیای لایهٔ سوختهٔ S174 (Al Brooks «Sell-Climax Exhaustion Reversal» → LONG)
با معیارِ رسمیِ جدیدِ RQS+ ≥ 80
================================================================================
مبنای سوختن: results/S174_BrooksSellClimaxReversal_NetProfit_237181_REJECTED.md
  ایدهٔ پایه (کتابِ Al Brooks، Trading Price Action: TRENDS، فصلِ ۲):
  «وقتی یک روندِ نزولیِ کشیده به یک بدنهٔ نزولیِ استثنایی-بزرگ (sell-climax) می‌رسد،
   این نشانهٔ خالی‌شدنِ فروش (sell vacuum) و خستگیِ روند است ⇒ قوی‌ها تهاجمی می‌خرند
   ⇒ ورودِ LONGِ برگشتی.»
  در نشستِ S174 رد شد. علتِ رد در آن سند: (۱) لبه واقعی بود (Δ+$1,977 فراتر از
  long-bias) اما ۴۹٪ همپوشان با اجتماعِ LONGِ طلا و سهمِ مستقلش WF-fail شد؛
  (۲) به‌عنوان فیلترِ ردِ SHORT روی S173، WR/PF را بهبود داد ولی سودِ خالص را −$162
  کاهش داد و در پارادایمِ «سودِ خالص است» رد شد.

--------------------------------------------------------------------------------
تشخیصِ ریشه‌ایِ سوختن (کشفِ این نشست — نبوغ + تفکرِ غیرخطی):
--------------------------------------------------------------------------------
  (۱) TP/SL معکوس نسبت به ماهیتِ لایه:  S174 با TP375/SL250 آزموده شد (TP>SL). این
      برای یک لایهٔ *reversal/exhaustion* یک تناقضِ ساختاری است: برگشتِ پس از climax
      ذاتاً یک حرکتِ *سریع و کوتاه* است (بازگشت به میانگین)، نه یک روندِ کشیدهٔ جدید.
      TP>SL نرخِ بردِ سربه‌سر را بالا می‌برد (breakeven=SL/(SL+TP)) و WR را به ۴۶.۹٪
      می‌کوبد ⇒ G0(WR≥60) قطعاً رد. راه‌حلِ RQS+: **TP کوچکِ سریع < SL** (fade).
  (۲) معیارِ قدیم فیلترِ climax را چون net را −$162 کرد رد کرد؛ اما RQS+ اصلاً net را
      بهینه نمی‌کند — PF/پایداری/دُم مهم‌اند. فیلترِ climax روی S173: PF 1.36→1.58،
      WR 50→52.3 (بخشِ ۵ سندِ S174). این دقیقاً همان چیزی است که RQS+ می‌خواهد.
  (۳) هیچ فیلترِ کیفیتِ چندبُعدیِ climax آزموده نشد: نسبتِ بدنه به دامنه (body ratio)،
      lower-wick (نشانهٔ ردِ فروش)، RSI اشباعِ فروش، فاصله از BB_lower، و طولِ رگهٔ
      نزولی — همه شناور می‌شوند.

--------------------------------------------------------------------------------
تزِ نو (چرا این‌بار زنده می‌شود — قانونِ «همه چیز شناور»):
--------------------------------------------------------------------------------
  sell-climax = فروشِ هیجانیِ خسته ⇒ mean-reversion فوری. با TP<SL این ذاتاً WR-بالاست.
  کلیدِ احیا = (الف) TP کوچکِ غیر-رند < SL  +  (ب) فیلترِ چندبُعدیِ کیفیتِ climax
  ⇒ WR_breakeven پایین ⇒ G0(WR≥60) + G1(p<0.05) با هم پاس.

بهبودهای شناور (قانونِ بی‌نهایت + «هیچ چیز ثابت نیست»):
  B1) قدرتِ کلایمکس: |body| ≥ k_body × میانگینِ ۲۰-کندلیِ |body|   (k_body غیر-رند)
  B2) نسبتِ بدنه به دامنهٔ کندلِ climax: body/range ≥ آستانه (کندلِ پرقدرتِ نزولی)
  B3) طولِ رگه/روندِ نزولی: streak_n کندلِ پیاپیِ close<open  یا  زیرِ EMA_fast
  B4) RSI اشباعِ فروش شناور (rsi_lo ∈ {OFF,42,35,30})
  B5) موقعیت: close < BB_lower×k (کشِ کِش‌بند)  یا  close>EMA200 (bounce در بولِ کلان)
  B6) SL/TP نامتقارنِ ATR-محورِ *غیر-رند* شناور (TP<SL)
  B7) max_hold شناور (بازگشت باید سریع باشد)
  B8) مولتی‌تایم‌فریم اجباری: XAUUSD {M5,M15,M30,H1,H4} + EURUSD {M5,M15,M30} — از XAU M5

⚠️ همه forward-safe: climax/رگه از کندل‌های *بسته‌شده* شمرده می‌شود؛ سیگنال روی کندلِ
   si، ورود روی open[si+1] (simulate_trades خودش رعایت می‌کند).
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
    """اندیکاتورهای forward-safe (همه از کندل‌های بسته‌شده)."""
    o = df['open'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    c = df['close'].values.astype(float)
    n = len(df)
    atr = ind.atr(df, 14).values
    rsi = ind.rsi(df['close'], 14).values
    ema_fast = ind.ema(df['close'], 20).values
    ema200 = ind.ema(df['close'], 200).values
    lower, mid, upper = ind.bollinger(df['close'], 20, 2.0)
    bb_lower = lower.values

    body = np.abs(c - o)
    rng = np.maximum(h - l, 1e-12)
    body_ratio = body / rng                       # B2 — قدرتِ بدنه
    lower_wick = (np.minimum(o, c) - l) / rng      # ردِ فروش (سایهٔ پایینی)
    is_bear = (c < o)

    # میانگینِ ۲۰-کندلیِ |body| (shift-safe: از کندلِ قبل، بدونِ خودِ کندل)
    body_s = pd.Series(body)
    body_ma = body_s.rolling(20).mean().shift(1).values

    # رگهٔ نزولیِ متوالی تا کندلِ t (شاملِ t)
    down = is_bear.astype(int)
    streak = np.zeros(n, dtype=int)
    run = 0
    for i in range(n):
        if down[i]:
            run += 1
        else:
            run = 0
        streak[i] = run

    return dict(o=o, h=h, l=l, c=c, atr=atr, rsi=rsi, ema_fast=ema_fast,
                ema200=ema200, bb_lower=bb_lower, body=body, body_ratio=body_ratio,
                lower_wick=lower_wick, is_bear=is_bear, body_ma=body_ma,
                streak=streak, n=n)


def make_signals(feat, k_body, br_min, streak_n, rsi_lo, regime, atr, c):
    """سیگنالِ LONG: کلایمکسِ فروش (بدنهٔ استثنایی-بزرگِ نزولی) + فیلترهای کیفیت."""
    n = feat['n']
    # هستهٔ climax: کندلِ نزولی + بدنه ≥ k_body × میانگینِ بدنه
    sig = feat['is_bear'] & np.isfinite(feat['body_ma']) & (feat['body_ma'] > 0)
    sig = sig & (feat['body'] >= k_body * feat['body_ma'])
    # B2 — نسبتِ بدنه به دامنه (کندلِ پرقدرت، نه دوجی)
    if br_min > 0:
        sig = sig & (feat['body_ratio'] >= br_min)
    # B3 — طولِ رگهٔ نزولیِ منتهی (روندِ نزولیِ کشیده پیش از climax)
    if streak_n > 0:
        sig = sig & (feat['streak'] >= streak_n)
    # B4 — RSI اشباعِ فروش
    if rsi_lo is not None:
        sig = sig & (feat['rsi'] <= rsi_lo)
    # B5 — رژیم/موقعیت
    if regime == 'bb':      # زیرِ باندِ پایینیِ Bollinger (کشِ کِش‌بند)
        sig = sig & (c < feat['bb_lower'])
    elif regime == 'trend': # bounce فقط در روندِ صعودیِ کلان
        sig = sig & (c > feat['ema200'])
    elif regime == 'below': # زیرِ EMA_fast (رژیمِ نزولیِ کوتاه‌مدت — تزِ اصلیِ Brooks)
        sig = sig & (c < feat['ema_fast'])
    sig = sig & np.isfinite(atr) & (atr > 0)
    return sig


def _cheap_prefilter(tr, asset, wr_min=58.0, pf_min=1.25):
    """پیش‌فیلترِ ارزان بدونِ WF: (n, WR, PF) مستقیم از pnl_pip."""
    if tr is None or len(tr) < rqs.N_FLOOR:
        return None
    pnl = tr['pnl_pip'].values
    wins = int((pnl > 0).sum())
    n = len(pnl)
    wr = wins / n * 100.0
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    pf = gains / losses if losses > 0 else 999.0
    if wr < wr_min or pf < pf_min:
        return None
    return dict(n=n, wr=wr, pf=pf)


def scan(asset, tf, verbose=False, budget=None):
    df = load(asset, tf)
    feat = build_features(df, asset)
    atr = feat['atr']
    c = feat['c']
    pip = se.ASSETS[asset]['pip']
    n = feat['n']
    atr_pip = np.where(atr > 0, atr / pip, np.nan)

    best = None
    # گریدِ فیلترهای کیفیت (غیر-رند جایی که معنا دارد)
    grid_kbody  = [1.6, 2.0, 2.5]        # قدرتِ کلایمکس (× میانگینِ بدنه)
    grid_brmin  = [0.0, 0.45, 0.6]       # نسبتِ بدنه/دامنه
    grid_streak = [0, 2, 3]              # طولِ رگهٔ نزولیِ منتهی
    grid_rsi    = [None, 42, 35, 30]
    grid_regime = [None, 'below', 'bb', 'trend']
    # SL/TP نامتقارنِ *غیر-رند* (TP<SL برای WR-بالا) — به pip از ATR
    grid_sltp   = [(2.4, 0.8), (2.8, 1.0), (3.1, 1.15), (2.0, 0.7), (3.5, 1.3)]
    grid_hold   = [16, 24, 48]

    evals = 0
    rqs_calls = 0
    t0 = time.time()
    short_sig = np.zeros(n, dtype=bool)
    for k_body, br_min, streak_n, rsi_lo, regime in itertools.product(
            grid_kbody, grid_brmin, grid_streak, grid_rsi, grid_regime):
        sig = make_signals(feat, k_body, br_min, streak_n, rsi_lo, regime, atr, c)
        valid_sig = sig & np.isfinite(atr_pip) & (atr_pip > 0)
        if valid_sig.sum() < 30:
            continue
        for (sl_m, tp_m), hold in itertools.product(grid_sltp, grid_hold):
            if budget and (time.time() - t0) > budget:
                if verbose:
                    print(f"  [{asset} {tf}] BUDGET HIT after {evals} evals")
                return best, evals
            sl_pip = np.where(np.isfinite(atr_pip), sl_m * atr_pip, 1.0)
            tp_pip = np.where(np.isfinite(atr_pip), tp_m * atr_pip, 1.0)
            tr = se.simulate_trades(df, valid_sig, short_sig,
                                    sl_pip, tp_pip, asset,
                                    max_hold=hold, allow_overlap=False)
            evals += 1
            pre = _cheap_prefilter(tr, asset)
            if pre is None:
                continue
            r = rqs.compute_rqs(tr, asset)
            rqs_calls += 1
            score = r['rqs_score']
            cfg = dict(k_body=k_body, br_min=br_min, streak_n=streak_n,
                       rsi_lo=rsi_lo, regime=regime, sl_m=sl_m, tp_m=tp_m, hold=hold)
            if best is None or score > best[0]:
                best = (score, r, cfg)
                if verbose and r['passed']:
                    print(f"  [{asset} {tf}] {rqs.format_report('S327', r)}  cfg={cfg}")
    if verbose:
        print(f"  [{asset} {tf}] evals={evals} rqs_calls={rqs_calls} ({time.time()-t0:.1f}s)")
    return best, evals


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default=None, help='e.g. XAUUSD_M5')
    ap.add_argument('--budget', type=float, default=None, help='seconds per TF')
    args = ap.parse_args()

    t0 = time.time()
    print("=" * 100)
    print("S327 — احیای S174 Sell-Climax Reversal با RQS+ | مولتی‌تایم‌فریم (از XAUUSD M5)")
    print("=" * 100)
    results = {}
    pairs = []
    for asset in ['XAUUSD', 'EURUSD']:
        for tf in DATA[asset]:
            pairs.append((asset, tf))
    if args.only:
        pairs = [tuple(args.only.split('_')) if False else
                 (args.only.rsplit('_', 1)[0], args.only.rsplit('_', 1)[1])]

    for asset, tf in pairs:
        key = f"{asset}_{tf}"
        best, evals = scan(asset, tf, verbose=True, budget=args.budget)
        results[key] = best
        if best is None:
            print(f"{key:14s} | NO CANDIDATE  [{evals} evals]")
        else:
            score, r, cfg = best
            print(f"{key:14s} | {rqs.format_report('best', r)}")
            print(f"{'':14s}   cfg={cfg}  [{evals} evals]")

    print("-" * 100)
    print(f"⏱ total {time.time()-t0:.1f}s")
    print("\n=== لایه‌های گیت-پاسِ RQS+≥80 ===")
    any_pass = False
    for k, b in results.items():
        if b and b[1]['passed'] and b[0] >= 80:
            any_pass = True
            print(f"  ✅ {k}: RQS+={b[0]}  cfg={b[2]}")
    if not any_pass:
        print("  (هیچ ترکیبی هنوز RQS+≥80 نداد — نیاز به بهبودِ بیشتر یا DEAD)")
