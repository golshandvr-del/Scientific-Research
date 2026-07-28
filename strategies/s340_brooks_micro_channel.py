# -*- coding: utf-8 -*-
"""
S340 — Al Brooks «Micro Channels» (فصلِ ۱۶ کتابِ Trading Price Action: Trends)
================================================================================
پارادایم: RQS+ ≥ ۸۰ (نه net-profit قدیمی).

تز (نقلِ Brooks):
- micro channel = رشتهٔ ۲..~۱۰ کندلِ فوق‌فشرده و هم‌جهت، بدونِ pullback یا با pullbackِ نادرِ کوچک
  ⇒ نمایندهٔ روندِ *بسیار قوی/مومنتومی*.
- «most breakouts fail»: اولین شکستِ نزولیِ یک micro channelِ صعودی (اولین pullback) معمولاً fail
  می‌شود و *به‌شدت خریده می‌شود* ⇒ ورودِ **ادامهٔ روند (with-trend / high-1 failed-breakout)**.
- «هرچه کندل‌های micro channel بیشتر، احتمالِ برنگشتنِ pullback بیشتر» ⇒ فیلترِ طول.
- micro channel > ~۱۰ کندل = climax ⇒ باید احتیاط کرد (سقفِ طول).

تفاوتِ بنیادی با S325 (فصل ۱۵): آن fade/mean-reversion بود (در تلهٔ اسپرد مرد)؛ این
continuation/momentum است — دقیقاً هم‌جهت با ماهیتِ momentum-persistentِ طلا (کشفِ S320).

منطقِ مکانیکی (causal، بدونِ look-ahead؛ سیگنال روی کندلِ i، ورود در open کندلِ i+1):
  bull micro channel روی پنجرهٔ [i-k+1 .. i]:
    - هر کندل higher-high و higher-low نسبت به قبلی (رشتهٔ صعودیِ فشرده)  → mc_len
    - بدنه‌های صعودی غالب (frac_bull ≥ body_min)
    - رژیم: ema_fast[i] > ema_slow[i]
  ماشهٔ LONG (failed-breakout / high-1):
    - کندلِ i یک pullbackِ کوچک است: low[i] < low[i-1]  (اولین شکستِ micro trend line)
    - اما close[i] برمی‌گردد نزدیکِ بالا (close[i] > (low[i]+high[i])/2)  ⇒ شکست fail شد
    - طولِ micro channel قبل از pullback در بازهٔ [k_min, k_max] (نه climax)
  قرینهٔ کامل برای SHORT در micro channelِ نزولی.
"""
import numpy as np
import pandas as pd

from engine import scalp_engine as se
from engine import indicator_bank as ib
from engine import rqs


# ---------------------------------------------------------------------------
def _ema(x, p):
    return pd.Series(x).ewm(span=p, adjust=False).mean().to_numpy()


def micro_channel_signals(df, side, k_min, k_max, ema_fast, ema_slow,
                          body_min, close_pos_min, overlap_max):
    """
    خروجی: آرایهٔ بولین هم‌طولِ df؛ True = سیگنالِ ورود روی این کندل (ورود در i+1).

    side='long'  ⇒ bull micro channel + failed downside breakout (high-1 continuation)
    side='short' ⇒ bear micro channel + failed upside breakout   (low-1 continuation)
    """
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(df)

    ef = _ema(c, ema_fast)
    es = _ema(c, ema_slow)

    rng = np.maximum(h - l, 1e-9)
    body = c - o
    body_frac = np.abs(body) / rng

    sig = np.zeros(n, dtype=bool)

    for i in range(k_max + 2, n):
        # ---- رژیمِ جهت ----
        if side == 'long':
            if not (ef[i] > es[i]):
                continue
        else:
            if not (ef[i] < es[i]):
                continue

        # ---- ماشهٔ pullback روی کندلِ i (اولین شکستِ micro trend line) ----
        if side == 'long':
            # اولین شکستِ نزولی + بازگشتِ close نزدیکِ بالا (failed breakout)
            is_pullback = l[i] < l[i - 1]
            close_pos = (c[i] - l[i]) / rng[i]
            failed = is_pullback and (close_pos >= close_pos_min)
        else:
            is_pullback = h[i] > h[i - 1]
            close_pos = (h[i] - c[i]) / rng[i]
            failed = is_pullback and (close_pos >= close_pos_min)
        if not failed:
            continue

        # ---- شمارشِ طولِ micro channel *پیش از* pullback (کندل‌های i-1, i-2, ...) ----
        # bull: رشتهٔ higher-high و higher-low با بدنه‌های صعودیِ غالب و overlap کم
        mc_len = 0
        strong_body = 0
        j = i - 1
        while j >= 1:
            if side == 'long':
                asc = (h[j] > h[j - 1]) and (l[j] >= l[j - 1])
            else:
                asc = (l[j] < l[j - 1]) and (h[j] <= h[j - 1])
            if not asc:
                break
            # overlap: چه مقدار از رنجِ این کندل با کندلِ قبلی هم‌پوشان است (کم = فشرده)
            ov_lo = max(l[j], l[j - 1]); ov_hi = min(h[j], h[j - 1])
            overlap = max(0.0, ov_hi - ov_lo) / rng[j]
            if overlap > overlap_max:
                break
            mc_len += 1
            # بدنهٔ هم‌جهتِ قوی
            if side == 'long' and body[j] > 0 and body_frac[j] >= 0.35:
                strong_body += 1
            if side == 'short' and body[j] < 0 and body_frac[j] >= 0.35:
                strong_body += 1
            j -= 1

        if mc_len < k_min or mc_len > k_max:
            continue
        # نسبتِ بدنه‌های قویِ هم‌جهت درونِ micro channel
        if strong_body / max(mc_len, 1) < body_min:
            continue

        sig[i] = True

    return sig


# ---------------------------------------------------------------------------
def run_one(tf_path, asset, side, k_min, k_max, ema_fast, ema_slow,
            body_min, close_pos_min, overlap_max, sl_pip, tp_pip, max_hold):
    df = se.load_data(tf_path)
    sig = micro_channel_signals(df, side, k_min, k_max, ema_fast, ema_slow,
                                body_min, close_pos_min, overlap_max)
    long_sig = sig if side == 'long' else np.zeros(len(df), bool)
    short_sig = sig if side == 'short' else np.zeros(len(df), bool)
    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=asset, max_hold=max_hold, allow_overlap=False)
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip, tp_pip=tp_pip)
    return trades, r


if __name__ == '__main__':
    # آزمونِ اولیه روی XAUUSD M5 (طبقِ قانون: از M5 شروع)
    tr, r = run_one('data/XAUUSD_M5.csv', 'XAUUSD', 'long',
                    k_min=4, k_max=9, ema_fast=21, ema_slow=55,
                    body_min=0.45, close_pos_min=0.5, overlap_max=0.6,
                    sl_pip=140, tp_pip=230, max_hold=48)
    print(rqs.format_report('S340_MicroChannel_XAU_M5_LONG', r))
