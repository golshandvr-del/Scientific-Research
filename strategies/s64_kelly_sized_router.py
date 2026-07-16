"""
S64 — Kelly-Sized Rolling Router (معیار: فقط «سودِ خالص» — PARADIGM v2)
================================================================================
انگیزه (شکافِ کشف‌شده در تحقیقاتِ قبلی):
  همهٔ روترهای S61–S63 با **حجمِ ثابت** (۱ لات فرضی برای هر معامله) کار می‌کردند.
  طبقِ PARADIGM v2 معیار فقط «سودِ خالص» است — و بزرگ‌ترین اهرمِ دست‌نخورده برای
  بالا بردنِ سودِ خالص **بدونِ تغییرِ WR**، مقیاس‌بندیِ حجمِ معامله بر اساسِ کیفیتِ
  (edge) هر سطلِ رژیم است. منطقِ ریاضی: اگر یک سطل اخیراً اکسپکتنسیِ بالاتری داشته،
  عقلانی است که حجمِ بیشتری در آن سطل ریسک کنیم (اصلِ Kelly کسری).

روش (کاملاً بدونِ نشتِ آینده — همان اسکلتِ برندهٔ S63):
  ۱) داده به بلوک‌های STEP کندلی تقسیم می‌شود.
  ۲) برای هر بلوکِ b، فقط از پنجرهٔ اخیرِ LOOKBACK کندلِ **قبل از b** یاد می‌گیریم:
       - کدام سطلِ رژیم اکسپکتنسیِ اخیرِ ≥EXP_MIN و n≥MIN_N دارد → «روشن».
       - **وزنِ حجمِ** آن سطل = تابعی از اکسپکتنسیِ اخیرش (Kelly-کسری، کلیپ‌شده).
  ۳) در بلوکِ b، معاملاتِ سطل‌های روشن با وزنِ حجمِ یادگرفته‌شده اجرا می‌شوند.
  ۴) سودِ خالصِ وزنی با baselineِ S63 (حجمِ ثابت) مقایسه می‌شود.

  probaها از کشِ walk-forwardِ S61 (بدونِ look-ahead).
  همهٔ وزن‌ها فقط از گذشته یاد گرفته می‌شوند → forward-safe.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
ER_TREND_THR = 0.30
P_HI = 0.66; P_MIN = 0.58
STEP = 6000
LOOKBACK = 24000
EXP_MIN = 0.10
MIN_N = 15

# --- پارامترهای مقیاس‌بندیِ حجم (Kelly کسری) ---
# وزن = clip( base + slope * (recent_exp - EXP_MIN), W_MIN, W_MAX )
# یعنی سطلی که اکسپکتنسیِ اخیرش بیشتر است، حجمِ بیشتری می‌گیرد.
W_MIN = 0.5     # حداقلِ وزنِ حجم (سطلِ ضعیفِ روشن)
W_MAX = 2.0     # حداکثرِ وزنِ حجم (سطلِ بسیار قوی)
W_BASE = 1.0    # وزنِ پایه در آستانهٔ EXP_MIN
W_SLOPE = 1.2   # حساسیتِ وزن به اکسپکتنسیِ اخیر ($ به وزن)

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')

print("=== S64: Kelly-Sized Rolling Router (معیار: سودِ خالص) ===\n", flush=True)

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

labL = build_labels('long', baseL)
labS = build_labels('short', baseS)

BUCKETS = ['trend_hi', 'trend_lo', 'chop_hi', 'chop_lo']


def recent_stats(direction, bucket, lo, hi, sl_s, tp_s, base_lab):
    """اکسپکتنسی و تعدادِ معاملهٔ سطل روی بازهٔ اخیر [lo,hi)."""
    m = np.zeros(n, dtype=bool)
    seg = (base_lab == bucket)
    m[lo:hi] = seg[lo:hi]
    if m.sum() < 1:
        return None, 0
    st, _ = run_backtest(df, m, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st['expectancy'], st['n_trades']


def kelly_weight(recent_exp):
    """وزنِ حجم از اکسپکتنسیِ اخیر (Kelly کسری، کلیپ‌شده)."""
    w = W_BASE + W_SLOPE * (recent_exp - EXP_MIN)
    return float(np.clip(w, W_MIN, W_MAX))


def rolling_entries_weighted(direction, base_lab, sl_s, tp_s):
    """
    خروجی: entries (bool) و weights (float هم‌طول) — وزنِ حجمِ هر کندلِ ورودی.
    منطقِ روشن‌شدنِ سطل دقیقاً مثلِ S63، اما هر سطلِ روشن یک وزنِ حجم هم می‌گیرد.
    """
    entries = np.zeros(n, dtype=bool)
    weights = np.zeros(n, dtype=np.float64)
    on_log = []
    b0 = LOOKBACK
    for start in range(b0, n, STEP):
        end = min(start + STEP, n)
        lb_lo = max(0, start - LOOKBACK)
        on = []
        for bk in BUCKETS:
            exp, ntr = recent_stats(direction, bk, lb_lo, start, sl_s, tp_s, base_lab)
            if exp is not None and ntr >= MIN_N and exp >= EXP_MIN:
                w = kelly_weight(exp)
                on.append((bk, w, exp))
        for bk, w, exp in on:
            seg = (base_lab == bk)
            sel = np.zeros(n, dtype=bool); sel[start:end] = seg[start:end]
            entries |= sel
            weights[sel] = w
        on_log.append((start, [(b, round(w, 2)) for b, w, _ in on]))
    return entries, weights, on_log


print("ساختِ ورودی‌های وزنیِ Bull ...", flush=True)
entL, wL, logL = rolling_entries_weighted('long', labL, slL, tpL)
print("ساختِ ورودی‌های وزنیِ Bear ...", flush=True)
entS, wS, logS = rolling_entries_weighted('short', labS, slS, tpS)

eval_mask = np.zeros(n, dtype=bool); eval_mask[LOOKBACK:] = True


def weighted_pnl(direction, sig, weights, sl_s, tp_s):
    """
    بک‌تست را با حجمِ ثابت اجرا می‌کنیم، سپس pnl هر معامله را در وزنِ حجمِ
    کندلِ سیگنالش (weights[signal_bar]) ضرب می‌کنیم → سودِ خالصِ وزنی.
    (چون هزینهٔ اسپرد هم به‌نسبتِ حجم مقیاس می‌خورد، این ضرب کاملاً درست است.)
    """
    s = sig & eval_mask
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_s, tp_series=tp_s)
    if len(tr) == 0:
        return 0.0, 0, 0.0, 0.0
    w = weights[tr['signal_bar'].values]
    w[w == 0] = 1.0   # ایمنی
    weighted = (tr['pnl'].values * w)
    wins = (tr['outcome'].values == 'win').sum()
    return weighted.sum(), len(tr), wins / len(tr) * 100, w.mean()


def flat_pnl(direction, sig, sl_s, tp_s):
    s = sig & eval_mask
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_s, tp_series=tp_s)
    if len(tr) == 0:
        return 0.0, 0, 0.0
    wins = (tr['outcome'].values == 'win').sum()
    return tr['pnl'].sum(), len(tr), wins / len(tr) * 100


print("\n--- مقایسهٔ سودِ خالص (بازهٔ فعال‌بودنِ Router) ---", flush=True)

# baseline S63: همان سطل‌های روشن اما حجمِ ثابت
fL_pnl, fL_n, fL_wr = flat_pnl('long', entL, slL, tpL)
fS_pnl, fS_n, fS_wr = flat_pnl('short', entS, slS, tpS)
flat_total = fL_pnl + fS_pnl
flat_n = fL_n + fS_n
flat_wr = (fL_wr * fL_n + fS_wr * fS_n) / flat_n if flat_n else 0
print(f"{'baseline S63 (حجمِ ثابت)':38s} n={flat_n:5d}  WR={flat_wr:5.1f}%  "
      f"سودِخالص={flat_total:9.1f}$  اکسپکتنسی={flat_total/flat_n if flat_n else 0:.3f}$", flush=True)

# S64: حجمِ وزنیِ Kelly
wL_pnl, wL_n, wL_wr, wL_avgw = weighted_pnl('long', entL, wL, slL, tpL)
wS_pnl, wS_n, wS_wr, wS_avgw = weighted_pnl('short', entS, wS, slS, tpS)
w_total = wL_pnl + wS_pnl
w_n = wL_n + wS_n
w_wr = (wL_wr * wL_n + wS_wr * wS_n) / w_n if w_n else 0
avg_w = (wL_avgw * wL_n + wS_avgw * wS_n) / w_n if w_n else 0
# اکسپکتنسیِ سرانه بر واحدِ حجم = سودِ خالص / مجموعِ حجم
print(f"{'★ S64 (حجمِ وزنیِ Kelly)':38s} n={w_n:5d}  WR={w_wr:5.1f}%  "
      f"سودِخالص={w_total:9.1f}$  میانگینِ‌وزن={avg_w:.2f}", flush=True)

print(f"\nبهبودِ S64 نسبت به baselineِ S63: {w_total - flat_total:+.1f}$ "
      f"({(w_total/flat_total-1)*100 if flat_total>0 else 0:+.1f}%)", flush=True)

# سودِ خالص بر واحدِ حجمِ ریسک‌شده (کارایی سرمایه)
total_units_flat = flat_n * 1.0
total_units_w = wL_avgw * wL_n + wS_avgw * wS_n
print(f"سودِ خالص بر واحدِ حجمِ ریسک‌شده — baseline: {flat_total/total_units_flat if total_units_flat else 0:.3f}$/واحد  |  "
      f"S64: {w_total/total_units_w if total_units_w else 0:.3f}$/واحد", flush=True)

if w_total > flat_total:
    print("✅ مقیاس‌بندیِ Kelly سودِ خالص را بالا برد.", flush=True)
else:
    print("△ مقیاس‌بندیِ Kelly سودِ خالص را بالا نبرد؛ باید کارایی سرمایه را سنجید.", flush=True)

# ---------------------------------------------------------------------------
# تحلیلِ ریسک-تعدیل‌شده: آیا بهبود واقعی است یا صرفاً ریسکِ بیشتر؟
# منحنیِ سرمایه (equity) هر دو سیستم را می‌سازیم و max-drawdown + Sharpe مقایسه می‌کنیم.
# ---------------------------------------------------------------------------
def equity_curve(direction, sig, weights, sl_s, tp_s, use_weight):
    s = sig & eval_mask
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_s, tp_series=tp_s)
    if len(tr) == 0:
        return pd.DataFrame(columns=['exit_bar', 'pnl'])
    w = np.ones(len(tr))
    if use_weight:
        w = weights[tr['signal_bar'].values]; w[w == 0] = 1.0
    out = tr[['exit_bar']].copy()
    out['pnl'] = tr['pnl'].values * w
    return out


def risk_stats(curve):
    """max-drawdown و Sharpه سرانه از یک منحنیِ pnlِ مرتب‌شده بر حسبِ زمانِ خروج."""
    if len(curve) == 0:
        return 0.0, 0.0
    c = curve.sort_values('exit_bar')
    eq = c['pnl'].cumsum().values
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak).min()          # عمقِ افتِ حداکثری ($)
    r = c['pnl'].values
    sharpe = (r.mean() / r.std() * np.sqrt(len(r))) if r.std() > 0 else 0.0
    return dd, sharpe

# منحنیِ ترکیبیِ هر سیستم (long+short)
flat_curve = pd.concat([equity_curve('long', entL, wL, slL, tpL, False),
                        equity_curve('short', entS, wS, slS, tpS, False)])
w_curve = pd.concat([equity_curve('long', entL, wL, slL, tpL, True),
                     equity_curve('short', entS, wS, slS, tpS, True)])
flat_dd, flat_sh = risk_stats(flat_curve)
w_dd, w_sh = risk_stats(w_curve)

print("\n--- تحلیلِ ریسک-تعدیل‌شده (آیا بهبود واقعی است؟) ---", flush=True)
print(f"baseline S63: MaxDD={flat_dd:8.1f}$  Sharpe={flat_sh:.2f}  "
      f"سود/|DD|={flat_total/abs(flat_dd) if flat_dd else 0:.2f}", flush=True)
print(f"★ S64:        MaxDD={w_dd:8.1f}$  Sharpe={w_sh:.2f}  "
      f"سود/|DD|={w_total/abs(w_dd) if w_dd else 0:.2f}", flush=True)
# نکتهٔ کلیدی: اگر «سود/|DD|» و Sharpe هم بهتر شوند، بهبود واقعی است نه صرفاً اهرم.
if abs(w_dd) > 0 and abs(flat_dd) > 0:
    if (w_total/abs(w_dd)) >= (flat_total/abs(flat_dd)) * 0.98:
        print("✅ بازدهِ ریسک-تعدیل‌شده (سود/DD) حفظ/بهتر شد → بهبودِ واقعیِ تخصیصِ سرمایه.", flush=True)
    else:
        print("⚠️ سود بالا رفت ولی به قیمتِ DDِ بیشتر (اهرمِ خام) — با احتیاط.", flush=True)

print("\n--- نمونهٔ وزنِ سطل‌های روشنِ Bull (هر ۵ بلوک) ---", flush=True)
for k, (start, on) in enumerate(logL):
    if k % 5 == 0:
        print(f"  کندلِ {start}: {on if on else '(هیچ — خنثی)'}", flush=True)

print("\nتمام.", flush=True)
