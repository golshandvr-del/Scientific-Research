# -*- coding: utf-8 -*-
"""
S344 — Al Brooks «Trend from the Open & Small Pullback Trends» (فصلِ ۲۳، Part IV)
================================================================================
پارادایم: RQS+ ≥ ۸۰ (نه net-profit قدیمی). سند: docs/RQS_ROBUST_QUALITY_SCORE.md
منبع: کتاب `1 Trading Price Action - Trends.pdf`، فصلِ ۲۳ (pdf idx 414–444).

تز (نقلِ مکانیکیِ Brooks، فصل ۲۳):
- «کفِ روزِ صعودی / سقفِ روزِ نزولی در چند کندلِ نخستِ روز شکل می‌گیرد.»
- «اگر opening range < 25% × ADR (رنجِ اولیهٔ کوچک) و اسپایکِ اولیه ۳+ کندل هم‌جهت
   بماند ⇒ روزِ روندیِ قوی.»
- ⭐ تزِ مرکزیِ معامله‌ای: «ورود در اولین pullbackِ کوچکِ با-روند» (continuation).
- «most strong moves have at least two legs ⇒ entering on the first pullback has a
   very good chance of leading to a profitable trade.»
- قرینهٔ کامل در روزِ نزولی (SHORT).

منطقِ مکانیکی (causal، بدونِ look-ahead؛ سیگنال روی کندلِ i، ورود در open کندلِ i+1):
  برای هر روزِ معاملاتی (مرزِ UTC date):
    1) opening-range از N کندلِ نخستِ روز: initR = max(high₁..ₙ) − min(low₁..ₙ)،
       initHi=max(high), initLo=min(low).
    2) فیلترِ رژیمِ trend-from-open: initR < f × ADR  (رنجِ اولیهٔ کوچک).
    3) جهتِ اسپایکِ اولیه: close کندلِ N-ام نسبت به open کندلِ ۱ روز
       (bull اگر بالاتر، bear اگر پایین‌تر) + شکستِ لبهٔ opening-range.
    4) ⭐ اولین pullback: پس از breakoutِ opening-range در جهتِ اسپایک، اولین بازگشتِ
       کوچک (که کمتر از pull_max × leg برمی‌گردد) و سپس یک کندلِ هم‌جهتِ تأیید
       (high1/low1 = شکستِ high/low کندلِ قبل) ⇒ سیگنالِ ورودِ با-روند.
    5) فیلترِ زمان: ورود فقط در پنجرهٔ اوایل/میانهٔ روز (پس از opening-range، پیش از
       پنجرهٔ climax اواخرِ روز) — بازگشتِ اکسترمم زود است.

بهبود «همه‌چیز شناور»: N, f, pull_max, پنجرهٔ ساعتِ ورود، SL/TP همه per-TF و غیررند.
"""
import numpy as np
import pandas as pd

from engine import scalp_engine as se


# ---------------------------------------------------------------------------
def _bars_per_day(tf: str) -> int:
    """تعدادِ تقریبیِ کندل در یک روزِ ۲۴ساعته برای هر تایم‌فریم (بازارِ ۲۴ساعتهٔ FX/طلا)."""
    return {
        'M1': 1440, 'M5': 288, 'M15': 96, 'M30': 48,
        'H1': 24, 'H4': 6, 'D1': 1, 'W1': 1,
    }.get(tf, 96)


def _daily_atr_from_intraday(df, day_id, lookback_days=14):
    """
    ADR (میانگینِ دامنهٔ روزانهٔ اخیر) از دادهٔ intraday.
    خروجی: آرایهٔ هم‌طولِ df، مقدارِ ADR در هر کندل = میانگینِ دامنهٔ lookback روزِ *قبلِ* روزِ جاری
    (کاملاً causal — از روزهای گذشته).
    """
    n = len(df)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    # دامنهٔ هر روز
    uniq_days = []
    day_hi = {}
    day_lo = {}
    for i in range(n):
        d = day_id[i]
        if d not in day_hi:
            day_hi[d] = h[i]; day_lo[d] = l[i]; uniq_days.append(d)
        else:
            if h[i] > day_hi[d]: day_hi[d] = h[i]
            if l[i] < day_lo[d]: day_lo[d] = l[i]
    day_range = {d: day_hi[d] - day_lo[d] for d in uniq_days}
    # ADR روزِ d = میانگینِ دامنهٔ lookback روزِ *قبل* از d
    adr_of_day = {}
    for idx, d in enumerate(uniq_days):
        prev = uniq_days[max(0, idx - lookback_days):idx]
        adr_of_day[d] = float(np.mean([day_range[p] for p in prev])) if prev else np.nan
    adr = np.array([adr_of_day[day_id[i]] for i in range(n)], dtype=float)
    return adr


