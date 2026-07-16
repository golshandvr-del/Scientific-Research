"""
S64b — تستِ حساسیتِ پارامترهای مقیاس‌بندیِ حجمِ S64 (اطمینان از عدمِ overfit)
================================================================================
اگر بهبودِ +۸۳٪ فقط به یک ترکیبِ خاصِ (W_SLOPE, W_MAX) وابسته باشد، یعنی overfit.
اینجا شبکه‌ای از پارامترها را اسکن می‌کنیم و می‌بینیم آیا بهبود روی همهٔ آن‌ها
پایدار است یا نه. اگر اکثریتِ نقاط سودِ خالصِ بالاتر از baselineِ S63 (۲۹۴۹$)
بدهند، بهبود ساختاری است نه اتفاقی.

خروجی هر معامله با وزنِ سطلش ضرب می‌شود (همان منطقِ S64). forward-safe.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
ER_TREND_THR = 0.30
P_HI = 0.66; P_MIN = 0.58
STEP = 6000; LOOKBACK = 24000
EXP_MIN = 0.10; MIN_N = 15
BASELINE_S63 = 2949.0

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')
z = np.load(CACHE, allow_pickle=True)
pL, pS = z['pL'], z['pS']
up_reg, down_reg = z['up_reg'], z['down_reg']
er = z['er']; atrv = z['atrv']

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)
slL = 1.5 * atrv; tpL = 1.0 * atrv
slS = 1.7 * atrv; tpS = 1.4 * atrv
baseL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
baseS = down_reg & ~np.isnan(atrv) & (pS >= P_MIN)

def build_labels(direction, base):
    p = pL if direction == 'long' else pS
    ef = np.where(trendy, 'trend', 'chop')
    pw = np.where(p >= P_HI, 'hi', 'lo')
    lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
    lab[~base] = ''
    return lab

labL = build_labels('long', baseL); labS = build_labels('short', baseS)
BUCKETS = ['trend_hi', 'trend_lo', 'chop_hi', 'chop_lo']

def recent_stats(direction, bucket, lo, hi, sl_s, tp_s, base_lab):
    m = np.zeros(n, dtype=bool); seg = (base_lab == bucket); m[lo:hi] = seg[lo:hi]
    if m.sum() < 1: return None, 0
    st, _ = run_backtest(df, m, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st['expectancy'], st['n_trades']

# پیش‌محاسبهٔ (exp اخیر) هر سطل در هر بلوک — یک‌بار، مستقل از پارامترهای وزن
print("پیش‌محاسبهٔ اکسپکتنسیِ اخیرِ سطل‌ها ...", flush=True)
blocks = list(range(LOOKBACK, n, STEP))
recent = {'long': {}, 'short': {}}
for direction, base_lab, sl_s, tp_s in [('long', labL, slL, tpL), ('short', labS, slS, tpS)]:
    for start in blocks:
        lb_lo = max(0, start - LOOKBACK)
        for bk in BUCKETS:
            exp, ntr = recent_stats(direction, bk, lb_lo, start, sl_s, tp_s, base_lab)
            recent[direction][(start, bk)] = (exp, ntr)

eval_mask = np.zeros(n, dtype=bool); eval_mask[LOOKBACK:] = True

def weighted_total(W_BASE, W_SLOPE, W_MIN, W_MAX):
    total = 0.0
    for direction, base_lab, sl_s, tp_s in [('long', labL, slL, tpL), ('short', labS, slS, tpS)]:
        entries = np.zeros(n, dtype=bool); weights = np.zeros(n)
        for start in blocks:
            end = min(start + STEP, n)
            for bk in BUCKETS:
                exp, ntr = recent[direction][(start, bk)]
                if exp is not None and ntr >= MIN_N and exp >= EXP_MIN:
                    w = float(np.clip(W_BASE + W_SLOPE * (exp - EXP_MIN), W_MIN, W_MAX))
                    seg = (base_lab == bk)
                    sel = np.zeros(n, dtype=bool); sel[start:end] = seg[start:end]
                    entries |= sel; weights[sel] = w
        s = entries & eval_mask
        st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                              sl_series=sl_s, tp_series=tp_s)
        if len(tr):
            w = weights[tr['signal_bar'].values]; w[w == 0] = 1.0
            total += (tr['pnl'].values * w).sum()
    return total

print("\n=== شبکهٔ حساسیتِ (W_SLOPE × W_MAX) — همه با W_BASE=1.0, W_MIN=0.5 ===", flush=True)
print(f"baseline S63 (حجمِ ثابت) = {BASELINE_S63:.0f}$\n", flush=True)
print(f"{'W_SLOPE\\W_MAX':>14s}", end='', flush=True)
maxes = [1.5, 2.0, 2.5, 3.0]
for mx in maxes: print(f"{mx:>10.1f}", end='', flush=True)
print(flush=True)

n_better = 0; n_total = 0; results = []
for sl in [0.6, 0.9, 1.2, 1.5, 2.0]:
    print(f"{sl:>14.1f}", end='', flush=True)
    for mx in maxes:
        t = weighted_total(1.0, sl, 0.5, mx)
        results.append(t); n_total += 1
        if t > BASELINE_S63: n_better += 1
        mark = '+' if t > BASELINE_S63 else ' '
        print(f"{t:>9.0f}{mark}", end='', flush=True)
    print(flush=True)

print(f"\nخلاصه: {n_better}/{n_total} ترکیب از baselineِ S63 بهتر بودند "
      f"(میانگین={np.mean(results):.0f}$, کمینه={np.min(results):.0f}$, بیشینه={np.max(results):.0f}$)", flush=True)
if n_better >= 0.8 * n_total and np.min(results) > BASELINE_S63 * 0.95:
    print("✅ بهبود روی کلِ شبکهٔ پارامتر پایدار است → ساختاری، نه overfit.", flush=True)
elif n_better >= 0.5 * n_total:
    print("⚠️ بهبود روی اکثریتِ نقاط هست ولی به پارامتر حساس است — با احتیاط.", flush=True)
else:
    print("❌ بهبود ناپایدار (overfit به پارامترِ خاص).", flush=True)
print("\nتمام.", flush=True)
