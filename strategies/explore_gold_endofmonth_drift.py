"""
explore_gold_endofmonth_drift.py — اکتشافِ ساختارِ «End-of-Month Drift» روی طلا M15
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **معیارِ موفقیت فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate، نه Profit Factor،
> نه تعدادِ معامله.** تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
شکافِ پژوهشیِ #۱ ماتریس (research/STRATEGY_MATRIX_ResearchGaps.md):
  «اثرِ پایانِ ماه روی طلا (End-of-Month Drift)» — هرگز لایهٔ مستقل نشده.
  ادبیاتِ آکادمیک (Ariel 1987؛ Lakonishok–Smidt 1988؛ McConnell–Xu 2008) نشان
  می‌دهد پنجرهٔ Turn-of-the-Month شاملِ *چند روزِ آخرِ ماهِ قبل* هم هست، نه فقط
  dom=1. S141 فقط اولین روزِ ماه (tom_rel=1) را گرفت. روزهای آخرِ ماه
  (from_end = -1, -2, -3, ...) هرگز به‌عنوان لایهٔ مستقل تست نشده‌اند.

این اسکریپت *فقط اکتشاف* است (هیچ ادعای رکورد نمی‌کند). خروجی: t-stat هر
«روزِ نسبی به پایانِ ماه» × both-halves × چهار-چارک، برای یافتنِ ساختارِ پایدار.
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
RESULTS = os.path.join(ROOT, 'results')


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    """رتبهٔ روزِ معاملاتی نسبت به پایانِ ماه:
    from_end = -1 یعنی آخرین روزِ معاملاتیِ ماه، -2 یکی مانده به آخر، ... .
    """
    days = df[['date', 'ym']].drop_duplicates('date').reset_index(drop=True)
    days['rank_in_month'] = days.groupby('ym').cumcount() + 1
    days['cnt_in_month'] = days.groupby('ym')['date'].transform('count')
    # آخرین روز → -1، یکی مانده به آخر → -2 ...
    days['from_end'] = days['rank_in_month'] - days['cnt_in_month'] - 1
    m = dict(zip(days['date'], days['from_end']))
    df = df.copy()
    df['from_end'] = df['date'].map(m).astype(int)
    return df


def bar_forward_return_pip(df, horizon_bars):
    """بازدهِ pip از open کندلِ بعدی تا close پس از horizon کندل (forward-safe)."""
    op = df['open'].values
    cl = df['close'].values
    n = len(df)
    fwd = np.full(n, np.nan)
    for i in range(n - 1 - horizon_bars):
        entry = op[i + 1]
        exit_ = cl[i + 1 + horizon_bars]
        fwd[i] = (exit_ - entry) / 0.1  # طلا: 1 pip = 0.1$
    return fwd


def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 30 or x.std(ddof=1) == 0:
        return 0.0, 0.0, len(x)
    t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
    return float(t), float(x.mean()), int(len(x))


def main():
    df = load()
    df = assign_from_end(df)
    n = len(df)
    print(f"داده: {n} کندلِ M15 XAUUSD")
    print(f"شکافِ پژوهشیِ #۱: End-of-Month Drift (روزهای آخرِ ماه، from_end منفی)\n")

    # افقِ نگهداری برای بازدهِ خام (برای t-stat؛ محافظه‌کارانه 16 کندل=4 ساعت)
    HOR = 16
    fwd = bar_forward_return_pip(df, HOR)

    print(f"{'='*70}")
    print(f"۱) t-stat هر «روزِ نسبی به پایانِ ماه» (horizon={HOR} کندل ≈ 4h)")
    print(f"{'='*70}")
    print(f"{'from_end':>9}{'t-stat':>10}{'mean pip':>11}{'N':>8}   note")
    rows = []
    for fe in [-1, -2, -3, -4, -5, -6, -7, -8, -9, -10]:
        mask = (df['from_end'].values == fe)
        t, m, cnt = tstat(fwd[mask])
        note = ''
        if t >= 4:
            note = '★ قوی'
        elif t >= 2:
            note = 'مثبتِ معنی‌دار'
        elif t <= -2:
            note = 'منفی'
        print(f"{fe:>9}{t:>10.2f}{m:>11.2f}{cnt:>8}   {note}")
        rows.append({'from_end': fe, 't': round(t, 2), 'mean_pip': round(m, 2), 'N': cnt})

    # --- بررسیِ خوشه‌های کاندید ---
    print(f"\n{'='*70}")
    print(f"۲) خوشه‌های کاندید (روزهای آخرِ ماه با هم)")
    print(f"{'='*70}")
    clusters = {
        'last1 {-1}': [-1],
        'last2 {-1,-2}': [-1, -2],
        'last3 {-1,-2,-3}': [-1, -2, -3],
        'pre-end {-6,-7}': [-6, -7],
        'pre-end3 {-6,-7,-3}': [-6, -7, -3],
        'pre-end-wide {-5,-6,-7,-8}': [-5, -6, -7, -8],
    }
    cluster_rows = []
    for name, fes in clusters.items():
        mask = np.isin(df['from_end'].values, fes)
        t, m, cnt = tstat(fwd[mask])
        # both-halves
        half = n // 2
        idx = np.arange(n)
        mh1 = mask & (idx < half); mh2 = mask & (idx >= half)
        t1, m1, _ = tstat(fwd[mh1]); t2, m2, _ = tstat(fwd[mh2])
        both = (m1 > 0 and m2 > 0)
        print(f"  {name:<22} t={t:+6.2f}  mean={m:+7.2f}pip  N={cnt:>5}  "
              f"h1={m1:+.2f} h2={m2:+.2f}  both={'✓' if both else '✗'}")
        cluster_rows.append({'cluster': name, 'fes': fes, 't': round(t, 2),
                             'mean_pip': round(m, 2), 'N': cnt,
                             'h1_mean': round(m1, 2), 'h2_mean': round(m2, 2),
                             'both': bool(both)})

    # --- برای بهترین خوشه: کالبدشکافیِ ساعتی ---
    best = max(cluster_rows, key=lambda r: r['t'] if r['both'] else -999)
    print(f"\n{'='*70}")
    print(f"۳) کالبدشکافیِ ساعتیِ بهترین خوشهٔ both✓: {best['cluster']} (fes={best['fes']})")
    print(f"{'='*70}")
    fes = best['fes']
    mask_c = np.isin(df['from_end'].values, fes)
    print(f"{'hour':>5}{'t-stat':>10}{'mean pip':>11}{'N':>7}")
    good_hours = []
    for h in range(24):
        mask = mask_c & (df['hour'].values == h)
        t, m, cnt = tstat(fwd[mask])
        flag = '←' if t >= 2 else ''
        if t >= 2:
            good_hours.append(h)
        if cnt >= 20:
            print(f"{h:>5}{t:>10.2f}{m:>11.2f}{cnt:>7}  {flag}")
    print(f"\nساعاتِ حاملِ drift (t≥2): {good_hours}")

    # --- چهار-چارک روی بهترین خوشه + ساعاتِ خوب ---
    print(f"\n{'='*70}")
    print(f"۴) پایداریِ چهار-چارک (خوشه {best['cluster']} × ساعاتِ خوب)")
    print(f"{'='*70}")
    mask_final = mask_c & np.isin(df['hour'].values, good_hours) if good_hours else mask_c
    q = np.linspace(0, n, 5, dtype=int)
    quarter_means = []
    for k in range(4):
        seg = np.zeros(n, bool); seg[q[k]:q[k+1]] = True
        _, m, cnt = tstat(fwd[mask_final & seg])
        quarter_means.append(round(m, 2))
        print(f"  چارک {k+1}: mean={m:+7.2f}pip  N={cnt}")
    all_pos = all(x > 0 for x in quarter_means)
    print(f"\nهر ۴ چارک مثبت؟ {'✅ بله (نه آرتیفکت)' if all_pos else '❌ خیر (مشکوک به آرتیفکت)'}")

    out = {
        'exploration': 'Gold End-of-Month Drift',
        'horizon_bars': HOR,
        'per_day': rows,
        'clusters': cluster_rows,
        'best_cluster': best,
        'good_hours': good_hours,
        'quarter_means': quarter_means,
        'all_quarters_positive': bool(all_pos),
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s144_eom_exploration.json'), 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nذخیره شد: results/_s144_eom_exploration.json")


if __name__ == '__main__':
    main()
