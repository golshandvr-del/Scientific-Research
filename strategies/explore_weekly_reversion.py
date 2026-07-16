"""
Deep-dive روی edge کشف‌شده: mean-reversion هفتگی (پاسخ به User Note دوم).

یافته اکتشافی (explore_time_dow.py):
  corr(early_move[Mon-Wed], thu_fri_chg) = -0.217  (p<0.001)
  - وقتی early صعودی: Thu به‌طور میانگین نزولی (-0.8$)
  - وقتی early نزولی: Thu به‌طور میانگین صعودی قوی (+3.15$)

این اسکریپت edge را کمی‌سازی می‌کند تا ببینیم آیا به یک استراتژی
قابل‌معامله با WR>60% تبدیل می‌شود. ساختار درون‌روزی، نامتقارن‌بودن،
و حساسیت به آستانه early_move بررسی می‌شود.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from scipy import stats
from backtest import load_data
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data()
df['dow']  = df['dt'].dt.dayofweek
df['hour'] = df['dt'].dt.hour
df['date'] = df['dt'].dt.date
df['dt_d'] = pd.to_datetime(df['date'])
df['iso_year'] = df['dt_d'].dt.isocalendar().year.values
df['iso_week'] = df['dt_d'].dt.isocalendar().week.values
c = df['close'].values
atr = ind.atr(df, 14).values

# ---- ساخت جدول روزانه ----
daily = df.groupby('date').agg(dow=('dow','first'),
                               d_open=('open','first'),
                               d_close=('close','last'),
                               iso_year=('iso_year','first'),
                               iso_week=('iso_week','first')).reset_index()
daily['chg'] = daily['d_close'] - daily['d_open']

# early_move برای هر هفته: از open دوشنبه(یا اولین روز) تا close چهارشنبه
early_map = {}   # (yr,wk) -> early_move
wed_close_map = {}  # (yr,wk) -> close چهارشنبه (نقطه مرجع mean-reversion)
for (yr,wk), g in daily.groupby(['iso_year','iso_week']):
    g = g.sort_values('date')
    early = g[g['dow'].isin([0,1,2])]
    if len(early)==0: continue
    early_map[(yr,wk)] = early['d_close'].iloc[-1] - early['d_open'].iloc[0]
    wed_close_map[(yr,wk)] = early['d_close'].iloc[-1]

df['early_move'] = df.apply(lambda r: early_map.get((r['iso_year'],r['iso_week']), np.nan), axis=1)

# ---- ATR هفتگی برای نرمال‌سازی آستانه ----
atr_series = pd.Series(atr)
# early_move را بر حسب دلار نگه می‌داریم؛ آستانه‌ها را جاروب می‌کنیم

print("="*78)
print("Deep-dive: mean-reversion هفتگی — جهت معامله = خلاف early_move در Thu/Fri")
print("="*78)

# ---------------------------------------------------------------------------
# آزمون ۱: بازده جهت‌دار در Thu/Fri وقتی خلاف early_move می‌رویم،
# به تفکیک آستانه early_move و افق نگهداری
# ---------------------------------------------------------------------------
n = len(df)
def fwd_ret(entry_i, horizon):
    j = min(entry_i+horizon, n-1)
    return c[j] - c[entry_i]

# سیگنال: در ابتدای Thu یا Fri (اولین کندل آن روز)، خلاف early_move پوزیشن بگیر
# «خلاف»: اگر early_move>0 => انتظار نزول => بازده مطلوب = -(c_future - c_now)
first_bar_of_day = df.groupby('date').head(1).index.values
is_first = np.zeros(n, dtype=bool); is_first[first_bar_of_day] = True

print("\n[1] بازده «خلاف early_move» در اولین کندل Thu/Fri (بدون SL/TP، فقط جهت)")
print(f"{'day':<5}{'thr$':>7}{'horiz':>7}{'n':>7}{'meanFav$':>11}{'P(fav)%':>9}{'p':>8}")
for day, dname in [(3,'Thu'),(4,'Fri')]:
    for thr in [0, 5, 10, 15, 20]:
        for horizon in [16, 32, 48, 64]:
            m = is_first & (df['dow'].values==day) & (np.abs(df['early_move'].values)>thr) & ~np.isnan(df['early_move'].values)
            idxs = np.where(m)[0]
            idxs = idxs[idxs < n-horizon]
            if len(idxs) < 30: continue
            fav = []
            for i in idxs:
                em = df['early_move'].values[i]
                raw = fwd_ret(i, horizon)
                fav.append(-raw if em>0 else raw)  # خلاف جهت early
            fav = np.array(fav)
            t,p = stats.ttest_1samp(fav,0)
            flag = " <==" if (p<0.05 and fav.mean()>0) else ""
            print(f"{dname:<5}{thr:>7}{horizon:>7}{len(idxs):>7}{fav.mean():>+11.3f}{np.mean(fav>0)*100:>9.1f}{p:>8.3f}{flag}")

# ---------------------------------------------------------------------------
# آزمون ۲: تفکیک نامتقارن — early صعودی (short setup) vs early نزولی (long setup)
# ---------------------------------------------------------------------------
print("\n[2] تفکیک نامتقارن جهت (horizon=48)")
print(f"{'day':<5}{'setup':<18}{'n':>7}{'meanFav$':>11}{'P(fav)%':>9}{'p':>8}")
horizon=48
for day,dname in [(3,'Thu'),(4,'Fri')]:
    for setup,cond in [('early_UP=>short', lambda em: em>10),
                       ('early_DN=>long',  lambda em: em<-10)]:
        m = is_first & (df['dow'].values==day) & ~np.isnan(df['early_move'].values)
        idxs = np.where(m)[0]; idxs=idxs[idxs<n-horizon]
        idxs = [i for i in idxs if cond(df['early_move'].values[i])]
        if len(idxs)<20: continue
        fav=[]
        for i in idxs:
            em=df['early_move'].values[i]; raw=fwd_ret(i,horizon)
            fav.append(-raw if em>0 else raw)
        fav=np.array(fav); t,p=stats.ttest_1samp(fav,0)
        flag=" <==" if (p<0.05 and fav.mean()>0) else ""
        print(f"{dname:<5}{setup:<18}{len(idxs):>7}{fav.mean():>+11.3f}{np.mean(fav>0)*100:>9.1f}{p:>8.3f}{flag}")

# ---------------------------------------------------------------------------
# آزمون ۳: آیا intraday-level هم edge دارد؟ (هر کندل Thu/Fri، نه فقط اولین)
#   این برای فرکانس ربات مهم است (نیاز به >=3 معامله/روز)
# ---------------------------------------------------------------------------
print("\n[3] سطح intraday: همه کندل‌های Thu/Fri، جهت=خلاف early، horizon کوتاه")
print(f"{'day':<5}{'thr$':>7}{'horiz':>7}{'n':>8}{'meanFav$':>11}{'P(fav)%':>9}{'p':>8}")
for day,dname in [(3,'Thu'),(4,'Fri')]:
    for thr in [10, 20]:
        for horizon in [8, 16, 24]:
            m = (df['dow'].values==day) & (np.abs(df['early_move'].values)>thr) & ~np.isnan(df['early_move'].values)
            idxs=np.where(m)[0]; idxs=idxs[idxs<n-horizon]
            if len(idxs)<200: continue
            fav=[]
            for i in idxs:
                em=df['early_move'].values[i]; raw=fwd_ret(i,horizon)
                fav.append(-raw if em>0 else raw)
            fav=np.array(fav); t,p=stats.ttest_1samp(fav,0)
            flag=" <==" if (p<0.05 and fav.mean()>0) else ""
            print(f"{dname:<5}{thr:>7}{horizon:>7}{len(idxs):>8}{fav.mean():>+11.3f}{np.mean(fav>0)*100:>9.1f}{p:>8.3f}{flag}")

print("\nتمام.")
