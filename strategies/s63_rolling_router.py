"""
S63 — Rolling Regime-Router (فرار از دامِ L35) — معیار: سودِ خالص
================================================================================
درسِ L35: Router نباید از یک دورهٔ مردهٔ گذشته «محلِ درست» را یاد بگیرد.
راه‌حل: Router رو به جلو (walk-forward) که در هر گام از پنجرهٔ اخیرِ متحرک یاد
می‌گیرد کدام سطلِ رژیم اخیراً سودده بوده، و همان را برای بلوکِ بعدی به کار می‌برد.

منطق (بدونِ نشتِ آینده):
  - داده به بلوک‌های متوالی (هرکدام ~STEP کندل) تقسیم می‌شود.
  - برای معامله در بلوکِ b، فقط از داده‌ی بلوک‌های < b (پنجرهٔ اخیر LOOKBACK) برای
    تصمیمِ «کدام سطل روشن باشد» استفاده می‌شود.
  - یک سطل برای بلوکِ b روشن است اگر روی پنجرهٔ اخیر اکسپکتنسیِ مثبت (≥ثر) داشته باشد.
  - probaها از کشِ walk-forwardِ S61 (که خودش بدونِ look-ahead است).

مقایسه: Rolling-Router در برابرِ baseline «هر دو جریان بدونِ گیت» (برندهٔ S62).
هدف: سودِ خالصِ بیشتر یا هم‌سطح ولی با drawdown/کیفیتِ بهتر.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
ER_TREND_THR = 0.30
P_HI = 0.66; P_MIN = 0.58
STEP = 6000                 # اندازهٔ هر بلوکِ ارزیابی (~۲ ماه کندلِ M15)
LOOKBACK = 24000            # پنجرهٔ یادگیریِ اخیر (~۸ ماه)
EXP_MIN = 0.10              # حداقلِ اکسپکتنسیِ اخیر برای روشن‌کردنِ سطل ($)
MIN_N = 15                  # حداقلِ معاملهٔ اخیر برای اعتماد به یک سطل

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')

print("=== S63: Rolling Regime-Router (معیار: سودِ خالص) ===\n", flush=True)

z = np.load(CACHE, allow_pickle=True)
pL, pS = z['pL'], z['pS']
up_reg, down_reg = z['up_reg'], z['down_reg']
er = z['er']; atrv = z['atrv']

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)

slL = 1.5 * atrv; tpL = 1.0 * atrv
slS = 1.7 * atrv; tpS = 1.4 * atrv

# سطلِ هر کندل (رشته) برای هر جریان
def bucket_label(i, direction):
    ef = 'trend' if trendy[i] else 'chop'
    p = pL[i] if direction == 'long' else pS[i]
    pw = 'hi' if p >= P_HI else 'lo'
    return f'{ef}_{pw}'

# کاندیدهای پایه هر جریان
baseL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
baseS = down_reg & ~np.isnan(atrv) & (pS >= P_MIN)

# برای سرعت: برچسبِ سطل را برداری بساز
def build_labels(direction, base):
    p = pL if direction == 'long' else pS
    ef = np.where(trendy, 'trend', 'chop')
    pw = np.where(p >= P_HI, 'hi', 'lo')
    lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
    lab[~base] = ''      # کاندید نیست
    return lab

labL = build_labels('long', baseL)
labS = build_labels('short', baseS)

# ---------------------------------------------------------------------------
# ساختِ ماسکِ ورودِ Rolling: برای هر بلوک، سطل‌های روشن را از پنجرهٔ اخیر یاد بگیر
# ---------------------------------------------------------------------------
def recent_expectancy(direction, bucket, lo, hi, sl_s, tp_s, base_lab):
    """اکسپکتنسیِ سطلِ bucket روی بازهٔ [lo,hi) — با بک‌تستِ همان بازه."""
    m = np.zeros(n, dtype=bool)
    seg = (base_lab == bucket)
    m[lo:hi] = seg[lo:hi]
    if m.sum() < 1:
        return None, 0
    st, _ = run_backtest(df, m, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st['expectancy'], st['n_trades']

BUCKETS = ['trend_hi', 'trend_lo', 'chop_hi', 'chop_lo']

def rolling_entries(direction, base_lab, sl_s, tp_s):
    entries = np.zeros(n, dtype=bool)
    on_log = []
    b0 = LOOKBACK      # اولین بلوکی که پنجرهٔ کاملِ گذشته دارد
    for start in range(b0, n, STEP):
        end = min(start + STEP, n)
        lb_lo = max(0, start - LOOKBACK)
        # کدام سطل‌ها روی پنجرهٔ اخیر [lb_lo,start) سودده بودند؟
        on = []
        for bk in BUCKETS:
            exp, ntr = recent_expectancy(direction, bk, lb_lo, start, sl_s, tp_s, base_lab)
            if exp is not None and ntr >= MIN_N and exp >= EXP_MIN:
                on.append(bk)
        # اعمال روی بلوکِ [start,end)
        for bk in on:
            seg = (base_lab == bk)
            entries[start:end] |= seg[start:end]
        on_log.append((start, on))
    return entries, on_log

print("ساختِ ورودی‌های Rolling برای Bull ...", flush=True)
entL, logL = rolling_entries('long', labL, slL, tpL)
print("ساختِ ورودی‌های Rolling برای Bear ...", flush=True)
entS, logS = rolling_entries('short', labS, slS, tpS)

# محدودهٔ ارزیابی = از LOOKBACK به بعد (که Router فعال است)
eval_mask = np.zeros(n, dtype=bool); eval_mask[LOOKBACK:] = True

def report(label, sigL, sigS):
    stL = run_backtest(df, (sigL & eval_mask) if sigL is not None else np.zeros(n, bool),
                       None, None, 'long', spread=SPREAD, max_hold=HZ, sl_series=slL, tp_series=tpL)[0] if sigL is not None else None
    stS = run_backtest(df, (sigS & eval_mask) if sigS is not None else np.zeros(n, bool),
                       None, None, 'short', spread=SPREAD, max_hold=HZ, sl_series=slS, tp_series=tpS)[0] if sigS is not None else None
    ntr = (stL['n_trades'] if stL else 0) + (stS['n_trades'] if stS else 0)
    pnl = (stL['total_pnl'] if stL else 0) + (stS['total_pnl'] if stS else 0)
    wins = ((stL['win_rate']*stL['n_trades']/100) if stL else 0) + ((stS['win_rate']*stS['n_trades']/100) if stS else 0)
    wr = (wins/ntr*100) if ntr else 0
    exp = (pnl/ntr) if ntr else 0
    print(f"{label:34s} n={ntr:5d}  WR={wr:5.1f}%  سودِخالص={pnl:9.1f}$  اکسپکتنسی={exp:.3f}$", flush=True)
    return pnl

print("\n--- مقایسهٔ سودِ خالص (بازهٔ فعال‌بودنِ Router) ---", flush=True)
baseAllL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
baseAllS = down_reg & ~np.isnan(atrv) & (pS >= P_MIN)
p_both = report('baseline: هر دو بدونِ گیت', baseAllL, baseAllS)
p_router = report('★ Rolling-Router', entL, entS)

print(f"\nبهبودِ Router نسبت به baseline: {p_router - p_both:+.1f}$ "
      f"({(p_router/p_both-1)*100 if p_both>0 else 0:+.1f}%)", flush=True)
if p_router > p_both:
    print("✅ Rolling-Router سودِ خالص را بالا برد → از دامِ L35 فرار کرد.", flush=True)
else:
    print("△ Rolling-Router سودِ خالصِ کمتر ولی احتمالاً باکیفیت‌تر؛ به اکسپکتنسی نگاه کن.", flush=True)

# نمونه‌ای از تصمیم‌های Router در طول زمان
print("\n--- نمونهٔ سطل‌های روشنِ Bull در بلوک‌ها (هر ۵ بلوک) ---", flush=True)
for k, (start, on) in enumerate(logL):
    if k % 5 == 0:
        print(f"  کندلِ {start}: {on if on else '(هیچ — خنثی)'}", flush=True)

print("\nتمام.", flush=True)
