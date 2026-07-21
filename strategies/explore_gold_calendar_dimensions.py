"""
explore_gold_calendar_dimensions.py — اسکنِ نبوغ+جنون‌آمیزِ ابعادِ زمانیِ تقویمیِ کشف‌نشده
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.** WR فقط گزارشی است.
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأِ ایده (User Note این نشست: «ترکیبی از نبوغ و جنون را به کار ببر!»):
  سه رکوردِ اخیر همه لبه‌های *زمان-محور* بودند و هر یک از یک بُعدِ تقویمیِ متعامد:
    • S139 Overnight → «ساعتِ روز»       (۲۲–۲۳ UTC)
    • S140 Monday    → «روزِ هفته»        (دوشنبه)
    • S141 Turn-of-Month → «روزِ تقویمیِ ماه» (اولین روزِ ماه)
  الگوی نبوغ: هر بُعدِ زمانیِ متعامدِ جدید ⇒ یک جریانِ سودِ ناهمبسته ⇒ افزایشی.

  «جنون»: به‌جای آزمودنِ تک‌به‌تک، هم‌زمان **پنج بُعدِ تقویمیِ کشف‌نشده** را اسکن
  می‌کنیم و t-stat/both-halves هرکدام را می‌سنجیم، تا قوی‌ترین کاندیدِ رکوردشکن
  را با روشِ علمی انتخاب کنیم. ابعادِ کاندید (هیچ‌کدام قبلاً آزموده نشده‌اند):

    D1) NFP-day: اولین جمعهٔ هر ماه (روزِ انتشارِ اشتغالِ آمریکا) — بزرگ‌ترین شوکِ
        ماکروِ ماهانهٔ طلا. ادبیات: Andersen–Bollerslev–Diebold–Vega (2003, AER).
    D2) week-of-month: هفتهٔ ۱..۵ ماه (بُعدِ کاملاً جدید، مکملِ روزِ هفته).
    D3) mid-month drift: روزهای ۱۳–۱۷ ماه (چرخهٔ نقدینگیِ میانِ ماه — نقطهٔ مقابلِ TOM).
    D4) day-of-month خام (۱..۳۱): برای کشفِ هر روزِ تقویمیِ قویِ خاص.
    D5) FOMC-proxy: هفتهٔ سومِ ماه (پنجرهٔ نوعیِ نشستِ فدرال‌رزرو، هر ~۶ هفته).

روشِ علمی: ابتدا ساختار (t-stat + دو نیمه)، سپس در استراتژیِ بعدی فقط قوی‌ترین
  خوشهٔ پایدار (both-halves ✓) به موتورِ سرمایه‌محور داده می‌شود.
================================================================================
"""
import os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')

HORIZON = 24   # افقِ بازدهِ آینده (۲۴×۱۵m = ۶ ساعت) — هم‌ترازِ اکتشاف‌های قبلی


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['dt'] = dt
    df['date'] = dt.dt.normalize()
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek         # 0=Mon
    df['dom'] = dt.dt.day               # روزِ تقویمیِ ماه ۱..۳۱
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def fwd_ret_pip(df, horizon):
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


