# -*- coding: utf-8 -*-
"""
S172 — Al Brooks «Two Legs» (فصلِ ۲۰ کتابِ Trading Price Action: TRENDS)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR تابعِ هدف نیست اما هر لایهٔ
> فعال باید WR≥۴۰٪ داشته باشد. تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (کتاب، فصلِ ۲۰ — «Two Legs»):
  نقلِ محوریِ Brooks: «The market regularly tries to do something twice, and this
  is why all moves tend to subdivide into two smaller moves. If it fails in its two
  attempts, it will usually try to do the opposite. If it succeeds, it will often
  then extend the trend.»
  یعنی هر حرکت (چه هم‌جهتِ روند، چه ضدِروند) تمایل دارد به **دو legِ کوچک‌تر** تقسیم
  شود. دو پیامدِ معاملاتیِ صریحِ فصل که *هنوز کدنویسی نشده‌اند*:

  (الف) ادامهٔ روند با **two-legged pullback مبتنی بر swing-pivot** (نه صرفِ
       bar-counting مثلِ S168). Brooks: در روندِ صعودی، اصلاح در دو legِ نزولی
       فرود می‌آید (A=leg اول، B=رالیِ میانی، C=leg دوم)؛ ورودِ Long وقتی legِ دوم
       تمام و رالیِ ادامهٔ روند شروع شود. تفاوت با S168: اینجا legها با
       **pivotهای ساختاری (swing high/low)** شمرده می‌شوند، نه high>high[1].

  (ب) **Two-legged reversal** (double-top/double-bottom ساختاری): Brooks: «If it
       fails in its two attempts, it will usually try to do the opposite.» —
       دو تلاشِ ناموفق برای عبور از یک extreme ⇒ برگشت. این یک لبهٔ **برگشتی/SHORT**
       است که پرتفوی به‌شدت به آن نیاز دارد (تنها لبهٔ SHORTِ اثبات‌شده تا کنون
       SHORT-MA-Confluence بود).

تعریفِ مکانیکیِ swing-pivot (causal، shift-safe):
  swing-high در اندیس i = high[i] بزرگ‌تر از high در k کندلِ چپ و k کندلِ راست.
  چون به k کندلِ راست نیاز است، pivot فقط با تأخیرِ k کندل «تأییدشده» تلقی می‌شود
  ⇒ همهٔ تصمیم‌ها با اطلاعاتِ در-دسترسِ همان لحظه گرفته و سپس shift(1) می‌شوند.

گیتِ پذیرش (سیب‌به‌سیب با S168/S171):
  net>0 کل + net>0 در هر دو نیمه + WR≥۴۰٪ + n≥۳۰ (+ walk-forward جداگانه).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK, YEARS = 10000.0, 1.0, 4
WR_FLOOR = 40.0
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


# ---------- بارگذاری/کمکی (هم‌سو با s171/s168) ----------
def load(tf):
    df = pd.read_csv(os.path.join(ROOT, 'data', tf + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def lastn(df, y=YEARS):
    end = df['dt'].iloc[-1]
    return df[df['dt'] >= end - pd.DateOffset(years=y)].reset_index(drop=True)


def stats(tr, asset):
    if tr is None or len(tr) == 0:
        return dict(net=0.0, n=0, wins=0, losses=0, wr=0.0, pf=0.0)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=True)
    nu = pt['net_usd'].values
    w = int((nu > 0).sum()); l = int((nu <= 0).sum()); n = len(nu)
    gp = float(nu[nu > 0].sum()); gl = float(-nu[nu <= 0].sum())
    return dict(net=float(st['net_profit']), n=n, wins=w, losses=l,
                wr=(w / n * 100 if n else 0.0), pf=(gp / gl if gl > 0 else float('inf')))


def sim(df, ls, shs, sl, tp, mh, asset):
    t = se.simulate_trades(df, ls, shs, sl, tp, asset, max_hold=mh, allow_overlap=False)
    if t is None or len(t) == 0:
        return None
    t = t.copy(); t['sl_pip'] = float(sl if np.isscalar(sl) else np.asarray(sl).flat[0])
    return t


def halves(df, ls, shs, sl, tp, mh, asset):
    tr = sim(df, ls, shs, sl, tp, mh, asset)
    if tr is None or len(tr) < 30:
        return None
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=False)
    nu = pt['net_usd']; h = len(nu) // 2
    return dict(h1=float(nu.iloc[:h].sum()), h2=float(nu.iloc[h:].sum()))


# ============================================================================
#  swing-pivot ساختاری (causal، با تأخیرِ تأییدِ k کندل)
# ============================================================================
def swing_pivots(high, low, k):
    """آرایه‌های بولی swing_high / swing_low — نسخهٔ vectorized.
    pivot در i وقتی high[i] اکیداً بزرگ‌تر از k همسایهٔ چپ و راست باشد.
    مقدار در اندیسِ i علامت‌گذاری می‌شود ولی تنها i+k «قابلِ مشاهده» است
    (چون به k کندلِ راست نیاز دارد). این تأخیر در توابعِ پایین لحاظ می‌شود.
    """
    n = len(high)
    hs = pd.Series(high); ls = pd.Series(low)
    win = 2 * k + 1
    # بیشینه/کمینهٔ متحرکِ متمرکز؛ pivot = اکیداً بزرگ‌ترِ منحصربه‌فردِ پنجره.
    # شرطِ «منحصربه‌فرد» را با «pivot اکیداً بزرگ‌تر از max همهٔ همسایه‌ها» می‌سازیم:
    # با گرفتنِ max/min روی پنجرهٔ همسایه‌ها (بدونِ خودِ i) و مقایسهٔ اکید.
    left_hmax = hs.shift(1).rolling(k).max().to_numpy()
    right_hmax = hs.shift(-k).rolling(k).max().to_numpy()
    left_lmin = ls.shift(1).rolling(k).min().to_numpy()
    right_lmin = ls.shift(-k).rolling(k).min().to_numpy()
    sh = (high > np.nan_to_num(left_hmax, nan=-1e18)) & (high > np.nan_to_num(right_hmax, nan=-1e18))
    sl_ = (low < np.nan_to_num(left_lmin, nan=1e18)) & (low < np.nan_to_num(right_lmin, nan=1e18))
    # لبه‌ها (که همسایهٔ کامل ندارند) را pivot نمی‌گیریم
    sh[:k] = False; sh[n - k:] = False
    sl_[:k] = False; sl_[n - k:] = False
    return sh.astype(bool), sl_.astype(bool)


# ============================================================================
#  (الف) Two-Legged Pullback Continuation (swing-pivot based)
# ============================================================================
def two_leg_pullback_signals(df, ema_fast, ema_slow, k, side):
    """در روندِ صعودی: پس از دیدنِ دو swing-low متوالیِ نزولی (دو legِ اصلاح)
    که هنوز بالاتر از آخرین swing-low پیش از اصلاح‌اند (higher-low structure)،
    ورودِ Long روی کندلِ تأییدِ pivot. قرینه برای short.
    همه با تأخیرِ k کندلِ تأییدِ pivot + یک shift اضافه (ضدِ look-ahead)."""
    high = df['high'].to_numpy(); low = df['low'].to_numpy(); close = df['close'].to_numpy()
    ef = ind.ema(pd.Series(close), ema_fast).to_numpy()
    es = ind.ema(pd.Series(close), ema_slow).to_numpy()
    n = len(df)
    sh, sl_ = swing_pivots(high, low, k)
    sig = np.zeros(n, bool)

    if side == 'long':
        # اندیسِ swing-lowها به‌ترتیب؛ فقط پس از i+k قابلِ استفاده
        low_idx = [i for i in range(n) if sl_[i]]
        for j in range(1, len(low_idx)):
            i2 = low_idx[j]; i1 = low_idx[j - 1]
            conf = i2 + k                      # کندلی که این pivot تأیید می‌شود
            if conf >= n:
                continue
            # رژیمِ صعودی در لحظهٔ تأیید + ساختارِ دو-پایه (legِ دوم پایین‌تر از legِ اول
            # ولی هر دو بالاتر از سطحِ EMA ⇒ اصلاحِ درونِ روند، نه شکست)
            if ef[conf] > es[conf] and low[i2] < low[i1] and close[conf] > es[conf]:
                sig[conf] = True
    else:
        high_idx = [i for i in range(n) if sh[i]]
        for j in range(1, len(high_idx)):
            i2 = high_idx[j]; i1 = high_idx[j - 1]
            conf = i2 + k
            if conf >= n:
                continue
            if ef[conf] < es[conf] and high[i2] > high[i1] and close[conf] < es[conf]:
                sig[conf] = True
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


# ============================================================================
#  (ب) Two-Legged Reversal (double-top / double-bottom ساختاری)
# ============================================================================
def two_leg_reversal_signals(df, k, tol_frac, lookback, side):
    """Brooks: دو تلاشِ ناموفق برای عبور از یک extreme ⇒ برگشت.
    double-top: دو swing-high نزدیک‌به‌هم (اختلاف ≤ tol_frac×قیمت) در پنجرهٔ lookback
    که دومی از اولی عبور نکرده ⇒ سیگنالِ Short. قرینه double-bottom ⇒ Long."""
    high = df['high'].to_numpy(); low = df['low'].to_numpy(); close = df['close'].to_numpy()
    n = len(df)
    sh, sl_ = swing_pivots(high, low, k)
    sig = np.zeros(n, bool)

    if side == 'short':
        hi_idx = [i for i in range(n) if sh[i]]
        for j in range(1, len(hi_idx)):
            i2 = hi_idx[j]; i1 = hi_idx[j - 1]
            conf = i2 + k
            if conf >= n or (i2 - i1) > lookback:
                continue
            tol = tol_frac * high[i1]
            # دومین قله در محدودهٔ تحملِ اولی و آن را نشکسته (تستِ دو-پایهٔ ناموفق)
            if abs(high[i2] - high[i1]) <= tol and high[i2] <= high[i1] + tol:
                sig[conf] = True
    else:
        lo_idx = [i for i in range(n) if sl_[i]]
        for j in range(1, len(lo_idx)):
            i2 = lo_idx[j]; i1 = lo_idx[j - 1]
            conf = i2 + k
            if conf >= n or (i2 - i1) > lookback:
                continue
            tol = tol_frac * low[i1]
            if abs(low[i2] - low[i1]) <= tol and low[i2] >= low[i1] - tol:
                sig[conf] = True
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def evaluate(df, asset, sig, side, sl, tp, mh):
    z = np.zeros(len(df), bool)
    if side == 'long':
        tr = sim(df, sig, z, sl, tp, mh, asset)
    else:
        tr = sim(df, z, sig, sl, tp, mh, asset)
    r = stats(tr, asset)
    if r['n'] < 30:
        return None
    hv = halves(df, sig if side == 'long' else z, z if side == 'long' else sig, sl, tp, mh, asset)
    acc = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and hv and hv['h1'] > 0 and hv['h2'] > 0)
    return dict(asset=asset, side=side, sl=sl, tp=tp, mh=mh,
                net=r['net'], wr=r['wr'], n=r['n'], pf=(r['pf'] if r['pf'] != float('inf') else 999.0),
                h1=(hv['h1'] if hv else None), h2=(hv['h2'] if hv else None), accepted=acc)


def main():
    print("=" * 100)
    print("S172 — Al Brooks «Two Legs» (فصلِ ۲۰): (الف) two-leg pullback  (ب) two-leg reversal")
    print("گیت: net>0 + هر دو نیمه + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    dfx = lastn(load('XAUUSD_M15'))
    dfe = lastn(load('EURUSD_M15'))
    grids = {'XAUUSD': [(150, 225), (200, 300), (250, 375), (300, 450)],
             'EURUSD': [(15, 22), (20, 30), (25, 45), (30, 45)]}
    mhs = [16, 32, 48]
    report = {}

    # ---------- (الف) Two-Legged Pullback ----------
    print("\n### (الف) Two-Legged Pullback Continuation (swing-pivot) ###")
    pullback = []
    for asset, df in (('XAUUSD', dfx), ('EURUSD', dfe)):
        for side in ('long', 'short'):
            for (ef, es) in [(20, 50), (10, 30)]:
                for k in (3, 5):
                    sig = two_leg_pullback_signals(df, ef, es, k, side)  # یک‌بار محاسبه
                    for (sl, tp) in grids[asset]:
                        for mh in mhs:
                            r = evaluate(df, asset, sig, side, sl, tp, mh)
                            if r:
                                r.update(ema_fast=ef, ema_slow=es, k=k)
                                pullback.append(r)
        best = sorted([x for x in pullback if x['asset'] == asset], key=lambda x: x['net'], reverse=True)[:6]
        print(f"\n  {asset}: بهترین‌ها بر اساس net")
        for x in best:
            tag = '✅ACCEPT' if x['accepted'] else 'reject'
            print(f"    {tag} {x['side']:5s} ema{x['ema_fast']}/{x['ema_slow']} k{x['k']} "
                  f"SL{x['sl']}/TP{x['tp']}/mh{x['mh']:2d}  net=${x['net']:+8,.0f} "
                  f"WR={x['wr']:5.1f}% n={x['n']:4d} PF={x['pf']:.2f}")
    report['pullback'] = pullback

    # ---------- (ب) Two-Legged Reversal ----------
    print("\n### (ب) Two-Legged Reversal (double-top/bottom) ###")
    reversal = []
    for asset, df in (('XAUUSD', dfx), ('EURUSD', dfe)):
        for side in ('short', 'long'):
            for k in (3, 5):
                for tol in (0.0015, 0.003):
                    for lb in (30, 60):
                        sig = two_leg_reversal_signals(df, k, tol, lb, side)
                        for (sl, tp) in grids[asset]:
                            for mh in mhs:
                                r = evaluate(df, asset, sig, side, sl, tp, mh)
                                if r:
                                    r.update(k=k, tol=tol, lb=lb)
                                    reversal.append(r)
        best = sorted([x for x in reversal if x['asset'] == asset], key=lambda x: x['net'], reverse=True)[:6]
        print(f"\n  {asset}: بهترین‌ها بر اساس net")
        for x in best:
            tag = '✅ACCEPT' if x['accepted'] else 'reject'
            print(f"    {tag} {x['side']:5s} k{x['k']} tol{x['tol']} lb{x['lb']} "
                  f"SL{x['sl']}/TP{x['tp']}/mh{x['mh']:2d}  net=${x['net']:+8,.0f} "
                  f"WR={x['wr']:5.1f}% n={x['n']:4d} PF={x['pf']:.2f}")
    report['reversal'] = reversal

    # ---------- خلاصهٔ کاندیداهای پذیرفته ----------
    acc_all = [x for x in (pullback + reversal) if x['accepted']]
    acc_all.sort(key=lambda x: x['net'], reverse=True)
    report['accepted_sorted'] = acc_all
    print("\n" + "=" * 100)
    print(f"تعدادِ کاندیدِ پذیرفته (net>0 + هر دو نیمه + WR≥40): {len(acc_all)}")
    for x in acc_all[:8]:
        fam = 'pullback' if 'ema_fast' in x else 'reversal'
        print(f"  [{fam}] {x['asset']} {x['side']} net=${x['net']:+,.0f} WR={x['wr']:.1f}% n={x['n']} PF={x['pf']:.2f}")

    with open(os.path.join(RESULTS, '_s172_two_legs.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s172_two_legs.json")


if __name__ == '__main__':
    main()
