# -*- coding: utf-8 -*-
"""
s408_dump_parity_fixture.py — ساختِ fixtureِ پریتیِ S408 (پایتون ⇄ TS)

چرا
---
اتصالِ هر لایه به سایت در این پروژه با **دو هارنسِ مستقل** اثبات می‌شود
(الگوی S966/S919): ① پریتیِ ماژول (همین fixture) و ② یکپارچگیِ کارت.
این ابزار سمتِ **مرجعِ پایتون** را می‌سازد: روی پنجرهٔ آخرِ دادهٔ M15، هر
مرزِ روز را با توابعِ *پیش‌ثبت‌شدهٔ* S400/S404 ارزیابی می‌کند و تصمیم +
اجزای میانی را ثبت می‌کند تا TS مو-به-مو با آن مقایسه شود.

نکتهٔ روشیِ مهم — **دو مرجع، نه یکی:**
  • `dec_rolling`  : تصمیم با آستانهٔ **رولینگِ علّی** (نسخهٔ داوری‌شده).
  • `dec_frozen`   : تصمیم با آستانهٔ **منجمد** (نسخهٔ زنده‌ای که TS اجرا می‌کند).
TS باید با `dec_frozen` **صفر اختلاف** داشته باشد (چون همان قاعده را اجرا
می‌کند)؛ و فاصلهٔ `dec_frozen` از `dec_rolling` همان چیزی است که
`results/_s408_arms/recency_M15.json` صادقانه ثبت کرده (در پنجرهٔ زندهٔ سایت
۱۰۰٪ یکی‌اند). این تفکیک عمدی است تا «سبزِ کاذب» ممکن نباشد.

⚠️ همچنین ATR روزانه (که TS **زنده** می‌سازد) از پایتون دامپ می‌شود تا دامِ ④
   (میانگینِ ساده در برابرِ EMA) و دامِ ⑥ (ردِ محافظه‌کارانه) قابلِ سنجش باشد.

اجرا:  python3 tools/s408_dump_parity_fixture.py [n_bars]
خروجی: results/_s408_arms/parity_m15_fixture.json
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
    build_days, daily_atr, thresholds_for_day, day_break_sec, PIP, SPREAD_PIP)
from strategies.s401_gap_fill_riskguard import sim_trade_be    # noqa: E402
from strategies.s404_gap_fill_window import vol_flags, VOL_ROLL, VOL_Q  # noqa: E402

TF = 'M15'
Q_GAP = 60
K_SL = 2.0
DATA = os.path.join(ROOT, 'data', 'mt5_full', 'XAUUSD_M15.csv')
ARMS = os.path.join(ROOT, 'results', '_s408_arms')
FROZEN = os.path.join(ARMS, f'frozen_thresholds_{TF}.json')
OUT = os.path.join(ARMS, f'parity_m15_fixture.json')

N_BARS_DEFAULT = 20000     # ~۲۰۸ روزِ معاملاتی — عمقی بیش از پنجرهٔ سایت


def main():
    n_bars = int(sys.argv[1]) if len(sys.argv) > 1 else N_BARS_DEFAULT
    os.makedirs(ARMS, exist_ok=True)
    with open(FROZEN) as f:
        fr = json.load(f)
    thr_we = fr['frozen_gap_threshold_usd']['weekend']
    thr_wd = fr['frozen_gap_threshold_usd']['weekday']
    thr_vol = fr['frozen_vol_threshold_usd']

    df = se.load_data(DATA)
    # ⚠️ روزها/ATR/vflags روی **کلِ تاریخ** ساخته می‌شوند (مرجعِ درست)، سپس
    #    fixture فقط پنجرهٔ آخر را می‌برد. اینطور اگر پورتِ TS به warm-up
    #    وابسته باشد، همین‌جا لو می‌رود.
    days = build_days(df)
    atr = daily_atr(days)
    vflags = vol_flags(days, atr)
    arrays = (df['open'].values, df['high'].values, df['low'].values,
              df['close'].values)

    n_all = len(df)
    lo_bar = max(0, n_all - n_bars)
    t = df['time'].values.astype('int64')
    dbs = int(day_break_sec(t))

    recs = []
    for k, d in enumerate(days):
        if d['fb'] < lo_bar + 2:      # مرز باید کاملاً داخلِ پنجره باشد
            continue
        agap = abs(d['gap'])
        th_roll = thresholds_for_day(days, atr, k, 'QW', Q_GAP)
        gap_roll = bool(np.isfinite(th_roll) and agap > th_roll)
        vol_roll_ok = bool(not vflags[k])

        th_fr = thr_we if d['weekend'] else thr_wd
        gap_fr = bool(agap > th_fr)
        a_prev = atr[k - 1] if k >= 1 else np.nan
        vol_fr_ok = bool(np.isfinite(a_prev) and a_prev <= thr_vol)

        dow_ok = bool(d['dow'] != 0)
        neg = bool(d['gap'] < 0)
        dec_roll = bool(neg and gap_roll and vol_roll_ok and dow_ok)
        dec_fr = bool(neg and gap_fr and vol_fr_ok and dow_ok)

        # هندسه (فقط وقتی تصمیمِ منجمد فعال است — همان چیزی که TS می‌سازد)
        tp_usd = float(d['prev_close'] - d['day_open'])
        sl_usd = float(K_SL * agap)
        tr = sim_trade_be(arrays, d, K_SL, None) if dec_fr else None

        recs.append({
            'k': int(k),
            'fb': int(d['fb']),                 # اندیسِ کندلِ اولِ روزِ نو
            'brk': int(d['fb'] - 1),            # اندیسِ مرز (آخرین کندلِ روزِ قبل)
            'fb_rel': int(d['fb'] - lo_bar),    # اندیسِ نسبی در fixture
            'brk_rel': int(d['fb'] - 1 - lo_bar),
            'dow': int(d['dow']),
            'weekend': bool(d['weekend']),
            'gap_usd': float(d['gap']),
            'prev_close': float(d['prev_close']),
            'day_open': float(d['day_open']),
            'thr_rolling': (float(th_roll) if np.isfinite(th_roll) else None),
            'thr_frozen': float(th_fr),
            'atr_prev': (float(a_prev) if np.isfinite(a_prev) else None),
            'gap_ok_rolling': gap_roll, 'gap_ok_frozen': gap_fr,
            'vol_ok_rolling': vol_roll_ok, 'vol_ok_frozen': vol_fr_ok,
            'dow_ok': dow_ok, 'neg_gap': neg,
            'dec_rolling': dec_roll, 'dec_frozen': dec_fr,
            'tp_usd': tp_usd, 'sl_usd': sl_usd,
            'sl_pip': (float(tr['sl_pip']) if tr else None),
            'tp_pip': (float(tr['tp_pip']) if tr else None),
        })

    candles = [{'time': int(t[i]),
                'open': float(df['open'].values[i]),
                'high': float(df['high'].values[i]),
                'low': float(df['low'].values[i]),
                'close': float(df['close'].values[i]),
                'volume': 0}
               for i in range(lo_bar, n_all)]

    out = {
        'layer': 'S408', 'tf': TF,
        'cfg': {'q_gap': Q_GAP, 'k_sl': K_SL, 'vol_q': VOL_Q,
                'vol_roll': VOL_ROLL, 'atr_n': 14,
                'pip': PIP, 'spread_pip': SPREAD_PIP,
                'day_break_sec': dbs},
        'frozen': {'weekend': thr_we, 'weekday': thr_wd, 'vol': thr_vol},
        'window': {'lo_bar': lo_bar, 'n_bars': len(candles),
                   'first_utc': str(df['dt'].iloc[lo_bar]),
                   'last_utc': str(df['dt'].iloc[-1])},
        'n_days_all_history': len(days),
        'records': recs,
        'candles': candles,
    }
    with open(OUT, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    n_fr = sum(1 for r in recs if r['dec_frozen'])
    n_rl = sum(1 for r in recs if r['dec_rolling'])
    print(f'fixture: bars={len(candles)} day_boundaries={len(recs)} '
          f'dec_frozen={n_fr} dec_rolling={n_rl}', flush=True)
    print(f'saved → {OUT}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
