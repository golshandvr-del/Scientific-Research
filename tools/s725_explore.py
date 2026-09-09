# -*- coding: utf-8 -*-
"""
s725_explore.py — اکتشافِ لایهٔ نو `S725`: «شوکِ ناکام» (Failed Shock) روی طلا
================================================================================
⚠️ اکتشافِ سود فقط روی **نیمهٔ اولِ** داده (مسیرِ C). از نیمهٔ دوم فقط **تعدادِ رویداد**
شمرده می‌شود (S724-LAW: پایداریِ جمعیتِ رویداد — بدون نگاه به نتیجهٔ معامله).

مفهوم: کندلِ شوک  S = بار t−1 با دامنهٔ ≥ θ×ATR21[t−2] (علّی)؛
        کندلِ ناکام‌کننده F = بار t که **تمامِ بدنهٔ S را می‌بلعد**:
          شوکِ صعودی (close_S>open_S) ناکام ⇔ close_F < open_S
          شوکِ نزولی ناکام ⇔ close_F > open_S
کایل ۱۹۸۵: اثرِ قیمتیِ جریانِ مطلع دائمی است؛ شوکی که در همان کندلِ بعد به‌طورِ کامل
برگردانده می‌شود، اثرِ **گذرا** داشته (نویز/لیکوییدیشن/اسپایکِ خبری) و بازارساز
موجودی را در جهتِ برگشت تخلیه می‌کند ⇒ ادامهٔ حرکتِ F.
  mode='with'    : هم‌جهتِ F (برگشتِ شوک ادامه می‌یابد)
  mode='against' : هم‌جهتِ S (شوک بعد از تنفس ادامه می‌یابد)   ← داده تصمیم می‌گیرد

نوبودگی (ممیزی 2026-09-04): «failed shock / shock engulf / shock retrace» ۰ پرونده.
متمایز از S964 (شوکِ دومِ هم‌جهت)، S967 (پذیرشِ آرام پس از شوک)، S792/S972 (فِیدِ
مستقیمِ شوک بدون کندلِ تأیید)، S965/S1520 (شوک با بدنهٔ قاطع ⇒ ادامه؛ اینجا شوک
**رد** شده است)، S652 (رشتهٔ follow-through).

غربال: lift در برابرِ نولِ غیرشرطیِ سمت‌کلیددار (نه حاشیهٔ BE) + سدّ lift·√n≥78.
هندسه: SL=k×ATR89ِ میانه، TP=rr×SL، max_hold=34 کندل.
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
OUT = os.path.join(ROOT, 'results', '_s725_explore')

THETAS = (1.618, 2.0, 2.618)    # آستانهٔ شوک در واحدِ ATR21
KS = (1.3, 2.1, 3.4)
RRS = (1.0, 1.5, 2.0)
MODES = ('with', 'against')
# سلول‌ها: 3×3×3×2 = 54 در هر TF

W_ATR = 21
WARMUP = 250
MH = 34
N_UNCOND = 6000
SEED = 20260904


def atr_causal(df: pd.DataFrame, w: int = W_ATR) -> np.ndarray:
    h, l, c = df['high'], df['low'], df['close']
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(w).mean().shift(1).to_numpy(float)   # ATR تا کندلِ قبل


def failed_shock_signals(df: pd.DataFrame, theta: float, mode: str):
    """سیگنال روی کندلِ t (کندلِ ناکام‌کننده) ⇒ ورود در openِ t+1."""
    o = df['open'].to_numpy(float)
    h = df['high'].to_numpy(float)
    l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    n = len(c)
    a = atr_causal(df)                           # a[t-1] = ATR21 تا t-2
    rng = h - l
    shock = np.zeros(n, bool)
    shock[1:] = rng[:-1] >= theta * a[:-1]       # بار t-1 شوک است
    shock &= ~np.isnan(np.roll(a, 1))
    up_s = np.zeros(n, bool); dn_s = np.zeros(n, bool)
    up_s[1:] = c[:-1] > o[:-1]                   # شوکِ صعودی در t-1
    dn_s[1:] = c[:-1] < o[:-1]
    fail_up = np.zeros(n, bool); fail_dn = np.zeros(n, bool)
    fail_up[1:] = c[1:] < o[:-1]                 # بستِ F زیرِ openِ شوکِ صعودی
    fail_dn[1:] = c[1:] > o[:-1]
    ev_short = shock & up_s & fail_up            # شوکِ صعودی ناکام ⇒ F نزولی
    ev_long = shock & dn_s & fail_dn             # شوکِ نزولی ناکام ⇒ F صعودی
    ev_short[:WARMUP] = False; ev_long[:WARMUP] = False
    if mode == 'with':
        return ev_long, ev_short
    return ev_short, ev_long


def event_stability(df_full: pd.DataFrame, theta: float) -> dict:
    """S724-LAW: فقط شمارشِ رویداد در دو نیمه — هیچ معامله‌ای شبیه‌سازی نمی‌شود."""
    ls, ss = failed_shock_signals(df_full, theta, 'with')
    h = len(df_full) // 2
    n1 = int(ls[:h].sum() + ss[:h].sum()); n2 = int(ls[h:].sum() + ss[h:].sum())
    return dict(theta=theta, first_half=n1, second_half=n2,
                ratio=round(n2 / n1, 3) if n1 else None)


def uncond_wr_sides(df, sl, tp, mh, rng):
    n = len(df)
    picks = rng.integers(WARMUP, n - mh - 2, N_UNCOND)
    m = np.zeros(n, bool); m[picks] = True
    z = np.zeros(n, bool)
    ul = se.simulate_trades(df, m, z, sl, tp, ASSET, max_hold=mh, allow_overlap=True)
    us = se.simulate_trades(df, z, m, sl, tp, ASSET, max_hold=mh, allow_overlap=True)
    return (100.0 * float((ul['pnl_pip'] > 0).mean()),
            100.0 * float((us['pnl_pip'] > 0).mean()))


def explore_tf(tf: str):
    d = fd.load_fast(ASSET, tf)
    df_full = fd.as_dataframe(d)
    src = d['src']
    stability = [event_stability(df_full, th) for th in THETAS]
    half = len(df_full) // 2
    df = df_full.iloc[:half].reset_index(drop=True)   # ⚠️ سود فقط نیمهٔ اول
    atr = atr_median(df)
    pip = se.ASSETS[ASSET]['pip']
    rng = np.random.default_rng(SEED)
    unc = {}
    for k in KS:
        sl = round(k * atr / pip, 1)
        if sl <= 6.6:
            continue
        for rr in RRS:
            tp = round(sl * rr, 1)
            unc[(sl, tp)] = uncond_wr_sides(df, sl, tp, MH, rng)
    rows = []
    for th in THETAS:
        for mode in MODES:
            ls, ss = failed_shock_signals(df, th, mode)
            n_ev = int(ls.sum() + ss.sum())
            for (sl, tp), (uwl, uws) in unc.items():
                tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET, max_hold=MH, allow_overlap=False)
                if len(tr) < 30:
                    rows.append(dict(tf=tf, theta=th, mode=mode, sl=sl, tp=tp, n=len(tr),
                                     n_events=n_ev, note='n<30'))
                    continue
                nl = int((tr['direction'] == 'long').sum()); ns = int((tr['direction'] == 'short').sum())
                wl = 100.0 * float((tr.loc[tr['direction'] == 'long', 'pnl_pip'] > 0).mean()) if nl else float('nan')
                ws = 100.0 * float((tr.loc[tr['direction'] == 'short', 'pnl_pip'] > 0).mean()) if ns else float('nan')
                wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                u = (uwl * nl + uws * ns) / (nl + ns)
                lift = wr - u
                pos = float(tr.loc[tr['pnl_pip'] > 0, 'pnl_pip'].sum())
                neg = float(-tr.loc[tr['pnl_pip'] < 0, 'pnl_pip'].sum())
                pf = pos / neg if neg > 0 else float('inf')
                mid = len(tr) // 2
                q1 = 100.0 * float((tr['pnl_pip'].iloc[:mid] > 0).mean())
                q2 = 100.0 * float((tr['pnl_pip'].iloc[mid:] > 0).mean())
                rows.append(dict(tf=tf, theta=th, mode=mode, k=round(sl / (atr / pip), 2), rr=round(tp / sl, 2),
                                 sl=sl, tp=tp, n=len(tr), n_long=nl, n_short=ns, n_events=n_ev,
                                 wr=round(wr, 2), uncond=round(u, 2), lift=round(lift, 2),
                                 lift_long=round(wl - uwl, 2) if nl else None,
                                 lift_short=round(ws - uws, 2) if ns else None,
                                 lift_sqrt_n=round(lift * np.sqrt(len(tr)), 1),
                                 pf=round(pf, 3), exp_pip=round(float(tr['pnl_pip'].mean()), 3),
                                 q1=round(q1, 1), q2=round(q2, 1)))
    return dict(tf=tf, src=src, bars_full=len(df_full), bars_half=len(df),
                atr89_med_pip=round(atr / pip, 2), max_hold=MH, n_uncond=N_UNCOND, seed=SEED,
                event_stability=stability, rows=rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    tfs = sys.argv[1:] or ['H4']
    for tf in tfs:
        print(f'── S725 اکتشاف · {ASSET}-{tf} · سود فقط نیمهٔ اول ──', flush=True)
        res = explore_tf(tf)
        print(f"src={res['src']} bars_full={res['bars_full']} ATR89={res['atr89_med_pip']}pip mh={MH}", flush=True)
        print('  پایداریِ رویداد (S724-LAW): ' + ' | '.join(
            f"θ{s['theta']}: {s['first_half']}→{s['second_half']} (r={s['ratio']})" for s in res['event_stability']), flush=True)
        pos = [r for r in res['rows'] if r.get('lift') is not None and r['lift'] > 0]
        for r in sorted(pos, key=lambda x: -x['lift_sqrt_n'])[:8]:
            flag = '★' if r['lift_sqrt_n'] >= 78 else ' '
            print(f"  {flag} θ={r['theta']} {r['mode']:7} k={r['k']} rr={r['rr']} n={r['n']} (L{r['n_long']}/S{r['n_short']}) "
                  f"WR={r['wr']} unc={r['uncond']} lift={r['lift']:+.2f} (L{r['lift_long']}/S{r['lift_short']}) "
                  f"lift√n={r['lift_sqrt_n']} PF={r['pf']} Q1/Q2={r['q1']}/{r['q2']}", flush=True)
        if not pos:
            print('  هیچ سلولِ lift مثبتی نیست.', flush=True)
        with open(os.path.join(OUT, f'explore_{tf}.json'), 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f'  ذخیره شد → results/_s725_explore/explore_{tf}.json', flush=True)


if __name__ == '__main__':
    main()
