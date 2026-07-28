# -*- coding: utf-8 -*-
"""
s337_archetype_scan.py — اسکنِ چند آرکه‌تایپِ سیگنالِ پُردقت با RQS+ کامل
=========================================================================
هدف: یافتنِ سیگنالی که هر ۶ گیتِ RQS+ را پاس کند و WR بالا (چالش) داشته باشد.
به‌جای حدس، چند «معماریِ سیگنال» را کنار هم می‌گذاریم و مستقیم RQS+ می‌گیریم.

نکتهٔ ضدِ تله (اشتباه ۹): RQS+ خودش TP<SL را با G1 (WR_breakeven) مهار می‌کند؛
پس ما TP≥SL یا متوازن نگه می‌داریم و به WRِ *واقعی* تکیه می‌کنیم.

آرکه‌تایپ‌ها (هر کدام trend-continuation، چون طلا hurst>0.5 دارد):
 A) Ehlers trendflex+reflex : روندِ کم‌تأخیر + تایمینگِ چرخه (buy dip / sell rally در روند)
 B) elder_impulse gate      : فقط وقتی شیبِ EMA و هیستوگرامِ MACD هم‌جهت‌اند
 C) aroon lock + pullback   : روندِ جوان (aroon قفل) + پول‌بکِ کوچک
 D) stc phase + ssf slope   : فازِ روندِ شاف + جهتِ سوپر-اسموتر
همه با فیلترِ رژیمِ آماری (r2/hurst) گیت می‌شوند.
"""
import numpy as np
import pandas as pd
import itertools
from engine import scalp_engine as se, rqs
from engine import indicator_bank as ib

BARS_DAY = {'M5': 288, 'M15': 96, 'M30': 48, 'H1': 24}


def load(asset, tf):
    return se.load_data(f'data/{asset}_{tf}.csv')


def rqs_of(df, asset, sig_long, sig_short, sl, tp, mh):
    tr = se.simulate_trades(df, sig_long, sig_short, sl, tp, asset, mh, False)
    if tr is not None and len(tr):
        tr = tr.copy(); tr['tp_pip'] = float(tp)
    r = rqs.compute_rqs(tr, asset, sl_pip=sl, tp_pip=tp)
    return r


def gline(r):
    return ''.join('1' if v else '0' for v in r['gates'].values())


