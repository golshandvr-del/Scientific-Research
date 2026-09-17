#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S678 — ماژولِ سیگنالِ مشترک (جستجو و فینال دقیقاً همین را import می‌کنند)

rN[t] = ln(c[t]/c[t−N]); σ[t−1] = std(r1) روی [t−100, t−1]
رویداد (لبه): |rN[t]| ≥ z·σ[t−1]·√N  ∧  |rN[t−1]| < z·σ[t−2]·√N
جهت: rN>0 → SHORT (fade)، rN<0 → LONG. سیگنال در t، ورود open[t+1].
"""
import numpy as np
import pandas as pd

K_DRIFT = 180
SIG_P = 100


def overreact_signals(c, N, z):
    n = len(c)
    lc = np.log(c)
    r1 = np.full(n, np.nan); r1[1:] = np.diff(lc)
    sig = pd.Series(r1).rolling(SIG_P, min_periods=SIG_P).std().values   # std تا t (شامل t)
    sig_tm1 = np.full(n, np.nan); sig_tm1[1:] = sig[:-1]                 # σ[t−1]
    sig_tm2 = np.full(n, np.nan); sig_tm2[2:] = sig[:-2]                 # σ[t−2]
    rN = np.full(n, np.nan); rN[N:] = lc[N:] - lc[:-N]
    rN_tm1 = np.full(n, np.nan); rN_tm1[1:] = rN[:-1]
    thr_t = z * sig_tm1 * np.sqrt(N)
    thr_tm1 = z * sig_tm2 * np.sqrt(N)
    now = np.abs(rN) >= thr_t
    prev = np.abs(rN_tm1) >= thr_tm1
    ok = np.isfinite(thr_t) & np.isfinite(thr_tm1) & np.isfinite(rN) & np.isfinite(rN_tm1)
    edge = ok & now & ~prev
    short_sig = edge & (rN > 0)
    long_sig = edge & (rN < 0)
    return long_sig, short_sig


def drift_masks(c, K=K_DRIFT):
    n = len(c)
    up = np.zeros(n, bool); dn = np.zeros(n, bool)
    up[K + 1:] = c[K:-1] > c[:-(K + 1)]
    dn[K + 1:] = c[K:-1] < c[:-(K + 1)]
    return up, dn
