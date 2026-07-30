# -*- coding: utf-8 -*-
"""
ساختِ کارت‌های تایم‌فریمِ بالاتر از دادهٔ موجود (تجمیعِ OHLCV)
================================================================

**چرا لازم شد؟** تشخیصِ شکستِ S347 (بندِ ۷ فایلِ
`results/S347_VoteEnsemble_Xauusd_AllTF_rqs27.md`) دو چیز را هم‌زمان نشان داد:

  ۱) قانون ۴ می‌گوید کفِ سربه‌سر `۵۰(۱+هزینه/TP)` است، پس تایم‌فریمِ بالاتر
     (TP بزرگ‌تر) کفِ پایین‌تری دارد. `data/` برای **EURUSD فقط M1/M5/M15/M30**
     دارد و هر چهار کارت **زیرِ کفِ هزینه**اند ⇒ نیمی از دامنهٔ پروژه عملاً
     بدونِ هیچ کارتِ قابلِ‌معامله مانده بود.
  ۲) شکستِ `H3` از کمبودِ **نمونه** آمد نه نبودِ الگو. کارت‌های تازهٔ
     بالای کفِ هزینه، `n` تجمیعی را بالا می‌برند و `sd` صفر را با `1/√n`
     کوچک می‌کنند — بدونِ آنکه هیچ پارامترِ نویی برازش شود.

`EURUSD_M30` دارای **۲۰۰٬۰۰۰ کندل از ۲۰۱۰-۰۵ تا ۲۰۲۶-۰۷** است ⇒ تجمیع به D1
حدودِ **۴٬۲۰۰ کندل** می‌دهد، یعنی **بیشتر** از ۳٬۹۸۹ کندلِ `XAUUSD_D1`ِ بومی.

------------------------------------------------------------------------
دو انتخابِ حساس (که اگر غلط باشند، همه‌چیزِ بعدی بی‌معنا می‌شود)
------------------------------------------------------------------------

**الف) مرزِ کندل باید عیناً مثلِ دادهٔ بومی باشد.** از دادهٔ بومیِ طلا
اندازه‌گیری شد، حدس زده نشد:
    • `XAUUSD_D1` : برچسبِ **نیمه‌شبِ UTC**، فقط روزهای کاری
    • `XAUUSD_W1` : لنگرِ **یکشنبه** (نه دوشنبه) — `W-SUN` در pandas
اگر مرزِ اشتباه انتخاب شود، کندلِ ساخته‌شده «همان تایم‌فریم» نیست و مقایسه با
نتایجِ کارت‌های بومی بی‌اعتبار می‌شود.

**ب) کندلِ **ناقصِ** انتهایی حذف می‌شود.** آخرین سبد ممکن است نصفه باشد
(دادهٔ M30 در ۱۶:۰۰ تمام می‌شود ⇒ روزِ آخر ناقص است). نگه‌داشتنش یک کندلِ
«با دامنهٔ کوچک‌ترِ غیرواقعی» می‌سازد که ATR و شکستِ کانال را تحریف می‌کند.

------------------------------------------------------------------------
آزمونِ اعتبارِ روش (درون‌ساخت، اجباری)
------------------------------------------------------------------------
روش ادعا نمی‌شود؛ **اثبات** می‌شود: `XAUUSD_H1`ِ بومی به D1 تجمیع می‌شود و با
`XAUUSD_D1`ِ **بومی** مقایسه می‌گردد. اگر روش درست باشد باید عملاً منطبق شوند.
اجرای `python -m tools.resample_cards --validate` این را گزارش می‌کند.
"""

import sys
import os
import argparse
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import scalp_engine as se        # noqa: E402

# قاعدهٔ تجمیع برای هر تایم‌فریمِ هدف — مرزها از دادهٔ بومی اندازه‌گیری شده‌اند
RULES = {
    'H1': '1h',
    'H4': '4h',
    'D1': '1D',
    'W1': 'W-SUN',      # لنگرِ یکشنبه، عیناً مثلِ XAUUSD_W1ِ بومی
}

