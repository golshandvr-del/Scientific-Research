# -*- coding: utf-8 -*-
"""
S790 — داوریِ نهایی: Deep Liquidity Sweep Fade — XAUUSD-M15 (مسیر C)
================================================================================
طبق strategies/S790_PREREG.md (commit 115fe815 — پیش از هر نگاه به نیمهٔ دوم):
  رخداد: sweep عمیقِ سطحِ روزِ قبل (depth>=1.0·ATR89, reclaim>=0.236·ATR89)،
  نخستینِ روز/سمت، ورود openِ بعدی، SL=TP=2.618·ATR89، mh=192، overlap ممنوع.
این اسکریپت:
  ۱) سیگنال را روی کلِ ۱۵.۶ سال می‌سازد و شبیه‌سازی می‌کند (هزینهٔ کامل)
  ۲) null اندازه‌گیری‌شده: بی‌قید (۴۰ نمونهٔ تصادفیِ بزرگ) + جایگشتِ زمانی K=500
  ۳) **یک** فراخوانِ compute_rqs2 با split_bar=n//2 (همان مرزِ اکتشاف)
چک‌پوینتِ JSON هر ۵۰ جایگشت در strategies/s790_final_ckpt.json.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from tools import s434_fast_data as fd
from engine import scalp_engine as se
from engine import rqs2

CKPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 's790_final_ckpt.json')
SEED = 790
N_PERM = 500
N_TRIALS = 150   # اندازهٔ صادقانهٔ فضای جست‌وجوی اکتشافِ S790 (همهٔ اسکن‌ها)

d = fd.load_fast('XAUUSD', 'M15')
df = fd.as_dataframe(d)
print('src =', d['src'], flush=True)
t = df['time'].values.astype(np.int64)
o = df['open'].values; h = df['high'].values
l = df['low'].values; c = df['close'].values
n = len(df)
split = n // 2
print(f'FULL DATA: {np.datetime64(int(t[0]),"s")} → {np.datetime64(int(t[-1]),"s")} '
      f'({n} bars, split_bar={split})', flush=True)

# ---- ساختِ ویژگی‌های منجمد ----
day = t // 86400
day_id = np.cumsum(np.r_[True, np.diff(day) != 0]) - 1
n_days = day_id[-1] + 1
d_high = np.full(n_days, -np.inf); d_low = np.full(n_days, np.inf)
np.maximum.at(d_high, day_id, h)
np.minimum.at(d_low, day_id, l)
prev_high = np.full(n, np.nan); prev_low = np.full(n, np.nan)
m = day_id >= 1
prev_high[m] = d_high[day_id[m] - 1]
prev_low[m] = d_low[day_id[m] - 1]

tr_ = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]),
                                   np.abs(l - np.r_[c[0], c[:-1]])))
atr = np.empty(n); a = tr_[0]; kk = 2.0 / 90.0
for i in range(n):
    a = a + kk * (tr_[i] - a); atr[i] = a
atr = np.r_[np.nan, atr[:-1]]

DTH, RTH, K_GEOM, MH = 1.0, 0.236, 2.618, 192
sw_hi = (h > prev_high) & (c < prev_high) & ((h - prev_high)/atr >= DTH) & ((prev_high - c)/atr >= RTH)
sw_lo = (l < prev_low) & (c > prev_low) & ((prev_low - l)/atr >= DTH) & ((c - prev_low)/atr >= RTH)

def first_per_day(sig):
    out = np.zeros(n, dtype=bool)
    seen = np.zeros(n_days, dtype=bool)
    for i in np.where(sig)[0]:
        if not seen[day_id[i]]:
            seen[day_id[i]] = True; out[i] = True
    return out

long_sig = first_per_day(sw_lo)
short_sig = first_per_day(sw_hi)
pip = 0.10
sl_arr = np.where(np.isnan(atr), 0.0, K_GEOM * atr / pip)
print(f'events: long={long_sig.sum()} short={short_sig.sum()}', flush=True)

trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_arr, tp_pip=sl_arr,
                            asset='XAUUSD', max_hold=MH, allow_overlap=False)
p = trades['pnl_pip'].values
print(f'TRADES n={len(trades)}  WR={np.mean(p>0)*100:.2f}%  net={np.sum(p):+.0f}pip', flush=True)

valid = np.where(~np.isnan(atr) & (day_id >= 1))[0]
valid = valid[valid < n - MH - 2]
rng = np.random.default_rng(SEED)

def wr_of(ls, ss):
    tr2 = se.simulate_trades(df, ls, ss, sl_pip=sl_arr, tp_pip=sl_arr,
                             asset='XAUUSD', max_hold=MH, allow_overlap=False)
    if len(tr2) == 0:
        return np.nan, np.nan
    isl = tr2['direction'].values == 'long'
    wl = float(np.mean(tr2.loc[isl, 'pnl_pip'] > 0)) if isl.sum() else np.nan
    ws = float(np.mean(tr2.loc[~isl, 'pnl_pip'] > 0)) if (~isl).sum() else np.nan
    return wl, ws

nL, nS = int(long_sig.sum()), int(short_sig.sum())

# ---- ۱) مبنای بی‌قید: همان هندسه در کندل‌های تصادفی (۴۰ تکرار برای پایداری) ----
uw_l, uw_s = [], []
for _ in range(40):
    pick = rng.choice(valid, size=nL + nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): uw_l.append(wl)
    if not np.isnan(ws): uw_s.append(ws)
uncond_l = float(np.mean(uw_l)) * 100
uncond_s = float(np.mean(uw_s)) * 100
print(f'uncond null: long={uncond_l:.2f}%  short={uncond_s:.2f}%', flush=True)

# ---- ۲) جایگشتِ زمانی K=500 (تعدادِ سیگنال و ترکیبِ جهت حفظ می‌شود) ----
perm_l, perm_s = [], []
t0 = time.time()
for kperm in range(N_PERM):
    pick = rng.choice(valid, size=nL + nS, replace=False)
    ls = np.zeros(n, bool); ss = np.zeros(n, bool)
    ls[pick[:nL]] = True; ss[pick[nL:]] = True
    wl, ws = wr_of(ls, ss)
    if not np.isnan(wl): perm_l.append(wl * 100)
    if not np.isnan(ws): perm_s.append(ws * 100)
    if (kperm + 1) % 50 == 0:
        ck = {'perm_done': kperm + 1, 'elapsed_s': round(time.time() - t0, 1),
              'perm_l_mean': float(np.mean(perm_l)), 'perm_s_mean': float(np.mean(perm_s))}
        json.dump(ck, open(CKPT, 'w'))
        print(f'  perm {kperm+1}/{N_PERM}  Lmean={ck["perm_l_mean"]:.2f}  '
              f'Smean={ck["perm_s_mean"]:.2f}  ({ck["elapsed_s"]}s)', flush=True)

null = {
    'long': {'uncond_wr': uncond_l, 'perm_mean': float(np.mean(perm_l)),
             'perm_sd': float(np.std(perm_l, ddof=1)), 'perm_max': float(np.max(perm_l)),
             'perm_k': len(perm_l)},
    'short': {'uncond_wr': uncond_s, 'perm_mean': float(np.mean(perm_s)),
              'perm_sd': float(np.std(perm_s, ddof=1)), 'perm_max': float(np.max(perm_s)),
              'perm_k': len(perm_s)},
}
print('NULL =', json.dumps(null, indent=1), flush=True)

# ---- ۳) داوریِ یگانه ----
res = rqs2.compute_rqs2(
    trades, 'XAUUSD',
    sl_pip=float(np.median(trades['sl_pip'].values)),
    tp_pip=float(np.median(trades['sl_pip'].values)),   # متقارن TP=SL
    bar_time=t, null=null, n_trials=N_TRIALS,
    split_bar=split, close=c,
)
out = {'null': null, 'verdict': res['verdict'], 'rqs2_score': res['rqs2_score'],
       'gates': {k: (bool(v) if v is not None else None) for k, v in res['gates'].items()},
       'metrics': {k: (float(v) if isinstance(v, (int, float, np.floating)) else v)
                   for k, v in res['metrics'].items()},
       'notes': res['notes'], 'n_trades': int(len(trades)),
       'src': d['src'], 'split_bar': int(split)}
json.dump(out, open(os.path.join(os.path.dirname(CKPT), 's790_final_result.json'), 'w'),
          indent=1, default=str)
print('\n================= VERDICT =================', flush=True)
print('verdict:', res['verdict'], ' score:', res['rqs2_score'], flush=True)
for g, v in res['gates'].items():
    print(f'  {g}: {v}', flush=True)
for nt in res['notes']:
    print('  note:', nt, flush=True)