def trend_from_open_signals(df, tf, side,
                            n_open=6, f_range=0.25, pull_max=0.62,
                            entry_from_bar=None, entry_to_bar=None,
                            adr_lb=14, min_spike_frac=0.30):
    """
    سیگنالِ «trend-from-open first-pullback continuation».

    df   : دیتافریمِ intraday یک TF.
    tf   : نامِ تایم‌فریم (برای bars_per_day).
    side : 'long' یا 'short'.
    n_open        : تعدادِ کندلِ opening-range.
    f_range       : سقفِ نسبتِ opening-range به ADR (رنجِ اولیهٔ کوچک).
    pull_max      : حداکثر نسبتِ pullback به leg (اسپایک) که هنوز «کوچک» است.
    entry_from_bar/entry_to_bar : پنجرهٔ اندیسِ کندل درونِ روز که ورود مجاز است
                                  (None ⇒ از n_open تا 0.85×bars_per_day).
    adr_lb        : تعدادِ روزِ ADR.
    min_spike_frac: حداقل نسبتِ leg (اسپایکِ اولیه) به ADR تا «اسپایکِ واقعی» شمرده شود.

    خروجی: آرایهٔ بولین هم‌طولِ df.
    """
    n = len(df)
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    dt = pd.to_datetime(df['time'], unit='s')
    day_id = dt.dt.floor('D').astype('int64').to_numpy()  # شناسهٔ روزِ UTC

    bpd = _bars_per_day(tf)
    if entry_from_bar is None:
        entry_from_bar = n_open
    if entry_to_bar is None:
        entry_to_bar = int(0.85 * bpd)

    adr = _daily_atr_from_intraday(df, day_id, adr_lb)

    sig = np.zeros(n, dtype=bool)

    # اندیسِ کندل درونِ هر روز (0-based)
    intraday_idx = np.zeros(n, dtype=int)
    day_start = {}
    for i in range(n):
        d = day_id[i]
        if d not in day_start:
            day_start[d] = i
        intraday_idx[i] = i - day_start[d]

    # پیمایشِ هر روز
    i = 0
    while i < n:
        d = day_id[i]
        # مرزِ روز
        j0 = i
        j = i
        while j < n and day_id[j] == d:
            j += 1
        j1 = j  # [j0, j1)
        day_len = j1 - j0

        if day_len > n_open + 2 and np.isfinite(adr[j0]) and adr[j0] > 0:
            # opening-range از n_open کندلِ نخست
            oi0 = j0
            oi1 = j0 + n_open
            initHi = np.max(h[oi0:oi1])
            initLo = np.min(l[oi0:oi1])
            initR = initHi - initLo
            open_px = o[j0]

            # فیلترِ رژیم: رنجِ اولیهٔ کوچک
            if initR < f_range * adr[j0]:
                # جهتِ اسپایکِ اولیه: بسته‌شدنِ کندلِ n_open نسبت به بازِ روز
                spike_dir = 'long' if c[oi1 - 1] >= open_px else 'short'
                if spike_dir == side:
                    # دنبالِ breakout لبهٔ opening-range در جهتِ side، سپس اولین pullback
                    # leg = فاصلهٔ breakout از لبهٔ مقابل (اندازهٔ اسپایک)
                    broke = False
                    leg_hi = initHi
                    leg_lo = initLo
                    k = oi1
                    while k < j1:
                        idr = intraday_idx[k]
                        if side == 'long':
                            # به‌روزرسانیِ اکسترممِ leg
                            if h[k] > leg_hi:
                                leg_hi = h[k]
                            # breakout بالای opening-range
                            if not broke and h[k] > initHi:
                                broke = True
                            if broke:
                                leg = leg_hi - initLo
                                if leg >= min_spike_frac * adr[j0] and leg > 0:
                                    # pullback نسبت به leg: چقدر از leg_hi پایین آمده
                                    pull = (leg_hi - l[k]) / leg
                                    # اولین pullbackِ کوچک + کندلِ تأییدِ هم‌جهت (high1):
                                    # کندلِ k یک pullback ساخت (low پایین‌تر از قبل) و
                                    # کندلِ بعد high کندلِ k را می‌شکند ⇒ سیگنال روی k.
                                    if 0 < pull <= pull_max and entry_from_bar <= idr <= entry_to_bar:
                                        # کندلِ pullback: low[k] < low[k-1] (بازگشتِ کوچک)
                                        if k >= 1 and l[k] < l[k - 1] and c[k] < leg_hi:
                                            sig[k] = True
                                            break  # فقط اولین pullbackِ روز
                        else:
                            if l[k] < leg_lo:
                                leg_lo = l[k]
                            if not broke and l[k] < initLo:
                                broke = True
                            if broke:
                                leg = initHi - leg_lo
                                if leg >= min_spike_frac * adr[j0] and leg > 0:
                                    pull = (h[k] - leg_lo) / leg
                                    if 0 < pull <= pull_max and entry_from_bar <= idr <= entry_to_bar:
                                        if k >= 1 and h[k] > h[k - 1] and c[k] > leg_lo:
                                            sig[k] = True
                                            break
                        k += 1
        i = j1

    return sig


# ---------------------------------------------------------------------------
def load_tf(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


if __name__ == '__main__':
    from engine import rqs
    df = load_tf('XAUUSD', 'M5')
    for side in ('long', 'short'):
        s = trend_from_open_signals(df, 'M5', side,
                                    n_open=6, f_range=0.25, pull_max=0.62,
                                    min_spike_frac=0.30)
        long_sig = s if side == 'long' else np.zeros(len(df), bool)
        short_sig = s if side == 'short' else np.zeros(len(df), bool)
        tr = se.simulate_trades(df, long_sig, short_sig, sl_pip=150, tp_pip=225,
                                asset='XAUUSD', max_hold=48, allow_overlap=False)
        r = rqs.compute_rqs(tr, 'XAUUSD', sl_pip=150, tp_pip=225)
        print(rqs.format_report(f'S344_XAU_M5_{side}', r), '| n=', len(tr))
