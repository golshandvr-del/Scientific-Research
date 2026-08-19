# -*- coding: utf-8 -*-
"""
S792 — رصدِ اکتشافی: خوشه‌بندیِ جریانِ سفارش (Order-Flow Persistence) — XAUUSD
================================================================================
⚠️ مسیر C: فقط نیمهٔ اول. ⚠️ بلوکِ شماره: S790–S799.

فرضیه (Kyle 1985، تقطیعِ سفارش‌های بزرگ): کندلِ پُردامنه‌ای که در
منتهی‌الیهِ دامنه‌اش بسته شود = فشارِ یک‌سویهٔ جذب‌نشده ⇒ ادامه در کندل‌های بعد.

رخداد (صفر اندیکاتور؛ ATR فقط مقیاس):
  big : range_i >= r_th·ATR89
  clv = (close−low)/range ; >= 1−q ⇒ long کاندید ; <= q ⇒ short کاندید
اسکن: r_th ∈ {1.0, 1.618, 2.618} · q ∈ {0.236, 0.146} · k_geom ∈ {1.618, 2.618}
      · mh ∈ {8, 21} · ورود openِ بعد · متقارن SL=TP.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'M15'
d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
print('src =', d['src'], '| TF =', TF)
n0 = len(df)
df = df.iloc[:n0 // 2].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values; h = df['high'].values
l = df['low'].values; c = df['close'].values
n = len(df)
print('EXPLORATION HALF ONLY:', np.datetime64(int(t[0]), 's'), '→',
      np.datetime64(int(t[-1]), 's'), f'({n} bars)')

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

rng_ = h - l
clv = np.where(rng_ > 0, (c - l) / np.where(rng_ > 0, rng_, 1.0), 0.5)
pip = 0.10

for r_th in (1.0, 1.618, 2.618):
    big = rng_ >= r_th * atr
    for q in (0.236, 0.146):
        ls = big & (clv >= 1 - q)
        ss = big & (clv <= q)
        for kg in (1.618, 2.618):
            sl_arr = np.where(np.isnan(atr), 0.0, kg * atr / pip)
            for mh in (8, 21):
                tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                                         asset='XAUUSD', max_hold=mh, allow_overlap=False)
                if len(tr2) == 0:
                    continue
                p = tr2['pnl_pip'].values
                isl = tr2['direction'] == 'long'
                wl = float(np.mean(tr2.loc[isl,'pnl_pip']>0)) if isl.sum() else float('nan')
                ws = float(np.mean(tr2.loc[~isl,'pnl_pip']>0)) if (~isl).sum() else float('nan')
                print(f'r={r_th:5.3f} q={q:.3f} k={kg:5.3f} mh={mh:2d}  n={len(tr2):6d}  '
                      f'WR={np.mean(p>0)*100:5.1f}%  avg={np.mean(p):+6.2f}p  net={np.sum(p):+9.0f}p  '
                      f'L{int(isl.sum())}/{wl*100:.1f}%  S{int((~isl).sum())}/{ws*100:.1f}%', flush=True)
