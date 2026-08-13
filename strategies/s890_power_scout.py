#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S890 «شکستِ بازتابی» — اسکاوتِ توان (پیش از هر آزمون).

هدف: قبل از نوشتنِ کدِ نهایی، طبقِ قانونِ پروژه، بسنجیم آیا این ایده اصلاً
*می‌تواند* H3 را پاس کند:
  - نرخِ شلیک (رویدادِ گذر از سقف/کفِ Lکندلیِ close) روی نیمهٔ اکتشاف
  - هندسهٔ ATR-محور و نسبتِ هزینه (اسپرد ۳.۳ pip / SL)
  - n_required_for_h3 در برابرِ nِ در دسترس

⚠️ این فایل هیچ آزمونِ RQS2 اجرا نمی‌کند — فقط امکان‌سنجی است. جست‌وجو فقط
روی ۷۰٪ اولِ داده (نیمهٔ اکتشافِ مسیرِ C).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd
from tools import s434_fast_data as fd
from engine.rqs2 import n_required_for_h3

ASSET = 'XAUUSD'
SPREAD_PIP = 3.3          # 0.33$/oz در pip=0.1
FIBS = [21, 34, 55, 89, 144]   # تنها پارامتر: L (غیرگرد، فیبوناچی)
SL_ATR_MULT = 1.5
RR = 1.5                  # TP = 1.5×SL ⇒ سربه‌سرِ بی‌هزینه = 40%

def atr(df, n=100):
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(n).mean().values

def scout_tf(tf):
    d = fd.load_fast(ASSET, tf)
    df = fd.as_dataframe(d)
    N = len(df)
    split = int(N * 0.70)
    dfe = df.iloc[:split]            # نیمهٔ اکتشاف — فقط همین را می‌بینیم
    c = dfe['close'].values
    a = atr(dfe, 100)
    med_atr = float(np.nanmedian(a))
    sl_pip = SL_ATR_MULT * med_atr / 0.1     # pip = 0.1$
    tp_pip = RR * sl_pip
    # سربه‌سرِ هزینه‌دار: (SL+c)/(SL+TP)
    be = (sl_pip + SPREAD_PIP) / (sl_pip + tp_pip) * 100.0
    cost_ratio = SPREAD_PIP / sl_pip * 100.0
    rows = []
    for L in FIBS:
        hh = pd.Series(c).shift(1).rolling(L).max().values   # سقفِ L کندلِ *قبل*
        ll = pd.Series(c).shift(1).rolling(L).min().values
        # رویدادِ گذر: الان بالای سقف، کندلِ قبل نبود
        lb = (c > hh) & ~(np.roll(c, 1) > np.roll(hh, 1))
        sb = (c < ll) & ~(np.roll(c, 1) < np.roll(ll, 1))
        lb[:L+2] = False; sb[:L+2] = False
        n_ev = int(lb.sum() + sb.sum())
        # با no-overlap و max_hold~64 تعدادِ معاملهٔ واقعی کمتر می‌شود؛
        # ضریبِ تجربیِ محافظه‌کارانه 0.5 (طبق تجربهٔ s382: رویدادها متراکم‌اند)
        n_est = int(n_ev * 0.5)
        rows.append(dict(L=L, events=n_ev, n_est=n_est))
    return dict(tf=tf, bars=N, split=split, med_atr=med_atr,
                sl_pip=round(sl_pip, 2), tp_pip=round(tp_pip, 2),
                be_pct=round(be, 2), cost_pct=round(cost_ratio, 2),
                span=f"{df['time'].iloc[0]} → {df['time'].iloc[split-1]}",
                src=d.get('src', '?'), rows=rows)

def main():
    print(f"{'TF':>4} {'bars':>9} {'medATR':>8} {'SL(pip)':>8} {'BE%':>6} {'cost%':>6}  events(per L)")
    out = []
    for tf in ['M1', 'M5', 'M15', 'M30', 'H1', 'H2', 'H3', 'D1']:
        try:
            r = scout_tf(tf)
        except Exception as e:
            print(f"{tf:>4}  ERR {e}"); continue
        ev = ' '.join(f"L{x['L']}:{x['events']}" for x in r['rows'])
        print(f"{r['tf']:>4} {r['bars']:>9} {r['med_atr']:>8.3f} {r['sl_pip']:>8.1f} "
              f"{r['be_pct']:>6.2f} {r['cost_pct']:>6.2f}  {ev}")
        out.append(r)
    # ریاضیِ توان: چه lift ی با چه n قابلِ اثبات است؟
    print("\n--- n_required_for_h3 (کرانِ خوش‌بینانه) ---")
    for lift in [4, 6, 8, 10, 14]:
        print(f"  lift={lift}pp  p0=0.42 ⇒ n≥{n_required_for_h3(lift, 0.42):.0f}")
    os.makedirs('results/_s890', exist_ok=True)
    with open('results/_s890/power_scout.json', 'w') as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("\nsaved → results/_s890/power_scout.json")

if __name__ == '__main__':
    main()
