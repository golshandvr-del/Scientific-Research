"""
s121_m5_scalp_direction_split.py — تفکیکِ جهت (long/short) در اسکالپِ M5 + فیلترِ زمان
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه: هدف فقط «سودِ خالصِ بیشتر» — نه WR.
> تعریفِ سودِ خالص = سودِ XAUUSD + سودِ EURUSD.
================================================================================
انگیزه: s120 نشان داد ماشهٔ رژیم-گیت‌شدهٔ M5 به PF≈۱.۰۹ می‌رسد ولی h1 هنوز منفی است.
  دو فرضیهٔ آزمون‌پذیر:
   ۱) شاید یکی از دو جهت (long یا short) سودده و آن‌یکی زیان‌ده است. اگر short به‌تنهایی
      روی M5 سودده باشد، دقیقاً پاسخِ User Note است («الان فقط long می‌زند، short ندارد»).
   ۲) شاید فیلترِ سِشِن (ساعاتِ پرنقدینگیِ لندن/نیویورک) h1 را نجات می‌دهد — اسکالپ در
      ساعاتِ کم‌نقدینگیِ آسیایی به‌خاطرِ اسپرد نابود می‌شود.
  اینجا برندهٔ s120 (M_htf_break20 SL40/TP400) را می‌گیریم و long/short و سِشِن را
  به‌تفکیک می‌سنجیم تا **جریانِ سوددهِ خالص** را جدا کنیم.
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
    df['hour'] = df['dt'].dt.hour
    return df.reset_index(drop=True)


def ema(x, p): return pd.Series(x).ewm(span=p, adjust=False).mean().values
def rsi(x, p=14):
    d = np.diff(x, prepend=x[0])
    g = np.where(d>0,d,0.0); l = np.where(d<0,-d,0.0)
    ag = pd.Series(g).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag/np.where(al==0,np.nan,al); return 100-100/(1+rs)
def atr(h,l,c,p=14):
    tr=np.maximum.reduce([h-l,np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))]); tr[0]=h[0]-l[0]
    return pd.Series(tr).ewm(alpha=1/p, adjust=False).mean().values


def build(df):
    c=df['close'].values.astype(float); h=df['high'].values.astype(float); l=df['low'].values.astype(float)
    e50=ema(c,50); e200=ema(c,200); r14=rsi(c,14)
    at=atr(h,l,c,14); at_med=pd.Series(at).rolling(200).median().values
    up=np.diff(h,prepend=h[0]); dn=-np.diff(l,prepend=l[0])
    plus=np.where((up>dn)&(up>0),up,0.0); minus=np.where((dn>up)&(dn>0),dn,0.0)
    trv=np.maximum.reduce([h-l,np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))]); trv[0]=h[0]-l[0]
    atrv=pd.Series(trv).ewm(alpha=1/14,adjust=False).mean().values
    pdi=100*pd.Series(plus).ewm(alpha=1/14,adjust=False).mean().values/np.where(atrv==0,np.nan,atrv)
    mdi=100*pd.Series(minus).ewm(alpha=1/14,adjust=False).mean().values/np.where(atrv==0,np.nan,atrv)
    dx=100*np.abs(pdi-mdi)/np.where((pdi+mdi)==0,np.nan,(pdi+mdi))
    adx=pd.Series(dx).ewm(alpha=1/14,adjust=False).mean().values
    hi20=pd.Series(h).rolling(20).max().shift(1).values
    lo20=pd.Series(l).rolling(20).min().shift(1).values
    strong=(adx>30)&(at>1.2*at_med)
    def cl(x): return np.nan_to_num(x,nan=0).astype(bool)
    long_sig  = cl((c>hi20)&(e50>e200)&strong&(r14>50))
    short_sig = cl((c<lo20)&(e50<e200)&strong&(r14<50))
    return long_sig, short_sig


def report(df, lsig, ssig, sl, tp, mh, be, trail, label):
    tr = se.simulate_trades(df, lsig, ssig, sl, tp, ASSET, max_hold=mh,
                            allow_overlap=False, be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr)==0:
        print(f"{label}: بدونِ معامله"); return None
    n=len(df); mid=n//2
    def net(t):
        s,_=se.run_capital(t, ASSET); return s
    full=net(tr)
    h1=net(tr[tr['exit_bar']<mid]); h2=net(tr[tr['exit_bar']>=mid])
    wf=[net(tr[(tr['exit_bar']>=k*n//4)&(tr['exit_bar']<(k+1)*n//4)])['net_profit'] for k in range(4)]
    gates = h1['net_profit']>0 and h2['net_profit']>0 and all(w>0 for w in wf)
    print(f"{label:26} net=${full['net_profit']:>9,.0f} n={len(tr):>4} "
          f"WR={full['win_rate']:.0f}% PF={full['profit_factor']:.2f} DD={full['max_dd_pct']:.0f}% "
          f"Sh={full['sharpe']:.2f} h1=${h1['net_profit']:>7,.0f} h2=${h2['net_profit']:>7,.0f} "
          f"wf={[round(w) for w in wf]} {'✅' if gates else ''}")
    return dict(net=full['net_profit'], n=len(tr), wr=full['win_rate'], pf=full['profit_factor'],
                dd=full['max_dd_pct'], sharpe=full['sharpe'],
                h1=h1['net_profit'], h2=h2['net_profit'], wf=wf, gates=bool(gates))


def main():
    df=load()
    print(f"داده: {len(df)} کندلِ M5 طلا\n")
    lsig, ssig = build(df)
    empty=np.zeros(len(df),dtype=bool)

    # پارامترِ برندهٔ s120
    sl,tp,mh,be,trail = 40,400,60,15,12

    print("### تفکیکِ جهت (پارامترِ برندهٔ s120: SL40/TP400/mh60) ###")
    r_both  = report(df, lsig, ssig, sl,tp,mh,be,trail, "هر دو جهت")
    r_long  = report(df, lsig, empty, sl,tp,mh,be,trail, "فقط LONG")
    r_short = report(df, empty, ssig, sl,tp,mh,be,trail, "فقط SHORT")

    # فیلترِ سِشِن: فقط ساعاتِ پرنقدینگیِ لندن+نیویورک (UTC 7..20)
    print("\n### فیلترِ سِشِن (فقط UTC 7..20 — لندن/نیویورک) ###")
    sess = df['hour'].between(7,20).values
    ls_sess = lsig & sess; ss_sess = ssig & sess
    r_both_s  = report(df, ls_sess, ss_sess, sl,tp,mh,be,trail, "هر دو (سِشِن)")
    r_long_s  = report(df, ls_sess, empty,   sl,tp,mh,be,trail, "LONG (سِشِن)")
    r_short_s = report(df, empty,   ss_sess, sl,tp,mh,be,trail, "SHORT (سِشِن)")

    # اگر یک جهت سودده شد، شبکهٔ خروجِ ریزتر روی همان
    print("\n### جارویِ خروج روی بهترین جریانِ تک‌جهته (سِشِن) ###")
    best=None
    for (isl,itp,imh,ibe,itr) in [(40,300,48,15,12),(40,400,60,15,12),(50,400,60,20,15),
                                   (50,500,72,20,15),(40,600,96,15,12),(60,500,72,25,18),
                                   (50,250,48,20,15),(40,800,120,15,10)]:
        for name,(L,S) in [("SHORT",(empty,ss_sess)),("LONG",(ls_sess,empty)),
                            ("BOTH",(ls_sess,ss_sess))]:
            r=report(df,L,S,isl,itp,imh,ibe,itr,f"{name} SL{isl}/TP{itp}/mh{imh}")
            if r and r['gates'] and (best is None or r['net']>best[1]['net']):
                best=(f"{name} SL{isl}/TP{itp}/mh{imh}/be{ibe}/tr{itr}", r, name,isl,itp,imh,ibe,itr)

    print("\n"+"="*70)
    if best:
        tag,r,name,isl,itp,imh,ibe,itr=best
        print(f"🏆 بهترین جریانِ اسکالپِ M5 با گیتِ سبز: {tag} — net=${r['net']:,.0f}")
        out=dict(winner=tag, side=name, session="UTC7-20", sl=isl,tp=itp,mh=imh,be=ibe,trail=itr,
                 net=float(r['net']), n=int(r['n']), wr=float(r['wr']), pf=float(r['pf']),
                 dd=float(r['dd']), sharpe=float(r['sharpe']),
                 h1=float(r['h1']), h2=float(r['h2']), wf=[float(w) for w in r['wf']])
        with open(os.path.join(RESULTS,'_s121_dir_split.json'),'w') as f:
            json.dump(out,f,ensure_ascii=False,indent=1,default=float)
        print("✅ ذخیره: results/_s121_dir_split.json")
    else:
        print("❌ هیچ جریانِ تک‌جهته/سِشِنی همهٔ گیت‌ها را سبز نکرد — نیازِ به رویکردِ متفاوت.")


if __name__=='__main__':
    main()
