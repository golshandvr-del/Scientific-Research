"""
s120_m5_dual_scalp_brain.py — مغزِ اسکالپِ M5 دوطرفه (long + short) — استراتژیِ نو
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD. WR فقط گزارشی است.
================================================================================

انگیزه (پاسخِ مستقیم به User Note):
  s119 (کارتِ امتیازِ M5) ثابت کرد مغزِ اسکالپِ فعلیِ سایت (S91: EMA20>EMA100 &
  RSI21<35، فقط long) روی M5 فقط **~۱٪** روندها را کشف می‌کند و **هیچ short ندارد**.
  اکتشافِ explore_m5_scalp_coverage نشان داد خانوادهٔ سیگنالِ درست می‌تواند پوششِ
  ۵۰–۷۵٪ با دقتِ شروعِ قابل‌قبول بدهد. این فایل یک **مغزِ اسکالپِ M5 دوطرفه** می‌سازد و
  با موتورِ واقعیِ scalp_engine (هزینهٔ واقعیِ حساب) بک‌تست و انتخابِ پارامتر می‌کند.

روش:
  • داده: XAUUSD_M5 کامل (۲۰۰k کندل).
  • چند «ماشهٔ ورود» دوطرفه + چند «طرحِ خروج» جارو می‌شود.
  • انتخابِ برنده صرفاً بر اساسِ **سودِ خالصِ دلاری** + گیت‌های ضدِ overfit:
      - هر دو نیمهٔ داده مثبت
      - هر ۴ پنجرهٔ walk-forward مثبت
  • هزینه واقعی: اسپردِ طلا ۴pip، اسلیپیج ۰.۵pip، کمیسیون صفر (طبقِ حسابِ کاربر).
================================================================================
"""
import sys, os, json, itertools
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


def ema(x, p): return pd.Series(x).ewm(span=p, adjust=False).mean().values
def sma(x, p): return pd.Series(x).rolling(p).mean().values
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


def build_signals(df):
    """چند خانوادهٔ ماشهٔ دوطرفه تولید کن. خروجی: dict[name] = (long_bool, short_bool).

    کشفِ کلیدیِ نسخهٔ اول (همه در h1 ضرر، در h2 سودِ نجومی):
      اسکالپِ M5 با تعدادِ زیادِ معامله در بازارِ رنج/بی‌روند (به‌خاطرِ اسپردِ ۴pipِ طلا)
      نابود می‌شود؛ ولی در رژیمِ روندی سودِ عظیم می‌دهد. پس ماشه باید با **فیلترِ رژیم**
      (ADX + گسترشِ ATR) گیت شود تا فقط در رژیمِ پرنوسان/روندی فایر کند و تعدادِ معامله
      شدیداً کاهش یابد (کیفیت بر کمیت). این پاسخِ فلسفیِ «محلِ درستِ استفاده» است.
    """
    c = df['close'].values.astype(float)
    h = df['high'].values.astype(float); l = df['low'].values.astype(float)
    e9=ema(c,9); e21=ema(c,21); e50=ema(c,50); e100=ema(c,100); e200=ema(c,200)
    r7=rsi(c,7); r14=rsi(c,14)
    at = atr(h,l,c,14)
    at_med = pd.Series(at).rolling(200).median().values      # ATRِ نرمالِ بلندمدت
    # ADXِ سبک (بدونِ وابستگی به indicators.py برای سرعت)
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    plus = np.where((up>dn)&(up>0), up, 0.0); minus = np.where((dn>up)&(dn>0), dn, 0.0)
    trv = np.maximum.reduce([h-l, np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))]); trv[0]=h[0]-l[0]
    atrv = pd.Series(trv).ewm(alpha=1/14, adjust=False).mean().values
    pdi = 100*pd.Series(plus).ewm(alpha=1/14, adjust=False).mean().values/np.where(atrv==0,np.nan,atrv)
    mdi = 100*pd.Series(minus).ewm(alpha=1/14, adjust=False).mean().values/np.where(atrv==0,np.nan,atrv)
    dx = 100*np.abs(pdi-mdi)/np.where((pdi+mdi)==0,np.nan,(pdi+mdi))
    adx = pd.Series(dx).ewm(alpha=1/14, adjust=False).mean().values

    slope9 = e9 - np.roll(e9,3)
    hi10 = pd.Series(h).rolling(10).max().shift(1).values
    lo10 = pd.Series(l).rolling(10).min().shift(1).values
    hi20 = pd.Series(h).rolling(20).max().shift(1).values
    lo20 = pd.Series(l).rolling(20).min().shift(1).values

    def clean(x): return np.nan_to_num(x, nan=0).astype(bool)

    # فیلترِ رژیم: فقط وقتی روند/نوسان کافی است اجازهٔ ورود بده
    trend_ok = (adx > 25) & (at > at_med)          # رژیمِ روندیِ پرنوسان
    strong_trend = (adx > 30) & (at > 1.2*at_med)  # سخت‌گیرتر

    sigs = {}

    # J) Breakout10 فقط در رژیمِ روندی (فیلترِ ADX+ATR)
    j_l = (c>hi10) & (e9>e21) & (c>e50) & trend_ok
    j_s = (c<lo10) & (e9<e21) & (c<e50) & trend_ok
    sigs['J_break10_regime'] = (clean(j_l), clean(j_s))

    # K) Breakout20 فقط در رژیمِ روندیِ قوی (کمترین معامله، بالاترین کیفیت)
    k_l = (c>hi20) & (slope9>0) & (c>e50) & strong_trend
    k_s = (c<lo20) & (slope9<0) & (c<e50) & strong_trend
    sigs['K_break20_strongreg'] = (clean(k_l), clean(k_s))

    # L) EMA9/21 cross فقط در رژیمِ روندی
    ec  = (e9>e21) & (np.roll(e9,1)<=np.roll(e21,1)) & (c>e50) & trend_ok
    ecs = (e9<e21) & (np.roll(e9,1)>=np.roll(e21,1)) & (c<e50) & trend_ok
    sigs['L_emacross_regime'] = (clean(ec), clean(ecs))

    # M) HTF-aligned breakout: علاوه بر رژیم، همسو با روندِ کندِ EMA200
    m_l = (c>hi20) & (e50>e200) & strong_trend & (r14>50)
    m_s = (c<lo20) & (e50<e200) & strong_trend & (r14<50)
    sigs['M_htf_break20'] = (clean(m_l), clean(m_s))

    return sigs


