# -*- coding: utf-8 -*-
"""
s726_explore.py — اکتشافِ لایهٔ نو `S726`: «شوکِ میان‌کانالی» (Mid-Channel Shock) روی طلا
================================================================================
⚠️ سود فقط روی **نیمهٔ اولِ** داده (مسیرِ C). از نیمهٔ دوم فقط تعدادِ رویداد (S724-LAW).

مفهوم: خوشهٔ برندهٔ پروژه «شوکِ پذیرفته‌شده» (S965/S749/S1520/S1740) است. همهٔ آن‌ها
شوک را یا مستقل از مکان می‌گیرند یا **روی لبهٔ کانال** (سقف/کفِ تازه: S526/S1520).
S726 بُعدِ نسنجیده را می‌آزماید: **جایگاهِ شوک درونِ کانالِ دانچینِ W-کندلی**.
  pos = (close_shock − low_W) / (high_W − low_W)     (کانالِ علّی تا کندلِ قبل)
  شوکِ صعودی «میان‌کانالی» ⇔ pos ≤ 1−m  (هنوز تا سقفِ کانال فضای m×عرض دارد)
  شوکِ نزولی «میان‌کانالی» ⇔ pos ≥ m
فرضیه (Kyle + فضای حرکت): شوکِ مطلعی که *دور از* لبهٔ کانال می‌زند، تا لبه مقاومتِ
ساختاری کم دارد ⇒ ادامه. شوکی که روی لبه می‌زند با عرضهٔ نهفتهٔ سقفِ کانال روبه‌روست.
  mode='mid'  : فقط شوک‌های میان‌کانالی (فرضیهٔ اصلی)
  mode='edge' : مکمل — شوک‌های لبه‌ای (pos>1−m برای صعودی) ⇒ کنترلِ تفکیک‌گر (P1)

شوک: range[t] ≥ θ×ATR21[t−1] (علّی) + بدنهٔ پذیرفته ρ=|c−o|/(h−l) ≥ 0.618 (وام از S965،
منجمد، جست‌وجو نمی‌شود) + جهت = جهتِ بدنه. ورود در open کندلِ بعد.

نوبودگی (ممیزی 2026-09-04): «mid-channel / middle of channel / channel position ×
shock / room to run» → ۰ پروندهٔ شوک‌محور (S325 INCOMPLETE و S219 روی M5–H4 مفهومِ
کانالِ بروکس بدون شوک). S1621 «حاشیهٔ رکورد» است (لبه، نه میانه).

هندسه: SL=k×ATR89ِ میانه، TP=rr×SL، max_hold=34.
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
from tools.s725_explore import atr_causal, uncond_wr_sides, WARMUP, N_UNCOND  # noqa: E402

ASSET = 'XAUUSD'
OUT = os.path.join(ROOT, 'results', '_s726_explore')

THETAS = (1.618, 2.0)          # آستانهٔ شوک (ATR21)
WS = (55, 144)                 # عرضِ کانالِ دانچین
MS = (0.382, 0.5)              # کمینهٔ فضای حرکت تا لبه (کسرِ عرضِ کانال)
KS = (1.3, 2.1)
RRS = (1.0, 1.5)
MODES = ('mid', 'edge')
# سلول‌ها: 2×2×2×2×2×2 = 64 در هر TF
RHO = 0.618
MH = 34
SEED = 20260904


def shock_position_signals(df: pd.DataFrame, theta: float, w: int, m: float, mode: str):
    o = df['open'].to_numpy(float); h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float); c = df['close'].to_numpy(float)
    n = len(c)
    a = atr_causal(df)                                   # ATR21 تا کندلِ قبل
    rng = h - l
    body = np.abs(c - o)
    shock = (rng >= theta * a) & ~np.isnan(a) & (rng > 0)
    accepted = np.divide(body, rng, out=np.zeros(n), where=rng > 0) >= RHO
    hi = pd.Series(h).rolling(w).max().shift(1).to_numpy(float)   # کانالِ علّی
    lo = pd.Series(l).rolling(w).min().shift(1).to_numpy(float)
    width = hi - lo
    pos = np.divide(c - lo, width, out=np.full(n, np.nan), where=width > 0)
    ok = shock & accepted & ~np.isnan(pos)
    ok[:WARMUP] = False
    up = ok & (c > o); dn = ok & (c < o)
    if mode == 'mid':
        longs = up & (pos <= 1.0 - m)
        shorts = dn & (pos >= m)
    else:
        longs = up & (pos > 1.0 - m)
        shorts = dn & (pos < m)
    return longs, shorts


def event_stability(df_full, theta, w, m):
    ls, ss = shock_position_signals(df_full, theta, w, m, 'mid')
    hf = len(df_full) // 2
    n1 = int(ls[:hf].sum() + ss[:hf].sum()); n2 = int(ls[hf:].sum() + ss[hf:].sum())
    return dict(theta=theta, w=w, m=m, first_half=n1, second_half=n2,
                ratio=round(n2 / n1, 3) if n1 else None)


def explore_tf(tf: str):
    d = fd.load_fast(ASSET, tf)
    df_full = fd.as_dataframe(d)
    src = d['src']
    stability = [event_stability(df_full, th, w, m) for th in THETAS for w in WS for m in MS]
    half = len(df_full) // 2
    df = df_full.iloc[:half].reset_index(drop=True)
    atr = atr_median(df)
    pip = se.ASSETS[ASSET]['pip']
    rng_ = np.random.default_rng(SEED)
    unc = {}
    for k in KS:
        sl = round(k * atr / pip, 1)
        if sl <= 6.6:
            continue
        for rr in RRS:
            tp = round(sl * rr, 1)
            unc[(sl, tp)] = uncond_wr_sides(df, sl, tp, MH, rng_)
    rows = []
    for th in THETAS:
        for w in WS:
            for m in MS:
                for mode in MODES:
                    ls, ss = shock_position_signals(df, th, w, m, mode)
                    n_ev = int(ls.sum() + ss.sum())
                    for (sl, tp), (uwl, uws) in unc.items():
                        tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=MH, allow_overlap=False)
                        base = dict(tf=tf, theta=th, w=w, m=m, mode=mode, sl=sl, tp=tp,
                                    k=round(sl / (atr / pip), 2), rr=round(tp / sl, 2), n=len(tr), n_events=n_ev)
                        if len(tr) < 30:
                            rows.append(dict(base, note='n<30')); continue
                        nl = int((tr['direction'] == 'long').sum()); ns = int((tr['direction'] == 'short').sum())
                        wl = 100.0 * float((tr.loc[tr['direction'] == 'long', 'pnl_pip'] > 0).mean()) if nl else float('nan')
                        ws_ = 100.0 * float((tr.loc[tr['direction'] == 'short', 'pnl_pip'] > 0).mean()) if ns else float('nan')
                        wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                        u = (uwl * nl + uws * ns) / (nl + ns); lift = wr - u
                        pos_ = float(tr.loc[tr['pnl_pip'] > 0, 'pnl_pip'].sum())
                        neg = float(-tr.loc[tr['pnl_pip'] < 0, 'pnl_pip'].sum())
                        pf = pos_ / neg if neg > 0 else float('inf')
                        mid = len(tr) // 2
                        rows.append(dict(base, n_long=nl, n_short=ns, wr=round(wr, 2), uncond=round(u, 2),
                                         lift=round(lift, 2),
                                         lift_long=round(wl - uwl, 2) if nl else None,
                                         lift_short=round(ws_ - uws, 2) if ns else None,
                                         lift_sqrt_n=round(lift * np.sqrt(len(tr)), 1), pf=round(pf, 3),
                                         exp_pip=round(float(tr['pnl_pip'].mean()), 3),
                                         q1=round(100.0 * float((tr['pnl_pip'].iloc[:mid] > 0).mean()), 1),
                                         q2=round(100.0 * float((tr['pnl_pip'].iloc[mid:] > 0).mean()), 1)))
    return dict(tf=tf, src=src, bars_full=len(df_full), bars_half=len(df), atr89_med_pip=round(atr / pip, 2),
                max_hold=MH, rho=RHO, n_uncond=N_UNCOND, seed=SEED, event_stability=stability, rows=rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    tfs = sys.argv[1:] or ['H4']
    for tf in tfs:
        print(f'── S726 اکتشاف · {ASSET}-{tf} · سود فقط نیمهٔ اول ──', flush=True)
        res = explore_tf(tf)
        print(f"src={res['src']} bars_full={res['bars_full']} ATR89={res['atr89_med_pip']}pip", flush=True)
        st = [s for s in res['event_stability'] if s['w'] == 55 and s['m'] == 0.382]
        print('  پایداری (w55,m.382): ' + ' | '.join(f"θ{s['theta']}: {s['first_half']}→{s['second_half']} r={s['ratio']}" for s in st), flush=True)
        for mode in MODES:
            pos = [r for r in res['rows'] if r.get('lift') is not None and r['mode'] == mode]
            print(f'  [{mode}] top by lift√n:', flush=True)
            for r in sorted(pos, key=lambda x: -x['lift_sqrt_n'])[:5]:
                flag = '★' if r['lift_sqrt_n'] >= 78 else ' '
                print(f"   {flag} θ={r['theta']} w={r['w']} m={r['m']} k={r['k']} rr={r['rr']} n={r['n']} (L{r['n_long']}/S{r['n_short']}) "
                      f"lift={r['lift']:+.2f} (L{r['lift_long']}/S{r['lift_short']}) lift√n={r['lift_sqrt_n']} PF={r['pf']} Q1/Q2={r['q1']}/{r['q2']}", flush=True)
        with open(os.path.join(OUT, f'explore_{tf}.json'), 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f'  ذخیره شد → results/_s726_explore/explore_{tf}.json', flush=True)


if __name__ == '__main__':
    main()
