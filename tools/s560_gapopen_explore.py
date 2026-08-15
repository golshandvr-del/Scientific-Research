# -*- coding: utf-8 -*-
"""
s560_gapopen_explore.py — اکتشافِ S560 (لایهٔ گپ-بازگشایی XAUUSD) — فقط نیمهٔ اول

پیش‌ثبت: results/S560_PREREG_GAPOPEN_XAUUSD_MISSION1.md (commit 0f0eab53)

🔴 قانون مسیر C: این ابزار فقط کندل‌های **قبل از 2018-10-20** را می‌بیند.
   نیمهٔ دوم تا داوری نهایی دست‌نخورده می‌ماند. هر عددِ اینجا «اکتشافی» است.

گاردهای ارثی (با نام باگ مولدشان — سنت S437):
  • BUG-DATASETDRIFT → داده فقط از tools/s434_fast_data.load_fast؛ src چاپ می‌شود.
  • BUG-GEOMDRIFT    → هندسه/آستانه‌های منتخب در JSON ذخیره و داور از همان فایل می‌خواند.
  • دام DST مارس     → مرز روز = گپ زمانی >=1800s؛ هرگز hour==1.
  • آستانهٔ علّی      → چندک گپ منفی فقط از گپ‌های منفیِ *قبل از امروز* (expanding).

اجرا:  python3 tools/s560_gapopen_explore.py M1   (یک TF در هر اجرا — قانون اندک‌اندک)
خروجی: results/_s560_explore/<TF>.json + جدول متنی
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import s434_fast_data as fd  # noqa: E402

SPLIT_UTC = '2018-10-20'          # مرز پیش‌ثبت‌شدهٔ مسیر C
SPREAD_USD = 0.33                 # هزینهٔ رفت‌وبرگشت $/oz (اسپرد؛ کمیسیون=۰)
QUANTILES = (50, 60, 70, 80)      # آستانه‌های پیش‌ثبت‌شده
HOLDS = (1, 2, 4, 8)              # خروج زمانی: k کندلِ همین TF
OUT_DIR = os.path.join(ROOT, 'results', '_s560_explore')


TF_SEC = {'M1': 60, 'M5': 300, 'M15': 900, 'M30': 1800, 'H1': 3600}


def day_breaks(t: np.ndarray, tf: str) -> np.ndarray:
    """اندیس i که کندل i آخرِ روز است و i+1 اولِ روزِ بعد.

    🔴 BUG-BRKTHRESH (کشف همین نشست، هنگام اجرای M30): قاعدهٔ Handoff
    «گپ زمانی > ۳۰ دقیقه» برای M15 نوشته شده بود. در M30 فاصلهٔ *عادی*
    دو کندل خودش 1800s است ⇒ شرط `>=1800` تقریباً هر کندل را مرز روز
    می‌شمرد (ده‌ها هزار «روز» جعلی ⇒ حلقهٔ چندکِ علّی منفجر شد و
    اجرا همیشگی ماند). تعمیم درستِ قاعده: مرز روز = گپِ اکیداً بزرگ‌تر
    از فاصلهٔ عادی کندل (1.5×) و دست‌کم 1800s. برای M1..M15 رفتار
    عیناً معادلِ قبلی می‌ماند (نتایج M1/M5/M15 دست‌نخورده معتبرند)؛
    فقط M30/H1 اصلاح می‌شوند.
    """
    thr = max(1800.0, 1.5 * TF_SEC[tf])
    return np.where(np.diff(t) > thr)[0]


def causal_neg_gap_quantile(gaps: np.ndarray, q: float, weekend: np.ndarray,
                            split_weekend: bool) -> np.ndarray:
    """آستانهٔ علّی: چندکِ q از |گپ‌های منفیِ| روزهای *قبلی* (expanding).

    split_weekend=True ⇒ چندک جداگانه برای مرزهای آخرهفته و میان‌هفته
    (کشف فاز ۱۲: گپ دوشنبه ~۸×). خروجی: آستانهٔ مثبت |گپ| برای هر روز؛
    NaN تا وقتی حداقل ۲۰ نمونهٔ تاریخی جمع شود (بدون حکم در بی‌دادگی).
    """
    n = len(gaps)
    thr = np.full(n, np.nan)
    if split_weekend:
        groups = (weekend, ~weekend)
    else:
        groups = (np.ones(n, bool),)
    for g in groups:
        hist: list[float] = []
        idx = np.flatnonzero(g)
        for i in idx:
            if len(hist) >= 20:
                thr[i] = float(np.percentile(hist, q))
            if gaps[i] < 0:
                hist.append(abs(gaps[i]))
    return thr


def explore(tf: str) -> dict:
    d = fd.load_fast('XAUUSD', tf)
    print(f"src={d['src']}  n={d['n_bars']}  {d['first_utc']} → {d['last_utc']}")
    t, o, h, c = d['time'], d['open'], d['high'], d['close']
    n = len(t)

    import calendar
    split_ts = calendar.timegm((2018, 10, 20, 0, 0, 0))
    split_bar = int(np.searchsorted(t, split_ts))
    print(f"split_bar={split_bar} ({split_bar/n:.1%} of data)  [مسیر C: فقط قبل از این]")

    brk = day_breaks(t, tf)
    first = brk + 1                       # اندیس کندل اول روز
    first = first[first < n - 20]         # حاشیهٔ امن انتها
    prev_close = c[first - 1]
    gaps = o[first] - prev_close
    # مرز آخرهفته: گپ زمانی > 24h
    weekend = (t[first] - t[first - 1]) > 86400

    # 🔴 مسیر C: فقط روزهایی که *کل* پنجرهٔ معامله‌شان قبل از split است
    in_first_half = first + max(HOLDS) < split_bar

    results = []
    for q in QUANTILES:
        for sw in (False, True):
            thr = causal_neg_gap_quantile(gaps, q, weekend, sw)
            sig = (gaps < 0) & ~np.isnan(thr) & (np.abs(gaps) > thr) & in_first_half
            sidx = np.flatnonzero(sig)
            if len(sidx) < 30:
                results.append(dict(q=q, split_weekend=sw, exit='-', n=int(len(sidx)),
                                    note='n<30 — بدون حکم'))
                continue
            fb = first[sidx]
            years = ((t[fb] // 31556952) + 1970).astype(int)  # سال تقریبی برای شمارش +yrs

            def rep(tag, pnl_arr, entry_tag):
                pnl_arr = np.asarray(pnl_arr, float)
                m = len(pnl_arr)
                if m < 30:
                    return
                se_ = pnl_arr.std(ddof=1) / np.sqrt(m)
                tt = pnl_arr.mean() / se_ if se_ > 0 else 0.0
                wr = float((pnl_arr > 0).mean())
                ys = {}
                for y, p in zip(years[:m], pnl_arr):
                    ys[int(y)] = ys.get(int(y), 0.0) + float(p)
                pos = sum(1 for v in ys.values() if v > 0)
                results.append(dict(q=q, split_weekend=sw, exit=tag, entry=entry_tag,
                                    n=m, avg=round(float(pnl_arr.mean()), 4),
                                    wr=round(wr, 4), t=round(float(tt), 3),
                                    net=round(float(pnl_arr.sum()), 1),
                                    pos_years=f"{pos}/{len(ys)}"))

            for hold in HOLDS:
                # E0: ورود open کندل اول روز (گپ در همان لحظه معلوم — علّی)
                rep(f'hold{hold}', c[fb + hold - 1] - o[fb] - SPREAD_USD, 'E0')
                # E1: ورود open کندل دوم (سازگار با موتور رسمی)
                rep(f'hold{hold}', c[fb + hold] - o[fb + 1] - SPREAD_USD, 'E1')

            # واریانت گپ-فیل: TP=close دیروز، سقف = تا مرز روز بعد (حداکثر ۱۴۴۰ دقیقه)
            cap = {'M1': 1440, 'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24}[tf]
            pnl_gf = []
            for k, i in enumerate(fb):
                tgt = prev_close[sidx[k]]
                j1 = min(i + cap, n - 1)
                seg_h = h[i:j1]
                hit = np.flatnonzero(seg_h >= tgt)
                exit_px = tgt if len(hit) else c[j1 - 1]
                pnl_gf.append(exit_px - o[i] - SPREAD_USD)
            rep('gapfill', pnl_gf, 'E0')

    os.makedirs(OUT_DIR, exist_ok=True)
    out = dict(tf=tf, src=d['src'], split_bar=split_bar, split_utc=SPLIT_UTC,
               n_bars=int(n), n_day_breaks=int(len(brk)), spread_usd=SPREAD_USD,
               results=results)
    path = os.path.join(OUT_DIR, f'{tf}.json')
    with open(path, 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"saved → {path}")

    # جدول مرتب‌شده بر حسب t
    rows = [r for r in results if 't' in r]
    rows.sort(key=lambda r: -r['t'])
    print(f"\n=== {tf} — بالاترین ۱۲ بازو (نیمهٔ اول، خالص از اسپرد $0.33) ===")
    print(f"{'q':>3} {'wknd':>5} {'exit':>8} {'ent':>3} {'n':>5} {'avg$':>8} "
          f"{'WR':>6} {'t':>6} {'+yrs':>6}")
    for r in rows[:12]:
        print(f"{r['q']:>3} {str(r['split_weekend']):>5} {r['exit']:>8} "
              f"{r.get('entry','-'):>3} {r['n']:>5} {r['avg']:>8.3f} "
              f"{r['wr']:>6.3f} {r['t']:>6.2f} {r['pos_years']:>6}")
    return out


if __name__ == '__main__':
    tf = sys.argv[1] if len(sys.argv) > 1 else 'M1'
    explore(tf)
