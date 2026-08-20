# -*- coding: utf-8 -*-
"""
S832 — کاوشِ ۴ (آخرین کارتِ این سرزمین): نگهداشتِ بلند + همراستاییِ روند
==========================================================================
منطق: تریل 1.0×ATR در کاوش ۳ PF را 1.064→1.135 برد یعنی «دویدنِ برنده» جوهرِ
این لبه است. دو اهرمِ باقی‌مانده:
  (الف) hold ∈ {21, 34, 55} — تریل خودش خروج را مدیریت می‌کند؛ سقفِ بلندتر
        شاید به روندهای چندروزه اجازه‌ی تنفس دهد.
  (ب) فیلتر همراستایی متقارن و درون‌زاد: فقط شکست‌هایی که با علامتِ
        (close − EMA200) هم‌جهت‌اند — long بالای EMA، short زیر EMA.
        آینه‌ای کامل؛ هیچ فرضِ جهتِ خارجی ندارد.
پایه‌ی ثابت: رنج آسیا 0..6، پنجره 7..16، اولین شکست روز، slm=2.1، trail=1.0×ATR،
be=هیچ (کاوش ۳ رد کرد)، rr ∈ {3.4, 6.0} (تریل عملاً خروج است؛ rr=6 یعنی TP دور).
گزارش: n, WR, lift, exp, PF [E1,E2]. فقط ۶۰٪ اکتشاف.
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
t = df['time'].values.astype(np.int64)
c = df['close'].values.astype(np.float64)
h = df['high'].values.astype(np.float64)
l = df['low'].values.astype(np.float64)
hour = (t // 3600) % 24
day = t // 86400
prev_c = np.concatenate([[c[0]], c[:-1]])
tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
atr = np.empty_like(tr); atr[0] = tr[0]
a = 1.0 / 34
for i in range(1, len(tr)):
    atr[i] = atr[i-1] + a * (tr[i] - atr[i-1])
atr_pip = atr / se.ASSETS['XAUUSD']['pip']
n = len(df)

# EMA200 علّی
ema = np.empty_like(c); ema[0] = c[0]
k = 2.0 / 201
for i in range(1, n):
    ema[i] = ema[i-1] + k * (c[i] - ema[i-1])
above = c > ema   # در کندل سیگنال (close همان کندل — علّی: ورود کندل بعد)

# رنج آسیا + اولین شکست (همان تعریف کاوش ۲)
rhi = np.full(n, np.nan); rlo = np.full(n, np.nan)
for dd in np.unique(day):
    m = (day == dd) & (hour <= 6)
    if m.sum() < 5:
        continue
    md = (day == dd) & (hour >= 7)
    rhi[md] = h[m].max(); rlo[md] = l[m].min()
in_win = (hour >= 7) & (hour <= 16)
brk_up = in_win & np.isfinite(rhi) & (c > rhi)
brk_dn = in_win & np.isfinite(rlo) & (c < rlo)
first = np.zeros(n, bool)
seen = set()
for i in range(n):
    if (brk_up[i] or brk_dn[i]) and day[i] not in seen:
        first[i] = True
        seen.add(day[i])
base_ls = first & brk_up
base_ss = first & brk_dn & ~base_ls
base_ls[:WARMUP] = False; base_ss[:WARMUP] = False

MED_ATR = float(np.median(atr_pip[WARMUP:]))
TRAIL = float(MED_ATR * 1.0)
SLM = 2.1
slp = np.clip(atr_pip * SLM, 8, 5000)

def pf_of(pnl):
    w = pnl[pnl > 0].sum(); lo_ = -pnl[pnl < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf

print(f'explore bars={n:,}  src={d["src"]}  MED_ATR={MED_ATR:.1f}pip trail={TRAIL:.1f}pip', flush=True)
print(f'base events: L={int(base_ls.sum())} S={int(base_ss.sum())}', flush=True)

for filt_name in ('all', 'trend-align'):
    if filt_name == 'all':
        ls, ss = base_ls, base_ss
    else:
        ls = base_ls & above          # long فقط بالای EMA200
        ss = base_ss & ~above         # short فقط زیر EMA200 — آینه‌ای
    print(f'\n===== filter={filt_name}  (L={int(ls.sum())} S={int(ss.sum())}) =====', flush=True)
    for rr in (3.4, 6.0):
        tpp = slp * rr
        for hold in (21, 34, 55):
            tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                     asset='XAUUSD', max_hold=hold,
                                     allow_overlap=False, trail_pip=TRAIL)
            if len(tdf) < 60:
                continue
            pnl = tdf['pnl_pip'].values
            eb = tdf['entry_bar'].values
            wr = float((pnl > 0).mean() * 100)
            med_sl = float(np.median(tdf['sl_pip']))
            be_cost = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
            pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
            print(f'  rr={rr} hold={hold}: n={len(tdf):5,} WR={wr:5.2f}% '
                  f'lift={wr-be_cost:+6.2f}pp exp={float(pnl.mean()):+7.2f}pip '
                  f'PF={pf:.3f} [E1={pf1:.3f} E2={pf2:.3f}]', flush=True)

print('\n[S832 explore-4 complete]', flush=True)
