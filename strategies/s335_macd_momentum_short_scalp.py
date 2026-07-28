# -*- coding: utf-8 -*-
"""
s335_macd_momentum_short_scalp.py
================================================================================
احیای «موتورِ اسکالپِ D3_MACD» (منشأ: s127/s128) به‌صورتِ یک لایهٔ **momentum SHORT**
روی تایم‌فریم‌های پایین — تحتِ معیارِ رسمیِ RQS+ (۶ گیتِ veto).

> پاسخ به User Note این نشست:
>   «تمرکز روی یک استراتژیِ اسکالپ. خیلی از نوسان‌های ریزِ روزانه را از دست می‌دهیم.
>    لانگ/شورت فرقی ندارد، ولی پروژه به SHORT بیشتر نیازمند است.»

--------------------------------------------------------------------------------
چرا این لایه؟ (تفکرِ خطی + انتخاب از کلِ تاریخچه — رفعِ اشتباه #۸)
--------------------------------------------------------------------------------
در فایلِ `ScalpV2_MACD_Engine_NetProfit_101259.md` (منشأ s127/s128) اثبات شد که
آشکارسازِ **D3_MACD** (تقاطعِ MACD 12/26/9) روی M5ِ طلا z≈+۴ تا +۶ برای *کشفِ روند*
دارد — یعنی یک آشکارسازِ momentum/trend-following واقعی (نه کور). اما آن موتور:
  ۱) فقط **LONG** بود (تقاطعِ صعودی + گیتِ EMA20>EMA100).
  ۲) تحتِ رژیمِ قدیمیِ «سودِ خالص» ساخته شد و **هرگز با RQS+ سنجیده نشد**.

همهٔ لایه‌های SHORTِ اسکالپِ زندهٔ فعلی روی M5 (**S328 RSI-fade, S334 z-fade, S330 ORB-fade**)
از خانوادهٔ **mean-reversion/fade** (ضدِ روند) هستند. هیچ لایهٔ **momentum/trend-following
SHORT** روی TF پایین وجود ندارد. پس نسخهٔ SHORTِ D3_MACD:
  • یک مکانیزمِ کاملاً متفاوت (شتابِ نزولی، نه بازگشت از اشباع) ⇒ همپوشانیِ کمِ ساختاری.
  • دقیقاً «نوسان‌های ریزِ روزانه» را در جهتِ نزول شکار می‌کند.
  • یک احیای واقعیِ یک موتورِ اثبات‌شده اما هرگز-RQS-نشده است.

منطقِ SHORT (آینهٔ LONG):
  ماشه   : تقاطعِ **نزولیِ** MACD  (ml از sl پایین می‌زند)
  گیتِ روند: EMA20 < EMA100  (روندِ نزولیِ زمینه)
  فیلترِ رژیم (بهبود): کیفیتِ روند بالا باشد (r2/hurst/chop) — یک روندِ نزولیِ *تمیز*،
             نه یک بازارِ رنج که تقاطع‌های MACD در آن نویز است.

--------------------------------------------------------------------------------
اجرا:
  python strategies/s335_macd_momentum_short_scalp.py --asset XAUUSD --tf M5 --stage baseline
  python strategies/s335_macd_momentum_short_scalp.py --asset XAUUSD --tf M5 --stage scan
  python strategies/s335_macd_momentum_short_scalp.py --stage mtf     # همهٔ TF/جفت‌ارز
================================================================================
"""
import os, sys, json, argparse, itertools
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib

RESULTS = os.path.join(ROOT, 'results')


# ==============================================================================
# اندیکاتورهای پایه (verbatim با s128 برای برابری — EMA/MACD)
# ==============================================================================
def _ema(x, p):
    a = 2.0 / (p + 1.0)
    out = np.empty_like(x, dtype=np.float64)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def base_indicators(df):
    c = df['close'].values.astype(np.float64)
    e20 = _ema(c, 20)
    e100 = _ema(c, 100)
    macd_line = _ema(c, 12) - _ema(c, 26)
    macd_sig = _ema(macd_line, 9)
    return c, e20, e100, macd_line, macd_sig


