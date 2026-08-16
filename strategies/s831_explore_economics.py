# -*- coding: utf-8 -*-
"""
S831 — کاوشِ ۵: بهینه‌سازی اقتصاد (PF) برای sweep-short — XAUUSD-H1
=====================================================================
فقط پنجره‌ی اکتشاف. کاوش ۴ نشان داد lift پایدار است (+7..+10pp در دو نیمه)
اما exp ضعیف — و گیت H1 (PF>=1.3) قاتل خواهد بود (درس S830: PF=1.047 ⇒ REJECT).
پرسش: آیا هندسه‌ای هست که PF>=1.3 را در پنجره‌ی اکتشاف بدهد و در هر دو
نیمه‌ی E1/E2 زنده بماند؟

رویداد ثابت: sweep_up_fail (prev_c<L, high>=L, close<L) — short
شبکه: G ∈ {25,50} × slm ∈ {1.0,1.4,1.8} × rr ∈ {2.0,2.6,3.4} × hold ∈ {8,21,34}
(rr بالاتر: برنده‌ها باید بزرگ شوند تا PF بالا برود؛ slm پایین‌تر: بازنده کوچک)
گزارش: PF کل + PF در E1 و E2 (پایداری).
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import s434_fast_data as fd
from engine import scalp_engine as se

SPLIT_IDX = 54798
WARMUP = 600
HALF = SPLIT_IDX // 2

d = fd.load_fast('XAUUSD', 'H1')
df = fd.as_dataframe(d).iloc[:SPLIT_IDX].reset_index(drop=True)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
atr_pip = atr / se.ASSETS['XAUUSD']['pip']

def pf_of(pnl):
    w = pnl[pnl > 0].sum(); lo = -pnl[pnl < 0].sum()
    return w / lo if lo > 0 else np.inf

print(f'explore bars={len(df):,}  src={d["src"]}', flush=True)
best = []
for G in (25.0, 50.0):
    lev = np.round(prev_c / G) * G
    ev = (prev_c < lev) & (h >= lev) & (c < lev)
    ev[:WARMUP] = False
    for slm in (1.0, 1.4, 1.8):
        slp = np.clip(atr_pip * slm, 8, 5000)
        for rr in (2.0, 2.6, 3.4):
            tpp = slp * rr
            for hold in (8, 21, 34):
                z0 = np.zeros(len(df), bool)
                tdf = se.simulate_trades(df, z0, ev, sl_pip=slp, tp_pip=tpp,
                                         asset='XAUUSD', max_hold=hold,
                                         allow_overlap=False)
                if len(tdf) < 60:
                    continue
                pnl = tdf['pnl_pip'].values
                eb = tdf['entry_bar'].values
                pf = pf_of(pnl)
                if pf < 1.05:
                    continue
                pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
                wr = float((pnl > 0).mean() * 100)
                exp = float(pnl.mean())
                med_sl = float(np.median(tdf['sl_pip']))
                be = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
                line = (f'G={G:.0f} slm={slm} rr={rr} hold={hold}: n={len(tdf):5,} '
                        f'WR={wr:5.2f}% lift={wr-be:+6.2f}pp exp={exp:+7.2f}pip '
                        f'PF={pf:.3f} [E1={pf1:.3f} E2={pf2:.3f}]')
                print(line, flush=True)
                best.append((min(pf1, pf2), line))

print('\n--- top by min(PF_E1, PF_E2) ---', flush=True)
for v, line in sorted(best, reverse=True)[:8]:
    print(f'minPF={v:.3f}  {line}', flush=True)
print('\n[S831 explore-5 complete]', flush=True)
