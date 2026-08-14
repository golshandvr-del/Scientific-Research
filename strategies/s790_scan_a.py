# -*- coding: utf-8 -*-
"""
S790 — اسکنِ اکتشافیِ Weekend Gap Fade روی XAUUSD-M1 (فقط نیمهٔ اول — مسیر C)
================================================================================
ایده: شکافِ بازگشاییِ دوشنبه به‌سوی closeِ جمعه جاذبه دارد (عدم‌توازنِ سفارش).
معامله: fade — شکافِ بالا ⇒ short، شکافِ پایین ⇒ long.
هندسه: **متقارن و برخاسته از خود پدیده** — TP = SL = |gap| (پیپ). هیچ عددِ
گِردی دست‌چین نمی‌شود؛ اندازهٔ هر معامله را خودِ شکاف تعیین می‌کند.

پارامترهای آزاد (خانوادهٔ کوچک، فیبوناچی):
  th ∈ {13, 21, 34, 55}        حداقل |gap| به پیپ (کف: هزینهٔ 3.3pip باید کوچک بماند)
  max_hold ∈ {377, 987, 1597}  کندلِ M1 (≈ 6h / 16h / 27h)
⇒ ۱۲ پیکربندی. جست‌وجو فقط روی نیمهٔ اول؛ نیمهٔ دوم برای آزمونِ یگانهٔ نهایی
مُهر و موم است.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

d = fd.load_fast('XAUUSD', 'M1')
df = fd.as_dataframe(d)
print('src =', d['src'])
n = len(df)
half = n // 2
df = df.iloc[:half].reset_index(drop=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values; c = df['close'].values
print('EXPLORATION HALF ONLY:', np.datetime64(int(t[0]), 's'), '→',
      np.datetime64(int(t[-1]), 's'), f'({len(df)} bars)')

pip = 0.10
dt = np.diff(t)
gap_prev = np.where(dt > 24 * 3600)[0]        # اندیسِ کندلِ جمعه (قبل از شکاف)
gap_pip = (o[gap_prev + 1] - c[gap_prev]) / pip   # + یعنی شکافِ بالا

print(f'weekend gaps: {len(gap_prev)}')

for th in (13, 21, 34, 55):
    sel = np.abs(gap_pip) >= th
    idx = gap_prev[sel]              # سیگنال روی کندلِ جمعه ⇒ ورود در openِ دوشنبه
    gp = gap_pip[sel]
    # هندسهٔ per-bar: sl=tp=|gap| روی کندلِ سیگنال
    sl_arr = np.zeros(len(df))   # 0 ⇒ شبیه‌ساز کندل را رد می‌کند (sl_d <= 0)
    sl_arr[idx] = np.abs(gp)
    long_sig = np.zeros(len(df), dtype=bool)
    short_sig = np.zeros(len(df), dtype=bool)
    long_sig[idx[gp < 0]] = True     # شکافِ پایین ⇒ خرید به‌سوی پُرشدن
    short_sig[idx[gp > 0]] = True    # شکافِ بالا ⇒ فروش به‌سوی پُرشدن
    for mh in (377, 987, 1597):
        tr = se.simulate_trades(df, long_sig, short_sig,
                                sl_pip=sl_arr, tp_pip=sl_arr,
                                asset='XAUUSD', max_hold=mh,
                                allow_overlap=False)
        if len(tr) == 0:
            print(f'th={th:3d} mh={mh:5d}  n=0'); continue
        p = tr['pnl_pip'].values
        wr = float(np.mean(p > 0))
        nl = int(np.sum(tr['direction'] == 'long'))
        wr_l = float(np.mean(tr.loc[tr['direction'] == 'long', 'pnl_pip'] > 0)) if nl else float('nan')
        wr_s = float(np.mean(tr.loc[tr['direction'] == 'short', 'pnl_pip'] > 0)) if nl < len(tr) else float('nan')
        print(f'th={th:3d} mh={mh:5d}  n={len(tr):4d}  WR={wr*100:5.1f}%  '
              f'avg={np.mean(p):+7.2f}pip  net={np.sum(p):+9.0f}pip  '
              f'long n={nl} WR={wr_l*100:5.1f}%  short n={len(tr)-nl} WR={wr_s*100:5.1f}%')
