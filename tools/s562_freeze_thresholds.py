# -*- coding: utf-8 -*-
"""
s562_freeze_thresholds.py — انجمادِ آستانه‌های علّیِ S562 برای مصرفِ زنده (سایت)

مسئله‌ای که این ابزار حل می‌کند
--------------------------------
لایهٔ S562 (`results/S562_GapOpenVolFilter_Xauusd_M15H1_rqs2_96_ACCEPT.md`) دو
کارتِ `ACCEPT` دارد: `XAUUSD-M15` با `RQS2 = 95.3` و `XAUUSD-H1` با `RQS2 = 96.0`.
قاعده‌اش = **سیگنالِ منجمدِ S560** (گپِ منفیِ بازگشایی) **+ فیلترِ V**:

    ردِ سیگنال اگر  vol_ref(روزِ قبل)  >  چندکِ qv از رولینگِ ۲۵۰-روزهٔ علّی

هر دو آستانه در بک‌تست **انبساطی/رولینگ** محاسبه می‌شوند و به تاریخِ کاملِ
۱۵.۶ ساله نیاز دارند. اما سایت روی این دو کارت فقط پنجرهٔ کوتاه می‌گیرد
(`GOLD_TF` در `web_tool/src/index.tsx`): M15 با `range='1mo'` و H1 با
`range='3mo'` ⇒ نه ۲۰ نمونهٔ تاریخیِ گپ جمع می‌شود و نه ۲۵۰ روز نوسان.
محاسبهٔ آن چندک‌ها از چند نمونه، **لایهٔ دیگری** است نه S562.

⇒ همان راهِ پیش‌ثبت‌شده و آزموده‌شدهٔ `tools/s560_freeze_thresholds.py`:
   هر دو آستانه یک بار از **همان دادهٔ داوری‌شده** استخراج و **منجمد** می‌شوند.
   این «برازشِ نو» نیست — هیچ پارامتری جست‌وجو نمی‌شود؛ فقط **آخرین مقدارِ**
   همان توابعِ علّیِ پیش‌ثبت‌شده گرفته می‌شود.

گاردهای ارثی که این ابزار رعایت می‌کند
--------------------------------------
• BUG-GEOMDRIFT   → `q`/`sw`/`hold` و هندسه از
                    `results/_s562_arms/locked_config.json` خوانده می‌شوند،
                    هرگز دست‌نویس نمی‌شوند.
• BUG-BRKTHRESH   → مرزِ روز از `day_breaks` همان ماژولِ اکتشاف
                    (آستانهٔ مقیاس‌پذیر با TF: max(1800, 1.5×TF_SEC)).
• آستانهٔ علّی      → `causal_neg_gap_quantile` و `vol_filter_mask` عیناً
                    بازاستفاده می‌شوند؛ کدِ آستانه بازنویسی **نمی‌شود**.
• BUG-DATASETDRIFT → داده فقط از `tools.s434_fast_data.load_fast`؛ `src` ثبت
                    می‌شود و `n_base_signals` با قفل مقایسه و assert می‌شود.
• صداقتِ انجماد     → شمارشِ سیگنال با آستانهٔ منجمد در برابرِ انبساطی/رولینگ
                    چاپ و ثبت می‌شود؛ اگر انجماد لایه را عوض می‌کرد، این دو
                    عدد فاصلهٔ معنادار می‌گرفتند.

اجرا:  python3 tools/s562_freeze_thresholds.py M15
       python3 tools/s562_freeze_thresholds.py H1
خروجی: results/_s562_arms/frozen_thresholds_<TF>.json
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
from tools.s562_volfilter import VOL_N, ROLL_D, MIN_S        # noqa: E402

ARMS_DIR = os.path.join(ROOT, 'results', '_s562_arms')
LOCKED = os.path.join(ARMS_DIR, 'locked_config.json')
ALLOWED_TFS = ('M15', 'H1')


def freeze(tf: str) -> dict:
    if tf not in ALLOWED_TFS:
        raise SystemExit(f'{tf} خارج از دامنهٔ ACCEPTِ S562 (فقط M15/H1)')

    with open(LOCKED, encoding='utf-8') as fh:
        locked = json.load(fh)
    if tf not in locked:
        raise SystemExit(f'TF {tf} در locked_config.json نیست')

    cfg = locked[tf]['cfg']
    q, sw, hold = float(cfg['q']), bool(cfg['sw']), int(cfg['hold'])
    picked = locked[tf]['picked']
    arm = locked[tf]['arms'][picked]
    qv = float(arm['qv'])
    geom = locked[tf]['geometry']

    d = fd.load_fast('XAUUSD', tf)
    print(f"src={d['src']}  n={d['n_bars']}  {d['first_utc']} → {d['last_utc']}")
    t, o, h, l, c = d['time'], d['open'], d['high'], d['low'], d['close']
    n = len(t)

    # ---------- ① آستانهٔ گپ (سیگنالِ پایهٔ S560 — منجمدشده) ----------
    brk = day_breaks(t, tf)
    brk = brk[brk + 1 < n]
    gaps = o[brk + 1] - c[brk]
    weekend = (t[brk + 1] - t[brk]) > 86400

    thr = causal_neg_gap_quantile(gaps, q, weekend, sw)

    def last_valid(group: np.ndarray) -> tuple[float, int]:
        idx = np.flatnonzero(group & ~np.isnan(thr))
        if len(idx) == 0:
            return float('nan'), 0
        return float(thr[idx[-1]]), int(len(idx))

    thr_we, n_we = last_valid(weekend)
    thr_wd, n_wd = last_valid(~weekend)

    frozen_gap = np.where(weekend, thr_we, thr_wd)
    valid_exp = ~np.isnan(thr)
    base_exp = (gaps < 0) & valid_exp & (np.abs(gaps) > thr)
    base_frz = (gaps < 0) & valid_exp & (np.abs(gaps) > frozen_gap)

    # ---------- ② آستانهٔ فیلترِ V (چندکِ رولینگِ ۲۵۰-روزه — منجمدشده) ----------
    # عیناً معناشناسیِ `s562_volfilter.vol_filter_mask`: روزها از همان مرزهای
    # `day_breaks` ساخته می‌شوند، `vol_ref[k]` = میانگینِ دامنهٔ روزانهٔ ۱۴ روزِ
    # منتهی به k (شاملِ k) — که در لحظهٔ ورودِ روزِ k+1 همه **کامل‌شده**اند.
    brk_all = day_breaks(t, tf)
    starts = np.concatenate([[0], brk_all + 1])
    ends = np.concatenate([brk_all, [n - 1]])
    n_days = len(starts)
    rng_day = np.array([h[starts[k]:ends[k] + 1].max()
                        - l[starts[k]:ends[k] + 1].min()
                        for k in range(n_days)])
    vol_ref = np.full(n_days, np.nan)
    csum = np.concatenate([[0.0], np.cumsum(rng_day)])
    for k in range(VOL_N - 1, n_days):
        vol_ref[k] = (csum[k + 1] - csum[k + 1 - VOL_N]) / VOL_N

    # آخرین آستانهٔ معتبرِ رولینگ = عددی که سایت از امروز به بعد مصرف می‌کند.
    thr_vol = float('nan')
    n_vol_hist = 0
    for k in range(n_days - 1, VOL_N - 2, -1):
        lo = max(VOL_N - 1, k - ROLL_D)
        hist = vol_ref[lo:k]
        hist = hist[~np.isnan(hist)]
        if len(hist) >= MIN_S:
            thr_vol = float(np.percentile(hist, qv))
            n_vol_hist = int(len(hist))
            break

    # ---------- ③ صداقتِ انجماد: شمارشِ سیگنالِ نهایی در دو حالت ----------
    day_of_end = {int(ends[k]): k for k in range(n_days)}

    def apply_vol(base_mask: np.ndarray, mode: str) -> int:
        """base_mask روی آرایهٔ brk است ⇒ اندیسِ کندلِ آخرِ روز = brk[j]."""
        keep = 0
        for j in np.flatnonzero(base_mask):
            i = int(brk[j])
            k = day_of_end.get(i)
            if k is None or np.isnan(vol_ref[k]):
                continue
            if mode == 'frozen':
                if not np.isnan(thr_vol) and vol_ref[k] <= thr_vol:
                    keep += 1
            else:
                lo = max(VOL_N - 1, k - ROLL_D)
                hist = vol_ref[lo:k]
                hist = hist[~np.isnan(hist)]
                if len(hist) < MIN_S:
                    continue
                if vol_ref[k] <= float(np.percentile(hist, qv)):
                    keep += 1
        return keep

    sig_rolling = apply_vol(base_exp, 'rolling')
    sig_frozen = apply_vol(base_frz, 'frozen')

    out = {
        'tf': tf,
        'cfg': {'q': q, 'split_weekend': sw, 'hold': hold, 'qv': qv},
        'frozen_threshold_usd': {
            'weekend': round(thr_we, 4),
            'weekday': round(thr_wd, 4),
        },
        'frozen_vol_threshold_usd': (round(thr_vol, 4)
                                     if not np.isnan(thr_vol) else None),
        'vol_filter_params': {'vol_n_days': VOL_N, 'roll_days': ROLL_D,
                              'min_samples': MIN_S},
        'n_history_used': {'weekend': n_we, 'weekday': n_wd,
                           'vol_rolling': n_vol_hist},
        'n_day_breaks': int(len(brk)),
        'n_days': int(n_days),
        'base_signals_expanding': int(base_exp.sum()),
        'base_signals_frozen': int(base_frz.sum()),
        'signals_rolling_volfilter': sig_rolling,
        'signals_frozen_volfilter': sig_frozen,
        'geometry': geom,
        'picked_arm': picked,
        'src': d['src'],
        'first_utc': d['first_utc'],
        'last_utc': d['last_utc'],
    }

    # --- گاردِ BUG-DATASETDRIFT: پایهٔ سیگنال باید با قفل بخواند ---
    n_locked = int(locked[tf]['n_base_signals'])
    out['n_base_signals_locked'] = n_locked
    out['datasetdrift_ok'] = bool(int(base_exp.sum()) == n_locked)

    os.makedirs(ARMS_DIR, exist_ok=True)
    path = os.path.join(ARMS_DIR, f'frozen_thresholds_{tf}.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    print(f'\n→ {path}')
    return out


if __name__ == '__main__':
    freeze(sys.argv[1] if len(sys.argv) > 1 else 'M15')
