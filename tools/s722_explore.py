# -*- coding: utf-8 -*-
"""
s722_explore.py — اکتشافِ لایهٔ نو `S722`: «لنگرِ بازشدنِ هفتگی» روی طلا
================================================================================
⚠️ فقط روی **نیمهٔ اولِ** داده (مسیرِ چندگانگیِ C). نیمهٔ دوم دست‌نخورده می‌ماند.

مفهوم: قیمتِ بازشدنِ هفته (اولین کندلِ هفتهٔ دوشنبه-مبنا) لنگرِ ذهنیِ بازار است.
  رویداد: **اولین** عبورِ لبه‌ایِ close از `weekly_open ± thr×ATR(89)`
  در هر هفته و هر سمت (debounce: یک سیگنال/هفته/سمت — الگوی S344/S692).
  mode='cont': عبور از بالا ⇒ LONG (هفتهٔ روندی) · mode='rev': fade.
  هر دو جهت آزموده می‌شود؛ داده تصمیم می‌گیرد.

نوبودگی (ممیزی 2026-08-20): grep کامل results/*.md — «weekly open» صفر پرونده.
  متمایز از S344 (لنگرِ روزانه، ACCEPT)، S692ِ همکار (PDH/PDL روزِ قبل)،
  S560/S404 (گپ)، S810 (گپِ آخرهفته، REJECT)، S890 (شکستِ کانالِ غلتان، REJECT
  — اینجا لنگرِ ثابتِ تقویمی است نه کانالِ غلتان).

هندسه: SL = k×ATR(89)ِ میانه، TP = rr×SL (rr≥1). max_hold = معادلِ ۷۲ ساعت
بر حسبِ کندلِ همان TF (علاجِ BUG-TFM) — تا پایانِ افقِ هفتگی.
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
OUT = os.path.join(ROOT, 'results', '_s722_explore')

# ── فضای جست‌وجو (شمارش صادقانه برای n_trials پیش‌ثبت) ────────────────────
THRS = (0.5, 1.0, 1.5, 2.0)     # آستانهٔ فاصله از weekly open در واحد ATR(89)
KS = (1.3, 2.1, 3.4)            # ضریب SL
RRS = (1.0, 1.5, 2.0)           # TP/SL — هرگز <1
MODES = ('cont', 'rev')
# سلول‌ها: 4×3×3×2 = 72 در هر TF


def week_id(t: np.ndarray) -> np.ndarray:
    """شاخصِ هفتهٔ دوشنبه-مبنا از epoch-seconds (۱۹۷۰-۰۱-۰۱ پنجشنبه بود)."""
    d = (t // 86400).astype(np.int64)
    return (d + 3) // 7


def weekly_anchor_signals(df: pd.DataFrame, thr_pip: float):
    """اولین عبورِ لبه‌ایِ close از weekly_open±thr در هر هفته/سمت.

    خروجی: (up_events, dn_events) — up یعنی close برای اولین بار در هفته
    بالای open+thr بسته شد؛ dn آینه. بدونِ look-ahead: weekly_open همان
    openِ اولین کندلِ هفته است که از لحظهٔ شروعِ هفته معلوم است.
    """
    t = df['time'].to_numpy(np.int64)
    o = df['open'].to_numpy(float)
    c = df['close'].to_numpy(float)
    w = week_id(t)
    # openِ اولین کندلِ هر هفته، ffill روی کلِ هفته
    first = np.r_[True, w[1:] != w[:-1]]
    wo = pd.Series(np.where(first, o, np.nan)).ffill().to_numpy()
    pip = se.ASSETS[ASSET]['pip']
    up_state = c > wo + thr_pip * pip
    dn_state = c < wo - thr_pip * pip
    up = np.zeros(len(c), bool)
    dn = np.zeros(len(c), bool)
    # debounce: اولین رخداد هر هفته/سمت (حلقه روی مرزهای هفته — سریع با numpy)
    idx = np.flatnonzero(first)
    bounds = np.r_[idx, len(c)]
    for i in range(len(idx)):
        a, b = bounds[i], bounds[i + 1]
        su = np.flatnonzero(up_state[a:b])
        sd = np.flatnonzero(dn_state[a:b])
        if su.size:
            up[a + su[0]] = True
        if sd.size:
            dn[a + sd[0]] = True
    return up, dn


def bars_per_hour(df: pd.DataFrame) -> float:
    d = np.median(np.diff(df['time'].values.astype(np.float64)))
    return 3600.0 / d if d > 0 else 1.0


def explore_tf(tf: str):
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    half = len(df) // 2
    df = df.iloc[:half].reset_index(drop=True)   # ⚠️ فقط نیمهٔ اول
    src = d['src']
    atr = atr_median(df)
    pip = se.ASSETS[ASSET]['pip']
    bph = bars_per_hour(df)
    mh = max(4, int(round(72 * bph)))            # ۷۲ ساعت در کندلِ همان TF
    rows = []
    for thr in THRS:
        thr_pip = round(thr * atr / pip, 1)
        up, dn = weekly_anchor_signals(df, thr_pip)
        n_ev = int(up.sum() + dn.sum())
        for mode in MODES:
            ls, ss = (up, dn) if mode == 'cont' else (dn, up)
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
        print(f'── S722 اکتشاف · {ASSET}-{tf} · فقط نیمهٔ اول ──', flush=True)
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
        print(f'  ذخیره شد → results/_s722_explore/explore_{tf}.json', flush=True)


if __name__ == '__main__':
    main()
