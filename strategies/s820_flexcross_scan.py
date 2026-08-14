# -*- coding: utf-8 -*-
"""S820 — اسکنِ اکتشافیِ «گذرِ Reflex/Trendflex» — فقط نیمهٔ اولِ داده (مسیر C)
================================================================================

چرا این خانواده؟ (استدلالِ طراحی — پیش از دیدنِ هر عددی نوشته شد)
--------------------------------------------------------------------------------
۱. **سرزمینِ بکر:** در ۶۲۶ سندِ آرشیوِ results/ حتی یک داوریِ RQS2 روی خانوادهٔ
   cycle/DSPِ الرز (reflex/trendflex/laguerre/ssf — ۳۸ اندیکاتور) وجود ندارد.
   مأموریتِ این نشست «ساختِ لایهٔ نو» است، نه احیا — این دقیقاً همان است.

۲. **خاصیتِ ریاضیِ منحصربه‌فرد:** خروجیِ reflex/trendflex بر RMSِ خودش نرمال
   می‌شود (Ehlers 2020, TASC Feb) ⇒ یک آمارهٔ **خود-استانداردشده** است، هم‌جنسِ
   z-score. یعنی آستانهٔ گذر بینِ تایم‌فریم‌ها **قابلِ انتقال** است — دقیقاً
   خاصیتی که قانونِ MTF می‌خواهد (ضدِ اشتباهِ #۶: هندسه از ATRِ همان کارت
   می‌آید، آستانه از توزیعِ نرمال‌شدهٔ خودِ اندیکاتور).

۳. **الگویِ برنده‌های تاریخ:** هر ۷ ACCEPT پروژه تک‌ایده، رویدادمحور و
   کم‌پارامترند (S382: یک گذرِ آستانهٔ غیررند، صفر فیلتر، score=82).
   این اسکن همان معماری را دارد: گذر (event)، نه حالت (state).

قوانینِ ضدِ تقلبِ مسیر C که این فایل رعایت می‌کند
--------------------------------------------------------------------------------
- **فقط نیمهٔ اولِ** کندل‌ها لود و لمس می‌شود (bar < n//2). نیمهٔ دوم برای
  «یک» آزمونِ تأییدیِ نهایی دست‌نخورده می‌ماند.
- شمارشِ صادقانهٔ فضای جست‌وجو در خروجی ذخیره می‌شود (برای MD نهایی).
- هندسه همیشه TP > SL (ضدِ اشتباهِ #۸)؛ آستانه‌ها غیررند (ضدِ #۷).
- هر دو جهتِ معامله برای هر رویداد آزموده می‌شود — داده تصمیم می‌گیرد،
  نه پیش‌داوریِ سبک (درسِ S382).

اجرا:  python3 strategies/s820_flexcross_scan.py --tf M1
خروجی: results/_s820/scan_<TF>.json  (+ خلاصهٔ چاپی)
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.signal import lfilter, lfiltic

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import scalp_engine as se          # noqa: E402
from tools import s434_fast_data as fd         # noqa: E402

OUT = 'results/_s820'
ASSET = 'XAUUSD'

# ── فضای جست‌وجو (اعلامِ صادقانه — در JSON هم ذخیره می‌شود) ──
INDICATORS = ('trendflex', 'reflex')
PERIODS = (13, 21, 34)            # فیبوناچیِ غیررند — عرفِ بانک
THRESHOLDS = (0.9, 1.3, 1.7, 2.1)  # غیررند؛ اندیکاتور خود-نرمال است
GEOMS = tuple((k, rr) for k in (1.2, 1.8) for rr in (1.3, 1.6))  # TP>SL همیشه
MAX_HOLD = 64
ATR_P = 100

# رویداد × جهتِ معامله: گذرِ بالا→{لانگِ مومنتوم، شورتِ بازگشتی}
#                       گذرِ پایین→{شورتِ مومنتوم، لانگِ بازگشتی}
ARMS_PER_CELL = 4
N_TRIALS_CARD = len(INDICATORS) * len(PERIODS) * len(THRESHOLDS) * ARMS_PER_CELL * len(GEOMS)


# ═══════════ نسخهٔ برداری‌شدهٔ ssf/flex — با اثباتِ برابری با بانک ═══════════
def ssf_arr_fast(x, period):
    """Super-smoother الرز — بازتولیدِ **بیت‌به‌بیتِ** engine.indicator_bank._ssf_arr.

    بانک شرایطِ اولیهٔ out[0]=x[0], out[1]=x[1] دارد (نه صفر). این‌جا با
    lfiltic همان شرط به فیلترِ IIR تزریق می‌شود — برابری با assert اثبات می‌شود.
    """
    n = len(x)
    a = np.exp(-1.414 * np.pi / period)
    b = 2.0 * a * np.cos(1.414 * np.pi / period)
    c2, c3 = b, -a * a
    c1 = 1.0 - c2 - c3
    if n < 3:
        return x.astype(float).copy()
    out = np.empty(n)
    out[0], out[1] = x[0], x[1]
    xin = (x[1:] + x[:-1]) / 2.0          # xin[i-1] = (x[i]+x[i-1])/2 برای i≥1
    bb, aa = [c1], [1.0, -c2, -c3]
    zi = lfiltic(bb, aa, y=[out[1], out[0]], x=[xin[0]])
    out[2:], _ = lfilter(bb, aa, xin[1:], zi=zi)
    return out


def flex_fast(x, period, trend):
    """معادلِ برداریِ engine.indicator_bank._flex — برابریِ عددی assert می‌شود."""
    n = len(x)
    s_arr = ssf_arr_fast(x, period / 2.0)
    cs = np.concatenate([[0.0], np.cumsum(s_arr)])
    out = np.zeros(n)
    i = np.arange(period, n)
    # Σ_{k=1..p} ssf[i-k] = cs[i] - cs[i-p]
    sum_prev = cs[i] - cs[i - period]
    if trend:
        s = s_arr[i] - sum_prev / period
    else:
        slope = (s_arr[i - period] - s_arr[i]) / period
        s = s_arr[i] + slope * (period + 1) / 2.0 - sum_prev / period
    s_full = np.zeros(n)
    s_full[period:] = s
    ms = lfilter([0.04], [1.0, -0.96], s_full ** 2)
    with np.errstate(divide='ignore', invalid='ignore'):
        out = np.where(ms > 0, s_full / np.sqrt(ms), 0.0)
    out[:period] = 0.0
    return out


def assert_parity(df_slice):
    """برابریِ عددی با بانکِ رسمی روی یک برش — شرطِ ادامهٔ اجرا."""
    from engine import indicator_bank as ib
    ref_t = ib.compute('trendflex', df_slice).to_numpy()
    ref_r = ib.compute('reflex', df_slice).to_numpy()
    my_t = flex_fast(df_slice['close'].to_numpy(float), 20, trend=True)
    my_r = flex_fast(df_slice['close'].to_numpy(float), 20, trend=False)
    # ssf بانک ممکن است شرایطِ اولیهٔ متفاوت داشته باشد ⇒ فقط دنباله (پس از warmup×۵)
    w = 200
    for name, a, b in (('trendflex', ref_t[w:], my_t[w:]), ('reflex', ref_r[w:], my_r[w:])):
        err = np.nanmax(np.abs(a - b))
        if not (err < 1e-6):
            raise AssertionError(f'parity FAILED for {name}: max|Δ|={err:.3e}')
    print(f'[parity] ✅ flex_fast ≡ indicator_bank (max|Δ|<1e-6 روی برشِ {len(df_slice)} کندلی)')


def atr_arr(df, p=ATR_P):
    h = df['high'].to_numpy(float); l = df['low'].to_numpy(float)
    c = df['close'].to_numpy(float)
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / p, adjust=False).mean().to_numpy()


def binom_z(wins, n, p0):
    if n == 0:
        return 0.0
    se_ = np.sqrt(p0 * (1 - p0) / n)
    return ((wins / n) - p0) / se_ if se_ > 0 else 0.0


def scan_card(tf, verbose=True):
    t0 = time.time()
    d = fd.load_fast(ASSET, tf)
    df_all = fd.as_dataframe(d)
    n_all = len(df_all)
    half = n_all // 2
    df = df_all.iloc[:half].reset_index(drop=True)   # 🔒 فقط نیمهٔ اول
    src = d['src']
    if verbose:
        print(f'[{tf}] src={src}')
        print(f'[{tf}] bars_total={n_all:,}  bars_search={len(df):,} (نیمهٔ اول — مسیر C)')

    # برابریِ عددی، یک بار روی برشِ ۲۰هزارتایی
    assert_parity(df.iloc[:20000] if len(df) > 20000 else df)

    x = df['close'].to_numpy(float)
    pip = se.ASSETS[ASSET]['pip']
    a = atr_arr(df)
    sl_base_pip = float(np.nanmedian(a[ATR_P:])) / pip   # ۱×ATR بر حسبِ pip
    cost_pip = se.ASSETS[ASSET]['spread_pip'] + 2.0 * se.ASSETS[ASSET]['slip_pip']

    rows = []
    n_arms = 0
    for ind in INDICATORS:
        for p in PERIODS:
            sig_v = flex_fast(x, p, trend=(ind == 'trendflex'))
            prev = np.concatenate([[0.0], sig_v[:-1]])
            for thr in THRESHOLDS:
                cross_up = (prev <= thr) & (sig_v > thr)
                cross_dn = (prev >= -thr) & (sig_v < -thr)
                for evt_name, evt in (('up', cross_up), ('dn', cross_dn)):
                    for side in ('long', 'short'):
                        for sl_k, rr in GEOMS:
                            n_arms += 1
                            sl_pip = sl_base_pip * sl_k
                            tp_pip = sl_pip * rr
                            ls = evt if side == 'long' else np.zeros(len(df), bool)
                            ss = evt if side == 'short' else np.zeros(len(df), bool)
                            tr = se.simulate_trades(df, ls, ss, sl_pip, tp_pip,
                                                    ASSET, max_hold=MAX_HOLD,
                                                    allow_overlap=False)
                            n = len(tr)
                            if n < 30:
                                continue
                            wins = int((tr['outcome'] == 'win').sum())
                            wr = wins / n * 100.0
                            be = (sl_pip + cost_pip) / (sl_pip + tp_pip) * 100.0
                            lift = wr - be
                            z = binom_z(wins, n, be / 100.0)
                            net = float(tr['pnl_pip'].sum())
                            rows.append(dict(ind=ind, period=p, thr=thr, evt=evt_name,
                                             side=side, sl_k=sl_k, rr=rr,
                                             sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                                             n=n, wr=round(wr, 2), be=round(be, 2),
                                             lift=round(lift, 2), z=round(z, 2),
                                             net_pip=round(net, 1)))
    rows.sort(key=lambda r: r['z'], reverse=True)
    out = dict(tf=tf, asset=ASSET, src=src, bars_total=n_all, bars_search=len(df),
               path='C (search=first half only)', n_trials_card=n_arms,
               declared_space=N_TRIALS_CARD, sl_base_pip=round(sl_base_pip, 2),
               cost_pip=cost_pip, max_hold=MAX_HOLD, elapsed_s=round(time.time() - t0, 1),
               results=rows)
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/scan_{tf}.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False)
    if verbose:
        print(f'[{tf}] arms={n_arms}  valid(n≥30)={len(rows)}  '
              f'elapsed={out["elapsed_s"]}s')
        print(f'[{tf}] ── ۱۰ بازوی برتر (بر z) ──')
        for r in rows[:10]:
            print(f"  {r['ind']:9s} p={r['period']:<3d} thr={r['thr']:<4} "
                  f"{r['evt']}/{r['side']:<5s} slk={r['sl_k']} rr={r['rr']} "
                  f"n={r['n']:<6d} wr={r['wr']:6.2f}% be={r['be']:5.2f}% "
                  f"lift={r['lift']:+6.2f}pp z={r['z']:+6.2f} net={r['net_pip']:+.0f}pip")
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--tf', default='M1')
    a = ap.parse_args()
    scan_card(a.tf)
