"""
explore_gold_calendar_short.py — اکتشافِ لبه‌های تقویمی/زمانیِ SHORT روی طلا M15
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،**
> **نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (User Note این نشست): «s144 رکورد دارد، رکوردشو بزن. راستی چرا روی SHORT کاری
نمی‌کنیم؟ SHORT یک غولِ شکست‌ناپذیر بوده تا اینجا!»

مشاهدهٔ کلیدی: تمامِ لایه‌هایی که رکورد را از +$128k به +$196k رساندند (S139..S144)
همگی **long** بودند و همگی از یک ایدهٔ واحد آمدند: «drift تقویمی/زمانیِ صعودیِ طلا».
سه محورِ متعامد کشف شد: ساعتِ روز (S139)، روزِ هفته (S140)، روزِ تقویمیِ ماه
(S141/S142/S144). اما این سه محور **هرگز در جهتِ SHORT** روی طلا اسکن نشده‌اند.

فرضیهٔ علمی (متقارنِ آینه‌ای): اگر برخی ساعت‌ها/روزها drift صعودیِ ساختاری دارند،
طبقِ حفظِ جریانِ سفارش و رفتارِ نهادی باید ساعت‌ها/روزهایی هم باشند که drift *نزولیِ*
ساختاری دارند (مثلاً فشارِ فروشِ ابتدای سشنِ آسیا، برداشتِ سود پیش از تعطیلات، یا
اثرِ معکوسِ پایانِ هفته). این اسکریپت این شکاف را می‌کاود.

روش: برای هر بُعد، forward-return نزولی (یعنی -1 × بازدهِ آتی) را بر حسبِ pip و
t-stat می‌سنجیم. drift نزولیِ واقعی = بازدهِ آتیِ **منفیِ** معنادار (t منفیِ بزرگ).
سپس فقط برای صداقتِ علمی، هر کاندید را در هر دو نیمهٔ داده و ۴ چارک چک می‌کنیم.
هیچ معامله‌ای هنوز اجرا نمی‌شود؛ این فقط فازِ کشفِ لبه است.
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
PIP = 0.1   # طلا: pip = 0.1 دلار (سازگار با engine ASSETS)


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek           # 0=Mon .. 6=Sun
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    m = dict(zip(days['date'], days['from_end']))
    df['from_end'] = df['date'].map(m).astype(int)
    m2 = dict(zip(days['date'], days['rank_in_month']))
    df['rank_in_month'] = df['date'].map(m2).astype(int)
    return df


def fwd_ret_pip(df, horizon):
    """بازدهِ آتی بر حسبِ pip: (close[t+h] - close[t]) / pip. ورود روی close کندلِ سیگنال."""
    c = df['close'].values
    n = len(c)
    fwd = np.full(n, np.nan)
    fwd[:n - horizon] = (c[horizon:] - c[:n - horizon]) / PIP
    return fwd


def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 30 or x.std() == 0:
        return 0.0, 0.0, 0
    return x.mean(), x.mean() / (x.std() / np.sqrt(len(x))), len(x)


def half_quartile_check(df, mask, fwd):
    """برای short: بازدهِ آتیِ منفی خوب است. mean در هر دو نیمه و هر ۴ چارک باید منفی باشد."""
    n = len(df); half = n // 2
    idx = np.where(mask)[0]
    def m(sel):
        v = fwd[sel]; v = v[~np.isnan(v)]
        return v.mean() if len(v) else 0.0
    h1 = m(idx[idx < half]); h2 = m(idx[idx >= half])
    q = np.linspace(0, n, 5, dtype=int)
    qs = [m(idx[(idx >= q[k]) & (idx < q[k+1])]) for k in range(4)]
    both_neg = (h1 < 0 and h2 < 0)
    allq_neg = all(x < 0 for x in qs)
    return h1, h2, qs, both_neg, allq_neg


def main():
    df = load()
    df = assign_from_end(df)
    n = len(df)
    print(f"داده: {n} کندلِ M15 XAUUSD")
    print("هدف: کشفِ drift نزولیِ ساختاری (بازدهِ آتیِ منفیِ معنادار) — لبهٔ SHORT\n")

    HORIZONS = {'1h': 4, '4h': 16, '1d': 96}

    # ============ محورِ ۱: ساعتِ روز ============
    print("="*80)
    print("محورِ ۱ — ساعتِ روز (کدام ساعت‌ها drift نزولی دارند؟)  [t منفیِ بزرگ = SHORT خوب]")
    print("="*80)
    for label, hz in HORIZONS.items():
        fwd = fwd_ret_pip(df, hz)
        rows = []
        for hr in range(24):
            mask = (df['hour'].values == hr)
            mean, t, cnt = tstat(fwd[mask])
            rows.append((hr, mean, t, cnt))
        rows.sort(key=lambda r: r[2])   # صعودی: منفی‌ترین t اول
        print(f"\n-- افق {label} — ۶ ساعتِ نزولی‌ترین --")
        print(f"{'hour':>5}{'meanPip':>10}{'t':>8}{'n':>8}")
        for hr, mean, t, cnt in rows[:6]:
            print(f"{hr:>5}{mean:>10.2f}{t:>8.2f}{cnt:>8}")

    # ============ محورِ ۲: روزِ هفته ============
    print("\n" + "="*80)
    print("محورِ ۲ — روزِ هفته (کدام روزها drift نزولی دارند؟)")
    print("="*80)
    dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    for label, hz in HORIZONS.items():
        fwd = fwd_ret_pip(df, hz)
        print(f"\n-- افق {label} --")
        print(f"{'dow':>5}{'meanPip':>10}{'t':>8}{'n':>8}")
        rows = []
        for d in range(7):
            mask = (df['dow'].values == d)
            mean, t, cnt = tstat(fwd[mask])
            if cnt > 0:
                rows.append((dow_names[d], mean, t, cnt))
        rows.sort(key=lambda r: r[2])
        for name, mean, t, cnt in rows:
            flag = ' <== نزولی' if t < -2 else ''
            print(f"{name:>5}{mean:>10.2f}{t:>8.2f}{cnt:>8}{flag}")

    # ============ محورِ ۳: روزِ هفته × ساعت ============
    print("\n" + "="*80)
    print("محورِ ۳ — تقاطعِ روزِ هفته × ساعت (نزولی‌ترین جیب‌ها) — افق ۴h و ۱d")
    print("="*80)
    for label, hz in [('4h', 16), ('1d', 96)]:
        fwd = fwd_ret_pip(df, hz)
        rows = []
        for d in range(7):
            for hr in range(24):
                mask = (df['dow'].values == d) & (df['hour'].values == hr)
                mean, t, cnt = tstat(fwd[mask])
                if cnt >= 100:
                    rows.append((dow_names[d], hr, mean, t, cnt))
        rows.sort(key=lambda r: r[3])
        print(f"\n-- افق {label} — ۱۲ جیبِ نزولی‌ترین (n>=100) --")
        print(f"{'dow':>5}{'hour':>6}{'meanPip':>10}{'t':>8}{'n':>8}")
        for name, hr, mean, t, cnt in rows[:12]:
            print(f"{name:>5}{hr:>6}{mean:>10.2f}{t:>8.2f}{cnt:>8}")

    # ============ محورِ ۴: روزِ تقویمیِ ماه (from_end و rank) ============
    print("\n" + "="*80)
    print("محورِ ۴ — روزِ تقویمیِ ماه (نزولی‌ترین روزها) — from_end و rank_in_month")
    print("="*80)
    for label, hz in [('4h', 16), ('1d', 96)]:
        fwd = fwd_ret_pip(df, hz)
        print(f"\n-- افق {label} — از پایانِ ماه (from_end) — نزولی‌ترین‌ها --")
        rows = []
        for fe in range(-1, -12, -1):
            mask = (df['from_end'].values == fe)
            mean, t, cnt = tstat(fwd[mask])
            if cnt >= 100:
                rows.append((fe, mean, t, cnt))
        rows.sort(key=lambda r: r[2])
        print(f"{'fromEnd':>8}{'meanPip':>10}{'t':>8}{'n':>8}")
        for fe, mean, t, cnt in rows[:6]:
            print(f"{fe:>8}{mean:>10.2f}{t:>8.2f}{cnt:>8}")

        print(f"\n-- افق {label} — از ابتدای ماه (rank) — نزولی‌ترین‌ها --")
        rows = []
        for rk in range(1, 16):
            mask = (df['rank_in_month'].values == rk)
            mean, t, cnt = tstat(fwd[mask])
            if cnt >= 100:
                rows.append((rk, mean, t, cnt))
        rows.sort(key=lambda r: r[2])
        print(f"{'rank':>6}{'meanPip':>10}{'t':>8}{'n':>8}")
        for rk, mean, t, cnt in rows[:6]:
            print(f"{rk:>6}{mean:>10.2f}{t:>8.2f}{cnt:>8}")


if __name__ == '__main__':
    main()
