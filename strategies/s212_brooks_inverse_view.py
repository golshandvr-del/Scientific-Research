# -*- coding: utf-8 -*-
"""
S212 — Al Brooks «Exchange-Traded Funds and Inverse Charts» (فصلِ ۹): «دیدِ معکوس»
================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

مفهومِ محوریِ فصلِ ۹ (تنها ایدهٔ قابلِ‌آزمونِ فصل — فصل قاعدهٔ ورودِ مستقل نمی‌دهد):
  «Inverse-Chart Cross-Check» — اگر یک bull-flag/pullback می‌بینی ولی چیزی درست نیست،
  به نمودارِ معکوس نگاه کن؛ ممکن است همان الگو یک "rounding bottom" باشد ⇒ ورود نکن،
  منتظرِ price-action بیشتر بمان. یعنی یک ستاپِ *واقعی* از هر دو منظر (مستقیم/معکوس)
  همان تصمیم را می‌دهد؛ اگر منظرِ معکوس تصمیمِ مبهم/متضاد بدهد ⇒ تله ⇒ رد.

ترجمهٔ علمیِ بک‌تست‌پذیر (همه causal، shift(1) ⇒ ورودِ next-open):
  ما ETF معکوس نداریم، اما تز = «عدم‌تقارنِ ساختارِ اصلاح در دو منظر». آینه‌کردنِ خطیِ
  قیمت (inv = -price) شتابِ نزولیِ اصلاح را به شتابِ صعودی قرینه می‌کند؛ پس معیارِ عملیاتی
  = «آیا اصلاح یک شکستِ خطی/تند است (bear-flag قوی در هر دو منظر) یا یک کف‌سازیِ محدب
  (rounding bottom در منظرِ معکوس)؟».

  اصلاحِ سالمِ pullback در روندِ صعودی: حرکتِ نزولیِ اصلاح **خطی/تند** (شتابِ ثابت).
  rounding-bottom: حرکتِ **محدب** ⇒ نیمهٔ دومِ اصلاح شتابِ نزولیِ کمتری از نیمهٔ اول دارد
  (در حالِ کف‌سازی). معیارِ عدم‌تقارن:
      leg = پنجرهٔ pullback (از سقفِ محلی تا کف)؛ آن را دو نیمه می‌کنیم.
      slope1 = شیبِ نیمهٔ اول، slope2 = شیبِ نیمهٔ دوم (هر دو منفی در اصلاحِ نزولی).
      convexity = slope1 - slope2  (اگر >0 ⇒ نیمهٔ دوم کندتر ⇒ rounding/محدب)
      asym = convexity نرمال‌شده به دامنهٔ اصلاح.
  فرضیهٔ اصلی (فیلترِ symmetry-confirm): ورودِ LONG تنها وقتی مجاز که asym ≤ thr
  (اصلاح خطی/تند = هر دو منظر همان تصمیم)؛ اگر asym > thr (rounding bottom) ⇒ رد.

مسیرِ آزمون (طبقِ درسِ فصل‌های قبل — این فصل قاعدهٔ ورودِ مستقل ندارد ⇒ اولویت با فیلتر):
  (الف) لبهٔ مستقل: ستاپِ pullback-LONG با symmetry-confirm (ثانوی؛ انتظارِ همپوشانیِ سنگین).
  (ب) فیلترِ symmetry-confirm روی لایه‌های مرزیِ زمان-محور (راهِ اولِ پروژه).

گیتِ سختِ ۴-گانه: net>0 + هر دو نیمه + walk-forward(۴/۴) + WR≥40 + n≥30.
چارچوبِ load/sim/stats/halves هم‌ترازِ S186 (سیب‌به‌سیب) از ماژولِ پایهٔ s172.
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
#  ساختارِ اصلاح (pullback) + معیارِ عدم‌تقارنِ «دیدِ معکوس» — همه causal
# ============================================================================
def inverse_view_asym(df, lb):
    """برای هر کندل، معیارِ عدم‌تقارنِ اصلاحِ اخیر (rounding-bottom detector).

    نگاه به پنجرهٔ `lb` کندلِ گذشته (shift(1) ⇒ فقط داده‌های بسته‌شده):
      - سقفِ محلی = argmax(high) در پنجره؛ کفِ محلی = argmin(low) پس از آن سقف.
      - legِ اصلاحی = از سقف تا کف. آن را دو نیمه می‌کنیم و شیبِ close هر نیمه را می‌گیریم.
      - convexity = slope1 - slope2 (نرمال به دامنهٔ اصلاح بر کندل).
        >0 ⇒ نیمهٔ دوم کندتر ⇒ محدب/rounding ⇒ در منظرِ معکوس "rounding bottom".
    خروجی: آرایهٔ asym (هرچه بزرگ‌تر ⇒ عدم‌تقارنِ بیشتر ⇒ ستاپِ مشکوک‌تر).
    """
    c = df['close'].to_numpy(); h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    asym = np.full(n, np.nan)
    for i in range(lb + 2, n):
        w_h = h[i - lb:i]         # پنجرهٔ بسته‌شده (تا i-1)
        w_l = l[i - lb:i]
        w_c = c[i - lb:i]
        pk = int(np.argmax(w_h))                      # سقفِ محلی
        if pk >= lb - 3:                              # سقف باید فضای اصلاح داشته باشد
            continue
        seg_l = w_l[pk:]
        tr = int(np.argmin(seg_l)) + pk               # کفِ پس از سقف
        if tr - pk < 4:                               # legِ اصلاحی باید ≥۴ کندل باشد
            continue
        leg = w_c[pk:tr + 1]
        m = len(leg)
        half = m // 2
        x1 = np.arange(half); x2 = np.arange(m - half)
        if len(x1) < 2 or len(x2) < 2:
            continue
        s1 = np.polyfit(x1, leg[:half], 1)[0]         # شیبِ نیمهٔ اول
        s2 = np.polyfit(x2, leg[half:], 1)[0]         # شیبِ نیمهٔ دوم
        rng = max(w_h[pk] - w_l[tr], 1e-9)
        asym[i] = (s1 - s2) / (rng / m)               # نرمال‌شده
    return asym


def pullback_long_signals(df, ema_fast, ema_slow, lb):
    """ستاپِ pullback-LONG پایه (بدونِ فیلترِ معکوس): در روندِ صعودی (ema_fast>ema_slow)،
    قیمت پس از یک اصلاح به نزدیکِ ema_fast برگشته و کندلِ اخیر bull-close است.
    (این baselineِ استانداردِ pullback است تا اثرِ *خالصِ* فیلترِ معکوس سنجیده شود.)"""
    c = df['close'].to_numpy(); o = df['open'].to_numpy()
    n = len(df)
    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()
    # اصلاح: low اخیر لمسِ ema_fast؛ سپس bull-close بالای ema_fast (ادامهٔ روند)
    l = df['low'].to_numpy()
    touched = pd.Series(l <= ef).shift(1).rolling(lb).max().fillna(0).to_numpy().astype(bool)
    sig = (ef > es) & touched & (c > o) & (c > ef)
    sig[:lb + 2] = False
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
    if r['net'] <= 0 or r['wr'] < WR_FLOOR:
        return dict(asset=asset, side=side, sl=sl, tp=tp, mh=mh,
                    net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                    pf=(round(r['pf'], 3) if r['pf'] != float('inf') else 999.0),
                    h1=None, h2=None, wf=[], wf_ok=False, both_ok=False, accepted=False)
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
    return dict(asset=asset, side=side, sl=sl, tp=tp, mh=mh,
                net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
                pf=(round(r['pf'], 3) if r['pf'] != float('inf') else 999.0),
                h1=(round(hv['h1'], 1) if hv else None),
                h2=(round(hv['h2'], 1) if hv else None),
                wf=wf, wf_ok=wf_ok, both_ok=both_ok, accepted=acc)


def main():
    print("=" * 100)
    print("S212 — Al Brooks «Inverse Charts» (فصلِ ۹): فیلترِ عدم‌تقارنِ دیدِ معکوس (rounding-bottom)")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    # تایم‌فریم‌ها طبقِ قانونِ مولتی‌تایم‌فریم — شروع از XAUUSD M1... اما M1 طلا در دیتا نیست
    # (XAU: M5..W1). طبقِ README از موجودها شروع می‌کنیم؛ EURUSD M1 هست.
    TFS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1',
           'EURUSD_M1', 'EURUSD_M5', 'EURUSD_M15', 'EURUSD_M30']

    SL_TP = [(150, 225), (200, 300), (250, 375), (300, 450)]
    MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24}
    LB = [12, 20, 32]
    ASYM_THR = [0.5, 1.0, 2.0]      # آستانهٔ رد (asym بالاتر ⇒ rounding ⇒ رد)

    all_rows = []
    for tf in TFS:
        asset = tf.split('_')[0]
        tag = tf.split('_')[1]
        mh = MH.get(tag, 48)
        try:
            df = S.lastn(S.load(tf), y=4)
        except Exception as e:
            print(f"[skip] {tf}: {e}"); continue
        print(f"\n{'─'*90}\n### {tf}  (n={len(df)}, mh={mh})", flush=True)

        for lb in LB:
            asym = inverse_view_asym(df, lb)
            asym_s = pd.Series(asym).shift(1).to_numpy()   # causal
            base_sig = pullback_long_signals(df, 20, 50, lb)
            for sl, tp in SL_TP:
                # baseline (بدونِ فیلتر) — برای سنجشِ اثرِ *خالصِ* فیلتر
                rb = evaluate(df, asset, base_sig, 'long', sl, tp, mh)
                if rb is None:
                    continue
                for thr in ASYM_THR:
                    keep = (asym_s <= thr) | np.isnan(asym_s)   # nan ⇒ فیلتر خنثی
                    filt_sig = base_sig & keep
                    if filt_sig.sum() < 30:
                        continue
                    rf = evaluate(df, asset, filt_sig, 'long', sl, tp, mh)
                    if rf is None:
                        continue
                    dnet = round(rf['net'] - rb['net'], 1)
                    dwr = round(rf['wr'] - rb['wr'], 2)
                    row = dict(tf=tf, lb=lb, sl=sl, tp=tp, thr=thr,
                               base_net=rb['net'], base_wr=rb['wr'], base_n=rb['n'],
                               filt_net=rf['net'], filt_wr=rf['wr'], filt_n=rf['n'],
                               dnet=dnet, dwr=dwr,
                               wf_ok=rf['wf_ok'], both_ok=rf['both_ok'], accepted=rf['accepted'])
                    all_rows.append(row)
                    # چاپِ مواردِ جالب: فیلتر net را افزایش داده و گیت پاس
                    if dnet > 0 and rf['accepted']:
                        print(f"  ✓ lb{lb} SL{sl}/TP{tp} thr{thr}: base net=${rb['net']:+,.0f}"
                              f"(WR{rb['wr']}) → filt net=${rf['net']:+,.0f}(WR{rf['wr']}) "
                              f"Δnet={dnet:+,.0f} Δwr={dwr:+.1f} n{rf['n']} WF{rf['wf_ok']}", flush=True)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s212_inverse_view.json'), 'w') as f:
        json.dump(all_rows, f, indent=1)
    print(f"\n{'='*100}\nمجموع ردیف: {len(all_rows)}")
    # خلاصه: بهترین موارد بر اساسِ dnet در بینِ گیت-پاس‌ها
    passed = [r for r in all_rows if r['accepted'] and r['dnet'] > 0]
    passed.sort(key=lambda r: -r['dnet'])
    print(f"گیت-پاس با Δnet>0: {len(passed)}")
    for r in passed[:15]:
        print(f"  {r['tf']} lb{r['lb']} SL{r['sl']}/TP{r['tp']} thr{r['thr']}: "
              f"Δnet={r['dnet']:+,.0f} (filt ${r['filt_net']:+,.0f}/WR{r['filt_wr']}) n{r['filt_n']}")
    print("saved: results/_s212_inverse_view.json")


if __name__ == '__main__':
    main()
