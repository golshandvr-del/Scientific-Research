# -*- coding: utf-8 -*-
"""
S640 — اکتشاف M1 (مسیرِ C، فقط نیمهٔ اول) — نسخهٔ کم‌حافظه (chunked)
سندباکس ~1GB حافظه دارد؛ M1 نیمهٔ اول = 2.5M کندل. موتورِ برداری روی کلِ آرایه
ماتریس‌های بزرگ می‌سازد → فریز. راه‌حل: قطعه‌های 300k با warmup مشترک 2000 کندل؛
معاملات محلی‌اند پس جمعِ آمارِ قطعات = آمارِ کل (تا مرزِ ناچیزِ لبه‌ها).
خروجی همان قالبِ results/_s640_explore/M1.json
"""
import json, os, sys, gc, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import indicator_bank as ib
from engine import scalp_engine as se
from tools import s434_fast_data as fd

OUT = 'results/_s640_explore/M1.json'
PIP = 0.1
CHUNK = 300_000
WARM = 2_000
K_GRID = [1.5, 3.0, 4.5]
SLOPE_GRID = [1, 3]
MAX_HOLD = 64

t0 = time.time()
d = fd.load_fast('XAUUSD', 'M1')
df_all = fd.as_dataframe(d)
half = len(df_all) // 2
df = df_all.iloc[:half].reset_index(drop=True)
del df_all, d; gc.collect()

# KAMA و سیگنال‌ها یک‌بار روی کل نیمهٔ اول (فقط بردارهای 1بعدی — سبک)
kama = ib.compute('kama', df).values.astype(np.float64)
close = df['close'].values
prev_c = np.roll(close, 1); prev_c[0] = close[0]
prev_k = np.roll(kama, 1);  prev_k[0] = kama[0]

# ATR پایه (میانهٔ نیمهٔ اول)
h, l, c = df['high'].values, df['low'].values, df['close'].values
pc = np.roll(c, 1); pc[0] = c[0]
tr_ = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
atr = pd.Series(tr_).rolling(100).mean()
sl_base = float(np.nanmedian(atr.values)) / PIP
del h, l, pc, tr_, atr; gc.collect()

sigs = {}
for slope_len in SLOPE_GRID:
    k_sh = np.roll(kama, slope_len); k_sh[:slope_len] = kama[:slope_len]
    up = (prev_c <= prev_k) & (close > kama) & (kama > k_sh)
    dn = (prev_c >= prev_k) & (close < kama) & (kama < k_sh)
    sigs[slope_len] = (up, dn)
del prev_c, prev_k, k_sh; gc.collect()

def agg_stats(df, long_sig, short_sig, sl, tp, per_side=False):
    """آمارِ تجمیعی روی قطعات؛ فقط شمارش‌ها نگه داشته می‌شوند."""
    n_tot = 0; n_win = 0; pnl_pos = 0.0; pnl_neg = 0.0
    nL = 0; wL = 0; nS = 0; wS = 0
    i = 0
    while i < len(df):
        a = max(0, i - WARM); b = min(len(df), i + CHUNK)
        sub = df.iloc[a:b].reset_index(drop=True)
        ls = long_sig[a:b].copy(); ss = short_sig[a:b].copy()
        # سیگنال‌های ناحیهٔ warmup را خاموش کن تا دوباره شمرده نشوند
        cut = i - a
        ls[:cut] = False; ss[:cut] = False
        t = se.simulate_trades(sub, ls, ss, sl_pip=sl, tp_pip=tp,
                               asset='XAUUSD', max_hold=MAX_HOLD, allow_overlap=False)
        if t is not None and len(t):
            p = t['pnl_pip'].values
            n_tot += len(p); n_win += int((p > 0).sum())
            pnl_pos += float(p[p > 0].sum()); pnl_neg += float(-p[p <= 0].sum())
            if per_side and 'direction' in t:
                dirv = t['direction'].values
                mL = dirv == 1 if dirv.dtype != object else dirv == 'long'
                nL += int(mL.sum()); wL += int(((p > 0) & mL).sum())
                nS += int((~mL).sum()); wS += int(((p > 0) & (~mL)).sum())
        del sub, t; gc.collect()
        i += CHUNK
    wr = 100.0 * n_win / n_tot if n_tot else 0.0
    pf = pnl_pos / max(1e-9, pnl_neg)
    wrL = 100.0 * wL / nL if nL else 0.0
    wrS = 100.0 * wS / nS if nS else 0.0
    return n_tot, wr, pf, nL, wrL, nS, wrS

cells = []
zeros = np.zeros(len(df), dtype=bool)
ones = np.ones(len(df), dtype=bool)
blind_cache = {}
for slope_len in SLOPE_GRID:
    up, dn = sigs[slope_len]
    for k in K_GRID:
        sl = max(1.0, round(k * sl_base, 1)); tp = sl
        n, wr, pf, nL, wrL, nS, wrS = agg_stats(df, up, dn, sl, tp, per_side=True)
        if k not in blind_cache:
            nb, wrb, _, _, _, _, _ = agg_stats(df, ones, zeros, sl, tp)
            blind_cache[k] = (nb, wrb)
        nb, wrb = blind_cache[k]
        lift = wr - wrb
        z = lift / (100.0 * np.sqrt(max(wrb, 1)/100*(1-max(wrb, 1)/100) / max(n, 1))) if n else 0.0
        cells.append({'slope_len': slope_len, 'k': k, 'sl_pip': sl, 'tp_pip': tp,
                      'n': n, 'wr': round(wr, 2), 'pf': round(pf, 3),
                      'wr_blind': round(wrb, 2), 'n_blind': nb,
                      'lift_pp': round(lift, 2), 'z_naive': round(z, 2),
                      'lift_sqrt_n': round(lift*np.sqrt(max(n, 0)), 1),
                      'nL': nL, 'wrL': round(wrL, 2), 'nS': nS, 'wrS': round(wrS, 2),
                      'cost_to_sl_pct': round(100.0*3.3/sl, 1)})
        print(f"[M1] slope{slope_len} k{k}: n={n} wr={wr:.2f} blind={wrb:.2f} lift={lift:+.2f}", flush=True)

res = {'tf': 'M1', 'n_bars_first_half': int(half), 'sl_base_atr_pip': round(sl_base, 1),
       'note': 'chunked low-memory run', 'elapsed_s': round(time.time()-t0, 1), 'cells': cells}
with open(OUT, 'w') as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print(f"[M1] DONE in {res['elapsed_s']}s", flush=True)
