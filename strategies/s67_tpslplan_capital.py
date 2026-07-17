"""
S67 — TP-Plan + SL-Plan روی موتورِ سرمایه‌محور (پاسخِ کاملِ User Note)
================================================================================
قانونِ شمارهٔ ۱ پروژه: هدف **فقط و فقط «سودِ خالصِ بیشتر»** است — نه Win-Rate.
WR صرفاً گزارشی است. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**

این استراتژی دو کارِ User Note را هم‌زمان حل می‌کند:
  ۱) نکتهٔ ۱ (سرمایهٔ اولیه): سودِ خالص را به یک **سرمایهٔ اولیهٔ واقعی** گره می‌زند
     با موتورِ `capital_engine.py` (ریسکِ درصدی + لاتِ واقعیِ XAUUSD + کمیسیون).
  ۲) نکتهٔ ۲ (tpplan/slplan): از ماژولِ مستقلِ `tpsl_plan.py` استفاده می‌کند که همان
     منطقِ SL/TP رژیم-آگاهِ برندهٔ ۷۳۵۰$ (S66 Adaptive-SL) را بازتولید می‌کند.

اسکلتِ ورود/رژیم دقیقاً همان برندهٔ پروژه (S63–S66) است؛ پس این یک استراتژیِ نو
نیست، بلکه **حسابداریِ واقع‌بینانهٔ برندهٔ موجود + استخراجِ tpplan/slplan** است.
معیار انتخاب: سودِ خالصِ دلاری روی سرمایهٔ اولیه.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
from tpsl_plan import build_plan, BUCKETS
from capital_engine import run_capital_backtest, summary_line, DEFAULT_CAPITAL
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
ER_TREND_THR = 0.30
P_HI = 0.66; P_MIN = 0.58

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


labL = build_labels('long', baseL)
labS = build_labels('short', baseS)
eval_mask = np.zeros(n, dtype=bool); eval_mask[24000:] = True

print("=== S67: TP-Plan + SL-Plan روی موتورِ سرمایه‌محور ===\n", flush=True)
print("ساختِ TP/SL-Plan رژیم-آگاه (Bull) ...", flush=True)
planL = build_plan('long', labL, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)
print("ساختِ TP/SL-Plan رژیم-آگاه (Bear) ...", flush=True)
planS = build_plan('short', labS, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)


def get_trades(direction, plan):
    """معاملاتِ واقعیِ روتر را با سری‌های SL/TP برنامه اجرا می‌کند."""
    s = plan.entries & eval_mask
    sl_ser = plan.sl_series()
    tp_ser = plan.tp_series()
    st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                          sl_series=sl_ser, tp_series=tp_ser)
    if len(tr) == 0:
        return tr, np.array([]), np.array([])
    sl_dist = plan.sl_dist_for_trades(tr)
    w = plan.weights[tr['signal_bar'].values]
    return tr, sl_dist, w


trL, slL, wL = get_trades('long', planL)
trS, slS, wS = get_trades('short', planS)

# ترکیبِ معاملاتِ Bull + Bear و مرتب‌سازی بر اساسِ زمانِ خروج
all_tr = pd.concat([trL, trS], ignore_index=True)
all_sl = np.concatenate([slL, slS]) if len(slL) or len(slS) else np.array([])
all_w = np.concatenate([wL, wS]) if len(wL) or len(wS) else np.array([])
order = all_tr['exit_bar'].values.argsort()
all_tr = all_tr.iloc[order].reset_index(drop=True)
all_sl = all_sl[order]
all_w = all_w[order]

print(f"\nمجموعِ معاملات: {len(all_tr)}  (Bull={len(trL)}, Bear={len(trS)})\n", flush=True)

# ---------------------------------------------------------------------------
# سناریوهای سرمایه: چند سرمایهٔ اولیه و ریسکِ درصدی — پاسخِ عددیِ User Note #1
# ---------------------------------------------------------------------------
print("=" * 100, flush=True)
print("جدولِ سرمایه‌محور — «با X دلار سرمایه و ریسکِ Y٪، سودِ خالص چقدر می‌شود»", flush=True)
print("=" * 100, flush=True)

results = {}
for cap in [1_000, 5_000, 10_000, 50_000]:
    for risk in [0.5, 1.0, 2.0]:
        s, eq = run_capital_backtest(all_tr, all_sl, weights=all_w,
                                     initial_capital=cap, risk_pct=risk,
                                     commission_per_lot=7.0, compounding=True)
        key = (cap, risk)
        results[key] = (s, eq)
        tag = "★" if (cap == 10_000 and risk == 1.0) else " "
        print(f"{tag} cap={cap:6d}$ risk={risk:.1f}%  → equity={s['final_equity']:11.0f}$  "
              f"netP={s['net_profit']:+10.0f}$ ({s['return_pct']:+7.1f}%)  "
              f"maxDD={s['max_dd_pct']:5.1f}%  PF={s['profit_factor']:.2f}  "
              f"WR={s['win_rate']:.1f}%  avgLot={s['avg_lot']:.2f}  ruin={s['ruined']}", flush=True)

print("\n" + "=" * 100, flush=True)
# سناریوی مرجعِ استاندارد پروژه
s_ref, eq_ref = results[(10_000, 1.0)]
print("سناریوی مرجعِ استاندارد (سرمایهٔ ۱۰٬۰۰۰$ ، ریسکِ ۱٪ در هر معامله ، کامپاند):", flush=True)
print(summary_line("  S67 reference", s_ref), flush=True)

# مقایسه با ریسکِ ثابت-دلاری (بدون کامپاند) برای شفافیت
s_fixed, _ = run_capital_backtest(all_tr, all_sl, weights=all_w,
                                  initial_capital=10_000, risk_pct=1.0,
                                  commission_per_lot=7.0, compounding=False)
print(summary_line("  S67 fixed-risk (no compound)", s_fixed), flush=True)

# ذخیرهٔ منحنیِ equity مرجع برای گزارش
np.save(os.path.join(os.path.dirname(__file__), '..', 'results', '_s67_equity.npy'), eq_ref)

# خلاصهٔ نگاشتِ عددیِ سودِ خام (اونس-محور) به سود سرمایه‌محور
raw_net = all_tr['pnl'].sum()   # مجموعِ حرکتِ خام (همان مقیاسِ قدیمِ ۶۸۰۰/۷۳۵۰$)
print(f"\nمرجعِ سودِ خامِ اونس-محور (مقیاسِ قدیم، ۰.۰۱ لاتِ ثابت): {raw_net:.0f}$", flush=True)
print(f"⇒ همین معاملات با موتورِ سرمایه (۱۰k$/۱٪): سودِ خالص = {s_ref['net_profit']:.0f}$ "
      f"({s_ref['return_pct']:+.1f}% بازده روی سرمایه)", flush=True)
print("\nتمام.", flush=True)

# ---------------------------------------------------------------------------
# اعتبارسنجیِ دو-نیمه (walk-forward) روی موتورِ سرمایه — پایداری
# ---------------------------------------------------------------------------
print("\n" + "=" * 100, flush=True)
print("آزمونِ پایداریِ دو-نیمه (ریسکِ ثابت ۱٪ ، سرمایهٔ ۱۰k$ ، بدون کامپاند برای مقایسهٔ منصفانه):", flush=True)
mid = all_tr['exit_bar'].median()
h1 = all_tr[all_tr['exit_bar'] <= mid].reset_index(drop=True)
h2 = all_tr[all_tr['exit_bar'] > mid].reset_index(drop=True)
sl1 = all_sl[all_tr['exit_bar'].values <= mid]
sl2 = all_sl[all_tr['exit_bar'].values > mid]
w1 = all_w[all_tr['exit_bar'].values <= mid]
w2 = all_w[all_tr['exit_bar'].values > mid]
for name, h, sl, w in [("نیمهٔ اول", h1, sl1, w1), ("نیمهٔ دوم", h2, sl2, w2)]:
    s, _ = run_capital_backtest(h, sl, weights=w, initial_capital=10_000,
                                risk_pct=1.0, commission_per_lot=7.0, compounding=False)
    print(f"  {name}: n={s['n_trades']:4d}  netP={s['net_profit']:+9.0f}$  "
          f"({s['return_pct']:+6.1f}%)  maxDD={s['max_dd_pct']:.1f}%  PF={s['profit_factor']:.2f}", flush=True)
print("تمام (اعتبارسنجی).", flush=True)
