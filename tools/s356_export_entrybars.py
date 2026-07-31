# -*- coding: utf-8 -*-
"""
`S356` — استخراجِ **مجموعهٔ ورودِ** لایه، برای ممیزیِ اجباریِ همپوشانی
================================================================================

قانونِ همپوشانیِ پروژه می‌گوید پیش از افزودنِ هر لایه باید بدانیم «با کدام
لایه/لایه‌های موجود همپوشانی دارد و چند درصد» — و این ممیزی نباید به مرحلهٔ بعد
موکول شود. این اسکریپت **سمتِ ما** از آن ممیزی را می‌سازد: اندیسِ کندلِ ورود و
مُهرِ زمانیِ هر ورودِ لایهٔ `S356` روی کارتِ پذیرفته‌شده.

### چرا `rebuild_card` را دوباره نمی‌نویسیم
منطقِ ساختِ کارت (بارگذاری، گیتِ رژیم، سیگنالِ causal، براکتِ مقیاس‌شده با ATR)
عیناً از `tools/s356_hires_null.rebuild_card` وارد می‌شود. اگر آن را اینجا
بازنویسی می‌کردیم، دو نسخه از یک منطق داشتیم که می‌توانند از هم دور شوند و
ممیزیِ همپوشانی روی مجموعه‌ای انجام شود که با مجموعهٔ داوری‌شده یکی نیست —
یعنی خطایی که کشفش تقریباً ناممکن است.

### دو مجموعهٔ ورود، و اینکه کدام «مجموعهٔ ورود» است
* `signal_bars` : هر کندلی که شرطِ ورودِ لایه در آن برقرار است (پیش از قاعدهٔ
  ناهم‌پوشانی). این مجموعهٔ **قانونِ لایه** است.
* `trade_bars`  : زیرمجموعه‌ای که شبیه‌سازِ رویداد-محور واقعاً معامله باز کرد
  (پس از حذفِ سیگنال‌هایی که در دلِ معاملهٔ بازِ قبلی افتاده‌اند).

برای ممیزیِ همپوشانی **`trade_bars` ملاک است**، چون همپوشانیِ عملی یعنی «آن
معامله‌ای که کاربر واقعاً می‌گیرد با معاملهٔ لایهٔ دیگر یکی است یا نه» — نه
همپوشانیِ شرط‌های نظری‌ای که هرگز به معامله تبدیل نشدند. هر دو نوشته می‌شود تا
هر دو خوانش قابلِ بازرسی بماند.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se                              # noqa: E402
from tools.s356_hires_null import rebuild_card                     # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', '_scan_S356')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--card', default='XAUUSD-H1')
    a = ap.parse_args()

    C = rebuild_card(a.card)
    df, asset = C['df'], C['asset']
    sl, tp, mh = C['sl'], C['tp'], C['mh']

    # سیگنالِ خامِ لایه (شرطِ قانون) — همان آرایه‌ای که `rebuild_card` ساخته است.
    sig = C['sig'] if 'sig' in C else None
    if sig is None:
        # `rebuild_card` سیگنال را برنمی‌گرداند؛ از `picks` بازسازی می‌کنیم.
        sig = np.zeros(len(df), bool)
        sig[C['picks']] = True

    signal_bars = np.flatnonzero(np.asarray(sig)).tolist()

    # معامله‌های واقعیِ شبیه‌سازِ رویداد-محور (با قاعدهٔ ناهم‌پوشانی).
    tr = se.simulate_trades(df, np.asarray(sig), np.zeros(len(df), bool),
                            sl, tp, asset, max_hold=mh, allow_overlap=False)
    ecol = next((c for c in ('entry_bar', 'entry_idx', 'bar', 'idx')
                 if tr is not None and c in tr.columns), None)
    trade_bars = ([int(x) for x in tr[ecol].to_numpy()]
                  if (tr is not None and ecol) else [])

    tcol = 'time' if 'time' in df.columns else df.columns[0]
    tvals = df[tcol].to_numpy()

    def stamps(idx):
        out = []
        for i in idx:
            v = tvals[i]
            try:
                out.append(str(np.datetime_as_string(np.datetime64(v), unit='s')))
            except Exception:
                out.append(str(v))
        return out

    rec = dict(
        card=a.card, asset=asset, bars=int(len(df)),
        sl_pip=sl, tp_pip=tp, max_hold=mh,
        n_signal=len(signal_bars), n_trade=len(trade_bars),
        signal_bars=signal_bars, trade_bars=trade_bars,
        signal_times=stamps(signal_bars), trade_times=stamps(trade_bars),
        note=('trade_bars مبنای ممیزیِ همپوشانی است (همپوشانیِ عملی)؛ '
              'signal_bars مجموعهٔ شرطِ قانون است.'),
    )
    os.makedirs(OUT_DIR, exist_ok=True)
    fn = os.path.join(OUT_DIR, f'{a.card}_entrybars.json')
    with open(fn, 'w', encoding='utf-8') as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)

    print(f'=== {a.card} :: bars={len(df):,} signals={len(signal_bars)} '
          f'trades={len(trade_bars)}')
    if trade_bars:
        print(f'    اولین معامله: {rec["trade_times"][0]}   '
              f'آخرین: {rec["trade_times"][-1]}')
    print(f'[saved] {os.path.relpath(fn)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
