# -*- coding: utf-8 -*-
"""
S211 — بررسیِ علمیِ ادعای تریدر: واکنشِ قیمت به سه SMA (8/70/240)
================================================================================
User Note (این نشست): تریدری ادعا کرد با ترکیبِ سه SMA با دوره‌های 8/70/240
معامله می‌کند و مدعی است چارت «در تایم‌فریم‌های مختلف» به این خطوط واکنش نشان
می‌دهد (به‌صورتِ بصری).

مرحلهٔ ۱ (این فایل): آزمونِ *آماریِ* ادعا — نه بصری.

روش‌شناسی (بدونِ look-ahead):
  «واکنش/bounce» را این‌گونه تعریف می‌کنیم: هرگاه low(bar) به SMA نزدیک شود
  (touch: |low−sma|/atr < tol و low ≤ sma ≤ high یا low کمی زیرِ sma)، آیا در
  N کندلِ بعد قیمت از SMA به بالا برمی‌گردد (برای supportِ صعودی) به‌طور معنی‌دار
  بیشتر از حالتِ پایه (base-rate)؟

  آزمونِ نول (H0): touchِ SMA هیچ اطلاعاتی ندارد ⇒ نرخِ bounce ≈ نرخِ پایهٔ
  حرکتِ رو-به-بالا در همان افق. اگر نرخِ bounce پس از touch به‌طور معنی‌دار
  (z-test دو-نسبتی) بالاتر از base-rate باشد ⇒ ادعا شواهدِ آماری دارد.

خروجی برای هر تایم‌فریم و هر SMA:
  - تعداد touch، نرخِ bounce (up)، base-rate، اختلاف، z و p-value.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.indicators import sma, atr


def load(path):
    df = pd.read_csv(path)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def two_prop_ztest(x1, n1, x2, n2):
    """z-test برای اختلافِ دو نسبت (p1=touch-bounce, p2=base-rate)."""
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0
    p1 = x1 / n1
    p2 = x2 / n2
    p = (x1 + x2) / (n1 + n2)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    # p-value یک‌طرفه (p1>p2)
    from math import erf, sqrt
    p_one = 0.5 * (1 - erf(z / sqrt(2)))
    return z, p_one


def analyze_reaction(df, period, horizon, tol_atr=0.15, lookahead_touch_dir='support'):
    """
    period       : دورهٔ SMA
    horizon      : افقِ بررسیِ واکنش (تعداد کندلِ بعد)
    tol_atr      : آستانهٔ نزدیکی به SMA بر حسبِ ATR (کسری از ATR)
    lookahead_touch_dir: 'support' = لمس از بالا (low نزدیکِ sma) و انتظارِ bounce صعودی
    """
    c = df['close'].values.astype(float)
    h = df['high'].values.astype(float)
    l = df['low'].values.astype(float)
    s = sma(df['close'], period).values
    a = atr(df, 14).values
    n = len(df)

    touch_idx = []
    for i in range(period + 14, n - horizon):
        if np.isnan(s[i]) or np.isnan(a[i]) or a[i] <= 0:
            continue
        # support-touch: کندل به SMA از بالا نزدیک شده (SMA زیرِ close، low آن را لمس کرده)
        if lookahead_touch_dir == 'support':
            near = (l[i] <= s[i] + tol_atr * a[i]) and (l[i] >= s[i] - tol_atr * a[i]) and (c[i] >= s[i] - tol_atr * a[i])
            if near:
                touch_idx.append(i)

    # نرخِ bounce پس از touch: close در افق به بالای close فعلی + 0.25*ATR برسد
    bounce = 0
    for i in touch_idx:
        target = c[i] + 0.25 * a[i]
        fut_hi = h[i + 1:i + 1 + horizon].max() if i + 1 + horizon <= n else h[i + 1:].max()
        if fut_hi >= target:
            bounce += 1

    # base-rate: روی همهٔ کندل‌ها (نه فقط touch)، نرخِ رسیدن به close+0.25*ATR در افق
    base_hit = 0
    base_tot = 0
    step = max(1, len(range(period + 14, n - horizon)) // 20000 + 1)  # نمونه‌گیری برای سرعت
    for i in range(period + 14, n - horizon, step):
        if np.isnan(a[i]) or a[i] <= 0:
            continue
        target = c[i] + 0.25 * a[i]
        fut_hi = h[i + 1:i + 1 + horizon].max()
        base_tot += 1
        if fut_hi >= target:
            base_hit += 1

    n_touch = len(touch_idx)
    p_bounce = bounce / n_touch if n_touch else 0.0
    p_base = base_hit / base_tot if base_tot else 0.0
    z, pval = two_prop_ztest(bounce, n_touch, base_hit, base_tot)
    return dict(period=period, horizon=horizon, n_touch=n_touch, bounce=bounce,
                p_bounce=round(p_bounce, 4), p_base=round(p_base, 4),
                edge=round(p_bounce - p_base, 4), z=round(z, 2), pval=round(pval, 5))


def main():
    tfs = ['M5', 'M15', 'M30', 'H1', 'H4', 'D1']
    periods = [8, 70, 240]
    # افقِ واکنش متناسب با TF (حدوداً معادلِ زمانِ ثابت)
    horizon_map = {'M5': 12, 'M15': 8, 'M30': 6, 'H1': 5, 'H4': 4, 'D1': 3}

    print("=" * 96)
    print("S211 — آزمونِ آماریِ ادعای واکنشِ قیمت به سه SMA (8/70/240) — XAUUSD همه تایم‌فریم‌ها")
    print("=" * 96)
    print(f"{'TF':>4} {'SMA':>5} {'horizon':>7} {'n_touch':>8} {'p_bounce':>9} {'p_base':>8} {'edge':>7} {'z':>7} {'pval':>8}  verdict")
    print("-" * 96)

    all_rows = []
    for tf in tfs:
        path = f'data/XAUUSD_{tf}.csv'
        if not os.path.exists(path):
            continue
        df = load(path)
        hz = horizon_map[tf]
        for p in periods:
            r = analyze_reaction(df, p, hz)
            r['tf'] = tf
            all_rows.append(r)
            verdict = ""
            if r['pval'] < 0.01 and r['edge'] > 0.02:
                verdict = "✅ معنی‌دار (ادعا تأیید)"
            elif r['pval'] < 0.05 and r['edge'] > 0.0:
                verdict = "◐ ضعیف"
            else:
                verdict = "✗ بی‌اثر"
            print(f"{tf:>4} {p:>5} {hz:>7} {r['n_touch']:>8} {r['p_bounce']:>9} {r['p_base']:>8} "
                  f"{r['edge']:>+7.4f} {r['z']:>7.2f} {r['pval']:>8.5f}  {verdict}")
        print("-" * 96)

    # ذخیرهٔ JSON
    import json
    os.makedirs('results', exist_ok=True)
    with open('results/_s211_triple_sma_reaction.json', 'w') as f:
        json.dump(all_rows, f, indent=2)
    print("saved: results/_s211_triple_sma_reaction.json")


if __name__ == '__main__':
    main()
