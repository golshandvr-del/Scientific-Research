"""
explore_gold_short_eom_deep.py — تعمیقِ لبهٔ SHORTِ «۹-۱۰ روز مانده به پایانِ ماه»
================================================================================
> قانونِ شمارهٔ ۱: فقط «سودِ خالصِ بیشتر». سودِ خالص = XAUUSD + EURUSD.

اکتشافِ اولیه (explore_gold_calendar_short.py) نشان داد قوی‌ترین drift نزولیِ طلا
در روزهای ~۹-۱۰ مانده به پایانِ ماه است (from_end=-9: t=-4.85 در افقِ 4h؛
from_end=-10: t=-12.56 در افقِ 1d). این آینهٔ متعامدِ S144 (long در from_end=-6..-8)
است. اینجا پایداریِ both-halves + ۴ چارک + بهترین ساعت را برای ماشهٔ SHORT می‌سنجیم.
هنوز معامله‌ای اجرا نمی‌شود؛ فقط انتخابِ پنجرهٔ روز/ساعت با شواهدِ آماری.
================================================================================
"""
import os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M15.csv')
PIP = 0.1


def load():
    df = pd.read_csv(DATA)
    dt = pd.to_datetime(df['time'], unit='s', utc=True)
    df['hour'] = dt.dt.hour; df['dow'] = dt.dt.dayofweek
    df['date'] = dt.dt.normalize(); df['ym'] = dt.dt.year*100 + dt.dt.month
    return df.reset_index(drop=True)


def assign_from_end(df):
    days = df[['date','ym']].drop_duplicates('date').reset_index(drop=True)
    days['rk'] = days.groupby('ym').cumcount()+1
    days['cnt'] = days.groupby('ym')['date'].transform('count')
    days['from_end'] = days['rk'] - days['cnt'] - 1
    df['from_end'] = df['date'].map(dict(zip(days['date'], days['from_end']))).astype(int)
    return df


def fwd(df, h):
    c = df['close'].values; n=len(c); f=np.full(n,np.nan)
    f[:n-h] = (c[h:]-c[:n-h])/PIP
    return f


def stats(df, mask, f):
    n=len(df); half=n//2; idx=np.where(mask)[0]
    def m(sel):
        v=f[sel]; v=v[~np.isnan(v)]; return (v.mean(), v.mean()/(v.std()/np.sqrt(len(v))) if len(v)>1 and v.std()>0 else 0.0, len(v))
    mean,t,cnt = m(idx)
    h1 = m(idx[idx<half]); h2 = m(idx[idx>=half])
    q=np.linspace(0,n,5,dtype=int); qs=[m(idx[(idx>=q[k])&(idx<q[k+1])]) for k in range(4)]
    return mean,t,cnt,h1[0],h2[0],[x[0] for x in qs]


def main():
    df = assign_from_end(load())
    print("تعمیقِ لبهٔ SHORT: روزهای مانده به پایانِ ماه × ساعت\n")

    # 1) کدام خوشهٔ from_end پایدارترین منفی است؟ (both-halves + ۴ چارک)
    print("="*78)
    print("۱) خوشه‌های from_end (افق 4h و 1d) — دنبالِ mean منفی + both<0 + هر ۴ چارک<0")
    print("="*78)
    clusters = [[-9],[-10],[-9,-10],[-9,-10,-11],[-5],[-5,-9,-10],[-9,-10,-5]]
    for hz_lbl, hz in [('4h',16),('1d',96)]:
        f = fwd(df, hz)
        print(f"\n-- افق {hz_lbl} --")
        print(f"{'cluster':>16}{'meanPip':>9}{'t':>7}{'n':>7}  both<0  4Q<0")
        for cl in clusters:
            mask = np.isin(df['from_end'].values, cl)
            mean,t,cnt,h1,h2,qs = stats(df, mask, f)
            both = (h1<0 and h2<0); allq = all(x<0 for x in qs)
            print(f"{str(cl):>16}{mean:>9.2f}{t:>7.2f}{cnt:>7}   {'✓' if both else '✗'}     {'✓' if allq else '✗'}   q={[round(x,1) for x in qs]}")

    # 2) بهترین ساعت‌ها درونِ خوشهٔ {-9,-10} (کجا drift نزولی متمرکز است؟)
    print("\n" + "="*78)
    print("۲) توزیعِ ساعتیِ drift نزولی درونِ from_end∈{-9,-10} (افق 4h)")
    print("="*78)
    f = fwd(df, 16)
    base = np.isin(df['from_end'].values, [-9,-10])
    rows=[]
    for hr in range(24):
        mask = base & (df['hour'].values==hr)
        if mask.sum()<50: continue
        mean,t,cnt,h1,h2,qs = stats(df, mask, f)
        rows.append((hr,mean,t,cnt,h1,h2))
    rows.sort(key=lambda r:r[2])
    print(f"{'hour':>5}{'meanPip':>9}{'t':>7}{'n':>7}{'h1':>8}{'h2':>8}")
    for hr,mean,t,cnt,h1,h2 in rows[:10]:
        print(f"{hr:>5}{mean:>9.2f}{t:>7.2f}{cnt:>7}{h1:>8.1f}{h2:>8.1f}")

    # 3) پنجرهٔ ساعتیِ کاندید: بلوک‌های پیوسته
    print("\n" + "="*78)
    print("۳) بلوک‌های ساعتیِ پیوسته درونِ {-9,-10} (افق 4h) — دنبالِ both<0 پایدار")
    print("="*78)
    windows = [(0,4),(1,6),(4,9),(7,12),(12,17),(13,18),(14,20),(16,22),(19,24)]
    print(f"{'window':>12}{'meanPip':>9}{'t':>7}{'n':>7}  both<0")
    for lo,hi in windows:
        hrs = list(range(lo,hi))
        mask = base & np.isin(df['hour'].values, hrs)
        mean,t,cnt,h1,h2,qs = stats(df, mask, f)
        both = (h1<0 and h2<0)
        print(f"{f'{lo}-{hi-1}':>12}{mean:>9.2f}{t:>7.2f}{cnt:>7}   {'✓' if both else '✗'}  h1={h1:.1f} h2={h2:.1f}")


if __name__ == '__main__':
    main()
