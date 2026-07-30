# -*- coding: utf-8 -*-
"""
ابزارِ نقشهٔ **دست‌یافتنی‌بودنِ سد** (Barrier Reachability Map)
==============================================================

پرسشِ این ابزار **یک** چیز است، و آن چیز تا این نشست هرگز در پروژه پرسیده
نشده بود:

    «سدی که روی `k × ATR` گذاشته‌ام، در `hold` کندلِ موجود، **اصلاً**
      قابلِ لمس شدن هست؟»

چرا این پرسش لازم شد — ردِ پای تجربی
-------------------------------------
در `S349` (انتقالِ صفر-پارامتریِ هندسهٔ طلا-D1 به یورو) یک تناقضِ ظاهری
پیدا شد که رهایش نکردم:

    EURUSD-D1 :  WR = ۴۳.۷۰٪   ولی   سربه‌سرِ مقاوم = ۲۴.۲٪
                 ⇒ باید سودِ درشتی می‌داد؛ اما exp = **−۷.۱۲ pip**

تفکیکِ دلیلِ خروج، علت را لو داد: زیرِ هندسهٔ منجمدِ
`sl_k=1.618, rr=3.236, hold=8`، سهمِ «TP خورد» روی یورو **۰.۸٪** بود و روی
طلا **۸.۳٪**. یعنی حدِ سود عملاً **لمس نمی‌شد**؛ نرخِ بردِ ۴۳.۷٪ تقریباً
تمامش از خروج‌های *زمانیِ* کوچک ساخته شده بود، نه از رسیدن به هدف.

قانونِ ریاضیِ پشتِ ماجرا — **قانونِ جذر**
-----------------------------------------
برای پیمایشِ تصادفیِ با انحرافِ معیارِ σ در هر کندل، زمانِ موردِ انتظار تا
نخستین لمسِ سطحِ `d` فاصله، متناسب است با `(d/σ)²` (زمانِ برخوردِ حرکتِ
براونی). اگر SL و TP را بر حسبِ ATR بگذاریم (`ATR ≈ σ` در هر کندل):

    زمانِ لمسِ SL ~ k_sl²          ,     زمانِ لمسِ TP ~ (k_sl · rr)²

پس با `sl_k=1.618` و `rr=3.236` و `hold=8`:

    SL : k² = 2.62  ≤ 8   ⇒ **در دسترس**
    TP : k² = 27.42 >  8   ⇒ **غیرقابلِ دسترس**
    عدمِ تقارنِ دسترسی = rr² = ۱۰.۵ برابر، **علیهِ** لایه

⇒ نتیجهٔ روش‌شناختیِ سنگین: از جایی به بعد، **بالا بردنِ `rr` یک `no-op`
است**. TP آن‌قدر دور می‌رود که دیگر بخشی از سیستم نیست، و معامله در عمل به
یک معاملهٔ «خروجِ زمانیِ محض» تبدیل می‌شود. این توضیح می‌دهد که چرا جاروبِ
`S348` بهینه را دقیقاً روی **لبهٔ گرید** (`rr=3.236`) یافت: نه به این دلیل
که آن‌جا بهترین است، بلکه به این دلیل که از یک آستانه به بعد `rr` هیچ‌کاری
نمی‌کند و مقایسه بی‌معنا می‌شود.

قانونِ قفلِ سه‌گانه — یافتهٔ اصلی
----------------------------------
سه پارامتری که پروژه همیشه **مستقل** می‌پنداشت، در واقع به هم قفل‌اند:

    hold ≥ (k_sl · rr)²        ⟺        rr_max = √hold / k_sl

هر ترکیبی که این نامعادله را نقض کند، **ادعای هندسیِ کاذب** دارد: روی کاغذ
`rr=3.236` است، در عمل یک استراتژیِ نگه‌داری تا انقضا.

چرا اندازه‌گیریِ تجربی هم لازم است (و ابزار همین را می‌کند)
--------------------------------------------------------------
`k²` از فرضِ پیمایشِ تصادفیِ خالص می‌آید. بازارِ واقعی نه خالصاً تصادفی است
(خودهم‌بستگی، خوشه‌بندیِ نوسان، رانش) و نه ATR دقیقاً σ است. پس این ابزار
عددِ نظری را **جای** اندازه‌گیری نمی‌گذارد؛ هر دو را کنارِ هم می‌گذارد و
شکاف را گزارش می‌کند.

⚠️ نکتهٔ طراحیِ کلیدی — **مستقل از استراتژی**
    این ابزار هیچ سیگنالی را صدا نمی‌زند. از نقاطِ ورودِ **تصادفیِ**
    بذرگذاری‌شده استفاده می‌کند، چون پرسشِ «آیا این سد در این افق قابلِ لمس
    است؟» خاصیتِ **سریِ قیمت** است، نه خاصیتِ لایه. اگر با ورودی‌های یک
    لایهٔ خاص می‌سنجیدیم، نتیجه به آن لایه آلوده می‌شد و دیگر به‌عنوان یک
    قانونِ عمومی قابلِ استفاده نبود.

    و هیچ هزینه‌ای (اسپرد/اسلیپیج) در این ابزار وارد نمی‌شود — عمداً.
    دست‌یافتنی‌بودن پرسشی **هندسی/زمانی** است؛ هزینه در
    `tools/rr_feasibility.py` سنجیده می‌شود. مخلوط کردنِ این دو، همان
    خطای بُعدی است که این نشست سه بار تکرارش را دید.

خروجی
------
برای هر کارت و هر `k`:
    P_touch(k | hold)  = احتمالِ لمسِ ±k·ATR در `hold` کندلِ نخست
    med_bars(k)        = میانهٔ کندل‌های لازم تا نخستین لمس (تجربی)
    k²                 = پیش‌بینیِ نظریِ قانونِ جذر
سپس برای هندسهٔ منجمدِ S348/S349، عدمِ تقارنِ دسترسیِ SL/TP گزارش می‌شود.

اجرا
-----
    PYTHONPATH=. python tools/reachability_map.py
    PYTHONPATH=. python tools/reachability_map.py --hold 8 --n-sample 4000
"""