# ==============================================================================
# ماشهٔ SHORTِ momentum: تقاطعِ نزولیِ MACD + گیتِ روندِ نزولی
#   forward-safe: سیگنال روی close کندلِ i؛ ورود در open کندلِ i+1 (داخلِ simulate_trades)
# ==============================================================================
def short_signal(df, trend_gate=True, warmup=102):
    c, e20, e100, ml, sl = base_indicators(df)
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    for i in range(warmup, n - 1):
        cross_dn = (ml[i] < sl[i]) and (ml[i - 1] >= sl[i - 1])
        if not cross_dn:
            continue
        if trend_gate and not (e20[i] < e100[i]):
            continue
        sig[i] = True
    return sig


def long_signal(df, trend_gate=True, warmup=102):
    """برای مقایسهٔ کنترلی (تز می‌گوید پروژه به SHORT نیاز دارد)."""
    c, e20, e100, ml, sl = base_indicators(df)
    n = len(df)
    sig = np.zeros(n, dtype=bool)
    for i in range(warmup, n - 1):
        cross_up = (ml[i] > sl[i]) and (ml[i - 1] <= sl[i - 1])
        if not cross_up:
            continue
        if trend_gate and not (e20[i] > e100[i]):
            continue
        sig[i] = True
    return sig


# ==============================================================================
# فیلترهای رژیم (بهبود) — از بانکِ ۴۰۱‌تایی، همه shift-safe (بدونِ look-ahead)
#   برای momentum می‌خواهیم روندِ «تمیز»: r2 بالا، chop پایین، hurst بالا.
# ==============================================================================
def regime_masks(df):
    """چند ماسکِ رژیم را یکجا محاسبه می‌کند (بولین هم‌طولِ df). همه با shift(1)."""
    out = {}
    def s(name, period=None):
        if period is None:
            return ib.compute(name, df)
        return ib.compute(name, df, period=period)
    # کیفیتِ روند
    out['r2'] = s('r2')                    # R² رگرسیون (۰..۱) — بالاتر=روندِ تمیزتر
    out['hurst'] = s('hurst')              # >0.5 persistent/trending
    out['chop'] = s('chop')                # choppiness (۰..۱۰۰) — پایین=روندی
    out['fdi'] = s('fdi')                  # fractal dimension — پایین=روندی
    out['kurt'] = s('kurt')                # dm safety-gate
    out['entropy'] = s('entropy')          # بی‌نظمی — پایین=ساختارمندتر
    # همه را shift(1) می‌کنیم تا مقدارِ کندلِ i فقط از داده تا i-1 بیاید (safe)
    for k in list(out.keys()):
        out[k] = out[k].shift(1)
    return out


def load_tf(asset, tf):
    path = f'data/{asset}_{tf}.csv'
    if not os.path.exists(os.path.join(ROOT, path)):
        return None
    return se.load_data(path)


# ==============================================================================
# ابزارِ اجرا: از سیگنال+فیلتر یک RQS+ می‌سازد
# ==============================================================================
def run_config(df, asset, sl_pip, tp_pip, direction='short',
               trend_gate=True, filters=None, max_hold=48):
    """
    filters: لیستی از (mask_series_bool) که باید هم‌زمان True باشند.
    خروجی: (rqs_result, n_signals)
    """
    if direction == 'short':
        sig = short_signal(df, trend_gate=trend_gate)
    else:
        sig = long_signal(df, trend_gate=trend_gate)

    if filters:
        combined = np.ones(len(df), dtype=bool)
        for m in filters:
            mv = np.asarray(m.fillna(False).values, dtype=bool) if isinstance(m, pd.Series) else np.asarray(m, bool)
            combined &= mv
        sig = sig & combined

    n_sig = int(sig.sum())
    if direction == 'short':
        long_sig = np.zeros(len(df), dtype=bool); short_sig = sig
    else:
        long_sig = sig; short_sig = np.zeros(len(df), dtype=bool)

    trades = se.simulate_trades(df, long_sig, short_sig, sl_pip=sl_pip, tp_pip=tp_pip,
                                asset=asset, max_hold=max_hold, allow_overlap=False)
    # افزودنِ ستونِ tp_pip برای RQS (WR_breakeven)
    if trades is not None and len(trades):
        trades = trades.copy()
        trades['tp_pip'] = float(tp_pip)
    r = rqs.compute_rqs(trades, asset, sl_pip=sl_pip, tp_pip=tp_pip)
    return r, n_sig, trades


