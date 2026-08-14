# -*- coding: utf-8 -*-
"""
S790-d — اسکنِ متمرکزِ M15: هندسه × نگهداری روی جارویِ عمیقِ تأییدشده
================================================================================
⚠️ مسیر C: فقط نیمهٔ اول. شرطِ رخداد از اسکنِ قبلی قفل شد:
   depth >= 1.0·ATR , reclaim >= 0.236·ATR , نخستین رخدادِ روز، هر دو سمت.
آزادِ باقی‌مانده: k (SL=TP=k·ATR89) و max_hold. + تفکیکِ long/short و
سهمِ خروج‌های timeout برای فهمِ ساختارِ سود.
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

DTH, RTH = 1.0, 0.236
sw_hi = (h > prev_high) & (c < prev_high) & ((h - prev_high) / atr >= DTH) & ((prev_high - c) / atr >= RTH)
sw_lo = (l < prev_low) & (c > prev_low) & ((prev_low - l) / atr >= DTH) & ((c - prev_low) / atr >= RTH)

def first_per_day(sig):
    out = np.zeros(n, dtype=bool)
    seen = np.zeros(n_days, dtype=bool)
    for i in np.where(sig)[0]:
        if not seen[day_id[i]]:
            seen[day_id[i]] = True; out[i] = True
    return out

short_sig = first_per_day(sw_hi)
long_sig = first_per_day(sw_lo)
print(f'events: long={long_sig.sum()} short={short_sig.sum()}')

pip = 0.10
print(f'{"k":>6} {"mh":>4} | {"n":>4} {"WR":>6} {"avg":>8} {"net":>9} {"tmo%":>5} | long n/WR | short n/WR')
for K in (1.0, 1.618, 2.618, 4.236):
    sl_arr = np.where(np.isnan(atr), 0.0, K * atr / pip)
    for mh in (96, 192, 384, 672):
        tr2 = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_arr, tp_pip=sl_arr,
                                 asset='XAUUSD', max_hold=mh, allow_overlap=False)
        if len(tr2) == 0:
            continue
        p = tr2['pnl_pip'].values
        tmo = float(np.mean(tr2['bars_held'] >= mh - 1))
        isl = tr2['direction'] == 'long'
        wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else float('nan')
        ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else float('nan')
        print(f'{K:6.3f} {mh:4d} | {len(tr2):4d} {np.mean(p>0)*100:5.1f}% '
              f'{np.mean(p):+7.2f}p {np.sum(p):+8.0f}p {tmo*100:4.0f}% | '
              f'{int(isl.sum()):4d}/{wl*100:5.1f}% | {int((~isl).sum()):4d}/{ws*100:5.1f}%')
