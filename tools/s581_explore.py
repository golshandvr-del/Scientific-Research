# -*- coding: utf-8 -*-
"""
s581_explore.py — اکتشافِ S581: فقط **نیمهٔ اولِ** XAUUSD-M1 (پیش‌ثبت §۳).

۳۶ نقطهٔ شمرده: sl_mult∈{8,11.17,16}×medATR14(نیمهٔ اول) · rr∈{1.5,2,2.5,3} · mh∈{30,60,120}
سیگنال و گیتِ رژیم منجمد (S334) — importشده، نه بازنویسی.

⚠️ نیمهٔ دوم در این اسکریپت هرگز لمس نمی‌شود: df پس از برش، حذف می‌شود.
نکتهٔ درستی: hurst/kurt/z/RSI همه علّی‌اند (پنجرهٔ گذشته‌نگر) ⇒ برشِ آرایه‌های
کش‌شدهٔ کلِ داده در اندیس‌های < split دقیقاً برابرِ محاسبه روی نیمهٔ اول است؛
از کشِ S580 استفاده می‌کنیم (صرفه‌جویی حافظه/زمان، بدون تغییرِ روش‌شناسی).

قاعدهٔ برنده (قفل‌شده): max expectancy_pip×√n بین نقاطِ n≥150 و net_pip>0.
تساوی: n بزرگ‌تر، سپس sl کوچک‌تر. اگر هیچ نقطه net>0 نداشت ⇒ مرگِ صادقانه.
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time as _time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, 'strategies'), os.path.join(ROOT, 'tools')):
    if p not in sys.path:
        sys.path.insert(0, p)

from engine import scalp_engine as se                       # noqa: E402
from engine import indicator_bank as ib                     # noqa: E402
from tools import s434_fast_data as fd                      # noqa: E402
import strategies.s334_mr_short_revival as s334             # noqa: E402

OUT = os.path.join(ROOT, 'results', '_s581_explore.json')
CACHE = os.path.join(ROOT, 'results', '_s580_regime_cache')

SL_MULTS = (8.0, 11.17, 16.0)
RRS = (1.5, 2.0, 2.5, 3.0)
MHS = (30, 60, 120)


def main() -> int:
    d = fd.load_fast('XAUUSD', 'M1')
    df = fd.as_dataframe(d)
    n_all = len(df)
    split = n_all // 2
    print(f'[S581 اکتشاف] src={d["src"]}\n  کل={n_all:,} · split={split:,} '
          f'({pd.to_datetime(df["time"].iloc[split], unit="s")})')
    assert 'mt5_full' in str(d['src']), 'BUG-DATASETDRIFT'

    # رژیم از کشِ S580 (علّی ⇒ برش مجاز)
    cp = os.path.join(CACHE, f'XAUUSD_M1_n{n_all}.npz')
    z = np.load(cp)
    gate = (z['hurst'][:split] < 0.50) & (z['kurt'][:split] < 1.8)
    del z
    gc.collect()

    # فقط نیمهٔ اول — نیمهٔ دوم همین‌جا دور ریخته می‌شود
    df = df.iloc[:split][['time', 'open', 'high', 'low', 'close']].reset_index(drop=True)
    gc.collect()

    base = s334.build_short_mr(df, z_win=34, z_thr=2.4, rsi_thr=70)
    mask = base & gate
    del base, gate
    gc.collect()
    print(f'  سیگنالِ نیمهٔ اول = {int(mask.sum())}')

    atr = pd.Series(ib.atr_s(df, 14))
    pip = se.ASSETS['XAUUSD']['pip']                # گاردِ BUG-PIPGUESS
    med = float(atr.median()) / pip
    del atr
    gc.collect()
    print(f'  medianATR14(نیمهٔ اول) = {med:.2f} pip')

    rows = []
    empty = np.zeros(len(df), bool)
    t0 = _time.time()
    for slm in SL_MULTS:
        sl = round(slm * med, 1)
        for rr in RRS:
            tp = round(rr * sl, 1)
            for mh in MHS:
                tr = se.simulate_trades(df, empty, mask, sl, tp, 'XAUUSD',
                                        max_hold=mh, allow_overlap=False)
                if tr is None or len(tr) == 0:
                    rows.append(dict(sl_mult=slm, rr=rr, mh=mh, sl=sl, tp=tp,
                                     n=0, wr=None, exp_pip=None, net_pip=None,
                                     score=None))
                    continue
                pnl = tr['pnl_pip'].values
                n = int(len(pnl))
                wr = 100.0 * float((pnl > 0).mean())
                exp = float(pnl.mean())
                net = float(pnl.sum())
                score = exp * np.sqrt(n)
                rows.append(dict(sl_mult=slm, rr=rr, mh=mh, sl=sl, tp=tp,
                                 n=n, wr=round(wr, 2), exp_pip=round(exp, 3),
                                 net_pip=round(net, 1), score=round(score, 2)))
                print(f'  slm={slm:5.2f} rr={rr:.1f} mh={mh:3d} '
                      f'SL={sl:6.1f}/TP={tp:6.1f} n={n:4d} WR={wr:5.2f} '
                      f'exp={exp:+7.3f} net={net:+9.1f} score={score:+8.2f}')

    # قاعدهٔ برندهٔ قفل‌شده
    elig = [r for r in rows if r['n'] and r['n'] >= 150 and r['net_pip'] > 0]
    win = None
    if elig:
        win = sorted(elig, key=lambda r: (-r['score'], -r['n'], r['sl']))[0]
        print(f'\n🏆 برنده (قاعدهٔ پیش‌ثبت): {win}')
    else:
        print('\n❌ هیچ نقطه‌ای n≥150 و net>0 نداشت — مرگِ صادقانه در اکتشاف؛ '
              'آزمونِ تأییدی طبق پیش‌ثبت اجرا نمی‌شود.')

    out = dict(mission='S581', stage='explore_first_half', split_bar=split,
               n_bars_total=n_all, src=d['src'], median_atr_pip=round(med, 3),
               n_signals=int(mask.sum()), grid=rows, winner=win,
               elapsed_s=round(_time.time() - t0, 1))
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'✅ ذخیره: {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
