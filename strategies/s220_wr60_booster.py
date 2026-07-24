# -*- coding: utf-8 -*-
"""
s220_wr60_booster.py — موتورِ سیستماتیکِ ارتقای WR هر لایه به بالای ۶۰٪ (پاسخِ User Note)
================================================================================
> # 🎯 قانونِ احیای پروژه (این نشست — بالاترین اولویت)
> کاربر صریحاً گفت: «WR را به هر قیمتی بالای ۶۰٪ ببر. سودِ خالصِ لایه می‌تواند هر
> میزان کاهش یابد، به شرطِ آنکه WR بالای ۶۰٪ تضمین شود.»
> پس تابعِ هدفِ این نشست: **بیشینه‌سازیِ سودِ خالص، مشروط بر قیدِ سختِ WR ≥ ۶۰٪.**
> (اگر net منفی شود لایه رد است؛ میانِ همهٔ پیکربندی‌های net>0 و WR≥۶۰، بیشترین net
>  انتخاب می‌شود.)

--------------------------------------------------------------------------------
تحلیلِ ریشه‌ایِ چرا WR فعلی پایین است (ممیزیِ audit_all_layers):
  لایه‌های زمان-محورِ فعلی TP/SL شدیداً نامتقارن دارند (مثلاً S141: SL100/TP700 = 1:7).
  این ساختار *به‌عمد* برای «بیشینهٔ سودِ خالص با WR≥۴۰» طراحی شده بود — TPِ دور به‌ندرت
  پُر می‌شود ⇒ WR ذاتاً پایین (۳۵–۴۸٪). هیچ فیلتری نمی‌تواند لایه‌ای با TP:SL=1:7 را به
  WR≥۶۰ برساند مگر ساختارِ خروج تغییر کند.

دو اهرمِ ریاضیِ مستقل برای WR≥۶۰ (هر دو هم‌زمان جستجو می‌شوند):
  اهرمِ ۱ — بازطراحیِ TP/SL به سمتِ WR-friendly:
     نسبتِ TP:SL نزدیک به ۱:۱ یا حتی TP<SL. با TP کوچک، معامله سریع در سود بسته می‌شود
     ⇒ WR بالا. ریسک: یک ضررِ بزرگ (SL بزرگ) می‌تواند چند بردِ کوچک را بخورد ⇒ net منفی.
     پس net>0 قیدِ هم‌زمان است.
  اهرمِ ۲ — فیلترهای تأییدِ چندگانه (بدونِ محدودیت در تعداد، طبقِ User Note):
     مومنتوم/رژیم (EMA20>EMA50)، RSI band، ADX، پنجرهٔ ساعتِ باریک‌تر، روزِ خاص،
     فیلترِ نوسان (ATR)، فیلترِ کندلِ صعودی. فقط بهترین setupها نگه داشته می‌شوند.

قانونِ مولتی‌تایم‌فریم: هر لایه روی هر TF مستقل تست می‌شود (XAU از M5 شروع — M1 برای
طلا موجود نیست). هر TF ممکن است TP/SL و فیلترِ متفاوتِ خود را بخواهد.

این ابزار قابلِ‌ری‌یوز است: تابعِ boost_layer(entry_signal_builder, ...) یک سازندهٔ
سیگنالِ ورودِ پایه می‌گیرد و کلِ فضای (TP/SL × فیلترها) را جاروب می‌کند و بهترین
پیکربندیِ گیت-پاسِ WR≥۶۰ را برمی‌گرداند.
================================================================================
"""
import os, sys, json, itertools
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK = 10000.0, 1.0
WR_FLOOR = 60.0
MIN_TRADES = 30  # کفِ اطمینانِ آماری (هم‌راستا با گیتِ پروژه n≥۳۰)

# مشخصاتِ واقعیِ حساب (single source of truth)
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)

# نسخه‌های per-TF طلا (همان مشخصات، فایلِ متفاوت) تا simulate_trades درست کار کند
for tf in ['M5', 'M30', 'H1', 'H4']:
    se.ASSETS[f'XAUUSD_{tf}'] = dict(file=f'data/XAUUSD_{tf}.csv', pip=0.10, contract=100.0,
                                     pip_value=10.0, spread_pip=3.3, comm=0.0, slip_pip=0.0)
for tf in ['M1', 'M5', 'M30']:
    se.ASSETS[f'EURUSD_{tf}'] = dict(file=f'data/EURUSD_{tf}.csv', pip=0.0001, contract=100_000.0,
                                     pip_value=10.0, spread_pip=1.0, comm=0.0, slip_pip=0.3)


def load(name):
    df = pd.read_csv(os.path.join(ROOT, 'data', name + '.csv'))
    df.columns = [c.lower() for c in df.columns]
    df['dt'] = pd.to_datetime(df['time'], unit='s')
    return df.reset_index(drop=True)


def add_calendar(df):
    dt = df['dt']
    df['hour'] = dt.dt.hour
    df['dow'] = dt.dt.dayofweek
    df['dom'] = dt.dt.day
    df['date'] = dt.dt.normalize()
    df['ym'] = dt.dt.year * 100 + dt.dt.month
    return df


