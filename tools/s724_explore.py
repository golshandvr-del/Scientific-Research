# -*- coding: utf-8 -*-
"""
s724_explore.py — اکتشافِ لایهٔ نو `S724`: «کندلِ بی‌همپوشانی» (Runaway Bar) روی طلا
================================================================================
⚠️ فقط روی **نیمهٔ اولِ** داده (مسیرِ چندگانگیِ C). نیمهٔ دوم دست‌نخورده می‌ماند.

مفهوم: کندلی که دامنه‌اش **هیچ همپوشانی** با کندلِ قبلی ندارد:
  gap-up  : low[t]  > high[t-1]
  gap-down: high[t] < low[t-1]
یعنی هیچ قیمتی از کندلِ قبل در کندلِ فعلی دوباره معامله نشد — ایمپالسِ خالص
بدون بازگشت (اثرِ قیمتیِ دائمی؛ کایل ۱۹۸۵). فقط **درونِ هفته** (فاصلهٔ زمانی
دو کندل دقیقاً یک TF) تا از گپِ آخرِ هفته (خانوادهٔ S560/S562) جدا بماند.
فیلترِ اندازهٔ گپ: (low[t]−high[t−1]) ≥ gmin×ATR89 (یا معکوس).
جهت: mode='with' (ادامهٔ گپ) · mode='against' (پرشدنِ گپ). داده تصمیم می‌گیرد.

نوبودگی (ممیزی 2026-09-04): grep results/*.md برای
  «low > prev high / range gap / gap between bars / non-overlap bar» صفر پرونده.
  متمایز از S965/S1520 (شوکِ دامنه + نسبتِ بدنه — کندلِ بی‌همپوشانی می‌تواند
  دامنهٔ کوچک داشته باشد)، S757 (دو انبساطِ پیاپی)، S560/S562 (گپِ آخرِ هفته که
  اینجا حذف می‌شود)، S404 (پرشدنِ گپ در پنجرهٔ نوسان).

درسِ S720–S723 (چهار REJECT): غربالِ اکتشاف بر پایهٔ «حاشیه نسبت به BE» گول‌زننده
است (رانشِ طلا). اینجا **lift در برابرِ نولِ غیرشرطیِ سمت‌کلیددار** روی همان
هندسه سنجیده می‌شود و سدّ **lift·√n ≥ 78** (S761) پیشِ‌نیازِ پیش‌ثبت است.

هندسه: SL = k×ATR(89)ِ میانه، TP = rr×SL. max_hold = 34 کندلِ همان TF.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import scalp_engine as se          # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402
from tools.s720_explore import atr_median      # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s724_explore')

# ── فضای جست‌وجو (شمارش صادقانه برای n_trials پیش‌ثبت) ────────────────────
GMINS = (0.0, 0.10, 0.25)        # کفِ اندازهٔ گپ در واحدِ ATR89
KS = (1.3, 2.1, 3.4)             # ضریب SL
RRS = (1.0, 1.5, 2.0)            # TP/SL — هرگز <1
MODES = ('with', 'against')
# سلول‌ها: 3×3×3×2 = 54 در هر TF

W_ATR = 89
WARMUP = 250
MH = 34
N_UNCOND = 6000
SEED = 20260904


def atr89(df: pd.DataFrame) -> np.ndarray:
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(W_ATR).mean().shift(1).to_numpy(float)   # علّی


def runaway_signals(df: pd.DataFrame, gmin: float, mode: str):
    """کندلِ بی‌همپوشانی درونِ هفته؛ سیگنال روی کندلِ t ⇒ ورود در openِ t+1."""
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    t = df['time'].to_numpy(np.int64)
    n = len(h)
    a = atr89(df)
    dt = np.zeros(n, np.int64)
    dt[1:] = np.diff(t)
    step = int(np.median(dt[1:2000]))
    intra = dt == step                       # کندلِ قبلی بلافاصله قبل (نه آخرِ هفته)
    up = np.zeros(n, bool)
    dn = np.zeros(n, bool)
    up[1:] = (l[1:] - h[:-1]) >= gmin * a[1:]
    dn[1:] = (l[:-1] - h[1:]) >= gmin * a[1:]
    if gmin == 0.0:                          # اکیداً بزرگ‌تر (بی‌همپوشانیِ واقعی)
        up[1:] &= l[1:] > h[:-1]
        dn[1:] &= h[1:] < l[:-1]
    ok = intra & ~np.isnan(a)
    ok[:WARMUP] = False
    up &= ok
    dn &= ok
    if mode == 'with':
        return up, dn
    return dn, up


def uncond_wr_sides(df, sl, tp, mh, rng):
    """WR غیرشرطیِ هر سمت با nمونه‌های تصادفی (allow_overlap=True) — نولِ ارزان."""
    n = len(df)
    picks = rng.integers(WARMUP, n - mh - 2, N_UNCOND)
    m = np.zeros(n, bool)
    m[picks] = True
    z = np.zeros(n, bool)
    ul = se.simulate_trades(df, m, z, sl, tp, ASSET, max_hold=mh, allow_overlap=True)
    us = se.simulate_trades(df, z, m, sl, tp, ASSET, max_hold=mh, allow_overlap=True)
    return (100.0 * float((ul['pnl_pip'] > 0).mean()),
            100.0 * float((us['pnl_pip'] > 0).mean()))


def explore_tf(tf: str):
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    half = len(df) // 2
    df = df.iloc[:half].reset_index(drop=True)   # ⚠️ فقط نیمهٔ اول
    src = d['src']
    atr = atr_median(df)
    pip = se.ASSETS[ASSET]['pip']
    rng = np.random.default_rng(SEED)
    rows = []
    unc_cache = {}
    for k in KS:
        sl = round(k * atr / pip, 1)
        if sl <= 6.6:
            continue
        for rr in RRS:
            tp = round(sl * rr, 1)
            unc_cache[(sl, tp)] = uncond_wr_sides(df, sl, tp, MH, rng)
    for gmin in GMINS:
        for mode in MODES:
            ls, ss = runaway_signals(df, gmin, mode)
            n_ev = int(ls.sum() + ss.sum())
            for (sl, tp), (uwl, uws) in unc_cache.items():
                tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                                        max_hold=MH, allow_overlap=False)
                if len(tr) < 30:
                    rows.append(dict(tf=tf, gmin=gmin, mode=mode, sl=sl, tp=tp,
                                     n=len(tr), n_events=n_ev, note='n<30'))
                    continue
                nl = int((tr['direction'] == 'long').sum())
                ns = int((tr['direction'] == 'short').sum())
                wl = 100.0 * float((tr.loc[tr['direction'] == 'long', 'pnl_pip'] > 0).mean()) if nl else float('nan')
                ws = 100.0 * float((tr.loc[tr['direction'] == 'short', 'pnl_pip'] > 0).mean()) if ns else float('nan')
                wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                unc = (uwl * nl + uws * ns) / (nl + ns)
                lift = wr - unc
                pos = float(tr.loc[tr['pnl_pip'] > 0, 'pnl_pip'].sum())
                neg = float(-tr.loc[tr['pnl_pip'] < 0, 'pnl_pip'].sum())
                pf = pos / neg if neg > 0 else float('inf')
                mid = len(tr) // 2
                q1 = 100.0 * float((tr['pnl_pip'].iloc[:mid] > 0).mean())
                q2 = 100.0 * float((tr['pnl_pip'].iloc[mid:] > 0).mean())
                rows.append(dict(tf=tf, gmin=gmin, mode=mode, k=round(sl / (atr / pip), 2),
                                 rr=round(tp / sl, 2), sl=sl, tp=tp, n=len(tr),
                                 n_long=nl, n_short=ns, n_events=n_ev,
                                 wr=round(wr, 2), uncond=round(unc, 2),
                                 lift=round(lift, 2),
                                 lift_long=round(wl - uwl, 2) if nl else None,
                                 lift_short=round(ws - uws, 2) if ns else None,
                                 lift_sqrt_n=round(lift * np.sqrt(len(tr)), 1),
                                 pf=round(pf, 3), exp_pip=round(float(tr['pnl_pip'].mean()), 3),
                                 q1=round(q1, 1), q2=round(q2, 1)))
    return dict(tf=tf, src=src, bars_half=len(df), atr89_med_pip=round(atr / pip, 2),
                max_hold=MH, n_uncond=N_UNCOND, seed=SEED, rows=rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    tfs = sys.argv[1:] or ['H4']
    for tf in tfs:
        print(f'── S724 اکتشاف · {ASSET}-{tf} · فقط نیمهٔ اول ──', flush=True)
        res = explore_tf(tf)
        print(f"src={res['src']} bars={res['bars_half']} ATR89={res['atr89_med_pip']}pip mh={MH}", flush=True)
        pos = [r for r in res['rows'] if r.get('lift') is not None and r['lift'] > 0]
        for r in sorted(pos, key=lambda x: -x['lift_sqrt_n'])[:8]:
            flag = '★' if r['lift_sqrt_n'] >= 78 else ' '
            print(f"  {flag} gmin={r['gmin']} {r['mode']:7} k={r['k']} rr={r['rr']} n={r['n']} "
                  f"(L{r['n_long']}/S{r['n_short']}) WR={r['wr']} unc={r['uncond']} "
                  f"lift={r['lift']:+.2f} (L{r['lift_long']}/S{r['lift_short']}) "
                  f"lift√n={r['lift_sqrt_n']} PF={r['pf']} Q1/Q2={r['q1']}/{r['q2']}", flush=True)
        if not pos:
            print('  هیچ سلولِ lift مثبتی نیست.', flush=True)
        with open(os.path.join(OUT, f'explore_{tf}.json'), 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f'  ذخیره شد → results/_s724_explore/explore_{tf}.json', flush=True)


if __name__ == '__main__':
    main()
