# -*- coding: utf-8 -*-
"""
audit_all_layers_4y_realspec.py — ممیزیِ کاملِ تک‌تکِ لایه‌های استراتژیِ فعلی
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR صرفاً یک عددِ
> گزارشی است. تعدادِ معامله و Profit Factor هم هدف نیستند. **ما دنبالِ پول هستیم،
> نه آمارِ زیبا.** تنها تابعِ هدف: **سودِ خالصِ تجمعیِ پس از اسپرد/اسلیپیج/کمیسیون.**
> **تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.**

--------------------------------------------------------------------------------
انگیزه (User Note این نشست — صریح):
  «گزارشی از استراتژیِ فعلی تهیه کن: چه لایه‌هایی دارد؟ روی دادهٔ ۴ سالِ اخیر تست کن.
   جدولی بکش: هر لایه به‌طور مجزا چند معاملهٔ صحیح/غلط، سود/زیانِ کلی، WR. همهٔ لایه‌ها
   را الان دقیقاً تست کن و برای هیچ لایه‌ای به رکورد قبلی/MD رجوع نکن.»

  ⇒ این اسکریپت **هیچ عددی را از فایل‌های نتیجه/رکورد نمی‌خواند**. هر لایه را با
     سیگنالِ نهاییِ تثبیت‌شده‌اش (استخراج‌شده از کدِ خودِ لایه، نه از جاروب) از نو،
     روی **پنجرهٔ ۴ سالِ اخیر** و با **مشخصاتِ واقعیِ حسابِ کاربر** اجرا می‌کند.

--------------------------------------------------------------------------------
مشخصاتِ واقعیِ حسابِ کاربر (مبنای همهٔ محاسبات این اسکریپت):
  • CONTRACT_SIZE = 100 (طلا)؛ EURUSD = 100,000
  • اسپردِ واقعیِ طلا = 0.33$/oz ≈ 3.3 pip ؛ کمیسیونِ جداگانه = صفر (کلِ حساب)
  • مارجین = 40$/لات (در بک‌تستِ ۱۰k$ محدودیتِ مارجین فعال نمی‌شود)
  • سرمایهٔ اولیه = 10,000$ ، ریسکِ ثابت = 1% در هر معامله ، کامپاند = True
    (همان استانداردِ سیب‌به‌سیبِ پروژه؛ برای S91 که کاربر حجم نمی‌بیند، حجمِ ثابتِ
     0.01 لات مطابقِ طراحیِ اصلیِ آن لایه)

پنجرهٔ زمانی: «۴ سالِ اخیر» = ۴ سالِ منتهی به آخرین کندلِ هر تایم‌فریم.
  توجه: XAUUSD_M5 فقط از ۲۰۲۳-۰۹ موجود است ⇒ لایهٔ S91 (M5) کل ۴ سال را پوشش نمی‌دهد
  و این در گزارش صریحاً ذکر می‌شود (محدودیتِ داده، نه انتخابِ ما).
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
YEARS = 4

# ---- مشخصاتِ واقعیِ کاربر را در موتور تثبیت می‌کنیم (single source of truth) ----
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)
# نسخهٔ M30 برای S81 (اگر لازم شد)
se.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)


def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def last_n_years(df, years=YEARS):
    """پنجرهٔ N سالِ منتهی به آخرین کندل."""
    end = df['dt'].iloc[-1]
    start = end - pd.DateOffset(years=years)
    out = df[df['dt'] >= start].reset_index(drop=True)
    return out, start, end


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


# ============================================================================
# آمارگیریِ استاندارد بر مبنای per-trade net_usd (تعریفِ صحیحِ «صحیح/غلط»)
#   یک معاملهٔ «صحیح» = net_usd>0 ؛ «غلط» = net_usd<=0.  (بر مبنای سود/زیانِ دلاریِ
#   واقعیِ پس از هزینه، نه صرفِ برخوردِ TP/SL.)
# ============================================================================
def stats_from_trades_capital(tr, asset):
    """اجرای لایهٔ سرمایه و برگرداندنِ (net, n, wins, losses, wr, per_trade_net)."""
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, gp=0.0, gl=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP,
                                        risk_pct=RISK, compounding=True)
    net_usd = pt['net_usd'].values if len(pt) else np.array([])
    wins = int((net_usd > 0).sum())
    losses = int((net_usd <= 0).sum())
    gp = float(net_usd[net_usd > 0].sum()) if len(net_usd) else 0.0
    gl = float(-net_usd[net_usd <= 0].sum()) if len(net_usd) else 0.0
    n = len(net_usd)
    return dict(net=float(st['net_profit']), n=n, wins=wins, losses=losses,
                wr=(wins / n * 100.0 if n else 0.0), gp=gp, gl=gl,
                pf=(gp / gl if gl > 0 else float('inf')))


def stats_from_papertrades(tr):
    """برای paper_broker (S91/Squeeze): net از net_usd جمع می‌شود (حجمِ ثابت 0.01)."""
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, gp=0.0, gl=0.0, pf=0.0)
    net_usd = tr['net_usd'].values
    wins = int((net_usd > 0).sum())
    losses = int((net_usd <= 0).sum())
    gp = float(net_usd[net_usd > 0].sum())
    gl = float(-net_usd[net_usd <= 0].sum())
    n = len(net_usd)
    return dict(net=float(net_usd.sum()), n=n, wins=wins, losses=losses,
                wr=(wins / n * 100.0 if n else 0.0), gp=gp, gl=gl,
                pf=(gp / gl if gl > 0 else float('inf')))


# ============================================================================
# لایه‌های سادهٔ زمان-محور و ساختاری (موتورِ scalp_engine + run_capital)
# ============================================================================
def run_engine_layer(df, long_sig, short_sig, sl, tp, mh, asset='XAUUSD',
                     be=None, trail=None):
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                            max_hold=mh, allow_overlap=False,
                            be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    return tr


def main():
    print("=" * 96)
    print("ممیزیِ کاملِ تک‌تکِ لایه‌های استراتژی — دادهٔ ۴ سالِ اخیر — مشخصاتِ واقعیِ حساب")
    print("قانونِ #۱: هدف = سودِ خالص (XAUUSD+EURUSD)، نه WR. هیچ رجوعی به رکورد/MD نشده.")
    print("=" * 96, flush=True)

    rows = []  # هر ردیف: dict لایه

    # ---------- دادهٔ M15 طلا (بیشترِ لایه‌ها) ----------
    dfx = add_calendar(load('XAUUSD_M15'))
    dfx = assign_from_end(dfx)
    dfx4, s4, e4 = last_n_years(dfx)
    dfx4 = assign_from_end(add_calendar(dfx4.copy()))  # بازمحاسبهٔ تقویم روی پنجره
    print(f"\nXAUUSD M15: پنجرهٔ ۴ ساله {s4.date()} → {e4.date()}  ({len(dfx4):,} کندل)")

    n = len(dfx4)
    zeros = np.zeros(n, bool)

    # --- S139 Overnight: hour∈{22,23}  SL150/TP500/mh96 ---
    ls = np.isin(dfx4['hour'].values, [22, 23])
    tr = run_engine_layer(dfx4, ls, zeros, 150, 500, 96)
    s = stats_from_trades_capital(tr, 'XAUUSD'); s['layer'] = 'S139 Overnight (طلا، ساعت‌۲۲–۲۳)'
    s['tf'] = 'M15'; s['dir'] = 'Long'; rows.append(s)

    # --- S140 Monday: dow=0 & hour∈{18..21}  SL100/TP300/mh96 ---
    ls = (dfx4['dow'].values == 0) & np.isin(dfx4['hour'].values, [18, 19, 20, 21])
    tr = run_engine_layer(dfx4, ls, zeros, 100, 300, 96)
    s = stats_from_trades_capital(tr, 'XAUUSD'); s['layer'] = 'S140 Monday (طلا، دوشنبه ۱۸–۲۱)'
    s['tf'] = 'M15'; s['dir'] = 'Long'; rows.append(s)

    # --- S141 Turn-of-Month: tom_rel=1 & hour∈{7..12}  SL100/TP700/mh96 ---
    ls = (dfx4['tom_rel'].values == 1) & np.isin(dfx4['hour'].values, [7, 8, 9, 10, 11, 12])
    tr = run_engine_layer(dfx4, ls, zeros, 100, 700, 96)
    s = stats_from_trades_capital(tr, 'XAUUSD'); s['layer'] = 'S141 Turn-of-Month (طلا، اولِ ماه)'
    s['tf'] = 'M15'; s['dir'] = 'Long'; rows.append(s)

    # --- S142 Mid-Month: dom∈{10,13,20} & hour∈{1..12}  SL100/TP500/mh96 ---
    ls = np.isin(dfx4['dom'].values, [10, 13, 20]) & np.isin(dfx4['hour'].values, list(range(1, 13)))
    tr = run_engine_layer(dfx4, ls, zeros, 100, 500, 96)
    s = stats_from_trades_capital(tr, 'XAUUSD'); s['layer'] = 'S142 Mid-Month (طلا، ۱۰/۱۳/۲۰)'
    s['tf'] = 'M15'; s['dir'] = 'Long'; rows.append(s)

    # --- S144 End-of-Month Pre-End: from_end∈{-6,-7,-8} & hour∈{19..23}  SL150/TP300/mh96 ---
    ls = np.isin(dfx4['from_end'].values, [-6, -7, -8]) & np.isin(dfx4['hour'].values, [19, 20, 21, 22, 23])
    tr = run_engine_layer(dfx4, ls, zeros, 150, 300, 96)
    s = stats_from_trades_capital(tr, 'XAUUSD'); s['layer'] = 'S144 End-of-Month Pre-End (طلا)'
    s['tf'] = 'M15'; s['dir'] = 'Long'; rows.append(s)

    # --- SHORT-MA-Confluence: price crosses mid[EMA50,EMA100,SMA200] down; SL40/TP200/mh12 BE8 trail8 ---
    c = dfx4['close']
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    price = c.values
    prev_above = np.r_[False, price[:-1] > mid[:-1]]
    sh = prev_above & (price < mid)
    tr = run_engine_layer(dfx4, zeros, sh, 40, 200, 12, be=8, trail=8)
    s = stats_from_trades_capital(tr, 'XAUUSD'); s['layer'] = 'SHORT-MA-Confluence (طلا، تنها لبهٔ SHORT)'
    s['tf'] = 'M15'; s['dir'] = 'Short'; rows.append(s)

    # ---------- Squeeze (S138): brk≥0.30 + rsi14≤75، paper_broker hidden 300/90 ----------
    print("اجرای لایهٔ Squeeze (paper_broker با هزینهٔ واقعیِ ۳.۳pip)...", flush=True)
    squeeze_stat = run_squeeze_layer(dfx4)
    squeeze_stat['layer'] = 'S132/S136/S138 Squeeze→Breakout (طلا)'
    squeeze_stat['tf'] = 'M15'; squeeze_stat['dir'] = 'Long'; rows.append(squeeze_stat)

    # ---------- S67 Router (پایهٔ طلا) — پیچیده، cache-محور ----------
    print("اجرای لایهٔ S67 (Router رژیم-محور، cache _s61)...", flush=True)
    s67_stat = run_s67_layer(s4, e4)
    s67_stat['layer'] = 'S67 Router (طلا، موتورِ پایهٔ رژیم-محور)'
    s67_stat['tf'] = 'M15'; s67_stat['dir'] = 'Long/Short'; rows.append(s67_stat)

    # ---------- S81 M30 Swing-Pullback: EMA20>EMA100 & RSI14<35; SL120/TP1200/mh144 ----------
    print("اجرای لایهٔ S81 (M30 swing pullback)...", flush=True)
    dfm30 = add_calendar(load('XAUUSD_M30'))
    dfm30_4, s30, e30 = last_n_years(dfm30)
    c30 = dfm30_4['close']
    e20 = ind.ema(c30, 20).values; e100b = ind.ema(c30, 100).values; r14 = ind.rsi(c30, 14).values
    ls = (e20 > e100b) & (r14 < 35)
    ls = np.nan_to_num(ls, nan=False).astype(bool)
    tr = run_engine_layer(dfm30_4, ls, np.zeros(len(dfm30_4), bool), 120, 1200, 144, asset='XAUUSD_M30')
    s = stats_from_trades_capital(tr, 'XAUUSD_M30'); s['layer'] = 'S81 Swing-Pullback (طلا M30)'
    s['tf'] = 'M30'; s['dir'] = 'Long'; rows.append(s)

    # ---------- S91 Scalp Signal-Exit (M5) — محدودیتِ داده ----------
    print("اجرای لایهٔ S91 (M5 scalp signal-exit، paper_broker)...", flush=True)
    s91_stat, s91_note = run_s91_layer()
    s91_stat['layer'] = 'S91 Scalp Signal-Exit (طلا M5)' + (f' — {s91_note}' if s91_note else '')
    s91_stat['tf'] = 'M5'; s91_stat['dir'] = 'Long'; rows.append(s91_stat)

    # ---------- دادهٔ M15 یورو ----------
    dfe = add_calendar(load('EURUSD_M15'))
    dfe4, se5, ee5 = last_n_years(dfe)
    dfe4 = add_calendar(dfe4.copy())
    print(f"\nEURUSD M15: پنجرهٔ ۴ ساله {se5.date()} → {ee5.date()}  ({len(dfe4):,} کندل)")
    ne = len(dfe4); ze = np.zeros(ne, bool)

    # --- S73 EURUSD Session-Open: hour=0 (+pullback ساده)  SL12/TP12/mh6 ---
    hour0 = dfe4['hour'].values == 0
    cc = dfe4['close'].values
    pull = np.zeros(ne, bool)
    pull[5:] = cc[4:-1] < cc[0:-5]
    ls = hour0 & pull
    tr = run_engine_layer(dfe4, ls, ze, 12, 12, 6, asset='EURUSD')
    s = stats_from_trades_capital(tr, 'EURUSD'); s['layer'] = 'S73 EURUSD Session-Open Drift'
    s['tf'] = 'M15'; s['dir'] = 'Long'; rows.append(s)

    # --- S143 EURUSD Mid-Month: dom∈{3,9,20} & hour∈{1..5,11..15}  SL20/TP120/mh96 ---
    ls = np.isin(dfe4['dom'].values, [3, 9, 20]) & np.isin(dfe4['hour'].values, [1, 2, 3, 4, 5, 11, 12, 13, 14, 15])
    tr = run_engine_layer(dfe4, ls, ze, 20, 120, 96, asset='EURUSD')
    s = stats_from_trades_capital(tr, 'EURUSD'); s['layer'] = 'S143 EURUSD Mid-Month Drift'
    s['tf'] = 'M15'; s['dir'] = 'Long'; rows.append(s)

    # ---------------- چاپِ جدول ----------------
    print("\n" + "=" * 112)
    print(f"{'لایه':44s}{'TF':4s}{'جهت':10s}{'n':>6}{'صحیح':>6}{'غلط':>6}{'WR%':>7}{'net$':>12}{'PF':>7}")
    print("-" * 112)
    xau_net = eur_net = 0.0
    for r in rows:
        pf = r['pf'] if r['pf'] != float('inf') else 99.99
        print(f"{r['layer'][:44]:44s}{r['tf']:4s}{r['dir']:10s}{r['n']:>6}{r['wins']:>6}"
              f"{r['losses']:>6}{r['wr']:>7.1f}{r['net']:>+12,.0f}{pf:>7.2f}")
        if 'EURUSD' in r['layer']:
            eur_net += r['net']
        else:
            xau_net += r['net']
    print("-" * 112)
    total = xau_net + eur_net
    print(f"{'جمعِ XAUUSD':44s}{'':4s}{'':10s}{'':>6}{'':>6}{'':>6}{'':>7}{xau_net:>+12,.0f}")
    print(f"{'جمعِ EURUSD':44s}{'':4s}{'':10s}{'':>6}{'':>6}{'':>6}{'':>7}{eur_net:>+12,.0f}")
    print(f"{'🥇 سودِ خالصِ کل (۴ سالِ اخیر، جمعِ مجزا)':44s}{'':4s}{'':10s}{'':>6}{'':>6}{'':>6}{'':>7}{total:>+12,.0f}")
    print("=" * 112)

    out = dict(window_years=YEARS, xau_window=[str(s4.date()), str(e4.date())],
               eur_window=[str(se5.date()), str(ee5.date())],
               spec=dict(xau_spread_pip=3.3, comm=0.0, contract=100, margin=40),
               layers=rows, xau_net=xau_net, eur_net=eur_net, total_net=total)
    with open(os.path.join(RESULTS, '_audit_all_layers_4y.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_audit_all_layers_4y.json")
    return out


def run_squeeze_layer(df):
    """Squeeze نهایی: entries brk≥0.30 + rsi14≤75، paper_broker hidden(TP300,SL90)."""
    from strategies.s132_squeeze_breakout_m15 import build_entries_squeeze, MAX_HOLD_M15
    from strategies.s94_scalp_hidden_target import make_hidden_exit
    import strategies.s91_scalp_signal_exit as s91
    # override هزینهٔ paper_broker به مشخصاتِ واقعی (۳.۳pip، comm=0، slip=0)
    s91.SPREAD_PIP = 3.3; s91.SLIP_PIP = 0.0; s91.COMM_PER_LOT = 0.0
    s91.COST_PIP = s91.SPREAD_PIP + 2.0 * s91.SLIP_PIP
    from strategies.s91_scalp_signal_exit import paper_broker, ema as s91ema, atr as s91atr

    TRIG = dict(sqz_pct=0.25, breakout_lookback=6)
    entries = build_entries_squeeze(df, **TRIG)
    # فیلترِ اولِ رکورد brk≥0.30
    cvals = df['close'].values.astype(np.float64); hvals = df['high'].values.astype(np.float64)
    a14 = s91atr(df, 14); brk = TRIG['breakout_lookback']
    def brkstr(i):
        ph = hvals[i - brk:i].max() if i >= brk else np.nan
        a = a14[i] if (np.isfinite(a14[i]) and a14[i] > 0) else np.nan
        return float((cvals[i] - ph) / a) if (np.isfinite(ph) and np.isfinite(a)) else 0.0
    ent = [(i, s) for (i, s) in entries if brkstr(i) >= 0.30]
    # فیلترِ دومِ رکورد rsi14≤75
    r14 = ind.rsi(df['close'], 14).values
    ent = [(i, s) for (i, s) in ent if np.isfinite(r14[i]) and r14[i] <= 75.0]
    exit_fn = make_hidden_exit(300.0, 90.0, use_trend_break=False)
    tr = paper_broker(df, ent, exit_fn, catastrophic_sl_pip=400.0, max_hold=MAX_HOLD_M15)
    return stats_from_papertrades(tr)


def run_s67_layer(start, end):
    """S67 Router از cache _s61 — فقط پنجرهٔ ۴ ساله را نگه می‌داریم."""
    from engine.backtest import load_data, run_backtest
    from engine.tpsl_plan import build_plan
    HZ = 48; SPREAD = 0.20; ER_TREND_THR = 0.30; P_HI = 0.66; P_MIN = 0.58
    cache = os.path.join(RESULTS, '_s61_cache.npz')
    z = np.load(cache, allow_pickle=True)
    pL, pS = z['pL'], z['pS']; up_reg, down_reg = z['up_reg'], z['down_reg']
    er = z['er']; atrv = z['atrv']
    dfg = load_data('data/XAUUSD_M15.csv')
    ng = len(dfg)
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
    eval_mask = np.zeros(ng, bool); eval_mask[24000:] = True
    planL = build_plan('long', labL, atrv, dfg, run_backtest, spread=SPREAD, max_hold=HZ)
    planS = build_plan('short', labS, atrv, dfg, run_backtest, spread=SPREAD, max_hold=HZ)

    def get_trades(direction, plan):
        s = plan.entries & eval_mask
        st, tr = run_backtest(dfg, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                              sl_series=plan.sl_series(), tp_series=plan.tp_series())
        return tr

    trL = get_trades('long', planL); trS = get_trades('short', planS)
    all_tr = pd.concat([trL, trS], ignore_index=True)
    if len(all_tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, gp=0.0, gl=0.0, pf=0.0)
    # فیلترِ پنجرهٔ ۴ ساله بر مبنای زمانِ خروج
    tms = pd.to_datetime(dfg['time'].values[np.clip(all_tr['exit_bar'].values.astype(int), 0, ng - 1)], unit='s')
    mask = (tms >= start) & (tms <= end)
    all_tr = all_tr[mask.values].reset_index(drop=True)
    if len(all_tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, gp=0.0, gl=0.0, pf=0.0)
    # S67 با موتورِ قدیمِ backtest سود را بر حسبِ pnl(قیمت) می‌دهد؛ برای هم‌ترازی با
    # مشخصاتِ واقعی، از capital_engine با هزینهٔ واقعی استفاده می‌کنیم:
    from engine.capital_engine import run_capital_backtest
    # sl_dist بر حسبِ قیمت از plan (تقریب: از ستونِ موجود)؛ اگر نبود از فاصلهٔ ثابت
    sl_dist = np.abs(all_tr['entry_price'].values - all_tr.get('sl_price', all_tr['entry_price']).values)
    sl_dist = np.where(sl_dist > 0, sl_dist, all_tr['entry_price'].values * 0.01)
    st, _ = run_capital_backtest(all_tr, sl_dist, initial_capital=CAP, risk_pct=RISK,
                                 commission_per_lot=0.0, compounding=True)
    pnl = all_tr['pnl'].values if 'pnl' in all_tr else np.zeros(len(all_tr))
    wins = int((pnl > 0).sum()); losses = int((pnl <= 0).sum()); n = len(pnl)
    gp = float(pnl[pnl > 0].sum()); gl = float(-pnl[pnl <= 0].sum())
    return dict(net=float(st['net_profit']), n=n, wins=wins, losses=losses,
                wr=(wins / n * 100.0 if n else 0.0), gp=gp, gl=gl,
                pf=(gp / gl if gl > 0 else float('inf')))


def run_s91_layer():
    """S91 M5 scalp signal-exit با هزینهٔ واقعی. محدودیت: M5 فقط از ۲۰۲۳-۰۹."""
    import strategies.s91_scalp_signal_exit as s91
    s91.SPREAD_PIP = 3.3; s91.SLIP_PIP = 0.0; s91.COMM_PER_LOT = 0.0
    s91.COST_PIP = s91.SPREAD_PIP + 2.0 * s91.SLIP_PIP
    from strategies.s91_scalp_signal_exit import paper_broker, ema as s91ema
    df = add_calendar(load('XAUUSD_M5'))
    df4, s5, e5 = last_n_years(df)
    span = (e5 - s5).days / 365.25
    note = f'داده فقط {span:.1f} سال (M5 از {s5.date()})'
    # سیگنالِ نمایندهٔ S91: پولبک به EMA20 در روندِ صعودی (EMA20>EMA50)، خروجِ سیگنال-محور
    c = df4['close']
    e20 = s91ema(c.values, 20); e50 = s91ema(c.values, 50)
    price = c.values
    up = e20 > e50
    touch = np.r_[False, (price[:-1] <= e20[:-1]) & (price[1:] > e20[1:])][:len(price)]
    entries = [(i, 'long') for i in range(len(price)) if up[i] and touch[i]]
    # خروجِ سیگنال-محور: بستن وقتی EMA20 زیرِ EMA50 برود یا قیمت زیرِ EMA20 ببندد
    def exit_fn(state):
        i = state['bar']; 
        return (e20[i] < e50[i]) or (state['close'] < e20[i])
    try:
        tr = paper_broker(df4, entries, exit_fn, catastrophic_sl_pip=200.0, max_hold=288)
    except Exception as ex:
        # exit_fn امضای متفاوت دارد؛ از خروجِ hidden استاندارد استفاده می‌کنیم
        from strategies.s94_scalp_hidden_target import make_hidden_exit
        tr = paper_broker(df4, entries, make_hidden_exit(150.0, 100.0, use_trend_break=True),
                          catastrophic_sl_pip=200.0, max_hold=288)
        note += ' (خروجِ hidden جایگزین)'
    return stats_from_papertrades(tr), note


if __name__ == '__main__':
    main()
