# -*- coding: utf-8 -*-
"""
s408_freeze_thresholds.py — انجمادِ آستانه‌های علّیِ S408 برای مصرفِ زنده (سایت)

مسئله‌ای که این ابزار حل می‌کند
--------------------------------
لایهٔ S408 (`results/S408_GapFillM15FullData_Xauusd_M15_rqs2_94_ACCEPT.md`) حکمِ
`ACCEPT` با `RQS2 = 93.8` (Tier A · ۱۱/۱۱ گیت سبز) روی کارتِ **XAUUSD-M15** دارد.
قاعده‌اش سه شرطِ علّی + یک هندسهٔ گپ-محور است:

    ① گپِ منفیِ روز:      gap = open(بارِ اولِ روز) − close(روزِ قبل) < 0
    ② آستانهٔ گپِ QW q=60: |gap| > چندکِ ۶۰ از |gap|های ۵۰۰ روزِ اخیرِ **هم‌نوع**
                            (آخرهفته با آخرهفته، میان‌هفته با میان‌هفته)
    ③ DOW ≠ دوشنبه
    ④ فیلترِ V (ATR q78):  ATR14ِ روزِ قبل ≤ چندکِ ۰.۷۸ از رولینگِ ۲۵۰ روزِ علّی
    ⑤ هندسه: LONG در open · TP = close روزِ قبل · SL = 2.0×|gap| · خروجِ اجباری
             در آخرین کندلِ روز · SPREAD_PIP = 3.3

شرط‌های ② و ④ هر دو **چندکِ رولینگ روی صدها روز** هستند و به تاریخِ کاملِ
۱۵.۶ ساله نیاز دارند. اما کارتِ M15 سایت (`GOLD_TF` در `web_tool/src/index.tsx`)
با `range='1mo'` فقط ~۲۲ روزِ معاملاتی می‌بیند ⇒ نه ۵۰۰ روز تاریخِ گپ جمع
می‌شود و نه ۲۵۰ روز تاریخِ ATR. محاسبهٔ آن چندک‌ها از ۲۲ نمونه **لایهٔ دیگری**
است، نه S408.

⇒ همان راهِ پیش‌ثبت‌شده و آزمودهٔ `tools/s560_freeze_thresholds.py` و
   `tools/s562_freeze_thresholds.py`: هر دو آستانه یک بار از **همان دادهٔ
   داوری‌شده** استخراج و **منجمد** می‌شوند. این «برازشِ نو» نیست — هیچ
   پارامتری جست‌وجو نمی‌شود؛ فقط **آخرین مقدارِ** همان توابعِ علّیِ
   پیش‌ثبت‌شده گرفته می‌شود.

⚠️ آنچه منجمد **نمی‌شود** (کمینه‌ترین انجمادِ ممکن — اصلِ ارثی از S562 §③):
   خودِ `ATR14` روزانه در مرورگر **زنده** محاسبه می‌شود (۱۴ روز در پنجرهٔ ۲۲
   روزهٔ کارت جا می‌شود). تنها *آستانهٔ* چندک منجمد است. هر چه کمتر منجمد شود،
   لایهٔ زنده به نسخهٔ داوری‌شده نزدیک‌تر می‌مانَد.

گاردهای ارثی که این ابزار رعایت می‌کند
--------------------------------------
• BUG-GEOMDRIFT   → `q`/`k_sl`/`SPREAD_PIP`/`PIP` از خودِ ماژولِ داوری‌شده
                    (`strategies/s408_gap_fill_m15_fulldata.py` و والدهایش)
                    خوانده می‌شوند، هرگز دست‌نویس نمی‌شوند.
• BUG-DAYBREAK-TF → مرزِ روز از `strategies.s400_gap_open.day_break_sec`
                    (۲ × میانهٔ فاصلهٔ بارها) — کدِ مرزِ روز بازنویسی نمی‌شود.
• آستانهٔ علّی      → `thresholds_for_day(..., 'QW', 60)` و `vol_flags` عیناً
                    بازاستفاده می‌شوند؛ فرمولِ چندک بازنویسی **نمی‌شود**.
• BUG-DATASETDRIFT → داده فقط `data/mt5_full/XAUUSD_M15.csv` با assertِ
                    بارها/تاریخِ اول/تاریخِ آخر عیناً مثلِ `load_full()`.
• صداقتِ انجماد     → شمارشِ سیگنالِ «آستانهٔ رولینگ» در برابرِ «آستانهٔ منجمد»
                    چاپ و در JSON ثبت می‌شود؛ همچنین شمارشِ سیگنالِ رولینگ با
                    `_s408_verdict.json::n_trades` مقایسه و assert می‌شود
                    (پریتیِ داور ⇒ اثباتِ درستیِ پورت پیش از انجماد).

اجرا:  python3 tools/s408_freeze_thresholds.py
خروجی: results/_s408_arms/frozen_thresholds_M15.json
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
    build_days, daily_atr, thresholds_for_day, day_break_sec,
    PIP, SPREAD_PIP, ROLL_DAYS, MIN_ROLL_OBS)
from strategies.s401_gap_fill_riskguard import sim_trade_be    # noqa: E402
from strategies.s404_gap_fill_window import vol_flags, VOL_ROLL, VOL_Q  # noqa: E402

# ── پارامترهای قفل‌شدهٔ S408 (از سندِ ACCEPT §۱ و کدِ داوری‌شده) ──────────────
TF = 'M15'
Q_GAP = 60          # چندکِ QW برندهٔ تیون (پیش‌ثبت §۲ — q∈{60,70,80})
K_SL = 2.0          # ضریبِ SL برندهٔ تیون (پیش‌ثبت §۲ — k_sl∈{1.7,2.0})
DATA = os.path.join(ROOT, 'data', 'mt5_full', 'XAUUSD_M15.csv')
EXPECT = dict(n=363778, first='2011-01-03 00:00:00', last='2026-08-07 23:45:00')
SPLIT_FULL = 180896

OUT_DIR = os.path.join(ROOT, 'results', '_s408_arms')
OUT = os.path.join(OUT_DIR, f'frozen_thresholds_{TF}.json')
VERDICT = os.path.join(ROOT, 'results', '_s408_verdict.json')


def load_full():
    """عیناً `s408_gap_fill_m15_fulldata.load_full` — assertِ بازهٔ زمانی."""
    df = se.load_data(DATA)
    first, last = str(df['dt'].iloc[0]), str(df['dt'].iloc[-1])
    print(f'DATA {DATA}: bars={len(df)} first={first} last={last}', flush=True)
    assert len(df) == EXPECT['n'] and first == EXPECT['first'] \
        and last == EXPECT['last'], 'data span mismatch vs prereg — STOP'
    assert str(df['dt'].iloc[SPLIT_FULL]) == '2018-10-25 11:30:00', 'split bar mismatch'
    return df


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_full()
    t = df['time'].values.astype('int64')
    dbs = day_break_sec(t)
    print(f'day_break_sec({TF}) = {dbs}s  (۲ × میانهٔ فاصلهٔ بارها)', flush=True)

    days = build_days(df)
    atr = daily_atr(days)
    vflags = vol_flags(days, atr)
    print(f'days={len(days)} · atr finite={int(np.isfinite(atr).sum())}', flush=True)

    # ── ① آخرین آستانهٔ گپِ QW برای هر دو نوعِ روز (منجمد) ───────────────────
    #    thresholds_for_day علّی است (فقط روزهای < k)؛ «آخرین مقدار» را برای
    #    هر نوعِ روز از انتهای تاریخ می‌گیریم — بی‌هیچ جست‌وجو یا تنظیم.
    last_thr = {'weekend': None, 'weekday': None}
    last_k = {'weekend': None, 'weekday': None}
    for k in range(len(days) - 1, -1, -1):
        kind = 'weekend' if days[k]['weekend'] else 'weekday'
        if last_thr[kind] is not None:
            continue
        th = thresholds_for_day(days, atr, k, 'QW', Q_GAP)
        if np.isfinite(th):
            last_thr[kind] = float(th)
            last_k[kind] = k
        if all(v is not None for v in last_thr.values()):
            break
    print(f"frozen gap threshold (QW q={Q_GAP}): "
          f"weekend={last_thr['weekend']:.4f}$ (day k={last_k['weekend']}) · "
          f"weekday={last_thr['weekday']:.4f}$ (day k={last_k['weekday']})", flush=True)

    # ── ② آخرین آستانهٔ نوسانِ V (چندکِ VOL_Q از رولینگِ VOL_ROLL روزِ ATR) ──
    #    عیناً همان محاسبهٔ داخلِ vol_flags، فقط برای آخرین روزِ دارای تاریخچه.
    vol_thr, vol_k, vol_hist_n = None, None, None
    for k in range(len(days) - 1, 0, -1):
        lo = max(0, k - VOL_ROLL)
        hist = atr[lo:k]
        hist = hist[np.isfinite(hist)]
        if len(hist) >= 60 and np.isfinite(atr[k - 1]):
            vol_thr = float(np.quantile(hist, VOL_Q))
            vol_k, vol_hist_n = k, int(len(hist))
            break
    print(f'frozen vol threshold (ATR14 q{VOL_Q}): {vol_thr:.4f}$ '
          f'(day k={vol_k} · hist={vol_hist_n})', flush=True)

    # ── ③ پریتیِ داور: شمارشِ سیگنال با آستانهٔ رولینگ (باید = n_trades داور) ─
    arrays = (df['open'].values, df['high'].values, df['low'].values, df['close'].values)
    n_roll, n_frozen = 0, 0
    sl_list, tp_list = [], []
    for k, d in enumerate(days):
        if not (d['gap'] < 0):
            continue
        if d['dow'] == 0:
            continue
        agap = abs(d['gap'])
        # آستانهٔ رولینگ (نسخهٔ داوری‌شده)
        th_roll = thresholds_for_day(days, atr, k, 'QW', Q_GAP)
        ok_roll = np.isfinite(th_roll) and agap > th_roll and not vflags[k]
        # آستانهٔ منجمد (نسخهٔ زنده)
        th_fr = last_thr['weekend'] if d['weekend'] else last_thr['weekday']
        a_prev = atr[k - 1] if k >= 1 else np.nan
        ok_frozen = (agap > th_fr) and np.isfinite(a_prev) and (a_prev <= vol_thr)
        if ok_roll:
            tr = sim_trade_be(arrays, d, K_SL, None)
            if tr is not None:
                n_roll += 1
                sl_list.append(tr['sl_pip'])
                tp_list.append(tr['tp_pip'])
        if ok_frozen:
            n_frozen += 1

    with open(VERDICT) as f:
        judged = json.load(f)
    n_judged = int(judged['metrics']['n_trades'])
    print(f'signals rolling={n_roll} · judged n_trades={n_judged} · '
          f'signals frozen(all-history replay)={n_frozen}', flush=True)
    assert n_roll == n_judged, \
        f'PARITY FAIL: rolling={n_roll} != judged={n_judged} — STOP (port bug)'
    print('PARITY OK ✓ — پورتِ آستانه/DOW/V/شبیه‌ساز بیت‌به‌بیت با داور یکی است',
          flush=True)

    sl_med = float(np.median(sl_list))
    tp_med = float(np.median(tp_list))
    print(f'judged geometry: sl_pip={sl_med:.1f} tp_pip={tp_med:.1f} '
          f'rr={tp_med / sl_med:.3f}', flush=True)

    out = {
        'layer': 'S408',
        'tf': TF,
        'doc': 'results/S408_GapFillM15FullData_Xauusd_M15_rqs2_94_ACCEPT.md',
        'cfg': {
            'q_gap': Q_GAP, 'family': 'QW', 'k_sl': K_SL,
            'dow_excluded': 0, 'vol_q': VOL_Q, 'vol_roll': VOL_ROLL,
            'roll_days_gap': 2 * ROLL_DAYS, 'min_roll_obs': MIN_ROLL_OBS,
            'atr_period': 14, 'pip': PIP, 'spread_pip': SPREAD_PIP,
        },
        'frozen_gap_threshold_usd': {
            'weekend': round(last_thr['weekend'], 4),
            'weekday': round(last_thr['weekday'], 4),
        },
        'frozen_vol_threshold_usd': round(vol_thr, 4),
        'frozen_at_day_index': {
            'weekend': last_k['weekend'], 'weekday': last_k['weekday'],
            'vol': vol_k, 'vol_hist_n': vol_hist_n,
        },
        'day_break_sec': int(dbs),
        'n_days': len(days),
        'parity': {
            'signals_rolling': n_roll,
            'judged_n_trades': n_judged,
            'ok': bool(n_roll == n_judged),
            'signals_frozen_all_history': n_frozen,
        },
        'geometry_judged': {
            'sl_pip_median': round(sl_med, 1),
            'tp_pip_median': round(tp_med, 1),
            'rr': round(tp_med / sl_med, 3),
        },
        'judged_metrics': {
            'rqs2': judged.get('rqs2_score', judged.get('score')),
            'n': n_judged,
            'wr': judged['metrics']['win_rate'],
            'pf': judged['metrics']['profit_factor'],
            'max_dd_pct': judged['metrics']['max_dd_pct'],
            'z': judged['metrics']['skill_z'],
        },
        'src': DATA,
        'first_utc': EXPECT['first'],
        'last_utc': EXPECT['last'],
    }
    with open(OUT, 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f'saved → {OUT}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
