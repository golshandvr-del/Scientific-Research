"""
s125_scalp_trend_aligned_brain.py — موتورِ اسکالپِ M5 هم‌سو با «ذاتِ روند»
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت — در همهٔ اسناد تکرار می‌شود)
> **هدفِ پروژه فقط و فقط «سودِ خالصِ بیشتر» است — نه Win-Rate.**
> تعریفِ رسمیِ سودِ خالص = جمعِ سودِ دو ارز: XAUUSD + EURUSD. WR فقط گزارشی است.
================================================================================

انگیزه (پاسخِ مهندسیِ مستقیم به یافتهٔ فلسفیِ s123/s124):
  s124 به‌صورتِ کمّی ثابت کرد «ذاتِ» موتورِ اسکالپِ فعلی (S91: EMA20>EMA100 &
  RSI21<35) یک **تناقضِ درونی** است: شرطِ EMA می‌گوید «روند فعال است» ولی شرطِ
  RSI<35 می‌گوید «اشباعِ فروش». این دو در M5 فقط ۰.۱٪ کندل‌ها هم‌زمان‌اند ⇒ پوششِ
  ۱٪. یعنی این استراتژی یک «صیّادِ pullbackِ نادر» است (پاسخِ سؤالِ User Note:
  «s3 چرا فقط روندِ ۹ را گرفت؟» چون ذاتش نادر-یاب است).

  فرضیهٔ این چرخه: اگر ماشه را **هم‌سو با ذاتِ روند** کنیم (pullbackِ *سبک* به EMA
  در دلِ روندِ تأییدشده، نه اشباعِ عمیق)، پوشش بالا می‌رود؛ اما طبقِ درسِ s111 پوششِ
  بالا به‌تنهایی ارزش ندارد — فقط **سودِ خالص** مهم است. پس چند خانوادهٔ ماشهٔ
  هم‌سو-با-روند را با **دقیقاً همان موتورِ حسابداریِ S91** (hidden TP/SL + run_capital،
  risk ۱٪ روی ۱۰k، compounding) بک‌تست می‌کنیم و فقط برنده‌ای را می‌پذیریم که:
    (۱) سودِ خالصِ طلا-M5 از baselineِ S91 (+۱۰٬۰۴۴$) بیشتر باشد،
    (۲) هر دو نیمهٔ داده مثبت،
    (۳) هر ۴ پنجرهٔ walk-forward مثبت.
  اگر هیچ‌کدام نگذرد ⇒ صادقانه ثبت می‌کنیم که baseline دست‌نخورده می‌ماند (رکورد ثابت).

روش: هزینهٔ واقعیِ حساب (اسپردِ طلا ۴pip). موتورِ scalp_engine.simulate_trades.
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
BASELINE_NET = 10044.0   # سهمِ اسکالپِ S91 در رکوردِ فعلی


def load():
    df = pd.read_csv(DATA); df['dt'] = pd.to_datetime(df['time'], unit='s', utc=True)
    return df.reset_index(drop=True)


def ema(x, p): return pd.Series(x).ewm(span=p, adjust=False).mean().values
def sma(x, p): return pd.Series(x).rolling(p).mean().values
def rsi(x, p=14):
    d = np.diff(x, prepend=x[0]); g = np.where(d > 0, d, 0.0); l = np.where(d < 0, -d, 0.0)
    ag = pd.Series(g).ewm(alpha=1/p, adjust=False).mean().values
    al = pd.Series(l).ewm(alpha=1/p, adjust=False).mean().values
    rs = ag/np.where(al == 0, np.nan, al); return 100-100/(1+rs)
def atr(h, l, c, p=14):
    tr = np.maximum.reduce([h-l, np.abs(h-np.roll(c, 1)), np.abs(l-np.roll(c, 1))]); tr[0] = h[0]-l[0]
    return pd.Series(tr).ewm(alpha=1/p, adjust=False).mean().values


def indicators(df):
    c = df['close'].values.astype(float)
    h = df['high'].values.astype(float); l = df['low'].values.astype(float)
    ind = dict(
        c=c, h=h, l=l,
        e20=ema(c, 20), e50=ema(c, 50), e100=ema(c, 100), e200=ema(c, 200),
        e9=ema(c, 9), e21=ema(c, 21),
        r21=rsi(c, 21), r14=rsi(c, 14), r7=rsi(c, 7),
        at=atr(h, l, c, 14),
    )
    ind['at_med'] = pd.Series(ind['at']).rolling(200).median().values
    # ADX سبک
    up = np.diff(h, prepend=h[0]); dn = -np.diff(l, prepend=l[0])
    plus = np.where((up > dn) & (up > 0), up, 0.0); minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    trv = np.maximum.reduce([h-l, np.abs(h-np.roll(c, 1)), np.abs(l-np.roll(c, 1))]); trv[0] = h[0]-l[0]
    atrv = pd.Series(trv).ewm(alpha=1/14, adjust=False).mean().values
    pdi = 100*pd.Series(plus).ewm(alpha=1/14, adjust=False).mean().values/np.where(atrv == 0, np.nan, atrv)
    mdi = 100*pd.Series(minus).ewm(alpha=1/14, adjust=False).mean().values/np.where(atrv == 0, np.nan, atrv)
    dx = 100*np.abs(pdi-mdi)/np.where((pdi+mdi) == 0, np.nan, (pdi+mdi))
    ind['adx'] = pd.Series(dx).ewm(alpha=1/14, adjust=False).mean().values
    return ind


def clean(x): return np.nan_to_num(x, nan=0).astype(bool)


def build_families(ind):
    """
    ماشه‌های LONG هم‌سو با ذاتِ روند. کلیدِ طراحی: به‌جای «RSI<35 (اشباعِ عمیق)»،
    از «pullbackِ سبک به EMA در روندِ تأییدشده» یا «ادامهٔ momentum» استفاده می‌کنیم.
    همه با فیلترِ رژیم گیت می‌شوند تا در رنج نابود نشوند (درسِ s120).
    """
    c, h, l = ind['c'], ind['h'], ind['l']
    e9, e21, e20, e50, e100, e200 = ind['e9'], ind['e21'], ind['e20'], ind['e50'], ind['e100'], ind['e200']
    r21, r14 = ind['r21'], ind['r14']
    adx, at, at_med = ind['adx'], ind['at'], ind['at_med']

    trend_up = e50 > e100                                  # رژیمِ صعودیِ ساختاری
    vol_ok = at > at_med                                   # نوسانِ کافی (نه رنجِ مرده)
    reg = trend_up & (adx > 20)                            # فیلترِ رژیمِ ملایم

    slope20 = e20 - np.roll(e20, 3)

    fam = {}

    # A) baselineِ فعلی (بازتولیدِ دقیقِ S91): اشباعِ عمیقِ نادر
    fam['A_S91_baseline'] = clean((e20 > e100) & (r21 < 35))

    # B) pullbackِ سبک: در روندِ صعودی، قیمت به EMA20 برگردد و RSI *ملایم* افت کند
    fam['B_light_pullback'] = clean(trend_up & (c <= e20*1.001) & (c > e50) & (r21 < 50) & (r21 > 35) & (adx > 20))

    # C) ادامهٔ momentum: قیمت بالای همهٔ EMAها، RSI رو به بالا از میانه عبور کند
    cross_up_50 = (r14 > 50) & (np.roll(r14, 1) <= 50)
    fam['C_momentum_cont'] = clean(reg & (c > e20) & (e20 > e50) & cross_up_50)

    # D) pullback به EMA50 (عمیق‌تر ولی هنوز در روند) + کندلِ برگشتی
    bull_candle = c > df_open_shift(ind)
    fam['D_ema50_pullback'] = clean(trend_up & (l <= e50) & (c > e50) & bull_candle & (adx > 18))

    # E) EMA9/21 cross در رژیمِ روندی (ماشهٔ کلاسیکِ آغازِ حرکت)
    ec = (e9 > e21) & (np.roll(e9, 1) <= np.roll(e21, 1))
    fam['E_ema9_21_cross'] = clean(ec & (c > e50) & reg)

    # F) ترکیب: pullbackِ سبک یا momentum (اجتماعِ B و C) — پوششِ بیشتر
    fam['F_union_BC'] = clean(fam['B_light_pullback'] | fam['C_momentum_cont'])

    return fam


def df_open_shift(ind):
    # کندلِ صعودی: close > open ⇒ open را نداریم مستقیم؛ از close قبلی تقریب می‌زنیم
    return np.roll(ind['c'], 1)


def evaluate(df, long_sig, sl, tp, mh, be, trail):
    empty_short = np.zeros(len(df), dtype=bool)
    tr = se.simulate_trades(df, long_sig, empty_short, sl, tp, ASSET,
                            max_hold=mh, allow_overlap=False,
                            be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    s, _ = se.run_capital(tr, ASSET, initial_capital=10_000.0, risk_pct=1.0, compounding=True)
    n = len(df); mid = n//2
    s1, _ = se.run_capital(tr[tr['exit_bar'] < mid], ASSET, compounding=True)
    s2, _ = se.run_capital(tr[tr['exit_bar'] >= mid], ASSET, compounding=True)
    wf = []
    for k in range(4):
        aa = k*n//4; bb = (k+1)*n//4
        sk, _ = se.run_capital(tr[(tr['exit_bar'] >= aa) & (tr['exit_bar'] < bb)], ASSET, compounding=True)
        wf.append(sk['net_profit'])
    return dict(net=s['net_profit'], wr=s['win_rate'], pf=s['profit_factor'],
                dd=s['max_dd_pct'], sharpe=s['sharpe'], n=len(tr),
                h1=s1['net_profit'], h2=s2['net_profit'], wf=wf)


def main():
    global df_open  # برای df_open_shift
    df = load()
    print(f"داده: {len(df)} کندلِ M5 طلا ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")
    print(f"baselineِ اسکالپِ فعلی (S91): +${BASELINE_NET:,.0f}\n")
    ind = indicators(df)
    fams = build_families(ind)

    # همان شبکهٔ خروجِ اسکالپ (شاملِ hidden TP120/SL80 که baselineِ S91 است)
    exit_grid = [
        (80, 120, 288, None, None),   # ← دقیقاً hidden-target S91 (SL80/TP120)
        (60, 120, 48, 30, 20),
        (50, 150, 48, 25, 18),
        (60, 180, 60, 30, 20),
        (40, 200, 72, 20, 15),
        (50, 300, 96, 25, 20),
        (60, 400, 120, 30, 25),       # «بگذار بردها بدوند»
    ]

    best = None
    rows = []
    for fname, lsig in fams.items():
        nfire = int(lsig.sum())
        for (sl, tp, mh, be, trail) in exit_grid:
            r = evaluate(df, lsig, sl, tp, mh, be, trail)
            if r is None:
                continue
            gates = (r['h1'] > 0 and r['h2'] > 0 and all(w > 0 for w in r['wf'])
                     and r['net'] > BASELINE_NET)
            tag = f"{fname:20} SL{sl}/TP{tp}/mh{mh}/be{be}/tr{trail}"
            rows.append((tag, r, gates, fname))
            flag = '✅BEATS' if gates else ''
            print(f"{tag:52} fire={nfire:>5} net=${r['net']:>9,.0f} n={r['n']:>4} "
                  f"WR={r['wr']:.0f}% PF={r['pf']:.2f} h1=${r['h1']:>7,.0f} h2=${r['h2']:>7,.0f} {flag}")
            if gates and (best is None or r['net'] > best[1]['net']):
                best = (tag, r, sl, tp, mh, be, trail, fname)

    print("\n" + "="*74)
    if best:
        tag, r, sl, tp, mh, be, trail, fname = best
        print(f"🏆 برنده‌ای که baselineِ اسکالپ را شکست (همهٔ گیت‌ها سبز):\n   {tag}")
        print(f"   net=${r['net']:,.0f} (baseline +${BASELINE_NET:,.0f}, Δ +${r['net']-BASELINE_NET:,.0f}) "
              f"| WR={r['wr']:.1f}% PF={r['pf']:.2f} DD={r['dd']:.1f}% Sharpe={r['sharpe']:.2f}")
        print(f"   h1=${r['h1']:,.0f} h2=${r['h2']:,.0f} | wf={[round(w) for w in r['wf']]}")
        out = dict(status='BEATS_BASELINE', winner=tag, family=fname,
                   sl=sl, tp=tp, mh=mh, be=be, trail=trail, baseline=BASELINE_NET,
                   **{k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v)
                      for k, v in r.items() if k != 'wf'},
                   wf=[float(w) for w in r['wf']])
    else:
        print("❌ هیچ خانواده‌ای همهٔ گیت‌ها را پاس نکرد و baselineِ اسکالپ را نشکست.")
        print("   ⇒ صادقانه: baselineِ S91 دست‌نخورده می‌ماند؛ رکوردِ کل +$95,645 ثابت.")
        # بهترین «سود» بدونِ قیدِ baseline را هم گزارش کن (برای تحلیل)
        cand = [row for row in rows if row[1]['h1'] > 0 and row[1]['h2'] > 0 and all(w > 0 for w in row[1]['wf'])]
        cand.sort(key=lambda x: -x[1]['net'])
        if cand:
            t, rr, _, fn = cand[0]
            print(f"   بهترین کاندید با گیت‌های both-halves+WF (ولی زیرِ baseline): {t} net=${rr['net']:,.0f}")
        out = dict(status='BASELINE_UNCHANGED', baseline=BASELINE_NET,
                   best_gated=(dict(tag=cand[0][0], net=float(cand[0][1]['net'])) if cand else None))
    with open(os.path.join(RESULTS, '_s125_trend_aligned.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print("\n✅ ذخیره شد: results/_s125_trend_aligned.json")


if __name__ == '__main__':
    main()
