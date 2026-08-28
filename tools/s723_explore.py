# -*- coding: utf-8 -*-
"""
s723_explore.py — اکتشافِ لایهٔ نو `S723`: «آرام‌گیریِ نوسانِ نوسان» روی طلا
================================================================================
⚠️ فقط روی **نیمهٔ اولِ** داده (مسیرِ چندگانگیِ C). نیمهٔ دوم دست‌نخورده می‌ماند.

مفهوم (vol-of-vol): نوسانِ *خودِ نوسان* — انحرافِ معیارِ تغییراتِ log(ATR13).
  R(t) = std(Δlog ATR13, 13) / std(Δlog ATR13, 89)   ← بی‌مقیاس، علّی (shift(1))
  رویداد: عبورِ **نزولیِ** R از آستانهٔ thr (نوسانِ نوسان آرام می‌گیرد ⇒
  رژیمِ نوسانیِ باثبات ⇒ روندِ منظم). جهت از علامتِ رانشِ ۳۴-کندلی.
  mode='with': هم‌جهتِ رانش · mode='against': خلافِ رانش. داده تصمیم می‌گیرد.

نوبودگی (ممیزی 2026-08-28): grep کامل results/*.md —
  «vol-of-vol» و «volatility of volatility» صفر پرونده.
  متمایز از S704ِ همکار (عبورِ *صعودیِ* سطحِ ATR8/ATR89 = انبساطِ نوسان —
  اینجا مشتقِ دوم و جهتِ عبور نزولی است)، S800 (فشردگیِ *سطحِ* نوسان +
  شکستِ Donchian)، S841 (رژیمِ variance-ratio روی بازده، نه ATR)،
  S690 (فروپاشیِ آنتروپی). هیچ لایه‌ای پایداریِ خودِ نوسان را نسنجیده.

هندسه: SL = k×ATR(89)ِ میانه، TP = rr×SL. max_hold = 55 کندلِ همان TF
(هم‌مقیاس با پنجرهٔ سیگنال — علاجِ BUG-TFM).
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
OUT = os.path.join(ROOT, 'results', '_s723_explore')

# ── فضای جست‌وجو (شمارش صادقانه برای n_trials پیش‌ثبت) ────────────────────
THRS = (0.60, 0.75, 0.90, 1.05)   # آستانهٔ عبورِ نزولیِ R (بی‌مقیاس)
KS = (1.3, 2.1, 3.4)              # ضریب SL
RRS = (1.0, 1.5, 2.0)             # TP/SL — هرگز <1
MODES = ('with', 'against')
# سلول‌ها: 4×3×3×2 = 72 در هر TF

W_ATR = 13      # پنجرهٔ ATR پایه
W_FAST = 13     # پنجرهٔ std سریعِ Δlog ATR
W_SLOW = 89     # پنجرهٔ std کندِ Δlog ATR
W_DRIFT = 34    # پنجرهٔ علامتِ رانش
WARMUP = 250


def vov_ratio(df: pd.DataFrame) -> np.ndarray:
    """R(t) = std(ΔlogATR13,13)/std(ΔlogATR13,89) — تماماً علّی با shift(1)."""
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(W_ATR).mean()
    dla = np.log(atr).diff()
    fast = dla.rolling(W_FAST).std()
    slow = dla.rolling(W_SLOW).std()
    r = (fast / slow).shift(1)          # فقط اطلاعاتِ تا پایانِ کندلِ قبل
    return r.to_numpy(float)


def calm_signals(df: pd.DataFrame, thr: float, mode: str):
    """رویدادِ عبورِ نزولیِ R از thr؛ جهت از علامتِ رانشِ ۳۴-کندلیِ علّی."""
    r = vov_ratio(df)
    c = df['close'].to_numpy(float)
    n = len(c)
    drift = np.zeros(n)
    drift[W_DRIFT:] = c[W_DRIFT - 1:-1] - c[:n - W_DRIFT]   # تا close کندلِ قبل
    cross_dn = np.zeros(n, bool)
    cross_dn[1:] = (r[:-1] >= thr) & (r[1:] < thr)          # لبه‌ایِ نزولی
    cross_dn[:WARMUP] = False
    cross_dn &= ~np.isnan(r)
    up_drift = drift > 0
    if mode == 'with':
        longs = cross_dn & up_drift
        shorts = cross_dn & ~up_drift
    else:
        longs = cross_dn & ~up_drift
        shorts = cross_dn & up_drift
    return longs, shorts


def bars_per_hour(df: pd.DataFrame) -> float:
    t = df['time'].to_numpy(np.int64)
    dt = np.median(np.diff(t[:5000]))
    return 3600.0 / float(dt)


def explore_tf(tf: str):
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    half = len(df) // 2
    df = df.iloc[:half].reset_index(drop=True)   # ⚠️ فقط نیمهٔ اول
    src = d['src']
    atr = atr_median(df)
    pip = se.ASSETS[ASSET]['pip']
    mh = 55                                       # 55 کندلِ همان TF
    rows = []
    for thr in THRS:
        for mode in MODES:
            ls, ss = calm_signals(df, thr, mode)
            n_ev = int(ls.sum() + ss.sum())
            for k in KS:
                sl = round(k * atr / pip, 1)
                if sl <= 6.6:
                    continue
                for rr in RRS:
                    tp = round(sl * rr, 1)
                    tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                                            max_hold=mh, allow_overlap=False)
                    if len(tr) < 30:
                        rows.append(dict(tf=tf, thr=thr, mode=mode, k=k, rr=rr,
                                         sl=sl, tp=tp, n=len(tr), note='n<30'))
                        continue
                    wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                    exp = float(tr['pnl_pip'].mean())
                    nl = int((tr['direction'] == 'long').sum())
                    ns = int((tr['direction'] == 'short').sum())
                    pos = float(tr.loc[tr['pnl_pip'] > 0, 'pnl_pip'].sum())
                    neg = float(-tr.loc[tr['pnl_pip'] < 0, 'pnl_pip'].sum())
                    pf = pos / neg if neg > 0 else float('inf')
                    be = 100.0 * (sl + 3.3) / (sl + tp)
                    rows.append(dict(tf=tf, thr=thr, mode=mode, k=k, rr=rr,
                                     sl=sl, tp=tp, n=len(tr), n_long=nl,
                                     n_short=ns, wr=round(wr, 2),
                                     be=round(be, 2), margin=round(wr - be, 2),
                                     pf=round(pf, 3), exp_pip=round(exp, 3),
                                     n_events=n_ev))
    return dict(tf=tf, src=src, bars_half=len(df),
                atr89_med_pip=round(atr / pip, 2), max_hold=mh, rows=rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    tfs = sys.argv[1:] or ['M1']
    for tf in tfs:
        print(f'── S723 اکتشاف · {ASSET}-{tf} · فقط نیمهٔ اول ──', flush=True)
        res = explore_tf(tf)
        print(f"src={res['src']} bars={res['bars_half']} "
              f"ATR89={res['atr89_med_pip']}pip mh={res['max_hold']}", flush=True)
        pos = [r for r in res['rows'] if r.get('margin') is not None and r['margin'] > 0]
        for r in sorted(pos, key=lambda x: -x['margin'])[:10]:
            print(f"  + thr={r['thr']} {r['mode']} k={r['k']} rr={r['rr']} "
                  f"SL={r['sl']}/TP={r['tp']} n={r['n']} (L{r['n_long']}/S{r['n_short']}) "
                  f"WR={r['wr']}% BE={r['be']}% حاشیه=+{r['margin']}pp PF={r['pf']}",
                  flush=True)
        if not pos:
            print('  هیچ سلولِ مثبتی نیست.', flush=True)
        with open(os.path.join(OUT, f'explore_{tf}.json'), 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f'  ذخیره شد → results/_s723_explore/explore_{tf}.json', flush=True)


if __name__ == '__main__':
    main()
