# -*- coding: utf-8 -*-
"""
S791 — رصدِ اکتشافی: شکستِ دامنهٔ آغازینِ روز (Opening Range Breakout) — XAUUSD
================================================================================
⚠️ مسیر C: فقط نیمهٔ اولِ داده. نیمهٔ دوم مُهر و موم.
⚠️ محدودهٔ شماره: S790–S799 (بلوکِ این دانشمند). فایل‌های دیگران لمس نمی‌شود.

فرضیه (ضدِ درسِ S790): طلا در ساعاتِ آغازینِ روزِ معاملاتی (جلسهٔ آسیا)
دامنه می‌سازد؛ نخستین شکستِ آن دامنه جهت‌دار است (continuation، نه fade).

تعریف (ساختاری، صفر اندیکاتور در رخداد):
  - دامنه = high/low در K ساعتِ نخستِ روزِ داده (روزِ تقویمیِ سرور)
  - سیگنال: نخستین کندلی که *بیرونِ* دامنه close کند (بالای high ⇒ long؛
    زیرِ low ⇒ short)؛ فقط یک معامله در روز و فقط در همان روز
  - هندسه: متقارن SL=TP=k·ATR89 · max_hold تا پایانِ روز (~بقیهٔ روز)
اسکن: K ∈ {3,5,8} ساعت · k ∈ {1.0, 1.618, 2.618}
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
tf_min = fd.TF_MINUTES[TF]
print('EXPLORATION HALF ONLY:', np.datetime64(int(t[0]), 's'), '→',
      np.datetime64(int(t[-1]), 's'), f'({n} bars)')

day = t // 86400
day_id = np.cumsum(np.r_[True, np.diff(day) != 0]) - 1
n_days = day_id[-1] + 1
day_start = np.zeros(n_days, dtype=np.int64)      # اندیسِ نخستین کندلِ هر روز
seen = np.zeros(n_days, dtype=bool)
for i in range(n):
    dd = day_id[i]
    if not seen[dd]:
        seen[dd] = True; day_start[dd] = i
day_end = np.r_[day_start[1:], n]                  # اندیسِ پایانِ (exclusive) هر روز

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

pip = 0.10

def build_sigs(K_hours):
    bars_or = max(1, int(round(K_hours * 60 / tf_min)))
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    for dd in range(1, n_days):
        s0, e0 = day_start[dd], day_end[dd]
        if e0 - s0 < bars_or + 2:
            continue
        orb_hi = np.max(h[s0:s0 + bars_or])
        orb_lo = np.min(l[s0:s0 + bars_or])
        # نخستین close بیرونِ دامنه در ادامهٔ همان روز
        for j in range(s0 + bars_or, e0 - 1):
            if c[j] > orb_hi:
                ls[j] = True; break
            if c[j] < orb_lo:
                ss[j] = True; break
    return ls, ss

# max_hold: تا پایانِ روز — تقریب: 24h - K ساعت (بر حسب کندل)
for K_hours in (3, 5, 8):
    ls, ss = build_sigs(K_hours)
    mh = max(2, int(round((24 - K_hours) * 60 / tf_min)))
    for kg in (1.0, 1.618, 2.618):
        sl_arr = np.where(np.isnan(atr), 0.0, kg * atr / pip)
        tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                                 asset='XAUUSD', max_hold=mh, allow_overlap=False)
        if len(tr2) == 0:
            continue
        p = tr2['pnl_pip'].values
        isl = tr2['direction'] == 'long'
        wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else float('nan')
        ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else float('nan')
        print(f'K={K_hours}h k={kg:5.3f}  n={len(tr2):5d}  WR={np.mean(p>0)*100:5.1f}%  '
              f'avg={np.mean(p):+6.2f}p  net={np.sum(p):+9.0f}p  '
              f'L {int(isl.sum())}/{wl*100:.1f}%  S {int((~isl).sum())}/{ws*100:.1f}%', flush=True)
