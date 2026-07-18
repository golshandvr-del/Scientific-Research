"""
S130 — حسابرسیِ سودِ خالصِ روزانه/هفتگی/ماهانهٔ «پرتفویِ رکوردِ فعلی (+$101,259)»
         + رسمِ منحنیِ سرمایه (Equity) با محورِ هفتگی و ماهانه  (پاسخ به User Note)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate (WR).**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD. WR فقط عددِ گزارشی است.

------------------------------------------------------------------------------
انگیزه (User Note این نشست):
  «الان سودِ خالصمون از ۱۰۰ هزار دلار بیشتر شده. حالا سؤال: سودِ خالصِ روزانه،
   هفتگی و ماهانه‌مون چجوریه؟ فقط ۳-۴ سال اخیر رو بررسی کن. اگر سودِ خالصِ هفتگیِ
   ما در دفعاتِ زیاد منفیه، یه کاری کن بتونیم مثبتش کنیم. یه نمودارِ سرمایه در طولِ
   زمان می‌تونی برام رسم کنی؟ با محورِ افقیِ هفتگی و ماهانه.»

------------------------------------------------------------------------------
این اسکریپت **دقیقاً پرتفویِ رکوردِ فعلی** (۵ لایه، مجموع +$101,259) را با timestamp
اجرا می‌کند:
  • S67        — XAUUSD M15  (لایهٔ نوسانیِ router + capital_engine)   ≈ +$30,490
  • ScalpV2    — XAUUSD M5   (ماشهٔ D3_MACD؛ ارتقای s128)              ≈ +$15,659
  • S81        — XAUUSD M30  (Swing Trend-Pullback)                    ≈ +$14,327
  • SHORT      — XAUUSD M15  (MA-Confluence؛ خروجِ let-winners-run)    ≈ +$34,542
  • S73        — EURUSD M15  (Session-Open Drift)                       ≈ +$9,223

سپس سودِ دلاریِ per-trade هر لایه (با زمانِ بسته‌شدن) را ادغام می‌کند، **فقط ۳-۴ سالِ
اخیر** را نگه می‌دارد، و با engine/periodic_pnl.py سود را در سطل‌های روزانه/هفتگی/ماهانه
تجمیع + تحلیلِ دنباله‌های منفی می‌کند. سرانجام منحنیِ Equity را رسم می‌کند.

⚠️ روش‌شناسی: هر لایه روی سرمایهٔ مستقلِ ۱۰k$ با ریسکِ ۱٪ (بدون کامپاند، افزایش‌پذیریِ
خطی) اجرا می‌شود تا سطلِ زمانی «جمعِ سودِ دلاری» معنای پرتفویِ منصفانه بدهد.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from engine import scalp_engine as SE
from engine.periodic_pnl import build_pnl_events, periodic_summary, print_periodic_report, worst_streak

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, 'results')

# مشخصاتِ M5/M30 طلا (هم‌راستا با s79/s81/s128)
SE.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
SE.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)

CAP = 10_000.0
RISK = 1.0

# محدودهٔ تحلیل: فقط N سالِ اخیر (User Note: «فقط ۳-۴ سالِ اخیر»)
YEARS_BACK = 4


def _ema(x, s):
    return pd.Series(x).ewm(span=s, adjust=False).mean().values


def _rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


# ---------------------------------------------------------------------------
# لایهٔ ScalpV2 — XAUUSD M5 — ماشهٔ D3_MACD (تقاطعِ صعودیِ MACD + گیتِ روند)
# ---------------------------------------------------------------------------
def layer_scalpv2():
    asset = 'XAUUSD_M5'
    df = SE.load_data(SE.ASSETS[asset]['file'])
    c = df['close'].values
    e20 = _ema(c, 20); e100 = _ema(c, 100)
    macd_line = _ema(c, 12) - _ema(c, 26)
    macd_sig = _ema(macd_line, 9)
    n = len(df)
    long_sig = np.zeros(n, bool)
    for i in range(1, n):
        cross_up = (macd_line[i] > macd_sig[i]) and (macd_line[i-1] <= macd_sig[i-1])
        if cross_up and (e20[i] > e100[i]):
            long_sig[i] = True
    short_sig = np.zeros(n, bool)
    # برندهٔ s128: TP=120/SL=80 (per-bar hidden target)
    tr = SE.simulate_trades(df, long_sig, short_sig, 80, 120, asset, max_hold=72)
    stats, eq, pt = SE.run_capital_pertrade(tr, asset, df=df, initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    return dict(name='ScalpV2 (طلا M5 · D3_MACD)', stats=stats, pt=pt)


# ---------------------------------------------------------------------------
# لایهٔ S81 — XAUUSD M30 Swing Trend-Pullback (فقط Long)
# ---------------------------------------------------------------------------
def layer_s81():
    asset = 'XAUUSD_M30'
    df = SE.load_data(SE.ASSETS[asset]['file'])
    c = df['close'].values
    long_sig = np.nan_to_num((_ema(c, 20) > _ema(c, 100)) & (_rsi(c, 14) < 35)).astype(bool)
    short_sig = np.zeros(len(df), bool)
    tr = SE.simulate_trades(df, long_sig, short_sig, 120, 1200, asset, max_hold=144)
    stats, eq, pt = SE.run_capital_pertrade(tr, asset, df=df, initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    return dict(name='S81 (طلا M30 swing)', stats=stats, pt=pt)


# ---------------------------------------------------------------------------
# لایهٔ SHORT — XAUUSD M15 MA-Confluence (خروجِ let-winners-run: SL70/TP800/be6/trail6)
# ---------------------------------------------------------------------------
def layer_short():
    asset = 'XAUUSD'
    df = SE.load_data(SE.ASSETS[asset]['file'])
    c = df['close']; price = c.values
    from engine import indicators as ind
    ema20 = ind.ema(c, 20).values
    ema50 = ind.ema(c, 50).values
    sma50 = ind.sma(c, 50).values
    sma200 = ind.sma(c, 200).values
    ma_stack = np.column_stack([ema20, ema50, sma50, sma200])
    ma_mid = np.nanmean(ma_stack, axis=1)
    ema20_slope = pd.Series(ema20).diff().values
    prev_above_mid = np.r_[False, price[:-1] > ma_mid[:-1]]
    short_sig = prev_above_mid & (price < ma_mid) & (ema20_slope < 0)
    short_sig = np.nan_to_num(short_sig).astype(bool)
    long_sig = np.zeros(len(df), bool)
    # خروجِ بازطراحی‌شدهٔ s118 «بگذار بردها بدوند»: SL70/TP800/be6/trail6/mh48
    tr = SE.simulate_trades(df, long_sig, short_sig, 70, 800, asset, max_hold=48,
                            be_trigger_pip=6, trail_pip=6)
    stats, eq, pt = SE.run_capital_pertrade(tr, asset, df=df, initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    return dict(name='SHORT (طلا M15 confluence)', stats=stats, pt=pt)


# ---------------------------------------------------------------------------
# لایهٔ S73 — EURUSD Session-Open Drift (فقط Long، ساعت 0 UTC، buy-the-dip)
# ---------------------------------------------------------------------------
def layer_s73():
    asset = 'EURUSD'
    df = SE.load_data(SE.ASSETS[asset]['file'])
    n = len(df)
    dt = pd.to_datetime(df['time'], unit='s')
    hour = dt.dt.hour.values
    c = df['close'].values
    eval_mask = np.zeros(n, bool); eval_mask[24000:] = True
    is_last_before_h0 = np.zeros(n, bool)
    is_last_before_h0[:-1] = (hour[1:] == 0) & (hour[:-1] != 0)
    long_sig = is_last_before_h0 & eval_mask
    prior = np.zeros(n); prior[4:] = c[4:] - c[:-4]
    long_sig = long_sig & (prior < 0)
    short_sig = np.zeros(n, bool)
    tr = SE.simulate_trades(df, long_sig, short_sig, 12, 12, asset, max_hold=6)
    stats, eq, pt = SE.run_capital_pertrade(tr, asset, df=df, initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    return dict(name='S73 (یورو M15 drift)', stats=stats, pt=pt)


# ---------------------------------------------------------------------------
# لایهٔ S67 — XAUUSD M15 (router + capital_engine) — از cache
# ---------------------------------------------------------------------------
def layer_s67():
    from engine.backtest import load_data, run_backtest
    from engine.tpsl_plan import build_plan
    from engine.capital_engine import run_capital_backtest
    HZ = 48; SPREAD = 0.20; ER_TREND_THR = 0.30; P_HI = 0.66; P_MIN = 0.58
    cache = os.path.join(RES, '_s61_cache.npz')
    z = np.load(cache, allow_pickle=True)
    pL, pS = z['pL'], z['pS']; up_reg, down_reg = z['up_reg'], z['down_reg']
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
    eval_mask = np.zeros(n, bool); eval_mask[24000:] = True
    planL = build_plan('long', labL, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)
    planS = build_plan('short', labS, atrv, df, run_backtest, spread=SPREAD, max_hold=HZ)

    def get_trades(direction, plan):
        s = plan.entries & eval_mask
        st, tr = run_backtest(df, s, None, None, direction, spread=SPREAD, max_hold=HZ,
                              sl_series=plan.sl_series(), tp_series=plan.tp_series())
        if len(tr) == 0:
            return tr, np.array([]), np.array([])
        return tr, plan.sl_dist_for_trades(tr), plan.weights[tr['signal_bar'].values]

    trL, slL, wL = get_trades('long', planL)
    trS, slS, wS = get_trades('short', planS)
    all_tr = pd.concat([trL, trS], ignore_index=True)
    all_sl = np.concatenate([slL, slS]) if len(slL) or len(slS) else np.array([])
    all_w = np.concatenate([wL, wS]) if len(wL) or len(wS) else np.array([])
    order = all_tr['exit_bar'].values.argsort()
    all_tr = all_tr.iloc[order].reset_index(drop=True)
    all_sl = all_sl[order]; all_w = all_w[order]

    stats, eq = run_capital_backtest(all_tr, all_sl, weights=all_w, initial_capital=CAP,
                                     risk_pct=RISK, commission_per_lot=7.0, compounding=False)
    net_per = np.diff(eq)
    m = min(len(net_per), len(all_tr))
    pt = pd.DataFrame({'exit_bar': all_tr['exit_bar'].values[:m], 'net_usd': net_per[:m]})
    idx = np.clip(pt['exit_bar'].values, 0, len(df) - 1)
    pt['dt'] = pd.to_datetime(df['time'].values[idx], unit='s', utc=True)
    return dict(name='S67 (طلا M15 router)', stats=stats, pt=pt)


def filter_recent(pt, years=YEARS_BACK, cutoff=None):
    """فقط رویدادهایِ N سالِ اخیر (بر اساسِ بیشترین زمانِ کلِ پرتفوی)."""
    if len(pt) == 0:
        return pt
    return pt[pt['dt'] >= cutoff].reset_index(drop=True)


def apply_weekly_breaker(events, stop):
    """
    بریکرِ هفتگی: در هر هفتهٔ ISO، معاملاتِ بسته‌شده را به‌ترتیبِ زمان می‌پیماییم؛
    وقتی زیانِ تجمعیِ هفته از -stop عبور کرد، سودِ معاملاتِ بعدیِ همان هفته را صفر
    می‌کنیم (شبیه‌سازیِ «توقفِ ورودِ جدید تا پایانِ هفته»).
    خروجی: DataFrame ['dt','pnl'] با pnl اصلاح‌شده.
    """
    ev = events.copy().sort_values('dt').reset_index(drop=True)
    iso = ev['dt'].dt.isocalendar()
    ev['_wk'] = iso['year'].astype(str) + '-' + iso['week'].astype(str)
    new_pnl = ev['pnl'].values.copy()
    for wk, idx in ev.groupby('_wk').groups.items():
        idx = list(idx)
        cum = 0.0; blocked = False
        for i in idx:
            if blocked:
                new_pnl[i] = 0.0
                continue
            cum += ev['pnl'].values[i]
            if cum <= -stop:
                blocked = True  # ورودهای بعدیِ همین هفته مسدود
    out = pd.DataFrame({'dt': ev['dt'].values, 'pnl': new_pnl})
    return out


def sweep_weekly_breaker(port, weekly_base):
    """چند آستانهٔ بریکر را جارو و بهترین را طبقِ قانونِ #۱ انتخاب می‌کند."""
    base_net = float(weekly_base.sum())
    base_neg = int((weekly_base < 0).sum()); base_tot = len(weekly_base)
    print(f"\n  پایه (بدونِ بریکر): سودِ خالص=+${base_net:,.0f}  |  "
          f"هفته‌های منفی={base_neg}/{base_tot} ({100*base_neg/base_tot:.1f}%)", flush=True)
    print(f"\n  {'آستانه ($)':>12}{'سودِ خالص':>14}{'هفتهٔ منفی':>14}{'%منفی':>9}"
          f"{'بدترین هفته':>14}{'ماهِ منفی':>12}", flush=True)
    print("  " + "-" * 78, flush=True)
    candidates = []
    for stop in [500, 800, 1000, 1200, 1500, 2000, 2500]:
        ev = apply_weekly_breaker(port, stop)
        res = periodic_summary(ev, label=f'breaker-{stop}')
        w = res['periods']['هفتگی (W)']['series']
        m = res['periods']['ماهانه (M)']['series']
        net = float(w.sum()); neg = int((w < 0).sum()); tot = len(w)
        worst = float(w.min()); mneg = int((m < 0).sum())
        print(f"  {stop:>12,.0f}{net:>14,.0f}{neg:>10}/{tot:<3}{100*neg/tot:>8.1f}%"
              f"{worst:>14,.0f}{mneg:>12}", flush=True)
        candidates.append(dict(stop=stop, net=net, neg=neg, tot=tot, worst=worst,
                               mneg=mneg, events=ev))
    # انتخاب: کمترین درصدِ هفتهٔ منفی، مشروط بر اینکه سودِ خالص حداکثر ۸٪ افت کند
    # (قانونِ #۱: سود مهم است؛ نمی‌گذاریم راهکار سودِ کل را نابود کند)
    min_keep = 0.92 * base_net
    viable = [c for c in candidates if c['net'] >= min_keep]
    if not viable:
        viable = candidates
    best = min(viable, key=lambda c: (c['neg'] / c['tot'], -c['net']))
    print(f"\n  ✅ بهترین آستانه: -${best['stop']:,.0f}  →  سودِ خالص=+${best['net']:,.0f} "
          f"(افت {100*(base_net-best['net'])/base_net:.1f}%)  |  هفتهٔ منفی "
          f"{best['neg']}/{best['tot']} ({100*best['neg']/best['tot']:.1f}%)  |  "
          f"ماهِ منفی={best['mneg']}", flush=True)
    print(f"     ⇒ کاهشِ درصدِ هفته‌های منفی از {100*base_neg/base_tot:.1f}% به "
          f"{100*best['neg']/best['tot']:.1f}%", flush=True)
    return best


