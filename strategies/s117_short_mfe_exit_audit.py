"""
s117_short_mfe_exit_audit.py — حسابرسیِ MFE/MAE و ضعفِ exit-timingِ مغزِ SHORTِ رکورد
================================================================================
> # قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.
================================================================================

انگیزه (پاسخِ مستقیم به User Note این نشست):
  کشفِ نشستِ قبلی (s116) گفت: «کشف ≠ گرفتن». مغزها روند را می‌بینند اما با نوسانِ
  داخلی استاپ می‌خورند و captured اغلب منفی می‌شود ⇒ **ضعفِ اصلی exit-timing است،
  نه ورود.** User Note پرسید: «چطور مغزها را بهبود دهیم تا دقیق‌تر عمل کنند؟»

  ⚠️ نکتهٔ User Note: «در نشستِ قبلی اشتباهاً با موتورِ long تست کردیم.» — این فایل
  فقط با موتورِ **درست** (direction='short' برای نزولی) کار می‌کند و این را صریحاً
  با یک آزمونِ کنترلی نشان می‌دهد: اگر همان سیگنالِ SHORT را با موتورِ long اجرا کنیم،
  نتیجه فاجعه است (کنترلِ منفی) — تا ثابت شود جهتِ موتور درست انتخاب شده.

  این فایل *تشخیصی* است: MFE (بیشترین سودِ در دسترس) و MAE (بیشترین ضررِ گذرا) هر
  معاملهٔ SHORTِ رکورد را می‌سنجد و کمّی می‌کند «چقدر سود روی میز جا مانده».
  خروجی: یک نقشهٔ راه برای طراحیِ قانونِ exitِ بهتر (که در s118 بک‌تست خواهد شد).

روش (کاملاً forward-safe؛ MFE/MAE فقط برای *تشخیص* است، نه تصمیمِ معامله):
  • سیگنالِ SHORT = قطعِ رو به پایینِ میانهٔ [EMA50,EMA100,SMA200] (ماشهٔ رکورد).
  • برای هر ورود، مسیرِ قیمت را تا max_hold دنبال می‌کنیم و ثبت می‌کنیم:
      - realized_pip : سود/زیانِ واقعیِ خروجِ رکورد (SL60/BE6/trail6/mh8).
      - mfe_pip      : بهترین سودِ لحظه‌ایِ در دسترس در طولِ نگهداری (سقفِ نظری).
      - mae_pip      : بدترین ضررِ لحظه‌ای.
      - bar_of_mfe   : چند کندل پس از ورود، MFE رخ داد.
  • «سودِ جامانده» = mfe − realized. اگر این بزرگ باشد ⇒ trailing خیلی زود/دیر است.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import indicators as ind
import scalp_engine as se

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(os.path.dirname(__file__), '..', 'results')

# پارامترهای دقیقِ خروجِ رکورد (SHORT، recent3y)
REC = dict(sl_pip=60, tp_pip=200, max_hold=8, be_trigger_pip=6, trail_pip=6)
PIP = 0.10  # طلا


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def short_signal(df):
    c = df['close']; p = c.values
    e50 = ind.ema(c, 50).values; e100 = ind.ema(c, 100).values; s200 = ind.sma(c, 200).values
    mid = np.nanmean(np.column_stack([e50, e100, s200]), axis=1)
    return (np.r_[False, p[:-1] > mid[:-1]]) & (p < mid)


def mfe_mae_for_trades(df, trades, max_hold):
    """
    برای هر معاملهٔ SHORT، MFE/MAE بر حسبِ pip را از مسیرِ قیمت محاسبه می‌کند.
    (فقط تشخیصی؛ برای طراحیِ exit استفاده می‌شود نه اجرای معامله.)
    SHORT: سود وقتی قیمت پایین می‌رود ⇒ favor = entry - low ، adverse = high - entry.
    """
    o = df['open'].values; h = df['high'].values; l = df['low'].values
    n = len(df)
    rows = []
    for _, t in trades.iterrows():
        eb = int(t['entry_bar'])
        entry = float(t['entry_price'])
        end = min(eb + max_hold, n)
        best_favor = -1e9; best_bar = eb; worst_adv = 0.0
        for j in range(eb, end):
            favor = (entry - l[j]) / PIP      # سودِ لحظه‌ایِ ماکزیمم (SHORT)
            adv = (h[j] - entry) / PIP        # ضررِ لحظه‌ای
            if favor > best_favor:
                best_favor = favor; best_bar = j
            if adv > worst_adv:
                worst_adv = adv
        rows.append(dict(entry_bar=eb,
                         realized_pip=float(t['pnl_pip']),
                         mfe_pip=float(best_favor),
                         mae_pip=float(worst_adv),
                         bar_of_mfe=int(best_bar - eb),
                         bars_held=int(t['bars_held']),
                         outcome=t['outcome']))
    return pd.DataFrame(rows)


def main():
    print("=" * 80)
    print("s117 — حسابرسیِ MFE/MAE و ضعفِ exit مغزِ SHORTِ رکورد (پاسخِ User Note)")
    print("=" * 80)
    df = load()
    print(f"داده: {len(df)} کندل  |  ماشه: قطعِ رو به پایینِ میانهٔ سه‌MA")

    sig = short_signal(df)
    long_flat = np.zeros(len(df), bool)

    # ── معاملاتِ واقعیِ رکورد با موتورِ درست (SHORT) ──
    tr = se.simulate_trades(df, long_flat, sig, asset='XAUUSD', **REC)
    st, _ = se.run_capital(tr, 'XAUUSD', 10000, 1.0, False)
    print(f"\n[موتورِ درست: SHORT]  n={st['n_trades']}  net=${st['net_profit']:,.0f}"
          f"  WR={st['win_rate']:.1f}%  PF={st['profit_factor']:.2f}")

    # ── کنترلِ منفی: همان سیگنال با موتورِ LONG (باگِ نشستِ قبلی) ──
    tr_wrong = se.simulate_trades(df, sig, long_flat, asset='XAUUSD', **REC)
    if tr_wrong is not None and len(tr_wrong):
        st_w, _ = se.run_capital(tr_wrong, 'XAUUSD', 10000, 1.0, False)
        print(f"[کنترلِ منفی: LONG اشتباه]  n={st_w['n_trades']}  net=${st_w['net_profit']:,.0f}"
              f"  WR={st_w['win_rate']:.1f}%  PF={st_w['profit_factor']:.2f}")
        print(f"  ⇒ اختلافِ ${st['net_profit']-st_w['net_profit']:,.0f} ثابت می‌کند جهتِ موتور مهم است"
              f" و این‌بار درست (SHORT) انتخاب شده.")

    # ── تحلیلِ MFE/MAE ──
    mm = mfe_mae_for_trades(df, tr, REC['max_hold'])
    left_on_table = mm['mfe_pip'] - mm['realized_pip']

    print(f"\n{'='*80}\nتحلیلِ MFE/MAE (سودِ در دسترس در برابرِ سودِ گرفته‌شده):")
    print(f"  میانگینِ realized (خروجِ رکورد) = {mm['realized_pip'].mean():+.1f} pip")
    print(f"  میانگینِ MFE (سقفِ نظری)        = {mm['mfe_pip'].mean():+.1f} pip")
    print(f"  میانگینِ MAE (بدترین ضررِ گذرا) = {mm['mae_pip'].mean():+.1f} pip")
    print(f"  میانگینِ «سودِ روی میز جامانده» = {left_on_table.mean():+.1f} pip")
    print(f"  کندلِ متوسطِ رخدادِ MFE          = {mm['bar_of_mfe'].mean():.1f} از {REC['max_hold']}")

    # چند بردِ بزرگ چقدر MFE داشتند که پس دادیم؟
    winners = mm[mm['realized_pip'] > 0]
    losers = mm[mm['realized_pip'] <= 0]
    print(f"\n  بردها  (n={len(winners)}): MFE میانگین={winners['mfe_pip'].mean():.1f}"
          f"  realized={winners['realized_pip'].mean():.1f}"
          f"  جامانده={((winners['mfe_pip']-winners['realized_pip'])).mean():.1f} pip")
    print(f"  باخت‌ها(n={len(losers)}): MFE میانگین={losers['mfe_pip'].mean():.1f}"
          f"  realized={losers['realized_pip'].mean():.1f}"
          f"  (چند باخت اصلاً MFE مثبت داشتند و پس دادیم؟)")
    # باخت‌هایی که در جایی سودِ خوبی داشتند ولی باخت شدند
    give_backs = losers[losers['mfe_pip'] >= 20]
    print(f"    باخت‌هایی با MFE≥20pip (سودِ خوب که به باخت تبدیل شد): "
          f"{len(give_backs)} از {len(losers)} ({len(give_backs)/max(len(losers),1)*100:.0f}%)")
    if len(give_backs):
        print(f"      این‌ها میانگین MFE={give_backs['mfe_pip'].mean():.1f}pip داشتند"
              f" ولی با realized={give_backs['realized_pip'].mean():.1f}pip بسته شدند.")

    # توزیعِ بار رخدادِ MFE (برای طراحیِ max_hold و trailing)
    print(f"\n  توزیعِ کندلِ رخدادِ MFE (کِی بهترین لحظه می‌آید؟):")
    for b in range(REC['max_hold'] + 1):
        cnt = (mm['bar_of_mfe'] == b).sum()
        if cnt:
            print(f"    کندل {b}: {cnt:4d} ({cnt/len(mm)*100:4.1f}%)")

    out = dict(record_exit=REC,
               net_short=float(st['net_profit']),
               n=int(st['n_trades']),
               mean_realized=float(mm['realized_pip'].mean()),
               mean_mfe=float(mm['mfe_pip'].mean()),
               mean_mae=float(mm['mae_pip'].mean()),
               mean_left_on_table=float(left_on_table.mean()),
               mean_bar_of_mfe=float(mm['bar_of_mfe'].mean()),
               give_backs_frac=float(len(give_backs)/max(len(losers),1)))
    with open(os.path.join(RESULTS, '_s117_mfe.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print(f"\n✅ ذخیره شد: results/_s117_mfe.json")


if __name__ == '__main__':
    main()