def scan(asset='XAUUSD', tf='M5'):
    df = load(asset, tf); n = len(df); days = n / BARS_DAY[tf]
    print(f"=== ARCHETYPE SCAN {asset}/{tf} === n={n} (~{days:.0f}روز)  "
          f"target: WR80@~{days:.0f}tr یا WR70@~{days*4:.0f}tr\n")

    # --- ابزارهای مشترک (shift(1) = بدون look-ahead) ---
    def S(name):
        return ib.compute(name, df).shift(1).values
    hurst = S('hurst'); r2 = S('r2_fib_55'); r2f34 = S('r2_fib_34')
    trendflex = S('trendflex'); reflex = S('reflex')
    elder = S('elder_impulse'); aroon = S('aroon')
    stc = S('stc'); ssf = ib.compute('ssf_fib_21', df)
    ssf_slope = (ssf - ssf.shift(2)).shift(1).values
    ema_dist = S('ema_dist_atr')

    def bmask(x):
        return np.nan_to_num(x, nan=False).astype(bool)

    results = []

    # ---------- آرکه‌تایپ A: trendflex روند + reflex تایمینگ ----------
    # LONG: روندِ صعودی (trendflex>0) + reflex از کف برمی‌گردد (پول‌بکِ چرخه تمام شد)
    for r2t, hut in [(0.45, 0.5), (0.6, 0.5), (0.6, 0.55)]:
        gate = (r2 > r2t) & (hurst > hut)
        # reflex turn up: reflex[i-1] بالاتر از reflex[i-2]  → از داده shift‌شده
        reflex_up = np.r_[False, reflex[1:] > reflex[:-1]]
        reflex_dn = np.r_[False, reflex[1:] < reflex[:-1]]
        longA = bmask(gate & (trendflex > 0) & reflex_up & (reflex < 0))
        shortA = bmask(gate & (trendflex < 0) & reflex_dn & (reflex > 0))
        for sl, tp in [(55, 55), (89, 89), (72, 89), (89, 110)]:
            rL = rqs_of(df, asset, longA, np.zeros(n, bool), sl, tp, 48)
            rS = rqs_of(df, asset, np.zeros(n, bool), shortA, sl, tp, 48)
            results.append(('A-long', f'r2>{r2t} H>{hut} SL{sl}/TP{tp}', rL))
            results.append(('A-short', f'r2>{r2t} H>{hut} SL{sl}/TP{tp}', rS))

    # ---------- آرکه‌تایپ B: elder_impulse gate + pullback ----------
    for r2t in [0.45, 0.6]:
        gate = (r2 > r2t) & (hurst > 0.5)
        longB = bmask(gate & (elder > 0) & (ema_dist < -0.3) & (ema_dist > -1.5))
        shortB = bmask(gate & (elder < 0) & (ema_dist > 0.3) & (ema_dist < 1.5))
        for sl, tp in [(55, 55), (89, 89), (72, 100)]:
            results.append(('B-long', f'r2>{r2t} SL{sl}/TP{tp}',
                            rqs_of(df, asset, longB, np.zeros(n, bool), sl, tp, 48)))
            results.append(('B-short', f'r2>{r2t} SL{sl}/TP{tp}',
                            rqs_of(df, asset, np.zeros(n, bool), shortB, sl, tp, 48)))

    # ---------- آرکه‌تایپ C: aroon lock (روندِ جوان) + جهتِ ssf ----------
    for at in [50, 70]:
        longC = bmask((aroon > at) & (ssf_slope > 0) & (hurst > 0.5))
        shortC = bmask((aroon < -at) & (ssf_slope < 0) & (hurst > 0.5))
        for sl, tp in [(89, 89), (110, 144), (89, 144)]:
            results.append(('C-long', f'aroon>{at} SL{sl}/TP{tp}',
                            rqs_of(df, asset, longC, np.zeros(n, bool), sl, tp, 64)))
            results.append(('C-short', f'aroon<-{at} SL{sl}/TP{tp}',
                            rqs_of(df, asset, np.zeros(n, bool), shortC, sl, tp, 64)))

    # ---------- آرکه‌تایپ D: stc فاز + ssf جهت ----------
    for r2t in [0.45, 0.6]:
        gate = (r2 > r2t)
        # stc از زیر 25 برمی‌گردد (شروعِ فازِ صعودی) / از بالای 75 برمی‌گردد
        stc_up = np.r_[False, (stc[1:] > 25) & (stc[:-1] <= 25)]
        stc_dn = np.r_[False, (stc[1:] < 75) & (stc[:-1] >= 75)]
        longD = bmask(gate & stc_up & (ssf_slope > 0))
        shortD = bmask(gate & stc_dn & (ssf_slope < 0))
        for sl, tp in [(89, 89), (89, 144), (110, 144)]:
            results.append(('D-long', f'r2>{r2t} SL{sl}/TP{tp}',
                            rqs_of(df, asset, longD, np.zeros(n, bool), sl, tp, 64)))
            results.append(('D-short', f'r2>{r2t} SL{sl}/TP{tp}',
                            rqs_of(df, asset, np.zeros(n, bool), shortD, sl, tp, 64)))

    # --- گزارش: مرتب بر اساس تعداد گیتِ پاس، سپس WR ---
    def keyf(x):
        r = x[2]; m = r['metrics']
        return (sum(r['gates'].values()), m.get('win_rate', 0))
    results.sort(key=keyf, reverse=True)
    print(f"{'arch':>8} {'RQS':>5} {'g':>2} {'n':>5} {'WR':>5} {'PF':>5} {'DD':>5} {'MCL':>4} {'/day':>5} {'gates':>7}  cfg")
    for name, cfg, r in results[:28]:
        m = r['metrics']; nt = m.get('n_trades', 0)
        print(f"{name:>8} {r['rqs_score']:>5.1f} {sum(r['gates'].values()):>2d} {nt:>5d} "
              f"{m.get('win_rate',0):>5.1f} {m.get('profit_factor',0):>5.2f} {m.get('max_dd_pct',0):>5.1f} "
              f"{m.get('max_consec_losses',0):>4d} {nt/days:>5.2f} {gline(r):>7}  {cfg}")


if __name__ == '__main__':
    import sys
    scan('XAUUSD', sys.argv[1] if len(sys.argv) > 1 else 'M5')
