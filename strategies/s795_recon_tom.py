#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
S795 RECON — Turn-of-Month Drift — XAUUSD
فرضیه: جریان‌های تقویمی ماهانه (حقوق/بازتوازن صندوق‌ها — Ogden 1990;
Etula et al. 2020 "Dash for Cash") در گردشِ ماه فشار خرید ایجاد می‌کند؛
روی طلا خانوادهٔ تقویمی سابقهٔ ACCEPT دارد (S312 mid-month, S432 pool) اما
پنجرهٔ ToM هرگز با RQS2 داوری نشده (فقط سند NetProfit قدیمی).
LONG-only در پنجرهٔ [T_start, T_end] روزِ معاملاتی نسبت به مرز ماه
(منفی = آخر ماه جاری، مثبت = اول ماه بعد). ورود: open اولین کندل روزِ شروع؛
خروج: زمانی (mh کندل) + براکت ایمنی پهن SL=TP=4.236×ATR89.
اکتشاف فقط نیمهٔ اول (Path C). usage: python3 s795_recon_tom.py [TF]
"""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/home/user/webapp')
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TF = sys.argv[1] if len(sys.argv) > 1 else 'H3'
PIP = 0.10

d = fd.load_fast('XAUUSD', TF)
df = fd.as_dataframe(d)
o = df['open'].values; h = df['high'].values; l = df['low'].values
c = df['close'].values
ts = df['time'].values.astype(np.int64)
n = len(c); split = n // 2
t = pd.to_datetime(ts, unit='s')
print(f"src={d['src']} | TF={TF} | bars={n} | discovery=first {split}", flush=True)

# trading-day segmentation by time gap (S560 lesson)
tf_sec = fd.TF_MINUTES[TF] * 60
gap = np.r_[10**9, np.diff(ts)]
day_start = gap > max(1800, int(1.5 * tf_sec))
first_idx = np.where(day_start)[0]
n_days = len(first_idx)
day_month = np.array([t[i].year * 12 + t[i].month for i in first_idx])
# trading-day offset relative to month boundary:
# for each day k, if month changes at k+j (first day of new month has index m0),
# offset = k - m0 (so first day of month = 0, last day of prev month = -1)
month_first_day = np.r_[0, np.where(np.diff(day_month) != 0)[0] + 1]
offset = np.full(n_days, 99, int)
for mi, m0 in enumerate(month_first_day):
    m1 = month_first_day[mi+1] if mi+1 < len(month_first_day) else n_days
    for k in range(m0, m1):
        fwd = k - m0                       # 0,1,2,... from month start
        back = k - m1                      # ..., -2, -1 to month end
        offset[k] = fwd if fwd <= abs(back) else back

# ATR89 shifted (for safety bracket)
pc = np.r_[c[0], c[:-1]]
tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
atr = np.empty(n); a0 = tr[0]; kk = 2.0/90.0
for i in range(n):
    a0 = a0 + kk*(tr[i]-a0); atr[i] = a0
atr = np.r_[np.nan, atr[:-1]]
valid = ~np.isnan(atr)
bars_per_day = max(1, round(1440 / fd.TF_MINUTES[TF]))

def run(t_start, hold_days, side='long'):
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    for k in range(n_days):
        if offset[k] != t_start: continue
        i = first_idx[k]
        if i - 1 < 0 or i >= n: continue
        # signal on the bar BEFORE the day's first bar => entry at open of first bar
        sig = i - 1
        if side == 'long': ls[sig] = True
        else: ss[sig] = True
    ls &= valid; ss &= valid
    ls[split:] = False; ss[split:] = False
    mh = hold_days * bars_per_day
    sl = np.where(valid, 4.236 * atr / PIP, 0.0)
    trd = se.simulate_trades(df, ls, ss, sl, sl, 'XAUUSD',
                             max_hold=mh, allow_overlap=False)
    if trd is None or len(trd) == 0: return dict(n=0, wr=np.nan, exp=np.nan, net=0)
    nn = len(trd); net = trd['pnl_pip'].sum()
    return dict(n=nn, wr=100*(trd['pnl_pip']>0).mean(), exp=net/nn, net=net)

print(f'{"start":>6} {"holdD":>5} {"side":>5} | {"n":>4} {"WR%":>6} {"exp":>8} {"net":>9}')
for t_start in (-4, -3, -2, -1, 0, 1, 2):
    for hold_days in (2, 3, 5):
        m = run(t_start, hold_days, 'long')
        print(f'{t_start:>6} {hold_days:>5} {"long":>5} | {m["n"]:>4} {m["wr"]:>6.2f} '
              f'{m["exp"]:>8.2f} {m["net"]:>9.1f}', flush=True)
# control: short in same windows (should be negative if flow story true)
for t_start in (-1, 0):
    m = run(t_start, 3, 'short')
    print(f'{t_start:>6} {3:>5} {"short":>5} | {m["n"]:>4} {m["wr"]:>6.2f} '
          f'{m["exp"]:>8.2f} {m["net"]:>9.1f}', flush=True)