def stats_from_trades(trades, sub_df):
    s, eq = se.run_capital(trades, ASSET, initial_capital=10_000.0, risk_pct=1.0)
    return s


def evaluate(df, long_sig, short_sig, sl, tp, mh, be, trail):
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False,
                            be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    s, eq = se.run_capital(tr, ASSET, initial_capital=10_000.0, risk_pct=1.0)
    # نیمه‌ها
    n = len(df); mid = n//2
    trh1 = tr[tr['exit_bar'] < mid]; trh2 = tr[tr['exit_bar'] >= mid]
    s1,_ = se.run_capital(trh1, ASSET); s2,_ = se.run_capital(trh2, ASSET)
    # walk-forward ۴ پنجره
    wf = []
    for k in range(4):
        aa = k*n//4; bb = (k+1)*n//4
        trk = tr[(tr['exit_bar']>=aa)&(tr['exit_bar']<bb)]
        sk,_ = se.run_capital(trk, ASSET)
        wf.append(sk['net_profit'])
    return dict(net=s['net_profit'], wr=s['win_rate'], pf=s['profit_factor'],
                dd=s['max_dd_pct'], sharpe=s['sharpe'], n=len(tr),
                nlong=int((tr['direction']=='long').sum()),
                nshort=int((tr['direction']=='short').sum()),
                h1=s1['net_profit'], h2=s2['net_profit'], wf=wf)


def main():
    df = load()
    print(f"داده: {len(df)} کندلِ M5 طلا ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    sigs = build_signals(df)

    # شبکهٔ خروج (pip طلا): SL, TP, max_hold, be, trail
    exit_grid = [
        # (sl, tp, mh, be, trail)  — اسکالپِ سریع تا نیمه‌سوینگ
        (30, 60, 12, None, None),
        (30, 90, 16, 15, 10),
        (40, 80, 16, 20, 12),
        (40, 120, 24, 20, 15),
        (50, 150, 32, 25, 18),
        (50, 250, 48, 20, 15),
        (60, 300, 48, 25, 20),
        (40, 400, 60, 15, 12),   # «بگذار بردها بدوند» — اسکالپِ trailing بلند
    ]

    best = None
    rows = []
    for sname, (lsig, ssig) in sigs.items():
        for (sl, tp, mh, be, trail) in exit_grid:
            r = evaluate(df, lsig, ssig, sl, tp, mh, be, trail)
            if r is None: continue
            gates = (r['h1']>0 and r['h2']>0 and all(w>0 for w in r['wf']))
            tag = f"{sname} SL{sl}/TP{tp}/mh{mh}/be{be}/tr{trail}"
            rows.append((tag, r, gates))
            flag = '✅GATES' if gates else ''
            print(f"{tag:44} net=${r['net']:>9,.0f} n={r['n']:>4} "
                  f"L/S={r['nlong']}/{r['nshort']} WR={r['wr']:.0f}% PF={r['pf']:.2f} "
                  f"h1=${r['h1']:>7,.0f} h2=${r['h2']:>7,.0f} {flag}")
            # فقط کاندیدهایی که همهٔ گیت‌ها را پاس کنند برای «برنده» واجدند
            if gates and (best is None or r['net'] > best[1]['net']):
                best = (tag, r, sl, tp, mh, be, trail, sname)

    print("\n" + "="*70)
    if best:
        tag, r, sl, tp, mh, be, trail, sname = best
        print(f"🏆 برندهٔ اسکالپِ M5 دوطرفه (همهٔ گیت‌ها سبز): {tag}")
        print(f"   net=${r['net']:,.0f} | L/S={r['nlong']}/{r['nshort']} | "
              f"WR={r['wr']:.1f}% PF={r['pf']:.2f} DD={r['dd']:.1f}% Sharpe={r['sharpe']:.2f}")
        print(f"   h1=${r['h1']:,.0f} h2=${r['h2']:,.0f} | wf={[round(w) for w in r['wf']]}")
        out = dict(winner=tag, signal=sname, sl=sl, tp=tp, mh=mh, be=be, trail=trail,
                   **{k:(float(v) if isinstance(v,(int,float,np.floating,np.integer)) else v)
                      for k,v in r.items() if k!='wf'},
                   wf=[float(w) for w in r['wf']])
        with open(os.path.join(RESULTS,'_s120_dual_scalp.json'),'w') as f:
            json.dump(out, f, ensure_ascii=False, indent=1, default=float)
        print("\n✅ ذخیره شد: results/_s120_dual_scalp.json")
    else:
        print("❌ هیچ کاندیدی همهٔ گیت‌های ضدِ overfit را پاس نکرد.")


if __name__ == '__main__':
    main()