AGG = {'open': 'first', 'high': 'max', 'low': 'min',
       'close': 'last', 'volume': 'sum'}


def resample(df, tf, drop_partial=True):
    """تجمیعِ OHLCV به تایم‌فریمِ `tf` با مرزهای مطابقِ دادهٔ بومی."""
    if tf not in RULES:
        raise ValueError(f"unknown tf {tf}; known={list(RULES)}")
    d = df.set_index('dt')[['open', 'high', 'low', 'close', 'volume']]
    r = d.resample(RULES[tf], label='left', closed='left').agg(AGG)
    r = r.dropna(subset=['open', 'high', 'low', 'close'])   # سبدهای خالی (تعطیل)
    if drop_partial and len(r) > 1:
        # سبدِ آخر ناقص است اگر دادهٔ منبع پیش از پایانِ آن سبد تمام شده باشد
        last_edge = r.index[-1] + pd.tseries.frequencies.to_offset(RULES[tf])
        if df['dt'].iloc[-1] < last_edge - pd.Timedelta(seconds=1):
            r = r.iloc[:-1]
    out = r.reset_index()
    out['time'] = (out['dt'].astype('int64') // 10 ** 9).astype('int64')
    return out[['time', 'open', 'high', 'low', 'close', 'volume']]


def validate():
    """اثباتِ روش: تجمیعِ H1ِ بومی ⇒ D1، در برابرِ D1ِ بومی."""
    print("=== VALIDATION: resample(native H1) -> D1  vs  native D1 ===")
    h1 = se.load_data('data/XAUUSD_H1.csv')
    d1n = se.load_data('data/XAUUSD_D1.csv')
    d1r = resample(h1, 'D1')
    d1r['dt'] = pd.to_datetime(d1r['time'], unit='s')

    m = d1n.merge(d1r, on='time', suffixes=('_nat', '_res'))
    print(f"  native D1 bars = {len(d1n):,} · resampled = {len(d1r):,} · "
          f"matched on timestamp = {len(m):,}")
    ok = True
    for col in ('open', 'high', 'low', 'close'):
        a = m[f'{col}_nat'].values.astype('float64')
        b = m[f'{col}_res'].values.astype('float64')
        diff = np.abs(a - b)
        rel = diff / np.maximum(np.abs(a), 1e-9)
        exact = float((diff <= 1e-9).mean() * 100)
        print(f"  {col:<6} exact={exact:6.2f}%  max|Δ|={diff.max():.5f}  "
              f"max rel={rel.max()*100:.4f}%  median|Δ|={np.median(diff):.6f}")
        if rel.max() > 0.01:      # >۱٪ اختلاف = مشکلِ روش
            ok = False
    cov = len(m) / len(d1n) * 100
    print(f"  timestamp coverage = {cov:.2f}%")
    print("  ⇒ METHOD VALID ✅" if (ok and cov > 95) else "  ⇒ METHOD SUSPECT ❌")
    return ok and cov > 95


def build(symbol, src_tf, targets):
    src = f"data/{symbol}_{src_tf}.csv"
    df = se.load_data(src)
    print(f"=== BUILD from {src} ({len(df):,} bars · "
          f"{df['dt'].iloc[0]} .. {df['dt'].iloc[-1]}) ===")
    for tf in targets:
        out = resample(df, tf)
        p = f"data/{symbol}_{tf}.csv"
        if os.path.exists(p):
            print(f"  SKIP {tf}: {p} already exists (native data is never "
                  f"overwritten by a derived card)")
            continue
        out.to_csv(p, index=False)
        dt = pd.to_datetime(out['time'], unit='s')
        print(f"  wrote {p}  bars={len(out):,}  {dt.iloc[0]} .. {dt.iloc[-1]}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--validate', action='store_true')
    ap.add_argument('--symbol', default='EURUSD')
    ap.add_argument('--src', default='M30')
    ap.add_argument('--targets', default='H1,H4,D1,W1')
    a = ap.parse_args()
    if a.validate:
        sys.exit(0 if validate() else 1)
    build(a.symbol, a.src, [t.strip() for t in a.targets.split(',') if t.strip()])
