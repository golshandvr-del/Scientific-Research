# -*- coding: utf-8 -*-
"""
S790 — جدولِ چندبازه‌ایِ گزارشی (تعریفِ منجمدِ PREREG؛ فقط گزارش، نه جست‌وجو)
================================================================================
حکم REJECT صادر شده؛ این جدول طبق قانونِ چندبازه‌ای فقط ثبتِ مشاهده است.
D1/W1/MN1 حذف: «جارویِ سطحِ روزِ قبل» درون‌روزی است و در کندلِ روزانه بی‌معنا.
چک‌پوینت به‌ازای هر TF در s790_mtf_ckpt.json.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se

CKPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 's790_mtf_ckpt.json')
TFS = ['M1','M2','M3','M4','M5','M6','M10','M12','M15','M20','M30','H1','H2','H3','H4','H6','H8','H12']
DTH, RTH, K_GEOM = 1.0, 0.236, 2.618
MH_HOURS = 48.0
pip = 0.10
rows = {}
if os.path.exists(CKPT):
    rows = json.load(open(CKPT))

for TF in TFS:
    if TF in rows:
        continue
    d = fd.load_fast('XAUUSD', TF)
    df = fd.as_dataframe(d)
    t = df['time'].values.astype(np.int64)
    h = df['high'].values; l = df['low'].values; c = df['close'].values
    n = len(df)
    tf_min = fd.TF_MINUTES[TF]
    mh = max(2, int(round(MH_HOURS * 60 / tf_min)))
    day = t // 86400
    day_id = np.cumsum(np.r_[True, np.diff(day) != 0]) - 1
    n_days = day_id[-1] + 1
    dh = np.full(n_days, -np.inf); dl = np.full(n_days, np.inf)
    np.maximum.at(dh, day_id, h); np.minimum.at(dl, day_id, l)
    ph = np.full(n, np.nan); pl = np.full(n, np.nan)
    m = day_id >= 1
    ph[m] = dh[day_id[m]-1]; pl[m] = dl[day_id[m]-1]
    tr_ = np.maximum(h-l, np.maximum(np.abs(h-np.r_[c[0],c[:-1]]), np.abs(l-np.r_[c[0],c[:-1]])))
    atr = np.empty(n); a = tr_[0]; kk = 2.0/90.0
    for i in range(n):
        a = a + kk*(tr_[i]-a); atr[i] = a
    atr = np.r_[np.nan, atr[:-1]]
    sw_hi = (h>ph)&(c<ph)&((h-ph)/atr>=DTH)&((ph-c)/atr>=RTH)
    sw_lo = (l<pl)&(c>pl)&((pl-l)/atr>=DTH)&((c-pl)/atr>=RTH)
    def fpd(sig):
        out = np.zeros(n,bool); seen = np.zeros(n_days,bool)
        for i in np.where(sig)[0]:
            if not seen[day_id[i]]: seen[day_id[i]]=True; out[i]=True
        return out
    ls, ss = fpd(sw_lo), fpd(sw_hi)
    sl_arr = np.where(np.isnan(atr), 0.0, K_GEOM*atr/pip)
    tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                             asset='XAUUSD', max_hold=mh, allow_overlap=False)
    if len(tr2)==0:
        rows[TF] = {'n':0}; json.dump(rows, open(CKPT,'w')); continue
    p = tr2['pnl_pip'].values
    split = n//2
    oos = tr2['entry_bar'].values >= split
    rows[TF] = {
        'n': int(len(tr2)), 'wr': round(float(np.mean(p>0))*100,2),
        'net': round(float(np.sum(p)),0),
        'is_wr': round(float(np.mean(p[~oos]>0))*100,2) if (~oos).sum() else None,
        'oos_wr': round(float(np.mean(p[oos]>0))*100,2) if oos.sum() else None,
        'oos_net': round(float(np.sum(p[oos])),0) if oos.sum() else None,
        'src': d['src'],
    }
    json.dump(rows, open(CKPT,'w'))
    r = rows[TF]
    print(f"{TF:4s} n={r['n']:5d} WR={r['wr']:5.1f}% net={r['net']:+8.0f}p "
          f"IS={r['is_wr']}% OOS={r['oos_wr']}% oos_net={r['oos_net']:+.0f}p", flush=True)

print('DONE', flush=True)
