# -*- coding: utf-8 -*-
"""
s560_freeze_thresholds.py — انجمادِ آستانه‌های علّیِ S560 برای مصرفِ زنده (سایت)

مسئله‌ای که این ابزار حل می‌کند
--------------------------------
لایهٔ S560 (`results/S560_GapOpenNegGap_Xauusd_M1M5M15M30H1_rqs2_96_ACCEPT.md`،
کارتِ `XAUUSD-M5` با `RQS2 = 96.0`) آستانهٔ گپِ خود را با **چندکِ انبساطیِ علّی**
(expanding causal quantile) می‌سازد: آستانهٔ امروز = چندکِ q۸۰ از |گپ‌های منفیِ|
همهٔ روزهای *قبل*. این تعریف روی ۱۵.۶ سالِ دادهٔ MT5 معنا دارد.

اما سایت روی کارتِ M5 فقط `range='5d'` کندل از Yahoo می‌گیرد (نگاشتِ
`GOLD_TF['XAUUSD-M5']` در `web_tool/src/index.tsx`) ⇒ حداکثر ۴–۵ مرزِ روز.
محاسبهٔ چندکِ انبساطی از ۵ نمونه، **لایهٔ دیگری** است نه S560: قاعدهٔ اصلی
تا جمع‌شدنِ ۲۰ نمونهٔ تاریخی `NaN` می‌دهد و اصلاً سیگنال صادر نمی‌کند.

⇒ راهِ درست (و تنها راهِ سازگار با «قانونِ MTF در جهتِ عکسش»): آستانه از
   **همان دادهٔ آزموده‌شده** یک بار محاسبه و **منجمد** شود، سپس سایت آن عددِ
   ثابت را مصرف کند. این کارِ «برازشِ نو» نیست: هیچ پارامتری جست‌وجو نمی‌شود؛
   فقط آخرین مقدارِ همان تابعِ علّیِ پیش‌ثبت‌شده استخراج می‌شود.

گاردهای ارثی که این ابزار رعایت می‌کند
--------------------------------------
• BUG-GEOMDRIFT   → `q`/`sw`/`hold` از `results/_s560_arms/locked_config.json`
                    خوانده می‌شوند، هرگز دست‌نویس نمی‌شوند.
• BUG-BRKTHRESH   → مرزِ روز از `day_breaks` همان ماژولِ اکتشاف می‌آید
                    (آستانهٔ مقیاس‌پذیر با TF).
• آستانهٔ علّی      → `causal_neg_gap_quantile` عیناً بازاستفاده می‌شود؛ کدِ
                    آستانه بازنویسی **نمی‌شود** تا انحرافِ پیاده‌سازی ممکن نباشد.
• BUG-DATASETDRIFT → داده فقط از `tools.s434_fast_data.load_fast`؛ `src` چاپ
                    و در خروجی ثبت می‌شود.

اجرا:  python3 tools/s560_freeze_thresholds.py M5
خروجی: results/_s560_arms/frozen_thresholds_<TF>.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import s434_fast_data as fd                       # noqa: E402
from tools.s560_gapopen_explore import (                     # noqa: E402
    day_breaks, causal_neg_gap_quantile)

ARMS_DIR = os.path.join(ROOT, 'results', '_s560_arms')
LOCKED = os.path.join(ARMS_DIR, 'locked_config.json')


def freeze(tf: str) -> dict:
    with open(LOCKED, encoding='utf-8') as fh:
        locked = json.load(fh)
    if tf not in locked:
        raise SystemExit(f'TF {tf} در locked_config.json نیست')
    cfg = locked[tf]['cfg']
    q, sw, hold = float(cfg['q']), bool(cfg['sw']), int(cfg['hold'])

    d = fd.load_fast('XAUUSD', tf)
    print(f"src={d['src']}  n={d['n_bars']}  {d['first_utc']} → {d['last_utc']}")
    t, o, c = d['time'], d['open'], d['close']
    n = len(t)

    brk = day_breaks(t, tf)
    brk = brk[brk + 1 < n]
    gaps = o[brk + 1] - c[brk]
    weekend = (t[brk + 1] - t[brk]) > 86400

    thr = causal_neg_gap_quantile(gaps, q, weekend, sw)

    # آخرین آستانهٔ معتبرِ هر گروه = عددی که سایت از امروز به بعد مصرف می‌کند.
    def last_valid(group: np.ndarray) -> tuple[float, int]:
        idx = np.flatnonzero(group & ~np.isnan(thr))
        if len(idx) == 0:
            return float('nan'), 0
        return float(thr[idx[-1]]), int(len(idx))

    thr_we, n_we = last_valid(weekend)
    thr_wd, n_wd = last_valid(~weekend)

    # شمارشِ سیگنال‌ها با آستانهٔ منجمد در برابرِ آستانهٔ انبساطی — سنجهٔ صداقت:
    # اگر انجماد لایه را عوض می‌کرد، این دو عدد فاصلهٔ معنادار می‌گرفتند.
    frozen = np.where(weekend, thr_we, thr_wd)
    valid_exp = ~np.isnan(thr)
    sig_exp = int(((gaps < 0) & valid_exp & (np.abs(gaps) > thr)).sum())
    sig_frz = int(((gaps < 0) & valid_exp & (np.abs(gaps) > frozen)).sum())

    out = {
        'tf': tf,
        'cfg': {'q': q, 'split_weekend': sw, 'hold': hold},
        'frozen_threshold_usd': {
            'weekend': round(thr_we, 4),
            'weekday': round(thr_wd, 4),
        },
        'n_history_used': {'weekend': n_we, 'weekday': n_wd},
        'n_day_breaks': int(len(brk)),
        'signals_expanding_quantile': sig_exp,
        'signals_frozen_threshold': sig_frz,
        'geometry': locked[tf]['variants'][locked[tf]['picked']],
        'picked_arm': locked[tf]['picked'],
        'src': d['src'],
        'first_utc': d['first_utc'],
        'last_utc': d['last_utc'],
    }

    os.makedirs(ARMS_DIR, exist_ok=True)
    path = os.path.join(ARMS_DIR, f'frozen_thresholds_{tf}.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'\n→ {path}')
    return out


if __name__ == '__main__':
    freeze(sys.argv[1] if len(sys.argv) > 1 else 'M5')
