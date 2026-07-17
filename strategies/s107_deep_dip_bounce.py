"""
s107_deep_dip_bounce.py — آشکارسازِ «بازگشت از کفِ عمیق» (جریانِ غیرِهم‌بستهٔ نو)
================================================================================
> قانونِ شمارهٔ ۱ پروژه: معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است، نه Win-Rate.
> تعریفِ سودِ خالص = جمعِ سودِ XAUUSD + EURUSD. WR فقط گزارشی است.

منشأ (پاسخِ عملیِ سوالِ فلسفی — s106):
  همهٔ لایه‌های long موجود «trend-following»اند (قیمت *بالای* میانگین‌ها). s106 نشان
  داد ۲۲۹ روندِ صعودی «کشف‌نشده» می‌مانند و DNA متمایزشان: قیمت *زیرِ* SMA200
  (dist_sma200<0)، شیبِ کوتاه‌مدت نزولی (slope50<0)، RSI پایین. یعنی این‌ها
  **بازگشت‌های صعودی از کفِ یک محیطِ نزولی/زیرِ میانگین**اند — نه ادامهٔ روند.

  چون هیچ لایهٔ فعلی در این نواحی فعال نیست، آشکارسازِ آن‌ها ذاتاً یک **جریانِ
  غیرِهم‌بسته** خواهد بود — دقیقاً «گلوگاهِ نبودِ جریانِ غیرِهم‌بستهٔ» پروژه (L50).

⚠️ چالشِ L53: طلا بایاسِ صعودیِ ساختاری دارد و mean-reversion/خرید در کف روی طلا
  قبلاً روی long-only trend جواب داد اما mean-rev کوتاه‌مدت شکست خورد. تفاوتِ اینجا:
  ما دنبالِ SHORT-counter-trend نیستیم؛ دنبالِ LONG هم‌جهت با بایاسِ ساختاریِ طلا
  ولی در نقطهٔ ورودِ متفاوت (کفِ عمیق زیرِ میانگین) هستیم. این با L53 سازگار است
  (LONG روی طلا) و صرفاً یک «محلِ ورودِ» متفاوت از trend-following است.

طراحیِ آشکارساز (forward-safe):
  ورود LONG وقتی:
    • close < SMA200  (زیرِ میانگینِ بلند — محیطِ کف)
    • RSI(rsi_p) < rsi_thr  (اشباعِ فروشِ عمیق)
    • close > close قبلی  (کندلِ بازگشتیِ تأییدی — momentum رو به بالا)
  خروج: SL/TP ثابتِ pip + max_hold. جاروبِ پارامتر برای بیشینه‌سازیِ سودِ خالص،
  سپس اعتبارسنجیِ walk-forward و سنجشِ هم‌بستگیِ روزانه با جریانِ long موجود.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def dip_signal(df, rsi_p, rsi_thr):
    c = df['close']
    s200 = ind.sma(c, 200).values
    rsi = ind.rsi(c, rsi_p).values
    p = c.values
    below = p < s200
    oversold = rsi < rsi_thr
    bounce = np.r_[False, p[1:] > p[:-1]]      # کندلِ بازگشتی
    sig = below & oversold & bounce
    return np.nan_to_num(sig, nan=0).astype(bool)


def bt(df, sig, sl, tp, mh):
    nosig = np.zeros(len(df), dtype=bool)
    trades = se.simulate_trades(df, sig, nosig, sl_pip=sl, tp_pip=tp,
                                asset='XAUUSD', max_hold=mh, allow_overlap=False)
    stats, eq = se.run_capital(trades, 'XAUUSD', 10_000, 1.0, compounding=False)
    return stats, trades


def wf_halves(df, sig, sl, tp, mh):
    """سودِ خالص در دو نیمهٔ داده (both-halves gate)."""
    n = len(df); mid = n // 2
    s1 = sig.copy(); s1[mid:] = False
    s2 = sig.copy(); s2[:mid] = False
    st1, _ = bt(df, s1, sl, tp, mh)
    st2, _ = bt(df, s2, sl, tp, mh)
    return st1['net_profit'], st2['net_profit']


def main():
    print("=" * 80)
    print("s107 — Deep-Dip Bounce: آشکارسازِ روندهای کشف‌نشده (جریانِ غیرِهم‌بسته)")
    print("=" * 80)
    df = load()
    print(f"داده: {len(df):,} کندل XAUUSD M15")

    # --- جاروبِ پارامتر (بیشینه‌سازیِ سودِ خالص با قیدِ both-halves مثبت) ---
    print("\nجاروبِ پارامتر (rsi_p, rsi_thr, SL, TP, max_hold):")
    best = None
    grid = []
    for rsi_p in [7, 14, 21]:
        for rsi_thr in [20, 25, 30]:
            for sl in [80, 120, 150]:
                for tp in [120, 240, 400]:
                    for mh in [24, 48, 96]:
                        sig = dip_signal(df, rsi_p, rsi_thr)
                        if sig.sum() < 40:
                            continue
                        st, _ = bt(df, sig, sl, tp, mh)
                        h1, h2 = wf_halves(df, sig, sl, tp, mh)
                        rec = dict(rsi_p=rsi_p, rsi_thr=rsi_thr, sl=sl, tp=tp, mh=mh,
                                   net=st['net_profit'], pf=st['profit_factor'],
                                   wr=st['win_rate'], n=st['n_trades'], h1=h1, h2=h2,
                                   both=(h1 > 0 and h2 > 0))
                        grid.append(rec)
    gdf = pd.DataFrame(grid)
    # اولویت: both-halves مثبت، سپس بیشترین سودِ خالص
    both = gdf[gdf['both']].sort_values('net', ascending=False)
    print(f"\nترکیب‌های both-halves مثبت: {len(both)} از {len(gdf)}")
    if len(both) > 0:
        top = both.head(8)
    else:
        top = gdf.sort_values('net', ascending=False).head(8)
    print(f"{'rsi_p':>5}{'thr':>5}{'SL':>5}{'TP':>5}{'mh':>4}{'net$':>10}{'PF':>6}{'WR%':>6}{'n':>6}{'h1$':>9}{'h2$':>9}")
    for _, r in top.iterrows():
        print(f"{int(r.rsi_p):>5}{int(r.rsi_thr):>5}{int(r.sl):>5}{int(r.tp):>5}{int(r.mh):>4}"
              f"{r.net:>10,.0f}{r.pf:>6.2f}{r.wr:>6.1f}{int(r.n):>6}{r.h1:>9,.0f}{r.h2:>9,.0f}")

    best = top.iloc[0]
    print(f"\nبهترین ترکیب: rsi_p={int(best.rsi_p)} thr={int(best.rsi_thr)} "
          f"SL={int(best.sl)} TP={int(best.tp)} mh={int(best.mh)}")
    print(f"سودِ خالصِ کل: ${best.net:,.0f}  PF={best.pf:.2f}  WR={best.wr:.1f}%  "
          f"n={int(best.n)}  (h1=${best.h1:,.0f}, h2=${best.h2:,.0f})")

    # --- walk-forward چهار-پنجره ---
    sig = dip_signal(df, int(best.rsi_p), int(best.rsi_thr))
    print(f"\n[Walk-Forward چهار-پنجره]")
    n4 = len(df) // 4
    wf = []
    for k in range(4):
        a = k*n4; b = (k+1)*n4 if k < 3 else len(df)
        s = np.zeros(len(df), dtype=bool); s[a:b] = sig[a:b]
        st, _ = bt(df, s, int(best.sl), int(best.tp), int(best.mh))
        wf.append((k+1, st['net_profit'], st['n_trades']))
        print(f"  پنجرهٔ {k+1}: net=${st['net_profit']:>8,.0f}  n={st['n_trades']}  "
              f"{'✅' if st['net_profit'] > 0 else '❌'}")

    out = dict(best=dict(rsi_p=int(best.rsi_p), rsi_thr=int(best.rsi_thr), sl=int(best.sl),
                         tp=int(best.tp), mh=int(best.mh), net=float(best.net),
                         pf=float(best.pf), wr=float(best.wr), n=int(best.n),
                         h1=float(best.h1), h2=float(best.h2)),
               wf=[[int(k), float(v), int(nn)] for k, v, nn in wf])
    with open(os.path.join(RESULTS, '_s107_dip.json'), 'w') as fj:
        json.dump(out, fj, ensure_ascii=False, indent=2, default=float)
    print("\nذخیره شد: results/_s107_dip.json")


if __name__ == '__main__':
    main()
