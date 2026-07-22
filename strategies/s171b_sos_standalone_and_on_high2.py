# -*- coding: utf-8 -*-
"""
S171-B — دو کاربردِ دیگرِ Signs-of-Strength (فصلِ ۱۹ Al Brooks) فراتر از AND سراسری:
================================================================================
> قانونِ #۱: هدف = بیشینهٔ سودِ خالص (XAUUSD+EURUSD)؛ WR≥۴۰٪ فقط کفِ هر لایه.

در S171 دیدیم فیلترِ SoS به‌صورتِ AND سراسری همیشه WR↑ ولی net↓ می‌دهد (رد).
اینجا دو مسیرِ دیگر آزموده می‌شود:

  (الف) SoS به‌عنوان «لایهٔ مستقلِ روند-دنبال‌کن» (راهِ سوم: لایهٔ جدید).
        ورود Long وقتی score از آستانه عبور *تازه* کند (rising-edge)، مستقل از
        هر پنجرهٔ زمانی. اگر گیتِ سخت را پاس کند ⇒ لبهٔ مستقلِ تازه.

  (ب) SoS به‌عنوان فیلترِ تأیید روی «سهمِ مستقلِ Brooks High-2» (S168, طلا long).
        S168 لبهٔ ساختاریِ +$1,351 داشت (WR ۴۷.۳٪). آیا افزودنِ شرطِ «روند قوی است»
        هم WR و هم net را بالا می‌برد؟ (هم‌افزاییِ دو مفهومِ کتابِ Brooks).

گیت (سیب‌به‌سیب): net>0 + هر دو نیمه + WR≥۴۰ + n≥۳۰. برای مسیرِ (ب) علاوه بر آن
net≥base و WR≥base (منطقِ فیلترِ بهبود).
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from engine import scalp_engine as se
from engine import indicators as ind
from s168_brooks_high2_low2 import count_high2_low2
from s171_brooks_signs_of_strength_filter import (
    load, lastn, cal, stats, sim, signs_of_strength_bull)

RESULTS = os.path.join(ROOT, 'results')
CAP, RISK, YEARS = 10000.0, 1.0, 4
WR_FLOOR = 40.0
se.ASSETS['XAUUSD'].update(spread_pip=3.3, comm=0.0, slip_pip=0.0)
se.ASSETS['EURUSD'].update(spread_pip=1.0, comm=0.0, slip_pip=0.3)


def halves_ok(df, sig, sl, tp, mh, asset):
    z = np.zeros(len(df), bool)
    tr = sim(df, sig, z, sl, tp, mh, asset)
    if tr is None or len(tr) < 30:
        return None
    st, _, pt = se.run_capital_pertrade(tr, asset, initial_capital=CAP, risk_pct=RISK, compounding=False)
    nu = pt['net_usd']; half = len(nu) // 2
    h1 = float(nu.iloc[:half].sum()); h2 = float(nu.iloc[half:].sum())
    return dict(h1=h1, h2=h2)


def sos_rising_edge(df, thr, ema_period, win):
    sos = signs_of_strength_bull(df, ema_period=ema_period, win=win)
    strong = sos['score'] >= thr
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)                      # لحظهٔ عبورِ رو به بالا
    return pd.Series(edge).shift(1).fillna(False).to_numpy()  # ورودِ کندلِ بعد


def main():
    print("=" * 100)
    print("S171-B — (الف) SoS لایهٔ مستقل   (ب) SoS فیلتر روی سهمِ مستقلِ Brooks High-2")
    print("=" * 100, flush=True)

    dfx = cal(lastn(cal(load('XAUUSD_M15'))))
    dfe = cal(lastn(cal(load('EURUSD_M15'))))
    report = {}

    # ---------- (الف) لایهٔ مستقلِ SoS روند-دنبال‌کن ----------
    print("\n### (الف) SoS به‌عنوان لایهٔ مستقلِ Long (rising-edge) ###")
    standalone = []
    for asset, df in (('XAUUSD', dfx), ('EURUSD', dfe)):
        grids = [(100, 300, 96), (100, 200, 64), (150, 300, 96)] if asset == 'XAUUSD' \
            else [(20, 40, 96), (20, 30, 64), (25, 45, 96)]
        for win in (12, 20, 32):
            for thr in (2, 3):
                sig = sos_rising_edge(df, thr, 20, win)
                for (sl, tp, mh) in grids:
                    r = stats(sim(df, sig, np.zeros(len(df), bool), sl, tp, mh, asset), asset)
                    if r['n'] < 30:
                        continue
                    hv = halves_ok(df, sig, sl, tp, mh, asset)
                    acc = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and hv and hv['h1'] > 0 and hv['h2'] > 0)
                    row = dict(asset=asset, win=win, thr=thr, sl=sl, tp=tp, mh=mh,
                               net=r['net'], wr=r['wr'], n=r['n'], pf=r['pf'],
                               h1=(hv['h1'] if hv else None), h2=(hv['h2'] if hv else None),
                               accepted=acc)
                    standalone.append(row)
        best = sorted([x for x in standalone if x['asset'] == asset], key=lambda x: x['net'], reverse=True)[:5]
        print(f"\n  {asset}: بهترین‌ها بر اساس net")
        for x in best:
            tag = '✅ACCEPT' if x['accepted'] else 'reject'
            print(f"    {tag} w{x['win']} thr{x['thr']} SL{x['sl']}/TP{x['tp']}/mh{x['mh']}  "
                  f"net=${x['net']:+8,.0f} WR={x['wr']:5.1f}% n={x['n']:4d} PF={x['pf']:.2f} "
                  f"h1={x['h1']:+.0f} h2={x['h2']:+.0f}")
    report['standalone'] = standalone

    # ---------- (ب) SoS فیلتر روی سیگنالِ Brooks High-2 (طلا long) ----------
    print("\n### (ب) SoS فیلتر روی سیگنالِ Brooks High-2 — XAUUSD long (ema20/50 SL300/TP450 mh32) ###")
    ef, es, sl, tp, mh = 20, 50, 300, 450, 32
    long_evt, _ = count_high2_low2(dfx, ef, es)
    base_sig = pd.Series(long_evt).shift(1).fillna(False).to_numpy()
    z = np.zeros(len(dfx), bool)
    base = stats(sim(dfx, base_sig, z, sl, tp, mh, 'XAUUSD'), 'XAUUSD')
    print(f"  baseline High-2: WR={base['wr']:.1f}% net=${base['net']:+,.0f} n={base['n']} PF={base['pf']:.2f}")
    onhigh2 = []
    for win in (12, 20, 32):
        for thr in (2, 3, 4):
            sos = signs_of_strength_bull(dfx, ema_period=20, win=win)
            filt = pd.Series(sos['score'] >= thr).shift(1).fillna(False).to_numpy()
            sig = base_sig & filt
            r = stats(sim(dfx, sig, z, sl, tp, mh, 'XAUUSD'), 'XAUUSD')
            hv = halves_ok(dfx, sig, sl, tp, mh, 'XAUUSD') if r['n'] >= 30 else None
            improve = bool(r['n'] >= 30 and r['wr'] >= WR_FLOOR and r['wr'] >= base['wr']
                           and r['net'] >= base['net'] and hv and hv['h1'] > 0 and hv['h2'] > 0)
            row = dict(win=win, thr=thr, net=r['net'], wr=r['wr'], n=r['n'], pf=r['pf'],
                       h1=(hv['h1'] if hv else None), h2=(hv['h2'] if hv else None), improve=improve)
            onhigh2.append(row)
            mark = '  ✅ بهبود' if improve else ''
            print(f"    SoS_w{win}_thr{thr}: WR={r['wr']:5.1f}% net=${r['net']:+8,.0f} "
                  f"n={r['n']:4d} PF={r['pf']:.2f}{mark}")
    report['on_high2'] = dict(base=base, variants=onhigh2)
    best_h2 = [x for x in onhigh2 if x['improve']]
    best_h2.sort(key=lambda x: x['net'], reverse=True)
    report['on_high2_best'] = best_h2[0] if best_h2 else None
    if best_h2:
        d = best_h2[0]['net'] - base['net']
        print(f"\n  🏅 بهترین بهبودِ (ب): w{best_h2[0]['win']} thr{best_h2[0]['thr']} "
              f"⇒ WR {base['wr']:.1f}%→{best_h2[0]['wr']:.1f}% net ${base['net']:+,.0f}→${best_h2[0]['net']:+,.0f} (Δ{d:+,.0f})")
    else:
        print("\n  ⛔ مسیرِ (ب) هم بهبودِ هم‌زمانِ WR↑ و net↑ نداد.")

    with open(os.path.join(RESULTS, '_s171b_sos_standalone_on_high2.json'), 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s171b_sos_standalone_on_high2.json")


if __name__ == '__main__':
    main()
