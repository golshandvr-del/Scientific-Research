# -*- coding: utf-8 -*-
"""کالیبراسیونِ آستانهٔ نسبتِ استقلال — **رفعِ عددِ رندِ دلبخواهیِ خودم**

## مسئله
در `tools/orthogonality_probe.py` من آستانهٔ `ratio < 0.25` را برای پرچمِ
«تضادِ ساختاری» گذاشتم. آن عدد **هیچ مبنای تجربی نداشت** — یک عددِ رندِ
دلبخواه بود، یعنی مصداقِ مستقیمِ **اشتباهِ رایجِ شمارهٔ ۷** پروژه
(«استفاده از اعدادِ رند و ساده... در حالی که مقدارِ واقعیِ نجات‌دهنده
۱۷۰-۱۳۵ و.. باشد»).

و این بی‌مبنایی **پیامدِ عملی** داشت: نامزدِ `inside_VA` روی چهار کارت
نسبت‌های `0.234, 0.156, 0.253, 0.208` گرفت — یعنی دقیقاً در همان ناحیه‌ای
خوشه کرد که آستانهٔ کالیبره‌نشدهٔ من **تصمیم‌گیرنده** است. سه کارت رد، یک
کارت قبول. حکمِ چنین نامزدی نباید به یک عددِ حدسی وابسته باشد.

## روشِ کالیبراسیون: توزیعِ صفرِ تجربیِ نسبت
آستانه باید از **توزیعِ خودِ کمیت** بیاید، نه از سلیقهٔ من. پس:

۱) یک **استخرِ مرجعِ بزرگ** از قیدهای بولینِ متنوع از بانکِ اندیکاتورِ پروژه
   ساخته می‌شود (بیش از ۴۰۰ اندیکاتور موجود است — قانونِ جعبه‌ابزار).
۲) نسبتِ استقلالِ **همهٔ جفت‌ها** محاسبه می‌شود ⇒ توزیعِ تجربیِ `ratio`.
۳) آستانه از **چارک‌های همان توزیع** گرفته می‌شود، نه از عددِ رند:
      - `q05` توزیع ⇒ «۵٪ متضادترین جفت‌ها» = پرچمِ تضاد
      - `q95` توزیع ⇒ «۵٪ افزون‌ترین جفت‌ها» = پرچمِ افزونگی

این همان روشی است که پروژه قبلاً در `S376` برای چارکِ فاصله به کار برد
(«چارک ∈ {0.30, 0.45, 0.60, 0.75} از **توزیعِ خودِ فاصله**») — پس سازگار با
رویهٔ موجود است، نه اختراعِ نو.

## نکتهٔ حیاتیِ روش‌شناختی: نسبت به فراوانیِ حاشیه‌ای وابسته است
دو قیدِ کم‌فراوان (`P≈0.03`) حتی اگر کاملاً مستقل باشند، نسبتِ نمونه‌ایِ
پرنویزی می‌دهند. پس توزیع **به‌تفکیکِ بازهٔ فراوانیِ حاشیه‌ای** هم گزارش
می‌شود، تا آستانه برای قیدهای نادر و فراوان یکسان تحمیل نشود.

## هزینهٔ درجهٔ آزادی
هیچ WR، سود، p-value یا معامله‌ای تولید نمی‌شود ⇒ **صفر**. این ابزار فقط
هندسهٔ فضایِ حالتِ بانکِ اندیکاتور را توصیف می‌کند.

## مرزِ صداقت
این ابزار **آستانه را کالیبره می‌کند، نه نامزد را تأیید**. اگر پس از
کالیبراسیون `inside_VA` پاس شد، این فقط یعنی «نمونه را ساختاری نمی‌کشد» —
**نه** اینکه لبه‌ای دارد.
"""
import sys, os, json, itertools

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import pandas as pd

from engine import scalp_engine as SE
from engine import indicator_bank as ib

OUT = 'results/_audit_orthogonality'
os.makedirs(OUT, exist_ok=True)


