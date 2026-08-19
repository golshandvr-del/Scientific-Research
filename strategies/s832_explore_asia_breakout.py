# -*- coding: utf-8 -*-
"""
S832 — کاوشِ ۲: شکست متقارن رنج آسیایی — XAUUSD-H1 (فقط ۶۰٪ اکتشاف)
======================================================================
طراحی با دو الزام از شکست‌های S830/S831:
  (۱) تقارن کامل: long بر شکست سقف، short بر شکست کف — منطق آینه‌ای
  (۲) جهت درون‌زاد: خودِ شکست جهت را تعیین می‌کند، نه فرضِ ما

تعریف (به وقت بروکر، از سرشماری کاوش ۱):
  رنج آسیا: high/low ساعات 0..6 هر روز (۷ کندل H1)
  پنجره‌ی معامله: ساعات 7..16 همان روز
  رخداد: اولین close بیرون رنج در پنجره ⇒ ورود کندل بعد در جهت شکست
  حداکثر یک معامله در روز (اولین شکست).
شبکه: عرض‌سنجِ رنج (فیلتر): هیچ / رنج < q40 روزهای اخیر (فشرده)
      slm ∈ {1.0, 1.4, 2.1} (SL=slm×ATR34) × rr ∈ {1.3, 2.0, 3.4} × hold ∈ {8, 13, 21}
گزارش: n, WR, lift(be_cost), exp, PF کل + PF در دو نیمه‌ی E1/E2 (پایداری رژیمی).
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
# رنج آسیای هر روز (ساعات 0..6) — علّی: در ساعت >=7 کامل شده است
asia_hi = np.full(n, np.nan); asia_lo = np.full(n, np.nan)
asia_rng = np.full(n, np.nan)
uniq_days = np.unique(day)
day_rng = {}
for dd in uniq_days:
    m = (day == dd) & (hour <= 6)
    if m.sum() < 5:      # روز ناقص (تعطیلی) — رد
        continue
    hi = h[m].max(); lo = l[m].min()
    md = (day == dd) & (hour >= 7)
    asia_hi[md] = hi; asia_lo[md] = lo
    day_rng[dd] = hi - lo
    asia_rng[md] = hi - lo

# فیلتر فشردگی: رنج امروز < چندک q از ۲۱ روز قبل (علّی)
rng_hist = np.array([day_rng.get(dd, np.nan) for dd in uniq_days])
day_index = {dd: i for i, dd in enumerate(uniq_days)}
narrow = np.zeros(n, bool)
for dd in uniq_days:
    i = day_index[dd]
    if i < 22 or dd not in day_rng:
        continue
    hist = rng_hist[i-21:i]
    hist = hist[np.isfinite(hist)]
    if len(hist) < 15:
        continue
    if day_rng[dd] < np.quantile(hist, 0.40):
        narrow[(day == dd)] = True

# رخداد شکست: اولین close بیرون رنج در ساعات 7..16
in_win = (hour >= 7) & (hour <= 16)
brk_up = in_win & np.isfinite(asia_hi) & (c > asia_hi)
brk_dn = in_win & np.isfinite(asia_lo) & (c < asia_lo)
first = np.zeros(n, bool)
seen = set()
for i in range(n):
    if (brk_up[i] or brk_dn[i]) and day[i] not in seen:
        first[i] = True
        seen.add(day[i])
long_sig = first & brk_up
short_sig = first & brk_dn & ~long_sig
long_sig[:WARMUP] = False; short_sig[:WARMUP] = False

print(f'explore bars={n:,}  src={d["src"]}', flush=True)
print(f'events: long={int(long_sig.sum())} short={int(short_sig.sum())} '
      f'(narrow-filtered: long={int((long_sig&narrow).sum())} short={int((short_sig&narrow).sum())})', flush=True)

def pf_of(pnl):
    w = pnl[pnl > 0].sum(); lo_ = -pnl[pnl < 0].sum()
    return w / lo_ if lo_ > 0 else np.inf

for filt_name, fmask in (('all', np.ones(n, bool)), ('narrow', narrow)):
    ls = long_sig & fmask; ss = short_sig & fmask
    print(f'\n===== filter={filt_name}  (L={int(ls.sum())} S={int(ss.sum())}) =====', flush=True)
    for slm in (1.0, 1.4, 2.1):
        slp = np.clip(atr_pip * slm, 8, 5000)
        for rr in (1.3, 2.0, 3.4):
            tpp = slp * rr
            for hold in (8, 13, 21):
                tdf = se.simulate_trades(df, ls, ss, sl_pip=slp, tp_pip=tpp,
                                         asset='XAUUSD', max_hold=hold,
                                         allow_overlap=False)
                if len(tdf) < 60:
                    continue
                pnl = tdf['pnl_pip'].values
                eb = tdf['entry_bar'].values
                wr = float((pnl > 0).mean() * 100)
                exp = float(pnl.mean())
                med_sl = float(np.median(tdf['sl_pip']))
                be = (med_sl + 3.3) / (med_sl + med_sl * rr) * 100
                pf = pf_of(pnl); pf1 = pf_of(pnl[eb < HALF]); pf2 = pf_of(pnl[eb >= HALF])
                print(f'  slm={slm} rr={rr} hold={hold}: n={len(tdf):5,} WR={wr:5.2f}% '
                      f'lift={wr-be:+6.2f}pp exp={exp:+7.2f}pip PF={pf:.3f} '
                      f'[E1={pf1:.3f} E2={pf2:.3f}]', flush=True)

print('\n[S832 explore-2 complete]', flush=True)
