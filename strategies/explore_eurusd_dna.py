"""
explore_eurusd_dna.py — تحلیلِ اکتشافیِ «DNA»ِ رفتاریِ EURUSD (بدونِ فرضیهٔ از پیش)
================================================================================
قانونِ شمارهٔ ۱ پروژه (تکرارِ الزامی): هدفِ پروژه **فقط و فقط «سودِ خالصِ بیشتر»**
است — نه Win-Rate. WR صرفاً یک عددِ گزارشی است. تعدادِ معامله و Profit Factor هم
هدف نیستند. **ما دنبالِ پول هستیم، نه آمارِ زیبا.** تعریفِ فعلیِ «سودِ خالص» =
مجموعِ سودِ خالصِ دو دارایی: XAUUSD + EURUSD.

--------------------------------------------------------------------------------
هدف: به‌جای تحمیلِ یک فرضیه (که در S71/S72 شکست خورد)، بگذاریم خودِ داده حرف بزند.
هیچ استراتژیِ طلا اینجا استفاده نمی‌شود. فقط آماریِ خام:
  1) اثرِ ساعتِ روز (session) روی بازدهِ آتیِ EURUSD.
  2) اثرِ روزِ هفته.
  3) Autocorrelation در افق‌های مختلف (momentum یا mean-reversion؟).
  4) رفتار به‌تفکیکِ رژیمِ نوسان.
  5) الگوی جهت‌دارِ ساعتی (drift) شرطی بر سشن.
همه shift-safe: بازدهِ آتی از r_{t→t+h} با نگاه به بعد؛ ویژگی‌ها فقط از گذشته/جاری.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import warnings; warnings.filterwarnings('ignore')

pd.set_option('display.width', 200)
pd.set_option('display.max_columns', 30)

def main():
    df = load_data('data/EURUSD_M15.csv')
    n = len(df)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['dt'].dt.hour            # UTC
    df['dow'] = df['dt'].dt.dayofweek        # 0=Mon
    c = df['close'].values
    # بازدهِ لگاریتمی هر کندل (به pip: EURUSD 1 pip = 0.0001)
    ret = np.zeros(n)
    ret[1:] = (c[1:] - c[:-1]) / 0.0001      # بازدهِ کندل به pip
    df['ret_pip'] = ret

    print(f"=== EURUSD M15 DNA  (n={n}, {df['dt'].iloc[0]} → {df['dt'].iloc[-1]}) ===\n", flush=True)

    # --- 1) میانگینِ حرکتِ مطلق و جهت‌دار به تفکیکِ ساعت ---
    print("### 1) اثرِ ساعتِ روز (UTC) — میانگینِ بازدهِ کندلِ جاری (pip)")
    g = df.groupby('hour')['ret_pip']
    tbl = pd.DataFrame({'mean_pip': g.mean(), 'abs_pip': g.apply(lambda s: s.abs().mean()),
                        'std_pip': g.std(), 'count': g.count()})
    print(tbl.round(3).to_string(), flush=True)

    # --- 2) روزِ هفته ---
    print("\n### 2) اثرِ روزِ هفته — میانگین/انحرافِ بازده (pip)")
    g2 = df.groupby('dow')['ret_pip']
    print(pd.DataFrame({'mean_pip': g2.mean(), 'abs_pip': g2.apply(lambda s: s.abs().mean()),
                        'count': g2.count()}).round(3).to_string(), flush=True)

    # --- 3) Autocorrelation در افق‌های مختلف ---
    print("\n### 3) Autocorrelation بازده (momentum مثبت / mean-reversion منفی)")
    r = pd.Series(ret[1:])
    for lag in [1, 2, 4, 8, 16, 32]:
        ac = r.autocorr(lag)
        print(f"  lag={lag:>3} candles ({lag*15}min): autocorr = {ac:+.4f}", flush=True)

    # --- 4) momentum افقی: آیا بازدهِ h کندلِ گذشته بازدهِ h کندلِ آینده را پیش‌بینی می‌کند؟ ---
    print("\n### 4) رابطهٔ بازدهِ گذشته(h) با آیندهٔ(h) — sign-accuracy و همبستگی")
    for h in [4, 8, 16, 32, 48, 96]:
        past = (c[h:n-h] - c[:n-2*h])
        fut = (c[2*h:n] - c[h:n-h])
        if len(past) < 100: continue
        corr = np.corrcoef(past, fut)[0,1]
        # اگر گذشته صعودی بود، آینده چند درصد هم صعودی؟ (momentum)
        mask = np.abs(past) > 1e-9
        cont = (np.sign(past[mask]) == np.sign(fut[mask])).mean()
        print(f"  h={h:>3} ({h*15}min): corr(past,fut)={corr:+.4f}  P(same-sign continue)={cont*100:.1f}%", flush=True)

    # --- 5) drift جهت‌دارِ ساعتی شرطی: میانگینِ بازدهِ 4 کندلِ آینده به تفکیکِ ساعتِ ورود ---
    print("\n### 5) drift آینده (میانگینِ حرکتِ 4 کندل=1h آینده به pip) به تفکیکِ ساعتِ فعلی")
    fut4 = np.full(n, np.nan)
    fut4[:n-4] = (c[4:] - c[:n-4]) / 0.0001
    df['fut4_pip'] = fut4
    gg = df.dropna(subset=['fut4_pip']).groupby('hour')['fut4_pip']
    drift = pd.DataFrame({'mean_fut4': gg.mean(), 'std': gg.std(), 'count': gg.count(),
                          't_stat': gg.mean()/(gg.std()/np.sqrt(gg.count()))})
    print(drift.round(3).to_string(), flush=True)

    # --- 6) رفتارِ رژیمِ نوسان: بازدهِ آتی بسته به کوانتایلِ ATR جاری ---
    print("\n### 6) وابستگیِ momentum به رژیمِ نوسان (ATR14 quartile)")
    from indicators import atr as atr_fn
    atrv = atr_fn(df, 14).values
    valid = ~np.isnan(atrv)
    q = pd.qcut(pd.Series(atrv[valid]), 4, labels=['Q1_low','Q2','Q3','Q4_high'])
    # momentum h=8
    h = 8
    past = np.full(n, np.nan); fut = np.full(n, np.nan)
    past[h:] = (c[h:] - c[:n-h]); 
    fut[:n-h] = (c[h:] - c[:n-h])
    dfm = pd.DataFrame({'atr': atrv, 'past': past, 'fut': fut}).dropna()
    dfm['q'] = pd.qcut(dfm['atr'], 4, labels=['Q1_low','Q2','Q3','Q4_high'])
    for name, sub in dfm.groupby('q'):
        m = np.abs(sub['past']) > 1e-9
        cont = (np.sign(sub['past'][m]) == np.sign(sub['fut'][m])).mean()
        corr = np.corrcoef(sub['past'], sub['fut'])[0,1]
        print(f"  ATR {name}: corr(past8,fut8)={corr:+.4f}  P(continue)={cont*100:.1f}%  n={len(sub)}", flush=True)

    print("\nتمام. این تحلیل هیچ فرضیه‌ای تحمیل نکرد؛ فقط ساختارِ خامِ داده را نشان داد.", flush=True)

if __name__ == '__main__':
    main()
