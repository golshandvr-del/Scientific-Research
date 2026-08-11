# -*- coding: utf-8 -*-
"""
s437_virgin_card_scout.py — **پیش‌سنجشِ توان روی کارت‌های دست‌نخورده**
=======================================================================

🎯 **پرسشِ دقیق:** خانوادهٔ `SoS` (Brooks فصل ۱۹) روی کارت‌هایی که باتریِ
جست‌وجوی `S202` **هرگز نگشته**، چند معامله در سال تولید می‌کند — و آیا آن
نرخ برای عبور از سدِ `H3 = ۳.۰۹` کافی است؟

──────────────────────────────────────────────────────────────────────
## چرا این گام **قبل** از پیش‌ثبت انجام می‌شود

درسِ مستقیمِ `E-17`. در `S436` اول پیش‌ثبت کردم، بعد ۱۹۲۸ واحد بودجه خرج
کردم، و **آخر** فهمیدم که نامزد با ~۱۹ معامله در سال هرگز نمی‌توانست پاس
شود. این اسکریپت همان محاسبه را **قبل** انجام می‌دهد و هیچ بودجه‌ای مصرف
نمی‌کند، چون **هیچ داوری‌ای انجام نمی‌دهد** — فقط می‌شمارد.

> ⚠️ **این اسکریپت عمداً `compute_rqs2` را صدا نمی‌زند.** شمارشِ سیگنال و
> معامله یک اندازه‌گیریِ توصیفی است، نه یک آزمونِ فرضیه؛ پس `n_trials`
> مصرف نمی‌کند. اگر اینجا حتی یک آستانه را «بهینه» کنم، آن دیگر پیش‌سنجش
> نیست و باید در بودجه شمرده شود. پس پیکربندی **دقیقاً همان `CAND`** ثابتِ
> `S435` می‌ماند و **هیچ پارامتری جست‌وجو نمی‌شود**.

──────────────────────────────────────────────────────────────────────
## نقشهٔ باتریِ مصرف‌شدهٔ خانوادهٔ `SoS` (از `priority_rank.json`)

| کارت | ردیف‌های آزموده | وضعیت |
|---|---|---|
| `XAUUSD-H1` | ۱۹ | ☠️ باتری مصرف‌شده — `S435` همان‌جا مرد |
| `XAUUSD-M15` | ۴ | ⚠️ تا حدی گشته (`S171`, `S203`, `S204`) |
| `XAUUSD-M30` · `H4` · `M5` | ۰ | 🎯 دست‌نخورده |
| `EURUSD-*` | ۰ | 🎯 دست‌نخورده (**هرگز** روی یورو آزموده نشده) |

توصیهٔ صریحِ `S435` §۱۰: «`SoS` را روی کارتی بیازمایید که باتریِ `S202`
آن را نگشته است — مثلاً `M30` یا `H4` یا روی `EURUSD`.»

──────────────────────────────────────────────────────────────────────
## معیارِ عبور از پیش‌سنجش (پیش‌ثبت‌شده در همین فایل، قبل از اجرا)

با `p₀ ≈ ۰.۵۰` و سدِ `z = ۳.۰۹` (کارتِ دست‌نخورده ⇒ `H3` غالب است چون
`expected_max_z(240) < 3.09`):

```
n_لازم(lift) = (3.09 · 100 · √0.25 / lift)²
```

| لیفتِ فرضی | n لازم |
|---|---|
| ۴pp | ۱۴۹۲ |
| ۶pp | ۶۶۳ |
| ۷.۰۸pp (مشاهده‌شده روی M15) | **۴۷۶** |
| ۱۰pp | ۲۳۹ |

**کارت از پیش‌سنجش عبور می‌کند اگر:** `n_معامله ≥ ۴۷۶`، یعنی توان برای
تکرارِ لیفتِ ۷.۰۸ کافی باشد. کارتی که کمتر تولید کند، حتی با لبهٔ کاملاً
واقعی، **نباید** بودجهٔ چندگانگی مصرف کند مگر از راهِ تجمیع.

⚠️ **این معیار سخت‌گیرانه است و عمداً.** فرضِ `p₀=۰.۵۰` بدترین حالت است
(بیشینهٔ واریانس)؛ اگر `p₀` واقعی دورتر از ۰.۵ باشد، `n` لازم **کمتر**
می‌شود ⇒ خطا به نفعِ محافظه‌کاری.
"""
from __future__ import annotations

import json
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'strategies'))

from engine import scalp_engine as se                       # noqa: E402
from engine.rqs2 import UNPROVEN_Z_H3                       # noqa: E402
import tools.s435_coverage_union as cov                     # noqa: E402

OUT = os.path.join(ROOT, 'results/_s437_scout')

