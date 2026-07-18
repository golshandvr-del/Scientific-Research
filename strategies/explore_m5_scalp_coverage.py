"""
explore_m5_scalp_coverage.py — اکتشافِ خانواده‌های سیگنالِ اسکالپِ M5 (پوشش + دقتِ شروع)
================================================================================
> # قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» است — نه WR.
> تعریفِ سودِ خالص = سودِ XAUUSD + سودِ EURUSD. این فایل اکتشافی است (سود اضافه نمی‌کند).
================================================================================
هدف: طبقِ کشفِ s119 (مغزِ اسکالپِ فعلی روی M5 فقط ~۱٪ روند را می‌گیرد چون RSI<35
     در روندِ صعودیِ سریعِ M5 تقریباً هرگز فایر نمی‌شود)، اینجا چند خانوادهٔ سیگنالِ
     *دوطرفه* را می‌سنجیم که کدام‌یک بیشترین «پوشش روند» را با «دقتِ شروعِ بالا»
     می‌دهد. معیار: coverage (چند درصد روندها کشف) + میانگین start_score.
     این پایهٔ طراحیِ استراتژیِ اسکالپِ دوطرفهٔ s120 است.
================================================================================
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M5.csv')
MIN_MOVE_USD = 8.0


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def ema(x, p):
    return pd.Series(x).ewm(span=p, adjust=False).mean().values

def sma(x, p):
    return pd.Series(x).rolling(p).mean().values

def rsi(x, p=14):
    d = np.diff(x, prepend=x[0])
    g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = pd.Series(g).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag / np.where(al == 0, np.nan, al)
    return 100 - 100/(1+rs)

def atr(h, l, c, p=14):
    tr = np.maximum.reduce([h-l, np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))]); tr[0]=h[0]-l[0]
    return pd.Series(tr).ewm(alpha=1/p, adjust=False).mean().values


def zigzag_trends(close, thr):
    n=len(close)
    if n<3: return []
    piv=[]; direction=0; ei=0; ep=close[0]
    for i in range(1,n):
        pr=close[i]
        if direction>=0:
            if pr>ep: ep=pr; ei=i
            if ep-pr>=thr: piv.append((ei,ep,'H')); direction=-1; ep=pr; ei=i
        if direction<=0:
            if pr<ep: ep=pr; ei=i
            if pr-ep>=thr: piv.append((ei,ep,'L')); direction=+1; ep=pr; ei=i
    trends=[]
    for k in range(1,len(piv)):
        i0,p0,t0=piv[k-1]; i1,p1,t1=piv[k]
        if i1<=i0: continue
        mv=p1-p0
        if t0=='L' and t1=='H' and mv>=thr:
            trends.append(dict(dir='UP',i_start=i0,i_end=i1,move=mv))
        elif t0=='H' and t1=='L' and -mv>=thr:
            trends.append(dict(dir='DOWN',i_start=i0,i_end=i1,move=-mv))
    return trends


def coverage_score(trends, sig_idx, direction):
    """برای هر روندِ این جهت: آیا سیگنالی داخلِ [i0,i1] فایر شد؟ و start_score."""
    ss=np.array(sorted(sig_idx))
    det=0; starts=[]; tot=0
    for t in trends:
        if t['dir']!=direction: continue
        tot+=1
        i0,i1=t['i_start'],t['i_end']; rng=max(i1-i0,1)
        inside=ss[(ss>=i0)&(ss<=i1)]
        if len(inside)>0:
            det+=1
            entry=int(inside[0])
            frac=(entry-i0)/rng
            starts.append(100*(1-frac))
    cov=100*det/max(tot,1)
    avg_start=np.mean(starts) if starts else 0.0
    return det, tot, cov, avg_start, len(sig_idx)


def find_window(df, target=50, step=200):
    n=len(df); end=n
    for win in range(step,n,step):
        s=max(end-win,0)
        tr=zigzag_trends(df['close'].values[s:end].astype(float), MIN_MOVE_USD)
        if sum(1 for t in tr if t['dir']=='UP')>=target: return s,end
    return 0,end


def main():
    df=load()
    a,b=find_window(df,50)
    seg=df.iloc[a:b].reset_index(drop=True)
    c=seg['close'].values.astype(float)
    h=seg['high'].values.astype(float); l=seg['low'].values.astype(float)
    trends=zigzag_trends(c,MIN_MOVE_USD)
    nu=sum(1 for t in trends if t['dir']=='UP'); nd=sum(1 for t in trends if t['dir']=='DOWN')
    print(f"پنجره [{a},{b}] — UP={nu} DOWN={nd}  ({seg['dt'].iloc[0]} → {seg['dt'].iloc[-1]})")

    e9=ema(c,9); e21=ema(c,21); e50=ema(c,50); e100=ema(c,100); e200=ema(c,200)
    r14=rsi(c,14); r7=rsi(c,7)
    at=atr(h,l,c,14)
    slope9 = e9 - np.roll(e9,3)           # شیبِ کوتاهِ EMA9
    hi20 = pd.Series(h).rolling(20).max().shift(1).values
    lo20 = pd.Series(l).rolling(20).min().shift(1).values
    hi10 = pd.Series(h).rolling(10).max().shift(1).values
    lo10 = pd.Series(l).rolling(10).min().shift(1).values

    # خانواده‌های سیگنال (بولین per-bar) — long و short
    fams = {}

    # A) مغزِ فعلیِ سایت (S91): EMA20>EMA100 & RSI(21)<35 — فقط long
    fams['A_current_long']  = (ema(c,20)>ema(c,100)) & (rsi(c,21)<35)
    fams['A_current_short'] = None

    # B) EMA9/EMA21 cross momentum (اسکالپِ کلاسیک)
    ec = (e9>e21) & (np.roll(e9,1)<=np.roll(e21,1))
    ecs= (e9<e21) & (np.roll(e9,1)>=np.roll(e21,1))
    fams['B_ema9_21_cross_long']  = ec
    fams['B_ema9_21_cross_short'] = ecs

    # C) Breakout: عبور از سقف/کفِ ۲۰ کندلی + شیبِ همسو
    fams['C_break20_long']  = (c>hi20) & (slope9>0)
    fams['C_break20_short'] = (c<lo20) & (slope9<0)

    # D) Breakout سریع‌تر: سقف/کفِ ۱۰ کندلی
    fams['D_break10_long']  = (c>hi10) & (e9>e21)
    fams['D_break10_short'] = (c<lo10) & (e9<e21)

    # E) Momentum pullback: روندِ صعودی (e21>e50) + RSI7 از زیر ۴۰ به بالا برگردد
    r7_up = (r7>40) & (np.roll(r7,1)<=40)
    r7_dn = (r7<60) & (np.roll(r7,1)>=60)
    fams['E_mom_pullback_long']  = (e21>e50) & r7_up
    fams['E_mom_pullback_short'] = (e21<e50) & r7_dn

    # F) EMA9 slope flip در جهتِ ساختار (e50 جهت)
    sflip_up = (slope9>0) & (np.roll(slope9,1)<=0)
    sflip_dn = (slope9<0) & (np.roll(slope9,1)>=0)
    fams['F_slope_flip_long']  = (c>e50) & sflip_up
    fams['F_slope_flip_short'] = (c<e50) & sflip_dn

    # G) ترکیبِ breakout OR slope-flip (پوششِ بیشینه)
    fams['G_combo_long']  = ((c>hi10)&(e9>e21)) | ((c>e50)&sflip_up)
    fams['G_combo_short'] = ((c<lo10)&(e9<e21)) | ((c<e50)&sflip_dn)

    print(f"\n{'خانواده':32} {'جهت':5} {'#سیگنال':>8} {'کشف':>5} {'پوشش%':>7} {'دقتِ شروع':>9}")
    for name, sig in fams.items():
        if sig is None: continue
        direction = 'UP' if 'long' in name else 'DOWN'
        idx = np.where(np.nan_to_num(sig, nan=0).astype(bool))[0]
        det,tot,cov,st,ns = coverage_score(trends, idx, direction)
        print(f"{name:32} {direction:5} {ns:>8} {det:>3}/{tot:<2} {cov:>6.1f}% {st:>8.1f}")


if __name__ == '__main__':
    main()
