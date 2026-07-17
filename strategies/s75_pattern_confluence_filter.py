"""
S75 — Visual-Pattern Confluence Filter روی موتورِ برندهٔ S67 (User Note: تکنیک بصری)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی در هر سند و کد): هدفِ پروژه **فقط و فقط «سودِ
خالصِ بیشتر»** است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است؛ تعدادِ معامله و
Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.**
تعریفِ فعلیِ «سودِ خالص» = مجموعِ سودِ خالصِ دو دارایی: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
انگیزه (User Note — صحبتِ تریدر «با چشمم شکلِ بازار را می‌فهمم»):
  اکتشافِ ما (explore_candle_patterns / explore_geometric_patterns / 
  explore_pattern_exit_design) نشان داد:
    ❌ الگوهای بصری به‌تنهایی (به‌عنوانِ ماشهٔ ورودِ مستقل) سودده نیستند: لبهٔ
       خامِ آن‌ها فقط چند bps است و با اسپرد + TP/SL از بین می‌رود (S74 ruin شد).
       این تأییدِ دیگری بر شکستِ Price Action خالص (S10–S12) است.
    ✅ اما جهتِ لبه واقعی و معنادار است: bear_engulf (t=-3.6)، double-top (t=-2.8)،
       pin_bear (t تا -4.1 در H1)، shooting_star در TREND (t=-2.15). یعنی این
       الگوها «اطلاعاتِ جهتِ نزولی» حمل می‌کنند.

فرضیهٔ S75 (به‌جای ماشهٔ مستقل، فیلترِ کیفیت/confluence):
  الگوها را نه به‌عنوانِ ماشه، بلکه به‌عنوانِ **لایهٔ تأییدِ کیفیت** روی معاملاتِ
  موتورِ برندهٔ S67 اعمال می‌کنیم — دقیقاً همان کاری که تریدرِ باتجربه می‌کند:
  «سیگنالِ سیستم را می‌گیرم، اما اگر چشمم الگوی متضاد ببیند، وارد نمی‌شوم.»
    • Long های S67: اگر در پنجرهٔ اخیر یک الگوی نزولیِ قوی (double-top تازه یا
      bear_engulf/shooting_star بالای EMA) ظاهر شده باشد ⇒ **veto** (ورود نکن).
    • Short های S67: اگر الگوی نزولیِ هم‌جهت وجود داشته باشد ⇒ نگه‌دار (تأیید مثبت)؛
      در غیرِ این صورت هم مجاز (فیلتر فقط veto ی Long را هدف می‌گیرد، چون
      لبهٔ نزولیِ الگوها قوی‌ترین سیگنالِ ماست).

  اگر این فیلتر سودِ خالص را از +37,156$ بالاتر ببرد ⇒ موتورِ طلا بهبود یافت و
  رکورد جابه‌جا می‌شود. اگر نه ⇒ درسِ منفیِ صادقانه ثبت می‌شود (S67 دست‌نخورده می‌ماند).

اعتبار: بدونِ نشتِ آینده (الگوها فقط از کندلِ گذشته)، همان موتورِ سرمایه‌محورِ S67،
ریسکِ ثابت ۱٪، اسپرد ۰.۲$، کمیسیون ۷$/لات، آزمونِ دو-نیمه.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data, run_backtest
from tpsl_plan import build_plan
from capital_engine import run_capital_backtest
import warnings; warnings.filterwarnings('ignore')

HZ = 48; SPREAD = 0.20
ER_TREND_THR = 0.30
P_HI = 0.66; P_MIN = 0.58
PATTERN_LOOKBACK = 6          # پنجرهٔ اخیر برای بررسیِ وجودِ الگوی نزولی


# ---------- بازتولیدِ دقیقِ اسکلتِ S67 (ورود/رژیم برنده) ----------
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


# ---------- کشفِ الگوهای نزولیِ اثبات‌شده (forward-safe) ----------
def bearish_pattern_mask():
    """هر کندلی که یک الگوی نزولیِ قوی روی آن یا در گذشتهٔ نزدیک تأیید شده."""
    o = df['open'].values; h = df['high'].values
    l = df['low'].values; c = df['close'].values
    body = c - o; body_abs = np.abs(body)
    up_wick = h - np.maximum(o, c); lo_wick = np.minimum(o, c) - l
    prev_body = np.zeros(n); prev_body[1:] = body[:-1]
    prev_o = np.zeros(n); prev_o[1:] = o[:-1]
    prev_c = np.zeros(n); prev_c[1:] = c[:-1]
    ema50 = df['close'].ewm(span=50, adjust=False).mean().values
    adx_val, _, _ = _adx(df, 14)

    bear_engulf = (prev_body > 0) & (body < 0) & (c <= prev_o) & (o >= prev_c)
    shooting = (up_wick >= 2.0 * body_abs) & (lo_wick <= 0.5 * body_abs) & (body_abs > 0) & (adx_val >= 25)
    # Double-Top تازه (سقفِ دوقلو در پنجرهٔ اخیر)
    dt = _double_top_mask()
    raw = bear_engulf | shooting | dt
    # گسترشِ سیگنال به پنجرهٔ اخیر (وجودِ الگو در LOOKBACK کندلِ گذشته)
    recent = np.zeros(n, dtype=bool)
    idx = np.where(raw)[0]
    for i in idx:
        recent[i:min(i + PATTERN_LOOKBACK, n)] = True
    return recent


def _adx(dfx, period):
    import indicators as ind
    return ind.adx(dfx, period)


def _double_top_mask():
    h = df['high'].values; l = df['low'].values
    left = right = 4
    ph = []
    for i in range(left, n - right):
        wh = h[i-left:i+right+1]
        if h[i] == wh.max() and (wh == h[i]).sum() == 1:
            ph.append((i, h[i], i + right))
    mask = np.zeros(n, dtype=bool)
    for a in range(len(ph) - 1):
        i1, p1, _ = ph[a]; i2, p2, cb2 = ph[a+1]
        if not (8 <= i2 - i1 <= 60) or cb2 >= n:
            continue
        if abs(p1 - p2) <= 0.5 * (atrv[i2] if not np.isnan(atrv[i2]) else 0):
            mask[cb2] = True
    return mask


def run_variant(veto_long_on_bear, tag):
    labL = build_labels('long', baseL)
    labS = build_labels('short', baseS)
    eval_mask = np.zeros(n, dtype=bool); eval_mask[24000:] = True

    planL = build_plan('long', labL, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)
    planS = build_plan('short', labS, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)

    entriesL = planL.entries & eval_mask
    entriesS = planS.entries & eval_mask

    if veto_long_on_bear:
        bear = bearish_pattern_mask()
        entriesL = entriesL & ~bear     # veto: Long را در حضورِ الگوی نزولی حذف کن

    def trades(direction, plan, ent):
        st, tr = run_backtest(df, ent, None, None, direction, spread=SPREAD, max_hold=HZ,
                              sl_series=plan.sl_series(), tp_series=plan.tp_series())
        if len(tr) == 0:
            return tr, np.array([])
        return tr, plan.sl_dist_for_trades(tr)

    trL, slL = trades('long', planL, entriesL)
    trS, slS = trades('short', planS, entriesS)
    all_tr = pd.concat([trL, trS], ignore_index=True).sort_values('exit_bar').reset_index(drop=True)
    sl_all = np.concatenate([slL, slS]) if len(slS) else slL
    # بازآرایی sl مطابقِ ترتیبِ exit_bar
    tmp = pd.concat([trL.assign(_sl=slL), trS.assign(_sl=slS)], ignore_index=True)
    tmp = tmp.sort_values('exit_bar').reset_index(drop=True)
    sl_all = tmp['_sl'].values

    cap, eq = run_capital_backtest(all_tr, sl_all, initial_capital=10_000.0,
                                   risk_pct=1.0, commission_per_lot=7.0, compounding=False)
    mid = n // 2
    halves = []
    for m in [(tmp['signal_bar'] < mid), (tmp['signal_bar'] >= mid)]:
        hh = tmp[m]
        if len(hh):
            hc, _ = run_capital_backtest(hh.reset_index(drop=True), hh['_sl'].values,
                                         initial_capital=10_000.0, risk_pct=1.0,
                                         commission_per_lot=7.0, compounding=False)
            halves.append(hc['net_profit'])
        else:
            halves.append(0)
    print(f"\n  [{tag}]  n={cap['n_trades']} (Long={len(trL)}, Short={len(trS)})")
    print(f"    netP={cap['net_profit']:+.0f}$ ({cap['return_pct']:+.1f}%) WR={cap['win_rate']:.1f}% "
          f"PF={cap['profit_factor']:.2f} maxDD={cap['max_dd_pct']:.1f}% Sharpe={cap['sharpe']:.2f}")
    print(f"    نیمه‌ها: H1={halves[0]:+.0f}$  H2={halves[1]:+.0f}$  "
          f"both-positive={'✓' if halves[0]>0 and halves[1]>0 else '✗'}")
    return cap['net_profit'], halves


if __name__ == '__main__':
    print("=" * 78)
    print("  S75 — Pattern Confluence Filter روی موتورِ S67 (XAUUSD)")
    print("=" * 78)
    base_np, base_h = run_variant(False, "S67 پایه (بدونِ فیلتر) — مرجع")
    filt_np, filt_h = run_variant(True, "S75 (+ veto ی Long روی الگوی نزولی)")
    print("\n" + "=" * 78)
    delta = filt_np - base_np
    print(f"  Δ سودِ خالصِ طلا = {delta:+.0f}$  "
          f"({'بهبود ✅' if delta > 0 else 'بدترشدن ❌'})")
    print(f"  مرجعِ رکورد (S67): +37,156$ | S73 (EURUSD): +7,302$ | کلِ فعلی: +44,458$")
    print("=" * 78)
