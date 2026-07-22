# -*- coding: utf-8 -*-
"""
S171 — اعتبارسنجیِ کاملِ «لایهٔ مستقلِ Signs-of-Strength» روی XAUUSD (long)
================================================================================
> قانونِ #۱: هدف = سودِ خالصِ بیشتر (XAUUSD+EURUSD)؛ WR≥۴۰٪ فقط کفِ هر لایه.

در S171-B مسیرِ (الف) نشان داد SoS rising-edge روی طلا با SL150/TP300/mh96 یک جریانِ
long با net مثبت و WR≥۴۰ و هر دو نیمه مثبت می‌سازد. طبقِ گیتِ سختِ پروژه و **قانونِ
همپوشانیِ پرامپت** باید پیش از پذیرش:
  ۱) walk-forward ۴-پنجره: هر پنجره net>0 و WR≥۴۰.
  ۲) درصدِ همپوشانی با لایه‌های زمان-محورِ موجود (روزهای Monday/Turn/Mid/EOM و ساعاتِ
     شب) و با ساختارِ Brooks High-2 محاسبه شود.
  ۳) سهمِ **مستقل** (سیگنال‌هایی که در هیچ‌کدام از پنجره‌های موجود نمی‌افتند) جدا
     ارزیابی شود؛ فقط این سهمِ مستقل به رکورد افزوده می‌شود (ضدِ دوباره‌شماری،
     دقیقاً مثلِ تصمیمِ محافظه‌کارانهٔ S168).

خروجی نهایی: حکمِ پذیرش/رد + Δ سودِ خالصِ مستقل.
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

# بهترین واریانتِ مستقلِ S171-B
WIN, THR, SL, TP, MH = 12, 2, 150, 300, 96


def sos_rising_edge(df, thr, ema_period, win):
    sos = signs_of_strength_bull(df, ema_period=ema_period, win=win)
    strong = sos['score'] >= thr
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


def wf(df, sig, sl, tp, mh, asset, k=4):
    """walk-forward: تقسیمِ زمانی به k پنجره، هر پنجره جدا."""
    n = len(df); bounds = np.linspace(0, n, k + 1).astype(int)
    rows = []
    for i in range(k):
        a, b = bounds[i], bounds[i + 1]
        sub = df.iloc[a:b].reset_index(drop=True)
        subsig = sig[a:b]
        r = stats(sim(sub, subsig, np.zeros(len(sub), bool), sl, tp, mh, asset), asset)
        rows.append(r)
    return rows


def main():
    print("=" * 100)
    print(f"S171 اعتبارسنجی — لایهٔ مستقلِ SoS (طلا long)  w{WIN} thr{THR} SL{SL}/TP{TP}/mh{MH}")
    print("=" * 100, flush=True)

    dfx = cal(lastn(cal(load('XAUUSD_M15'))))
    sig = sos_rising_edge(dfx, THR, 20, WIN)
    z = np.zeros(len(dfx), bool)

    full = stats(sim(dfx, sig, z, SL, TP, MH, 'XAUUSD'), 'XAUUSD')
    print(f"\nکلِ لایه: net=${full['net']:+,.0f}  WR={full['wr']:.1f}%  n={full['n']}  PF={full['pf']:.2f}")

    # --- walk-forward ---
    print("\n### walk-forward ۴-پنجره ###")
    wfr = wf(dfx, sig, SL, TP, MH, 'XAUUSD', 4)
    wf_ok = True
    for i, r in enumerate(wfr, 1):
        ok = r['net'] > 0 and r['wr'] >= WR_FLOOR and r['n'] >= 5
        wf_ok = wf_ok and ok
        print(f"   W{i}: net=${r['net']:+8,.0f}  WR={r['wr']:5.1f}%  n={r['n']:4d}  PF={r['pf']:.2f}  {'✅' if ok else '⛔'}")
    print(f"   ⇒ walk-forward {'پاس' if wf_ok else 'رد'}")

    # --- همپوشانی با پنجره‌های زمان-محورِ موجود ---
    print("\n### همپوشانی با لایه‌های موجود ###")
    hour = dfx['hour'].values; dow = dfx['dow'].values; dom = dfx['dom'].values
    # مجموعه پنجره‌های زمان-محورِ طلا (S139..S144) + Brooks High-2
    overnight = np.isin(hour, [22, 23])                          # S139
    monday = (dow == 0) & np.isin(hour, [18, 19, 20, 21])        # S140
    turn = np.isin(dom, [1, 2, 3])                               # S141
    midm = np.isin(dom, [10, 13, 20])                            # S142
    eom = np.isin(dom, [24, 25, 26])                             # S144 (تقریبی)
    long_evt, _ = count_high2_low2(dfx, 20, 50)
    high2 = pd.Series(long_evt).shift(1).fillna(False).to_numpy()  # S168

    time_union = overnight | monday | turn | midm | eom
    sig_idx = np.where(sig)[0]
    n_sig = len(sig_idx)

    def pct_overlap(mask, label):
        if n_sig == 0:
            return 0.0
        ov = float(mask[sig_idx].sum()) / n_sig * 100
        print(f"   با {label:22s}: {ov:5.1f}%")
        return ov

    pct_overlap(overnight, 'S139 Overnight')
    pct_overlap(monday, 'S140 Monday')
    pct_overlap(turn, 'S141 Turn-of-Month')
    pct_overlap(midm, 'S142 Mid-Month')
    pct_overlap(eom, 'S144 EOM')
    ov_time = pct_overlap(time_union, 'اجتماعِ زمان-محورها')
    ov_h2 = pct_overlap(high2, 'S168 Brooks High-2')

    # --- سهمِ مستقل: سیگنال‌هایی که در هیچ پنجرهٔ زمان-محور و نه High-2 نمی‌افتند ---
    indep_mask = sig & (~time_union) & (~high2)
    indep = stats(sim(dfx, indep_mask, z, SL, TP, MH, 'XAUUSD'), 'XAUUSD')
    print(f"\n### سهمِ مستقل (خارج از همهٔ پنجره‌ها و High-2) ###")
    print(f"   net=${indep['net']:+,.0f}  WR={indep['wr']:.1f}%  n={indep['n']}  PF={indep['pf']:.2f}")
    # walk-forward روی سهمِ مستقل
    wfi = wf(dfx, indep_mask, SL, TP, MH, 'XAUUSD', 4)
    indep_wf_ok = all(r['net'] > 0 and r['n'] >= 3 for r in wfi)
    print("   walk-forward سهمِ مستقل:")
    for i, r in enumerate(wfi, 1):
        print(f"     W{i}: net=${r['net']:+8,.0f}  WR={r['wr']:5.1f}%  n={r['n']:4d}")

    # --- حکم ---
    accept_full = wf_ok and full['wr'] >= WR_FLOOR and full['net'] > 0
    indep_edge_ok = (indep['n'] >= 30 and indep['wr'] >= WR_FLOOR and indep['net'] > 0 and indep_wf_ok)
    print("\n" + "=" * 100)
    print("### حکم ###")
    print(f"   کلِ لایه گیتِ سخت را پاس می‌کند؟ {'✅' if accept_full else '⛔'} "
          f"(اما همپوشانیِ زمان-محور {ov_time:.0f}% + High-2 {ov_h2:.0f}%)")
    print(f"   سهمِ مستقل لبهٔ واقعیِ ناهمبسته است؟ {'✅' if indep_edge_ok else '⛔'}")
    delta = indep['net'] if indep_edge_ok else 0.0
    verdict = 'ACCEPTED (independent share)' if indep_edge_ok else 'REJECTED'
    print(f"   ⇒ تصمیمِ محافظه‌کارانهٔ ضدِ دوباره‌شماری: Δ سودِ خالص = ${delta:+,.0f}  [{verdict}]")
    record_before = 225130
    print(f"   رکورد: +${record_before:,.0f} ⇒ +${record_before + delta:,.0f}")

    out = dict(variant=dict(win=WIN, thr=THR, sl=SL, tp=TP, mh=MH),
               full=full, wf=wfr, wf_ok=wf_ok,
               overlap_time_union=ov_time, overlap_high2=ov_h2,
               independent=indep, independent_wf=wfi, independent_wf_ok=indep_wf_ok,
               accept_full=accept_full, indep_edge_ok=indep_edge_ok,
               delta_net=float(delta), verdict=verdict,
               record_before=record_before, record_after=float(record_before + delta))
    with open(os.path.join(RESULTS, '_s171_sos_standalone_validate.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)
    print("\n✅ ذخیره شد: results/_s171_sos_standalone_validate.json")


if __name__ == '__main__':
    main()
