"""
explore_eurusd_calendar_dimensions.py — اسکنِ گستردهٔ ابعادِ تقویمیِ EURUSD
================================================================================
> قانونِ #۱ پروژه: تنها معیار «سودِ خالص = XAUUSD + EURUSD» است، نه Win-Rate.

منشأ (User Note این نشست: «ترکیبی از نبوغ و جنون را به کار ببر!»):
  «جنون» = چهار رکوردِ اخیر همه لبه‌های زمان-محورِ تقویمیِ **طلا** بودند
  (Overnight/Monday/TurnOfMonth/MidMonth). اما تعریفِ رسمیِ سودِ خالص =
  XAUUSD + EURUSD؛ و سهمِ EURUSD فقط از یک لایه (S73، +$9,223) می‌آید.
  همهٔ اکتشافاتِ تقویمی تا امروز فقط روی طلا انجام شده — **بُعدِ تقویمیِ EURUSD
  کاملاً دست‌نخورده است.**

  «نبوغ» = فرضیهٔ اقتصادیِ متمایز: EURUSD یک *جفت‌ارز* است؛ رفتارِ تقویمی‌اش با
  طلا (داراییِ امن) باید متفاوت باشد. جریان‌های ارزیِ نهادی (بازموازنه‌سازیِ
  ماهانهٔ FX، «London 4pm Fix») امضای تقویمیِ مخصوص دارند. اگر لبه‌ای بیابیم،
  چون روی داراییِ متفاوت و بُعدِ متفاوت است ⇒ ذاتاً متعامد (corr پایین) با همهٔ
  لایه‌های طلا.

این اسکریپت *فقط اکتشاف* است (کشفِ ساختار، پیش از ساختِ استراتژی). t-stat +
both-halves روی مجموعه رویدادهای تقویمیِ EURUSD:
   • hour-of-day (۰–۲۳)
   • day-of-week (۰–۴)
   • day-of-month (۱–۳۱)
   • turn-of-month (اولین/آخرین روزهای معاملاتیِ ماه)
   • week-of-month
همه با معیارِ «drift پیش‌روِ N کندلی» سنجیده می‌شوند (forward return پس از رویداد).
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, 'data', 'EURUSD_M15.csv')
PIP = 0.0001            # EURUSD pip size
FWD = 16                # افقِ drift پیش‌رو (۱۶ کندلِ M15 = ۴ ساعت)


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    df['close'] = df['close'].astype(float)
    return df.reset_index(drop=True)


def fwd_return_pips(df, fwd=FWD):
    """بازدهِ پیش‌روِ fwd کندل، بر حسبِ pip (long-drift)."""
    c = df['close'].values
    n = len(c)
    out = np.full(n, np.nan)
    out[:n-fwd] = (c[fwd:] - c[:n-fwd]) / PIP
    return out


def tstat_both(mask, ret, half_idx):
    """t-stat کل + میانگین + هر دو نیمه."""
    m = mask & ~np.isnan(ret)
    x = ret[m]
    if len(x) < 30:
        return None
    mean = x.mean()
    t = mean / (x.std(ddof=1) / np.sqrt(len(x))) if x.std() > 0 else 0.0
    idx = np.where(m)[0]
    h1 = ret[idx[idx < half_idx]]
    h2 = ret[idx[idx >= half_idx]]
    m1 = h1.mean() if len(h1) else 0.0
    m2 = h2.mean() if len(h2) else 0.0
    return dict(n=len(x), mean=mean, t=t, h1=m1, h2=m2,
                both=(m1 > 0 and m2 > 0))


def scan_dimension(df, ret, half, colname, values, label):
    print(f"\n{'='*72}\n{label}\n{'='*72}")
    print(f"{'val':>6}{'n':>8}{'mean_pip':>11}{'t':>9}{'h1':>9}{'h2':>9}  both")
    rows = []
    col = df[colname].values
    for v in values:
        r = tstat_both(col == v, ret, half)
        if r is None:
            continue
        flag = '✓' if r['both'] else ''
        rows.append((v, r))
        if abs(r['t']) >= 3.0:  # فقط قوی‌ها را چاپ کن
            print(f"{v:>6}{r['n']:>8}{r['mean']:>11.2f}{r['t']:>9.2f}"
                  f"{r['h1']:>9.2f}{r['h2']:>9.2f}  {flag}")
    return rows


def assign_tom_rel(df):
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rank_in_month'] - days['cnt'] - 1

    def rel(row):
        if row['from_end'] >= -3:      # ۳ روزِ آخرِ ماه
            return int(row['from_end'])
        return int(row['rank_in_month'])
    days['tom_rel'] = days.apply(rel, axis=1)
    m = dict(zip(days['date'], days['tom_rel']))
    df = df.copy()
    df['tom_rel'] = df['date'].map(m).astype(int)
    return df


def main():
    df = load()
    n = len(df); half = n // 2
    ret = fwd_return_pips(df, FWD)
    print(f"داده: {n} کندلِ M15 EURUSD | افقِ drift = {FWD} کندل ({FWD*15/60:.0f} ساعت)")
    print(f"pip={PIP} | نیمه در ایندکسِ {half}")
    print("هدف: کشفِ ابعادِ تقویمیِ قوی و پایدار (both-halves) کشف‌نشدهٔ EURUSD")

    scan_dimension(df, ret, half, 'hour', list(range(24)),
                   'بُعدِ ۱: ساعتِ روز (hour-of-day) — |t|≥3')
    scan_dimension(df, ret, half, 'dow', list(range(5)),
                   'بُعدِ ۲: روزِ هفته (day-of-week) — |t|≥3')
    scan_dimension(df, ret, half, 'dom', list(range(1, 32)),
                   'بُعدِ ۳: روزِ تقویمیِ ماه (day-of-month) — |t|≥3')

    dft = assign_tom_rel(df)
    scan_dimension(dft, ret, half, 'tom_rel',
                   [1, 2, 3, 4, 5, -1, -2, -3, -4],
                   'بُعدِ ۴: Turn-of-Month (روزِ نسبت به چرخشِ ماه) — |t|≥3')

    print(f"\n{'='*72}\nخلاصه: قوی‌ترین رویدادهای both-halves برای طراحیِ لایهٔ نو\n{'='*72}")
    print("(اگر هیچ رویدادِ قویِ both یافت نشد ⇒ EURUSD بُعدِ تقویمی ندارد و")
    print(" باید مسیرِ متعامدِ دیگری برای شکستنِ رکورد جست.)")


if __name__ == '__main__':
    main()
