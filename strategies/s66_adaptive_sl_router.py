"""
S66 — Adaptive-SL Rolling Router (اهرمِ چهارمِ سودِ خالص) — معیار: سودِ خالص
================================================================================
قانونِ شمارهٔ ۱ پروژه: هدف فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.

انگیزه (بُعدِ چهارمِ دست‌نخورده):
  «محلِ درستِ استفاده» تا حالا سه بُعد داشت:
    (۱) کجا وارد شویم        → S63 (رژیمِ رو-به-جلو)          → 2949$
    (۲) با چه حجمی           → S64 (Kelly رژیم-آگاه)          → 5412$ (+83%)
    (۳) تا کجا سود بگیریم    → S65 (TP رژیم-آگاه)             → 6082$ (+106%)
  اما در همهٔ S61–S65، **SL همیشه ثابت بوده** (Bull 1.5×ATR, Bear 1.7×ATR).
  این آخرین بُعدِ دست‌نخوردهٔ معادلهٔ سودِ خالص است: **کجا ضرر را ببندیم.**

  شهودِ بازار (که این استراتژی کمی‌سازی و آزمون می‌کند):
    - در رژیمِ روندیِ کارآمد (trend_hi) حرکت‌ها یک‌طرفه‌اند → SL نزدیک‌تر می‌تواند
      ضررِ هر باخت را کوچک کند بدونِ اینکه بردها را قربانی کند → R:R و سودِ خالص↑.
    - در رژیمِ پرنوسان/کم‌کارا (chop) نویزِ درون‌روزی زیاد است → SL دورتر لازم است
      تا استاپِ زودهنگام (whipsaw) نخوریم.
  بنابراین ضریبِ SL هم باید مثلِ TP و حجم، **رژیم-آگاه و forward-safe** باشد.

روش (کاملاً روی اسکلتِ S63/S64/S65 — بدونِ نشتِ آینده):
  - برای هر بلوک و هر سطلِ روشن، **ضریبِ SLِ بهینه** را از میانِ چند کاندید روی
    پنجرهٔ اخیرِ گذشته انتخاب می‌کنیم — همانی که بیشترین سودِ خالص را داده.
  - هم‌زمان، ضریبِ TPِ بهینه (S65) و وزنِ Kelly (S64) نیز فعال می‌مانند.
  - چون هم SL هم TP از گذشته انتخاب می‌شوند، **کلِ R:R رژیم-آگاه** می‌شود.
  - جست‌وجوی مشترکِ (SL, TP) روی گرید انجام می‌شود تا بهترین جفت انتخاب شود
    (نه بهینه‌سازیِ جدا-جدا که ممکن است به نقطهٔ زین برسد).

مقایسه: S66 (SL+TP تطبیقی + Kelly) در برابرِ S65 (فقط TP تطبیقی + Kelly) و پایه‌ها.
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
# وزنِ Kelly (همان S64)
W_MIN, W_MAX, W_BASE, W_SLOPE = 0.5, 2.0, 1.0, 1.2
# کاندیدهای ضریبِ TP (بر حسبِ ATR) — همان S65
TP_CANDS_L = [0.8, 1.0, 1.3, 1.6, 2.0]     # Bull
TP_CANDS_S = [1.0, 1.4, 1.8, 2.2, 2.6]     # Bear
# --- جدید در S66: کاندیدهای ضریبِ SL ---
# پایهٔ قبلی (S63–S65): Bull 1.5, Bear 1.7. حالا اطرافِ آن جست‌وجو می‌کنیم.
SL_CANDS_L = [1.0, 1.25, 1.5, 1.75, 2.0]   # Bull
SL_CANDS_S = [1.2, 1.45, 1.7, 1.95, 2.2]   # Bear
SL_BASE_L = 1.5; SL_BASE_S = 1.7           # مقدارِ پایهٔ ثابتِ S65 (برای مرجع)
BASELINE_S63 = 2949.0; BASELINE_S64 = 5412.0; BASELINE_S65 = 6082.0

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')
z = np.load(CACHE, allow_pickle=True)
pL, pS = z['pL'], z['pS']
up_reg, down_reg = z['up_reg'], z['down_reg']
er = z['er']; atrv = z['atrv']

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)
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

def bucket_backtest(direction, bucket, lo, hi, sl_mult, tp_mult, base_lab):
    """بک‌تستِ سطل روی [lo,hi) با ضریبِ SL و TP مشخص. برمی‌گرداند (exp,n,pnl)."""
    m = np.zeros(n, dtype=bool); seg = (base_lab == bucket); m[lo:hi] = seg[lo:hi]
    if m.sum() < 1: return None, 0, 0.0
    sl_s = sl_mult * atrv
    tp_s = tp_mult * atrv
    st, _ = run_backtest(df, m, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st['expectancy'], st['n_trades'], st['total_pnl']

def kelly_weight(exp):
    return float(np.clip(W_BASE + W_SLOPE * (exp - EXP_MIN), W_MIN, W_MAX))

def build_router(direction, base_lab, sl_cands, tp_cands, adaptive_sl, adaptive_tp, use_kelly):
    """
    ماسکِ ورود + وزنِ حجم + ضریبِ SL و TPِ هر کندل را می‌سازد.
    adaptive_sl=False → SL ثابتِ پایه (S65). adaptive_tp=False → TP ثابتِ پایه.
    جست‌وجوی مشترکِ (SL,TP) روی گرید تا جفتِ بیشینه‌کنندهٔ سودِ خالص انتخاب شود.
    """
    entries = np.zeros(n, dtype=bool)
    weights = np.ones(n)
    tp_mult_arr = np.zeros(n)
    sl_mult_arr = np.zeros(n)
    base_tp = tp_cands[1]                    # 1.0 / 1.4 پایهٔ S64/S65
    base_sl = SL_BASE_L if direction == 'long' else SL_BASE_S
    log = []
    for start in range(LOOKBACK, n, STEP):
        end = min(start + STEP, n); lb_lo = max(0, start - LOOKBACK)
        chosen = []
        for bk in BUCKETS:
            # ابتدا با (SL,TP) پایه چک کن سطل روشن است یا نه (همان قاعدهٔ S63)
            exp0, ntr0, _ = bucket_backtest(direction, bk, lb_lo, start, base_sl, base_tp, base_lab)
            if exp0 is None or ntr0 < MIN_N or exp0 < EXP_MIN:
                continue
            # جست‌وجوی مشترکِ SL×TP روی پنجرهٔ اخیر (بهترین سودِ خالص)
            sl_grid = sl_cands if adaptive_sl else [base_sl]
            tp_grid = tp_cands if adaptive_tp else [base_tp]
            best_sl, best_tp, best_pnl, best_exp = base_sl, base_tp, -1e9, exp0
            for slc in sl_grid:
                for tpc in tp_grid:
                    e, nt, pnl = bucket_backtest(direction, bk, lb_lo, start, slc, tpc, base_lab)
                    if e is not None and nt >= MIN_N and pnl > best_pnl:
                        best_pnl, best_sl, best_tp, best_exp = pnl, slc, tpc, e
            w = kelly_weight(best_exp) if use_kelly else 1.0
            chosen.append((bk, best_sl, best_tp, w))
        for bk, slc, tpc, w in chosen:
            seg = (base_lab == bk)
            sel = np.zeros(n, dtype=bool); sel[start:end] = seg[start:end]
            entries |= sel; weights[sel] = w; tp_mult_arr[sel] = tpc; sl_mult_arr[sel] = slc
        log.append((start, [(b, sl, tp, round(w, 2)) for b, sl, tp, w in chosen]))
    return entries, weights, tp_mult_arr, sl_mult_arr, log

eval_mask = np.zeros(n, dtype=bool); eval_mask[LOOKBACK:] = True

def _series(mult_arr, default_mult):
    return np.where(mult_arr > 0, mult_arr * atrv, default_mult * atrv)

def evaluate(direction, entries, weights, tp_mult_arr, sl_mult_arr):
    s = entries & eval_mask
    base_sl = SL_BASE_L if direction == 'long' else SL_BASE_S
    sl_series = _series(sl_mult_arr, base_sl)
    tp_series = _series(tp_mult_arr, tp_mult_arr.max() if tp_mult_arr.max() > 0 else 1.0)
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_series, tp_series=tp_series)
    if len(tr) == 0:
        return 0.0, 0, 0.0
    w = weights[tr['signal_bar'].values]; w[w == 0] = 1.0
    weighted = tr['pnl'].values * w
    wins = (tr['outcome'].values == 'win').sum()
    return weighted.sum(), len(tr), wins / len(tr) * 100

def eval_curve(direction, entries, weights, tp_mult_arr, sl_mult_arr):
    s = entries & eval_mask
    base_sl = SL_BASE_L if direction == 'long' else SL_BASE_S
    sl_series = _series(sl_mult_arr, base_sl)
    tp_series = _series(tp_mult_arr, 1.0)
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_series, tp_series=tp_series)
    if len(tr) == 0:
        return pd.DataFrame(columns=['exit_bar', 'pnl'])
    w = weights[tr['signal_bar'].values]; w[w == 0] = 1.0
    out = tr[['exit_bar']].copy(); out['pnl'] = tr['pnl'].values * w
    return out

def risk_stats(curve):
    if len(curve) == 0: return 0.0, 0.0
    c = curve.sort_values('exit_bar'); eq = c['pnl'].cumsum().values
    dd = (eq - np.maximum.accumulate(eq)).min()
    r = c['pnl'].values
    sh = (r.mean() / r.std() * np.sqrt(len(r))) if r.std() > 0 else 0.0
    return dd, sh

print("=== S66: Adaptive-SL Rolling Router (معیار: سودِ خالص) ===\n", flush=True)
print(f"baseline S63 (ورودِ رژیمی)                = {BASELINE_S63:.0f}$", flush=True)
print(f"baseline S64 (+ حجمِ Kelly)               = {BASELINE_S64:.0f}$", flush=True)
print(f"baseline S65 (+ TP تطبیقی)                = {BASELINE_S65:.0f}$\n", flush=True)

def run_config(name, adaptive_sl, adaptive_tp, use_kelly, show_risk=False):
    eL, wL_, tpL_, slL_, _ = build_router('long', labL, SL_CANDS_L, TP_CANDS_L, adaptive_sl, adaptive_tp, use_kelly)
    eS, wS_, tpS_, slS_, _ = build_router('short', labS, SL_CANDS_S, TP_CANDS_S, adaptive_sl, adaptive_tp, use_kelly)
    pL_, nL_, wrL_ = evaluate('long', eL, wL_, tpL_, slL_)
    pS_, nS_, wrS_ = evaluate('short', eS, wS_, tpS_, slS_)
    tot = pL_ + pS_; nn = nL_ + nS_
    wr = (wrL_ * nL_ + wrS_ * nS_) / nn if nn else 0
    line = f"{name:48s} n={nn:5d}  WR={wr:5.1f}%  سودِخالص={tot:9.1f}$"
    if show_risk:
        curve = pd.concat([eval_curve('long', eL, wL_, tpL_, slL_),
                           eval_curve('short', eS, wS_, tpS_, slS_)])
        dd, sh = risk_stats(curve)
        line += f"  MaxDD={dd:8.1f}$  Sharpe={sh:.2f}  سود/|DD|={tot/abs(dd) if dd else 0:.2f}"
    print(line, flush=True)
    return tot

# مرجع: بازتولیدِ S65 (فقط TP تطبیقی) با همین کد → باید ~6082 بدهد
p_s65 = run_config('مرجع S65 (فقط TP تطبیقی + Kelly)', False, True, True, show_risk=True)
# اهرمِ چهارم به‌تنهایی: فقط SL تطبیقی (TP ثابت) روی S64
p_slonly = run_config('فقط SL تطبیقی + Kelly (بدونِ TP تطبیقی)', True, False, True, show_risk=True)
# S66 کامل: SL + TP تطبیقی + Kelly
p_full = run_config('★ S66: SL + TP تطبیقی + Kelly', True, True, True, show_risk=True)

print(f"\nاثرِ تنهای SL تطبیقی (بر S64={BASELINE_S64:.0f}$): {p_slonly - BASELINE_S64:+.1f}$ "
      f"({(p_slonly/BASELINE_S64-1)*100:+.1f}%)", flush=True)
print(f"اثرِ S66 نسبت به S65 ({BASELINE_S65:.0f}$): {p_full - BASELINE_S65:+.1f}$ "
      f"({(p_full/BASELINE_S65-1)*100:+.1f}%)", flush=True)
print(f"اثرِ کلِ S66 نسبت به پایهٔ S63: {p_full - BASELINE_S63:+.1f}$ "
      f"({(p_full/BASELINE_S63-1)*100:+.1f}%)", flush=True)
if p_full > BASELINE_S65:
    print("✅ SL تطبیقی یک اهرمِ مستقلِ چهارم است → سودِ خالصِ بیشتر.", flush=True)
else:
    print("△ SL تطبیقی چیزی اضافه نکرد (بُعدِ SL روی داده اشباع شده است).", flush=True)
print("\nتمام.", flush=True)