def last_n_years(df, years=4):
    end = df['dt'].iloc[-1]
    start = end - pd.DateOffset(years=years)
    return df[df['dt'] >= start].reset_index(drop=True)


def add_indicators(df):
    """اندیکاتورهای پایه برای فیلترها (بدونِ look-ahead)."""
    c = df['close']
    df['ema20'] = ind.ema(c, 20)
    df['ema50'] = ind.ema(c, 50)
    df['ema100'] = ind.ema(c, 100)
    df['ema200'] = ind.ema(c, 200)
    df['rsi14'] = ind.rsi(c, 14)
    df['atr14'] = ind.atr(df, 14)
    adx_, pdi, mdi = ind.adx(df, 14)
    df['adx14'] = adx_
    df['pdi'] = pdi; df['mdi'] = mdi
    # کندلِ صعودی/نزولی
    df['bull'] = (c > df['open']).astype(int)
    return df


# ============================================================================
# آمارگیریِ استاندارد (per-trade net_usd) — همان تعریفِ audit
# ============================================================================
def eval_signal(df, long_sig, short_sig, sl, tp, mh, asset,
                be=None, trail=None):
    """اجرای کامل و برگرداندنِ dict آمار + per-trade net برای گیت‌های ضدِ overfit."""
    tr = se.simulate_trades(df, long_sig, short_sig, sl, tp, asset,
                            max_hold=mh, allow_overlap=False,
                            be_trigger_pip=be, trail_pip=trail)
    if tr is None or len(tr) == 0:
        return None
    tr = tr.copy(); tr['sl_pip'] = float(sl)
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP,
                                        risk_pct=RISK, compounding=True)
    if len(pt) == 0:
        return None
    net_usd = pt['net_usd'].values
    exit_bars = pt['exit_bar'].values
    wins = int((net_usd > 0).sum()); n = len(net_usd)
    return dict(net=float(st['net_profit']), n=n, wins=wins, losses=n - wins,
                wr=(wins / n * 100.0 if n else 0.0),
                pf=st['profit_factor'],
                net_usd=net_usd, exit_bars=exit_bars, trades=tr)


def antioverfit_gates(res, df):
    """گیتِ سختِ ضدِ overfit: هر دو نیمه مثبت + هر ۴ پنجرهٔ walk-forward مثبت.
    برمی‌گرداند (passed, detail)."""
    net_usd = res['net_usd']; exit_bars = res['exit_bars']
    n = len(net_usd)
    if n < MIN_TRADES:
        return False, f'n={n}<{MIN_TRADES}'
    # نیمه‌ها بر مبنای زمانِ خروج (اندیسِ کندل)
    order = np.argsort(exit_bars)
    nu = net_usd[order]
    half = n // 2
    h1 = nu[:half].sum(); h2 = nu[half:].sum()
    if h1 <= 0 or h2 <= 0:
        return False, f'half h1={h1:+.0f} h2={h2:+.0f}'
    # walk-forward ۴ پنجره
    q = n // 4
    wf = [nu[i*q:(i+1)*q].sum() if i < 3 else nu[3*q:].sum() for i in range(4)]
    if any(w <= 0 for w in wf):
        return False, f'wf={[round(w) for w in wf]}'
    return True, f'h1={h1:+.0f} h2={h2:+.0f} wf={[round(w) for w in wf]}'


# ============================================================================
# فیلترهای قابلِ‌ترکیب (هرکدام یک ماسکِ بولین می‌سازد)
# ============================================================================
def build_filters(df):
    """دیکشنریِ فیلترهای نامدار ⇒ ماسکِ بولین. طبقِ User Note: خطی و غیرخطی، معروف و کمیاب."""
    c = df['close'].values
    F = {}
    # --- رژیم/مومنتوم (خطی، معروف) ---
    F['ema20>50'] = (df['ema20'] > df['ema50']).values
    F['ema50>100'] = (df['ema50'] > df['ema100']).values
    F['ema20>50>100'] = ((df['ema20'] > df['ema50']) & (df['ema50'] > df['ema100'])).values
    F['price>ema200'] = (c > df['ema200'].values)
    # --- RSI band (غیرخطی) ---
    F['rsi<70'] = (df['rsi14'] < 70).values
    F['rsi40-70'] = ((df['rsi14'] >= 40) & (df['rsi14'] <= 70)).values
    F['rsi>50'] = (df['rsi14'] > 50).values
    # --- ADX (قدرتِ روند) ---
    F['adx>20'] = (df['adx14'] > 20).values
    F['adx>25'] = (df['adx14'] > 25).values
    F['pdi>mdi'] = (df['pdi'] > df['mdi']).values
    # --- کندلِ ورود صعودی ---
    F['bull_bar'] = (df['bull'] == 1).values
    # --- فیلترِ نوسان: ATR نه‌خیلی‌بزرگ (ضدِ climax) و نه‌خیلی‌کوچک ---
    atr = df['atr14'].values
    atr_med = np.nanmedian(atr)
    F['atr<1.8med'] = (atr < 1.8 * atr_med)
    F['atr>0.5med'] = (atr > 0.5 * atr_med)
    # همه را nan-safe کن
    for k in F:
        F[k] = np.nan_to_num(F[k], nan=False).astype(bool)
    return F


