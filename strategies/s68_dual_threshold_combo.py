"""
S68 — ترکیبِ دو-آستانه‌ای (پاسخِ علمی به User Note 2: «آیا معاملاتِ بیشتر ⇒ سودِ خالصِ بیشتر؟»)
================================================================================
قانونِ شمارهٔ ۱ پروژه: هدف **فقط و فقط «سودِ خالصِ بیشتر»** است — نه Win-Rate.
WR صرفاً گزارشی است. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**

--------------------------------------------------------------------------------
انگیزه (User Note 2)
--------------------------------------------------------------------------------
کاربر پیشنهاد داد: «S66 و S67 و هر استراتژیِ خوبِ گذشته را ترکیب کنیم (S68)، شاید
تعدادِ معاملات و در نتیجه سودِ خالص بیشتر شود.»

تحلیلِ علمیِ پیش از کد (ثبت‌شده در گزارش):
  • S67 خودش حاصلِ ترکیبِ زنجیرهٔ برنده است (S61→S63→S64→S65→S66). پس «ترکیبِ
    S66+S67» بازتاب است، نه ترکیبِ نو.
  • منابعِ معاملاتیِ *متعامدِ* دیگر (S53 mean-reversion، S54/S55 multi-asset)
    همگی expectancy **منفی** داشتند (S53: PF=0.96). افزودنِ آن‌ها = تعدادِ معاملهٔ
    بیشتر ولی سودِ خالصِ **کمتر** — دقیقاً دامِ Win-Rate (قانونِ L3).

پس تنها ترکیبِ باقی‌مانده که می‌ارزد آزموده شود، ترکیب در **همان محورِ روندیِ سودده**
است: افزودنِ یک **لایهٔ دومِ سیگنال با آستانهٔ نرم‌ترِ proba** که فقط جایی فعال شود
که لایهٔ اصلی خالی است، و چون کم‌کیفیت‌تر است با **وزنِ کمتر** وارد شود.

فرضیهٔ آزمون‌پذیرِ S68:
  «سیگنال‌های با proba در بازهٔ [P_MIN2, P_MIN) که اکنون رد می‌شوند، اگر با وزنِ
   کاهش‌یافته اضافه شوند، آیا سودِ خالصِ روی سرمایه را بالا می‌برند یا (طبقِ L3)
   پایین می‌آورند؟»

هر دو نتیجه علمی ارزشمند است. معیارِ انتخاب: سودِ خالصِ دلاری روی سرمایهٔ اولیه.
--------------------------------------------------------------------------------
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
from tpsl_plan import build_plan
from capital_engine import run_capital_backtest, summary_line
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
ER_TREND_THR = 0.30
P_HI = 0.66
P_MIN = 0.58          # آستانهٔ لایهٔ اصلی (برندهٔ S67)
P_MIN2 = 0.52         # آستانهٔ نرمِ لایهٔ دوم (سیگنال‌هایی که S67 رد می‌کند)
LAYER2_WEIGHT = 0.5   # وزنِ کمترِ لایهٔ دوم (کیفیتِ پایین‌تر ⇒ ریسکِ کمتر)

CACHE = os.path.join(os.path.dirname(__file__), '..', 'results', '_s61_cache.npz')
z = np.load(CACHE, allow_pickle=True)
pL, pS = z['pL'], z['pS']
up_reg, down_reg = z['up_reg'], z['down_reg']
er = z['er']; atrv = z['atrv']

df = load_data('data/XAUUSD_M15.csv')
n = len(df)
trendy = np.nan_to_num(er >= ER_TREND_THR, nan=False).astype(bool)
eval_mask = np.zeros(n, dtype=bool); eval_mask[24000:] = True


def build_labels(direction, base):
    p = pL if direction == 'long' else pS
    ef = np.where(trendy, 'trend', 'chop')
    pw = np.where(p >= P_HI, 'hi', 'lo')
    lab = np.array([f'{a}_{b}' for a, b in zip(ef, pw)], dtype=object)
    lab[~base] = ''
    return lab


def get_trades(direction, plan, extra_weight=1.0):
    """معاملاتِ واقعیِ روتر را با سری‌های SL/TP برنامه اجرا می‌کند."""
    s = plan.entries & eval_mask
    sl_ser = plan.sl_series()
    tp_ser = plan.tp_series()
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_ser, tp_series=tp_ser)
    if len(tr) == 0:
        return tr, np.array([]), np.array([])
    sl_dist = plan.sl_dist_for_trades(tr)
    w = plan.weights[tr['signal_bar'].values] * extra_weight
    return tr, sl_dist, w


def build_stream(p_min, extra_weight=1.0, exclude_bars=None):
    """یک جریانِ کامل (Bull+Bear) با آستانهٔ proba داده‌شده می‌سازد.
    exclude_bars: مجموعهٔ signal_bar هایی که نباید تکرار شوند (تا لایهٔ دوم با اصلی هم‌پوشان نشود)."""
    baseL = up_reg & ~np.isnan(atrv) & (pL >= p_min)
    baseS = down_reg & ~np.isnan(atrv) & (pS >= p_min)
    if exclude_bars is not None:
        # لایهٔ دوم فقط جایی که لایهٔ اصلی سیگنال ندارد
        excl = np.zeros(n, dtype=bool)
        excl[list(exclude_bars)] = True
        baseL = baseL & ~excl
        baseS = baseS & ~excl
    labL = build_labels('long', baseL)
    labS = build_labels('short', baseS)
    planL = build_plan('long', labL, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)
    planS = build_plan('short', labS, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)
    trL, slL, wL = get_trades('long', planL, extra_weight)
    trS, slS, wS = get_trades('short', planS, extra_weight)
    all_tr = pd.concat([trL, trS], ignore_index=True)
    all_sl = np.concatenate([slL, slS]) if len(slL) or len(slS) else np.array([])
    all_w = np.concatenate([wL, wS]) if len(wL) or len(wS) else np.array([])
    # مرتب‌سازی بر اساسِ زمانِ خروج (موتورِ سرمایه به ترتیب حساس است)
    o = all_tr['exit_bar'].values.argsort()
    return all_tr.iloc[o].reset_index(drop=True), all_sl[o], all_w[o], planL, planS


def combine_and_sort(streams):
    trs = pd.concat([s[0] for s in streams], ignore_index=True)
    sls = np.concatenate([s[1] for s in streams]) if any(len(s[1]) for s in streams) else np.array([])
    ws  = np.concatenate([s[2] for s in streams]) if any(len(s[2]) for s in streams) else np.array([])
    order = trs['exit_bar'].values.argsort()
    return trs.iloc[order].reset_index(drop=True), sls[order], ws[order]


def evaluate(all_tr, all_sl, all_w, label):
    s, eq = run_capital_backtest(all_tr, all_sl, weights=all_w, initial_capital=10_000,
                                 risk_pct=1.0, commission_per_lot=7.0, compounding=True)
    sf, _ = run_capital_backtest(all_tr, all_sl, weights=all_w, initial_capital=10_000,
                                 risk_pct=1.0, commission_per_lot=7.0, compounding=False)
    print(f"\n[{label}]  n={len(all_tr)}", flush=True)
    print(summary_line("  compound(10k/1%)", s), flush=True)
    print(summary_line("  fixed-risk       ", sf), flush=True)
    return s, sf, eq


print("=== S68: ترکیبِ دو-آستانه‌ای (User Note 2) ===\n", flush=True)

# --- خطِ مبنا: لایهٔ اصلیِ S67 به‌تنهایی (P_MIN=0.58) ---
print("ساختِ لایهٔ اصلی (P_MIN=0.58 ، همان برندهٔ S67) ...", flush=True)
base_tr, base_sl, base_w, planL1, planS1 = build_stream(P_MIN, extra_weight=1.0)
main_bars = set(np.where(planL1.entries & eval_mask)[0].tolist()) | \
            set(np.where(planS1.entries & eval_mask)[0].tolist())
s67_c, s67_f, s67_eq = evaluate(base_tr, base_sl, base_w, "S67 baseline — فقط لایهٔ اصلی")

# --- لایهٔ دوم: سیگنال‌های نرم‌ترِ [0.52, 0.58) با وزنِ نصف، بدونِ هم‌پوشانی با اصلی ---
print("\nساختِ لایهٔ دوم (P_MIN2=0.52 ، وزنِ نصف ، بدونِ هم‌پوشانی) ...", flush=True)
l2_tr, l2_sl, l2_w, _, _ = build_stream(P_MIN2, extra_weight=LAYER2_WEIGHT, exclude_bars=main_bars)
# فقط سیگنال‌هایی که proba زیرِ آستانهٔ اصلی داشتند (یعنی «نو» نسبت به S67)
print(f"  معاملاتِ نوِ لایهٔ دوم: {len(l2_tr)}", flush=True)

# --- S68 = لایهٔ اصلی + لایهٔ دوم ---
c68_tr, c68_sl, c68_w = combine_and_sort([(base_tr, base_sl, base_w),
                                          (l2_tr, l2_sl, l2_w)])
s68_c, s68_f, s68_eq = evaluate(c68_tr, c68_sl, c68_w, "S68 — لایهٔ اصلی + لایهٔ دوم")

# ---------------------------------------------------------------------------
# داوری
# ---------------------------------------------------------------------------
print("\n" + "=" * 100, flush=True)
print("داوریِ فرضیهٔ User Note 2 (آیا معاملاتِ بیشتر ⇒ سودِ خالصِ بیشتر؟):", flush=True)
print(f"  S67 (پایه):  n={s67_f['n_trades']:4d}  netP(fixed)={s67_f['net_profit']:+9.0f}$  "
      f"maxDD={s67_f['max_dd_pct']:.1f}%  PF={s67_f['profit_factor']:.2f}", flush=True)
print(f"  S68 (ترکیب): n={s68_f['n_trades']:4d}  netP(fixed)={s68_f['net_profit']:+9.0f}$  "
      f"maxDD={s68_f['max_dd_pct']:.1f}%  PF={s68_f['profit_factor']:.2f}", flush=True)
delta = s68_f['net_profit'] - s67_f['net_profit']
dpct = 100 * delta / abs(s67_f['net_profit']) if s67_f['net_profit'] else 0
print(f"\n  Δ سودِ خالص (ریسکِ ثابت): {delta:+.0f}$  ({dpct:+.1f}%)", flush=True)
if delta > 0:
    print("  ✅ فرضیه تأیید شد: لایهٔ دوم سودِ خالص را بالا برد → S68 برندهٔ جدید.", flush=True)
    np.save(os.path.join(os.path.dirname(__file__), '..', 'results', '_s68_equity.npy'), s68_eq)
else:
    print("  ❌ فرضیه رد شد: معاملاتِ بیشتر سودِ خالص را کم/خنثی کرد (تأییدِ مجددِ L3).", flush=True)
    print("     ⇒ S67 برندهٔ رسمی می‌مانَد. کیفیت مهم‌تر از کمیتِ معامله است.", flush=True)

# اعتبارسنجیِ دو-نیمهٔ S68
print("\nآزمونِ دو-نیمهٔ S68 (ریسکِ ثابت):", flush=True)
mid = c68_tr['exit_bar'].median()
for name, msk in [("نیمهٔ اول", c68_tr['exit_bar'].values <= mid),
                  ("نیمهٔ دوم", c68_tr['exit_bar'].values > mid)]:
    h = c68_tr[msk].reset_index(drop=True)
    s, _ = run_capital_backtest(h, c68_sl[msk], weights=c68_w[msk], initial_capital=10_000,
                                risk_pct=1.0, commission_per_lot=7.0, compounding=False)
    print(f"  {name}: n={s['n_trades']:4d}  netP={s['net_profit']:+9.0f}$  "
          f"({s['return_pct']:+6.1f}%)  maxDD={s['max_dd_pct']:.1f}%  PF={s['profit_factor']:.2f}", flush=True)

print("\nتمام.", flush=True)
