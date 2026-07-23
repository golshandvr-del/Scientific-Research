"""
s203_sos_h1_vs_m15_overlap.py — قانونِ همپوشانیِ اجباری: SoS-H1 در برابر SoS-M15 (رکورد)
================================================================================
SoS روی M15 در پرتفویِ فعال است (w32/thr2/SL300/TP450/mh96، سهمِ مستقل +$8,130).
SoS روی H1 (SL250/TP750/mh96) در S202 گیتِ سخت را با net=+$12,765 پاس کرد.

قبل از هر تصمیم، طبقِ قانونِ همپوشانی باید مشخص شود دو نسخه چقدر همپوشانی/همبستگی دارند:
  • هم‌بستگیِ PnLِ روزانه (آیا در روزهای یکسان سود/زیان می‌سازند؟)
  • همپوشانیِ روز-معاملاتی (٪ روزهایی که هر دو در آن‌ها ترید دارند)
  • سهمِ مستقلِ افزایشیِ SoS-H1 = تریدهای H1 در روزهایی که SoS-M15 ترید نداشته.

سه حالتِ تصمیم:
  1) corr پایین (<0.35) و همپوشانیِ روز پایین ⇒ لبهٔ مستقلِ نو ⇒ افزودن مستقل (سود خالص↑).
  2) corr بالا و H1 پرسودتر ⇒ ارتقا/جایگزینی.
  3) corr بالا و M15 پرسودتر ⇒ بررسیِ SoS-H1 به‌عنوان فیلترِ تأیید (قانونِ سومِ همپوشانی).
همه روی بازهٔ هم‌ترازِ رکورد M15 (۲۰۲۰+) سنجیده می‌شود (مقایسهٔ سیب‌به‌سیب).
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(__file__))
from s171_brooks_signs_of_strength_filter import (
    load, cal, stats, sim, signs_of_strength_bull)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIGN = pd.Timestamp('2020-02-20')


def sos_edge(df):
    sos = signs_of_strength_bull(df, ema_period=20, win=32)
    strong = sos['score'] >= 2
    prev = pd.Series(strong).shift(1).fillna(False).to_numpy()
    edge = strong & (~prev)
    return pd.Series(edge).shift(1).fillna(False).to_numpy()


def trades_with_days(df, sl, tp, mh):
    """تریدها + روزِ ورود (UTC date) + pnl دلاری (۱ لات = pnl_pip*CONTRACT/100... اما
    برای همبستگی، pnl_pip کافی است چون مقیاس ثابت است)."""
    edge = sos_edge(df)
    z = np.zeros(len(df), bool)
    t = sim(df, edge, z, sl, tp, mh, 'XAUUSD')
    if t is None or len(t) == 0:
        return None
    t = t.copy()
    t['day'] = df['dt'].iloc[t['entry_bar'].values].dt.floor('D').values
    return t


def daily_pnl(t):
    return t.groupby('day')['pnl_pip'].sum()


def main():
    print("=" * 92)
    print("s203 — قانونِ همپوشانیِ اجباری: SoS-H1 در برابر SoS-M15 (بازهٔ ۲۰۲۰+)")
    print("=" * 92, flush=True)

    # --- بارگذاریِ هر دو تایم‌فریم روی بازهٔ هم‌تراز ---
    dfm = cal(load('XAUUSD_M15')); dfm = dfm[dfm['dt'] >= ALIGN].reset_index(drop=True)
    dfh = cal(load('XAUUSD_H1'));  dfh = dfh[dfh['dt'] >= ALIGN].reset_index(drop=True)
    print(f"M15: {len(dfm):,} کندل | H1: {len(dfh):,} کندل")

    tm = trades_with_days(dfm, 300, 450, 96)   # پارامترِ رکوردِ M15
    th = trades_with_days(dfh, 250, 750, 96)   # بهترین گیت-پاسِ H1

    sm = stats(tm, 'XAUUSD'); sh = stats(th, 'XAUUSD')
    print(f"\nSoS-M15 (رکورد SL300/TP450/mh96): net=${sm['net']:+,.0f}  WR={sm['wr']:.1f}%  n={sm['n']}")
    print(f"SoS-H1  (نو     SL250/TP750/mh96): net=${sh['net']:+,.0f}  WR={sh['wr']:.1f}%  n={sh['n']}")

    # --- همبستگیِ PnLِ روزانه ---
    dm = daily_pnl(tm); dh = daily_pnl(th)
    all_days = sorted(set(dm.index) | set(dh.index))
    a = dm.reindex(all_days).fillna(0.0)
    b = dh.reindex(all_days).fillna(0.0)
    corr = np.corrcoef(a.values, b.values)[0, 1] if len(all_days) > 2 else 0.0

    # --- همپوشانیِ روز-معاملاتی ---
    days_m = set(dm.index); days_h = set(dh.index)
    inter = days_m & days_h
    overlap_h_in_m = 100.0 * len(inter) / max(1, len(days_h))   # ٪ روزهای H1 که M15 هم ترید دارد
    overlap_m_in_h = 100.0 * len(inter) / max(1, len(days_m))

    print(f"\nهمبستگیِ PnLِ روزانه (M15 ↔ H1): {corr:+.3f}")
    print(f"روزهای معاملاتی: M15={len(days_m)}  H1={len(days_h)}  مشترک={len(inter)}")
    print(f"٪ روزهای H1 که M15 هم در آن ترید دارد: {overlap_h_in_m:.1f}%")
    print(f"٪ روزهای M15 که H1 هم در آن ترید دارد: {overlap_m_in_h:.1f}%")

    # --- سهمِ مستقلِ افزایشیِ H1: تریدهای H1 در روزهایی که M15 ترید نداشته ---
    th_indep = th[~th['day'].isin(days_m)].copy()
    s_indep = stats(th_indep, 'XAUUSD') if len(th_indep) else dict(net=0, wr=0, n=0, pf=0)
    print(f"\nسهمِ *مستقلِ* SoS-H1 (روزهای بدونِ تریدِ SoS-M15):")
    print(f"   net=${s_indep['net']:+,.0f}  WR={s_indep['wr']:.1f}%  n={s_indep['n']}")

    # walk-forward روی سهمِ مستقل برای اطمینان از پایداری
    def wf_indep(t, k=4):
        if t is None or len(t) < 8:
            return [0, 0, 0, 0]
        t = t.sort_values('entry_bar').reset_index(drop=True)
        bnd = [int(len(t) * i / k) for i in range(k + 1)]
        return [round(t.iloc[bnd[i]:bnd[i+1]]['pnl_pip'].sum() * 100 / 100) for i in range(k)]
    # (تقریبِ pnl دلاری با ۰.۰۱ لات پایه؛ فقط علامتِ WF مهم است)
    wf = wf_indep(th_indep)
    print(f"   WF سهمِ مستقل (علامت مهم است): {wf}")

    # --- حکم ---
    print("\n" + "=" * 92)
    print("حکمِ قانونِ همپوشانی:")
    if abs(corr) < 0.35 and overlap_h_in_m < 60:
        verdict = "INDEPENDENT"
        print("  ⇒ ناهمبسته و همپوشانیِ روز پایین ⇒ لایهٔ مستقلِ نو. سهمِ مستقل را می‌افزاییم.")
    elif corr >= 0.35 and sh['net'] > sm['net']:
        verdict = "UPGRADE"
        print("  ⇒ همبسته و H1 پرسودتر ⇒ ارتقا/جایگزینیِ نسخهٔ M15 با H1 (بررسی شود).")
    elif corr >= 0.35:
        verdict = "FILTER"
        print("  ⇒ همبسته و M15 پرسودتر ⇒ SoS-H1 به‌عنوان فیلترِ تأیید بررسی شود (قانونِ سوم).")
    else:
        verdict = "PARTIAL-INDEPENDENT"
        print("  ⇒ همپوشانیِ جزئی ⇒ سهمِ مستقلِ افزایشی ارزیابی و در صورتِ پایداری افزوده شود.")

    out = dict(corr=round(float(corr), 3),
               m15=dict(net=round(sm['net']), wr=round(sm['wr'], 1), n=sm['n']),
               h1=dict(net=round(sh['net']), wr=round(sh['wr'], 1), n=sh['n']),
               overlap_h_in_m=round(overlap_h_in_m, 1),
               overlap_m_in_h=round(overlap_m_in_h, 1),
               indep=dict(net=round(s_indep['net']), wr=round(s_indep['wr'], 1),
                          n=s_indep['n'], wf=wf),
               verdict=verdict)
    with open(os.path.join(ROOT, 'results', '_s203_sos_overlap.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("=" * 92)
    print("ذخیره شد: results/_s203_sos_overlap.json")


if __name__ == '__main__':
    main()
