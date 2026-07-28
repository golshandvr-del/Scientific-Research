# -*- coding: utf-8 -*-
"""
S335 — اسکنِ مولتی‌تایم‌فریم (قانونِ #۱ پروژه) + دو نوع تریگرِ اِهلرز
================================================================================
دو تریگرِ چرخهٔ کاندیدا (هر دو forward-safe):
  A) dip_turn : reflex از کف (<= -rf_dip) رو به بالا برمی‌گردد   (پول‌بکِ عمیق)
  B) zero_up  : reflex از زیرِ صفر به بالای صفر عبور می‌کند       (تریگرِ چرخهٔ استاندارد اِهلرز)

گیت‌های مشترک (رژیم/کیفیت):
  trendflex(pTf) > tf_min  &  hurst(pHu) > hu_min  &  r2(pR2) > r2_min  &  chop(pC) < chop_max

روی هر (asset × TF) بهترین ترکیب اسکن و RQS+ گزارش می‌شود. SL/TP per-TF غیررند و مقیاس‌شده
با نوسانِ TF (M5 کوچک، H4 بزرگ) — رفعِ اشتباه #۶/#۷.

اجرا:
  python3 strategies/s335_mtf.py XAUUSD M5
  python3 strategies/s335_mtf.py XAUUSD M15
  ... (asset ∈ {XAUUSD,EURUSD}, TF ∈ {M5,M15,M30,H1,H4})
"""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from engine import scalp_engine as se
from engine import rqs
from engine import indicator_bank as ib


# پارامترهای اندیکاتورِ ثابت (غیررندِ فیبوناچی/لوکاس)
IND = dict(p_rf=21, p_tf=34, p_hu=55, p_r2=21, p_chop=21)

# SL/TP غیررندِ per-TF (مقیاسِ نوسانِ هر TF؛ TP≥SL برای پرهیز از اشتباه #۹)
#   (لیستِ کاندیدا؛ اسکن بهترین را برای هر TF برمی‌گزیند)
SLTP_BY_TF = {
    'M5':  [(150, 225, 55), (170, 255, 60), (135, 240, 72)],
    'M15': [(230, 345, 48), (260, 390, 56), (200, 340, 64)],
    'M30': [(320, 480, 40), (360, 540, 48), (280, 476, 56)],
    'H1':  [(430, 645, 32), (480, 720, 40), (390, 663, 48)],
    'H4':  [(720, 1080, 24), (820, 1230, 28), (650, 1105, 32)],
}
# برای EURUSD (pip=0.0001) SL/TP بر حسبِ pip کوچک‌تر است
SLTP_BY_TF_EUR = {
    'M5':  [(18, 27, 55), (22, 33, 60), (16, 32, 72)],
    'M15': [(30, 45, 48), (36, 54, 56), (26, 44, 64)],
    'M30': [(42, 63, 40), (50, 75, 48), (38, 65, 56)],
    'H1':  [(60, 90, 32), (70, 105, 40), (54, 92, 48)],
    'H4':  [(95, 143, 24), (110, 165, 28), (85, 145, 32)],
}


def precompute(df):
    return {
        'reflex': ib.reflex(df, period=IND['p_rf']).values.astype(float),
        'tflex':  ib.trendflex(df, period=IND['p_tf']).values.astype(float),
        'hurst':  ib.hurst(df, p=IND['p_hu']).values.astype(float),
        'r2':     ib.r2(df, p=IND['p_r2']).values.astype(float),
        'chop':   ib.chop(df, p=IND['p_chop']).values.astype(float),
    }


