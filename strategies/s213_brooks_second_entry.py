# -*- coding: utf-8 -*-
"""
S213 — Al Brooks «Second Entries» (فصلِ ۱۰ کتابِ Trading Price Action: TRENDS)
================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

مفهومِ محوریِ فصلِ ۱۰ (قاعدهٔ زمان‌بندیِ ورود — نه هندسهٔ کندلِ جدید):
  «A second entry is almost always more likely to result in a profitable trade than
   a first entry.» بازار معمولاً برای برگشت به **دو** تلاش نیاز دارد.

  قاعدهٔ momentum-guard (هستهٔ آزمون): پس از یک اسپایکِ قوی (≈۴ کندلِ trend پیاپی یا
  ۲–۳ کندلِ بزرگ)، **اولین** تلاشِ برگشتِ ضدِروند را نگیر؛ بگذار روند ۱–۲ کندل ادامه
  یابد، سپس روی **دومین** تلاشِ برگشت وارد شو.

  فیلترِ good-fill: «Most good second entries are at the same price or worse.» ⇒ اگر
  تریگرِ ورودِ دوم قیمتِ *مساعدتر* از تلاشِ اول بدهد، تله است ⇒ رد.

ترجمهٔ بک‌تست‌پذیر (همه causal، shift(1) ⇒ ورودِ next-open):
  --- setupِ SHORT (fade در روندِ صعودیِ قوی؛ جهتِ موردِنیازِ پرتفوی) ---
  1) اسپایک: در پنجرهٔ اخیر ≥`spk` از آخرین کندل‌ها bull-trend-bar (close>open با بدنهٔ
     ≥ نصفِ range) ⇒ momentum صعودیِ بالا.
  2) تلاشِ برگشتِ اول = نخستین bear-signal (bear-close که low کندلِ قبل را می‌شکند).
     این را نمی‌گیریم؛ فقط علامت می‌زنیم.
  3) پس از تلاشِ اول، اگر بازار ۱–۲ کندل رالی کند و سپس **دومین** bear-signal رخ دهد
     در همان ناحیه (طیِ `gap` کندل) ⇒ SHORT.
  4) فیلترِ good-fill: قیمتِ ورودِ دوم (تریگر) نباید *بهتر* (بالاتر برای SHORT) از تلاشِ
     اول باشد؛ باید same-or-worse (≤) باشد.
  --- setupِ LONG قرینه (در روندِ نزولیِ قوی) ---

مسیرِ آزمون (طبقِ درسِ فصل‌های قبل):
  (الف) لبهٔ مستقلِ دو-جهته روی همهٔ TFها.
  (ب) طبقِ قانونِ همپوشانیِ اجباری، اگر لبهٔ مستقل ضعیف/هم‌پوشان بود، second-entry
      به‌عنوان فیلترِ تأیید روی لایه‌های موجود (فایلِ جدا: s213c).

گیتِ سختِ ۴-گانه: net>0 + هر دو نیمه + walk-forward(۴/۴) + WR≥40 + n≥30.
چارچوبِ load/sim/stats/halves هم‌ترازِ S186/S212 از ماژولِ پایهٔ s172.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S          # load/lastn/sim/stats/halves + cost-calibrated ASSETS
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0


# ============================================================================
#  سیگنالِ second-entry — همه causal، خروجی shift(1) شده (ورودِ next-open)
# ============================================================================
def second_entry_signals(df, side, ema_fast, ema_slow, spk, gap, good_fill=True):
    """سیگنالِ ورودِ *دوم* برگشت پس از اسپایکِ هم‌جهت.

    side='short' ⇒ fade یک روندِ صعودیِ قوی (SHORT روی تلاشِ دومِ برگشت).
    side='long'  ⇒ fade یک روندِ نزولیِ قوی (LONG روی تلاشِ دومِ برگشت).

    spk = حداقل تعدادِ کندلِ trend هم‌جهت در پنجرهٔ اسپایک (momentum-guard).
    gap = حداکثر فاصلهٔ کندلی بینِ تلاشِ اول و دوم.
    good_fill = اعمالِ فیلترِ «same price or worse» روی ورودِ دوم.
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    rng = np.maximum(h - l, 1e-9)
    body = c - o
    big = np.abs(body) >= 0.5 * rng          # کندلِ trend (بدنهٔ ≥ نصفِ range)

    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()

    sig = np.zeros(n, bool)
    trig_price = np.full(n, np.nan)          # قیمتِ تریگرِ ورود (برای فیلترِ good-fill)

    if side == 'short':
        bull_bar = (body > 0) & big
        # اسکنِ رو به جلو: در هر کندلِ i که «اسپایکِ صعودی» تازه تمام شده،
        # به‌دنبالِ تلاشِ برگشتِ اول سپس دوم در پنجرهٔ gap کندلِ بعدی می‌گردیم.
        i = spk + 1
        while i < n - gap - 2:
            # اسپایک = spk کندلِ اخیرِ bull-trend-bar پیاپی (تا i، بسته‌شده) + روندِ صعودی
            win = bull_bar[i - spk + 1:i + 1]
            if win.sum() < spk or not (ef[i] > es[i]):
                i += 1
                continue
            # از کندلِ i+1 به بعد، دنبالِ تلاشِ برگشتِ اول (bear-close که low قبل را شکسته)
            first = -1
            for j in range(i + 1, min(i + 1 + gap, n)):
                if c[j] < o[j] and l[j] < l[j - 1]:
                    first = j
                    break
            if first < 0:
                i += 1
                continue
            # پس از first باید یک رالی (higher-high نسبت به first) و سپس تلاشِ دوم بیاید
            second = -1
            for j in range(first + 1, min(first + 1 + gap, n)):
                if h[j] > h[first] and c[j] < o[j] and l[j] < l[j - 1]:
                    second = j
                    break
            if second < 0:
                i = first + 1
                continue
            # فیلترِ good-fill: تریگرِ SHORT (شکستِ low[second]) نباید بهتر (بالاتر) از اول باشد
            if good_fill and (l[second] > l[first]):
                i = second + 1
                continue
            # سیگنال روی کندلِ second صادر (ورود در open کندلِ بعد پس از shift)
            sig[second] = True
            trig_price[second] = l[second]
            i = second + 1
    else:  # long — روندِ نزولیِ قوی، LONG روی تلاشِ دومِ برگشتِ صعودی
        bear_bar = (body < 0) & big
        i = spk + 1
        while i < n - gap - 2:
            win = bear_bar[i - spk + 1:i + 1]
            if win.sum() < spk or not (ef[i] < es[i]):
                i += 1
                continue
            first = -1
            for j in range(i + 1, min(i + 1 + gap, n)):
                if c[j] > o[j] and h[j] > h[j - 1]:
                    first = j
                    break
            if first < 0:
                i += 1
                continue
            second = -1
            for j in range(first + 1, min(first + 1 + gap, n)):
                if l[j] < l[first] and c[j] > o[j] and h[j] > h[j - 1]:
                    second = j
                    break
            if second < 0:
                i = first + 1
                continue
            if good_fill and (h[second] < h[first]):
                i = second + 1
                continue
            sig[second] = True
            trig_price[second] = h[second]
            i = second + 1

    # shift(1) ⇒ همه‌چیز تا کندلِ سیگنال بسته‌شده؛ ورود در open کندلِ بعد
    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def evaluate(df, asset, sig, side, sl, tp, mh):
    z = np.zeros(len(df), bool)
    if side == 'long':
        tr = S.sim(df, sig, z, sl, tp, mh, asset)
    else:
        tr = S.sim(df, z, sig, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if r is None or r['n'] < 30:
        return None
    base = dict(asset=asset, side=side, sl=sl, tp=tp, mh=mh,
                net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                pf=(round(r['pf'], 3) if r['pf'] != float('inf') else 999.0),
                h1=None, h2=None, wf=[], wf_ok=False, both_ok=False, accepted=False)
    if r['net'] <= 0 or r['wr'] < WR_FLOOR:
        return base
    hv = S.halves(df, sig if side == 'long' else z, z if side == 'long' else sig, sl, tp, mh, asset)
    wf = []
    n = len(df)
    for k in range(4):
        a = int(n * k / 4); b = int(n * (k + 1) / 4)
        sub = df.iloc[a:b].reset_index(drop=True)
        sg = sig[a:b]
        z2 = np.zeros(len(sub), bool)
        if sg.sum() < 6:
            wf.append((0.0, 0.0, 0)); continue
        t2 = S.sim(sub, sg if side == 'long' else z2, z2 if side == 'long' else sg, sl, tp, mh, asset)
        if t2 is None or len(t2) == 0:
            wf.append((0.0, 0.0, 0)); continue
        s2 = S.stats(t2, asset)
        wf.append((round(s2['net'], 1), round(s2['wr'], 1), int(s2['n'])))
    wf_ok = all(w[0] > 0 for w in wf)
    both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
    acc = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok and r['n'] >= 30)
    base.update(h1=(round(hv['h1'], 1) if hv else None),
                h2=(round(hv['h2'], 1) if hv else None),
                wf=wf, wf_ok=wf_ok, both_ok=both_ok, accepted=acc)
    return base


