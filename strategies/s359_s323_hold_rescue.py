# -*- coding: utf-8 -*-
"""
S359 — نجاتِ `S323` از دروازهٔ `H5` از راهِ **آزادکردنِ سیگنال‌های مسدود**

═══════════════════════════════════════════════════════════════════════════
چرا این مسیر، بعد از شکستِ مسیرِ فیلتر
═══════════════════════════════════════════════════════════════════════════
`s358` هشتادوهشت فیلترِ اصولی را آزمود و بهترینش `z=3.423` در برابر سدِ
`3.506` داد — یعنی شکست. علتِ شکست **ریاضی** بود، نه بدشانسی:

    z = (WR − ref) · √n / √(ref·(1−ref))

هر فیلتر هم‌زمان `WR` را بالا و `n` را پایین می‌برد. بهترین نامزد `WR` را از
۷۲.۵٪ به ۸۱٪ رساند ولی `n` را از ۱۶۰ به ۶۳ کوباند: ضریبِ `√n` از ۱۲.۶ به ۷.۹
افتاد و کلِ سودِ WR را بلعید. آن فیلتر ۶۵ برد را قربانی کرد تا ۳۲ باخت را حذف
کند — یعنی چیزی نزدیک به «نازک‌کردنِ تصادفی»، نه تشخیص.

اما همان فرمول یک درِ دیگر باز می‌گذارد که مسیرِ فیلتر آن را نادیده گرفت:
**افزایشِ `n` با ثابت‌ماندنِ `WR`**. حسابِ فاصله می‌گوید `n=184` با همان
۷۲.۵٪ برای عبور کافی است — یعنی فقط ۲۴ معاملهٔ بیشتر.

═══════════════════════════════════════════════════════════════════════════
⭐ مشاهدهٔ کلیدی: ۱۴۴ سیگنال دور ریخته می‌شود
═══════════════════════════════════════════════════════════════════════════
لایه روی `XAUUSD-M30` **۳۰۴ سیگنال** تولید می‌کند ولی فقط **۱۶۰ معامله** ثبت
می‌شود. اختلافِ ۱۴۴تایی به‌خاطرِ قاعدهٔ ناهم‌پوشانی است: تا وقتی معاملهٔ جاری
باز است هیچ ورودِ تازه‌ای پذیرفته نمی‌شود، و `maxHold=48` روی M30 یعنی یک
معامله می‌تواند تا **۲۴ ساعت** جای دیگران را اشغال کند.

آن `maxHold=48` هم — مهم‌تر از همه — **انتخابِ مستدلی نبوده**: از پیکربندیِ
کارتِ خواهر ارث رسیده. یعنی اینجا یک پارامترِ تصادفیِ ارثی دارد بیش از نیمی از
نمونهٔ آماریِ لایه را نابود می‌کند.

پس فرضیهٔ این اسکریپت:
    کوتاه‌کردنِ افقِ نگه‌داری، سیگنال‌های مسدود را آزاد می‌کند و `n` را بالا
    می‌برد؛ اگر `WR` فرو نریزد، `z` از راهِ `√n` بالا می‌رود.

این دقیقاً مصداقِ «قانونِ بهبود» است (تغییرِ اندازه/افقِ TP-SL یک بهبودِ مجاز
است) و هم‌زمان اشتباهِ رایج #۶ را رفع می‌کند: افقِ نگه‌داری نباید یک عددِ
ارثیِ مشترک باشد، باید متناسبِ همان تایم‌فریم انتخاب شود.

═══════════════════════════════════════════════════════════════════════════
دقتِ روش‌شناختی
═══════════════════════════════════════════════════════════════════════════
· تغییرِ `maxHold` **مدلِ صفر را هم عوض می‌کند** (براکتی که زودتر بسته می‌شود
  نرخِ بردِ بی‌قیدِ متفاوتی دارد). پس برای هر افق، مبنا از نو ساخته می‌شود؛
  مقایسه با مبنای افقِ قدیم تقلبِ آشکار بود.
· افق‌ها غیررند و از نسبت‌های فیبوناچی/لوکاس گرفته شده‌اند (اشتباهِ رایج #۷)
  و همگی از افقِ فعلی کوتاه‌ترند یا کمی بلندتر تا جهتِ اثر معلوم شود.
· بهترین فیلترِ `s358` (شاخصِ اره‌ای در جهتِ بالا) روی هر افق هم آزموده می‌شود،
  چون ممکن است ترکیبِ «افقِ کوتاه‌تر + فیلتر» از هرکدام به‌تنهایی بهتر باشد؛
  «قانونِ همکاریِ بهبودها» همین را می‌خواهد.
· هر آزمونِ اجراشده صادقانه در `n_trials` شمرده می‌شود و روی سرجمعِ
  ۲۴۰۰ (ساختِ اصلی) + ۸۸ (اسکنِ `s358`) سوار می‌گردد. هیچ آزمونی پنهان نیست.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import indicators as ind          # noqa: E402
from engine import rqs2 as R2                 # noqa: E402
from engine import scalp_engine as se         # noqa: E402
from engine import indicator_bank as BANK     # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s357_s323_v24_rejudge import (           # noqa: E402
    cfg_for, signals_backtested, outcome_table, wr_of,
)
from s358_s323_h5_rescue import binom_z, perm_mean_for   # noqa: E402

CARD = 'XAUUSD-M30'
OUT_DIR = 'results/_s359_s323_hold'

N_TRIALS_PRIOR = 2400 + 88      # ساختِ اصلی + اسکنِ فیلترِ s358
SEEDS = (23, 101, 777)
K_SCAN = 600

# افق‌های آزمودنی — غیررند، از نسبت‌های فیبوناچی/لوکاس روی مقیاسِ M30.
# ۴۸ (فعلی) هم هست تا مبنای مقایسه در همین جدول دیده شود.
HOLDS = (11, 18, 24, 29, 34, 47, 48, 76)

# جهتِ فیلترِ برندهٔ s358 (شاخصِ اره‌ای، نگه‌داشتنِ مقادیرِ بالا) + حالتِ بی‌فیلتر
CHOP_QUANTILES = (None, 0.30, 0.45, 0.60)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    asset, tf = CARD.split('-')
    df = se.load_data(os.path.join('data', f'{asset}_{tf}.csv'))
    if 'dt' not in df.columns:
        df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)

    cfg = cfg_for(CARD)
    atr14 = ind.atr(df, 14).values
    pip = se.ASSETS[asset]['pip']
    atr_pip_med = float(np.nanmedian(atr14[260:]) / pip)
    sl = round(cfg['slMult'] * atr_pip_med, 1)
    tp = round(cfg['tpMult'] * atr_pip_med, 1)

    sig = signals_backtested(df, asset, cfg)
    idx = np.flatnonzero(sig)
    chop = BANK.compute('chop', df).values.astype(float)

    print(f"{CARD}  SL={sl}pip TP={tp}pip RR={tp/sl:.3f}  سیگنالِ خام={len(idx)}",
          flush=True)
    print(f"سدِ فعلی = expected_max_z({N_TRIALS_PRIOR}) = "
          f"{R2.expected_max_z(N_TRIALS_PRIOR):.3f}\n", flush=True)

    rows = []
    trials = 0
    t0 = time.time()
    for mh in HOLDS:
        # مدلِ صفرِ مخصوصِ همین افق — بازسازیِ کامل، نه بازاستفاده
        res, xbar = outcome_table(df, asset, sl, tp, mh)
        valid = np.arange(260, max(261, len(df) - mh - 2))
        valid = valid[res[valid] != 0]
        uncond = wr_of(valid, res, xbar)

        for q in CHOP_QUANTILES:
            trials += 1
            if q is None:
                mask = sig.copy()
                tag = 'بی‌فیلتر'
            else:
                sv = chop[idx]
                thr = float(np.quantile(sv[np.isfinite(sv)], q))
                keep = np.isfinite(sv) & (sv >= thr)
                mask = np.zeros(len(df), dtype=bool)
                mask[idx[keep]] = True
                tag = f'chop≥q{q:.2f}'

            tr = se.simulate_trades(df, mask, np.zeros(len(df), bool), sl, tp,
                                    asset, max_hold=mh, allow_overlap=False)
            if tr is None or len(tr) < 30:
                continue
            n = len(tr)
            w = int((tr['pnl_pip'] > 0).sum())
            pm = perm_mean_for(res, xbar, valid, n, K_SCAN, SEEDS[0])
            ref = max(uncond, pm)
            z = binom_z(w, n, ref / 100.0)
            rows.append(dict(mh=mh, filt=tag, q=q, n=n, wins=w,
                             wr=round(100.0 * w / n, 2),
                             uncond=round(uncond, 2), perm_mean=round(pm, 2),
                             ref=round(ref, 2),
                             lift=round(100.0 * w / n - ref, 2), z=round(z, 3)))

    zbar = R2.expected_max_z(N_TRIALS_PRIOR + trials)
    print(f"{trials} آزمون در {time.time()-t0:.0f}s — سدِ جدید = "
          f"expected_max_z({N_TRIALS_PRIOR}+{trials}) = {zbar:.3f}\n", flush=True)

    rows.sort(key=lambda r: -r['z'])
    print(f"{'mh':>4s} {'filter':>12s} {'n':>4s} {'WR':>6s} {'uncond':>7s} "
          f"{'ref':>6s} {'lift':>6s} {'z':>6s}")
    for r in rows:
        flag = ' ✅' if r['z'] > zbar else ''
        print(f"{r['mh']:4d} {r['filt']:>12s} {r['n']:4d} {r['wr']:6.2f} "
              f"{r['uncond']:7.2f} {r['ref']:6.2f} {r['lift']:6.2f} "
              f"{r['z']:6.3f}{flag}")

    out = dict(card=CARD, sl_pip=sl, tp_pip=tp,
               n_trials_prior=N_TRIALS_PRIOR, n_trials_scan=trials,
               n_trials_total=N_TRIALS_PRIOR + trials,
               z_bar=round(zbar, 3), holds=list(HOLDS),
               chop_quantiles=[q for q in CHOP_QUANTILES], rows=rows)
    path = os.path.join(OUT_DIR, 'hold_scan.json')
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"\n→ wrote {path}")


if __name__ == '__main__':
    main()
