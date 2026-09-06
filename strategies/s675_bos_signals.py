#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S675 — ماژولِ سیگنالِ مشترک (جستجو و فینال هر دو دقیقاً همین را import می‌کنند)

فرکتالِ Williams ۵-باره (تأیید در i+2) → دنبالهٔ swingها → HL/LH → اولین closeِ
شکنندهٔ swingِ مقابل = BOS (لبه). همه‌چیز علّی: در بارِ k فقط از فرکتال‌های
تأییدشده تا k (یعنی i ≤ k−2) استفاده می‌شود.
"""
import numpy as np

K_DRIFT = 180


def bos_signals(h, lo, c):
    """برمی‌گرداند (long_sig, short_sig) در بارِ تأییدِ BOS (ورود open[k+1] در موتور)."""
    n = len(c)
    long_sig = np.zeros(n, bool)
    short_sig = np.zeros(n, bool)

    # فرکتال‌ها (بازنگر برای شناسایی؛ اما در k تنها فرکتال‌های i≤k−2 «شناخته» می‌شوند)
    fl = np.zeros(n, bool); fh = np.zeros(n, bool)
    fl[2:-2] = (lo[2:-2] < lo[:-4]) & (lo[2:-2] < lo[1:-3]) & \
               (lo[2:-2] < lo[3:-1]) & (lo[2:-2] < lo[4:])
    fh[2:-2] = (h[2:-2] > h[:-4]) & (h[2:-2] > h[1:-3]) & \
               (h[2:-2] > h[3:-1]) & (h[2:-2] > h[4:])

    prev_low = np.nan      # فرکتالِ کفِ پیشین
    last_low = np.nan      # آخرین فرکتالِ کف
    last_low_bar = -1
    prev_high = np.nan
    last_high = np.nan
    last_high_bar = -1
    # سقفِ swing برای BOS-long: آخرین فرکتالِ سقفِ *بعد از* prev_low (بین دو کف) — اگر نبود، آخرین سقف
    # برای سادگی و علّیت: H_swing = آخرین فرکتالِ سقفِ تأییدشده با bar > last_low_bar_prev
    armed_long = False; H_swing = np.nan
    armed_short = False; L_swing = np.nan

    for k in range(4, n):
        i = k - 2  # فرکتالِ تأییدشده در این بار
        if fl[i]:
            prev_low, last_low, prev_low_bar = last_low, lo[i], last_low_bar
            last_low_bar = i
            if np.isfinite(prev_low) and last_low > prev_low:
                # HL تشکیل شد → سقفِ swing = بالاترین فرکتالِ سقفِ بینِ prev_low_bar و i
                seg = np.where(fh[prev_low_bar:i])[0] if prev_low_bar >= 0 else []
                if len(seg):
                    H_swing = float(h[prev_low_bar + seg].max())
                    armed_long = True
                else:
                    armed_long = False
            else:
                armed_long = False
        if fh[i]:
            prev_high, last_high, prev_high_bar = last_high, h[i], last_high_bar
            last_high_bar = i
            if np.isfinite(prev_high) and last_high < prev_high:
                seg = np.where(fl[prev_high_bar:i])[0] if prev_high_bar >= 0 else []
                if len(seg):
                    L_swing = float(lo[prev_high_bar + seg].min())
                    armed_short = True
                else:
                    armed_short = False
            else:
                armed_short = False
        # BOS: اولین close بالای H_swing (لبه)
        if armed_long and c[k] > H_swing and c[k - 1] <= H_swing:
            long_sig[k] = True
            armed_long = False   # هر HL فقط یک BOS
        if armed_short and c[k] < L_swing and c[k - 1] >= L_swing:
            short_sig[k] = True
            armed_short = False
    return long_sig, short_sig


def drift_masks(c, K=K_DRIFT):
    n = len(c)
    up = np.zeros(n, bool); dn = np.zeros(n, bool)
    up[K + 1:] = c[K:-1] > c[:-(K + 1)]
    dn[K + 1:] = c[K:-1] < c[:-(K + 1)]
    return up, dn
