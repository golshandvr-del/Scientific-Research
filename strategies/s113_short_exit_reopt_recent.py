"""
s113_short_exit_reopt_recent.py — بازبهینه‌سازیِ خروجِ لایهٔ SHORTِ رکورد روی ۳ سالِ اخیر
================================================================================
زمینه (طبق User note2 «تمرکز روی ۳ سالِ اخیر»):
  لایهٔ SHORTِ رکورد (Short-MA-Confluence + trailing) با پارامترِ خروجِ
  SL40/BE8/trail8/mh12 ساخته شد که روی *کلِ ۱۵۰k* بهینه بود. اما کاربر اکنون
  تأکید می‌کند تمرکز روی ۳ سالِ اخیر باشد. این اسکریپت پروفایلِ خروج را *فقط*
  روی ۳ سالِ اخیر جاروب می‌کند تا ببیند آیا سودِ SHORT بالاتر می‌رود.

چرا این مسیر ارزشمند است (کشفِ s111):
  • SHORTِ فعلی در ۳ سالِ اخیر coverage=28٪، WR=46.6٪، R:R=1.40، خالص ~+6,491pip.
  • SHORT با long‌های رکورد *ناهمبسته* است (corr=-0.11) ⇒ هر بهبود مستقیماً
    به رکوردِ کل (+76,082$) اضافه می‌شود.

روش:
  • ماشهٔ ثابت (همان رکورد): قطعِ رو به پایینِ میانهٔ [EMA50,EMA100,SMA200].
  • جاروبِ خروج: SL × BE × trail × max_hold.
  • معیار: سودِ خالصِ دلاری (موتورِ سرمایه‌محور) + both-halves مثبت +
    مقایسه با baselineِ رکورد (SL40/BE8/trail8/mh12).
  • فقط اگر baselineِ ۳-ساله را *معنادار* شکست بدهد، نامزدِ بهبودِ رکورد است.

قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود):
  فقط و فقط دنبالِ «سودِ خالصِ بیشتر» هستیم — WR مهم نیست.
  تعریفِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
================================================================================
"""
import sys, os, json, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')
YEARS_RECENT = 3


def load_recent():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    cut = df['dt'].max() - pd.Timedelta(days=365 * YEARS_RECENT)
    return df[df['dt'] >= cut].reset_index(drop=True)


def short_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def net_usd(df, sig, params):
    long_sig = np.zeros(len(df), bool)
    trades = se.simulate_trades(df, long_sig, sig, asset='XAUUSD', **params)
    if trades is None or len(trades) == 0:
        return 0.0, 0, 0.0
    stats, _ = se.run_capital(trades, asset='XAUUSD')
    return stats['net_profit'], stats['n_trades'], stats['win_rate']


