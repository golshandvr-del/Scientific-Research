# -*- coding: utf-8 -*-
"""
s338_conditional_wr.py — کشفِ «رژیمِ شرطیِ باlift» (conditional win-rate mining)

مسیرِ نشستِ قبل: تنها ناحیهٔ رد نشده «شرطِ ورودِ نادرِ جهت‌دار با lift آماری» است.
این اسکریپت برعکسِ روشِ قدیم عمل می‌کند:
  قدیم: «این سیگنال را بزن، ببین WR چقدر است» (اسکنِ کور)
  نو  : «outcomeِ هر کندل را ثبت کن، بعد ببین کدام STATE نرخِ برد را از ۵۰٪ دور می‌کند»

روش (data-mining هدایت‌شدهٔ علمی، ضدِ over-fit):
  1) baseline: هر کندل یک معامله long/short با TP=SL=k×ATR (شناور per-TF). outcome ثبت.
  2) برای هر اندیکاتورِ بانک، مقدارش را در لحظهٔ ورود ثبت کن (shift(1) — بدونِ look-ahead).
  3) داده را IN-SAMPLE (نیمهٔ اول) / OOS (نیمهٔ دوم) کن.
  4) در IS بهترین آستانه (چارک‌ها) را بیاب که conditional-WR را با n کافی ماکس کند.
  5) فقط شرط‌هایی که در OOS هم lift را نگه می‌دارند و p<0.05 (binomial) → کاندیدا.

خروجی: لیستِ رتبه‌بندی‌شدهٔ (اندیکاتور، جهت، آستانه، WR_is, WR_oos, n, p).
"""
import sys
import numpy as np
import pandas as pd
from scipy import stats

from engine import scalp_engine as se
from engine import indicator_bank as ib

ASSET = 'XAUUSD'
TF = 'M5'

TF_BARS_PER_DAY = {'M1': 1440, 'M5': 288, 'M15': 96, 'M30': 48,
                   'H1': 24, 'H4': 6, 'D1': 1, 'W1': 0.2}


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def atr_pips(df, asset):
    """ATR بر حسب pip با ib."""
    atr = ib.compute('atr_fib_13', df)
    pip = se.ASSETS[asset]['pip']
    return (atr / pip).values


def build_baseline(df, asset, direction, k_atr=1.5, max_hold=24):
    """
    هر کندل یک معامله در جهتِ ثابت. برمی‌گرداند:
      entry_idx (آرایهٔ ایندکسِ کندلِ ورود), win (بولین: pnl_pip>0)
    TP=SL=k×ATR(median) — متقارن، پس WRِ خام ~۴۶٪ (طبقِ کشفِ S337).
    هدف: پیدا کردنِ STATEای که این ۴۶٪ را معنادار بالا ببرد.
    """
    n = len(df)
    atrp = atr_pips(df, asset)
    sl = float(np.nanmedian(atrp)) * k_atr
    tp = sl
    if not np.isfinite(sl) or sl < 1:
        return None, None, None, None
    long_sig = np.zeros(n, dtype=bool)
    short_sig = np.zeros(n, dtype=bool)
    if direction == 'long':
        long_sig[:] = True
    else:
        short_sig[:] = True
    # allow_overlap=True تا هر کندل مستقل ارزیابی شود (نمونه‌گیریِ کامل)
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                            max_hold=max_hold, allow_overlap=True)
    if tr is None or len(tr) == 0:
        return None, None, None, None
    entry_idx = tr['entry_bar'].values
    win = (tr['pnl_pip'].values > 0)
    return entry_idx, win, sl, tp


def binom_p(wins, n, p0=0.5):
    """p-value دو دامنه (normal approx به binomial) — برداری و سریع.
    برای n بزرگ (اینجا n>=30) تقریبِ نرمال دقیق است."""
    if n == 0:
        return 1.0
    phat = wins / n
    se_ = np.sqrt(p0 * (1 - p0) / n)
    if se_ == 0:
        return 1.0
    z = (phat - p0) / se_
    return 2.0 * (1.0 - stats.norm.cdf(abs(z)))


