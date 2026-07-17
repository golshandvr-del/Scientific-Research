"""
explore_m30_portfolio_role.py — نقشِ درستِ M30 در پرتفوی + همبستگی با همهٔ لایه‌ها
================================================================================
> قانونِ شمارهٔ ۱: هدف فقط «سودِ خالصِ بیشتر». تعریف = XAUUSD + EURUSD.

کشفِ قبلی: corr(M30, H1) = +0.75 (همبسته). پس نمی‌توان M30 و H1 را ساده جمع کرد.
سوال: نقشِ درستِ M30 چیست؟
  گزینهٔ A: M30 را به‌جای H1 بگذاریم (S80 حذف، S81=M30 جایگزین). سودِ M30 (14.3k) > H1 (10k).
  گزینهٔ B: هر دو نگه‌داریم اما تخصیصِ سرمایهٔ مستقل (dedup سود از راهِ سرمایهٔ جدا).
این اسکریپت همبستگیِ M30 با M15(S67-مانند)/M5(S79)/H1(S80) را می‌سنجد و سودِ
پرتفوی را در دو سناریو (با/بدون H1) مقایسه می‌کند.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

for a, f in [('XAUUSD_M30', 'data/XAUUSD_M30.csv'), ('XAUUSD_H1', 'data/XAUUSD_H1.csv'),
             ('XAUUSD_M5', 'data/XAUUSD_M5.csv'), ('XAUUSD', 'data/XAUUSD_M15.csv')]:
    SE.ASSETS[a] = dict(file=f, pip=0.10, contract=100.0, pip_value=10.0,
                        spread_pip=4.0, comm=0.0, slip_pip=0.5)


def ema(x, s): return pd.Series(x).ewm(span=s, adjust=False).mean().values
def rsi(x, p):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def trend_pullback(asset, ema_f, ema_s, rsi_p, rsi_th, sl, tp, hold):
    df = SE.load_data(SE.ASSETS[asset]['file'])
    c = df['close'].values; n = len(df)
    ls = np.nan_to_num((ema(c, ema_f) > ema(c, ema_s)) & (rsi(c, rsi_p) < rsi_th)).astype(bool)
    tr = SE.simulate_trades(df, ls, np.zeros(n, bool), sl, tp, asset, max_hold=hold)
    s, _ = SE.run_capital(tr, asset, compounding=False)
    return tr, s, df


def daily_pnl(tr, df):
    if len(tr) == 0:
        return pd.Series(dtype=float)
    days = df['dt'].dt.floor('D').values[tr['exit_bar'].values]
    return pd.Series(tr['pnl_pip'].values, index=pd.to_datetime(days)).groupby(level=0).sum()


# لایه‌ها با پارامترهای برندهٔ خودشان
print("#" * 100)
print("  نقشِ M30 در پرتفوی + همبستگی با لایه‌ها")
print("#" * 100)
tr_m30, s_m30, df_m30 = trend_pullback('XAUUSD_M30', 20, 100, 14, 35, 120, 1200, 144)
tr_h1, s_h1, df_h1 = trend_pullback('XAUUSD_H1', 20, 100, 14, 40, 150, 700, 72)
tr_m5, s_m5, df_m5 = trend_pullback('XAUUSD_M5', 20, 100, 21, 35, 60, 150, 48)  # ~S79
tr_m15, s_m15, df_m15 = trend_pullback('XAUUSD', 20, 100, 14, 35, 100, 500, 96)  # trend-pullback روی M15

print(f"\n  M30:  net={s_m30['net_profit']:+8.0f}$ n={s_m30['n_trades']:4d} PF={s_m30['profit_factor']:.2f} DD={s_m30['max_dd_pct']:.1f}%")
print(f"  H1 :  net={s_h1['net_profit']:+8.0f}$ n={s_h1['n_trades']:4d} PF={s_h1['profit_factor']:.2f} DD={s_h1['max_dd_pct']:.1f}%")
print(f"  M5 :  net={s_m5['net_profit']:+8.0f}$ n={s_m5['n_trades']:4d} PF={s_m5['profit_factor']:.2f}")
print(f"  M15:  net={s_m15['net_profit']:+8.0f}$ n={s_m15['n_trades']:4d} PF={s_m15['profit_factor']:.2f}")

d = {'M30': daily_pnl(tr_m30, df_m30), 'H1': daily_pnl(tr_h1, df_h1),
     'M5': daily_pnl(tr_m5, df_m5), 'M15': daily_pnl(tr_m15, df_m15)}
print("\n  ماتریسِ همبستگیِ pnl روزانه:")
keys = list(d.keys())
print("        " + "  ".join(f"{k:>6s}" for k in keys))
for k1 in keys:
    row = []
    for k2 in keys:
        common = d[k1].index.intersection(d[k2].index)
        if len(common) > 20:
            corr = np.corrcoef(d[k1].reindex(common).fillna(0), d[k2].reindex(common).fillna(0))[0, 1]
            row.append(f"{corr:+.2f}")
        else:
            row.append("  -  ")
    print(f"  {k1:>4s}: " + "  ".join(f"{x:>6s}" for x in row))

print("\n  تحلیلِ نقش:")
print(f"    • S80(H1) فعلی = +{int(s_h1['net_profit'])}$؛ کاندیدِ M30 = +{int(s_m30['net_profit'])}$")
print(f"    • corr(M30,H1) بالاست ⇒ نمی‌توان هر دو را جمع کرد (double-count).")
print(f"    • اگر M30 جایگزینِ H1 شود: سودِ لایهٔ swing از {int(s_h1['net_profit'])}$ → {int(s_m30['net_profit'])}$ "
      f"(+{int(s_m30['net_profit']-s_h1['net_profit'])}$، DD کمتر).")
print("#" * 100)
