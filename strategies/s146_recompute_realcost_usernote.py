"""
s146_recompute_realcost_usernote.py — بازمحاسبهٔ سودِ خالصِ رکورد با مشخصاتِ دقیقِ حسابِ کاربر
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله در روز.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
> این فایل یک بازمحاسبهٔ حسابداری است (نه استراتژیِ نو).

--------------------------------------------------------------------------------
انگیزه (User Note جدید — گامِ اول: «ابتدا سود خالص رو با مشخصاتِ حساب دقیق که تازگی
دادم حساب کن»):

  مشخصاتِ واقعیِ حسابِ دمو که کاربر داد:
    • CONTRACT_SIZE = 100  (هر ۱ لات = ۱۰۰ اونس؛ حرکتِ ۱.۰۰$ = ۱۰۰$/لات)
    • اسپردِ واقعیِ طلا = 0.33$/oz  (~۳.۳ pip = ۳۳ point)
    • کمیسیونِ جداگانه = ندارد (صفر)
    • مارجین = ۴۰$/لات

  مدلِ هزینهٔ فعلیِ پروژه (engine/scalp_engine.py، جدولِ ASSETS):
    • XAUUSD: spread_pip=4.0, slip_pip=0.5  ⇒  cost = spread + 2×slip = 5.0 pip = 0.50$/oz
    یعنی مدلِ فعلی **۵.۰ pip** هزینه می‌گیرد در حالی که واقعیتِ حسابِ کاربر **۳.۳ pip** است.
    ⇒ مدلِ فعلی ~۱.۵۲× بدبینانه‌تر از واقعیت است.

  نتیجهٔ مورد انتظار: چون هزینهٔ واقعی کمتر است، سودِ خالصِ واقعیِ حساب باید **بیشتر**
  از رکوردِ ثبت‌شده (+۱۹۶٬۴۸۱$) باشد. این اسکریپت آن را کمّی اثبات می‌کند.

--------------------------------------------------------------------------------
روش:
  همهٔ لایه‌های زمان-محورِ طلا (S139..S144) + لایهٔ پایهٔ روندِ طلا (proxy S67) با
  دو مدلِ هزینه بازتولید می‌شوند:
    (A) مدلِ قدیمِ رکورد: cost_pip = 5.0  (spread=4.0, slip=0.5)
    (B) مدلِ واقعیِ کاربر: cost_pip = 3.3  (spread=3.3, slip=0.0 — کمیسیون صفر)
  اختلافِ سودِ خالص گزارش می‌شود. لایه‌های غیر-طلاییِ رکورد (Squeeze، Short-MA، EURUSD)
  که سهمِ ثابت دارند، با نسبتِ کاهشِ هزینه تخمینِ محافظه‌کارانه زده می‌شوند.
================================================================================
"""
import os, sys, json, copy
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
CAP, RISK = 10000.0, 1.0

# --- دو مدلِ هزینهٔ طلا ---
COST_OLD = dict(spread_pip=4.0, slip_pip=0.5)   # رکورد فعلی: cost = 5.0 pip
COST_REAL = dict(spread_pip=3.3, slip_pip=0.0)  # User Note جدید: 3.3 pip، کمیسیون صفر


def set_xau_cost(spread_pip, slip_pip):
    """مدلِ هزینهٔ طلا را در جدولِ ASSETS به‌صورتِ سراسری تنظیم می‌کند."""
    se.ASSETS['XAUUSD']['spread_pip'] = float(spread_pip)
    se.ASSETS['XAUUSD']['slip_pip'] = float(slip_pip)
    se.ASSETS['XAUUSD']['comm'] = 0.0


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank'] - days['cnt'] - 1
    m = dict(zip(days['date'], days['from_end']))
    df = df.copy(); df['from_end'] = df['date'].map(m).astype(int)
    return df