# ============================================================================
# boost_layer — موتورِ دو-مرحله‌ایِ ارتقای WR (بهینه از نظرِ سرعت)
#   مرحله A: فقط TP/SL grid روی سیگنالِ پایه (بدونِ فیلتر) ⇒ کدام (SL,TP) بیشترین
#            «امتیازِ ترکیبی» (WR بالا + net مثبت) را می‌دهد. ارزان: |SL|×|TP| فراخوانی.
#   مرحله B: با کاندیدهای برترِ TP/SL، ترکیبِ فیلترها (تا MAX_FILTERS) جستجو می‌شود تا
#            WR≥۶۰ با بیشینهٔ net و گیتِ سختِ ضدِ overfit پاس شود.
#   این ساختار فضای جستجو را از |F|×|SL|×|TP| به |SL|×|TP| + K×|F| کاهش می‌دهد.
# ============================================================================
def boost_layer(df, base_sig, asset, mh,
                sl_grid, tp_grid, filter_pool, max_filters=3,
                side='long', top_tpsl=4, be=None, trail=None, verbose=True):
    """
    ورودی:
      df         : دیتافریمِ آماده (با add_indicators/add_calendar).
      base_sig   : ماسکِ بولینِ سیگنالِ پایهٔ لایه (منطقِ ورودِ اصلی).
      asset      : کلیدِ ASSETS.
      mh         : max_hold.
      sl_grid/tp_grid : فهرستِ کاندیدهای SL/TP (pip).
      filter_pool: فهرستِ نامِ فیلترها (کلیدهای build_filters).
      side       : 'long' یا 'short'.
      top_tpsl   : چند کاندیدِ برترِ TP/SL از مرحله A وارد مرحله B شود.
    خروجی: dict(best=..., best_wr_any=..., base_stat=...)
    """
    n = len(df); zeros = np.zeros(n, bool)
    F = build_filters(df)

    def run(mask, sl, tp):
        if side == 'long':
            return eval_signal(df, mask, zeros, sl, tp, mh, asset, be=be, trail=trail)
        else:
            return eval_signal(df, zeros, mask, sl, tp, mh, asset, be=be, trail=trail)

    # آمارِ پایه (نسخهٔ رکورد، برای گزارش)
    # --- مرحله A: TP/SL grid روی base ---
    tpsl_results = []
    for sl in sl_grid:
        for tp in tp_grid:
            r = run(base_sig, sl, tp)
            if r is None or r['n'] < MIN_TRADES:
                continue
            # امتیازِ ترکیبی: اولویت با WR≥۶۰؛ در میانِ آن‌ها net بالاتر. اگر هیچ‌کدام
            # WR≥۶۰ نبود، آن‌هایی که به ۶۰ نزدیک‌ترند و net مثبت دارند بالا می‌آیند.
            score = (1 if r['wr'] >= WR_FLOOR else 0, r['wr'], r['net'])
            tpsl_results.append((score, sl, tp, r))
    if not tpsl_results:
        return dict(best=None, best_wr_any=None, note='مرحله A: هیچ TP/SL با n کافی')
    tpsl_results.sort(key=lambda x: x[0], reverse=True)
    top = tpsl_results[:top_tpsl]

    best_wr_any = None
    for _, sl, tp, r in tpsl_results:
        if best_wr_any is None or r['wr'] > best_wr_any['wr']:
            best_wr_any = dict(wr=r['wr'], net=r['net'], n=r['n'], sl=sl, tp=tp, f=[])

    # --- مرحله B: فیلترها روی کاندیدهای برترِ TP/SL ---
    filter_combos = [()]
    for k in range(1, max_filters + 1):
        filter_combos += list(itertools.combinations(filter_pool, k))

    best = None
    for _, sl, tp, _r in top:
        for fcombo in filter_combos:
            mask = base_sig.copy()
            for fname in fcombo:
                mask = mask & F[fname]
            if int(mask.sum()) < MIN_TRADES:
                continue
            r = run(mask, sl, tp)
            if r is None or r['n'] < MIN_TRADES:
                continue
            if r['wr'] > best_wr_any['wr']:
                best_wr_any = dict(wr=r['wr'], net=r['net'], n=r['n'], sl=sl, tp=tp,
                                   f=list(fcombo))
            if r['wr'] >= WR_FLOOR and r['net'] > 0:
                passed, detail = antioverfit_gates(r, df)
                if passed:
                    cand = dict(wr=r['wr'], net=r['net'], n=r['n'], pf=r['pf'],
                                sl=sl, tp=tp, mh=mh, side=side, f=list(fcombo),
                                detail=detail)
                    if best is None or cand['net'] > best['net']:
                        best = cand
    return dict(best=best, best_wr_any=best_wr_any)


if __name__ == '__main__':
    print("s220_wr60_booster.py — ماژولِ کمکی. از boost_layer در اسکریپت‌های لایه استفاده کنید.")
