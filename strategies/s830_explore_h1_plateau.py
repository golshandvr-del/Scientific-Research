# -*- coding: utf-8 -*-
"""
S830 — کاوشِ ۴: (الف) حذفِ ریاضیِ M1 با هندسهٔ هزینه، (ب) فلاتِ همسایگیِ H1
==============================================================================
هنوز اکتشاف است — فقط ۶۰٪ اولِ داده.

(الف) M1: به‌جای شبیه‌سازیِ کامل (که OOM می‌دهد)، میانهٔ ATR(34) در پنجرهٔ
اکتشاف محاسبه و be_cost تحلیلی گزارش می‌شود. اگر be_cost چنان بالا باشد که
حتی lift مشاهده‌شده در M5 (بهترین حالت پایین‌مقیاس) هم نتواند بپوشاند،
M1 به‌طور ریاضی حذف می‌شود — بدون نیاز به شبیه‌سازی.

(ب) H1: همسایگیِ سلولِ برنده (W=8,k=2.5,slm=2.1,rr=1.6) اسکن می‌شود تا
معلوم شود قله تک‌نقطه‌ای (نویز) است یا فلات (ساختار). این اسکن نیز جزءِ
فضای کشف است و در PREREG شمرده می‌شود.
"""
import sys, os, gc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

# ---------- (الف) حذف ریاضی M1 ----------
print('===== (A) M1 mathematical cost-geometry check =====', flush=True)
d = fd.load_fast('XAUUSD', 'M1')
n_all = len(d['close'])
split = int(n_all * 0.60)
c = d['close'][:split].astype(np.float32)
h = d['high'][:split].astype(np.float32)
l = d['low'][:split].astype(np.float32)
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
del h, l, prev_c, c
gc.collect()
# EWMA ATR(34) روی float32
atr = np.empty_like(tr)
atr[0] = tr[0]
alpha = np.float32(1.0 / 34)
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
del tr
gc.collect()
atr_pip = atr.astype(np.float64) / 0.10
del atr
gc.collect()
med_atr = float(np.median(atr_pip[600:]))
for slm in (1.3, 2.1):
    med_sl = max(float(np.median(np.clip(atr_pip[600:] * slm, 8, 5000))), 8.0)
    for rr in (1.0, 1.6):
        be = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
        be_free = 1.0 / (1.0 + rr) * 100
        print(f'  M1 slm={slm} rr={rr}: medSL={med_sl:.1f}pip  '
          f'be_cost={be:.2f}%  be_costfree={be_free:.2f}%  '
          f'cost_burden={be-be_free:+.2f}pp', flush=True)
print(f'  M1 median ATR(34) = {med_atr:.2f} pip  (spread=3.3 pip)', flush=True)
del atr_pip, d
gc.collect()

# ---------- (ب) فلات همسایگی H1 ----------
print('\n===== (B) H1 neighborhood plateau scan (explore 60% only) =====', flush=True)
d = fd.load_fast('XAUUSD', 'H1')
n_all = len(d['close'])
split = int(n_all * 0.60)
df = fd.as_dataframe(d).iloc[:split].reset_index(drop=True)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
r = np.concatenate([[0.0], np.diff(np.log(c))])
lam = 0.97
sig2 = np.empty_like(r); sig2[0] = np.var(r[:500])
for i in range(1, len(r)):
    sig2[i] = lam * sig2[i-1] + (1 - lam) * r[i]*r[i]
sig = np.sqrt(np.maximum(sig2, 1e-18))
prev_c = np.concatenate([[c[0]], c[:-1]])
tr_ = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr_); atr[0] = tr_[0]
alpha = 1.0 / 34
for i in range(1, len(tr_)):
    atr[i] = atr[i-1] + alpha * (tr_[i] - atr[i-1])
atr_pip = atr / 0.10

W_LIST = [5, 8, 13]
K_LIST = [2.0, 2.5, 3.0]
SLM_LIST = [1.7, 2.1, 2.6]
RR_LIST = [1.3, 1.6, 2.0]
HOLD = 21

for W in W_LIST:
    cs = np.cumsum(r)
    cum = np.concatenate([[np.nan]*W, cs[W:] - cs[:-W]])[:len(r)]
    zW = cum / (sig * np.sqrt(W))
    for k in K_LIST:
        sig_mask = zW < -k
        sig_mask[:600] = False
        n_ev = int(np.nansum(sig_mask))
        if n_ev < 60:
            print(f'  W={W} k={k}: only {n_ev} events — skip', flush=True)
            continue
        for slm in SLM_LIST:
            for rr in RR_LIST:
                slp = np.clip(atr_pip * slm, 8, 5000)
                tpp = slp * rr
                tr_df = se.simulate_trades(df, sig_mask, np.zeros(len(df), bool),
                                           sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                                           max_hold=HOLD, allow_overlap=False)
                if len(tr_df) < 30:
                    continue
                pnl = tr_df['pnl_pip'].values
                wr = float((pnl > 0).mean() * 100)
                exp = float(pnl.mean())
                med_sl = float(np.median(tr_df['sl_pip']))
                be = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
                print(f'  W={W} k={k} slm={slm} rr={rr}: n={len(tr_df):5,} '
                      f'WR={wr:5.2f}% be_cost={be:5.2f}% lift={wr-be:+6.2f}pp '
                      f'exp={exp:+7.2f}pip', flush=True)
                del tr_df
print('\n[plateau exploration complete]', flush=True)