def main():
    print("=" * 92, flush=True)
    print("  S130 — حسابرسیِ دوره‌ای + منحنیِ سرمایهٔ پرتفویِ رکوردِ فعلی (+$101,259)", flush=True)
    print("  قانونِ #۱: فقط سودِ خالص (XAUUSD + EURUSD). WR گزارشی است.", flush=True)
    print(f"  محدودهٔ تحلیل: فقط {YEARS_BACK} سالِ اخیر (User Note).", flush=True)
    print("=" * 92, flush=True)

    layers = []
    for fn in (layer_s67, layer_scalpv2, layer_s81, layer_short, layer_s73):
        try:
            L = fn()
            layers.append(L)
            s = L['stats']
            print(f"\n  ✓ {L['name']}: net={s['net_profit']:+,.0f}$  n={s['n_trades']}  "
                  f"WR={s['win_rate']:.1f}%  PF={s['profit_factor']:.2f}", flush=True)
        except Exception as e:
            import traceback; traceback.print_exc()
            print(f"\n  ✗ خطا در {fn.__name__}: {e}", flush=True)

    # cutoff مشترک بر اساسِ آخرین زمانِ کلِ پرتفوی
    max_dt = max(L['pt']['dt'].max() for L in layers if len(L['pt']))
    cutoff = max_dt - pd.DateOffset(years=YEARS_BACK)
    print(f"\n  آخرین زمانِ داده: {max_dt.date()}  |  cutoff ({YEARS_BACK}y): {cutoff.date()}", flush=True)

    # -------- ساختِ پرتفویِ کل (فقط ۴ سالِ اخیر) --------
    all_ev = []
    for L in layers:
        pt = filter_recent(L['pt'], cutoff=cutoff)
        if len(pt):
            all_ev.append(build_pnl_events(pt, 'net_usd', 'dt'))
    port = pd.concat(all_ev, ignore_index=True).sort_values('dt').reset_index(drop=True)

    print("\n\n" + "#" * 92, flush=True)
    print("#  سطحِ پرتفوی (جمعِ سود دلاریِ همهٔ لایه‌ها) — فقط ۴ سالِ اخیر", flush=True)
    print("#" * 92, flush=True)
    port_res = periodic_summary(port, label=f'پرتفویِ رکورد — {YEARS_BACK} سالِ اخیر')
    print()
    print_periodic_report(port_res)

    print("\n  --- تحلیلِ دنباله‌های منفی (پاسخ به «آیا هفته‌ها زیاد منفی‌اند؟») ---", flush=True)
    for name in ('هفتگی (W)', 'ماهانه (M)'):
        if port_res and name in port_res['periods']:
            ser = port_res['periods'][name]['series']
            streak, wsum = worst_streak(ser)
            neg = port_res['periods'][name]['n_negative']
            tot = port_res['periods'][name]['n_periods']
            print(f"  {name}: {neg}/{tot} دورهٔ منفی ({100*neg/tot:.1f}%)  |  "
                  f"بدترین دنبالهٔ متوالیِ منفی = {streak} دوره  |  "
                  f"بدترین افتِ متوالی = {wsum:+,.0f}$", flush=True)

    # ذخیرهٔ سریِ هفتگی/ماهانه برای رسم و گزارش
    weekly = port_res['periods']['هفتگی (W)']['series']
    monthly = port_res['periods']['ماهانه (M)']['series']

    # ==================================================================
    # راهکارِ کاهشِ هفته‌های منفی: «بریکرِ هفتگی» (Weekly Circuit Breaker)
    # قانونِ سطح-پرتفوی: در هر هفتهٔ تقویمیِ UTC، معاملاتِ بسته‌شده را به‌ترتیبِ
    # زمان جمع می‌کنیم؛ به‌محضِ اینکه زیانِ تجمعیِ آن هفته از -STOP دلار عبور کرد،
    # ورودهای بعدیِ همان هفته «مسدود» می‌شوند (سود آن معاملات صفر فرض می‌شود).
    # هدف: کم‌کردنِ تعداد و عمقِ هفته‌های منفی، بدونِ آسیب به هفته‌های خوب.
    # چند آستانه جارو می‌شود و بهترین بر مبنایِ قانونِ #۱ (بیشترین سودِ خالص با
    # کمترین هفتهٔ منفی) انتخاب می‌شود.
    # ==================================================================
    print("\n\n" + "#" * 92, flush=True)
    print("#  راهکارِ User Note — «بریکرِ هفتگی» برای مثبت‌کردنِ هفته‌های منفی", flush=True)
    print("#" * 92, flush=True)
    best = sweep_weekly_breaker(port, weekly)
    port_bt = best['events']
    port_res_bt = periodic_summary(port_bt, label=f'پرتفوی + بریکرِ هفتگی (-${best["stop"]:.0f})')
    weekly_bt = port_res_bt['periods']['هفتگی (W)']['series']
    monthly_bt = port_res_bt['periods']['ماهانه (M)']['series']
    out_breaker = {
        'stop': best['stop'],
        'total_net': port_res_bt['total_net'],
        'periods': {k: {kk: vv for kk, vv in v.items() if kk != 'series'}
                    for k, v in port_res_bt['periods'].items()},
        'weekly_series': {str(k.date()): float(v) for k, v in weekly_bt.items()},
        'monthly_series': {str(k.date()): float(v) for k, v in monthly_bt.items()},
    }

    out = {
        'years_back': YEARS_BACK,
        'cutoff': str(cutoff.date()),
        'max_dt': str(max_dt.date()),
        'portfolio_recent': {
            'total_net': port_res['total_net'],
            'n_trades': port_res['n_trades'],
            'periods': {k: {kk: vv for kk, vv in v.items() if kk != 'series'}
                        for k, v in port_res['periods'].items()},
        },
        'weekly_series': {str(k.date()): float(v) for k, v in weekly.items()},
        'monthly_series': {str(k.date()): float(v) for k, v in monthly.items()},
        'breaker': out_breaker,
    }
    with open(os.path.join(RES, '_s130_periodic.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\n  خلاصه در results/_s130_periodic.json ذخیره شد.", flush=True)

    # ------------------------------------------------------------------
    # رسمِ منحنیِ سرمایه (Equity) — محورِ هفتگی و ماهانه
    # ------------------------------------------------------------------
    plot_equity(port, weekly, monthly, tag='baseline')
    plot_compare(weekly, monthly, weekly_bt, monthly_bt, best['stop'])
    print("\nتمام.", flush=True)
    return port, weekly, monthly


def plot_equity(port, weekly, monthly, tag='baseline'):
    """منحنیِ سرمایهٔ تجمعی + بارِ سود/زیانِ هفتگی و ماهانه."""
    base = 100_000.0  # مبنایِ نمایشی (رکوردِ فعلی)
    # equity هفتگی و ماهانه تجمعی
    w_cum = base + weekly.cumsum()
    m_cum = base + monthly.cumsum()

    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # --- بالا: منحنیِ سرمایهٔ تجمعی (هفتگی و ماهانه) ---
    ax = axes[0]
    ax.plot(w_cum.index, w_cum.values, color='#2563eb', lw=1.3, label='Equity (weekly)')
    ax.plot(m_cum.index, m_cum.values, color='#dc2626', lw=2.2, marker='o', ms=3,
            label='Equity (monthly)')
    ax.axhline(base, color='gray', ls='--', lw=0.8)
    ax.set_title(f'Portfolio Equity Curve (recent 4y) — start=${base:,.0f}', fontsize=13)
    ax.set_ylabel('Cumulative Net Profit ($)')
    ax.legend(loc='upper left')
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    # --- پایین: بارِ سود/زیانِ هفتگی (سبز مثبت، قرمز منفی) ---
    ax = axes[1]
    colors = ['#16a34a' if v >= 0 else '#dc2626' for v in weekly.values]
    ax.bar(weekly.index, weekly.values, width=5, color=colors)
    ax.axhline(0, color='black', lw=0.8)
    neg = int((weekly < 0).sum()); tot = len(weekly)
    ax.set_title(f'Weekly Net P/L — {neg}/{tot} weeks negative ({100*neg/tot:.1f}%)', fontsize=13)
    ax.set_ylabel('Weekly Net Profit ($)')
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

    plt.tight_layout()
    path = os.path.join(RES, f'_s130_equity_{tag}.png')
    plt.savefig(path, dpi=110, bbox_inches='tight')
    plt.close()
    print(f"  نمودار ذخیره شد: {path}", flush=True)


def plot_compare(weekly, monthly, weekly_bt, monthly_bt, stop):
    """مقایسهٔ منحنیِ سرمایه و توزیعِ هفتگی: پایه در برابر «بریکرِ هفتگی»."""
    base = 100_000.0
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))

    # --- بالا: مقایسهٔ Equity تجمعیِ ماهانه ---
    ax = axes[0]
    ax.plot(base + monthly.cumsum().values, color='#94a3b8', lw=2.0, marker='o', ms=3,
            label='Baseline (monthly)')
    ax.plot((base + monthly_bt.cumsum()).values, color='#dc2626', lw=2.4, marker='s', ms=3,
            label=f'Weekly Circuit-Breaker -${stop:,.0f} (monthly)')
    idx = [d.strftime('%Y-%m') for d in monthly.index]
    step = max(1, len(idx)//12)
    ax.set_xticks(range(0, len(idx), step))
    ax.set_xticklabels(idx[::step], rotation=45, ha='right', fontsize=8)
    ax.axhline(base, color='gray', ls='--', lw=0.8)
    ax.set_title('Equity Curve — Baseline vs Weekly Circuit-Breaker (recent 4y)', fontsize=13)
    ax.set_ylabel('Cumulative Net Profit ($)')
    ax.legend(loc='upper left'); ax.grid(alpha=0.3)

    # --- پایین: مقایسهٔ توزیعِ هفتگی ---
    ax = axes[1]
    nb = int((weekly < 0).sum()); na = int((weekly_bt < 0).sum()); tot = len(weekly)
    ax.bar(np.arange(len(weekly)) - 0.2, weekly.values, width=0.4,
           color=['#16a34a' if v >= 0 else '#dc2626' for v in weekly.values],
           alpha=0.55, label=f'Baseline (neg {nb}/{tot})')
    wb = weekly_bt.reindex(weekly.index).fillna(0.0)
    ax.bar(np.arange(len(weekly)) + 0.2, wb.values, width=0.4,
           color=['#065f46' if v >= 0 else '#7f1d1d' for v in wb.values],
           alpha=0.9, label=f'Breaker (neg {na}/{tot})')
    ax.axhline(0, color='black', lw=0.8)
    ax.set_title(f'Weekly Net P/L — negative weeks: {nb}/{tot} → {na}/{tot} '
                 f'({100*nb/tot:.1f}% → {100*na/tot:.1f}%)', fontsize=13)
    ax.set_ylabel('Weekly Net Profit ($)'); ax.set_xlabel('week index')
    ax.legend(loc='upper left'); ax.grid(alpha=0.3)

    plt.tight_layout()
    path = os.path.join(RES, '_s130_equity_breaker_compare.png')
    plt.savefig(path, dpi=110, bbox_inches='tight')
    plt.close()
    print(f"  نمودارِ مقایسه ذخیره شد: {path}", flush=True)


if __name__ == '__main__':
    main()
