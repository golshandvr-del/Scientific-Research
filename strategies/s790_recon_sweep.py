# -*- coding: utf-8 -*-
"""
S790-b — رصدِ اکتشافیِ «جارویِ نقدینگیِ روزِ قبل» (Prior-Day Sweep Fade) — XAUUSD
================================================================================
⚠️ مسیر C: فقط نیمهٔ اولِ داده. نیمهٔ دوم مُهر و موم.

رخداد (سبکِ ICT / turtle-soup، صفر اندیکاتور در تعریف):
  sweep-high: high[i] > سقفِ روزِ قبل  و  close[i] < سقفِ روزِ قبل  ⇒ کاندیدِ short
  sweep-low : low[i]  < کفِ روزِ قبل   و  close[i] > کفِ روزِ قبل   ⇒ کاندیدِ long
  فقط *نخستین* رخدادِ هر سمت در هر روز (جلوگیری از خوشه‌بندی).

هندسه: متقارن SL=TP=k·ATR89 (k فیبوناچی‌وار). این رصد فقط فراوانی و WRِ خام
پس از هزینهٔ کامل را می‌سنجد.
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

# ---- سقف/کفِ روزِ قبل (روزِ تقویمیِ UTC) ----
day = t // 86400
day_change = np.r_[True, np.diff(day) != 0]
day_id = np.cumsum(day_change) - 1          # شمارهٔ روزِ هر کندل
n_days = day_id[-1] + 1
d_high = np.full(n_days, -np.inf)
d_low = np.full(n_days, np.inf)
np.maximum.at(d_high, day_id, h)
np.minimum.at(d_low, day_id, l)
prev_high = np.full(n, np.nan)
prev_low = np.full(n, np.nan)
mask = day_id >= 1
prev_high[mask] = d_high[day_id[mask] - 1]
prev_low[mask] = d_low[day_id[mask] - 1]

# ---- ATR89 (بدونِ نگاه به آینده: shift 1) ----
tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.full(n, np.nan)
k_ = 2.0 / 90.0
a = tr_[0]
for i in range(n):
    a = a + k_ * (tr_[i] - a)
    atr[i] = a
atr = np.r_[np.nan, atr[:-1]]               # فقط اطلاعِ کندلِ قبل

sw_hi = (h > prev_high) & (c < prev_high)   # شکستِ ناکامِ سقف ⇒ short
sw_lo = (l < prev_low) & (c > prev_low)     # شکستِ ناکامِ کف ⇒ long

# نخستین رخدادِ هر سمت در هر روز
def first_per_day(sig):
    out = np.zeros(n, dtype=bool)
    seen = np.zeros(n_days, dtype=bool)
    idx = np.where(sig)[0]
    for i in idx:
        dd = day_id[i]
        if not seen[dd]:
            seen[dd] = True
            out[i] = True
    return out

short_sig = first_per_day(sw_hi)
long_sig = first_per_day(sw_lo)
print(f'events: short(sweep-high)={short_sig.sum()}  long(sweep-low)={long_sig.sum()}'
      f'  days={n_days}')

pip = 0.10
for k in (0.618, 1.0, 1.618, 2.618):
    sl_arr = np.where(np.isnan(atr), 0.0, k * atr / pip)
    for mh_bars in (48, 96, 288):           # بر حسبِ کندلِ همین TF
        tr = se.simulate_trades(df, long_sig, short_sig,
                                sl_pip=sl_arr, tp_pip=sl_arr,
                                asset='XAUUSD', max_hold=mh_bars,
                                allow_overlap=False)
        if len(tr) == 0:
            continue
        p = tr['pnl_pip'].values
        isl = tr['direction'] == 'long'
        wl = float(np.mean(tr.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else float('nan')
        ws = float(np.mean(tr.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else float('nan')
        print(f'k={k:5.3f} mh={mh_bars:3d}  n={len(tr):5d}  WR={np.mean(p>0)*100:5.1f}%  '
              f'avg={np.mean(p):+7.2f}pip  net={np.sum(p):+10.0f}pip  '
              f'long n={int(isl.sum())} WR={wl*100:5.1f}%  short n={int((~isl).sum())} WR={ws*100:5.1f}%')
