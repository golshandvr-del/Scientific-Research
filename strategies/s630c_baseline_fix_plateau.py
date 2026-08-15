# -*- coding: utf-8 -*-
"""
S630c — دو کارِ هم‌زمان (قانون بهبودهای چندگانه) — «فقط نیمهٔ نخست»
====================================================================
۱) رفع شکاف خط پایهٔ شورت در بازوی D: هر سمت شبیه‌سازیِ مستقل می‌گیرد
   (در s630b هر دو سمت با stride یکسان در یک شبیه‌سازی بودند و
    allow_overlap=False سمت شورت را حذف می‌کرد → base=None).
۲) آزمون فلاتِ گیتِ روند برای بازوی B (لانگ در روند صعودی):
   SMA ∈ {89, 100, 144, 200, 233} — طبق دکترین variants.md:
   «به فلات اعتماد کن، از قلهٔ تنها بگریز».
هر دو روی M30/H1 (مرز اعتبار IBS) و فقط نیمهٔ اول داده.
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'research', 's630_explore')
K_IBS, THR = 5, 0.235

def wrn(t, side=None):
    if side is not None and 'direction' in t:
        t = t[t['direction'] == side]
    if len(t) == 0: return None, 0
    return round(100*float((t['outcome']=='win').mean()),2), len(t)

def uncond_side(df, gate, side, sl_pip, tp_pip, stride=7):
    """خط مبنای بی‌قیدِ گیت‌خورده — یک سمت، شبیه‌سازی مستقل (رفع باگ s630b)."""
    base = pd.Series(False, index=df.index); base.iloc[::stride] = True
    sig = (base & gate).fillna(False)
    empty = pd.Series(False, index=df.index)
    lo, hi = (sig, empty) if side == 'long' else (empty, sig)
    t = se.simulate_trades(df, lo, hi, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset='XAUUSD', max_hold=64, allow_overlap=False)
    return wrn(t, side)

all_res = {}
for TF in ['M30', 'H1']:
    d = fd.load_fast('XAUUSD', TF)
    df = fd.as_dataframe(d)
    df = df.iloc[:len(df)//2].reset_index(drop=True)   # فقط نیمهٔ اول
    h,l,c = df['high'].values, df['low'].values, df['close'].values
    rng = h-l
    ibs = np.where(rng>0,(c-l)/np.where(rng>0,rng,1.0),0.5)
    ibs_k = pd.Series(ibs).rolling(K_IBS).mean()
    lo_sig = ((ibs_k.shift(1)>=THR)&(ibs_k<THR)).fillna(False)
    hi_sig = ((ibs_k.shift(1)<=1-THR)&(ibs_k>1-THR)).fillna(False)
    tr_ = np.maximum(h-l, np.maximum(abs(h-np.roll(c,1)), abs(l-np.roll(c,1)))); tr_[0]=h[0]-l[0]
    atr = pd.Series(tr_).rolling(100).mean().values
    sl_pip = float(np.nanmedian(atr))*1.5/0.1; tp_pip = sl_pip
    cs = pd.Series(c)
    empty = pd.Series(False, index=df.index)

    # ---------- بخش ۱: فلاتِ گیت B (لانگ در روند صعودی، SMA متغیر) ----------
    plateau = {}
    for P in [89, 100, 144, 200, 233]:
        sma = cs.rolling(P).mean()
        up = (cs > sma).fillna(False)
        sig = (lo_sig & up).fillna(False)
        t = se.simulate_trades(df, sig, empty, sl_pip=sl_pip, tp_pip=tp_pip,
                               asset='XAUUSD', max_hold=64, allow_overlap=False)
        bw, bn = uncond_side(df, up, 'long', sl_pip, tp_pip)
        w, n = wrn(t, 'long')
        lift = None if (w is None or bw is None) else round(w-bw, 2)
        pnl = round(float(t['pnl_pip'].mean()),3) if len(t) else None
        plateau[f'SMA{P}'] = dict(n=n, wr=w, base=bw, base_n=bn, lift=lift, pnl=pnl)
        print(TF, f'B_plateau SMA{P}', plateau[f'SMA{P}'], flush=True)

    # ---------- بخش ۲: بازوی D با خط پایهٔ شورتِ درست ----------
    sma144 = cs.rolling(144).mean()
    dn = (cs < sma144).fillna(False)
    hi_g = (hi_sig & dn).fillna(False)
    t = se.simulate_trades(df, empty, hi_g, sl_pip=sl_pip, tp_pip=tp_pip,
                           asset='XAUUSD', max_hold=64, allow_overlap=False)
    sw, sn = wrn(t, 'short')
    bw, bn = uncond_side(df, dn, 'short', sl_pip, tp_pip)
    lift = None if (sw is None or bw is None) else round(sw-bw, 2)
    pnl = round(float(t['pnl_pip'].mean()),3) if len(t) else None
    d_short = dict(n=sn, wr=sw, base=bw, base_n=bn, lift=lift, pnl=pnl)
    print(TF, 'D_short_fixed', d_short, flush=True)

    all_res[TF] = dict(sl_pip=sl_pip, B_plateau=plateau, D_short_fixed=d_short)

with open(f'{OUT}/s630c_plateau_shortfix.json','w') as f:
    json.dump(all_res,f,ensure_ascii=False,indent=1)
print('saved -> s630c_plateau_shortfix.json')