# ==============================================================================
# مرحله‌ها
# ==============================================================================
def stage_baseline(asset, tf):
    df = load_tf(asset, tf)
    if df is None:
        print(f"داده {asset}_{tf} موجود نیست"); return
    print(f"=== BASELINE {asset}/{tf} — D3_MACD SHORT (اعدادِ رندِ کنترلی) ===")
    print(f"کندل‌ها: {len(df)}")
    # اعدادِ رندِ کنترلی — انتظار می‌رود سوخته باشد (baseline)
    for sl, tp in [(60, 100), (80, 120), (100, 150)]:
        r, n, _ = run_config(df, asset, sl, tp, 'short', trend_gate=True)
        print(rqs.format_report(f'S335_{asset}_{tf}_SL{sl}TP{tp}', r), f'| nsig={n}')
    # مقایسهٔ کنترلی LONG (تز: SHORT نیازِ پروژه است)
    rL, nL, _ = run_config(df, asset, 80, 120, 'long', trend_gate=True)
    print(rqs.format_report(f'S335_{asset}_{tf}_LONG_ctrl', rL), f'| nsig={nL}')


def stage_scan(asset, tf):
    """
    مرحلهٔ احیا: افزودنِ فیلترهای رژیم + اسکنِ TP/SL غیررند.
    تز: تقاطعِ نزولیِ MACD فقط در روندِ نزولیِ *تمیز* کیفیت دارد.
    """
    df = load_tf(asset, tf)
    if df is None:
        print(f"داده {asset}_{tf} موجود نیست"); return
    print(f"=== SCAN {asset}/{tf} — D3_MACD SHORT + فیلترهای رژیم ===")
    print(f"کندل‌ها: {len(df)}")
    m = regime_masks(df)

    # آستانه‌های رژیم (کاندیدا) — تفسیر: روندِ نزولیِ تمیز
    r2_thr    = [0.30, 0.45, 0.60]
    chop_thr  = [61.8, 50.0, 38.2]     # زیرِ این = روندی (فیبوناچی)
    hurst_thr = [0.50, 0.55]
    # TP/SL غیررند (اسکالپ M5 طلا؛ مضربِ ATR). واحد pip طلا=0.1$
    sltp_grid = [(34, 55), (55, 89), (89, 144), (55, 55), (89, 110), (144, 178)]

    best = None
    rows = []
    for r2t, cht, hut in itertools.product(r2_thr, chop_thr, hurst_thr):
        filt = [m['r2'] > r2t, m['chop'] < cht, m['hurst'] > hut]
        for sl, tp in sltp_grid:
            r, nsig, _ = run_config(df, asset, sl, tp, 'short', trend_gate=True,
                                    filters=filt, max_hold=48)
            met = r['metrics']
            npass = sum(r['gates'].values())
            rows.append((r['rqs_score'], npass, r2t, cht, hut, sl, tp, met.get('n_trades', 0),
                         met.get('win_rate', 0), met.get('profit_factor', 0)))
            if best is None or (r['rqs_score'] > best[0]):
                best = (r['rqs_score'], r, r2t, cht, hut, sl, tp, nsig)
    # چاپِ ۱۲ نتیجهٔ برتر
    rows.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f"\n{'RQS':>5} {'gts':>3} {'r2>':>5} {'chop<':>6} {'H>':>5} {'SL':>4} {'TP':>4} "
          f"{'n':>4} {'WR':>5} {'PF':>5}")
    for row in rows[:14]:
        print(f"{row[0]:>5.1f} {row[1]:>3d} {row[2]:>5.2f} {row[3]:>6.1f} {row[4]:>5.2f} "
              f"{row[5]:>4d} {row[6]:>4d} {row[7]:>4d} {row[8]:>5.1f} {row[9]:>5.2f}")
    if best:
        print("\n--- بهترین ---")
        print(rqs.format_report(f'S335_{asset}_{tf}_BEST', best[1]),
              f"| r2>{best[2]} chop<{best[3]} H>{best[4]} SL{best[5]}/TP{best[6]} nsig={best[7]}")


