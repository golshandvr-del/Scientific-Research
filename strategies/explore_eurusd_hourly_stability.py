"""
explore_eurusd_hourly_stability.py — آیا drift ساعتیِ EURUSD در طولِ زمان پایدار است؟
================================================================================
قانونِ شمارهٔ ۱ پروژه: هدف **فقط سودِ خالصِ بیشتر**. سودِ خالص = XAUUSD + EURUSD.

یافتهٔ اکتشافی (explore_eurusd_dna): drift ساعتیِ بسیار معنادار وجود دارد:
  ساعتِ 0 UTC: t=+23 (صعودی قوی)، ساعاتِ 22/13/18/6/23: نزولیِ معنادار.
اما autocorrelation تقریباً صفر ⇒ momentum/mean-reversion سادهٔ M15 کار نمی‌کند
(چرا S71/S72 شکست خوردند).

پرسشِ حیاتی: آیا این drift ساعتی یک ویژگیِ **پایدار و out-of-sample** است یا
artifactِ یک دورهٔ خاص؟ اگر پایدار باشد، پایهٔ یک استراتژیِ واقعی است.

روش: داده را به 4 چهارک زمانی (period) تقسیم می‌کنیم و میانگینِ drift 4-کندلیِ
آینده را برای هر ساعت در هر period جدا می‌سنجیم. اگر علامتِ ساعاتِ کلیدی در همهٔ
دوره‌ها ثابت بماند ⇒ الگوی ساختاریِ پایدار.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
from backtest import load_data
import warnings; warnings.filterwarnings('ignore')
pd.set_option('display.width', 220); pd.set_option('display.max_columns', 40)

def main():
    df = load_data('data/EURUSD_M15.csv')
    n = len(df)
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    df['hour'] = df['dt'].dt.hour
    c = df['close'].values
    for h in [4]:
        fut = np.full(n, np.nan); fut[:n-h] = (c[h:] - c[:n-h]) / 0.0001
        df[f'fut{h}'] = fut

    # 4 دورهٔ زمانیِ متوالی
    df['period'] = pd.qcut(np.arange(n), 4, labels=['P1','P2','P3','P4'])

    print("=== پایداریِ drift ساعتی (میانگینِ fut4 به pip) در 4 دورهٔ زمانی ===\n", flush=True)
    piv = df.dropna(subset=['fut4']).pivot_table(index='hour', columns='period',
                                                 values='fut4', aggfunc='mean')
    piv['ALL'] = df.dropna(subset=['fut4']).groupby('hour')['fut4'].mean()
    print(piv.round(3).to_string(), flush=True)

    # علامتِ سازگار در هر 4 دوره؟
    print("\n=== ساعاتی که علامتِ drift در هر 4 دوره یکسان است (سیگنالِ ساختاریِ پایدار) ===", flush=True)
    sign_consistent = []
    for hr in range(24):
        row = piv.loc[hr, ['P1','P2','P3','P4']].values
        if np.all(row > 0):
            sign_consistent.append((hr, '+', piv.loc[hr,'ALL']))
        elif np.all(row < 0):
            sign_consistent.append((hr, '-', piv.loc[hr,'ALL']))
    for hr, sgn, allv in sign_consistent:
        print(f"  ساعت {hr:>2} UTC: علامتِ {sgn} در هر 4 دوره ثابت — میانگینِ کل = {allv:+.3f} pip", flush=True)

    # t-stat به تفکیک period برای ساعاتِ کاندید
    print("\n=== t-stat ساعاتِ پایدار به تفکیکِ دوره ===", flush=True)
    cand_hours = [hr for hr,_,_ in sign_consistent]
    d2 = df.dropna(subset=['fut4'])
    for hr in cand_hours:
        parts = []
        for p in ['P1','P2','P3','P4']:
            s = d2[(d2['hour']==hr)&(d2['period']==p)]['fut4']
            t = s.mean()/(s.std()/np.sqrt(len(s))) if len(s)>1 else 0
            parts.append(f"{p}:{t:+.1f}")
        print(f"  ساعت {hr:>2}: " + "  ".join(parts), flush=True)

    print("\nتمام.", flush=True)

if __name__ == '__main__':
    main()