def assign_week_of_month(df):
    """هفتهٔ تقویمیِ ماه: 1..5 (بر اساسِ ((dom-1)//7)+1)."""
    df['wom'] = ((df['dom'] - 1) // 7) + 1
    return df


def assign_nfp_day(df):
    """اولین جمعهٔ هر ماه = روزِ NFP (تقریب استاندارد)."""
    # جمعه = dow==4. اولین جمعهٔ هر ym.
    fri = df[df['dow'] == 4][['date', 'ym']].drop_duplicates('date')
    first_fri = fri.groupby('ym')['date'].min()
    nfp_dates = set(first_fri.values)
    df['is_nfp'] = df['date'].isin(nfp_dates)
    return df


def report_axis(df, colname, label, values, half):
    print(f"\n{'='*80}\n{label}\n{'='*80}")
    print(f"{'val':>8}{'t-stat':>9}{'mean_pip':>10}{'N':>9}   {'h1':>8}{'h2':>8}  both>0?")
    winners = []
    for v in values:
        sub = df[df[colname] == v]
        t, m, cnt = tstat(sub['fr'].values)
        h1 = sub[sub.index < half]['fr'].values
        h2 = sub[sub.index >= half]['fr'].values
        _, m1, _ = tstat(h1); _, m2, _ = tstat(h2)
        both = (m1 > 0 and m2 > 0)
        mark = "✓" if both else ""
        star = " ⭐" if (both and abs(t) > 3.5) else ""
        print(f"{str(v):>8}{t:>9.2f}{m:>10.2f}{cnt:>9}   {m1:>8.2f}{m2:>8.2f}  {mark}{star}")
        if both and abs(t) > 3.0:
            winners.append((v, t, m, m1, m2, cnt))
    return winners


def main():
    df = load()
    df = assign_week_of_month(df)
    df = assign_nfp_day(df)
    df['fr'] = fwd_ret_pip(df, HORIZON)
    n = len(df); half = n // 2
    print(f"داده: {n} کندلِ M15 XAUUSD | افقِ بازده = {HORIZON} کندل ({HORIZON*15/60:.0f}h)")

    all_winners = {}

    # --- D2) هفتهٔ ماه (week-of-month) ---
    w = report_axis(df, 'wom', "D2) هفتهٔ تقویمیِ ماه (week-of-month 1..5)", [1, 2, 3, 4, 5], half)
    all_winners['week_of_month'] = w

    # --- D4) روزِ خامِ ماه (day-of-month) — کشفِ هر روزِ قوی ---
    w = report_axis(df, 'dom', "D4) روزِ خامِ تقویمیِ ماه (day-of-month 1..31)", list(range(1, 32)), half)
    all_winners['day_of_month'] = w

    # --- D1) NFP-day (اولین جمعهٔ ماه) در برابرِ بقیه ---
    print(f"\n{'='*80}\nD1) روزِ NFP (اولین جمعهٔ ماه) در برابرِ بقیهٔ روزها\n{'='*80}")
    for label, mask in [('NFP-day', df['is_nfp']), ('non-NFP', ~df['is_nfp'])]:
        t, m, cnt = tstat(df[mask]['fr'].values)
        h1 = df[mask & (df.index < half)]['fr'].values
        h2 = df[mask & (df.index >= half)]['fr'].values
        _, m1, _ = tstat(h1); _, m2, _ = tstat(h2)
        print(f"  {label:>10}: t={t:+.2f}  mean={m:+.2f}pip  N={cnt}  h1={m1:+.2f} h2={m2:+.2f}  both={'✓' if m1>0 and m2>0 else '✗'}")
    # NFP × ساعت (شاید فقط ساعاتِ خاص)
    print("  NFP-day × ساعت (t>2.5):")
    nfp = df[df['is_nfp']]
    hours_strong = []
    for h in range(24):
        hh = nfp[nfp['hour'] == h]['fr'].values
        t, m, cnt = tstat(hh)
        if abs(t) > 2.5 and cnt > 30:
            hours_strong.append((h, round(t, 1), round(m, 1)))
    print(f"    {hours_strong}")

    # --- D3) mid-month drift (روزهای ۱۳–۱۷) در برابرِ بقیه ---
    print(f"\n{'='*80}\nD3) میانهٔ ماه (dom 13..17) در برابرِ بقیه\n{'='*80}")
    mid = df['dom'].between(13, 17)
    for label, mask in [('mid(13-17)', mid), ('other', ~mid)]:
        t, m, cnt = tstat(df[mask]['fr'].values)
        h1 = df[mask & (df.index < half)]['fr'].values
        h2 = df[mask & (df.index >= half)]['fr'].values
        _, m1, _ = tstat(h1); _, m2, _ = tstat(h2)
        print(f"  {label:>12}: t={t:+.2f}  mean={m:+.2f}pip  N={cnt}  h1={m1:+.2f} h2={m2:+.2f}  both={'✓' if m1>0 and m2>0 else '✗'}")

    # --- D5) FOMC-proxy: هفتهٔ سومِ ماه × ساعت ---
    print(f"\n{'='*80}\nD5) هفتهٔ سومِ ماه (wom==3، پنجرهٔ نوعیِ FOMC) × ساعت (t>2.5)\n{'='*80}")
    w3 = df[df['wom'] == 3]
    hours_strong = []
    for h in range(24):
        hh = w3[w3['hour'] == h]['fr'].values
        t, m, cnt = tstat(hh)
        if abs(t) > 2.5 and cnt > 50:
            hours_strong.append((h, round(t, 1), round(m, 1)))
    print(f"  ساعاتِ قویِ هفتهٔ سوم: {hours_strong}")

    # --- جمع‌بندیِ برنده‌ها ---
    print(f"\n{'='*80}\n🏁 جمع‌بندیِ کاندیداهای رکوردشکن (both-halves ✓ و |t|>3)\n{'='*80}")
    for axis, ws in all_winners.items():
        if ws:
            print(f"\n  محور «{axis}»:")
            for v, t, m, m1, m2, cnt in sorted(ws, key=lambda x: -abs(x[1])):
                print(f"    val={v}: t={t:+.2f}, mean={m:+.2f}pip, h1={m1:+.2f}, h2={m2:+.2f}, N={cnt}")
        else:
            print(f"\n  محور «{axis}»: هیچ کاندیدِ پایداری یافت نشد.")


if __name__ == '__main__':
    main()
