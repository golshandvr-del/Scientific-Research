# -*- coding: utf-8 -*-
"""ساختِ fixture پریتیِ S965 — پایتونِ مرجع ↔ TSِ سایت.

خروجی: results/_scan_S965/parity_h8_fixture.json
  candles       : ۳۰۰۰ کندلِ آخرِ H8 (همان چیزی که سایت می‌بیند)
  py.idx_long   : ایندکسِ سیگنال‌های LONG پایتون **در فضای همین ۳۰۰۰ کندل**
  py.idx_short  : همان برای SHORT
  py.sl_pip     : SL پیپیِ هر ایندکسِ سیگنال (هندسهٔ شناور از atr_prev)
  py.tp_pip     : TP پیپی

مرجعِ پایتون **روی کلِ تاریخ (۱۱٬۹۷۸ کندل)** محاسبه می‌شود و بعد برش می‌خورد،
تا اگر پورتِ TS به warm-up وابسته باشد اختلاف لو برود.

اجرا: python3 web_tool/tools/make_s965_fixture.py
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from strategies import s965_kyle_intrabar_permanence as S  # noqa: E402
from tools import s434_fast_data as fd                     # noqa: E402
from engine import scalp_engine as se                      # noqa: E402

TF = 'H8'
TAIL = 3000
CFG = dict(th=2.618, arm='hi', R=0.618, mode='follow',
           k_sl=1.272, k_tp=2.058)
OUT = 'results/_scan_S965/parity_h8_fixture.json'


def main():
    d = fd.load_fast('XAUUSD', TF)
    n = len(d['close'])
    df = S._views_df(d)
    pip = se.ASSETS['XAUUSD']['pip']

    shock, rho, body_sgn, atr_prev = S.features(df, CFG['th'])
    ls, ss = S.member_signals(shock, rho, body_sgn,
                              CFG['arm'], CFG['R'], CFG['mode'], S.WARM)

    off = n - TAIL
    idx_long = [int(i) - off for i in np.flatnonzero(ls) if i >= off]
    idx_short = [int(i) - off for i in np.flatnonzero(ss) if i >= off]

    sl_arr = np.maximum(CFG['k_sl'] * atr_prev / pip, 1e-9)
    tp_arr = np.maximum(CFG['k_tp'] * atr_prev / pip, 1e-9)

    candles = [dict(time=int(d['time'][i]), open=float(d['open'][i]),
                    high=float(d['high'][i]), low=float(d['low'][i]),
                    close=float(d['close'][i]),
                    volume=float(d['volume'][i]))
               for i in range(off, n)]

    fx = dict(
        tf=TF, src=d['src'], n_bars_full=n, tail=TAIL, offset=off,
        cfg=CFG, warm=S.WARM,
        candles=candles,
        py=dict(
            idx_long=idx_long, idx_short=idx_short,
            # مرجعِ عددیِ ویژگی‌ها روی همین دم (برای مقایسهٔ سخت‌گیرانه)
            atr_prev=[float(x) for x in atr_prev[off:]],
            rho=[float(x) for x in rho[off:]],
            sl_pip=[float(x) for x in sl_arr[off:]],
            tp_pip=[float(x) for x in tp_arr[off:]],
        ),
    )
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(fx, open(OUT, 'w'))
    print(f'fixture written: {OUT}  candles={len(candles)} '
          f'long={len(idx_long)} short={len(idx_short)}')


if __name__ == '__main__':
    main()
