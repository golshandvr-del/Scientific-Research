# -*- coding: utf-8 -*-
"""
s720_explore.py — اکتشافِ لایهٔ نو `S720`: «تشدیدِ کششِ چندمقیاسی» روی طلا
================================================================================
⚠️ این فایل فقط روی **نیمهٔ اولِ** داده کار می‌کند (مسیرِ چندگانگیِ C).
   نیمهٔ دوم تا لحظهٔ داوریِ نهایی **دست‌نخورده** می‌ماند. هر عددی که اینجا
   تولید می‌شود «اکتشاف» است، نه «شاهد».

مفهومِ لایه (الهام از docs/indicators/variants.md، بخشِ zscore_fib):
  z(p) = (close − SMA(p)) / STD(p) روی سه پنجرهٔ فیبوناچی 21/55/89.
  رویدادِ ورود: هر سه z هم‌زمان از آستانهٔ ±thr عبور کنند (لبهٔ ورود به
  ناحیه، نه حالتِ ماندن در آن) ⇒ کششِ افراطیِ هم‌نوا در سه مقیاس ⇒
  ورودِ بازگشتی خلافِ جهتِ کشش. دو طرفه (long + short).

هندسه: SL = k×ATR(89)ِ میانهٔ همان TF (خودکالیبره، غیررند — ضدِ #6/#7)،
  TP = rr×SL با rr ∈ {1.0, 1.5} (متقارن یا سخاوتمندانه — هرگز TP<SL، ضدِ #8).
max_hold بر حسبِ **ساعت** (علاجِ BUG-TFM) — متناسب با پنجرهٔ 89 کندلی.

شمارشِ صادقانهٔ فضای جست‌وجو در همین فایل انجام و ذخیره می‌شود تا
پیش‌ثبت عددِ واقعی را گزارش کند.
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

ASSET = 'XAUUSD'
FIBS = (21, 55, 89)          # سه پنجرهٔ فیبوناچی — ثابت، جاروب نمی‌شوند
OUT = os.path.join(ROOT, 'results', '_s720_explore')

# ── فضای جست‌وجوی اکتشاف (شمارشِ صادقانه برای H5 در پیش‌ثبت) ────────────
THRS = (1.5, 2.0, 2.5)       # آستانهٔ z
KS = (0.8, 1.3, 2.1)         # ضریبِ SL نسبت به ATR(89) — غیررند
RRS = (1.0, 1.5)             # نسبتِ TP/SL — هرگز <1
HOLD_HOURS = None            # از پنجرهٔ 89 کندل مشتق می‌شود (زیر)


def zscore(c: np.ndarray, p: int) -> np.ndarray:
    s = pd.Series(c)
    m = s.rolling(p).mean()
    sd = s.rolling(p).std(ddof=0)
    return ((s - m) / sd.replace(0.0, np.nan)).to_numpy()


def atr_median(df: pd.DataFrame, p: int = 89) -> float:
    h = df['high'].astype(float)
    l = df['low'].astype(float)
    c = df['close'].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    a = tr.ewm(alpha=1.0 / p, adjust=False).mean()
    return float(np.nanmedian(a.to_numpy()))


def bars_per_hour(df: pd.DataFrame) -> float:
    d = np.median(np.diff(df['time'].values.astype(np.float64)))
    return 3600.0 / d if d > 0 else 1.0


def stretch_signals(c: np.ndarray, thr: float):
    """لبهٔ ورود به ناحیهٔ کششِ هم‌نوا. رویداد، نه حالت (درسِ S382)."""
    zs = [zscore(c, p) for p in FIBS]
    hi = np.ones(len(c), bool)
    lo = np.ones(len(c), bool)
    for z in zs:
        hi &= z > thr
        lo &= z < -thr
    hi = np.nan_to_num(hi.astype(float)).astype(bool)
    lo = np.nan_to_num(lo.astype(float)).astype(bool)
    hi_prev = np.roll(hi, 1); hi_prev[0] = False
    lo_prev = np.roll(lo, 1); lo_prev[0] = False
    short_sig = hi & ~hi_prev      # کششِ مثبتِ افراطی ⇒ SHORT بازگشتی
    long_sig = lo & ~lo_prev       # کششِ منفیِ افراطی ⇒ LONG بازگشتی
    return long_sig, short_sig


def uncond_wr(df, sl, tp, mh, seed=20260813, n_pick=20000):
    """WRِ غیرشرطیِ همان هندسه — مرجعِ ارزانِ lift برای مقایسهٔ اکتشافی."""
    n = len(df)
    rng = np.random.default_rng(seed)
    valid = np.zeros(n, bool)
    valid[250:n - mh - 1] = True
    vidx = np.flatnonzero(valid)
    pick = rng.choice(vidx, size=min(n_pick, len(vidx)), replace=False)
    m = np.zeros(n, bool); m[pick] = True
    z = np.zeros(n, bool)
    # هر دو سمت جدا (بازگشتی دوطرفه ⇒ مرجعِ هر سمت جدا لازم است)
    tl = se.simulate_trades(df, m, z, sl, tp, ASSET, max_hold=mh, allow_overlap=True)
    ts = se.simulate_trades(df, z, m, sl, tp, ASSET, max_hold=mh, allow_overlap=True)
    wl = 100.0 * float((tl['pnl_pip'] > 0).mean()) if len(tl) else None
    ws = 100.0 * float((ts['pnl_pip'] > 0).mean()) if len(ts) else None
    return wl, ws


def explore_tf(tf: str):
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    half = len(df) // 2
    df = df.iloc[:half].reset_index(drop=True)   # ⚠️ فقط نیمهٔ اول
    src = d['src']
    atr = atr_median(df)
    pip = se.ASSETS[ASSET]['pip']
    bph = bars_per_hour(df)
    # max_hold: زمانِ لازم برای بازگشت به میانگینِ پنجرهٔ میانی (55 کندل)
    mh = max(4, int(round(55)))    # 55 کندلِ همان TF — هم‌مقیاس با سیگنال
    rows = []
    c = df['close'].to_numpy(float)
    for thr in THRS:
        ls, ss = stretch_signals(c, thr)
        n_ev = int(ls.sum() + ss.sum())
        for k in KS:
            sl = round(k * atr / pip, 1)
            if sl <= 6.6:            # SL کمتر از ۲×هزینه = خودکشیِ H9
                continue
            for rr in RRS:
                tp = round(sl * rr, 1)
                tr = se.simulate_trades(df, ls, ss, sl, tp, ASSET,
                                        max_hold=mh, allow_overlap=False)
                if len(tr) < 30:
                    rows.append(dict(tf=tf, thr=thr, k=k, rr=rr, sl=sl, tp=tp,
                                     n=len(tr), note='n<30'))
                    continue
                wr = 100.0 * float((tr['pnl_pip'] > 0).mean())
                exp = float(tr['pnl_pip'].mean())
                nl = int((tr['direction'] == 'long').sum())
                ns = int((tr['direction'] == 'short').sum())
                wl = 100.0 * float((tr.loc[tr['direction'] == 'long', 'pnl_pip'] > 0).mean()) if nl else None
                ws = 100.0 * float((tr.loc[tr['direction'] == 'short', 'pnl_pip'] > 0).mean()) if ns else None
                be = 100.0 * (sl + 3.3) / (sl + tp)
                rows.append(dict(tf=tf, thr=thr, k=k, rr=rr, sl=sl, tp=tp,
                                 n=len(tr), n_long=nl, n_short=ns,
                                 wr=round(wr, 2), wr_long=None if wl is None else round(wl, 2),
                                 wr_short=None if ws is None else round(ws, 2),
                                 be=round(be, 2), margin=round(wr - be, 2),
                                 exp_pip=round(exp, 3), n_events=n_ev))
    return dict(tf=tf, src=src, bars_half=len(df), atr89_med_pip=round(atr / pip, 2),
                bars_per_hour=round(bph, 2), max_hold=mh, rows=rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    tfs = sys.argv[1:] or ['M1']
    for tf in tfs:
        print(f'── S720 اکتشاف · {ASSET}-{tf} · فقط نیمهٔ اول ──', flush=True)
        res = explore_tf(tf)
        print(f"src={res['src']} bars={res['bars_half']} "
              f"ATR89={res['atr89_med_pip']}pip mh={res['max_hold']}", flush=True)
        for r in res['rows']:
            if r.get('note'):
                print(f"  thr={r['thr']} k={r['k']} rr={r['rr']} SL={r['sl']} → {r['note']} (n={r['n']})")
                continue
            print(f"  thr={r['thr']} k={r['k']} rr={r['rr']} SL={r['sl']}/TP={r['tp']} "
                  f"n={r['n']} (L{r['n_long']}/S{r['n_short']}) WR={r['wr']}% "
                  f"BE={r['be']}% حاشیه={r['margin']}pp exp={r['exp_pip']}pip", flush=True)
        with open(os.path.join(OUT, f'explore_{tf}.json'), 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
        print(f'  ذخیره شد → results/_s720_explore/explore_{tf}.json', flush=True)


if __name__ == '__main__':
    main()