def main():
    print("=" * 80)
    print("s113 — بازبهینه‌سازیِ خروجِ SHORT روی ۳ سالِ اخیر (بهبودِ مستقیمِ رکورد)")
    print("=" * 80)
    df = load_recent()
    mid = len(df) // 2
    h1 = df.iloc[:mid].reset_index(drop=True)
    h2 = df.iloc[mid:].reset_index(drop=True)
    print(f"داده: {len(df)} کندل  ({df['dt'].min().date()} → {df['dt'].max().date()})\n")

    sig_full = short_signal(df); sig_h1 = short_signal(h1); sig_h2 = short_signal(h2)

    # baselineِ رکورد
    base_p = dict(sl_pip=40, tp_pip=200, max_hold=12, be_trigger_pip=8, trail_pip=8)
    base_net, base_n, base_wr = net_usd(df, sig_full, base_p)
    print(f"baselineِ رکورد (SL40/BE8/trail8/mh12):  ${base_net:,.0f}   n={base_n}   WR={base_wr:.0f}%\n")

    # جاروب
    SL   = [30, 40, 50, 60]
    BE   = [6, 8, 12, 16]
    TR   = [6, 8, 12, 16, 20]
    MH   = [8, 12, 16, 24]
    rows = []
    for sl, be, tr, mh in itertools.product(SL, BE, TR, MH):
        p = dict(sl_pip=sl, tp_pip=200, max_hold=mh, be_trigger_pip=be, trail_pip=tr)
        net_f, n_f, wr_f = net_usd(df, sig_full, p)
        rows.append(dict(sl=sl, be=be, tr=tr, mh=mh, net=net_f, n=n_f, wr=wr_f))

    rows.sort(key=lambda r: r['net'], reverse=True)
    print(f"{'SL':>4}{'BE':>4}{'trail':>6}{'mh':>4}{'net':>10}{'n':>6}{'WR':>6}")
    print("─" * 42)
    for r in rows[:12]:
        print(f"{r['sl']:>4}{r['be']:>4}{r['tr']:>6}{r['mh']:>4}{r['net']:>10,.0f}{r['n']:>6}{r['wr']:>5.0f}%")

    # both-halves برای بهترین‌ها
    print(f"\nآزمونِ both-halves روی top-8 (نیمهٔ اول و دومِ همین ۳ سال):")
    print(f"{'SL':>4}{'BE':>4}{'trail':>6}{'mh':>4}{'net_full':>10}{'h1':>9}{'h2':>9}{'both':>6}")
    print("─" * 54)
    validated = []
    for r in rows[:8]:
        p = dict(sl_pip=r['sl'], tp_pip=200, max_hold=r['mh'],
                 be_trigger_pip=r['be'], trail_pip=r['tr'])
        n1, _, _ = net_usd(h1, sig_h1, p)
        n2, _, _ = net_usd(h2, sig_h2, p)
        both = n1 > 0 and n2 > 0
        flag = '✅' if both else '  '
        print(f"{r['sl']:>4}{r['be']:>4}{r['tr']:>6}{r['mh']:>4}{r['net']:>10,.0f}{n1:>9,.0f}{n2:>9,.0f}{flag:>6}")
        if both:
            validated.append({**r, 'h1': n1, 'h2': n2})

    print("\n" + "=" * 80)
    improved = [v for v in validated if v['net'] > base_net + 500]  # حاشیهٔ معناداری
    if improved:
        b = improved[0]
        gain = b['net'] - base_net
        print(f"✅ خروجِ بهترِ SHORT یافت شد (both-halves مثبت):")
        print(f"   SL{b['sl']}/BE{b['be']}/trail{b['tr']}/mh{b['mh']}")
        print(f"   سودِ ۳-ساله = ${b['net']:,.0f}  (baseline ${base_net:,.0f}، بهبودِ +${gain:,.0f})")
        print(f"   h1=${b['h1']:,.0f}  h2=${b['h2']:,.0f}")
        print(f"\n   ⚠️ توجه: این سودِ ۳-ساله است؛ برای اعلامِ رکوردِ جدید باید سودِ *کلِ ۱۵۰k*")
        print(f"   با این پارامترِ جدید محاسبه و با سهمِ SHORTِ رکورد (+14,979$) مقایسه شود (s114).")
    else:
        print(f"❌ baselineِ رکورد شکسته نشد؛ خروجِ فعلی (SL40/BE8/trail8/mh12) روی ۳ سالِ اخیر بهینه است.")
        print(f"   (این خودش تأییدی بر استواریِ رکورد است.)")
    print("=" * 80)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s113_short_reopt.json'), 'w') as f:
        json.dump({'window': f'{YEARS_RECENT}y_recent', 'baseline_net': base_net,
                   'baseline_n': base_n, 'top': rows[:12],
                   'validated': validated, 'improved': improved},
                  f, ensure_ascii=False, indent=2, default=float)
    print(f"\nذخیره شد: results/_s113_short_reopt.json")


if __name__ == '__main__':
    main()
