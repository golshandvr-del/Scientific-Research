"""
S65 — Adaptive-TP Rolling Router (اهرمِ دومِ سودِ خالص) — معیار: سودِ خالص
================================================================================
انگیزه:
  S64 اثبات کرد که «حجمِ رژیم-آگاه» یک اهرمِ مستقلِ سودِ خالص است (+۸۳٪).
  اهرمِ دستِ‌نخوردهٔ بعدی: **TP رژیم-آگاه**. همهٔ روترهای S61–S64 از TP ثابتِ
  ATR-محور استفاده می‌کردند (Bull TP=1.0×ATR, Bear TP=1.4×ATR). اما شهودِ بازار
  می‌گوید: در سطلِ **روندیِ کارآمد (trend_hi)** حرکت‌ها ادامه‌دارترند → TP دورتر
  سودِ بیشتری برداشت می‌کند؛ در سطلِ **رنج (chop)** بهتر است TP نزدیک بماند.

روش (forward-safe — همان اسکلتِ S63/S64):
  - برای هر بلوک و هر سطلِ روشن، **ضریبِ TPِ بهینه** را روی پنجرهٔ اخیر جست‌وجو
    می‌کنیم (از میانِ چند کاندید) — همانی که در پنجرهٔ گذشته بیشترین سودِ خالص را
    داده. سپس همان ضریب را برای بلوکِ آینده به کار می‌بریم.
  - این کاملاً بدونِ نشتِ آینده است: ضریبِ TP هم مثلِ روشن/خاموش و مثلِ وزنِ حجم،
    فقط از گذشته یاد گرفته می‌شود.
  - سپس **روی S64 سوار می‌شود** (حجمِ Kelly هم فعال می‌ماند) تا ببینیم دو اهرم
    با هم سودِ خالص را بیشتر می‌کنند یا نه.

مقایسه: S65 (Adaptive-TP + Kelly) در برابرِ S64 (TP ثابت + Kelly) و S63 (پایه).
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
# کاندیدهای ضریبِ TP (بر حسبِ ATR) که در پنجرهٔ اخیر جست‌وجو می‌شوند
TP_CANDS_L = [0.8, 1.0, 1.3, 1.6, 2.0]     # Bull
TP_CANDS_S = [1.0, 1.4, 1.8, 2.2, 2.6]     # Bear
SL_MULT_L = 1.5; SL_MULT_S = 1.7           # SL ثابت می‌ماند (مثلِ قبل)
BASELINE_S63 = 2949.0; BASELINE_S64 = 5412.0

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')
z = np.load(CACHE, allow_pickle=True)
pL, pS = z['pL'], z['pS']
up_reg, down_reg = z['up_reg'], z['down_reg']
er = z['er']; atrv = z['atrv']

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)
slL = SL_MULT_L * atrv; slS = SL_MULT_S * atrv
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

def bucket_backtest(direction, bucket, lo, hi, sl_s, tp_mult, base_lab):
    """بک‌تستِ سطل روی بازهٔ [lo,hi) با ضریبِ TP مشخص. برمی‌گرداند (exp,n,pnl)."""
    m = np.zeros(n, dtype=bool); seg = (base_lab == bucket); m[lo:hi] = seg[lo:hi]
    if m.sum() < 1: return None, 0, 0.0
    tp_s = tp_mult * atrv
    st, _ = run_backtest(df, m, None, None, direction, spread=SPREAD, max_hold=HZ,
                         sl_series=sl_s, tp_series=tp_s)
    return st['expectancy'], st['n_trades'], st['total_pnl']

def kelly_weight(exp):
    return float(np.clip(W_BASE + W_SLOPE * (exp - EXP_MIN), W_MIN, W_MAX))

def build_router(direction, base_lab, sl_s, tp_cands, adaptive_tp, use_kelly):
    """
    ماسکِ ورود + وزنِ حجم + ضریبِ TPِ هر کندل را می‌سازد.
    adaptive_tp=False → TP ثابت (اولین کاندید = مقدارِ پایهٔ S64: 1.0/1.4).
    use_kelly=False → وزنِ همه ۱.
    """
    entries = np.zeros(n, dtype=bool)
    weights = np.ones(n)
    tp_mult_arr = np.zeros(n)
    base_tp = tp_cands[1] if direction == 'long' else tp_cands[1]  # 1.0 / 1.4 پایهٔ S64
    log = []
    for start in range(LOOKBACK, n, STEP):
        end = min(start + STEP, n); lb_lo = max(0, start - LOOKBACK)
        chosen = []
        for bk in BUCKETS:
            # ابتدا با TP پایه چک کن سطل روشن است یا نه (همان قاعدهٔ S63)
            exp0, ntr0, _ = bucket_backtest(direction, bk, lb_lo, start, sl_s, base_tp, base_lab)
            if exp0 is None or ntr0 < MIN_N or exp0 < EXP_MIN:
                continue
            # انتخابِ ضریبِ TP: بهترین سودِ خالصِ اخیر (یا پایه اگر adaptive خاموش)
            if adaptive_tp:
                best_tp, best_pnl, best_exp = base_tp, -1e9, exp0
                for tpc in tp_cands:
                    e, nt, pnl = bucket_backtest(direction, bk, lb_lo, start, sl_s, tpc, base_lab)
                    if e is not None and nt >= MIN_N and pnl > best_pnl:
                        best_pnl, best_tp, best_exp = pnl, tpc, e
            else:
                best_tp, best_exp = base_tp, exp0
            w = kelly_weight(best_exp) if use_kelly else 1.0
            chosen.append((bk, best_tp, w))
        for bk, tpc, w in chosen:
            seg = (base_lab == bk)
            sel = np.zeros(n, dtype=bool); sel[start:end] = seg[start:end]
            entries |= sel; weights[sel] = w; tp_mult_arr[sel] = tpc
        log.append((start, [(b, tp, round(w, 2)) for b, tp, w in chosen]))
    return entries, weights, tp_mult_arr, log

eval_mask = np.zeros(n, dtype=bool); eval_mask[LOOKBACK:] = True

def evaluate(direction, entries, weights, tp_mult_arr, sl_s):
    """
    بک‌تست با TP متغیرِ هر کندل. چون run_backtest یک tp_series می‌گیرد و ما ضریبِ
    TP را per-signal داریم، tp_series را از ضریبِ هر کندل × ATR می‌سازیم.
    سپس pnl هر معامله در وزنِ حجمِ کندلِ سیگنالش ضرب می‌شود.
    """
    s = entries & eval_mask
    tp_series = np.where(tp_mult_arr > 0, tp_mult_arr * atrv, atrv)  # پیش‌فرض ایمن
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_s, tp_series=tp_series)
    if len(tr) == 0:
        return 0.0, 0, 0.0
    w = weights[tr['signal_bar'].values]; w[w == 0] = 1.0
    weighted = tr['pnl'].values * w
    wins = (tr['outcome'].values == 'win').sum()
    return weighted.sum(), len(tr), wins / len(tr) * 100

print("=== S65: Adaptive-TP Rolling Router (معیار: سودِ خالص) ===\n", flush=True)

def eval_curve(direction, entries, weights, tp_mult_arr, sl_s):
    s = entries & eval_mask
    tp_series = np.where(tp_mult_arr > 0, tp_mult_arr * atrv, atrv)
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_s, tp_series=tp_series)
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

def run_config(name, adaptive_tp, use_kelly, show_risk=False):
    eL, wL_, tpL_, _ = build_router('long', labL, slL, TP_CANDS_L, adaptive_tp, use_kelly)
    eS, wS_, tpS_, _ = build_router('short', labS, slS, TP_CANDS_S, adaptive_tp, use_kelly)
    pL_, nL_, wrL_ = evaluate('long', eL, wL_, tpL_, slL)
    pS_, nS_, wrS_ = evaluate('short', eS, wS_, tpS_, slS)
    tot = pL_ + pS_; nn = nL_ + nS_
    wr = (wrL_ * nL_ + wrS_ * nS_) / nn if nn else 0
    line = f"{name:44s} n={nn:5d}  WR={wr:5.1f}%  سودِخالص={tot:9.1f}$"
    if show_risk:
        curve = pd.concat([eval_curve('long', eL, wL_, tpL_, slL),
                           eval_curve('short', eS, wS_, tpS_, slS)])
        dd, sh = risk_stats(curve)
        line += f"  MaxDD={dd:8.1f}$  Sharpe={sh:.2f}  سود/|DD|={tot/abs(dd) if dd else 0:.2f}"
    print(line, flush=True)
    return tot

print(f"baseline S63 (TP ثابت، حجمِ ثابت) = {BASELINE_S63:.0f}$", flush=True)
print(f"baseline S64 (TP ثابت، حجمِ Kelly) = {BASELINE_S64:.0f}$\n", flush=True)

p_tponly = run_config('TP تطبیقی + حجمِ ثابت', True, False, show_risk=True)
p_full = run_config('★ S65: TP تطبیقی + حجمِ Kelly', True, True, show_risk=True)

print(f"\nاثرِ تنهای TP تطبیقی (بر S63): {p_tponly - BASELINE_S63:+.1f}$ "
      f"({(p_tponly/BASELINE_S63-1)*100:+.1f}%)", flush=True)
print(f"اثرِ ترکیبیِ S65 (بر S64): {p_full - BASELINE_S64:+.1f}$ "
      f"({(p_full/BASELINE_S64-1)*100:+.1f}%)", flush=True)
print(f"اثرِ کلِ S65 نسبت به پایهٔ S63: {p_full - BASELINE_S63:+.1f}$ "
      f"({(p_full/BASELINE_S63-1)*100:+.1f}%)", flush=True)
if p_full > BASELINE_S64:
    print("✅ TP تطبیقی یک اهرمِ مستقلِ اضافه بر Kelly است → سودِ خالصِ بیشتر.", flush=True)
else:
    print("△ TP تطبیقی بر Kelly چیزی اضافه نکرد (اهرم‌ها هم‌پوشان‌اند).", flush=True)
print("\nتمام.", flush=True)