def build_signal(S, trigger, rf_dip, tf_min, hu_min, r2_min, chop_max):
    """نسخهٔ برداری‌شدهٔ numpy — بیت‌به‌بیت هم‌ارزِ حلقهٔ اصلی (بدون look-ahead).
    تصمیمِ کندلِ i از دادهٔ تا i؛ ورود در i+1 توسطِ simulate_trades.
    reflex[i-1] برای i=0 نامعتبر است ⇒ اندیس‌های 0 و 1 هرگز سیگنال نمی‌دهند
    (منطبق با حلقهٔ اصلی که از i=2 شروع می‌شد)."""
    reflex, tflex, hurst, r2, chop = S['reflex'], S['tflex'], S['hurst'], S['r2'], S['chop']
    n = len(reflex)
    # گیت‌های رژیم/کیفیت (finite-safe: NaN>x → False به‌طورِ خودکار)
    gate = np.isfinite(tflex) & (tflex > tf_min)
    gate &= np.isfinite(hurst) & (hurst > hu_min)
    if r2_min is not None:
        gate &= np.isfinite(r2) & (r2 > r2_min)
    if chop_max is not None:
        gate &= np.isfinite(chop) & (chop < chop_max)
    # reflex شیفت‌یافته (reflex[i-1])
    rprev = np.empty(n, dtype=float); rprev[0] = np.nan; rprev[1:] = reflex[:-1]
    finite_r = np.isfinite(reflex) & np.isfinite(rprev)
    if trigger == 'dip_turn':
        trig = (rprev <= -rf_dip) & (reflex > rprev)
    elif trigger == 'zero_up':
        trig = (rprev <= 0.0) & (reflex > 0.0)
    else:
        trig = np.zeros(n, dtype=bool)
    sig = gate & finite_r & trig
    # اندیس‌های 0,1 را صفر کن (منطبق با range(2,n) در نسخهٔ حلقه)
    sig[0] = False
    if n > 1:
        sig[1] = False
    return sig


def scan(asset, tf):
    fpath = f'data/{asset}_{tf}.csv'
    if not os.path.exists(fpath):
        print(f"[skip] {fpath} not found"); return
    df = se.load_data(fpath)
    S = precompute(df)
    sltp = (SLTP_BY_TF_EUR if asset == 'EURUSD' else SLTP_BY_TF)[tf]

    grid_trig   = ['dip_turn', 'zero_up']
    grid_rf_dip = [0.6, 0.8, 1.0]
    grid_tf_min = [0.2, 0.5]
    grid_hu_min = [0.50, 0.53]
    grid_r2_min = [None, 0.50, 0.55]
    grid_chop   = [None, 38.2]

    results = []
    combos = list(itertools.product(grid_trig, grid_rf_dip, grid_tf_min, grid_hu_min,
                                    grid_r2_min, grid_chop, sltp))
    for (trig, rf_dip, tf_min, hu_min, r2_min, chop_max, (sl, tp, hold)) in combos:
        sig = build_signal(S, trig, rf_dip, tf_min, hu_min, r2_min, chop_max)
        if sig.sum() < 30:
            continue
        short = np.zeros(len(df), dtype=bool)
        trades = se.simulate_trades(df, sig, short, sl_pip=sl, tp_pip=tp,
                                    asset=asset, max_hold=hold, allow_overlap=False)
        r = rqs.compute_rqs(trades, asset, sl_pip=sl, tp_pip=tp)
        m = r['metrics']; g = r['gates']; npass = sum(g.values())
        results.append((r['rqs_score'], npass, r['verdict'], m['n_trades'], m['win_rate'],
                        m['profit_factor'], m['max_dd_pct'], m['max_consec_losses'], m['p_value'],
                        trig, rf_dip, tf_min, hu_min, r2_min, chop_max, sl, tp, hold))

    accepts = [r for r in results if r[1] == 6]
    accepts.sort(key=lambda x: (x[3], x[0]), reverse=True)  # n سپس RQS (استحکام)
    print(f"\n===== {asset} {tf} — {len(accepts)} ACCEPT / {len(results)} tested =====")
    print("RQS  gP  n    WR    PF    DD   MCL  p     | trig     rf  tf  hu   r2   chop  sl   tp   hold")
    show = accepts[:12] if accepts else sorted([r for r in results if r[1] == 5],
                                               key=lambda x: x[0], reverse=True)[:8]
    for row in show:
        (rqsv, npass, verd, n, wr, pf, dd, mcl, pv,
         trig, rf_dip, tf_min, hu_min, r2_min, chop_max, sl, tp, hold) = row
        print(f"{rqsv:4.1f} {npass}/6 {n:4d} {wr:4.1f} {pf:5.2f} {dd:4.1f} {mcl:3d} {pv:.3f} | "
              f"{trig:8s} {rf_dip} {tf_min} {hu_min} {str(r2_min):4s} {str(chop_max):4s} {sl:4d} {tp:4d} {hold}")


if __name__ == '__main__':
    asset = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD'
    tf = sys.argv[2] if len(sys.argv) > 2 else 'M5'
    scan(asset, tf)
