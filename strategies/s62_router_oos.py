"""
S62 — ساختِ Router با تفکیکِ IS/OOS (معیار: سودِ خالص) — فازِ ۲
================================================================================
از کشِ S61 (_s61_cache.npz) استفاده می‌کند (بدونِ آموزشِ مجدد → سریع و کم‌حافظه).

منطق (بدونِ نشتِ آینده):
  ۱) هر کندل به یک «سطلِ رژیم» نگاشت می‌شود:
       جهت   : bull (up_reg) | bear (down_reg)
       کارایی: trend (ER≥thr) | chop
       قدرتِ proba: hi (p≥p_hi) | lo  → سه محور، ۲×۲×۲ = ۸ سطل (۴ برای هر جهت)
  ۲) IS = نیمهٔ اولِ داده، OOS = نیمهٔ دوم.
  ۳) روی IS: سودِ خالصِ سرانه (اکسپکتنسی) و سودِ خالصِ کلِ هر سطل را می‌سنجیم.
     Router فقط سطل‌هایی را «روشن» می‌کند که روی IS اکسپکتنسیِ مثبت (> حداقلِ آستانه) دارند.
  ۴) روی OOS: با همان نگاشتِ یادگرفته‌شده معامله می‌کنیم و سودِ خالص را می‌سنجیم.
  ۵) مقایسه با baselineها: (الف) همیشه Bull، (ب) همیشه Bear، (ج) هر دو بدونِ گیتِ رژیم.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
ER_TREND_THR = 0.30
P_HI = 0.66                      # آستانهٔ «قدرتِ بالا»ی proba
P_MIN = 0.58                     # حداقلِ probaِ لازم برای هر ورود
IS_EXP_MIN = 0.05                # حداقلِ اکسپکتنسیِ IS برای روشن‌کردنِ یک سطل ($)

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')

print("=== S62: Router با تفکیکِ IS/OOS (معیار: سودِ خالص) ===\n", flush=True)

z = np.load(CACHE, allow_pickle=True)
pL, pS = z['pL'], z['pS']
up_reg, down_reg = z['up_reg'], z['down_reg']
er = z['er']; atrv = z['atrv']

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
trendy = er >= ER_TREND_THR
half = n // 2
is_mask = np.zeros(n, dtype=bool); is_mask[:half] = True
oos_mask = ~is_mask

slL = 1.5 * atrv; tpL = 1.0 * atrv
slS = 1.7 * atrv; tpS = 1.4 * atrv

# ---------------------------------------------------------------------------
# تعریفِ سطل‌ها: هر جریان (bull/bear) × کارایی (trend/chop) × قدرتِ proba (hi/lo)
# ---------------------------------------------------------------------------
def stream_buckets(direction):
    if direction == 'long':
        base = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
        p = pL
    else:
        base = down_reg & ~np.isnan(atrv) & (pS >= P_MIN)
        p = pS
    tmask = np.nan_to_num(trendy, nan=False).astype(bool)
    out = {}
    for ef, efm in [('trend', tmask), ('chop', ~tmask)]:
        for pw, pwm in [('hi', p >= P_HI), ('lo', (p < P_HI))]:
            out[f'{ef}_{pw}'] = base & efm & pwm
    return out

bucketsL = stream_buckets('long')
bucketsS = stream_buckets('short')


def bt(sig, direction, sl_s, tp_s, sub_mask):
    s = sig & sub_mask
    st, _ = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st


# ---------------------------------------------------------------------------
# فازِ یادگیری روی IS: کدام سطل‌ها اکسپکتنسیِ مثبت دارند؟
# ---------------------------------------------------------------------------
print("--- IS (نیمهٔ اول): اکسپکتنسیِ هر سطل ---", flush=True)
print(f"{'جریان':6s} {'سطل':12s} {'n':>5s} {'WR%':>6s} {'سودِخالص$':>11s} {'اکسپکتنسی$':>11s} {'روشن؟':>6s}", flush=True)
router_on = {'long': [], 'short': []}
for dname, buckets, d, sl_s, tp_s in [('long', bucketsL, 'long', slL, tpL),
                                       ('short', bucketsS, 'short', slS, tpS)]:
    for bname, bmask in buckets.items():
        st = bt(bmask, d, sl_s, tp_s, is_mask)
        on = st['n_trades'] >= 20 and st['expectancy'] >= IS_EXP_MIN
        if on:
            router_on[dname].append(bname)
        print(f"{dname:6s} {bname:12s} {st['n_trades']:5d} {st['win_rate']:6.1f} {st['total_pnl']:11.1f} {st['expectancy']:11.3f} {'✅' if on else '❌':>6s}", flush=True)

print(f"\nسطل‌های روشنِ Router:", flush=True)
print(f"  long : {router_on['long']}", flush=True)
print(f"  short: {router_on['short']}", flush=True)

# ---------------------------------------------------------------------------
# فازِ ارزیابی روی OOS: Router در برابرِ baselineها
# ---------------------------------------------------------------------------
def combine(buckets, names):
    m = np.zeros(n, dtype=bool)
    for nm in names:
        m |= buckets[nm]
    return m

routerL = combine(bucketsL, router_on['long'])
routerS = combine(bucketsS, router_on['short'])

print("\n--- OOS (نیمهٔ دوم): مقایسهٔ سودِ خالص ---", flush=True)
print(f"{'سیستم':28s} {'n':>5s} {'WR%':>6s} {'سودِخالص$':>11s} {'اکسپکتنسی$':>11s}", flush=True)

def report(label, sigL, sigS):
    stL = bt(sigL, 'long', slL, tpL, oos_mask) if sigL is not None else None
    stS = bt(sigS, 'short', slS, tpS, oos_mask) if sigS is not None else None
    ntr = (stL['n_trades'] if stL else 0) + (stS['n_trades'] if stS else 0)
    pnl = (stL['total_pnl'] if stL else 0) + (stS['total_pnl'] if stS else 0)
    wins = ((stL['win_rate']*stL['n_trades']/100) if stL else 0) + ((stS['win_rate']*stS['n_trades']/100) if stS else 0)
    wr = (wins / ntr * 100) if ntr else 0
    exp = (pnl / ntr) if ntr else 0
    print(f"{label:28s} {ntr:5d} {wr:6.1f} {pnl:11.1f} {exp:11.3f}", flush=True)
    return pnl

# baselineها
allL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
allS = down_reg & ~np.isnan(atrv) & (pS >= P_MIN)
p_bullOnly = report('baseline: فقط Bull (بدونِ گیت)', allL, None)
p_bearOnly = report('baseline: فقط Bear (بدونِ گیت)', None, allS)
p_bothRaw  = report('baseline: هر دو (بدونِ گیتِ رژیم)', allL, allS)
p_router   = report('★ Router (سطل‌های سودده)', routerL, routerS)

print("\n--- جمع‌بندی (OOS) ---", flush=True)
best_base = max(p_bullOnly, p_bearOnly, p_bothRaw)
print(f"بهترین baseline: {best_base:.1f}$ | Router: {p_router:.1f}$ | "
      f"بهبود: {p_router - best_base:+.1f}$ ({(p_router/best_base-1)*100 if best_base>0 else 0:+.1f}%)", flush=True)
if p_router > best_base:
    print("✅ Router سودِ خالصِ OOS را نسبت به بهترین baseline افزایش داد → فرضیهٔ «محلِ درست» تأیید شد.", flush=True)
else:
    print("❌ Router در OOS بهتر از baseline نبود → نگاشتِ سطل بازبینی شود.", flush=True)

print("\nتمام.", flush=True)