def stage_refine(asset, tf):
    """
    ریزتنظیم روی ناحیهٔ امیدوارکننده (chop تمیز) + فیلترهای مکملِ بانک برای عبور از
    G0(WR≥60) و G4(پایداری). قانونِ «همه‌چیز شناور» + «همکاریِ بهبودها».
    """
    df = load_tf(asset, tf)
    if df is None:
        print(f"داده {asset}_{tf} موجود نیست"); return
    print(f"=== REFINE {asset}/{tf} — عبور از G0/G4 ===")
    m = regime_masks(df)

    # ریزِ آستانه‌ها حولِ نقطهٔ برنده (غیررند)
    r2_thr    = [0.40, 0.48, 0.55]
    chop_thr  = [42.0, 38.2, 34.0, 30.0]
    hurst_thr = [0.50, 0.53]
    # فیلترهای مکمل (کاندیدا) — هرکدام None یعنی بدونِ آن فیلتر
    kurt_thr    = [None, 2.5, 1.5, 0.5]      # کنترلِ ریسکِ دُم (G4)
    entropy_thr = [None, 2.7, 2.4]           # زیرِ این = ساختارمندتر
    sltp_grid = [(55, 89), (89, 144), (110, 178), (89, 110), (144, 200), (72, 110)]

    best = None; rows = []
    for r2t, cht, hut, kt, et in itertools.product(r2_thr, chop_thr, hurst_thr, kurt_thr, entropy_thr):
        filt = [m['r2'] > r2t, m['chop'] < cht, m['hurst'] > hut]
        if kt is not None:
            filt.append(m['kurt'] < kt)
        if et is not None:
            filt.append(m['entropy'] < et)
        for sl, tp in sltp_grid:
            r, nsig, _ = run_config(df, asset, sl, tp, 'short', trend_gate=True,
                                    filters=filt, max_hold=48)
            met = r['metrics']; npass = sum(r['gates'].values())
            rows.append((r['rqs_score'], npass, r, dict(r2=r2t, chop=cht, hu=hut, kt=kt, et=et, sl=sl, tp=tp, nsig=nsig)))
            if best is None or (npass, r['rqs_score']) > (best[1], best[0]):
                best = (r['rqs_score'], npass, r, dict(r2=r2t, chop=cht, hu=hut, kt=kt, et=et, sl=sl, tp=tp, nsig=nsig))
    rows.sort(key=lambda x: (x[1], x[0]), reverse=True)
    print(f"\n{'RQS':>5} {'gts':>3}  cfg")
    for rr in rows[:16]:
        c = rr[3]; met = rr[2]['metrics']; g = rr[2]['gates']
        gl = ''.join('1' if v else '0' for v in g.values())
        print(f"{rr[0]:>5.1f} {rr[1]:>3d}  r2>{c['r2']} chop<{c['chop']} H>{c['hu']} kurt<{c['kt']} ent<{c['et']} "
              f"SL{c['sl']}/TP{c['tp']} | n={met.get('n_trades',0)} WR={met.get('win_rate',0)} PF={met.get('profit_factor',0)} G={gl}")
    if best:
        print("\n--- بهترین ---")
        c = best[3]
        print(rqs.format_report(f'S335_{asset}_{tf}_REFINE', best[2]),
              f"| r2>{c['r2']} chop<{c['chop']} H>{c['hu']} kurt<{c['kt']} ent<{c['et']} SL{c['sl']}/TP{c['tp']} nsig={c['nsig']}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--asset', default='XAUUSD')
    ap.add_argument('--tf', default='M5')
    ap.add_argument('--stage', default='baseline')
    a = ap.parse_args()
    if a.stage == 'baseline':
        stage_baseline(a.asset, a.tf)
    elif a.stage == 'scan':
        stage_scan(a.asset, a.tf)
    elif a.stage == 'refine':
        stage_refine(a.asset, a.tf)