def assign_tom_rel(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank'] - days['cnt'] - 1
    days['tom_rel'] = days.apply(lambda r: int(r['from_end']) if r['from_end'] >= -2 else int(r['rank']), axis=1)
    m = dict(zip(days['date'], days['tom_rel']))
    df = df.copy(); df['tom_rel'] = df['date'].map(m).astype(int)
    return df


def ema(x, span):
    return pd.Series(x).ewm(span=span, adjust=False).mean().values

def rsi(x, period=14):
    d = np.diff(x, prepend=x[0])
    up = np.where(d > 0, d, 0.0); dn = np.where(d < 0, -d, 0.0)
    ru = pd.Series(up).ewm(alpha=1/period, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/period, adjust=False).mean().values
    rs = ru / (rd + 1e-12)
    return 100 - 100/(1+rs)


# ---- سازندهٔ سیگنالِ هر لایه (long-only، هم‌ترازِ رکورد) ----
def sig_overnight(df):
    n = len(df); return np.isin(df['hour'].values, [22, 23]), np.zeros(n, bool)

def sig_monday(df):
    n = len(df); return ((df['dow'].values == 0) & np.isin(df['hour'].values, [18,19,20,21])), np.zeros(n, bool)

def sig_tom(df):
    d = assign_tom_rel(df); n = len(df)
    return ((d['tom_rel'].values == 1) & np.isin(d['hour'].values, [7,8,9,10,11,12])), np.zeros(n, bool)

def sig_midmonth(df):
    n = len(df)
    return (np.isin(df['dom'].values, [10,13,20]) & np.isin(df['hour'].values, list(range(1,13)))), np.zeros(n, bool)

def sig_eom(df):
    d = assign_from_end(df); n = len(df)
    return (np.isin(d['from_end'].values, [-6,-7,-8]) & np.isin(d['hour'].values, [19,20,21,22,23])), np.zeros(n, bool)

def sig_trend_base(df):
    """proxy لایهٔ پایهٔ روندِ طلا (S67-مانند): EMA20>EMA100 روند صعودی، ورودِ pullback RSI<40."""
    c = df['close'].values
    e20, e100 = ema(c, 20), ema(c, 100); r = rsi(c, 14)
    n = len(df)
    long_sig = (e20 > e100) & (r < 40)
    return long_sig, np.zeros(n, bool)


# پارامترهای خروجِ هر لایه (SL/TP/max_hold به pip)، هم‌ترازِ فایل‌های رکورد
LAYERS = [
    ('Overnight (S139)',  sig_overnight, dict(sl_pip=150, tp_pip=500, max_hold=96)),
    ('Monday (S140)',     sig_monday,    dict(sl_pip=150, tp_pip=500, max_hold=96)),
    ('TurnOfMonth (S141)',sig_tom,       dict(sl_pip=100, tp_pip=700, max_hold=96)),
    ('MidMonth (S142)',   sig_midmonth,  dict(sl_pip=100, tp_pip=500, max_hold=96)),
    ('EndOfMonth (S144)', sig_eom,       dict(sl_pip=150, tp_pip=300, max_hold=96)),
    ('TrendBase (S67px)', sig_trend_base,dict(sl_pip=120, tp_pip=360, max_hold=96)),
]


def run_layer(df, sigfn, exit_kw):
    long_sig, short_sig = sigfn(df)
    tr = se.simulate_trades(df, long_sig, short_sig, asset='XAUUSD',
                            allow_overlap=False, **exit_kw)
    if tr is None or len(tr) == 0:
        return 0.0, 0
    stats, eq = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return float(stats['net_profit']), len(tr)


def main():
    df = load()
    print("=" * 78)
    print("بازمحاسبهٔ سودِ خالص با مشخصاتِ دقیقِ حسابِ کاربر (User Note)")
    print("=" * 78)

    results = {}
    for label, model in [('OLD_5.0pip', COST_OLD), ('REAL_3.3pip', COST_REAL)]:
        set_xau_cost(**model)
        cp = se.ASSETS['XAUUSD']['spread_pip'] + 2*se.ASSETS['XAUUSD']['slip_pip']
        print(f"\n### مدلِ هزینه: {label}  (cost_pip = {cp:.1f} = {cp*0.10:.3f}$/oz) ###")
        total = 0.0
        results[label] = {}
        for name, sigfn, ekw in LAYERS:
            net, ntr = run_layer(df, sigfn, ekw)
            results[label][name] = net
            total += net
            print(f"  {name:22s}: net = {net:+12,.0f}$   (N={ntr})")
        results[label]['_TOTAL_XAU_layers'] = total
        print(f"  {'مجموعِ لایه‌های طلا':22s}: {total:+12,.0f}$")

    # اختلاف
    print("\n" + "=" * 78)
    print("اختلافِ سودِ خالصِ طلا: واقعی (۳.۳pip) منهای قدیم (۵.۰pip)")
    print("=" * 78)
    diff_total = 0.0
    for name, _, _ in LAYERS:
        d = results['REAL_3.3pip'][name] - results['OLD_5.0pip'][name]
        diff_total += d
        print(f"  {name:22s}: Δ = {d:+12,.0f}$")
    print(f"  {'مجموعِ Δ طلا':22s}: {diff_total:+12,.0f}$")

    # نسبتِ بهبود برای تعمیم به کلِ رکورد
    old_t = results['OLD_5.0pip']['_TOTAL_XAU_layers']
    real_t = results['REAL_3.3pip']['_TOTAL_XAU_layers']
    ratio = real_t / old_t if old_t != 0 else 1.0
    print(f"\n  نسبتِ بهبود (طلا واقعی/قدیم) = {ratio:.4f}  ⇒  +{(ratio-1)*100:.1f}% روی لایه‌های طلا")

    out = {
        'user_note_spec': {'contract_size': 100, 'xau_spread_pip': 3.3,
                           'xau_cost_usd_oz': 0.33, 'commission': 0.0, 'margin_per_lot': 40.0},
        'old_cost_pip': 5.0, 'real_cost_pip': 3.3,
        'layers_old': results['OLD_5.0pip'],
        'layers_real': results['REAL_3.3pip'],
        'xau_layer_improvement_ratio': ratio,
    }
    with open(os.path.join(RESULTS, '_s146_recompute_realcost.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\n✅ ذخیره شد: results/_s146_recompute_realcost.json")
    return out


if __name__ == '__main__':
    main()
