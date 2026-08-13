# -*- coding: utf-8 -*-
"""
S830 — کاوشِ ۳: مقیاس‌سنجیِ «بازگشت پس از وحشتِ فروش» روی تایم‌فریم‌های بالا
==============================================================================
ادامهٔ کاوشِ ۲ (که H1 را برنده نشان داد: lift=+9.3pp). هنوز اکتشاف است و
**فقط ۶۰٪ اولِ داده** دیده می‌شود. پرسش: آیا لبه با بالا رفتنِ مقیاس قوی‌تر
می‌شود؟ H2, H3, H6, H8, H12, D1 آزموده می‌شوند.

هزینه: 3.3pip اسپرد در شبیه‌ساز لحاظ است؛ be_cost با میانهٔ SL گزارش می‌شود.
این جست‌وجو بعداً با مسیرِ C (holdout) پرداخت می‌شود — فضای کشف اینجا
ثبت و شمرده می‌شود.
"""
import sys, os, gc
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

TFS = ['H2', 'H3', 'H6', 'H8', 'H12', 'D1']
W_LIST = [8, 13, 21]          # پنجرهٔ سقوطِ تجمعی (fib)
K_LIST = [2.5, 3.5]           # آستانهٔ z
SLM_LIST = [1.3, 2.1]         # sl = slm * ATR(34)
RR_LIST = [1.0, 1.6]          # tp = rr * sl
MAX_HOLD = {'H2': 21, 'H3': 13, 'H6': 13, 'H8': 8, 'H12': 8, 'D1': 5}
MIN_EVENTS = 40               # کندل کمتر ⇒ آستانهٔ رویداد پایین‌تر (صادقانه گزارش می‌شود)

def atr_series(h, l, c, p=34):
    prev_c = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = np.empty_like(tr)
    atr[0] = tr[0]
    alpha = 1.0 / p
    for i in range(1, len(tr)):
        atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
    return atr

for tf in TFS:
    d = fd.load_fast('XAUUSD', tf)
    n_all = len(d['close'])
    split = int(n_all * 0.60)
    df = fd.as_dataframe(d).iloc[:split].reset_index(drop=True)
    c = df['close'].values.astype(np.float64)
    h = df['high'].values.astype(np.float64)
    l = df['low'].values.astype(np.float64)
    r = np.concatenate([[0.0], np.diff(np.log(c))])
    lam = 0.97
    sig2 = np.empty_like(r); sig2[0] = np.var(r[:500]) if len(r) > 500 else np.var(r)
    for i in range(1, len(r)):
        sig2[i] = lam * sig2[i-1] + (1 - lam) * r[i]*r[i]
    sig = np.sqrt(np.maximum(sig2, 1e-18))
    atr = atr_series(h, l, c, 34)
    atr_pip = atr / 0.10

    print(f'\n===== {tf}  (explore bars={split:,}  src={d["src"]}) =====', flush=True)
    for W in W_LIST:
        cs = np.cumsum(r)
        cum = np.concatenate([[np.nan]*W, cs[W:] - cs[:-W]])[:len(r)]
        zW = cum / (sig * np.sqrt(W))
        for k in K_LIST:
            sig_mask = zW < -k
            sig_mask[:600] = False
            n_ev = int(np.nansum(sig_mask))
            if n_ev < MIN_EVENTS:
                print(f'  W={W} k={k}: only {n_ev} events — skip', flush=True)
                continue
            for slm in SLM_LIST:
                for rr in RR_LIST:
                    slp = np.clip(atr_pip * slm, 8, 5000)
                    tpp = slp * rr
                    tr_df = se.simulate_trades(df, sig_mask, np.zeros(len(df), bool),
                                               sl_pip=slp, tp_pip=tpp, asset='XAUUSD',
                                               max_hold=MAX_HOLD[tf], allow_overlap=False)
                    if len(tr_df) < 30:
                        continue
                    pnl = tr_df['pnl_pip'].values
                    wr = float((pnl > 0).mean() * 100)
                    exp = float(pnl.mean())
                    med_sl = float(np.median(tr_df['sl_pip']))
                    med_tp = med_sl * rr
                    be = (med_sl + 3.3) / (med_sl + med_tp) * 100
                    print(f'  W={W} k={k} slm={slm} rr={rr}: n={len(tr_df):6,} '
                          f'WR={wr:5.2f}% be_cost={be:5.2f}% lift={wr-be:+6.2f}pp '
                          f'exp={exp:+7.2f}pip medSL={med_sl:.0f}', flush=True)
                    del tr_df
    del d, df, c, h, l, r, sig2, sig, atr, atr_pip
    gc.collect()
print('\n[high-TF scale exploration complete]', flush=True)
