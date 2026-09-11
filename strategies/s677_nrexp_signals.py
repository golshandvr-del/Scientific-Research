#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S677 — ماژولِ سیگنالِ مشترک (جستجو و فینال دقیقاً همین را import می‌کنند)

فشردگی در t−1: range[t−1] ≤ q·med21[t−1]   (med21 = میانهٔ range روی [t−21, t−1])
انبساط در t:   range[t] ≥ R·range[t−1] ∧ |body|/range ≥ 0.5 ؛ جهت = علامتِ body
سیگنال در t (ورود open[t+1] در موتور). همه علّی.
"""
import numpy as np
import pandas as pd

K_DRIFT = 180
MED_P = 21
RHO_MIN = 0.5


def nrexp_signals(o, h, lo, c, q, R):
    n = len(c)
    rng = h - lo
    body = c - o
    with np.errstate(divide='ignore', invalid='ignore'):
        rho = np.where(rng > 0, np.abs(body) / rng, 0.0)
    med_prev = pd.Series(rng).rolling(MED_P, min_periods=MED_P).median().values  # med تا t (شامل t)
    # med21[t-1] برای مقایسه با range[t-1] → شیفت ۱: استفاده در بارِ t از میانهٔ [t-21..t-1]
    med_tm1 = np.full(n, np.nan); med_tm1[1:] = med_prev[:-1]         # میانه‌ی پنجرهٔ منتهی به t-1 (شامل t-1)
    # برای علّیتِ سخت‌تر، فشردگیِ t-1 را با میانهٔ پنجرهٔ منتهی به t-2 مقایسه می‌کنیم:
    med_tm2 = np.full(n, np.nan); med_tm2[2:] = med_prev[:-2]
    rng_tm1 = np.full(n, np.nan); rng_tm1[1:] = rng[:-1]
    compressed = (rng_tm1 <= q * med_tm2) & np.isfinite(med_tm2) & (rng_tm1 > 0)
    expanded = (rng >= R * rng_tm1) & (rho >= RHO_MIN)
    ev = compressed & expanded
    long_sig = ev & (body > 0)
    short_sig = ev & (body < 0)
    return long_sig, short_sig


def drift_masks(c, K=K_DRIFT):
    n = len(c)
    up = np.zeros(n, bool); dn = np.zeros(n, bool)
    up[K + 1:] = c[K:-1] > c[:-(K + 1)]
    dn[K + 1:] = c[K:-1] < c[:-(K + 1)]
    return up, dn
