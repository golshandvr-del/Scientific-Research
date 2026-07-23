# -*- coding: utf-8 -*-
"""
s187_m5_timeframe_audit.py — ممیزیِ تک‌تکِ لایه‌های استراتژی روی تایم‌فریمِ M5 (پاسخِ User Note)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف = «سودِ خالصِ بیشتر» (XAUUSD+EURUSD)، نه WR.
> WR فقط کفِ پذیرش است (≥۴۰٪ برای هر لایهٔ فعال).

--------------------------------------------------------------------------------
انگیزه (User Note این نشست — صریح):
  «ما استراتژی‌ها را فقط روی یک تایم‌فریم (عمدتاً M15) تست کرده‌ایم. شاید همان لایه‌ها
   روی تایم‌فریم‌های دیگر — که داده‌شان هم موجود است — بازدهیِ خوبی داشته باشند. وظیفهٔ
   تو: تحقیقِ تک‌تکِ لایه‌های استراتژی‌های موجود و حتی سوخته/ردشده، روی تایم‌فریمِ M5.»

روش‌شناسیِ سیب‌به‌سیب (اجتنابِ از دامِ مقایسهٔ ناعادلانه):
  ۱) داده M5 هر دو دارایی فقط از ~۲۰۲۳-۰۹ موجود است (نه ۴ سال). پس هر لایه را روی
     **بازهٔ زمانیِ مشترکِ دقیقاً یکسان** (شروعِ داده M5 → پایان) روی *هر دو* تایم‌فریمِ
     M15 و M5 اجرا می‌کنیم. اختلافِ نتیجه در این صورت *فقط* به تایم‌فریم مربوط است،
     نه به بازهٔ متفاوت.
  ۲) منطقِ سیگنالِ لایه‌های زمان-محور (ساعت/روز/روزِ ماه) تایم‌فریم-اگنوستیک است، اما
     `max_hold` بر حسبِ *تعداد کندل* است. mh روی M15 معادلِ mh×3 روی M5 است (تا مدتِ
     نگهداریِ ساعتیِ یکسان حفظ شود). SL/TP بر حسبِ pip ثابت می‌مانند (مستقل از تایم‌فریم).
  ۳) مشخصاتِ هزینه (اسپرد/کمیسیون/…) مستقل از تایم‌فریم است ⇒ همان مشخصاتِ واقعیِ حساب.

خروجی: جدولِ مقایسه‌ایِ M15-vs-M5 برای هر لایه + JSON در results/_s187_m5_audit.json
       + تصمیمِ «آیا M5 لبهٔ نو/بهبود می‌دهد؟».
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0

# ---- مشخصاتِ واقعیِ حساب (single source of truth) ----
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)
# نسخهٔ M5 (همان pip/contract/هزینه؛ فقط فایلِ داده فرق دارد)
se.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD_M5'] = dict(file='data/EURUSD_M5.csv', pip=0.0001, contract=100_000.0,
                              pip_value=10.0, spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def clip_window(df, start, end):
    out = df[(df['dt'] >= start) & (df['dt'] <= end)].reset_index(drop=True)
    return out


def add_calendar(df):
    dt = df['dt']
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    def rel(r):
        return int(r['from_end']) if r['from_end'] >= -2 else int(r['rank_in_month'])
    days['tom_rel'] = days.apply(rel, axis=1)
    df['tom_rel'] = df['date'].map(dict(zip(days['date'], days['tom_rel']))).astype(int)
    return df


def stats_capital(tr, asset):
    """اجرای لایهٔ سرمایه و برگرداندنِ net/n/wins/losses/wr/pf با تعریفِ صحیحِ صحیح/غلط."""
    base_asset = asset.replace('_M5', '')  # لایهٔ سرمایه از pip_value مشترک استفاده می‌کند
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP,
                                        risk_pct=RISK, compounding=True)
    net_usd = pt['net_usd'].values if len(pt) else np.array([])
    wins = int((net_usd > 0).sum()); losses = int((net_usd <= 0).sum())
    gp = float(net_usd[net_usd > 0].sum()) if len(net_usd) else 0.0
    gl = float(-net_usd[net_usd <= 0].sum()) if len(net_usd) else 0.0
    n = len(net_usd)
    return dict(net=float(st['net_profit']), n=n, wins=wins, losses=losses,
                wr=(wins / n * 100.0 if n else 0.0),
                pf=(gp / gl if gl > 0 else float('inf')))


def run_layer(df, long_sig, short_sig, sl, tp, mh, asset, be=None, trail=None):
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                            max_hold=mh, allow_overlap=False,
                            be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    return tr


# ============================================================================
# تعریفِ لایه‌ها به‌صورتِ توابعِ سیگنال‌ساز (تایم‌فریم-اگنوستیک)
#   هر تابع: (df_با_تقویم) -> (long_sig, short_sig, sl, tp, mh15, be, trail, asset_base)
#   mh15 = max_hold روی M15 ؛ برای M5 در اجرا ×3 می‌شود.
# ============================================================================
def sig_S139(df):  # Overnight: hour∈{22,23}
    ls = np.isin(df['hour'].values, [22, 23])
    return ls, np.zeros(len(df), bool), 150, 500, 96, None, None

def sig_S140(df):  # Monday: dow=0 & hour∈{18..21}
    ls = (df['dow'].values == 0) & np.isin(df['hour'].values, [18, 19, 20, 21])
    return ls, np.zeros(len(df), bool), 100, 300, 96, None, None

def sig_S141(df):  # Turn-of-Month: tom_rel=1 & hour∈{7..12}
    ls = (df['tom_rel'].values == 1) & np.isin(df['hour'].values, list(range(7, 13)))
    return ls, np.zeros(len(df), bool), 100, 700, 96, None, None

def sig_S142(df):  # Mid-Month: dom∈{10,13,20} & hour∈{1..12}
    ls = np.isin(df['dom'].values, [10, 13, 20]) & np.isin(df['hour'].values, list(range(1, 13)))
    return ls, np.zeros(len(df), bool), 100, 500, 96, None, None

def sig_S144(df):  # End-of-Month Pre-End: from_end∈{-6,-7,-8} & hour∈{19..23}
    ls = np.isin(df['from_end'].values, [-6, -7, -8]) & np.isin(df['hour'].values, [19, 20, 21, 22, 23])
    return ls, np.zeros(len(df), bool), 150, 300, 96, None, None

def sig_SHORTMA(df):  # SHORT-MA-Confluence: cross below mid(EMA50,EMA100,SMA200)
    c = df['close']
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    price = c.values
    prev_above = np.r_[False, price[:-1] > mid[:-1]]
    sh = prev_above & (price < mid)
    return np.zeros(len(df), bool), sh, 40, 200, 12, 8, 8

def sig_S81(df):  # Swing-Pullback (EMA20>EMA100 & RSI14<35) — سوخته روی M15/M30
    c = df['close']
    e20 = ind.ema(c, 20).values; e100 = ind.ema(c, 100).values; r14 = ind.rsi(c, 14).values
    ls = (e20 > e100) & (r14 < 35)
    ls = np.nan_to_num(ls, nan=False).astype(bool)
    return ls, np.zeros(len(df), bool), 120, 1200, 144, None, None

def sig_S73_eur(df):  # EURUSD Session-Open: hour=0 + pullback
    hour0 = df['hour'].values == 0
    cc = df['close'].values; n = len(df)
    pull = np.zeros(n, bool); pull[5:] = cc[4:-1] < cc[0:-5]
    ls = hour0 & pull
    return ls, np.zeros(n, bool), 12, 12, 6, None, None

def sig_S143_eur(df):  # EURUSD Mid-Month: dom∈{3,9,20} & hour∈{1..5,11..15}
    ls = np.isin(df['dom'].values, [3, 9, 20]) & np.isin(df['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15])
    return ls, np.zeros(len(df), bool), 20, 120, 96, None, None


XAU_LAYERS = [
    ('S139 Overnight',        'Long',  sig_S139),
    ('S140 Monday',           'Long',  sig_S140),
    ('S141 Turn-of-Month',    'Long',  sig_S141),
    ('S142 Mid-Month',        'Long',  sig_S142),
    ('S144 End-of-Month',     'Long',  sig_S144),
    ('SHORT-MA-Confluence',   'Short', sig_SHORTMA),
    ('S81 Swing-Pullback(REJ)', 'Long', sig_S81),
]
EUR_LAYERS = [
    ('S73 Session-Open',      'Long',  sig_S73_eur),
    ('S143 Mid-Month',        'Long',  sig_S143_eur),
]


def audit_asset(base_asset, layers):
    tf15 = base_asset + '_M15'
    tf5 = base_asset + '_M5'
    df15 = add_calendar(load(tf15))
    df5 = add_calendar(load(tf5))
    # بازهٔ مشترک = شروعِ دیرترِ داده تا پایانِ زودترِ داده
    start = max(df15['dt'].iloc[0], df5['dt'].iloc[0])
    end = min(df15['dt'].iloc[-1], df5['dt'].iloc[-1])
    df15 = clip_window(df15, start, end); df5 = clip_window(df5, start, end)
    df15 = assign_from_end(add_calendar(df15)); df5 = assign_from_end(add_calendar(df5))
    print(f"\n{'='*100}\n{base_asset}: بازهٔ مشترکِ سیب‌به‌سیب {start.date()} → {end.date()}"
          f"  (M15={len(df15):,} کندل، M5={len(df5):,} کندل)\n{'='*100}", flush=True)
    out = []
    for name, direction, sigfn in layers:
        ls15, sh15, sl, tp, mh15, be, trail = sigfn(df15)
        ls5, sh5, _, _, _, _, _ = sigfn(df5)
        mh5 = mh15 * 3  # هم‌ترازیِ مدتِ نگهداریِ ساعتی
        tr15 = run_layer(df15, ls15, sh15, sl, tp, mh15, tf15, be, trail)
        tr5 = run_layer(df5, ls5, sh5, sl, tp, mh5, tf5, be, trail)
        s15 = stats_capital(tr15, tf15)
        s5 = stats_capital(tr5, tf5)
        rec = dict(layer=name, direction=direction, asset=base_asset,
                   sl=sl, tp=tp, mh15=mh15, mh5=mh5, m15=s15, m5=s5)
        out.append(rec)
        pf15 = s15['pf'] if s15['pf'] != float('inf') else 99.99
        pf5 = s5['pf'] if s5['pf'] != float('inf') else 99.99
        print(f"{name[:26]:26s} {direction:6s} | "
              f"M15 net={s15['net']:+9,.0f} WR={s15['wr']:4.1f}% n={s15['n']:4d} PF={pf15:.2f} | "
              f"M5 net={s5['net']:+9,.0f} WR={s5['wr']:4.1f}% n={s5['n']:4d} PF={pf5:.2f}", flush=True)
    return out, str(start.date()), str(end.date())


def main():
    print("=" * 100)
    print("S187 — ممیزیِ تک‌تکِ لایه‌ها روی M5 (پاسخِ User Note). مقایسهٔ سیب‌به‌سیب M15↔M5.")
    print("قانونِ #۱: هدف = سودِ خالص (XAU+EUR)؛ WR≥40 فقط کفِ پذیرش.")
    print("=" * 100, flush=True)

    xau, xs, xe = audit_asset('XAUUSD', XAU_LAYERS)
    eur, es, ee = audit_asset('EURUSD', EUR_LAYERS)

    # ---- تحلیلِ تصمیم: کدام لایه روی M5 (با WR≥40) net بالاتری از M15 دارد؟ ----
    print("\n" + "=" * 100)
    print("تحلیلِ تصمیم — کدام لایه روی M5 لبهٔ بهتر/جدید می‌دهد؟ (کفِ WR≥40)")
    print("=" * 100)
    winners = []
    for rec in xau + eur:
        m15, m5 = rec['m15'], rec['m5']
        m5_valid = m5['wr'] >= 40.0 and m5['n'] >= 30 and m5['net'] > 0
        m15_valid = m15['wr'] >= 40.0 and m15['net'] > 0
        verdict = ''
        if m5_valid and (not m15_valid or m5['net'] > m15['net']):
            verdict = '⭐ M5 بهتر/جدید'
            winners.append(rec)
        elif m5_valid:
            verdict = 'M5 معتبر ولی ≤ M15'
        elif m5['wr'] < 40.0:
            verdict = f"M5 رد: WR={m5['wr']:.1f}%<40"
        else:
            verdict = 'M5 رد: net≤0 یا n<30'
        print(f"  {rec['layer'][:26]:26s} → {verdict}")

    print("\n" + "-" * 100)
    if winners:
        print(f"✅ {len(winners)} لایه روی M5 نامزدِ بهبود/لبهٔ نو هستند (نیاز به گیتِ ضدِ overfit):")
        for w in winners:
            print(f"   • {w['layer']} ({w['direction']}): M5 net={w['m5']['net']:+,.0f} "
                  f"WR={w['m5']['wr']:.1f}% vs M15 net={w['m15']['net']:+,.0f}")
    else:
        print("❌ هیچ لایه‌ای روی M5 لبهٔ بهتر از M15 با WR≥40 نداد (نتیجهٔ آموزنده).")

    out = dict(note='S187 M5 timeframe audit — User Note',
               spec=dict(xau_spread_pip=3.3, eur_spread_pip=1.0, comm=0.0, contract_xau=100),
               methodology='apple-to-apple same window; mh_M5 = mh_M15 * 3',
               xau_window=[xs, xe], eur_window=[es, ee],
               xau_layers=xau, eur_layers=eur,
               n_winners=len(winners), winners=[w['layer'] for w in winners])
    with open(os.path.join(RESULTS, '_s187_m5_audit.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s187_m5_audit.json")
    return out


if __name__ == '__main__':
    main()
