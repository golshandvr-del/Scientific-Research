"""
S84 — «حسابرسیِ سودِ خالصِ روزانه/هفتگی/ماهانهٔ پرتفویِ برندهٔ فعلی» (پاسخ به User Note)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدف **فقط و فقط «سودِ خالصِ بیشتر»** است —
نه Win-Rate. تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز XAUUSD + EURUSD. WR گزارشی است.

------------------------------------------------------------------------------
پاسخِ مستقیم به User Note:
  «تا الان فقط یک عددِ سودِ خالصِ کل داشتیم. حالا تست را طوری گسترش بده که سودِ
   خالصِ روزانه/هفتگی/ماهانه هم حساب شود. سپس استراتژیِ برندهٔ فعلی را در این تست
   ببین: آیا همیشه سودِ خالصِ روزانه/هفتگی/ماهانه مثبت است؟»

این اسکریپت هر ۴ لایهٔ پرتفویِ برنده (رکوردِ +۵۸٬۲۹۵$) را با timestamp اجرا می‌کند:
  • S67  — XAUUSD M15 (لایهٔ نوسانی، موتورِ router + capital_engine)
  • S79  — XAUUSD M5  (لایهٔ اسکالپِ trend-pullback، scalp_engine)
  • S81  — XAUUSD M30 (لایهٔ swingِ trend-pullback، scalp_engine)
  • S73  — EURUSD M15 (Session-Open Drift، scalp_engine — هم‌گام‌سازی‌شده)

سپس سود دلاریِ per-trade هر لایه را با زمانِ بسته‌شدن ادغام می‌کند و با
engine/periodic_pnl.py سود را در سطل‌های روزانه/هفتگی/ماهانه تجمیع و تحلیل می‌کند.

⚠️ نکتهٔ روش‌شناختی: چون لایه‌ها روی تایم‌فریم‌های متفاوت (M5/M15/M30) هستند، «سودِ
خالصِ روزانه» به‌صورتِ جمعِ سود دلاریِ همهٔ لایه‌ها در همان روزِ تقویمیِ UTC تعریف
می‌شود (portfolio-level daily/weekly/monthly). هر لایه روی سرمایهٔ مستقلِ ۱۰k$ با
ریسکِ ۱٪ (بدون کامپاند، برای مقایسهٔ منصفانه و افزایش‌پذیریِ خطی) اجرا می‌شود.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
import warnings; warnings.filterwarnings('ignore')

from engine import scalp_engine as SE
from engine.periodic_pnl import build_pnl_events, periodic_summary, print_periodic_report, worst_streak

RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results')

# مشخصاتِ M5/M30 طلا (هم‌راستا با s79/s81)
SE.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
SE.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)

CAP = 10_000.0
RISK = 1.0


def _ema(x, s):
    return pd.Series(x).ewm(span=s, adjust=False).mean().values


def _rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


# ---------------------------------------------------------------------------
# لایهٔ S79 — XAUUSD M5 Trend-Pullback (فقط Long)
# ---------------------------------------------------------------------------
def layer_s79():
    asset = 'XAUUSD_M5'
    df = SE.load_data(SE.ASSETS[asset]['file'])
    c = df['close'].values
    long_sig = np.nan_to_num((_ema(c, 20) > _ema(c, 100)) & (_rsi(c, 21) < 35)).astype(bool)
    short_sig = np.zeros(len(df), bool)
    tr = SE.simulate_trades(df, long_sig, short_sig, 50, 120, asset, max_hold=72)
    stats, eq, pt = SE.run_capital_pertrade(tr, asset, df=df, initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    return dict(name='S79 (طلا M5)', stats=stats, pt=pt)


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
    return dict(name='S81 (طلا M30)', stats=stats, pt=pt)


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
    # SL/TP = 12 pip، hold=6 (هم‌راستا با S73)
    tr = SE.simulate_trades(df, long_sig, short_sig, 12, 12, asset, max_hold=6)
    stats, eq, pt = SE.run_capital_pertrade(tr, asset, df=df, initial_capital=CAP,
                                            risk_pct=RISK, compounding=False)
    return dict(name='S73 (یورو M15)', stats=stats, pt=pt)


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

    # حسابداریِ per-trade با همان منطقِ capital_engine (ریسکِ ثابت ۱٪، بدون کامپاند)
    stats, eq = run_capital_backtest(all_tr, all_sl, weights=all_w, initial_capital=CAP,
                                     risk_pct=RISK, commission_per_lot=7.0, compounding=False)
    # بازسازیِ سود دلاریِ per-trade (equity diff)
    net_per = np.diff(eq)
    m = min(len(net_per), len(all_tr))
    pt = pd.DataFrame({'exit_bar': all_tr['exit_bar'].values[:m], 'net_usd': net_per[:m]})
    idx = np.clip(pt['exit_bar'].values, 0, len(df) - 1)
    pt['dt'] = pd.to_datetime(df['time'].values[idx], unit='s', utc=True)
    n_short = int((all_tr['direction'] == 'short').sum()) if 'direction' in all_tr else 0
    stats['n_short'] = n_short; stats['n_long'] = len(all_tr) - n_short
    return dict(name='S67 (طلا M15)', stats=stats, pt=pt)


def main():
    print("=" * 90, flush=True)
    print("  S84 — حسابرسیِ سودِ خالصِ روزانه/هفتگی/ماهانهٔ پرتفویِ برندهٔ فعلی", flush=True)
    print("  قانونِ #۱: فقط سودِ خالص (XAUUSD + EURUSD). WR گزارشی است.", flush=True)
    print("=" * 90, flush=True)

    layers = []
    for fn in (layer_s67, layer_s79, layer_s81, layer_s73):
        try:
            L = fn()
            layers.append(L)
            s = L['stats']
            extra = ''
            if 'n_short' in s:
                extra = f"  (Long={s.get('n_long','?')}, Short={s.get('n_short','?')})"
            print(f"\n  ✓ {L['name']}: net={s['net_profit']:+,.0f}$  n={s['n_trades']}  "
                  f"WR={s['win_rate']:.1f}%  PF={s['profit_factor']:.2f}{extra}", flush=True)
        except Exception as e:
            print(f"\n  ✗ خطا در {fn.__name__}: {e}", flush=True)

    # -------- تحلیلِ دوره‌ایِ هر لایه --------
    print("\n\n" + "#" * 90, flush=True)
    print("#  بخش ۱ — تحلیلِ سودِ خالصِ دوره‌ای برای هر لایه به‌طورِ مستقل", flush=True)
    print("#" * 90, flush=True)
    layer_results = {}
    for L in layers:
        pt = L['pt']
        if len(pt) == 0:
            continue
        ev = build_pnl_events(pt, 'net_usd', 'dt')
        res = periodic_summary(ev, label=L['name'])
        layer_results[L['name']] = res
        print()
        print_periodic_report(res)

    # -------- تحلیلِ سطحِ پرتفوی (جمعِ همهٔ لایه‌ها در همان روز/هفته/ماه) --------
    print("\n\n" + "#" * 90, flush=True)
    print("#  بخش ۲ — سطحِ پرتفوی (جمعِ سود دلاریِ همهٔ لایه‌ها در همان دورهٔ تقویمی)", flush=True)
    print("#" * 90, flush=True)
    all_ev = []
    for L in layers:
        if len(L['pt']):
            all_ev.append(build_pnl_events(L['pt'], 'net_usd', 'dt'))
    port = pd.concat(all_ev, ignore_index=True).sort_values('dt').reset_index(drop=True)
    port_res = periodic_summary(port, label='کلِ پرتفوی (S67+S79+S81+S73)')
    print()
    print_periodic_report(port_res)

    # streak analysis روی سطلِ ماهانه و هفتگی
    print("\n  --- تحلیلِ دنباله‌های منفی (پاسخ به «آیا همیشه مثبت است؟») ---", flush=True)
    for name in ('هفتگی (W)', 'ماهانه (M)'):
        if port_res and name in port_res['periods']:
            ser = port_res['periods'][name]['series']
            streak, wsum = worst_streak(ser)
            neg = port_res['periods'][name]['n_negative']
            tot = port_res['periods'][name]['n_periods']
            print(f"  {name}: {neg}/{tot} دورهٔ منفی  |  بدترین دنبالهٔ متوالیِ منفی = "
                  f"{streak} دوره  |  بدترین افتِ متوالی = {wsum:+,.0f}$", flush=True)

    # ذخیرهٔ خلاصه برای گزارشِ MD
    out = {'layers': {}, 'portfolio': {}}
    for nm, r in layer_results.items():
        if r is None:
            continue
        out['layers'][nm] = {'total_net': r['total_net'], 'n_trades': r['n_trades'],
                             'periods': {k: {kk: vv for kk, vv in v.items() if kk != 'series'}
                                         for k, v in r['periods'].items()}}
    if port_res:
        out['portfolio'] = {'total_net': port_res['total_net'], 'n_trades': port_res['n_trades'],
                            'periods': {k: {kk: vv for kk, vv in v.items() if kk != 'series'}
                                        for k, v in port_res['periods'].items()}}
    with open(os.path.join(RES, '_s84_periodic.json'), 'w') as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2, default=float)
    print("\n  خلاصه در results/_s84_periodic.json ذخیره شد.", flush=True)
    print("\nتمام.", flush=True)


if __name__ == '__main__':
    main()
