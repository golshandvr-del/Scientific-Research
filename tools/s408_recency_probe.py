# -*- coding: utf-8 -*-
"""
s408_recency_probe.py — سنجهٔ صداقتِ انجمادِ S408 در **پنجرهٔ واقعیِ سایت**

چرا این ابزار لازم است
----------------------
`tools/s408_freeze_thresholds.py` نشان داد بازپخشِ آستانهٔ منجمد روی **کلِ
۱۵.۶ سال** فقط ۲۱۲ سیگنال می‌دهد در برابرِ ۴۹۶ سیگنالِ رولینگ. این عدد
به‌خودی‌خود *ایراد پورت نیست* — پریتیِ داور در همان ابزار سبز شد (۴۹۶=۴۹۶) —
بلکه اثرِ **جهشِ رژیمِ قیمت/نوسانِ طلا** است: آستانهٔ گپِ امروزی (۱.۲۹۶$ در
میان‌هفته، وقتی طلا ~۳۵۰۰$ است) برای سالِ ۲۰۱۱ (طلا ~۱۴۰۰$) بزرگ است و
گپ‌های واقعیِ آن دوره را «کوچک» می‌بیند.

پس سؤالِ درست این نیست که «آستانهٔ منجمد کلِ تاریخ را بازتولید می‌کند؟»
(نمی‌کند و نباید ازش انتظار داشت) بلکه:

    **در همان ~۲۲ روزی که کارتِ M15 سایت واقعاً می‌بیند، آیا آستانهٔ منجمد
      همان تصمیمی را می‌دهد که آستانهٔ رولینگِ داوری‌شده می‌داد؟**

اگر پاسخ «بله» باشد، لایهٔ زنده = لایهٔ داوری‌شده در پنجرهٔ عملیاتی، و
انجماد صادقانه است. اگر «نه» باشد، اتصال باید متوقف شود.

روش
---
پنجره‌های recency مختلف (۲۲ / ۴۵ / ۹۰ / ۱۸۰ / ۲۵۰ روزِ آخرِ داده) گرفته
می‌شوند و در هر پنجره سه توافق اندازه‌گیری می‌شود:
  • agree_gap  : توافقِ شرطِ «|gap| > آستانه» بین منجمد و رولینگ
  • agree_vol  : توافقِ شرطِ فیلترِ V بین منجمد و رولینگ
  • agree_joint: توافقِ تصمیمِ نهایی (گپ ∧ DOW ∧ V)
هیچ پارامتری تنظیم نمی‌شود؛ این ابزار فقط **می‌سنجد و ثبت می‌کند**.

اجرا:  python3 tools/s408_recency_probe.py
خروجی: results/_s408_arms/recency_M15.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import scalp_engine as se                          # noqa: E402
from strategies.s400_gap_open import (                         # noqa: E402
    build_days, daily_atr, thresholds_for_day)
from strategies.s404_gap_fill_window import vol_flags, VOL_ROLL, VOL_Q  # noqa: E402

TF = 'M15'
Q_GAP = 60
DATA = os.path.join(ROOT, 'data', 'mt5_full', 'XAUUSD_M15.csv')
ARMS = os.path.join(ROOT, 'results', '_s408_arms')
FROZEN = os.path.join(ARMS, f'frozen_thresholds_{TF}.json')
OUT = os.path.join(ARMS, f'recency_{TF}.json')

WINDOWS = (22, 45, 90, 180, 250)     # ۲۲ = پنجرهٔ واقعیِ کارتِ M15 (range=1mo)


def main():
    with open(FROZEN) as f:
        fr = json.load(f)
    thr_we = fr['frozen_gap_threshold_usd']['weekend']
    thr_wd = fr['frozen_gap_threshold_usd']['weekday']
    thr_vol = fr['frozen_vol_threshold_usd']

    df = se.load_data(DATA)
    days = build_days(df)
    atr = daily_atr(days)
    vflags = vol_flags(days, atr)
    n = len(days)
    print(f'days={n} · frozen gap we={thr_we} wd={thr_wd} · vol={thr_vol}',
          flush=True)

    report = {}
    for w in WINDOWS:
        lo = max(1, n - w)
        g_ag = v_ag = j_ag = tot = 0
        n_roll_sig = n_frozen_sig = 0
        for k in range(lo, n):
            d = days[k]
            if not (d['gap'] < 0):
                continue
            tot += 1
            agap = abs(d['gap'])
            # رولینگ (داوری‌شده)
            th_roll = thresholds_for_day(days, atr, k, 'QW', Q_GAP)
            gap_roll = bool(np.isfinite(th_roll) and agap > th_roll)
            vol_roll_ok = bool(not vflags[k])
            # منجمد (زنده)
            th_fr = thr_we if d['weekend'] else thr_wd
            gap_fr = bool(agap > th_fr)
            a_prev = atr[k - 1] if k >= 1 else np.nan
            vol_fr_ok = bool(np.isfinite(a_prev) and a_prev <= thr_vol)

            dow_ok = d['dow'] != 0
            dec_roll = gap_roll and vol_roll_ok and dow_ok
            dec_fr = gap_fr and vol_fr_ok and dow_ok

            g_ag += int(gap_roll == gap_fr)
            v_ag += int(vol_roll_ok == vol_fr_ok)
            j_ag += int(dec_roll == dec_fr)
            n_roll_sig += int(dec_roll)
            n_frozen_sig += int(dec_fr)

        pct = lambda x: round(100.0 * x / tot, 1) if tot else None
        report[f'last_{w}_days'] = {
            'neg_gap_days': tot,
            'agree_gap_pct': pct(g_ag),
            'agree_vol_pct': pct(v_ag),
            'agree_joint_pct': pct(j_ag),
            'signals_rolling': n_roll_sig,
            'signals_frozen': n_frozen_sig,
        }
        print(f'last {w:3d} days: neg-gap={tot:3d} · gap {pct(g_ag)}% · '
              f'vol {pct(v_ag)}% · joint {pct(j_ag)}% · '
              f'sig roll={n_roll_sig} frozen={n_frozen_sig}', flush=True)

    out = {
        'layer': 'S408', 'tf': TF,
        'frozen_src': f'results/_s408_arms/frozen_thresholds_{TF}.json',
        'site_window_days': 22,
        'note': ('انجماد فقط برای پنجرهٔ زنده مجاز است، نه بازپخشِ تاریخی — '
                 'علتِ واگراییِ تاریخی جهشِ رژیمِ قیمت/نوسانِ طلاست، نه نقصِ پورت '
                 '(پریتیِ داور در ابزارِ انجماد سبز بود: 496=496).'),
        'windows': report,
        'vol_params': {'q': VOL_Q, 'roll': VOL_ROLL},
    }
    with open(OUT, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f'saved → {OUT}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
