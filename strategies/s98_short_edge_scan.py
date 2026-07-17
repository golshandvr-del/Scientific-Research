"""
s98_short_edge_scan.py — جاروبِ سیستماتیک برای یافتنِ لبهٔ SHORTِ سودده (User Note)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر». سودِ خالص = XAUUSD + EURUSD.

درسِ s97: رویدادِ ساده «قطعِ MAها» drift نزولیِ ~۴pip می‌دهد اما اسپردِ ۴pip طلا
آن را می‌بلعد ⇒ ضرر. برای SHORTِ سودده باید یا (الف) drift نزولیِ بزرگ‌تر (>>اسپرد)
یافت، یا (ب) RR مثبت با WR کافی ساخت.

این اسکریپت پیشنهادِ صریحِ User Note را پیاده می‌کند: «تستی بساز که اعدادِ مختلف،
تعدادِ مختلف و انواعِ مختلفِ MA را بکشد و طبقِ آن‌ها روند تشخیص دهد و با واقعیتِ
روندِ بعدی مطابقت دهد و امتیاز بدهد.» — امتیاز = میانگینِ forward-return نزولی
(هرچه منفی‌تر، لبهٔ SHORTِ قوی‌تر) + سپس بک‌تستِ واقعیِ نامزدهای برتر.
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np
import pandas as pd
import indicators as ind
import scalp_engine as se
import itertools

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')

def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)

def ma(c, kind, p):
    return (ind.ema(c, p) if kind == 'e' else ind.sma(c, p)).values

def scan_events(df):
    """
    جاروبِ رویدادهای نامزدِ SHORT و امتیازدهی بر اساسِ forward-return.
    امتیاز = میانگینِ forward pip در افق کوتاه (باید منفیِ معنادار باشد).
    گزارش برای چند افق تا ببینیم لبه کوتاه‌مدت است یا بلندمدت.
    """
    c = df['close']; price = c.values
    atr = ind.atr(df, 14).values
    rsi = ind.rsi(c, 14).values
    _, _, macdh = ind.macd(c)
    macdh = macdh.values
    adx_, pdi, mdi = ind.adx(df, 14)
    adx_ = adx_.values; pdi = pdi.values; mdi = mdi.values

    # forward returns
    HZs = [2, 4, 6, 8, 12]
    fwd = {}
    for HZ in HZs:
        f = np.full(len(df), np.nan)
        f[:-HZ] = (price[HZ:] - price[:-HZ]) / 0.10
        fwd[HZ] = f

    events = {}

    # -- گروهِ ۱: breakdown مومنتوم‌محور (drift نزولیِ واقعی، نه mean-reversion) --
    ll20 = pd.Series(df['low']).rolling(20).min().shift(1).values
    events['break_LL20'] = price < ll20                       # شکستِ کفِ ۲۰
    ll50 = pd.Series(df['low']).rolling(50).min().shift(1).values
    events['break_LL50'] = price < ll50
    events['macdh_neg_cross'] = (np.r_[np.nan, macdh[:-1]] > 0) & (macdh < 0)
    events['di_bear_cross'] = (np.r_[np.nan, (pdi-mdi)[:-1]] > 0) & ((pdi-mdi) < 0) & (adx_ > 20)
    events['rsi_break50_dn'] = (np.r_[np.nan, rsi[:-1]] > 50) & (rsi < 50)

    # -- گروهِ ۲: ترکیبِ MA (حرفِ تریدر) --
    ema20 = ma(c,'e',20); ema50 = ma(c,'e',50); sma50 = ma(c,'s',50); sma200 = ma(c,'s',200)
    mm = np.column_stack([ema20,ema50,sma50,sma200]); mid = np.nanmean(mm,axis=1); bot = np.nanmin(mm,axis=1)
    events['cross_mid_dn'] = (np.r_[False,price[:-1]>mid[:-1]]) & (price<mid) & (pd.Series(ema20).diff().values<0)
    events['cross_all_dn'] = (np.r_[False,price[:-1]>np.nanmax(mm,axis=1)[:-1]]) & (price<bot)
    # ترتیبِ نزولیِ کاملِ ریبون + قیمت زیرِ همه (روندِ نزولیِ تثبیت‌شده)
    order_dn = (ema20<ema50)&(ema50<sma50)&(sma50<sma200)
    events['ribbon_stacked_dn'] = order_dn & (price<ema20)
    # تازه‌واردِ ترتیبِ نزولی (فشردگی سپس گسترش)
    events['ribbon_newstack_dn'] = order_dn & np.r_[False, ~order_dn[:-1]]

    print(f"\n{'رویداد':24s} {'n':>6s}  " + "  ".join(f"fwd{h}" for h in HZs))
    scores = []
    for name, ev in events.items():
        ev = ev & ~np.isnan(atr)
        n = int(np.nansum(ev))
        if n < 30:
            print(f"{name:24s} {n:6d}  (کم)")
            continue
        row = []
        for HZ in HZs:
            m = ev & ~np.isnan(fwd[HZ])
            row.append(fwd[HZ][m].mean())
        best = min(row)
        scores.append((name, n, row, best))
        print(f"{name:24s} {n:6d}  " + "  ".join(f"{v:+6.1f}" for v in row))
    return events, scores, HZs

def backtest_top(df, events, top_names):
    print(f"\n{'='*70}\nبک‌تستِ واقعیِ نامزدهای برترِ SHORT (اسپرد ۴pip، ۱۰k$/۱٪)\n{'='*70}")
    long = np.zeros(len(df), bool)
    best_result = None
    for name in top_names:
        ev = events[name]
        print(f"\n[{name}] n_raw={int(ev.sum())}")
        for sl, tp, hold in [(20,40,12),(25,50,16),(30,60,24),(40,80,32),(30,90,48),(20,60,24)]:
            tr = se.simulate_trades(df, long, ev, sl_pip=sl, tp_pip=tp, asset='XAUUSD',
                                    max_hold=hold, allow_overlap=False)
            if len(tr) < 5: continue
            st = se.run_capital(tr,'XAUUSD',10000,1.0,False)[0]
            mid = len(df)//2
            t1=tr[tr['entry_bar']<mid]; t2=tr[tr['entry_bar']>=mid]
            n1=se.run_capital(t1,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t1) else 0
            n2=se.run_capital(t2,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t2) else 0
            flag = "✅" if st['net_profit']>0 and n1>0 and n2>0 else ("+" if st['net_profit']>0 else "")
            print(f"  SL{sl}/TP{tp}/H{hold:2d}: net={st['net_profit']:+8.0f}$ n={st['n_trades']:4d} "
                  f"WR={st['win_rate']:4.1f}% PF={st['profit_factor']:.2f} H1={n1:+.0f} H2={n2:+.0f} {flag}")
            if st['net_profit']>0 and (best_result is None or st['net_profit']>best_result[1]):
                best_result=(f"{name} SL{sl}/TP{tp}/H{hold}", st['net_profit'], n1, n2)
    return best_result

def main():
    df_full = load()
    df_2y = df_full.iloc[-2*365*24*4:].reset_index(drop=True)
    print(f"\n{'#'*70}\n### اسکنِ لبهٔ SHORT — ۲ سالِ اخیر ({len(df_2y)} کندل)\n{'#'*70}")
    ev2, sc2, HZs = scan_events(df_2y)
    top = [n for n,_,_,_ in sorted(sc2, key=lambda x:x[3])[:5]]
    print("\nنامزدهای برتر (منفی‌ترین forward):", top)
    br = backtest_top(df_2y, ev2, top)
    print("\n>>> بهترین نتیجهٔ سودده (۲ سال):", br)

if __name__ == '__main__':
    main()
