"""
explore_gold_turn_of_month.py — اکتشافِ ساختاریِ «اثرِ چرخشِ ماه» روی طلا M15
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR فقط گزارشی است.
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأِ ایده (User Note: «نبوغ‌آمیز فکر کن! رکوردشو بشکن»):
  دو رکوردِ اخیر لبه‌های *زمان-محور* بودند:
    • S139 Overnight Drift = بُعدِ «ساعتِ روز» (۲۲–۲۳ UTC هرروزه).
    • S140 Monday Drift    = بُعدِ «روزِ هفته» (دوشنبه ۱۸–۲۱ UTC).
  یک بُعدِ زمانیِ **سوم و متعامد** که هرگز در این پروژه آزموده نشده و ادبیاتِ
  آکادمیک قویاً می‌شناسد: **«اثرِ چرخشِ ماه» (Turn-of-the-Month Effect)** —
  Ariel (1987, JFE)، Lakonishok & Smidt (1988, RFS)، McConnell & Xu (2008).
  فرضیه: بازده عمدتاً در پنجرهٔ «چند روزِ آخرِ ماه + چند روزِ اولِ ماهِ بعد»
  انباشته می‌شود (به‌علتِ بازموازنه‌سازیِ صندوق‌ها، جریانِ حقوق/مستمری، و ورودِ
  نقدینگیِ نهادی در ابتدای ماه). این بُعد «روزِ تقویمیِ ماه» است — متعامد با
  «ساعت» و «روزِ هفته».

روشِ علمی: ابتدا ساختار را کشف می‌کنیم (t-stat هر «فاصله تا چرخشِ ماه»)، سپس اگر
  خوشهٔ پایدار (هر دو نیمهٔ داده مثبت) یافت شد، در s141 استراتژی می‌سازیم.

معیارِ ساختار: «فاصلهٔ نسبی تا چرخشِ ماه» = شمارهٔ روزِ معاملاتیِ نسبت به آخرین/اولین
  روزِ ماه. اندیسِ متعارف (Lakonishok–Smidt): روزهای [-1..+3] پنجرهٔ TOM هستند
  (روزِ آخرِ ماه = -1، سه روزِ اولِ ماهِ بعد = +1,+2,+3).
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')

HORIZON = 24   # افقِ بازدهِ آینده بر حسبِ کندل (۲۴×۱۵m = ۶ ساعت) — هم‌ترازِ اکتشافِ Monday


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['dt'] = dt
    df['date'] = dt.dt.normalize()
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_tom_index(df):
    """
    به هر کندل یک «شاخصِ روزِ معاملاتی نسبت به چرخشِ ماه» می‌دهد.
    قاعدهٔ استانداردِ آکادمیک (Lakonishok–Smidt):
      • هر روزِ معاملاتی درونِ ماه یک اندیس از ابتدا (1,2,...) و از انتها (-1,-2,...) دارد.
      • پنجرهٔ TOM = {روزهای انتهاییِ ماهِ قبل: -1} ∪ {روزهای ابتداییِ ماه: +1..+3}.
    ما دو شاخص می‌سازیم: tom_from_end (منفی، از آخرِ ماه) و tom_from_start (مثبت، از اولِ ماه).
    سپس یک شاخصِ یکپارچهٔ «tom_rel» می‌سازیم که -1 = آخرین روزِ معاملاتیِ ماه و +1..
    = روزهای اولِ ماه.
    """
    # فهرستِ روزهای معاملاتیِ یکتا (به ترتیب)
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1          # 1,2,...
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1  # آخرین روز = -1
    # شاخصِ یکپارچه: اگر جزوِ ۲ روزِ آخرِ ماه ⇒ from_end (-1,-2)؛ در غیرِاین‌صورت from_start (+1..)
    def rel(row):
        if row['from_end'] >= -2:      # دو روزِ آخرِ ماه
            return int(row['from_end'])       # -1 یا -2
        return int(row['rank_in_month'])      # 1,2,3,...
    days['tom_rel'] = days.apply(rel, axis=1)
    m = dict(zip(days['date'], days['tom_rel']))
    df['tom_rel'] = df['date'].map(m).astype(int)
    return df


def fwd_ret_pip(df, horizon):
    """بازدهِ آیندهٔ horizon-کندلی بر حسبِ pip (طلا: pip=0.10)."""
    c = df['close'].values
    n = len(c)
    fr = np.full(n, np.nan)
    fr[:n - horizon] = (c[horizon:] - c[:n - horizon]) / 0.10
    return fr


def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 30 or x.std() == 0:
        return 0.0, 0.0, len(x)
    return float(x.mean() / (x.std() / np.sqrt(len(x)))), float(x.mean()), len(x)


def main():
    df = load()
    df = assign_tom_index(df)
    df['fr'] = fwd_ret_pip(df, HORIZON)
    n = len(df); half = n // 2

    print(f"داده: {n} کندلِ M15 XAUUSD | افقِ بازده = {HORIZON} کندل ({HORIZON*15/60:.0f}h)")
    print(f"{'='*78}\n۱) محورِ خالصِ «شاخصِ چرخشِ ماه» (tom_rel) — t-stat و پایداریِ دو نیمه\n{'='*78}")
    print(f"{'tom_rel':>8}{'t-stat':>9}{'mean_pip':>10}{'N':>8}   {'h1_mean':>9}{'h2_mean':>9}  both>0?")

    stable_positive = []
    for rel in sorted(df['tom_rel'].unique()):
        sub = df[df['tom_rel'] == rel]
        t, m, cnt = tstat(sub['fr'].values)
        h1 = sub[sub.index < half]['fr'].values
        h2 = sub[sub.index >= half]['fr'].values
        _, m1, _ = tstat(h1); _, m2, _ = tstat(h2)
        both = (m1 > 0 and m2 > 0)
        mark = "✓" if both else ""
        # فقط اندیس‌های نزدیکِ چرخشِ ماه را نشان بده (بازهٔ جالب)
        if -3 <= rel <= 6:
            print(f"{rel:>8}{t:>9.2f}{m:>10.2f}{cnt:>8}   {m1:>9.2f}{m2:>9.2f}  {mark}")
        if both and t > 2.0 and -3 <= rel <= 6:
            stable_positive.append((rel, t, m, m1, m2))

    print(f"\n{'='*78}\n۲) اندیس‌های پایدارِ مثبت (both-halves ✓ و t>2) در پنجرهٔ [-3..+6]\n{'='*78}")
    if not stable_positive:
        print("هیچ اندیسِ پایداری یافت نشد.")
    else:
        for rel, t, m, m1, m2 in stable_positive:
            print(f"  tom_rel={rel:+d}: t={t:.2f}, mean={m:+.2f}pip, h1={m1:+.2f}, h2={m2:+.2f}")

    # --- بررسیِ خوشهٔ TOM استاندارد (روزهای -1..+3) ---
    print(f"\n{'='*78}\n۳) خوشهٔ TOM استاندارد {{-1,+1,+2,+3}} در برابرِ «بقیهٔ ماه»\n{'='*78}")
    tom_mask = df['tom_rel'].isin([-1, 1, 2, 3])
    t_in, m_in, n_in = tstat(df[tom_mask]['fr'].values)
    t_out, m_out, n_out = tstat(df[~tom_mask]['fr'].values)
    print(f"  داخلِ TOM {{-1,1,2,3}}: t={t_in:+.2f}  mean={m_in:+.2f}pip  N={n_in}")
    print(f"  بیرونِ TOM         : t={t_out:+.2f}  mean={m_out:+.2f}pip  N={n_out}")
    print(f"  اختلافِ mean (edge): {m_in - m_out:+.2f}pip")

    # --- ترکیبِ بهترین اندیس‌ها با ساعت (هم‌افزایی احتمالی) ---
    print(f"\n{'='*78}\n۴) نقشهٔ tom_rel × hour برای بهترین اندیس‌ها (t-stat)\n{'='*78}")
    best_rels = [r for r, *_ in stable_positive] or [-1, 1, 2, 3]
    for rel in best_rels[:5]:
        sub = df[df['tom_rel'] == rel]
        hours_t = []
        for h in range(24):
            hh = sub[sub['hour'] == h]['fr'].values
            t, m, cnt = tstat(hh)
            if t > 2.5 and cnt > 30:
                hours_t.append((h, round(t, 1), round(m, 1)))
        print(f"  tom_rel={rel:+d}: ساعاتِ قوی (t>2.5) = {hours_t}")


if __name__ == '__main__':
    main()