import argparse

import numpy as np
import pandas as pd

from engine import scalp_engine as se


# کارت‌ها — شاملِ چهار کارتِ یورو که تا این نشست در هیچ فهرستی نبودند
CARDS = {
    'XAUUSD-M5':  ('XAUUSD', 'data/XAUUSD_M5.csv'),
    'XAUUSD-M15': ('XAUUSD', 'data/XAUUSD_M15.csv'),
    'XAUUSD-M30': ('XAUUSD', 'data/XAUUSD_M30.csv'),
    'XAUUSD-H1':  ('XAUUSD', 'data/XAUUSD_H1.csv'),
    'XAUUSD-H4':  ('XAUUSD', 'data/XAUUSD_H4.csv'),
    'XAUUSD-D1':  ('XAUUSD', 'data/XAUUSD_D1.csv'),
    'XAUUSD-W1':  ('XAUUSD', 'data/XAUUSD_W1.csv'),
    'EURUSD-M1':  ('EURUSD', 'data/EURUSD_M1.csv'),
    'EURUSD-M5':  ('EURUSD', 'data/EURUSD_M5.csv'),
    'EURUSD-M15': ('EURUSD', 'data/EURUSD_M15.csv'),
    'EURUSD-M30': ('EURUSD', 'data/EURUSD_M30.csv'),
    'EURUSD-H1':  ('EURUSD', 'data/EURUSD_H1.csv'),
    'EURUSD-H4':  ('EURUSD', 'data/EURUSD_H4.csv'),
    'EURUSD-D1':  ('EURUSD', 'data/EURUSD_D1.csv'),
    'EURUSD-W1':  ('EURUSD', 'data/EURUSD_W1.csv'),
}

# هندسهٔ منجمدِ S348/S349 — همان که این کشف را برانگیخت
FROZEN = dict(sl_k=1.618, rr=3.236, hold=8)

# شبکهٔ k — فیبوناچی‌وار، نه اعدادِ رند (اشتباهِ رایجِ #۷)
K_GRID = (0.618, 1.0, 1.618, 2.058, 2.618, 3.236, 4.236, 5.236)

