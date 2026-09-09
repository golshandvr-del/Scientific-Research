#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S676 — ماژولِ سیگنالِ مشترک (جستجو و فینال دقیقاً همین را import می‌کنند)

شوک در t−1 (S965): range[t−1] ≥ 2.618·ATR21[t−2] ∧ |body|/range ≥ 0.618
مکث در t: range[t] ≤ α·ATR21[t−1] ∧ inside(t در t−1) ∧ clv هم‌جهت
سیگنال در t (ورود open[t+1] در موتور). همه علّی.
"""
import numpy as np

SHOCK_MULT = 2.618
RHO_MIN = 0.618
ATR_P = 21
K_DRIFT = 180


def shock_pause_signals(o, h, lo, c, atr21, alpha):
    """atr21: آرایهٔ ATR21 هم‌طول (مقدارِ بارِ i از بارهای ≤ i)."""
    n = len(c)
    rng = h - lo
    body = c - o
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(rng > 0, np.abs(body) / rng, 0.0)
        clv = np.where(rng > 0, (c - lo) / rng, 0.5)
    atr_prev = np.full(n, np.nan); atr_prev[1:] = atr21[:-1]          # ATR21[i-1]
    atr_prev2 = np.full(n, np.nan); atr_prev2[2:] = atr21[:-2]        # ATR21[i-2]

    # شوک در بارِ t-1 → ارزیابی در t
    shock_up = np.zeros(n, bool); shock_dn = np.zeros(n, bool)
    s_ok = (rng >= SHOCK_MULT * atr_prev) & (rho >= RHO_MIN) & np.isfinite(atr_prev)
    shock_up[1:] = s_ok[:-1] & (body[:-1] > 0)
    shock_dn[1:] = s_ok[:-1] & (body[:-1] < 0)

    inside = np.zeros(n, bool)
    inside[1:] = (h[1:] <= h[:-1]) & (lo[1:] >= lo[:-1])
    tight = (rng <= alpha * atr_prev) & np.isfinite(atr_prev) & (rng > 0)

    long_sig = shock_up & inside & tight & (clv >= 0.5)
    short_sig = shock_dn & inside & tight & (clv <= 0.5)
    return long_sig, short_sig


def drift_masks(c, K=K_DRIFT):
    n = len(c)
    up = np.zeros(n, bool); dn = np.zeros(n, bool)
    up[K + 1:] = c[K:-1] > c[:-(K + 1)]
    dn[K + 1:] = c[K:-1] < c[:-(K + 1)]
    return up, dn
