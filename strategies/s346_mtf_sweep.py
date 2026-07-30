# -*- coding: utf-8 -*-
"""
S346 — پیمایشِ **کیفیتِ پایه** روی همهٔ کارت‌ها (اجرای قانونِ مولتی‌تایم‌فریم)
================================================================================

چرا این فایل لازم شد
--------------------------------------------------------------------------------
روی `XAUUSD-M15` نتیجهٔ قاطع گرفتیم: از **۱۲۹۶ هندسه، صفر موردِ قابلِ نجات**
(بهترین کیفیتِ پایه = ۵۰.۹۶٪ ⇒ فاصلهٔ ۱۰.۰۴pp تا کف، بیش از سقفِ لیفتِ ۸pp).

اما «مرگ روی یک تایم‌فریم» ≠ «مرگِ ابزار». این دقیقاً **اشتباهِ رایجِ شمارهٔ ۵**
است (نتیجه‌گیریِ سریع از یک تایم‌فریم). شاهدِ مقدماتی هم داریم: در اسکنِ اولیه
`XAUUSD-H4` خامْ WR=۵۵.۰٪ داد — یعنی فاصلهٔ ۶pp که **زیرِ** سقفِ لیفت است و
بنابراین *بالقوه* قابلِ نجات.

منطقِ ساختاریِ این تفاوت (نه صرفاً آماری): هزینهٔ معامله ثابت است (اسپردِ
۰.۳۳$/oz) ولی دامنهٔ حرکت با √تایم‌فریم بزرگ می‌شود. پس نسبتِ سیگنال‌به‌هزینه
روی تایم‌فریم‌های بالاتر **ساختاراً** بهتر است. برگشت‌به‌میانگین هم روی
تایم‌فریم‌های بالاتر بازهٔ معناداری دارد.

روش
--------------------------------------------------------------------------------
برای هر کارت `sweep_card` اجرا و از JSONِ ذخیره‌شده سه سنجه استخراج می‌شود:
  ۱. `best_q`      : بیشترین `min(WR_D, WR_H)` در میانِ هندسه‌هایی با n کافی
  ۲. `n_reachable` : تعداد هندسه‌هایی که فاصله‌شان تا کف ≤ سقفِ لیفت است
  ۳. `best_n`      : بودجهٔ N بهترین هندسهٔ کیفی

⚠️ قانونِ «اندک اندک»: پس از **هر کارت** نتیجه روی دیسک ذخیره می‌شود؛ منتظرِ
پایانِ همهٔ ۱۱ کارت نمی‌مانیم چون سندباکس ناپایدار است.
"""

import os
import sys
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.s346_geom import CARDS
from strategies.s346_joint import (sweep_card, OUT, WR_FLOOR_REF,
                                   LIFT_CEILING_PP)

SUMMARY = f"{OUT}/mtf_quality_survey.json"

# ترتیبِ اجرا: طلا از ریزترین تایم‌فریمِ موجود (M5 — چون M1 برای طلا داده ندارد)
# سپس به سمتِ بالا، بعد یورو. مطابقِ «از xauusd و ریزترین tf شروع کن».
ORDER = ['XAUUSD-M5', 'XAUUSD-M15', 'XAUUSD-M30', 'XAUUSD-H1',
         'XAUUSD-H4', 'XAUUSD-D1', 'XAUUSD-W1',
         'EURUSD-M1', 'EURUSD-M5', 'EURUSD-M15', 'EURUSD-M30']


def _load(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def summarize_card(card, min_n_survey=100):
    """سه سنجهٔ کیفیت را از JSONِ sweep یک کارت بیرون می‌کشد."""
    d = _load(f"{OUT}/{card}_sweep.json")
    if not d or not d.get('rows'):
        return None
    rows = d['rows']
    # فقط هندسه‌هایی که n پس‌از‌صفِ معناداری دارند (نه نمونهٔ چند‌تایی)
    elig = [r for r in rows if r.get('base_n', 0) >= min_n_survey]
    if not elig:
        elig = rows
    best = max(elig, key=lambda r: r.get('base_wr_min', -1))
    reach = [r for r in elig if r.get('reachable')]
    return dict(
        card=card,
        n_geoms=len(rows),
        n_eligible=len(elig),
        best_q=round(best.get('base_wr_min', 0.0), 2),
        best_q_n=int(best.get('base_n', 0)),
        best_q_pf=round(best.get('base_pf', 0.0), 3),
        best_q_geom=best.get('geom'),
        gap_to_floor=round(WR_FLOOR_REF - best.get('base_wr_min', 0.0), 2),
        n_reachable=len(reach),
        max_n=int(max(r.get('base_n', 0) for r in elig)),
    )


def run(cards=None, min_base_n=100, wr_min_base=51.0, min_n_survey=100):
    cards = cards or ORDER
    os.makedirs(OUT, exist_ok=True)
    out = _load(SUMMARY) or {}
    for card in cards:
        if card not in CARDS:
            print(f"  skip {card}: not in CARDS", flush=True)
            continue
        if card in out:
            print(f"  skip {card}: already surveyed "
                  f"(best_q={out[card]['best_q']})", flush=True)
            continue
        t0 = time.time()
        print(f"\n########## SURVEY {card} ##########", flush=True)
        try:
            sweep_card(card, min_base_n=min_base_n, top_k=24,
                       wr_min_base=wr_min_base)
        except Exception as e:
            print(f"  !! {card} failed: {type(e).__name__}: {e}", flush=True)
            out[card] = dict(card=card, error=f"{type(e).__name__}: {e}")
            json.dump(out, open(SUMMARY, 'w'), indent=1, default=float)
            continue
        s = summarize_card(card, min_n_survey=min_n_survey)
        if s is None:
            out[card] = dict(card=card, error='no rows')
        else:
            s['secs'] = round(time.time() - t0, 1)
            out[card] = s
            g = s['best_q_geom'] or {}
            print(f"  >>> SURVEY {card}: best_q={s['best_q']}% "
                  f"(n={s['best_q_n']} PF={s['best_q_pf']}) "
                  f"gap={s['gap_to_floor']:+.2f}pp "
                  f"reachable={s['n_reachable']}/{s['n_eligible']} "
                  f"| {g.get('mode')}/{g.get('side')} p={g.get('p')} "
                  f"m={g.get('mult')} sl={g.get('sl_k')} rr={g.get('rr')} "
                  f"h={g.get('hold')}", flush=True)
        # ⚠️ ذخیرهٔ فوری پس از هر کارت (قانونِ اندک اندک)
        json.dump(out, open(SUMMARY, 'w'), indent=1, default=float)

    print("\n================ MTF QUALITY SURVEY ================", flush=True)
    print(f"floor={WR_FLOOR_REF}%  lift_ceiling={LIFT_CEILING_PP}pp", flush=True)
    rank = sorted([v for v in out.values() if 'best_q' in v],
                  key=lambda v: -v['best_q'])
    for v in rank:
        flag = 'REACHABLE' if v['gap_to_floor'] <= LIFT_CEILING_PP else '  dead   '
        print(f"  {v['card']:12s} best_q={v['best_q']:5.2f}% "
              f"gap={v['gap_to_floor']:+6.2f}pp {flag} "
              f"n={v['best_q_n']:6d} maxN={v['max_n']:6d} "
              f"reach={v['n_reachable']:3d}", flush=True)
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    run(args or None)
