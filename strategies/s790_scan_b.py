# -*- coding: utf-8 -*-
"""
S790-c — اسکنِ شرطیِ جارویِ نقدینگی: عمقِ نفوذ × قدرتِ بازگشت — XAUUSD (نیمهٔ اول)
================================================================================
⚠️ مسیر C: فقط نیمهٔ اول. نیمهٔ دوم مُهر و موم.

فرضیهٔ ریزساختاری: جارویی که *عمیق* از سطحِ روزِ قبل بگذرد (حدضررهای بیشتری
بردارد) و *قاطعانه* به داخل برگردد (ردِ شکست)، بازگشتِ قوی‌تری می‌دهد.

شرط‌ها (ساختاری، بر حسبِ ATR89 — بدونِ عددِ گِرد):
  depth = نفوذِ فتیله از سطح / ATR      ∈ {>=0.236, >=0.5, >=1.0}
  reclaim = فاصلهٔ close از سطح / ATR    ∈ {>=0 (هر), >=0.236}
هندسه: متقارن SL=TP=1.618·ATR (بهترین تعادلِ اسکنِ قبلی؛ ثابت نگه می‌داریم
تا آزادیِ هندسی خرج نشود). max_hold=96.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'M5'
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

day = t // 86400
day_id = np.cumsum(np.r_[True, np.diff(day) != 0]) - 1
n_days = day_id[-1] + 1
d_high = np.full(n_days, -np.inf); d_low = np.full(n_days, np.inf)
np.maximum.at(d_high, day_id, h)
np.minimum.at(d_low, day_id, l)
prev_high = np.full(n, np.nan); prev_low = np.full(n, np.nan)
m = day_id >= 1
prev_high[m] = d_high[day_id[m] - 1]
prev_low[m] = d_low[day_id[m] - 1]

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

sw_hi = (h > prev_high) & (c < prev_high)
sw_lo = (l < prev_low) & (c > prev_low)
depth_hi = (h - prev_high) / atr        # عمقِ نفوذ بالای سقف
depth_lo = (prev_low - l) / atr
recl_hi = (prev_high - c) / atr         # قدرتِ بازگشتِ close به زیرِ سقف
recl_lo = (c - prev_low) / atr

def first_per_day(sig):
    out = np.zeros(n, dtype=bool)
    seen = np.zeros(n_days, dtype=bool)
    for i in np.where(sig)[0]:
        if not seen[day_id[i]]:
            seen[day_id[i]] = True; out[i] = True
    return out

pip = 0.10
K = 1.618
sl_arr = np.where(np.isnan(atr), 0.0, K * atr / pip)

print(f'{"depth":>7} {"recl":>6} | {"n":>5} {"WR":>6} {"avg":>8} {"net":>10} | long WR | short WR')
for dth in (0.236, 0.5, 1.0):
    for rth in (0.0, 0.236):
        s_sig = first_per_day(sw_hi & (depth_hi >= dth) & (recl_hi >= rth))
        l_sig = first_per_day(sw_lo & (depth_lo >= dth) & (recl_lo >= rth))
        tr2 = se.simulate_trades(df, l_sig, s_sig, sl_pip=sl_arr, tp_pip=sl_arr,
                                 asset='XAUUSD', max_hold=96, allow_overlap=False)
        if len(tr2) == 0:
            print(f'{dth:7.3f} {rth:6.3f} | n=0'); continue
        p = tr2['pnl_pip'].values
        isl = tr2['direction'] == 'long'
        wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else float('nan')
        ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else float('nan')
        print(f'{dth:7.3f} {rth:6.3f} | {len(tr2):5d} {np.mean(p>0)*100:5.1f}% '
              f'{np.mean(p):+7.2f}p {np.sum(p):+9.0f}p | '
              f'{int(isl.sum()):4d}/{wl*100:5.1f}% | {int((~isl).sum()):4d}/{ws*100:5.1f}%')
