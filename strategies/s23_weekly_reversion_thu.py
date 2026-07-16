"""
استراتژی ۲۳: Weekly Mean-Reversion + Thursday Drift (پاسخ به User Note دوم)

پایه علمی (از explore_time_dow.py و explore_weekly_reversion.py):
  1. corr(early_move[Mon-Wed], thu_fri_chg) = -0.217, p<0.001  → mean-reversion هفتگی واقعی است.
  2. در روز پنجشنبه، drift در جهتِ «خلاف حرکت اوایل هفته» از نظر آماری معنادار است
     (t-test intraday، p<0.01، n>23000). یعنی اگر Mon-Wed صعودی بوده، پنجشنبه
     تمایل نزولی دارد و بالعکس.
  3. اثر در پنجشنبه تمیزتر از جمعه است (جمعه نویزی‌تر بود).

منطق معامله:
  - فقط در روز پنجشنبه (UTC) معامله می‌کنیم.
  - جهت = خلاف early_move هفته:
        early_move > +THR  → SHORT (انتظار برگشت نزولی)
        early_move < -THR  → LONG  (انتظار برگشت صعودی)
  - برای بردن WR بالای BE، از TP کوچک نسبت به SL استفاده می‌کنیم (BE≈60٪)
    و ورود را با یک «کشش کوتاه‌مدت در جهت early» (pullback) هماهنگ می‌کنیم تا
    قیمت بهتری بگیریم (mean-reversion را از نقطه‌ی افراط شروع کنیم).

این اسکریپت شبکه‌ی پارامتر را جاروب می‌کند و بهترین ترکیب WR/exp/freq را می‌یابد.
"""
import sys; sys.path.insert(0, 'engine')
import numpy as np, pandas as pd
from scipy import stats
from backtest import load_data, run_backtest
import indicators as ind
import warnings; warnings.filterwarnings('ignore')

df = load_data()
df['dow']  = df['dt'].dt.dayofweek
df['hour'] = df['dt'].dt.hour
df['date'] = df['dt'].dt.date
df['dt_d'] = pd.to_datetime(df['date'])
df['iso_year'] = df['dt_d'].dt.isocalendar().year.values
df['iso_week'] = df['dt_d'].dt.isocalendar().week.values
c = df['close'].values; o = df['open'].values
h = df['high'].values; l = df['low'].values
n = len(df)
atr = ind.atr(df, 14).values
rsi = ind.rsi(df['close'], 14).values
ema20 = ind.ema(df['close'], 20).values

# early_move برای هر هفته
daily = df.groupby('date').agg(dow=('dow','first'), d_open=('open','first'),
                               d_close=('close','last'),
                               iso_year=('iso_year','first'),
                               iso_week=('iso_week','first')).reset_index()
early_map = {}
for (yr,wk), g in daily.groupby(['iso_year','iso_week']):
    g = g.sort_values('date')
    early = g[g['dow'].isin([0,1,2])]
    if len(early)==0: continue
    early_map[(yr,wk)] = early['d_close'].iloc[-1] - early['d_open'].iloc[0]
df['early_move'] = df.apply(lambda r: early_map.get((r['iso_year'],r['iso_week']), np.nan), axis=1)
early = df['early_move'].values

# ATR-نرمال‌شده early_move برای آستانه‌ی وابسته به نوسان
atr_daily = pd.Series(atr).rolling(96).mean().values  # ~1 روز
early_atr = early / (atr_daily + 1e-9)

print("="*80)
print("S23: Weekly Mean-Reversion — فقط پنجشنبه، جهت=خلاف early_move")
print("="*80)

TARGET_DAY = 3  # Thursday
is_thu = (df['dow'].values == TARGET_DAY)

def build_signals(thr_atr, entry_hours, use_rsi_gate, rsi_lo, rsi_hi):
    """
    long_sig/short_sig روی کندل i (سیگنال؛ ورود در open i+1 توسط موتور).
    thr_atr: آستانه early_move بر حسب ATR روزانه.
    entry_hours: مجموعه ساعت‌های مجاز برای ورود.
    use_rsi_gate: اگر True، برای long فقط RSI پایین (oversold نسبی) و برای short فقط RSI بالا.
    """
    hr_ok = np.isin(df['hour'].values, list(entry_hours))
    base = is_thu & hr_ok & ~np.isnan(early) & ~np.isnan(early_atr) & ~np.isnan(rsi)
    # short setup: هفته صعودی بوده
    short_sig = base & (early_atr > thr_atr)
    # long setup: هفته نزولی بوده
    long_sig  = base & (early_atr < -thr_atr)
    if use_rsi_gate:
        # برای mean-reversion: در short، RSI بالا (کشش صعودی برای فروش) بهتر است
        short_sig = short_sig & (rsi > rsi_hi)
        long_sig  = long_sig  & (rsi < rsi_lo)
    return long_sig, short_sig

# جاروب
print(f"{'thr':>5}{'hours':>16}{'rsi':>5}{'tp':>5}{'sl':>5}{'BE%':>6}"
      f"{'nL':>6}{'nS':>6}{'WR%':>7}{'exp$':>8}{'pnl$':>9}{'p':>7}")
print("-"*95)

hour_sets = {
    'all':      set(range(24)),
    '0-12':     set(range(0,13)),
    '7-20':     set(range(7,21)),
    '12-23':    set(range(12,24)),
}
best = None
for thr in [0.3, 0.5, 0.8, 1.0]:
    for hname, hours in hour_sets.items():
        for use_rsi in [False, True]:
            for tp_m, sl_m in [(1.0,1.5),(1.0,1.3),(0.8,1.2),(1.2,1.8),(1.0,1.0)]:
                lsig, ssig = build_signals(thr, hours, use_rsi, 45, 55)
                if lsig.sum()+ssig.sum() < 60:
                    continue
                sL,_ = run_backtest(df, lsig, None, None, 'long', spread=0.20,
                                    max_hold=48, sl_series=sl_m*atr, tp_series=tp_m*atr,
                                    allow_overlap=False)
                sS,_ = run_backtest(df, ssig, None, None, 'short', spread=0.20,
                                    max_hold=48, sl_series=sl_m*atr, tp_series=tp_m*atr,
                                    allow_overlap=False)
                nL, nS = sL['n_trades'], sS['n_trades']
                ntot = nL+nS
                if ntot < 60: continue
                wins = (sL['win_rate']/100*nL + sS['win_rate']/100*nS)
                wr = wins/ntot*100
                pnl = sL['total_pnl']+sS['total_pnl']
                exp = pnl/ntot
                be = sl_m/(tp_m+sl_m)*100
                # p-value برای WR>be
                from scipy.stats import binomtest
                pv = binomtest(int(round(wins)), ntot, be/100, alternative='greater').pvalue
                flag = ""
                if wr>60 and exp>0:
                    flag=" <== WR>60 & exp>0"
                if best is None or (wr>60 and exp>0 and (best[2]<=60 or exp>best[4])):
                    if wr>60 and exp>0:
                        best = (thr,hname,tp_m,sl_m,exp,wr,ntot,pv,use_rsi)
                rlab = 'Y' if use_rsi else '-'
                print(f"{thr:>5.1f}{hname:>16}{rlab:>5}{tp_m:>5.1f}{sl_m:>5.1f}{be:>6.1f}"
                      f"{nL:>6}{nS:>6}{wr:>7.2f}{exp:>+8.3f}{pnl:>+9.1f}{pv:>7.3f}{flag}")

print("\nبهترین ترکیب (WR>60 & exp>0):", best)
