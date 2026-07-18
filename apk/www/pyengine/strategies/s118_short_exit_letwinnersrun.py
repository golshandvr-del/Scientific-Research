"""
s118_short_exit_letwinnersrun.py — بازطراحیِ exit مغزِ SHORT: «بگذار بردها بدوند»
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
================================================================================

فرضیه (مستقیم از کشفِ کمّیِ s117 — پاسخِ User Note «چطور مغز را بهبود دهیم؟»):
  s117 نشان داد خروجِ فعلیِ SHORT (SL60/BE6/trail6/mh8):
    • میانگین فقط +4.8 pip می‌گیرد ولی MFE=69.3 pip در دسترس بوده ⇒ 64.6 pip جامانده.
    • ۴۳٪ باخت‌ها در جایی MFE≥20pip (میانگین ۹۶pip!) داشتند ولی به باخت تبدیل شدند.
  ریشه: **trail=6pip بیش‌ازحد تنگ است** — با نوسانِ عادیِ طلا در همان کندل‌های اول
  استاپِ trailing می‌خورد و اجازه نمی‌دهد حرکتِ نزولیِ بزرگ ادامه یابد. این دقیقاً
  نقضِ قانونِ شمارهٔ ۱ است («بگذار بردها بدوند، باخت را کوچک نگه دار»).

آزمون (کاملاً forward-safe، بدونِ look-ahead، ضدِ overfit):
  • ماشهٔ ثابت (بدونِ تغییر): قطعِ رو به پایینِ میانهٔ سه‌MA (ماشهٔ رکورد).
  • جاروبِ فقط پارامترهای *خروج* (trail بزرگ‌تر، BE دیرتر، max_hold بلندتر، TP بزرگ‌تر).
  • معیارِ انتخاب: سودِ خالص روی *نیمهٔ اول* (in-sample)، سپس تأییدِ روی *نیمهٔ دوم*
    (out-of-sample) — نامزد فقط وقتی پذیرفته می‌شود که **هر دو نیمه** مثبت باشند و
    OOS از baseline بهتر باشد. این جلوی overfit را می‌گیرد.
  • سپس walk-forward چهار-پنجره + مقایسهٔ افزایشی با رکوردِ کل.

تنظیماتِ سرمایه دقیقاً مثلِ رکورد: initial=10000, risk=1%, compounding=False.
================================================================================
"""
import sys, os, json, itertools
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')

RECORD_TOTAL = 88955.0
RECORD_XAU_LONG = 51880.0
RECORD_EUR = 9223.0
RECORD_SHORT = 27852.0          # سهمِ SHORTِ فعلیِ رکورد (baseline)
BASELINE = dict(sl_pip=60, tp_pip=200, max_hold=8, be_trigger_pip=6, trail_pip=6)

CAP = dict(initial_capital=10000, risk_pct=1.0, compounding=False)


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def short_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def long_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] < mid[:-1]]) & (p > mid)


def run(df, sig, params):
    long_flat = np.zeros(len(df), bool)
    tr = se.simulate_trades(df, long_flat, sig, asset='XAUUSD', **params)
    if tr is None or len(tr) == 0:
        return None, None
    st, _ = se.run_capital(tr, 'XAUUSD', CAP['initial_capital'], CAP['risk_pct'], CAP['compounding'])
    return st, tr


def daily_pnl(df, trades):
    if trades is None or len(trades) == 0:
        return pd.Series(dtype=float)
    exit_dt = df['dt'].values[trades['exit_bar'].values.astype(int)]
    day = pd.to_datetime(exit_dt).normalize()
    s = pd.Series(trades['pnl_pip'].values, index=day)
    return s.groupby(level=0).sum()


