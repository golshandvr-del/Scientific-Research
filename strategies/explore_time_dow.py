"""
تحلیل اکتشافی الگوهای زمانی و روز-هفته (پاسخ به User Note دوم).

فرضیه‌های کاربر:
  (A) رفتار بازار در هر روز هفته (دوشنبه..جمعه) الگوی مشابه دارد (نه لزوماً جهت).
  (B) بازار هرچقدر در طول هفته بالا/پایین رفته، در پنجشنبه و به‌ویژه جمعه
      برعکسش را می‌رود (mean-reversion هفتگی).

این اسکریپت هیچ استراتژی‌ای نمی‌سازد؛ فقط شواهد آماری خام را استخراج می‌کند.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from scipy import stats
from backtest import load_data
import warnings; warnings.filterwarnings('ignore')

df = load_data()
df['dow']  = df['dt'].dt.dayofweek          # 0=Mon .. 6=Sun
df['hour'] = df['dt'].dt.hour
df['date'] = df['dt'].dt.date
c = df['close'].values
o = df['open'].values
n = len(df)
DOW_NAMES = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']

print("="*78)
print("داده:", n, "کندل  |  بازه:", df['dt'].iloc[0], "->", df['dt'].iloc[-1])
print("="*78)

# ---------------------------------------------------------------------------
# بخش ۱: بازده روزانه به تفکیک روز هفته (candle-level intraday return per DOW)
# ---------------------------------------------------------------------------
# بازده ۱ کندل آینده به‌عنوان معیار «حرکت درون‌روزی»
ret1 = np.full(n, np.nan); ret1[:-1] = c[1:] - c[:-1]
print("\n[1] میانگین بازده هر کندل (M15) و P(up) به تفکیک روز هفته")
print(f"{'DOW':<5}{'n':>8}{'mean$':>10}{'P(up)%':>9}{'std$':>9}")
baseline_up = np.mean(ret1[~np.isnan(ret1)] > 0) * 100
for d in range(7):
    m = (df['dow'].values == d) & ~np.isnan(ret1)
    if m.sum() < 50: continue
    rr = ret1[m]
    print(f"{DOW_NAMES[d]:<5}{m.sum():>8}{rr.mean():>+10.4f}{np.mean(rr>0)*100:>9.2f}{rr.std():>9.3f}")
print(f"baseline P(up) کل = {baseline_up:.2f}%")

# ---------------------------------------------------------------------------
# بخش ۲: میانگین تغییر قیمت «کل روز» (close_روز - open_روز) به تفکیک DOW
# ---------------------------------------------------------------------------
daily = df.groupby('date').agg(dow=('dow','first'),
                               d_open=('open','first'),
                               d_close=('close','last'),
                               d_high=('high','max'),
                               d_low=('low','min')).reset_index()
daily['chg'] = daily['d_close'] - daily['d_open']
daily['range'] = daily['d_high'] - daily['d_low']
print("\n[2] تغییر کل روز (close-open) و رنج روز به تفکیک DOW")
print(f"{'DOW':<5}{'n_days':>8}{'mean_chg$':>12}{'P(up_day)%':>12}{'mean_range$':>13}")
for d in range(7):
    sub = daily[daily['dow']==d]
    if len(sub) < 20: continue
    print(f"{DOW_NAMES[d]:<5}{len(sub):>8}{sub['chg'].mean():>+12.3f}"
          f"{np.mean(sub['chg']>0)*100:>12.2f}{sub['range'].mean():>13.3f}")

# ---------------------------------------------------------------------------
# بخش ۳: فرضیه mean-reversion هفتگی (Thu/Fri برعکسِ Mon-Wed)
# ---------------------------------------------------------------------------
# برای هر هفته (سال+شماره‌هفته): حرکت Mon..Wed را محاسبه، سپس حرکت Thu و Fri را ببین
daily['dt'] = pd.to_datetime(daily['date'])
daily['iso_year'] = daily['dt'].dt.isocalendar().year
daily['iso_week'] = daily['dt'].dt.isocalendar().week
weeks = daily.groupby(['iso_year','iso_week'])

rows = []
for (yr,wk), g in weeks:
    g = g.sort_values('dt')
    dd = {r['dow']: r for _, r in g.iterrows()}
    # حرکت اوایل هفته: از open دوشنبه تا close چهارشنبه (dow 0..2)
    early = g[g['dow'].isin([0,1,2])]
    if len(early) == 0: continue
    early_move = early['d_close'].iloc[-1] - early['d_open'].iloc[0]
    thu = dd.get(3); fri = dd.get(4)
    rows.append({
        'yr':yr,'wk':wk,
        'early_move': early_move,
        'thu_chg': (thu['chg'] if thu is not None else np.nan),
        'fri_chg': (fri['chg'] if fri is not None else np.nan),
        'thu_fri_chg': ((thu['chg'] if thu is not None else 0) +
                        (fri['chg'] if fri is not None else 0)),
    })
wk_df = pd.DataFrame(rows).dropna(subset=['early_move'])
print(f"\n[3] فرضیه mean-reversion هفتگی — {len(wk_df)} هفته کامل")

# همبستگی early_move با thu_fri_chg. اگر فرضیه درست باشد باید منفی و معنادار باشد.
for target in ['thu_chg','fri_chg','thu_fri_chg']:
    sub = wk_df.dropna(subset=[target])
    if len(sub) < 30: continue
    r, p = stats.pearsonr(sub['early_move'], sub[target])
    # شرطی: وقتی early_move صعودی قوی بود، Thu/Fri چقدر نزولی شد؟
    up_weeks = sub[sub['early_move'] > sub['early_move'].median()]
    dn_weeks = sub[sub['early_move'] <= sub['early_move'].median()]
    print(f"  target={target:<12} corr(early,target)={r:+.3f} (p={p:.3f}) | "
          f"وقتی early صعودی: mean({target})={up_weeks[target].mean():+.3f}$ | "
          f"وقتی early نزولی: mean({target})={dn_weeks[target].mean():+.3f}$")

# ---------------------------------------------------------------------------
# بخش ۴: اثر تعاملی DOW × ساعت (کدام روز/ساعت جهت‌دارترین است)
# ---------------------------------------------------------------------------
ret8 = np.full(n, np.nan); ret8[:-8] = c[8:] - c[:-8]
print("\n[4] بهترین/بدترین جیب‌های (DOW × ساعت) بر اساس |میانگین بازده ۸ کندل آینده|")
pockets = []
for d in range(5):
    for hr in range(24):
        m = (df['dow'].values==d) & (df['hour'].values==hr) & ~np.isnan(ret8)
        if m.sum() < 150: continue
        rr = ret8[m]
        t, p = stats.ttest_1samp(rr, 0)
        pockets.append((DOW_NAMES[d], hr, m.sum(), rr.mean(),
                        np.mean(rr>0)*100, p))
pk = pd.DataFrame(pockets, columns=['dow','hour','n','mean','pup','pval'])
pk = pk.sort_values('mean')
print("  --- ۸ جیب نزولی‌ترین ---")
for _, r in pk.head(8).iterrows():
    print(f"  {r['dow']} h{int(r['hour']):02d}: mean={r['mean']:+.4f}$ P(up)={r['pup']:.1f}% n={int(r['n'])} p={r['pval']:.3f}")
print("  --- ۸ جیب صعودی‌ترین ---")
for _, r in pk.tail(8).iloc[::-1].iterrows():
    print(f"  {r['dow']} h{int(r['hour']):02d}: mean={r['mean']:+.4f}$ P(up)={r['pup']:.1f}% n={int(r['n'])} p={r['pval']:.3f}")

# ---------------------------------------------------------------------------
# بخش ۵: اثر دوشنبه-گپ / بازگشایی هفته و اثر پایان‌هفته
# ---------------------------------------------------------------------------
print("\n[5] بازده جهت‌دار روز کامل به تفکیک DOW (t-test در برابر صفر)")
for d in range(7):
    sub = daily[daily['dow']==d]
    if len(sub) < 20: continue
    t,p = stats.ttest_1samp(sub['chg'].values, 0)
    print(f"  {DOW_NAMES[d]}: mean_chg={sub['chg'].mean():+.3f}$ t={t:+.2f} p={p:.3f} n={len(sub)}")
print("\nتمام.")