# کارت‌های موردِ کاوش. `H1` و `M15` **عمداً** گنجانده شده‌اند به‌عنوانِ
# **شاهدِ منفی**: اگر ابزار روی کارتی که `S435` سنجیده عددِ متفاوتی بدهد،
# یعنی ابزار خراب است. (درسِ `BUG-LPSBIMPORT`: دو ابزار باید یک لایه بسازند.)
CARDS = {
    'XAUUSD-M5':  'data/mt5_full/XAUUSD_M5.csv.gz',
    'XAUUSD-M15': 'data/mt5_full/XAUUSD_M15.csv.gz',
    'XAUUSD-M30': 'data/mt5_full/XAUUSD_M30.csv.gz',
    'XAUUSD-H1':  'data/mt5_full/XAUUSD_H1.csv.gz',
    'XAUUSD-H2':  'data/mt5_full/XAUUSD_H2.csv.gz',
    'XAUUSD-H3':  'data/mt5_full/XAUUSD_H3.csv.gz',
    'XAUUSD-H6':  'data/mt5_full/XAUUSD_H6.csv.gz',
    'EURUSD-M5':  'data/EURUSD_M5.csv',
    'EURUSD-M15': 'data/EURUSD_M15.csv',
    'EURUSD-M30': 'data/EURUSD_M30.csv',
    'EURUSD-H1':  'data/EURUSD_H1.csv',
    'EURUSD-H4':  'data/EURUSD_H4.csv',
}

# باتریِ مصرف‌شده — از `results/_s432_priority/priority_rank.json` شمرده شد.
BATTERY = {'XAUUSD-H1': 19, 'XAUUSD-M15': 4}

# هندسه — عیناً از `S171`/`S205` (پیپِ طلا و یورو متفاوت است ⇒ نسبت ثابت
# می‌ماند نه عددِ مطلق). `SL:TP = 1:2` ⇒ سربه‌سرِ هزینه‌دار پایین.
GEOM = {'XAUUSD': dict(sl=150, tp=300, mh=96),
        'EURUSD': dict(sl=50,  tp=100, mh=96)}

LIFT_REF = 7.08          # لیفتِ مشاهده‌شدهٔ `S171` روی M15
P0_WORST = 0.50          # بیشینهٔ واریانس ⇒ محافظه‌کارانه


def n_required(lift_pp: float, p0: float = P0_WORST,
               z: float = UNPROVEN_Z_H3) -> float:
    """همان فرمولِ `engine.rqs2.n_required_for_h3` — کپی، نه بازنویسی."""
    return (z * 100.0 * math.sqrt(p0 * (1.0 - p0)) / float(lift_pp)) ** 2


def load_card(path: str) -> pd.DataFrame:
    df = se.load_data(os.path.join(ROOT, path))
    if 'dt' not in df.columns:
        for c in ('time', 'datetime', 'date'):
            if c in df.columns:
                df['dt'] = pd.to_datetime(df[c])
                break
    return df


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    need = n_required(LIFT_REF)
    print(f'[S437 کاوشِ کارتِ دست‌نخورده] سد z={UNPROVEN_Z_H3} · '
          f'لیفتِ مرجع={LIFT_REF}pp ⇒ n لازم={need:,.0f}')
    print(f'{"card":13} {"bars":>8} {"years":>6} {"sig":>6} {"trades":>7} '
          f'{"tr/yr":>7} {"ratio":>6} {"battery":>8}  verdict')

    rows = []
    for card, path in CARDS.items():
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            print(f'{card:13} ⛔ فایل نیست: {path}')
            continue
        try:
            df = load_card(path)
            asset = card.split('-')[0]
            g = GEOM[asset]
            sig = cov.sos_edge(df)
            t = se.simulate_trades(df, sig, np.zeros(len(df), bool),
                                   g['sl'], g['tp'], asset,
                                   max_hold=g['mh'], allow_overlap=False)
            n_tr = 0 if t is None else len(t)
            span = float((df['dt'].iloc[-1] - df['dt'].iloc[0]).days) / 365.25
            rate = n_tr / span if span > 0 else 0.0
            ratio = n_tr / need if need else 0.0
            bat = BATTERY.get(card, 0)
            verdict = ('VIRGIN-OK' if (ratio >= 1.0 and bat == 0) else
                       'VIRGIN-LOW' if bat == 0 else
                       'SPENT-OK' if ratio >= 1.0 else 'SPENT-LOW')
            print(f'{card:13} {len(df):>8,} {span:>6.1f} {int(sig.sum()):>6} '
                  f'{n_tr:>7} {rate:>7.1f} {ratio:>6.2f} {bat:>8}  {verdict}')
            rows.append(dict(card=card, bars=len(df), years=round(span, 2),
                             n_signal_bars=int(sig.sum()), n_trades=n_tr,
                             trades_per_year=round(rate, 2),
                             power_ratio=round(ratio, 4), battery_rows=bat,
                             verdict=verdict, geometry=g))
        except Exception as e:                                # noqa: BLE001
            print(f'{card:13} ⛔ خطا: {type(e).__name__}: {e}')
            rows.append(dict(card=card, error=f'{type(e).__name__}: {e}'))

    with open(os.path.join(OUT, 'virgin_scout.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(lift_ref=LIFT_REF, p0=P0_WORST, z_bar=UNPROVEN_Z_H3,
                       n_required=round(need, 1), rows=rows),
                  f, ensure_ascii=False, indent=1)
    print(f'\n  ✅ ذخیره شد ⇒ {OUT}/virgin_scout.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
