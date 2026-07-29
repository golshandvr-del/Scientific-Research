# -*- coding: utf-8 -*-
"""
S345 — Al Brooks «Reversal Day» (فصلِ ۲۴، Part IV)
================================================================================
پارادایم: RQS+ ≥ ۸۰ (نه net-profit قدیمی). سند: docs/RQS_ROBUST_QUALITY_SCORE.md
منبع: کتاب `1 Trading Price Action - Trends.pdf`، فصلِ ۲۴ (pdf idx 446–453).

تز (نقلِ مکانیکیِ Brooks، فصل ۲۴):
- «The day trends in one direction and then it trends in the opposite direction
   into the close.» ⇒ چرخشِ درون-روزیِ روند.
- «There is almost always at least one countertrend spike before the [reverse]
   channel begins.» ⇒ اسپایکِ ضدِ‌روندِ قوی = ماشهٔ چرخش.
- «The pullback to bar 5 broke the bull trend line, and the bar 6 lower high set
   the stage for a bear trend day into the close.» ⇒ تأییدِ ساختاری:
   شکستِ خطِ روندِ اولیه + lower-high (روزِ صعودی→نزولی) / higher-low (نزولی→صعودی).
- «If the reversal starts in the last couple of hours and is strong, it will
   usually have follow-through.» ⇒ چرخشِ اواخرِ روز پایدارتر (فیلترِ زمان).

منطقِ مکانیکی (causal، بدونِ look-ahead؛ سیگنال روی کندلِ i، ورود در open کندلِ i+1):
  برای هر روزِ معاملاتی (مرزِ UTC date):
    1) جهتِ روندِ اولیهٔ روز از N کندلِ نخست: initTrend = sign(close[N-1] - open[0]).
       اکسترممِ روز تا لحظهٔ جاری = بالاترین high (روزِ صعودی) / پایین‌ترین low (نزولی).
    2) خطِ روندِ اولیه = رگرسیونِ ساده روی close از آغازِ روز تا کندلِ جاری (شیب).
       روندِ اولیهٔ صعودی ⇒ شیبِ مثبتِ معنادار.
    3) ⭐ ماشهٔ چرخش (SHORT در روزِ صعودی‌شونده→نزولی):
       - countertrend spike: کندلِ نزولیِ اخیر با بدنهٔ |close-open| ≥ k × ATR.
       - شکستِ خطِ روندِ صعودی: close < trendline(t).
       - lower-high: high کندلِ اخیر < اکسترممِ روز (سقف زده و برنگشته).
       ⇒ SHORT تا close. قرینهٔ کامل برای LONG در روزِ نزولی‌شونده→صعودی.
    4) فیلترِ زمان: ورود فقط در پنجرهٔ میانه/اواخرِ روز
       (t_from .. t_to از bars_per_day) — نه در opening range.

بهبود «همه‌چیز شناور»: N, k, پنجرهٔ زمانی، آستانهٔ شیب، SL/TP همه per-TF و غیررند.
"""
import numpy as np
import pandas as pd

from engine import scalp_engine as se
# بازاستفادهٔ helperهای روز/ADR از S344 (verbatim — تضمینِ سازگاری)
from strategies.s344_brooks_trend_from_open import _bars_per_day, _daily_atr_from_intraday


def _atr(df, p=14):
    """ATR ساده (Wilder-approx، causal)."""
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)
    tr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr = np.full(n, np.nan)
    if n >= p:
        atr[p - 1] = tr[:p].mean()
        for i in range(p, n):
            atr[i] = (atr[i - 1] * (p - 1) + tr[i]) / p
    return atr


