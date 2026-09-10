# -*- coding: utf-8 -*-
"""S931 — «شکستِ تازهٔ اکسترممِ هفتهٔ قبل با کندلِ مطلع» (Informed Weekly-Extremum Break).

پیش‌ثبت: results/S931_PREREG_weekly_extremum_break.md (کامیت 3f51a9ad — پیش از این کد).

تک‌نقطهٔ تغییر نسبت به S930: شناسهٔ دوره = هفتهٔ دوشنبه‌محور (UTC) به‌جای ماهِ تقویمی.
همهٔ اجزای دیگر (رویداد، بازوها، براکتِ شناور، شبیه‌ساز، نول، داور) عیناً از s930 وارد می‌شود.
n_trials=76 (تجمعیِ بلوک S930–S939).
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from strategies import s930_monthly_extremum_break as B   # noqa: E402

WEEK_OFF = 172800      # epoch(1970-01-01)=پنج‌شنبه ⇒ دوشنبه = 1970-01-05 = 4 روز = 345600؛
                       # (t − 345600)//604800 هفتهٔ دوشنبه‌محور می‌دهد. S693 از 345600 استفاده کرد؛
                       # معادل: (t − 172800) // 604800 مرزها را روی *شنبه* می‌گذارد.
                       # چون طلا شنبه/یکشنبه کندل ندارد، هر دو انتخاب افرازِ یکسانی از کندل‌ها می‌دهند.
                       # در verify هم‌ارزی با افرازِ dt.isocalendar().week چک می‌شود.


def week_id(t_epoch: np.ndarray) -> np.ndarray:
    return ((np.asarray(t_epoch, dtype=np.int64) - WEEK_OFF) // 604800).astype(np.int64)


# ── تزریقِ شناسهٔ دوره در ماژولِ S930 (تک‌نقطهٔ تغییر) ──
B.month_id = week_id
B.N_TRIALS = 76
B.OUT = 'results/_s931'
B.LABEL = 'S931_InformedWeeklyExtremumBreak'
B.SEED = 20260905


def verify(n=40000, seed=9) -> float:
    """PWH/PWL مقابلِ pandas groupby(week) + shift؛ افرازِ هفته مقابلِ isocalendar؛ no-look-ahead."""
    rng = np.random.default_rng(seed)
    # H1 مصنوعی فقط Mon–Fri (مثلِ طلا)
    t0 = 1_400_000_000 - (1_400_000_000 % 86400)
    ts = []
    t = t0
    while len(ts) < n:
        dow = pd.Timestamp(t, unit='s').dayofweek
        if dow < 5:
            ts.append(t)
        t += 3600
    t = np.asarray(ts, dtype=np.int64)
    c = 1800 + np.cumsum(rng.normal(0, 2, n))
    o = np.concatenate([[c[0]], c[:-1]]) + rng.normal(0, 0.3, n)
    h = np.maximum(o, c) + np.abs(rng.normal(0, 1.5, n))
    l = np.minimum(o, c) - np.abs(rng.normal(0, 1.5, n))
    d = dict(time=t, open=o, high=h, low=l, close=c)
    f = B.features(d, keep_aux=True)
    dt = pd.to_datetime(t, unit='s')
    iso = dt.isocalendar()
    iso_key = (iso['year'].to_numpy() * 100 + iso['week'].to_numpy())
    # افرازِ یکسان: هر week_id دقیقاً به یک iso_key نگاشت شود و برعکس
    df = pd.DataFrame(dict(w=f['mid'], k=iso_key, high=h, low=l, close=c))
    part_ok = (df.groupby('w')['k'].nunique().max() == 1) and (df.groupby('k')['w'].nunique().max() == 1)
    worst = 0.0 if part_ok else 1.0
    wk_hi = df.groupby('w')['high'].max(); wk_lo = df.groupby('w')['low'].min()
    ws = wk_hi.index.to_numpy()
    prev_hi = pd.Series(wk_hi.values, index=ws).shift(1)
    prev_lo = pd.Series(wk_lo.values, index=ws).shift(1)
    adjacent = pd.Series(np.concatenate([[False], np.diff(ws) == 1]), index=ws)
    prev_hi[~adjacent] = np.nan; prev_lo[~adjacent] = np.nan
    ref_pwh = df['w'].map(prev_hi).to_numpy(); ref_pwl = df['w'].map(prev_lo).to_numpy()
    for got, ref in ((f['pmh'], ref_pwh), (f['pml'], ref_pwl)):
        assert np.array_equal(np.isfinite(got), np.isfinite(ref)), 'NaN pattern mismatch'
        m = np.isfinite(ref)
        worst = max(worst, float(np.max(np.abs(got[m] - ref[m]))))
    up = ((df['close'] > ref_pwh) & (df['close'].shift() <= ref_pwh)).to_numpy() & f['valid']
    df['up'] = up
    ref_first = (df.groupby('w')['up'].cumsum().eq(1) & df['up']).to_numpy()
    worst = max(worst, float(np.sum(ref_first != f['up'])))
    cut = n // 2
    d2 = {k: v.copy() for k, v in d.items()}
    for k in ('open', 'high', 'low', 'close'):
        d2[k][cut:] += rng.normal(0, 50, n - cut)
    f2 = B.features(d2, keep_aux=True)
    la = int(np.sum(f['up'][:cut] != f2['up'][:cut]) + np.sum(f['dn'][:cut] != f2['dn'][:cut]))
    worst = max(worst, float(la))
    print(f'  synthetic H1 Mon-Fri: weeks={len(ws)} up_first={int(f["up"].sum())} '
          f'dn_first={int(f["dn"].sum())} partition_ok={part_ok} look-ahead diffs={la}')
    return worst


def run_card(tf: str, verbose=True) -> dict:
    # فقط برچسبِ چاپ/نام؛ منطق عیناً S930
    out = B.run_card(tf, verbose)
    return out


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        w = verify()
        print(f'PWH/PWL + week partition + first-cross + look-ahead worst |Δ| = {w:.3e}')
        sys.exit(0 if w < 1e-9 else 1)
    run_card(sys.argv[1] if len(sys.argv) > 1 else 'M1')
