"""
s122_m5_short_meanreversion.py — اسکالپِ SHORT روی M5 با منطقِ mean-reversion
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» — نه WR.
> تعریفِ سودِ خالص = سودِ XAUUSD + سودِ EURUSD.
================================================================================
انگیزه (پاسخِ مستقیم به User Note «مغزِ اسکالپ فقط long باز می‌کند، short ندارد»):
  s121 ثابت کرد SHORTِ momentum-breakout روی M5 بازنده است (PF 0.94) — چون طلا
  بایاسِ صعودیِ ساختاری دارد (هم‌راستا با یافتهٔ L53). اما یک مسیرِ دیگر باقی است:
  s116 نشان داد SHORT بهتر روی **برگشت از اشباعِ خرید (RSI بالا)** کار می‌کند — یعنی
  منطقِ **mean-reversion**، نه trend-following. اینجا این فرضیه را روی M5 آزمون می‌کنیم:
    SHORT وقتی قیمت بیش‌ازحد از میانگین بالا رفته (فاصلهٔ z-score بالا + RSI اشباع)
    و شمعِ برگشتی ظاهر شده ⇒ ورودِ کوتاهِ برگشت‌به‌میانگین.
  اگر این SHORTِ اسکالپ سودده و additive باشد، اولین لایهٔ SHORTِ M5 پروژه می‌شود.
================================================================================
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'engine'))
import numpy as np, pandas as pd
import scalp_engine as se

ROOT = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(ROOT, 'data', 'XAUUSD_M5.csv')
RESULTS = os.path.join(ROOT, 'results')
ASSET = 'XAUUSD'


def load():
    df = pd.read_csv(DATA)
    df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def ema(x,p): return pd.Series(x).ewm(span=p,adjust=False).mean().values
def rsi(x,p=14):
    d=np.diff(x,prepend=x[0]); g=np.where(d>0,d,0.0); l=np.where(d<0,-d,0.0)
    ag=pd.Series(g).ewm(alpha=1/p,adjust=False).mean().values
    al=pd.Series(l).ewm(alpha=1/p,adjust=False).mean().values
    rs=ag/np.where(al==0,np.nan,al); return 100-100/(1+rs)
def atr(h,l,c,p=14):
    tr=np.maximum.reduce([h-l,np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))]);tr[0]=h[0]-l[0]
    return pd.Series(tr).ewm(alpha=1/p,adjust=False).mean().values


def build_short_mr(df, z_win=50, z_thr=2.0, rsi_thr=70, rsi_p=14):
    """SHORT mean-reversion: قیمت بیش‌ازحد بالای میانگین + RSI اشباعِ خرید + شمعِ برگشتی."""
    c=df['close'].values.astype(float); o=df['open'].values.astype(float)
    h=df['high'].values.astype(float); l=df['low'].values.astype(float)
    ma=pd.Series(c).rolling(z_win).mean().values
    sd=pd.Series(c).rolling(z_win).std().values
    z=(c-ma)/np.where(sd==0,np.nan,sd)
    r=rsi(c,rsi_p)
    # شمعِ برگشتی: کندلِ نزولی بعد از رشد (close<open) و close زیرِ close قبلی
    bear_candle = (c<o) & (c<np.roll(c,1))
    sig = (z>z_thr) & (r>rsi_thr) & bear_candle
    return np.nan_to_num(sig,nan=0).astype(bool)


def build_long_mr(df, z_win=50, z_thr=2.0, rsi_thr=30, rsi_p=14):
    """LONG mean-reversion آینه: قیمت بیش‌ازحد زیرِ میانگین + RSI اشباعِ فروش + شمعِ صعودی."""
    c=df['close'].values.astype(float); o=df['open'].values.astype(float)
    ma=pd.Series(c).rolling(z_win).mean().values
    sd=pd.Series(c).rolling(z_win).std().values
    z=(c-ma)/np.where(sd==0,np.nan,sd)
    r=rsi(c,rsi_p)
    bull_candle=(c>o)&(c>np.roll(c,1))
    sig=(z<-z_thr)&(r<rsi_thr)&bull_candle
    return np.nan_to_num(sig,nan=0).astype(bool)


def rep(df, lsig, ssig, sl, tp, mh, be, trail, label):
    tr=se.simulate_trades(df,lsig,ssig,sl,tp,ASSET,max_hold=mh,allow_overlap=False,
                          be_trigger_pip=be,trail_pip=trail)
    if tr is None or len(tr)==0:
        print(f"{label}: بدونِ معامله"); return None
    n=len(df); mid=n//2
    def net(t):
        s,_=se.run_capital(t,ASSET); return s
    full=net(tr); h1=net(tr[tr['exit_bar']<mid]); h2=net(tr[tr['exit_bar']>=mid])
    wf=[net(tr[(tr['exit_bar']>=k*n//4)&(tr['exit_bar']<(k+1)*n//4)])['net_profit'] for k in range(4)]
    gates=h1['net_profit']>0 and h2['net_profit']>0 and all(w>0 for w in wf)
    print(f"{label:34} net=${full['net_profit']:>8,.0f} n={len(tr):>4} WR={full['win_rate']:.0f}% "
          f"PF={full['profit_factor']:.2f} DD={full['max_dd_pct']:.0f}% Sh={full['sharpe']:.2f} "
          f"h1=${h1['net_profit']:>6,.0f} h2=${h2['net_profit']:>6,.0f} {'✅' if gates else ''}")
    return dict(net=full['net_profit'],n=len(tr),wr=full['win_rate'],pf=full['profit_factor'],
                dd=full['max_dd_pct'],sharpe=full['sharpe'],h1=h1['net_profit'],
                h2=h2['net_profit'],wf=wf,gates=bool(gates))


def main():
    df=load(); empty=np.zeros(len(df),dtype=bool)
    print(f"داده: {len(df)} کندلِ M5 طلا\n")
    print("### SHORT mean-reversion (اشباعِ خرید + برگشت) — جارویِ آستانه ###")
    best=None
    for zt in [1.5,2.0,2.5]:
        for rt in [65,70,75]:
            ssig=build_short_mr(df, z_thr=zt, rsi_thr=rt)
            for (sl,tp,mh,be,trail) in [(40,60,12,None,None),(50,80,16,25,15),
                                        (60,100,20,30,20),(50,120,24,25,15),(40,100,20,20,12)]:
                r=rep(df,empty,ssig,sl,tp,mh,be,trail,f"SHORT z>{zt} rsi>{rt} SL{sl}/TP{tp}")
                if r and r['gates'] and (best is None or r['net']>best[1]['net']):
                    best=(f"SHORT z>{zt} rsi>{rt} SL{sl}/TP{tp}/mh{mh}/be{be}/tr{trail}",r,zt,rt,sl,tp,mh,be,trail)

    print("\n### LONG mean-reversion (آینه، برای مقایسه) ###")
    for zt in [2.0]:
        for rt in [30]:
            lsig=build_long_mr(df,z_thr=zt,rsi_thr=rt)
            for (sl,tp,mh,be,trail) in [(50,80,16,25,15),(50,120,24,25,15),(60,150,32,30,20)]:
                rep(df,lsig,empty,sl,tp,mh,be,trail,f"LONG z<-{zt} rsi<{rt} SL{sl}/TP{tp}")

    print("\n"+"="*70)
    if best:
        tag,r,zt,rt,sl,tp,mh,be,trail=best
        print(f"🏆 بهترین SHORTِ mean-reversionِ M5 با گیتِ سبز: {tag} — net=${r['net']:,.0f}")
        out=dict(winner=tag,z_thr=zt,rsi_thr=rt,sl=sl,tp=tp,mh=mh,be=be,trail=trail,
                 net=float(r['net']),n=int(r['n']),wr=float(r['wr']),pf=float(r['pf']),
                 dd=float(r['dd']),sharpe=float(r['sharpe']),h1=float(r['h1']),h2=float(r['h2']),
                 wf=[float(w) for w in r['wf']])
        with open(os.path.join(RESULTS,'_s122_short_mr.json'),'w') as f:
            json.dump(out,f,ensure_ascii=False,indent=1,default=float)
        print("✅ ذخیره: results/_s122_short_mr.json")
    else:
        print("❌ SHORTِ mean-reversionِ M5 هم گیتِ سبزِ کامل نداد.")


if __name__=='__main__':
    main()