ATR_P = 21          # عیناً همان دوره‌ای که موتور استفاده می‌کند
SEED = 20260730
MAX_H = 64          # بیشینهٔ افقی که جست‌وجو می‌شود


def atr(df, p=ATR_P):
    """ATR کلاسیک (میانگینِ سادهٔ محدودهٔ واقعی) — بر حسبِ **واحدِ قیمت**."""
    h, l, c = df['high'].values, df['low'].values, df['close'].values
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).rolling(p).mean().values


def first_touch(df, a, k_grid, n_sample, max_h, rng):
    """میانهٔ زمانِ نخستین لمس و احتمالِ لمس، برای هر k.

    از ورودی‌های **تصادفی** استفاده می‌کند: پرسش خاصیتِ سری است نه لایه.
    لمس دوطرفه است (بالا یا پایین) — چون در یک براکتِ واقعی هم سد در هر دو
    جهت وجود دارد و پرسشِ «چند کندل تا لمس» بی‌جهت است.
    """
    hi, lo, cl = df['high'].values, df['low'].values, df['close'].values
    n = len(df)
    warm = ATR_P + 5
    hi_lim = n - max_h - 1
    if hi_lim <= warm:
        return None
    idx = rng.choice(np.arange(warm, hi_lim), size=min(n_sample, hi_lim - warm),
                     replace=False)
    idx = idx[np.isfinite(a[idx]) & (a[idx] > 0)]
    if len(idx) < 100:
        return None

    # پنجرهٔ آیندهٔ هر ورود: شکلِ (M, max_h)
    off = np.arange(1, max_h + 1)
    win = idx[:, None] + off[None, :]
    fwd_hi = hi[win]
    fwd_lo = lo[win]
    entry = cl[idx][:, None]
    a_e = a[idx][:, None]

    # بیشینه/کمینهٔ تجمعی ⇒ «آیا تا کندلِ j لمس شده؟»
    run_max = np.maximum.accumulate(fwd_hi, axis=1)
    run_min = np.minimum.accumulate(fwd_lo, axis=1)
    up_excursion = (run_max - entry) / a_e         # بر حسبِ ATR
    dn_excursion = (entry - run_min) / a_e

    out = {}
    for k in k_grid:
        touched = (up_excursion >= k) | (dn_excursion >= k)   # (M, max_h)
        ever = touched[:, -1]
        # نخستین ستونی که True شده
        first = np.argmax(touched, axis=1) + 1
        first = np.where(ever, first, np.nan)
        out[k] = dict(
            med=float(np.nanmedian(first)) if np.any(ever) else float('nan'),
            p_at=[float(touched[:, min(h, max_h) - 1].mean())
                  for h in (5, 8, 13, 21, 34, 55)],
            ever=float(ever.mean()),
        )
    return out, len(idx)


