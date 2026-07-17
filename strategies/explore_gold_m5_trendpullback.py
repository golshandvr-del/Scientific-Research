"""
explore_gold_m5_trendpullback.py — Trend-Pullback روی XAUUSD M5 با نگهداریِ بلند (User Note 2)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» — نه WR.
> **تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.**

کشفِ کلیدیِ اکتشافِ قبل: روی M5 طلا اسکالپِ کوتاه (۶–۱۲ کندل) سود نمی‌دهد چون
هزینه (اسپرد+کمیسیون) غالب است؛ اما «buy-dip در روندِ صعودی» با نگهداریِ
بلندتر (K=24 کندل ≈ ۲ ساعت) میانگینِ net مثبت می‌شود (+۰.۱۶$/واحد). یعنی لبهٔ
طلا از جنسِ momentum/swing است نه اسکالپِ سریع — دقیقاً چرایی موفقیتِ S67 در M15.

این اسکریپت این بینش را روی موتورِ نو با نگهداریِ بلند و فیلترهای سخت‌گیرانه
جارو می‌کند تا ببیند آیا به سودِ خالصِ واقعی (پس از هزینهٔ کامل) تبدیل می‌شود.
منطق (forward-safe): روندِ کلانِ صعودی (EMA_fast>EMA_slow) + pullback (RSI پایین)،
Long، TP بزرگ‌تر از SL (سوارِ روند)، max_hold بلند.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from engine import scalp_engine as SE

SE.ASSETS['XAUUSD_M5'] = dict(file='data/XAUUSD_M5.csv', pip=0.10, contract=100.0,
                              pip_value=10.0, spread_pip=2.0, comm=7.0, slip_pip=0.5)
ASSET = 'XAUUSD_M5'


def ema(x, s):
    return pd.Series(x).ewm(span=s, adjust=False).mean().values


def rsi(x, p=14):
    d = np.diff(x, prepend=x[0]); up = np.where(d > 0, d, 0); dn = np.where(d < 0, -d, 0)
    ru = pd.Series(up).ewm(alpha=1/p, adjust=False).mean().values
    rd = pd.Series(dn).ewm(alpha=1/p, adjust=False).mean().values
    return 100 - 100 / (1 + ru / (rd + 1e-12))


def main():
    df = SE.load_data(SE.ASSETS[ASSET]['file'])
    n = len(df); half = n // 2
    c = df['close'].values
    print("=" * 100)
    print("  Trend-Pullback روی XAUUSD M5 (نگهداریِ بلند) — موتورِ نو (IS/OOS دو-نیمه)")
    print("=" * 100)

    best = []
    for ef, es in ((50, 200), (100, 400), (20, 100)):
        e_f = ema(c, ef); e_s = ema(c, es)
        uptrend = e_f > e_s
        for rp in (14, 21):
            r = rsi(c, rp)
            for rsi_th in (30, 35, 40):
                dip = r < rsi_th
                long_sig = np.nan_to_num(uptrend & dip).astype(bool)
                if long_sig.sum() < 300:
                    continue
                short = np.zeros(n, bool)
                for sl in (30, 50, 80):
                    for tp in (50, 80, 120):
                        for mh in (24, 48, 72):
                            tr = SE.simulate_trades(df, long_sig, short, sl, tp, ASSET, max_hold=mh)
                            if len(tr) < 200:
                                continue
                            tr_is = tr[tr['entry_bar'] < half]
                            tr_oos = tr[tr['entry_bar'] >= half]
                            if len(tr_is) < 60 or len(tr_oos) < 60:
                                continue
                            s_is, _ = SE.run_capital(tr_is, ASSET)
                            s_oos, _ = SE.run_capital(tr_oos, ASSET)
                            if s_is['net_profit'] > 0 and s_oos['net_profit'] > 0:
                                s_all, _ = SE.run_capital(tr, ASSET)
                                best.append((s_all['net_profit'], ef, es, rp, rsi_th, sl, tp, mh,
                                             s_is['net_profit'], s_oos['net_profit'],
                                             s_all['n_trades'], s_all['win_rate'],
                                             s_all['profit_factor'], s_all['max_dd_pct']))

    best.sort(reverse=True)
    print(f"\n  === لبه‌های دو-نیمه-مثبت — {len(best)} ترکیب ===")
    if not best:
        print("   هیچ ترکیبِ دو-نیمه-مثبتی یافت نشد.")
    else:
        print(f"  {'netAll':>8} {'ef/es':>8}{'rp':>3}{'rTh':>4}{'SL':>4}{'TP':>4}{'mh':>4} | {'IS':>7}{'OOS':>8} | {'n':>5}{'WR':>5}{'PF':>5}{'DD%':>6}")
        for r in best[:20]:
            netA, ef, es, rp, rt, sl, tp, mh, isp, oosp, ntr, wr, pf, dd = r
            print(f"  {netA:+8.0f} {ef:>3}/{es:<4}{rp:>3}{rt:>4}{sl:>4}{tp:>4}{mh:>4} | "
                  f"{isp:+7.0f}{oosp:+8.0f} | {ntr:>5}{wr:>5.0f}{pf:>5.2f}{dd:>6.1f}")
    print("=" * 100)


if __name__ == '__main__':
    main()