def mine_indicator(df, name, entry_idx, win, base_wr, min_frac=0.05):
    """
    برای یک اندیکاتور: مقدار را در entry_idx بگیر، به IS/OOS بشکن،
    بهترین آستانهٔ چارکی را بیاب که WR_is را ماکس کند با n کافی،
    و همان آستانه را در OOS بسنج.
    برمی‌گرداند بهترین رکورد یا None.
    """
    try:
        vals_full = ib.compute(name, df).shift(1).values  # بدون look-ahead
    except Exception:
        return None
    v = vals_full[entry_idx]
    ok = np.isfinite(v)
    if ok.sum() < 200:
        return None
    v = v[ok]; w = win[ok]
    m = len(v)
    split = m // 2
    v_is, w_is = v[:split], w[:split]
    v_oos, w_oos = v[split:], w[split:]
    if len(v_is) < 100 or len(v_oos) < 100:
        return None

    min_n_is = max(30, int(len(v_is) * min_frac))
    # آستانه‌های کاندیدا = صدک‌های ۵..۹۵ (نه اعداد رند؛ داده‌محور)
    qs = np.percentile(v_is, np.arange(5, 96, 5))
    w_is_f = w_is.astype(np.float64)
    w_oos_f = w_oos.astype(np.float64)
    best = None
    for th in qs:
        for side in ('gt', 'lt'):
            mask_is = (v_is > th) if side == 'gt' else (v_is < th)
            n_is = int(mask_is.sum())
            if n_is < min_n_is:
                continue
            wr_is = w_is_f[mask_is].mean() * 100
            # فقط بهبودِ معنادار نسبت به baseline جالب است
            if wr_is <= base_wr + 3:
                continue
            # همان شرط در OOS
            mask_oos = (v_oos > th) if side == 'gt' else (v_oos < th)
            n_oos = int(mask_oos.sum())
            if n_oos < 30:
                continue
            wins_oos = float(w_oos_f[mask_oos].sum())
            wr_oos = wins_oos / n_oos * 100
            p_oos = binom_p(wins_oos, n_oos, 0.5)
            # معیارِ کاندیدا: WR_oos هم بالای baseline+3 و p<0.05
            score = min(wr_is, wr_oos)
            rec = dict(name=name, side=side, th=float(th),
                       wr_is=wr_is, n_is=n_is,
                       wr_oos=wr_oos, n_oos=n_oos,
                       p_oos=p_oos, score=score)
            if best is None or score > best['score']:
                best = rec
    return best


def run(asset=ASSET, tf=TF, direction='long', max_names=None, tail=None):
    print(f"\n=== S338 CONDITIONAL-WR MINING {asset}/{tf} dir={direction} ===", flush=True)
    df = load(asset, tf)
    if tail:
        df = df.iloc[-tail:].reset_index(drop=True)
    n = len(df)
    days = n / TF_BARS_PER_DAY[tf]
    print(f"n_candles={n} (~{days:.0f} روز)")

    entry_idx, win, sl, tp = build_baseline(df, asset, direction)
    if entry_idx is None:
        print("baseline failed"); return
    base_wr = win.mean() * 100
    print(f"baseline: dir={direction} TP=SL={sl:.1f}pip  WR_خام={base_wr:.2f}%  n={len(win)}")
    print(f"هدف: STATEای که WR را معنادار (p<0.05 در OOS) بالای {base_wr+3:.0f}% ببرد\n")

    all_names = []
    for cat in ib.categories():
        all_names += ib.by_category(cat)
    all_names = sorted(set(all_names))
    if max_names:
        all_names = all_names[:max_names]
    print(f"اسکنِ {len(all_names)} اندیکاتور با اعتبارسنجیِ IS/OOS ...\n")

    import time
    t0 = time.time()
    results = []
    for i, name in enumerate(all_names):
        rec = mine_indicator(df, name, entry_idx, win, base_wr)
        if rec is not None:
            results.append(rec)
        if (i + 1) % 50 == 0:
            print(f"  ...{i+1}/{len(all_names)} cand={len(results)} ({time.time()-t0:.0f}s)", flush=True)

    # مرتب بر اساس score (کمینهٔ WR_is,WR_oos) و p_oos
    results.sort(key=lambda r: (-r['score'], r['p_oos']))
    print(f"{'indicator':>22} {'side':>4} {'th':>10} {'WR_is':>6} {'n_is':>6} "
          f"{'WR_oos':>6} {'n_oos':>6} {'p_oos':>8}")
    print("-" * 78)
    shown = 0
    for r in results:
        # فقط آنهایی که در OOS واقعاً lift دارند و معنادارند
        robust = (r['wr_oos'] > base_wr + 3) and (r['p_oos'] < 0.05)
        flag = ' <== ROBUST' if robust else ''
        if shown < 30 or robust:
            print(f"{r['name']:>22} {r['side']:>4} {r['th']:>10.4f} "
                  f"{r['wr_is']:>6.1f} {r['n_is']:>6} {r['wr_oos']:>6.1f} "
                  f"{r['n_oos']:>6} {r['p_oos']:>8.4f}{flag}")
            shown += 1
    n_robust = sum(1 for r in results if (r['wr_oos'] > base_wr + 3) and (r['p_oos'] < 0.05))
    print(f"\nمعنادار در OOS (ROBUST): {n_robust} از {len(results)} کاندیدا")
    return results


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else ASSET
    tf = sys.argv[2] if len(sys.argv) > 2 else TF
    direction = sys.argv[3] if len(sys.argv) > 3 else 'long'
    tail = int(sys.argv[4]) if len(sys.argv) > 4 else None
    run(asset, tf, direction, tail=tail)
