"""
S66 — جاروبِ آستانهٔ ER (راهکار A از User Note) — معیار: سودِ خالص
================================================================================
قانونِ شمارهٔ ۱ پروژه: معیارِ موفقیت **فقط و فقط «سودِ خالصِ بیشتر»** است — نه WR،
نه Profit Factor، نه تعدادِ معامله در روز. اینجا فرکانس را بالا می‌بریم فقط اگر
سودِ خالص افت نکند.

انگیزه (User Note — راهکار A):
  در S63–S65 آستانهٔ `ER_TREND_THR = 0.30` ثابت بود. این آستانه تعیین می‌کند چه
  کندلی «روندی (trend)» شمرده می‌شود. با آستانهٔ ۰.۳۰ فقط ~۱۹.۵٪ زمان trendy است
  (بقیه chop). فایلِ L33 نشان داد با er=0.15 نسبتِ trendy به ~۵۲.۴٪ و اکشن/روز به
  ۵.۶۲ می‌رسد. فرضیهٔ User Note: کاهشِ آستانه فرکانس را بالا می‌برد؛ باید بک‌تست
  شود که آیا سودِ خالص افت می‌کند یا نه.

روش (کاملاً forward-safe — همان اسکلتِ برندهٔ S65):
  - دقیقاً موتور/سطل/Kelly/TP-تطبیقیِ S65 را نگه می‌داریم (تا مقایسه منصفانه باشد).
  - تنها متغیرِ آزمایش: `ER_TREND_THR` که در چند مقدار جاروب می‌شود.
  - برای هر آستانه: سودِ خالصِ کل + **آزمونِ walk-forward دو-نیمه** (نیمهٔ اول و
    نیمهٔ دومِ بازهٔ فعالِ Router) تا مطمئن شویم بهبود پایدار است، نه وابسته به
    یک رژیمِ خاص.
  - baseline مقایسه: S65 با آستانهٔ ۰.۳۰ = ۶۰۸۲$.

خروجی: بهترین آستانه بر اساسِ سودِ خالصِ کل، با گزارشِ پایداریِ دو-نیمه.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
P_HI = 0.66; P_MIN = 0.58
STEP = 6000; LOOKBACK = 24000
EXP_MIN = 0.10; MIN_N = 15
W_MIN, W_MAX, W_BASE, W_SLOPE = 0.5, 2.0, 1.0, 1.2
TP_CANDS_L = [0.8, 1.0, 1.3, 1.6, 2.0]
TP_CANDS_S = [1.0, 1.4, 1.8, 2.2, 2.6]
SL_MULT_L = 1.5; SL_MULT_S = 1.7
BASELINE_S65 = 6081.9   # آستانهٔ ۰.۳۰

# جاروبِ آستانهٔ ER (راهکار A: 0.30 → 0.15، به‌علاوهٔ مقادیرِ اطراف برای منحنی)
ER_GRID = [0.15, 0.18, 0.20, 0.25, 0.30, 0.35]

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')
z = np.load(CACHE, allow_pickle=True)
pL, pS = z['pL'], z['pS']
up_reg, down_reg = z['up_reg'], z['down_reg']
er = z['er']; atrv = z['atrv']

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
slL = SL_MULT_L * atrv; slS = SL_MULT_S * atrv
baseL = up_reg & ~np.isnan(atrv) & (pL >= P_MIN)
baseS = down_reg & ~np.isnan(atrv) & (pS >= P_MIN)
BUCKETS = ['trend_hi', 'trend_lo', 'chop_hi', 'chop_lo']
eval_mask = np.zeros(n, dtype=bool); eval_mask[LOOKBACK:] = True


def build_labels(direction, base, trendy):
    p = pL if direction == 'long' else pS
    ef = np.where(trendy, 'trend', 'chop')
    pw = np.where(p >= P_HI, 'hi', 'lo')
    lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
    lab[~base] = ''
    return lab


def bucket_backtest(direction, bucket, lo, hi, sl_s, tp_mult, base_lab):
    m = np.zeros(n, dtype=bool); seg = (base_lab == bucket); m[lo:hi] = seg[lo:hi]
    if m.sum() < 1: return None, 0, 0.0
    tp_s = tp_mult * atrv
    st, _ = run_backtest(df, m, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st['expectancy'], st['n_trades'], st['total_pnl']


def kelly_weight(exp):
    return float(np.clip(W_BASE + W_SLOPE * (exp - EXP_MIN), W_MIN, W_MAX))


def build_router(direction, base_lab, sl_s, tp_cands):
    entries = np.zeros(n, dtype=bool); weights = np.ones(n); tp_mult_arr = np.zeros(n)
    base_tp = tp_cands[1]
    for start in range(LOOKBACK, n, STEP):
        end = min(start + STEP, n); lb_lo = max(0, start - LOOKBACK)
        chosen = []
        for bk in BUCKETS:
            exp0, ntr0, _ = bucket_backtest(direction, bk, lb_lo, start, sl_s, base_tp, base_lab)
            if exp0 is None or ntr0 < MIN_N or exp0 < EXP_MIN:
                continue
            best_tp, best_pnl, best_exp = base_tp, -1e9, exp0
            for tpc in tp_cands:
                e, nt, pnl = bucket_backtest(direction, bk, lb_lo, start, sl_s, tpc, base_lab)
                if e is not None and nt >= MIN_N and pnl > best_pnl:
                    best_pnl, best_tp, best_exp = pnl, tpc, e
            w = kelly_weight(best_exp)
            chosen.append((bk, best_tp, w))
        for bk, tpc, w in chosen:
            seg = (base_lab == bk)
            sel = np.zeros(n, dtype=bool); sel[start:end] = seg[start:end]
            entries |= sel; weights[sel] = w; tp_mult_arr[sel] = tpc
    return entries, weights, tp_mult_arr


def eval_curve(direction, entries, weights, tp_mult_arr, sl_s):
    s = entries & eval_mask
    tp_series = np.where(tp_mult_arr > 0, tp_mult_arr * atrv, atrv)
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_s, tp_series=tp_series)
    if len(tr) == 0:
        return pd.DataFrame(columns=['exit_bar', 'signal_bar', 'pnl', 'outcome'])
    w = weights[tr['signal_bar'].values]; w[w == 0] = 1.0
    out = tr[['exit_bar', 'signal_bar', 'outcome']].copy()
    out['pnl'] = tr['pnl'].values * w
    return out


def risk_stats(curve):
    if len(curve) == 0: return 0.0, 0.0
    c = curve.sort_values('exit_bar'); eq = c['pnl'].cumsum().values
    dd = (eq - np.maximum.accumulate(eq)).min()
    r = c['pnl'].values
    sh = (r.mean() / r.std() * np.sqrt(len(r))) if r.std() > 0 else 0.0
    return dd, sh


def run_threshold(er_thr):
    trendy = np.nan_to_num(er >= er_thr, nan=False).astype(bool)
    labL = build_labels('long', baseL, trendy)
    labS = build_labels('short', baseS, trendy)
    eL, wL_, tpL_ = build_router('long', labL, slL, TP_CANDS_L)
    eS, wS_, tpS_ = build_router('short', labS, slS, TP_CANDS_S)
    cL = eval_curve('long', eL, wL_, tpL_, slL)
    cS = eval_curve('short', eS, wS_, tpS_, slS)
    curve = pd.concat([cL, cS]).sort_values('exit_bar')
    if len(curve) == 0:
        return dict(thr=er_thr, n=0, pnl=0, wr=0, dd=0, sh=0, trendy_pct=0,
                    h1=0, h2=0, tpd=0)
    n_tr = len(curve)
    pnl = curve['pnl'].sum()
    wr = (curve['outcome'] == 'win').mean() * 100
    dd, sh = risk_stats(curve)
    trendy_pct = trendy[LOOKBACK:].mean() * 100
    # آزمونِ دو-نیمه (walk-forward) بر اساسِ exit_bar
    mid = (LOOKBACK + n) // 2
    h1 = curve[curve['exit_bar'] < mid]['pnl'].sum()
    h2 = curve[curve['exit_bar'] >= mid]['pnl'].sum()
    # اکشن/روز (تقریبی): معاملات در روزهای تقویمی بازهٔ فعال
    span_days = (df['time'].iloc[n - 1] - df['time'].iloc[LOOKBACK]) / 86400.0
    tpd = n_tr / span_days if span_days > 0 else 0
    return dict(thr=er_thr, n=n_tr, pnl=pnl, wr=wr, dd=dd, sh=sh,
                trendy_pct=trendy_pct, h1=h1, h2=h2, tpd=tpd)


print("=== S66: جاروبِ آستانهٔ ER (راهکار A) — معیار: سودِ خالص ===\n", flush=True)
print(f"baseline S65 (ER_THR=0.30) = {BASELINE_S65:.1f}$\n", flush=True)
print(f"{'ER_THR':>7} {'trendy%':>8} {'n':>6} {'WR':>6} {'سودخالص':>10} "
      f"{'نیمه۱':>8} {'نیمه۲':>8} {'MaxDD':>9} {'Sharpe':>7} {'سود/DD':>7} {'trade/day':>9}", flush=True)
print("-" * 100, flush=True)

results = []
for thr in ER_GRID:
    r = run_threshold(thr)
    results.append(r)
    sd = r['pnl'] / abs(r['dd']) if r['dd'] else 0
    mark = " ★" if abs(thr - 0.30) < 1e-9 else ""
    print(f"{r['thr']:>7.2f} {r['trendy_pct']:>7.1f}% {r['n']:>6d} {r['wr']:>5.1f}% "
          f"{r['pnl']:>9.1f}$ {r['h1']:>7.1f}$ {r['h2']:>7.1f}$ {r['dd']:>8.1f}$ "
          f"{r['sh']:>7.2f} {sd:>7.2f} {r['tpd']:>8.2f}{mark}", flush=True)

# انتخابِ برنده بر اساسِ سودِ خالصِ کل (قانونِ شمارهٔ ۱)
best = max(results, key=lambda r: r['pnl'])
print("\n" + "=" * 60, flush=True)
print(f"بهترین آستانه بر اساسِ سودِ خالص: ER_THR={best['thr']:.2f} "
      f"→ سودِ خالص={best['pnl']:.1f}$", flush=True)
delta = best['pnl'] - BASELINE_S65
print(f"اختلاف با baseline S65: {delta:+.1f}$ ({delta/BASELINE_S65*100:+.1f}%)", flush=True)

# آیا هر دو نیمه مثبت‌اند؟ (پایداری walk-forward)
stable = best['h1'] > 0 and best['h2'] > 0
print(f"پایداریِ دو-نیمه: نیمه۱={best['h1']:.1f}$  نیمه۲={best['h2']:.1f}$  "
      f"→ {'✅ هر دو مثبت' if stable else '⚠️ یک نیمه ضعیف'}", flush=True)

# آیا راهکار A (کاهش به 0.15) به‌تنهایی سود خالص را حفظ/بهبود داد؟
r015 = next(r for r in results if abs(r['thr'] - 0.15) < 1e-9)
d015 = r015['pnl'] - BASELINE_S65
print(f"\nراهکار A (ER 0.30→0.15): سودِ خالص={r015['pnl']:.1f}$ ({d015:+.1f}$), "
      f"trade/day={r015['tpd']:.2f} (فرکانس {r015['tpd']/results[4]['tpd']:.2f}× نسبت به 0.30)", flush=True)
if d015 >= 0:
    print("✅ راهکار A: فرکانس بالا رفت و سودِ خالص افت نکرد → تأییدِ User Note.", flush=True)
else:
    print("⚠️ راهکار A: فرکانس بالا رفت اما سودِ خالص افت کرد → طبقِ قانونِ ۱ ردّ می‌شود.", flush=True)

if best['pnl'] > BASELINE_S65 and stable:
    print(f"\n🏆 برندهٔ جدید: ER_THR={best['thr']:.2f} با سودِ خالص {best['pnl']:.1f}$ "
          f"(> {BASELINE_S65:.1f}$ و پایدار).", flush=True)
else:
    print(f"\n△ baseline S65 (ER=0.30) بهترین می‌ماند یا بهبود ناپایدار است.", flush=True)
print("\nتمام.", flush=True)