def main():
    print("=" * 80)
    print("s118 — بازطراحیِ exit مغزِ SHORT: «بگذار بردها بدوند» (پاسخِ User Note)")
    print("=" * 80)
    df = load()
    n = len(df)
    half = n // 2
    df_h1 = df.iloc[:half].reset_index(drop=True)
    df_h2 = df.iloc[half:].reset_index(drop=True)
    sig_full = short_signal(df)
    sig_h1 = short_signal(df_h1)
    sig_h2 = short_signal(df_h2)

    # baseline
    st_b, _ = run(df, sig_full, BASELINE)
    st_b1, _ = run(df_h1, sig_h1, BASELINE)
    st_b2, _ = run(df_h2, sig_h2, BASELINE)
    print(f"\nBaselineِ رکورد (SL60/BE6/tr6/mh8):")
    print(f"  کل ۱۵۰k: ${st_b['net_profit']:>8,.0f}  |  نیمهٔ۱: ${st_b1['net_profit']:>8,.0f}"
          f"  |  نیمهٔ۲: ${st_b2['net_profit']:>8,.0f}")

    # ── جاروبِ فقط پارامترهای خروج (بگذار بردها بدوند) ──
    SL   = [50, 60, 70]
    TP   = [200, 400, 800]         # TP بزرگ‌تر = فضای دویدنِ برد
    TRAIL = [6, 12, 20, 30, 45]    # trail وسیع‌تر (کلیدِ فرضیه)
    BE   = [6, 12, 20]             # BE دیرتر
    MH   = [8, 16, 32, 48]         # نگهداریِ بلندتر

    print(f"\nجاروبِ exit: {len(SL)}×{len(TP)}×{len(TRAIL)}×{len(BE)}×{len(MH)} "
          f"= {len(SL)*len(TP)*len(TRAIL)*len(BE)*len(MH)} ترکیب (فقط روی نیمهٔ اول برای انتخاب)")

    results = []
    for sl, tp, tr_p, be, mh in itertools.product(SL, TP, TRAIL, BE, MH):
        if be > sl:  # BE منطقی باید کوچک‌تر از SL باشد
            continue
        p = dict(sl_pip=sl, tp_pip=tp, max_hold=mh, be_trigger_pip=be, trail_pip=tr_p)
        s1, _ = run(df_h1, sig_h1, p)
        if s1 is None:
            continue
        results.append((p, s1['net_profit'], s1['profit_factor']))

    # مرتب بر اساسِ سودِ نیمهٔ اول
    results.sort(key=lambda x: -x[1])
    print(f"\n۱۰ نامزدِ برترِ نیمهٔ اول (in-sample):")
    print(f"{'SL':>4}{'TP':>6}{'trail':>7}{'BE':>4}{'mh':>4}  {'net_h1':>10}  {'PF':>5}")
    for p, net, pf in results[:10]:
        print(f"{p['sl_pip']:>4}{p['tp_pip']:>6}{p['trail_pip']:>7}{p['be_trigger_pip']:>4}"
              f"{p['max_hold']:>4}  ${net:>9,.0f}  {pf:>5.2f}")

    # ── تأییدِ out-of-sample: بهترین نامزدها روی نیمهٔ دوم ──
    print(f"\n{'='*80}\nتأییدِ OOS (نیمهٔ دوم) برای ۸ نامزدِ برتر:")
    print(f"{'SL':>4}{'TP':>6}{'trail':>7}{'BE':>4}{'mh':>4}  {'h1':>9}  {'h2(OOS)':>9}  {'full':>9}  حکم")
    validated = []
    for p, net1, pf1 in results[:8]:
        s2, _ = run(df_h2, sig_h2, p)
        sf, trf = run(df, sig_full, p)
        both_pos = net1 > 0 and s2['net_profit'] > 0
        beats_base_full = sf['net_profit'] > st_b['net_profit']
        beats_base_oos = s2['net_profit'] > st_b2['net_profit']
        ok = both_pos and beats_base_full and beats_base_oos
        flag = "✅" if ok else "—"
        print(f"{p['sl_pip']:>4}{p['tp_pip']:>6}{p['trail_pip']:>7}{p['be_trigger_pip']:>4}"
              f"{p['max_hold']:>4}  ${net1:>8,.0f}  ${s2['net_profit']:>8,.0f}"
              f"  ${sf['net_profit']:>8,.0f}  {flag}")
        if ok:
            validated.append((p, sf, trf))

    if not validated:
        print("\n⚠️ هیچ نامزدی هر سه گیت (both-halves + beats OOS + beats full) را پاس نکرد.")
        print("   ⇒ خروجِ رکورد کافی است؛ رکورد بدون تغییر می‌ماند.")
        best = None
    else:
        # بهترین نامزدِ تأییدشده بر اساسِ سودِ کل
        validated.sort(key=lambda x: -x[1]['net_profit'])
        best = validated[0]

    out = {'baseline_full': st_b['net_profit'], 'baseline_h1': st_b1['net_profit'],
           'baseline_h2': st_b2['net_profit'], 'record_total': RECORD_TOTAL}

    if best is not None:
        p, sf, trf = best
        print(f"\n{'='*80}\n🏆 بهترین نامزدِ تأییدشده: {p}")
        print(f"  net کل ۱۵۰k = ${sf['net_profit']:,.0f}  (baseline ${st_b['net_profit']:,.0f}"
              f", Δ ${sf['net_profit']-st_b['net_profit']:+,.0f})")
        print(f"  WR={sf['win_rate']:.1f}%  PF={sf['profit_factor']:.2f}  DD={sf['max_dd_pct']:.1f}%")

        # walk-forward چهار پنجره
        print(f"\n  Walk-forward چهار پنجره:")
        edges = [0, n//4, n//2, 3*n//4, n]; wf = []; all_pos = True
        for i in range(4):
            seg = df.iloc[edges[i]:edges[i+1]].reset_index(drop=True)
            s = short_signal(seg)
            stw, _ = run(seg, s, p)
            net = stw['net_profit'] if stw else 0.0
            wf.append(net)
            if net <= 0: all_pos = False
            print(f"    W{i+1}: ${net:>9,.0f}")

        # ناهمبستگی با long
        lo = long_signal(df); _, tr_lo = run(df, lo, p)
        d_sh = daily_pnl(df, trf); d_lo = daily_pnl(df, tr_lo)
        joined = pd.concat([d_sh.rename('s'), d_lo.rename('l')], axis=1).fillna(0.0)
        corr = joined['s'].corr(joined['l'])
        print(f"\n  ناهمبستگی با long-XAUUSD: corr={corr:+.3f}")

        new_short = sf['net_profit']
        new_total = RECORD_XAU_LONG + new_short + RECORD_EUR
        print(f"\n  رکوردِ جدیدِ کل = long ${RECORD_XAU_LONG:,.0f} + SHORT ${new_short:,.0f}"
              f" + EUR ${RECORD_EUR:,.0f} = ${new_total:,.0f}")
        print(f"  Δ نسبت به رکوردِ ${RECORD_TOTAL:,.0f} = ${new_total-RECORD_TOTAL:+,.0f}")
        verdict = all_pos and abs(corr) < 0.35 and new_total > RECORD_TOTAL
        print(f"\n  {'✅✅ رکوردِ جدید تأیید شد!' if verdict else '⚠️ استرس‌تست ناموفق'}")
        out.update(best_params=p, best_net_short=new_short, new_total=new_total,
                   wf=wf, wf_all_pos=all_pos, corr=corr, verdict=bool(verdict))

    with open(os.path.join(RESULTS, '_s118_exit.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s118_exit.json")


if __name__ == '__main__':
    main()
