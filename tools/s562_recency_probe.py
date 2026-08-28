# -*- coding: utf-8 -*-
"""
s562_recency_probe.py — سنجشِ «هم‌ارزیِ پنجرهٔ زنده» برای آستانه‌های منجمدِ S562

چرا این ابزار لازم شد (کشفِ مرحلهٔ انجماد)
------------------------------------------
`tools/s562_freeze_thresholds.py` نشان داد که پخشِ آستانهٔ **منجمد** روی کلِ
۱۵.۶ سال، فیلترِ نوسان را عملاً بی‌اثر می‌کند:

    M15: rolling → 438 سیگنال   |   frozen → 613 سیگنال
    H1 : rolling → 255 سیگنال   |   frozen → 361 سیگنال

این **باگِ پورت نیست** (پورت با بیت‌به‌بیتِ judge خواند: 438 و 255). این یک
واقعیتِ اقتصادی است: نوسانِ طلا در ۲۰۲۶ چند برابرِ ۲۰۱۱ است، پس عددِ منجمدِ
امروز، سال‌های ۲۰۱۱–۲۰۱۵ را «آرام» می‌بیند و همه را عبور می‌دهد.

⇒ نتیجهٔ روش‌شناختی: عددِ منجمد **هرگز** ادعا نمی‌کند تاریخ را بازتولید می‌کند.
  ادعای درست فقط این است: «در پنجرهٔ زنده‌ای که سایت می‌بیند، این عدد همان
  تصمیمی را می‌گیرد که چندکِ رولینگ می‌گرفت.» و آن ادعا **سنجش‌پذیر** است.
  این ابزار همان را می‌سنجد و اگر نخواند، اتصال حق ندارد انجام شود.

سنجهٔ اصلی: روی N روزِ آخرِ داده (پنجرهٔ زنده)، برای هر سیگنالِ پایه، تصمیمِ
«عبور/رد»ِ فیلترِ رولینگ در برابرِ فیلترِ منجمد مقایسه می‌شود ⇒ نرخِ توافق.

⚠️ **نکتهٔ طراحیِ حاصل از همین سنجش**: خودِ `vol_ref` (میانگینِ دامنهٔ روزانهٔ
   ۱۴ روز) در پنجرهٔ سایت **قابلِ محاسبه** است (M15 با 1mo ≈ ۲۲ روز، H1 با
   3mo ≈ ۶۵ روز). پس فقط **آستانه** منجمد می‌شود، نه خودِ سنجه. این حداقلِ
   انجمادِ ممکن است — هر چه بیشتر زنده بماند، لایه صادق‌تر است.

اجرا:  python3 tools/s562_recency_probe.py M15
خروجی: results/_s562_arms/recency_<TF>.json
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

# پنجره‌های زنده‌ای که سایت واقعاً می‌بیند (GOLD_TF در web_tool/src/index.tsx)
# M15: range='1mo' ⇒ ~۲۲ روزِ معاملاتی | H1: range='3mo' ⇒ ~۶۵ روز
SITE_WINDOW_DAYS = {'M15': 22, 'H1': 65}
# پنجره‌های سنجش: از پنجرهٔ واقعیِ سایت تا یک سالِ کامل (برای دیدنِ روندِ توافق)
PROBE_WINDOWS = (22, 65, 125, 250, 500)


def probe(tf: str) -> dict:
    locked = json.load(open(LOCKED, encoding='utf-8'))
    frozen = json.load(open(os.path.join(
        ARMS_DIR, f'frozen_thresholds_{tf}.json'), encoding='utf-8'))

    cfg = locked[tf]['cfg']
    q, sw = float(cfg['q']), bool(cfg['sw'])
    qv = float(locked[tf]['arms'][locked[tf]['picked']]['qv'])
    thr_we = float(frozen['frozen_threshold_usd']['weekend'])
    thr_wd = float(frozen['frozen_threshold_usd']['weekday'])
    thr_vol = float(frozen['frozen_vol_threshold_usd'])

    d = fd.load_fast('XAUUSD', tf)
    t, o, h, l, c = d['time'], d['open'], d['high'], d['low'], d['close']
    n = len(t)
    print(f"src={d['src']}  n={n}  {d['first_utc']} → {d['last_utc']}")

    # --- روزها و vol_ref (عیناً معناشناسیِ s562_volfilter) ---
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

    # --- سیگنال‌های پایه (گپ) با هر دو آستانه ---
    brk = brk_all[brk_all + 1 < n]
    gaps = o[brk + 1] - c[brk]
    weekend = (t[brk + 1] - t[brk]) > 86400
    thr_roll_gap = causal_neg_gap_quantile(gaps, q, weekend, sw)
    frozen_gap = np.where(weekend, thr_we, thr_wd)
    valid = ~np.isnan(thr_roll_gap)

    base_roll = (gaps < 0) & valid & (np.abs(gaps) > thr_roll_gap)
    base_frz = (gaps < 0) & valid & (np.abs(gaps) > frozen_gap)

    day_of_end = {int(ends[k]): k for k in range(n_days)}

    def vol_pass_rolling(k: int) -> bool | None:
        lo = max(VOL_N - 1, k - ROLL_D)
        hist = vol_ref[lo:k]
        hist = hist[~np.isnan(hist)]
        if len(hist) < MIN_S:
            return None
        return bool(vol_ref[k] <= float(np.percentile(hist, qv)))

    def vol_pass_frozen(k: int) -> bool | None:
        if np.isnan(vol_ref[k]):
            return None
        return bool(vol_ref[k] <= thr_vol)

    out_windows = {}
    for w in PROBE_WINDOWS:
        k_min = n_days - w                    # فقط روزهای انتهایی
        # --- ① توافقِ آستانهٔ گپ ---
        gap_agree = gap_total = 0
        # --- ② توافقِ فیلترِ نوسان (روی سیگنال‌های پایهٔ رولینگ) ---
        vol_agree = vol_total = 0
        # --- ③ توافقِ سیگنالِ نهایی (گپ ∧ نوسان) ---
        fin_agree = fin_total = 0
        for j in range(len(brk)):
            k = day_of_end.get(int(brk[j]))
            if k is None or k < k_min or not valid[j]:
                continue
            gap_total += 1
            if bool(base_roll[j]) == bool(base_frz[j]):
                gap_agree += 1
            if base_roll[j]:
                pr, pf = vol_pass_rolling(k), vol_pass_frozen(k)
                if pr is not None and pf is not None:
                    vol_total += 1
                    if pr == pf:
                        vol_agree += 1
            # سیگنالِ نهایی
            fr = bool(base_roll[j]) and (vol_pass_rolling(k) is True)
            ff = bool(base_frz[j]) and (vol_pass_frozen(k) is True)
            fin_total += 1
            if fr == ff:
                fin_agree += 1
        out_windows[str(w)] = {
            'days': w,
            'gap_decisions': gap_total,
            'gap_agree_pct': round(100.0 * gap_agree / gap_total, 2) if gap_total else None,
            'vol_decisions': vol_total,
            'vol_agree_pct': round(100.0 * vol_agree / vol_total, 2) if vol_total else None,
            'final_decisions': fin_total,
            'final_agree_pct': round(100.0 * fin_agree / fin_total, 2) if fin_total else None,
        }
        print(f"  window={w}d  gap {out_windows[str(w)]['gap_agree_pct']}% "
              f"({gap_total})  vol {out_windows[str(w)]['vol_agree_pct']}% "
              f"({vol_total})  final {out_windows[str(w)]['final_agree_pct']}% ({fin_total})")

    out = {
        'tf': tf,
        'site_window_days': SITE_WINDOW_DAYS.get(tf),
        'frozen': {'gap_weekend': thr_we, 'gap_weekday': thr_wd,
                   'vol': thr_vol, 'qv': qv, 'q': q},
        'windows': out_windows,
        'n_days_total': int(n_days),
        'src': d['src'], 'last_utc': d['last_utc'],
    }
    os.makedirs(ARMS_DIR, exist_ok=True)
    path = os.path.join(ARMS_DIR, f'recency_{tf}.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f'\n→ {path}')
    return out


if __name__ == '__main__':
    probe(sys.argv[1] if len(sys.argv) > 1 else 'M15')
