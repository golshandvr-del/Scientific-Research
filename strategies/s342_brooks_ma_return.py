# -*- coding: utf-8 -*-
"""
S342 — Al Brooks «Example of How to Trade a Trend» (فصلِ ۱۸، آغازِ Part III)
================================================================================
پارادایم: RQS+ ≥ ۸۰ (نه net-profit قدیمی). سند: docs/RQS_ROBUST_QUALITY_SCORE.md

تز (نقلِ مکانیکیِ Brooks، فصل ۱۸ — «قاعدهٔ ۵»، تنها لبهٔ نو/مکانیکیِ فصل):
- «در روندِ صعودیِ برقرار که بازار برای ≥N کندل به میانگینِ متحرک pullback نکرده،
   اولین بازگشت به MA یک limit-buy با-روند است؛ خروج روی testِ سقفِ اخیر.»
- یعنی: کش‌آمدگیِ طولانی از MA ⇒ MA به‌مثابهِ مغناطیس ⇒ بازگشتِ محتمل به MA و سپس
   ادامهٔ روند (mean-reversion-within-trend، نه ضدِ روند).
- قرینهٔ کامل در روندِ نزولی (SHORT).

منطقِ مکانیکی (causal، بدونِ look-ahead؛ سیگنال روی کندلِ i، ورود در open کندلِ i+1):
  LONG (بازگشت به MA در روندِ صعودی):
    1) روندِ صعودی برقرار: MA شیبِ صعودی دارد و رژیمِ روندی فعال است (r2 بالا / hurst>0.5).
    2) «دوریِ طولانی»: close برای حداقل N کندلِ متوالیِ گذشته اکیداً بالای MA بوده
       (run_above[i-1] >= N) — یعنی هیچ pullback‌ی به MA در N کندلِ اخیر نبوده.
    3) «اولین لمسِ MA»: در کندلِ i، low[i] <= MA[i]  (بازار برای اولین‌بار MA را لمس کرد).
  SHORT قرینهٔ کامل (روندِ نزولی، close زیرِ MA برای ≥N کندل، سپس high[i] >= MA[i]).

هدفِ RQS+: چون این یک ورودِ «pullback در روند» است، فیلترِ رژیمِ روند (r2/hurst) و
TP=با-روند (test-of-high) کلیدِ عبور از گیت‌هاست. N و MAدوره غیررند و per-TF (اشتباه #۷/#۶).
"""
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicator_bank as ib


# ---------------------------------------------------------------------------
def _run_length_above(c, ma):
    """طولِ رشتهٔ متوالیِ close > ma تا (و شاملِ) هر کندل. خروجی هم‌طولِ c."""
    n = len(c)
    run = np.zeros(n, dtype=int)
    r = 0
    for i in range(n):
        if np.isfinite(ma[i]) and c[i] > ma[i]:
            r += 1
        else:
            r = 0
        run[i] = r
    return run


def _run_length_below(c, ma):
    """طولِ رشتهٔ متوالیِ close < ma تا (و شاملِ) هر کندل."""
    n = len(c)
    run = np.zeros(n, dtype=int)
    r = 0
    for i in range(n):
        if np.isfinite(ma[i]) and c[i] < ma[i]:
            r += 1
        else:
            r = 0
        run[i] = r
    return run


def _trend_regime(df, r2_min, hurst_min, r2_p, hurst_p):
    """ماسکِ بولینِ رژیمِ روند (بدونِ look-ahead). r2 بالا و/یا hurst>0.5 = روندی."""
    mask = np.ones(len(df), dtype=bool)
    if r2_min is not None:
        r2 = ib.r2(df, p=r2_p).to_numpy()
        mask &= (r2 >= r2_min) & np.isfinite(r2)
    if hurst_min is not None:
        hu = ib.hurst(df, p=hurst_p).to_numpy()
        mask &= (hu >= hurst_min) & np.isfinite(hu)
    return mask


def ma_return_signals(df, side, ma_period=34, ma_kind='ema', n_away=13,
                      slope_lb=5, r2_min=None, hurst_min=None,
                      r2_p=21, hurst_p=55):
    """
    خروجی: آرایهٔ بولین هم‌طولِ df؛ True = سیگنالِ ورود روی این کندل (ورود در i+1).

    side='long'  ⇒ روندِ صعودی، ≥n_away کندل بالای MA، سپس اولین لمسِ MA از بالا.
    side='short' ⇒ روندِ نزولی، ≥n_away کندل زیرِ MA،  سپس اولین لمسِ MA از پایین.
    ma_kind      ⇒ 'ema' یا 'sma'.
    slope_lb     ⇒ پنجرهٔ سنجشِ شیبِ MA (MA[i] vs MA[i-slope_lb]) برای تأییدِ جهتِ روند.
    r2_min/hurst_min ⇒ فیلترِ رژیمِ روند (اختیاری، برای بالا بردنِ RQS+).
    """
    c = df['close'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    x = ib._c(df)
    ma = (ib.ema_s(x, ma_period) if ma_kind == 'ema'
          else ib.sma_s(x, ma_period)).to_numpy(float)
    n = len(df)

    reg = _trend_regime(df, r2_min, hurst_min, r2_p, hurst_p)

    if side == 'long':
        run = _run_length_above(c, ma)
    else:
        run = _run_length_below(c, ma)

    sig = np.zeros(n, dtype=bool)
    start = max(ma_period + slope_lb + 2, 2)
    for i in range(start, n):
        if not reg[i]:
            continue
        if not (np.isfinite(ma[i]) and np.isfinite(ma[i - slope_lb])):
            continue

        if side == 'long':
            # شیبِ MA صعودی (روندِ صعودیِ برقرار)
            if ma[i] <= ma[i - slope_lb]:
                continue
            # «دوریِ طولانی»: کندلِ قبلی حداقل n_away کندلِ متوالی بالای MA بوده
            if run[i - 1] < n_away:
                continue
            # «اولین لمسِ MA»: این کندل MA را از بالا لمس کرد (pullback)
            if l[i] <= ma[i] and c[i - 1] > ma[i - 1]:
                sig[i] = True
        else:
            if ma[i] >= ma[i - slope_lb]:
                continue
            if run[i - 1] < n_away:
                continue
            if h[i] >= ma[i] and c[i - 1] < ma[i - 1]:
                sig[i] = True

    return sig


# ---------------------------------------------------------------------------
def load_tf(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


if __name__ == '__main__':
    from engine import rqs
    # تستِ دود روی XAUUSD M5 (شروعِ اجباری از M پایین)
    df = load_tf('XAUUSD', 'M5')
    for side in ('long', 'short'):
        s = ma_return_signals(df, side, ma_period=34, ma_kind='ema',
                              n_away=13, slope_lb=5,
                              r2_min=0.25, hurst_min=0.52)
        long_sig = s if side == 'long' else np.zeros(len(df), bool)
        short_sig = s if side == 'short' else np.zeros(len(df), bool)
        tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=180, tp_pip=270,
                                asset='XAUUSD', max_hold=48, allow_overlap=False)
        r = rqs.compute_rqs(tr, 'XAUUSD', sl_pip=180, tp_pip=270)
        print(rqs.format_report(f'S342_XAU_M5_{side}', r))
