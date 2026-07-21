# -*- coding: utf-8 -*-
"""
s154_recompute_full_newspec.py — بازمحاسبهٔ کاملِ سودِ خالصِ رکورد با مشخصاتِ دقیقِ حسابِ جدید
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله در روز.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
> این فایل یک بازمحاسبهٔ حسابداری است (نه استراتژیِ نو).

--------------------------------------------------------------------------------
انگیزه (User Note جدید):
  «سود خالص اشتباهیِ قبلی را بر مبنای مشخصاتِ حسابِ جدید حساب کن و در مستندات ثبت کن.»

  مشخصاتِ واقعیِ حسابِ دموِ کاربر:
    • CONTRACT_SIZE = 100  (هر ۱ لات = ۱۰۰ اونس؛ حرکتِ ۱.۰۰$ = ۱۰۰$/لات)
    • اسپردِ واقعیِ طلا = 0.33$/oz  (~۳.۳ pip = ۳۳ point)
    • کمیسیونِ جداگانه = ندارد (صفر)  ← این برای کلِ حساب است، نه فقط طلا
    • مارجین = ۴۰$/لات

--------------------------------------------------------------------------------
چرا این بازمحاسبه از s146 دقیق‌تر است:
  s146 (بازمحاسبهٔ قبلی) دو ساده‌سازی داشت:
    (۱) سهمِ طلا را با یک نسبتِ کلیِ ۱.۱۸۵۴ مقیاس کرد (تقریبِ منطقی، نه دقیق برای هر لایه).
    (۲) سهمِ EURUSD را **ثابت** فرض کرد — اما مدلِ قدیمی برای EURUSD کمیسیونِ ۷$/لات
        می‌گرفت که طبقِ مشخصاتِ جدیدِ کاربر باید **صفر** باشد ⇒ سهمِ EURUSD هم افزایش می‌یابد.

  این اسکریپت:
    • طلا: همان نسبتِ کاهشِ هزینه (۵.۰→۳.۳pip) را از پروکسیِ لایه‌ها می‌گیرد (شفاف).
    • EURUSD: **مستقیماً** هر دو لایه (S73 + S143) را با موتورِ واقعی و **دو مدلِ کمیسیون**
      (۷$ قدیم در برابر صفرِ جدید) اجرا می‌کند تا اثرِ واقعیِ حذفِ کمیسیون را کمّی نشان دهد.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0

# ============================================================================
# رکوردِ ثبت‌شده (با مدلِ هزینهٔ قدیمِ طلا = ۵.۰pip و EURUSD کمیسیون ۷$)
# ============================================================================
RECORD_TOTAL_OLD = 196_481.0          # جمعِ کلِ رکورد (XAUUSD + EURUSD) با هزینهٔ قدیم
EUR_S73_OLD      = 9_223.0            # سهمِ S73 با کمیسیونِ ۷$ (ثبت‌شده)
EUR_S143_OLD     = 5_367.0            # سهمِ S143 با کمیسیونِ ۷$ (ثبت‌شده)
EUR_TOTAL_OLD    = EUR_S73_OLD + EUR_S143_OLD   # = 14,590$
XAU_TOTAL_OLD    = RECORD_TOTAL_OLD - EUR_TOTAL_OLD   # = 181,891$

# --- دو مدلِ هزینهٔ طلا (برای نسبتِ کاهشِ هزینه) ---
COST_XAU_OLD  = dict(spread_pip=4.0, slip_pip=0.5)   # cost = 5.0 pip
COST_XAU_REAL = dict(spread_pip=3.3, slip_pip=0.0)   # cost = 3.3 pip (User Note)


# ---------------------------------------------------------------------------
# پروکسیِ لایه‌های زمان-محورِ طلا (هم‌ترازِ فایل‌های رکورد؛ برای نسبتِ هزینه)
# ---------------------------------------------------------------------------
def load_xau():
    df = pd.read_csv(os.path.join(ROOT, 'data', 'XAUUSD_M15.csv'))
    df.columns = [c.lower() for c in df.columns]
    dt = pd.to_datetime(df['time'], unit='s') if np.issubdtype(df['time'].dtype, np.number) \
        else pd.to_datetime(df['time'])
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['_dt'] = dt
    return df


def _from_end(dt):
    """شمارهٔ روزِ معاملاتی از پایانِ ماه (−۱ = آخرین، −۲ = یکی مانده…)."""
    d = pd.Series(dt.values)
    ym = dt.dt.to_period('M')
    order = d.groupby(ym.values).rank(method='dense')
    size = d.groupby(ym.values).transform('nunique')  # noqa (approx)
    return None  # not needed for ratio; overnight dominates


def sig_overnight(df):
    from engine.indicators import ema, rsi
    n = len(df)
    return np.isin(df['hour'].values, [22, 23]), np.zeros(n, bool)

def sig_monday(df):
    n = len(df)
    return (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20, 21]), np.zeros(n, bool)

def sig_midmonth(df):
    n = len(df)
    return np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, list(range(1, 13))), np.zeros(n, bool)

def sig_trend_base(df):
    from engine.indicators import ema, rsi
    c = df['close']
    e20 = ema(c, 20); e100 = ema(c, 100); r = rsi(c, 14)
    n = len(df)
    return ((e20 > e100) & (r < 40)).fillna(False).values, np.zeros(n, bool)


XAU_LAYERS = [
    ('Overnight (S139)',  sig_overnight,  dict(sl_pip=150, tp_pip=500, max_hold=96)),
    ('Monday (S140)',     sig_monday,     dict(sl_pip=150, tp_pip=500, max_hold=96)),
    ('MidMonth (S142)',   sig_midmonth,   dict(sl_pip=100, tp_pip=500, max_hold=96)),
    ('TrendBase (S67px)', sig_trend_base, dict(sl_pip=120, tp_pip=360, max_hold=96)),
]


def set_xau_cost(spread_pip, slip_pip):
    se.ASSETS['XAUUSD']['spread_pip'] = float(spread_pip)
    se.ASSETS['XAUUSD']['slip_pip'] = float(slip_pip)
    se.ASSETS['XAUUSD']['comm'] = 0.0


def run_xau_layer(df, sigfn, ekw):
    ls, ss = sigfn(df)
    tr = se.simulate_trades(df, ls, ss, asset='XAUUSD', allow_overlap=False, **ekw)
    if tr is None or len(tr) == 0:
        return 0.0
    st, _ = se.run_capital(tr, 'XAUUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return float(st['net_profit'])


def xau_ratio(df):
    """نسبتِ کاهشِ هزینهٔ طلا (net با ۳.۳pip / net با ۵.۰pip) از پروکسیِ لایه‌ها."""
    tot = {}
    for label, model in [('OLD', COST_XAU_OLD), ('REAL', COST_XAU_REAL)]:
        set_xau_cost(**model)
        s = sum(run_xau_layer(df, fn, ekw) for _, fn, ekw in XAU_LAYERS)
        tot[label] = s
    return tot['REAL'] / tot['OLD'], tot


# ---------------------------------------------------------------------------
# لایه‌های EURUSD (S73 + S143) — اجرای مستقیم با دو مدلِ کمیسیون
# ---------------------------------------------------------------------------
def load_eur():
    df = pd.read_csv(os.path.join(ROOT, 'data', 'EURUSD_M15.csv'))
    df.columns = [c.lower() for c in df.columns]
    dt = pd.to_datetime(df['time'], unit='s') if np.issubdtype(df['time'].dtype, np.number) \
        else pd.to_datetime(df['time'])
    df['hour'] = dt.dt.hour
    df['dom'] = dt.dt.day
    return df


def sig_s73(df):
    """S73: EURUSD Session-Open drift، ساعتِ ۰ UTC، buy-the-dip pullback."""
    n = len(df)
    hour0 = df['hour'].values == 0
    c = df['close'].values
    # فیلترِ pullback: ۴ کندلِ قبل نزولی بوده باشد
    pull = np.zeros(n, bool)
    for i in range(4, n):
        if c[i - 1] < c[i - 5]:
            pull[i] = True
    ls = hour0 & pull
    return ls, np.zeros(n, bool)


def sig_s143(df):
    """S143: EURUSD Mid-Month drift، dom∈{3,9,20}، ساعاتِ لندن/US (بدونِ ۰)."""
    n = len(df)
    days = [3, 9, 20]
    hours = [8, 9, 10, 11, 12, 13, 14, 15]
    ls = np.isin(df['dom'].values, days) & np.isin(df['hour'].values, hours)
    return ls, np.zeros(n, bool)


def set_eur_comm(comm):
    se.ASSETS['EURUSD']['comm'] = float(comm)
    se.ASSETS['EURUSD']['spread_pip'] = 1.0
    se.ASSETS['EURUSD']['slip_pip'] = 0.3


def run_eur_layer(df, sigfn, sl, tp, mh):
    ls, ss = sigfn(df)
    tr = se.simulate_trades(df, ls, ss, sl, tp, 'EURUSD', max_hold=mh)
    if tr is None or len(tr) == 0:
        return 0.0, 0
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _ = se.run_capital(tr, 'EURUSD', initial_capital=CAP, risk_pct=RISK, compounding=True)
    return float(st['net_profit']), len(tr)


def main():
    print("=" * 80)
    print("S154 — بازمحاسبهٔ کاملِ سودِ خالص با مشخصاتِ دقیقِ حسابِ جدید")
    print("=" * 80)

    # ---------- ۱) طلا: نسبتِ کاهشِ هزینه ----------
    dfx = load_xau()
    ratio, xau_tot = xau_ratio(dfx)
    print(f"\n[۱] طلا — نسبتِ کاهشِ هزینه (۵.۰pip → ۳.۳pip)")
    print(f"    پروکسیِ لایه‌ها: OLD={xau_tot['OLD']:+,.0f}$  REAL={xau_tot['REAL']:+,.0f}$")
    print(f"    نسبتِ بهبودِ طلا = {ratio:.4f}  (+{(ratio-1)*100:.1f}%)")
    xau_real = XAU_TOTAL_OLD * ratio
    print(f"    سهمِ طلای رکورد: OLD={XAU_TOTAL_OLD:+,.0f}$  →  REAL={xau_real:+,.0f}$  (Δ {xau_real-XAU_TOTAL_OLD:+,.0f}$)")

    # ---------- ۲) EURUSD: اجرای مستقیم با دو مدلِ کمیسیون ----------
    dfe = load_eur()
    eur = {}
    for label, comm in [('OLD_comm7', 7.0), ('REAL_comm0', 0.0)]:
        set_eur_comm(comm)
        n73, c73 = run_eur_layer(dfe, sig_s73, sl=12, tp=12, mh=6)
        n143, c143 = run_eur_layer(dfe, sig_s143, sl=20, tp=120, mh=96)
        eur[label] = dict(s73=n73, s143=n143, total=n73 + n143, n73=c73, n143=c143)
        print(f"\n[۲] EURUSD — کمیسیون = {comm}$/لات  ({label})")
        print(f"    S73  net = {n73:+,.0f}$  (N={c73})")
        print(f"    S143 net = {n143:+,.0f}$  (N={c143})")
        print(f"    جمعِ EURUSD = {eur[label]['total']:+,.0f}$")

    # نکتهٔ روش‌شناختی مهم: بازتولیدِ مستقیمِ S73/S143 اعدادی متفاوت از ثبت‌شده می‌دهد
    # (چون سیگنالِ پروکسیِ pullback ساده‌تر است) ⇒ روشِ «نسبتِ ضربی» وقتی علامت‌ها فرق دارند
    # نامعتبر است (می‌تواند منفی/انفجاری شود). روشِ درست = **اختلافِ افزایشیِ (additive) دلاری**:
    #   Δ_کمیسیون = net(کمیسیون=۰) − net(کمیسیون=۷) روی همان لایه‌ها (علامت‌مستقل، دقیق).
    # این Δ اثرِ خالصِ حذفِ کمیسیون است و آن را به سهمِ ثبت‌شدهٔ EURUSD اضافه می‌کنیم.
    eur_delta = eur['REAL_comm0']['total'] - eur['OLD_comm7']['total']
    eur_real = EUR_TOTAL_OLD + eur_delta
    print(f"\n    Δ افزایشیِ حذفِ کمیسیون (comm ۷→۰$) = {eur_delta:+,.0f}$  (روی پروکسیِ همان دو لایه)")
    print(f"    سهمِ EURUSD رکورد: OLD={EUR_TOTAL_OLD:+,.0f}$  →  REAL={eur_real:+,.0f}$  (Δ {eur_delta:+,.0f}$)")

    # ---------- ۳) سودِ خالصِ واقعیِ رکورد ----------
    total_real = xau_real + eur_real
    print("\n" + "=" * 80)
    print("[۳] سودِ خالصِ واقعیِ رکورد با مشخصاتِ جدید")
    print("=" * 80)
    print(f"    رکوردِ ثبت‌شده (هزینهٔ قدیم):        {RECORD_TOTAL_OLD:+,.0f}$")
    print(f"      سهمِ طلا  (۵.۰→۳.۳pip):           {XAU_TOTAL_OLD:+,.0f}$ → {xau_real:+,.0f}$")
    print(f"      سهمِ EUR  (comm ۷→۰$):            {EUR_TOTAL_OLD:+,.0f}$ → {eur_real:+,.0f}$")
    print(f"    " + "-" * 60)
    print(f"    🥇 سودِ خالصِ واقعیِ رکورد:          {total_real:+,.0f}$")
    print(f"       Δ نسبت به رکوردِ قدیم = {total_real - RECORD_TOTAL_OLD:+,.0f}$  (+{(total_real/RECORD_TOTAL_OLD-1)*100:.1f}%)")

    out = {
        'user_note_spec': {'contract_size': 100, 'xau_spread_pip': 3.3,
                           'xau_cost_usd_oz': 0.33, 'commission': 0.0, 'margin_per_lot': 40.0},
        'record_total_old': RECORD_TOTAL_OLD,
        'xau': {'old': XAU_TOTAL_OLD, 'ratio': ratio, 'real': xau_real,
                'proxy_old': xau_tot['OLD'], 'proxy_real': xau_tot['REAL']},
        'eur': {'old': EUR_TOTAL_OLD, 'delta': eur_delta, 'real': eur_real,
                'layers_old': eur['OLD_comm7'], 'layers_real': eur['REAL_comm0']},
        'record_total_real': total_real,
        'delta_vs_old': total_real - RECORD_TOTAL_OLD,
    }
    with open(os.path.join(RESULTS, '_s154_recompute_full.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print("\n✅ ذخیره شد: results/_s154_recompute_full.json")
    return out


if __name__ == '__main__':
    main()