def reversal_day_signals(df, tf, side,
                         n_open=6, k_spike=1.0, slope_min_frac=0.10,
                         entry_from_frac=0.30, entry_to_frac=0.90,
                         adr_lb=14, atr_p=14):
    """
    سیگنالِ «reversal day / intraday trend flip».

    df    : دیتافریمِ intraday یک TF.
    tf    : نامِ تایم‌فریم.
    side  : 'long'  = روزِ نزولی‌شونده→صعودی (چرخش رو به بالا)
            'short' = روزِ صعودی‌شونده→نزولی (چرخش رو به پایین)
    n_open        : تعدادِ کندلِ opening-range (برای تعیینِ جهتِ روندِ اولیه).
    k_spike       : ضریبِ ATR برای «countertrend spike» (بدنهٔ اسپایک ≥ k×ATR).
    slope_min_frac: حداقلِ شیبِ روندِ اولیه (بر حسبِ کسری از ATR در هر کندل) تا
                    «روندِ اولیهٔ واقعی» شمرده شود.
    entry_from_frac/entry_to_frac : پنجرهٔ ورود درونِ روز (کسری از bars_per_day).
    adr_lb        : تعدادِ روزِ ADR.
    atr_p         : دورهٔ ATR.

    خروجی: آرایهٔ بولین هم‌طولِ df (True = ماشهٔ چرخشِ همین کندل ⇒ ورود در i+1).
    """
    n = len(df)
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    dt = pd.to_datetime(df['time'], unit='s')
    day_id = dt.dt.floor('D').astype('int64').to_numpy()

    bpd = _bars_per_day(tf)
    atr = _atr(df, atr_p)
    adr = _daily_atr_from_intraday(df, day_id, adr_lb)

    t_from = max(n_open, int(entry_from_frac * bpd))
    t_to = int(entry_to_frac * bpd)

    sig = np.zeros(n, dtype=bool)

    # پیمایشِ روزها
    i = 0
    while i < n:
        d = day_id[i]
        j0 = i
        j = i
        while j < n and day_id[j] == d:
            j += 1
        # کندل‌های روز: [j0, j)
        day_len = j - j0
        if day_len <= n_open + 2:
            i = j
            continue

        # جهتِ روندِ اولیهٔ روز از N کندلِ نخست
        open0 = o[j0]
        close_n = c[j0 + n_open - 1]
        atr_ref = atr[j0 + n_open - 1]
        if not np.isfinite(atr_ref) or atr_ref <= 0:
            i = j
            continue
        init_dir = np.sign(close_n - open0)  # +1 صعودی، -1 نزولی

        # side='short' نیاز به روندِ اولیهٔ صعودی دارد (تا رو به پایین بچرخد)
        # side='long'  نیاز به روندِ اولیهٔ نزولی دارد (تا رو به بالا بچرخد)
        need_init = +1.0 if side == 'short' else -1.0
        if init_dir != need_init:
            i = j
            continue

        # اکسترممِ روز (running) و شیبِ روندِ اولیه
        for pos in range(t_from, min(day_len, t_to + 1)):
            t = j0 + pos
            if t + 1 >= n:  # نیاز به کندلِ بعد برای ورود
                break
            # پنجرهٔ روز تا کنون
            seg_c = c[j0:t + 1]
            m = len(seg_c)
            if m < n_open + 2:
                continue
            # شیبِ روندِ اولیه (رگرسیونِ خطیِ close روی زمان)
            xs = np.arange(m, dtype=float)
            slope = np.polyfit(xs, seg_c, 1)[0]  # قیمت/کندل
            slope_norm = slope / atr_ref
            # روندِ اولیه باید در جهتِ init_dir و معنادار باشد
            if init_dir > 0 and slope_norm < slope_min_frac:
                continue
            if init_dir < 0 and slope_norm > -slope_min_frac:
                continue

            body = abs(c[t] - o[t])
            atr_t = atr[t] if np.isfinite(atr[t]) and atr[t] > 0 else atr_ref

            if side == 'short':
                # روزِ صعودی‌شونده→نزولی
                day_high = np.max(h[j0:t + 1])
                # خطِ روندِ صعودی (امتدادِ رگرسیون تا t)
                line_t = np.polyval(np.polyfit(xs, seg_c, 1), m - 1)
                # ماشه: countertrend bear spike + شکستِ خط + lower-high
                bear_spike = (c[t] < o[t]) and (body >= k_spike * atr_t)
                broke_line = c[t] < line_t
                lower_high = h[t] < day_high  # سقفِ روز زده شده و این کندل زیرِ آن
                if bear_spike and broke_line and lower_high:
                    sig[t] = True
            else:
                # روزِ نزولی‌شونده→صعودی
                day_low = np.min(l[j0:t + 1])
                line_t = np.polyval(np.polyfit(xs, seg_c, 1), m - 1)
                bull_spike = (c[t] > o[t]) and (body >= k_spike * atr_t)
                broke_line = c[t] > line_t
                higher_low = l[t] > day_low
                if bull_spike and broke_line and higher_low:
                    sig[t] = True
        i = j

    return sig


def load_tf(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


if __name__ == '__main__':
    from engine import rqs
    df = load_tf('XAUUSD', 'M5')
    for side in ('long', 'short'):
        s = reversal_day_signals(df, 'M5', side, n_open=6, k_spike=1.0)
        long_sig = s if side == 'long' else np.zeros(len(df), bool)
        short_sig = s if side == 'short' else np.zeros(len(df), bool)
        tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=150, tp_pip=225,
                                asset='XAUUSD', max_hold=48, allow_overlap=False)
        r = rqs.compute_rqs(tr, 'XAUUSD', sl_pip=150, tp_pip=225)
        print(f"{side}: n={s.sum()} trades={0 if tr is None else len(tr)} "
              f"RQS={r['rqs_score']:.1f} {'ACC' if r['passed'] else 'rej'}")
