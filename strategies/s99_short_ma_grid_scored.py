"""
s99_short_ma_grid_scored.py — «سیستمِ امتیازدهیِ MA» کاملِ User Note برای SHORT
================================================================================
> # قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر». سودِ خالص = XAUUSD + EURUSD.

پیاده‌سازیِ دقیقِ پیشنهادِ User Note:
> «یه تست اصلا میتونیم بسازیم که اعداد مختلف، تعداد مختلف و انواع ma رو بکشه و
>  طبقشون روند تشخیص بده و بعد با واقعیت روند بعدی مطابقت بده و طبق درستیش امتیاز
>  بده.»

سه اهرمِ اضافیِ نجاتِ SHORT هم آزموده می‌شوند (چون درسِ s97/s98 نشان داد TP ثابت
با اسپردِ ۴pip و V-recovery طلا شکست می‌خورد):
  ۱) خروجِ trailing/breakeven (به‌جای TP ثابت) — گرفتنِ سودِ سریع پیش از بازگشت.
  ۲) فیلترِ سشن (شاید SHORT فقط در ساعاتِ خاص کار کند).
  ۳) جاروبِ گستردهٔ اعداد و انواعِ MA (e/s، دوره‌های مختلف، تعدادِ خطوط).
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
    df = pd.read_csv(DATA); df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)

def maval(c, kind, p):
    return (ind.ema(c, p) if kind == 'e' else ind.sma(c, p)).values

# ------------------------------------------------------------------
# بخش ۱: جاروبِ اعداد/انواع/تعدادِ MA با امتیازِ forward-return نزولی
# ------------------------------------------------------------------
def grid_score(df):
    c = df['close']; price = c.values
    HZ = 6
    fwd = np.full(len(df), np.nan); fwd[:-HZ] = (price[HZ:]-price[:-HZ])/0.10

    # مجموعه‌های نامزدِ MA: (نوع، دوره‌ها)
    candidates = []
    for kinds in [('e','e','e'), ('s','s','s'), ('e','e','s')]:
        for combo in [(10,20,50),(20,50,100),(20,50,200),(9,21,50),(5,13,34),(50,100,200)]:
            candidates.append((kinds, combo))
    # ۵-تایی (حرفِ تریدر)
    candidates.append((('e','e','s','s','e'),(20,50,50,200,100)))

    print(f"{'MA-set':32s} {'n_dn':>6s} {'fwd6_on_dn':>10s} {'t':>6s}")
    results = []
    for kinds, periods in candidates:
        mas = [maval(c, k, p) for k, p in zip(kinds, periods)]
        M = np.column_stack(mas)
        mid = np.nanmean(M, axis=1)
        # سیگنالِ «قطعِ رو به پایینِ میانهٔ بسته» (خطِ چارت از بالا قطع می‌کند)
        ev = (np.r_[False, price[:-1] > mid[:-1]]) & (price < mid)
        m = ev & ~np.isnan(fwd)
        if m.sum() < 50: continue
        vals = fwd[m]
        t = vals.mean()/(vals.std()/np.sqrt(len(vals))+1e-12)
        label = "+".join(f"{k}{p}" for k,p in zip(kinds,periods))
        results.append((label, m.sum(), vals.mean(), t, kinds, periods, ev))
        print(f"{label:32s} {m.sum():6d} {vals.mean():+10.2f} {t:+6.2f}")
    return sorted(results, key=lambda x: x[2])  # منفی‌ترین اول

# ------------------------------------------------------------------
# بخش ۲: خروجِ trailing به‌جای TP ثابت (نجاتِ سود پیش از V-recovery)
# ------------------------------------------------------------------
def backtest_trailing(df, ev, label):
    long = np.zeros(len(df), bool)
    print(f"\n[{label}] trailing/BE sweep, n_raw={int(ev.sum())}")
    best = None
    for sl, be, trail, hold in [(30,15,15,16),(25,12,12,12),(40,20,20,24),
                                 (30,10,10,8),(50,25,25,32),(25,15,10,16)]:
        tr = se.simulate_trades(df, long, ev, sl_pip=sl, tp_pip=200, asset='XAUUSD',
                                max_hold=hold, allow_overlap=False,
                                be_trigger_pip=be, trail_pip=trail)
        if len(tr) < 5: continue
        st = se.run_capital(tr,'XAUUSD',10000,1.0,False)[0]
        mid=len(df)//2; t1=tr[tr['entry_bar']<mid]; t2=tr[tr['entry_bar']>=mid]
        n1=se.run_capital(t1,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t1) else 0
        n2=se.run_capital(t2,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t2) else 0
        flag="✅" if st['net_profit']>0 and n1>0 and n2>0 else ("+" if st['net_profit']>0 else "")
        print(f"  SL{sl}/BE{be}/TR{trail}/H{hold:2d}: net={st['net_profit']:+8.0f}$ "
              f"n={st['n_trades']:4d} WR={st['win_rate']:4.1f}% PF={st['profit_factor']:.2f} "
              f"H1={n1:+.0f} H2={n2:+.0f} {flag}")
        if st['net_profit']>0 and (best is None or st['net_profit']>best[1]):
            best=(f"{label} SL{sl}/BE{be}/TR{trail}/H{hold}",st['net_profit'],n1,n2)
    return best

# ------------------------------------------------------------------
# بخش ۳: فیلترِ سشن روی بهترین نامزد
# ------------------------------------------------------------------
def backtest_session(df, ev, label):
    hours = df['dt'].dt.hour.values
    long = np.zeros(len(df), bool)
    print(f"\n[{label}] فیلترِ سشن (SL30/BE15/TR15/H16):")
    best=None
    sessions = {'همه':range(24),'آسیا 0-7':range(0,8),'لندن 7-13':range(7,14),
                'نیویورک 13-21':range(13,22),'لندن+نیویورک 12-20':range(12,21)}
    for sname, hrs in sessions.items():
        mask = ev & np.isin(hours, list(hrs))
        if mask.sum()<10: continue
        tr=se.simulate_trades(df,long,mask,sl_pip=30,tp_pip=200,asset='XAUUSD',
                              max_hold=16,allow_overlap=False,be_trigger_pip=15,trail_pip=15)
        if len(tr)<5: continue
        st=se.run_capital(tr,'XAUUSD',10000,1.0,False)[0]
        mid=len(df)//2; t1=tr[tr['entry_bar']<mid]; t2=tr[tr['entry_bar']>=mid]
        n1=se.run_capital(t1,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t1) else 0
        n2=se.run_capital(t2,'XAUUSD',10000,1.0,False)[0]['net_profit'] if len(t2) else 0
        flag="✅" if st['net_profit']>0 and n1>0 and n2>0 else ("+" if st['net_profit']>0 else "")
        print(f"  {sname:20s}: net={st['net_profit']:+8.0f}$ n={st['n_trades']:4d} "
              f"WR={st['win_rate']:4.1f}% H1={n1:+.0f} H2={n2:+.0f} {flag}")
        if st['net_profit']>0 and (best is None or st['net_profit']>best[1]):
            best=(f"{label}/{sname}",st['net_profit'],n1,n2)
    return best

def main():
    df_full = load()
    df = df_full.iloc[-2*365*24*4:].reset_index(drop=True)
    print(f"### ۲ سالِ اخیر ({len(df)} کندل): {df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()}\n")
    print("="*70,"\nبخش ۱: جاروبِ اعداد/انواع/تعدادِ MA (امتیاز = fwd6 روی رویدادِ نزولی)\n","="*70)
    res = grid_score(df)
    print("\nبرترین ۳ مجموعهٔ MA (منفی‌ترین forward):")
    for r in res[:3]: print(f"  {r[0]}: fwd={r[2]:+.2f}pip t={r[3]:+.2f}")

    print("\n","="*70,"\nبخش ۲: خروجِ trailing/BE روی برترین نامزدها\n","="*70)
    overall_best=None
    for r in res[:3]:
        b=backtest_trailing(df, r[6], r[0])
        if b and (overall_best is None or b[1]>overall_best[1]): overall_best=b

    print("\n","="*70,"\nبخش ۳: فیلترِ سشن روی برترین نامزد\n","="*70)
    b=backtest_session(df, res[0][6], res[0][0])
    if b and (overall_best is None or b[1]>overall_best[1]): overall_best=b

    print("\n>>> بهترین نتیجهٔ سوددهِ SHORT (۲ سال):", overall_best)

if __name__ == '__main__':
    main()