def main(hold, n_sample):
    rng = np.random.default_rng(SEED)
    print('=' * 108)
    print(f'BARRIER REACHABILITY MAP   ·   ATR{ATR_P}   ·   random seeded entries'
          f'   ·   hold under test = {hold} bars')
    print('=' * 108)
    print('P_touch(k | H) = probability that price touches ±k·ATR within H bars.'
          '  A barrier with low P_touch is DECORATIVE.')
    print()

    holds = (5, 8, 13, 21, 34, 55)
    hdr = ''.join(f'{"H=" + str(h):>8}' for h in holds)
    frozen_rows = {}

    for card, (asset, path) in CARDS.items():
        try:
            df = se.load_data(path)
        except Exception as e:                       # noqa: BLE001
            print(f'{card:<12} !! cannot load: {e}')
            continue
        a = atr(df)
        r = first_touch(df, a, K_GRID, n_sample, MAX_H, rng)
        if r is None:
            print(f'{card:<12} !! too few bars for a {MAX_H}-bar forward window')
            continue
        res, m = r
        print(f'--- {card}   (bars={len(df):,}  sampled entries={m:,}) ---')
        print(f'{"k":>7}{"k² (theory)":>13}{"med bars":>10}{hdr}')
        for k in K_GRID:
            d = res[k]
            cells = ''.join(f'{p * 100:>7.1f}%' for p in d['p_at'])
            med = d['med']
            med_s = f'{med:>10.1f}' if np.isfinite(med) else f'{">64":>10}'
            print(f'{k:>7.3f}{k * k:>13.2f}{med_s}{cells}')
        # ردیفِ هندسهٔ منجمد
        # ⚠️ رفعِ باگِ تطبیقِ اعشاری: `1.618 × 3.236 = 5.235848…` است، نه
        #    دقیقاً `5.236`ی که در گرید هست. جست‌وجوی عضویتِ `in` روی float
        #    شکست می‌خورد و `P_touch(TP)` را `nan` می‌کرد — یعنی همان عددی که
        #    کلِ کشف را اثبات می‌کند در سکوت گم می‌شد. **نزدیک‌ترین** k را
        #    برمی‌داریم و اگر فاصله بیش از رزولوشنِ گرید بود، صریح اعتراض.
        def _nearest(kv):
            kk = min(K_GRID, key=lambda g: abs(g - kv))
            return kk if abs(kk - kv) < 0.02 else None

        k_sl = FROZEN['sl_k']
        k_tp = FROZEN['sl_k'] * FROZEN['rr']
        hi_ = holds.index(hold) if hold in holds else 1
        ksl_g, ktp_g = _nearest(k_sl), _nearest(k_tp)
        p_sl = res[ksl_g]['p_at'][hi_] if ksl_g is not None else float('nan')
        p_tp = res[ktp_g]['p_at'][hi_] if ktp_g is not None else float('nan')
        frozen_rows[card] = (p_sl, p_tp)
        print(f'   FROZEN S348/S349 geometry @H={hold}:  '
              f'P_touch(SL={k_sl:.3f}ATR)={p_sl * 100:5.1f}%   '
              f'P_touch(TP={k_tp:.3f}ATR)={p_tp * 100:5.1f}%   '
              f'ratio={p_sl / p_tp if p_tp > 0 else float("inf"):6.1f}x against')
        print()

    # ================= جمع‌بندیِ قانونِ قفلِ سه‌گانه =================
    print('=' * 108)
    print('THE TRIPLE-LOCK LAW      hold ≥ (k_sl · rr)²      ⟺      rr_max = √hold / k_sl')
    print('=' * 108)
    print(f'{"hold":>6}' + ''.join(f'{"k_sl=" + f"{k:.3f}":>14}' for k in
                                   (0.618, 1.0, 1.618, 2.058)))
    print('       ' + '  (max rr that keeps the TP reachable)')
    for h in holds:
        row = ''.join(f'{np.sqrt(h) / k:>14.2f}' for k in
                      (0.618, 1.0, 1.618, 2.058))
        print(f'{h:>6}{row}')
    print()
    k_sl, rr, h = FROZEN['sl_k'], FROZEN['rr'], FROZEN['hold']
    print(f'  S348/S349 used sl_k={k_sl}, rr={rr}, hold={h}:')
    print(f'    rr_max allowed by reachability = √{h}/{k_sl} = '
          f'{np.sqrt(h) / k_sl:.2f}      (used {rr} ⇒ '
          f'{rr / (np.sqrt(h) / k_sl):.2f}× OVER the ceiling)')
    print(f'    hold required by the chosen rr  = ({k_sl}·{rr})² = '
          f'{(k_sl * rr) ** 2:.1f} bars   (had {h} ⇒ short by '
          f'{(k_sl * rr) ** 2 - h:.1f} bars)')
    print()
    print('  ⇒ the take-profit was DECORATIVE: the layer was, in effect, a')
    print('    hold-to-expiry strategy wearing a bracket costume. Any claim')
    print('    about "the optimal RR" measured under this configuration is')
    print('    a claim about time-exit drift harvesting, NOT about the target.')
    print()
    print('  MEASURED CONFIRMATION (P_touch of the two barriers, per card):')
    for card, (p_sl, p_tp) in frozen_rows.items():
        flag = '  <-- TP essentially never touched' if p_tp < 0.10 else ''
        print(f'    {card:<12} SL={p_sl * 100:5.1f}%   TP={p_tp * 100:5.1f}%{flag}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--hold', type=int, default=FROZEN['hold'])
    ap.add_argument('--n-sample', type=int, default=4000)
    args = ap.parse_args()
    main(args.hold, args.n_sample)