def main():
    print("=" * 100)
    print("S213 — Al Brooks «Second Entries» (فصلِ ۱۰): ورودِ دومِ برگشت پس از اسپایک + momentum-guard")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    # قانونِ مولتی‌تایم‌فریم: از XAUUSD شروع (M1 طلا موجود نیست ⇒ M5..H1)، سپس EURUSD.
    TFS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1',
           'EURUSD_M1', 'EURUSD_M5', 'EURUSD_M15', 'EURUSD_M30']

    SL_TP = [(150, 225), (200, 300), (250, 375), (300, 450)]
    MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24}
    EMA = [(10, 30), (20, 50)]
    SPK = [3, 4]          # حداقل کندلِ اسپایک (momentum-guard)
    GAP = [4, 6]          # حداکثر فاصلهٔ تلاشِ اول تا دوم
    SIDES = ['short', 'long']

    all_rows = []
    accepted = []
    for tf in TFS:
        asset = tf.split('_')[0]; tag = tf.split('_')[1]
        mh = MH.get(tag, 48)
        try:
            df = S.lastn(S.load(tf), y=4)
        except Exception as e:
            print(f"[skip] {tf}: {e}"); continue
        print(f"\n{'─'*90}\n### {tf}  (n={len(df)}, mh={mh})", flush=True)

        for side in SIDES:
            for (ef, es) in EMA:
                for spk in SPK:
                    for gap in GAP:
                        sig = second_entry_signals(df, side, ef, es, spk, gap, good_fill=True)
                        ns = int(sig.sum())
                        if ns < 30:
                            continue
                        for sl, tp in SL_TP:
                            r = evaluate(df, asset, sig, side, sl, tp, mh)
                            if r is None:
                                continue
                            row = dict(tf=tf, side=side, ema=f"{ef}/{es}", spk=spk, gap=gap,
                                       sl=sl, tp=tp, net=r['net'], wr=r['wr'], n=r['n'],
                                       pf=r['pf'], wf=r['wf'], wf_ok=r['wf_ok'],
                                       both_ok=r['both_ok'], accepted=r['accepted'])
                            all_rows.append(row)
                            if r['accepted']:
                                accepted.append(row)
                                print(f"  ✓ {side} ema{ef}/{es} spk{spk} gap{gap} SL{sl}/TP{tp}: "
                                      f"net=${r['net']:+,.0f} WR{r['wr']} n{r['n']} PF{r['pf']} "
                                      f"WF{r['wf']}", flush=True)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s213_second_entry.json'), 'w') as f:
        json.dump(all_rows, f, indent=1)
    print(f"\n{'='*100}\nمجموع ردیف: {len(all_rows)} | گیت-پاس: {len(accepted)}")
    accepted.sort(key=lambda r: -r['net'])
    for r in accepted[:20]:
        print(f"  {r['tf']} {r['side']} ema{r['ema']} spk{r['spk']} gap{r['gap']} "
              f"SL{r['sl']}/TP{r['tp']}: net=${r['net']:+,.0f} WR{r['wr']} n{r['n']}")
    print("saved: results/_s213_second_entry.json")


if __name__ == '__main__':
    main()