def build_reference_pool(df, max_inds=60, seed=20260804):
    """استخرِ مرجع: قیدهای بولین از اندیکاتورهای بانک، در چارک‌های خودشان.

    برای هر اندیکاتورِ عددی، دو قید ساخته می‌شود: بالای چارکِ سومِ **خودش** و
    زیرِ چارکِ اولِ **خودش**. آستانه از توزیعِ خودِ اندیکاتور می‌آید ⇒ هیچ
    عددِ رندِ تحمیلی‌ای وارد نمی‌شود.
    """
    rng = np.random.default_rng(seed)
    names = sorted(ib.list_indicators()) if hasattr(ib, 'list_indicators') else None
    if not names:
        # fallback: کشفِ نام‌ها از رجیستریِ بانک
        names = sorted(getattr(ib, 'REGISTRY', {}).keys())
    if not names:
        raise RuntimeError('cannot enumerate indicator bank')

    if len(names) > max_inds:
        idx = rng.choice(len(names), size=max_inds, replace=False)
        names = [names[i] for i in sorted(idx)]

    pool = []
    for nm in names:
        try:
            s = ib.compute(nm, df)
        except Exception:
            continue
        v = np.asarray(s.values, dtype=np.float64)
        fin = np.isfinite(v)
        if fin.sum() < 5000:
            continue
        if len(np.unique(v[fin])) < 20:      # قیدِ شبه‌ثابت/بولین ⇒ رد
            continue
        q1, q3 = np.nanquantile(v[fin], [0.25, 0.75])
        if not np.isfinite(q1) or not np.isfinite(q3) or q3 <= q1:
            continue
        pool.append((f'{nm}>q75', fin & (v > q3)))
        pool.append((f'{nm}<q25', fin & (v < q1)))
    return pool


def ratio(A, B):
    pA, pB = A.mean(), B.mean()
    pAB = (A & B).mean()
    ind = pA * pB
    return (pAB / ind if ind > 0 else np.nan), pA, pB


def main():
    card = sys.argv[1] if len(sys.argv) > 1 else 'XAUUSD_M30'
    pair, tf = card.split('_')
    df = SE.load_data(f'data/{pair}_{tf}.csv')
    print(f'{card}  bars={len(df):,}')

    pool = build_reference_pool(df)
    print(f'reference pool: {len(pool)} boolean constraints '
          f'from {len(pool)//2} indicators')

    ratios, marg = [], []
    labels = []
    for (na, A), (nb, B) in itertools.combinations(pool, 2):
        # جفت‌های برخاسته از یک اندیکاتور حذف می‌شوند (تضادِ تعریفی، نه ساختاری)
        if na.split('>')[0].split('<')[0] == nb.split('>')[0].split('<')[0]:
            continue
        r, pA, pB = ratio(A, B)
        if not np.isfinite(r) or r <= 0:
            continue
        ratios.append(r)
        marg.append(min(pA, pB))
        labels.append((na, nb))

    ratios = np.array(ratios); marg = np.array(marg)
    print(f'\npairs measured: {len(ratios):,}')

    qs = [0.01, 0.02, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.98, 0.99]
    qv = np.nanquantile(ratios, qs)
    print('\n=== empirical null distribution of independence ratio ===')
    for q, v in zip(qs, qv):
        print(f'  q{int(q*100):02d} = {v:8.4f}')

    # به‌تفکیکِ فراوانیِ حاشیه‌ایِ کمینه — چون نسبتِ نمونه‌ای به آن وابسته است
    print('\n=== same, split by min marginal frequency ===')
    bands = [(0.0, 0.05), (0.05, 0.15), (0.15, 0.30), (0.30, 1.0)]
    band_out = []
    for lo, hi in bands:
        m = (marg >= lo) & (marg < hi)
        if m.sum() < 50:
            print(f'  min-marg [{lo:.2f},{hi:.2f}): n={m.sum()} (too few)')
            continue
        v = np.nanquantile(ratios[m], [0.05, 0.50, 0.95])
        print(f'  min-marg [{lo:.2f},{hi:.2f}): n={m.sum():6,d}  '
              f'q05={v[0]:7.4f}  median={v[1]:7.4f}  q95={v[2]:7.4f}')
        band_out.append(dict(lo=lo, hi=hi, n=int(m.sum()),
                             q05=round(float(v[0]), 4),
                             median=round(float(v[1]), 4),
                             q95=round(float(v[2]), 4)))

    # مقایسهٔ آستانهٔ دلبخواهیِ من با چارک‌های تجربی
    print('\n=== my arbitrary 0.25 vs empirical quantiles ===')
    frac_below = float((ratios < 0.25).mean())
    print(f'  fraction of ALL pairs with ratio<0.25 : {100*frac_below:.2f}%')
    print(f'  empirical q05 = {qv[2]:.4f}   (my 0.25 flags '
          f'{"MORE" if 0.25 > qv[2] else "FEWER"} pairs than a 5% tail)')

    out = dict(card=card, bars=int(len(df)),
               pool_size=len(pool), pairs=int(len(ratios)),
               quantiles={f'q{int(q*100):02d}': round(float(v), 4)
                          for q, v in zip(qs, qv)},
               by_marginal_band=band_out,
               my_arbitrary_threshold=0.25,
               fraction_below_my_threshold=round(frac_below, 5))
    with open(os.path.join(OUT, f'threshold_calibration_{card}.json'), 'w') as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
    print(f'\nsaved → {OUT}/threshold_calibration_{card}.json')


if __name__ == '__main__':
    main()
