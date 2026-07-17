"""
explore_gold_m30_validate.py — اعتبارسنجیِ عمیقِ کاندیدِ M30 (S81) + استقلال + سرمایهٔ کم
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر». تعریف = XAUUSD + EURUSD.

پس از explore_gold_mtf_swing کشف شد:
  • M30: فرضیهٔ User Note درست — trend-pullback جواب می‌دهد و پایدار است.
  • H4: فرضیه رد شد (نیمهٔ اول منفی، n کم، ناپایدار).

این اسکریپت نقطهٔ محافظه‌کارِ M30 (DD پایین) را عمیق می‌سنجد:
  ۱) چهار چارَک زمانی + دو نیمه.
  ۲) مقاومت به هزینه (اسپردِ ۲×).
  ۳) مقاومت به پارامتر (همسایگی).
  ۴) همبستگیِ pnl روزانه با S67(M15)/S79(M5)/S80(H1) → استقلالِ پرتفوی.
  ۵) تحلیلِ سرمایهٔ کم (۵۰$): آیا SL=120pip=12$ روی ۵۰$ قابلِ‌مدیریت است؟
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

SE.ASSETS['XAUUSD_M30'] = dict(file='data/XAUUSD_M30.csv', pip=0.10, contract=100.0,
                               pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
SE.ASSETS['XAUUSD_H1'] = dict(file='data/XAUUSD_H1.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=4.0, comm=0.0, slip_pip=0.5)
ASSET = 'XAUUSD_M30'

# نقطهٔ نهاییِ محافظه‌کار (DD پایین، PF بالا، هر دو نیمه مثبت):
EMA_FAST, EMA_SLOW, RSI_P, RSI_TH = 20, 100, 14, 35
SL_PIP, TP_PIP, MAX_HOLD = 120, 1200, 144


def ema(x, s): return pd.Series(x).ewm(span=s, adjust=False).mean().values
def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def build(df, rsi_th=RSI_TH):
    c = df['close'].values; n = len(df)
    ls = np.nan_to_num((ema(c, EMA_FAST) > ema(c, EMA_SLOW)) & (rsi(c, RSI_P) < rsi_th)).astype(bool)
    return ls, np.zeros(n, bool)


def run(asset, sl=SL_PIP, tp=TP_PIP, hold=MAX_HOLD, rsi_th=RSI_TH, spread=None):
    df = SE.load_data(SE.ASSETS[asset]['file'])
    old = SE.ASSETS[asset]['spread_pip']
    if spread is not None:
        SE.ASSETS[asset]['spread_pip'] = spread
    ls, ss = build(df, rsi_th)
    tr = SE.simulate_trades(df, ls, ss, sl, tp, asset, max_hold=hold)
    s, eq = SE.run_capital(tr, asset, compounding=False)
    SE.ASSETS[asset]['spread_pip'] = old
    return tr, s, df


def daily_pnl(tr, df):
    """جمعِ pnl_pip بر حسبِ روز (برای همبستگیِ پرتفوی)."""
    if len(tr) == 0:
        return pd.Series(dtype=float)
    d = df['dt'].dt.floor('D').values
    days = d[tr['exit_bar'].values]
    return pd.Series(tr['pnl_pip'].values, index=pd.to_datetime(days)).groupby(level=0).sum()


print("#" * 100)
print("  اعتبارسنجیِ عمیقِ کاندیدِ M30 (S81): EMA20>EMA100 + RSI(14)<35, SL=120 TP=1200 hold=144")
print("#" * 100)

tr, s, df = run(ASSET)
n = len(df); half = n // 2
print(SE.summary_line('XAU_M30', s))

print("\n[۱] دو نیمه:")
for name, a, b in [('IS نیمهٔ اول', 0, half), ('OOS نیمهٔ دوم', half, n)]:
    trh = tr[(tr['entry_bar'] >= a) & (tr['entry_bar'] < b)]
    sh, _ = SE.run_capital(trh, ASSET, compounding=False)
    print(f"    {name}: net={sh['net_profit']:+8.0f}$ n={sh['n_trades']:4d} "
          f"WR={sh['win_rate']:.0f}% PF={sh['profit_factor']:.2f} DD={sh['max_dd_pct']:.1f}%")

print("\n[۲] چهار چارَک:")
q = n // 4
for qi in range(4):
    a, b = qi*q, (qi+1)*q if qi < 3 else n
    trq = tr[(tr['entry_bar'] >= a) & (tr['entry_bar'] < b)]
    sq, _ = SE.run_capital(trq, ASSET, compounding=False)
    print(f"    Q{qi+1}: net={sq['net_profit']:+8.0f}$ n={sq['n_trades']:4d} "
          f"WR={sq['win_rate']:.0f}% PF={sq['profit_factor']:.2f}")

print("\n[۳] مقاومت به هزینه (اسپردِ ۲× = ۸pip):")
_, s2x, _ = run(ASSET, spread=8.0)
print(f"    net={s2x['net_profit']:+8.0f}$  (اصلی {s['net_profit']:+.0f}$)  "
      f"{'✅ هنوز سودده' if s2x['net_profit'] > 0 else '❌'}")

print("\n[۴] مقاومت به پارامتر (همسایگی):")
for rsi_th in [30, 35, 40]:
    for sl in [80, 120, 180]:
        _, sp, _ = run(ASSET, sl=sl, rsi_th=rsi_th)
        flag = '✅' if sp['net_profit'] > 0 else '❌'
        print(f"    RSI<{rsi_th} SL={sl}: net={sp['net_profit']:+8.0f}$ PF={sp['profit_factor']:.2f} {flag}")

print("\n[۵] استقلال — همبستگیِ pnl روزانه با S80(H1):")
tr80, s80, df80 = run('XAUUSD_H1', sl=150, tp=700, hold=72, rsi_th=40)
d_m30 = daily_pnl(tr, df)
d_h1 = daily_pnl(tr80, df80)
common = d_m30.index.intersection(d_h1.index)
if len(common) > 30:
    corr = np.corrcoef(d_m30.reindex(common).fillna(0), d_h1.reindex(common).fillna(0))[0, 1]
    print(f"    corr(M30, H1) = {corr:+.3f}  (روزهای مشترک={len(common)})  "
          f"{'✅ مستقل' if abs(corr) < 0.3 else '⚠️ همبسته'}")

print("\n[۶] تحلیلِ سرمایهٔ کم (User Note: آیا برای ۵۰$ مناسب است؟):")
for cap in [50, 100, 500, 1000, 10000]:
    _, sc = SE.run_capital(tr, ASSET, initial_capital=cap, risk_pct=1.0, compounding=False)[0:2] \
        if False else (None, None)
    sc, _ = SE.run_capital(tr, ASSET, initial_capital=cap, risk_pct=1.0, compounding=False)
    # ریسکِ واقعیِ هر معامله با MIN_LOT روی این سرمایه:
    risk_min_lot = SL_PIP * SE.ASSETS[ASSET]['pip_value'] * SE.MIN_LOT  # زیانِ SL با 0.01 لات
    risk_pct_real = risk_min_lot / cap * 100
    print(f"    سرمایه {cap:6d}$: net={sc['net_profit']:+9.0f}$ ({sc['return_pct']:+.0f}%) "
          f"avgLot={sc['avg_lot']:.3f}  DD={sc['max_dd_pct']:.1f}%  "
          f"| ریسکِ SL با MIN_LOT(0.01)={risk_min_lot:.0f}$ = {risk_pct_real:.0f}% از سرمایه")
print("#" * 100)
