# -*- coding: utf-8 -*-
"""
S215 — Al Brooks «Trend Lines» (فصلِ ۱۳ کتابِ Trading Price Action: TRENDS، Part II)
=====================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

تزِ محوریِ فصلِ ۱۳ (نقلِ مکانیکیِ Brooks):
  «As a trend progresses, countertrend moves break the trend lines and USUALLY THE
   BREAKOUTS FAIL, setting up WITH-TREND entries.»
  «While beginners are shorting on those strong sell-offs near the bull trend line,
   experienced traders … have limit orders to BUY at and JUST BELOW the trend line.
   The market usually has to go A LITTLE BELOW the trend line during a sharp sell-off
   to find information … Most of the time, there will be more buyers and the bull
   trend will resume.»

  ⇒ در روندِ صعودی، هر بار sell-offِ تند قیمت را به/کمی‌زیرِ خطِ روندِ صعودی (وصل‌کنندهٔ
    دو کفِ اخیر) می‌رساند و قیمت به بالای خط بازمی‌گردد (failed breakout) ⇒ ستاپِ LONGِ
    ادامهٔ روند. قرینه برای SHORT در روندِ نزولی.

ترجمهٔ بک‌تست‌پذیر (همه causal، shift(1) ⇒ ورودِ next-open):
  1) دو swing-lowِ تأییدشدهٔ اخیر (swing_pivots(k) ماژولِ s172) با low[i2]>low[i1] ⇒
     خطِ روندِ صعودی با شیبِ m=(low[i2]-low[i1])/(i2-i1)؛ رژیم ema_fast>ema_slow.
  2) امتدادِ خط: line(t)=low[i2]+m*(t-i2).
  3) ماشه LONG: low[t] < line(t)  (overshoot/penetration) و close[t] > line(t)-tol
     (بازگشت به بالای خط = failed breakout؛ tol=pen×ATR).
  4) قیدِ ضدِ رنج (اختیاری): بدنه‌های اخیر کاملاً هم‌پوش نباشند.
  قرینهٔ کامل برای SHORT (دو swing-high نزولی، تستِ خطِ روندِ نزولی از پایین).

گیتِ سختِ ۴-گانه: net>0 + هر دو نیمه + walk-forward(۴/۴) + WR≥40 + n≥30.
چارچوبِ load/sim/stats/halves + swing_pivots هم‌ترازِ S172/S214.
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import s172_brooks_two_legs as S          # load/lastn/sim/stats/halves/swing_pivots + cost-calibrated
from engine import indicators as ind

RESULTS = os.path.join(ROOT, 'results')
WR_FLOOR = 40.0


# ============================================================================
#  سیگنالِ trend-line test (failed-breakout continuation) — causal، shift(1)
# ============================================================================
def trend_line_signals(df, side, ema_fast, ema_slow, k, pen, max_gap, anti_range=True, atr_len=14):
    """ورودِ ادامهٔ روند روی «تستِ ناموفقِ خطِ روند».

    side='long':  خطِ روندِ صعودی از دو swing-low اخیر؛ ماشه وقتی قیمت کمی زیرِ خط
                  می‌رود و بالای خط می‌بندد (failed breakout) در رژیمِ ema_fast>ema_slow.
    side='short': قرینه با دو swing-high و رژیمِ نزولی.

    k       = نیم-پنجرهٔ swing-pivot (تأخیرِ تأییدِ k کندل، مطابقِ s172).
    pen     = عمقِ نفوذِ مجاز به آن‌سوی خط برحسبِ ضریبِ ATR (tol=pen×ATR).
    max_gap = حداکثر فاصلهٔ دو pivot سازندهٔ خط (کندل) تا خط «تازه» بماند.
    anti_range = رد سیگنال وقتی ۳ کندلِ اخیر بیش‌ازحد هم‌پوش‌اند (نشانهٔ رنج).
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    atr = ind.atr(df, atr_len).to_numpy()
    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()
    sh, sl_ = S.swing_pivots(h, l, k)

    # لیستِ اندیسِ pivotها؛ هر pivot تنها از i+k «قابلِ مشاهده» است.
    sig = np.zeros(n, bool)

    if side == 'long':
        piv = [i for i in range(n) if sl_[i]]
        yv = l
        regime = ef > es
    else:
        piv = [i for i in range(n) if sh[i]]
        yv = h
        regime = ef < es

    # برای هر کندلِ t، از آخرین دو pivotِ «تأییدشده تا t» خط را بساز.
    # اندیسِ آخرین دو pivot که conf=i+k <= t باشند.
    # برای کارایی: با اشاره‌گر پیش می‌رویم.
    conf_idx = [p + k for p in piv]           # کندلی که هر pivot در آن تأیید می‌شود
    ptr = 0
    last2 = []                                 # اندیسِ خودِ pivot (i)، حداکثر ۲ عدد اخیر
    for t in range(n):
        # همهٔ pivotهایی که تا اکنون (conf<=t) تأیید شده‌اند را وارد کن
        while ptr < len(piv) and conf_idx[ptr] <= t:
            last2.append(piv[ptr]); ptr += 1
            if len(last2) > 2:
                last2 = last2[-2:]
        if len(last2) < 2:
            continue
        i1, i2 = last2[0], last2[1]
        if (i2 - i1) <= 0 or (i2 - i1) > max_gap:
            continue
        if np.isnan(atr[t]) or atr[t] <= 0:
            continue
        m = (yv[i2] - yv[i1]) / (i2 - i1)
        line_t = yv[i2] + m * (t - i2)
        tol = pen * atr[t]

        if side == 'long':
            # خطِ روندِ صعودی: pivotِ دوم بالاتر از اولی + شیبِ مثبت + رژیمِ صعودی
            if not (yv[i2] > yv[i1] and m > 0 and regime[t]):
                continue
            # failed breakout: کمی زیرِ خط رفت ولی بالای خط بست
            if l[t] < line_t and c[t] > (line_t - tol) and c[t] >= o[t]:
                if anti_range and _is_range(h, l, o, c, t):
                    continue
                sig[t] = True
        else:
            if not (yv[i2] < yv[i1] and m < 0 and regime[t]):
                continue
            if h[t] > line_t and c[t] < (line_t + tol) and c[t] <= o[t]:
                if anti_range and _is_range(h, l, o, c, t):
                    continue
                sig[t] = True

    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def _is_range(h, l, o, c, t, lb=3):
    """۳ کندلِ اخیر «large and almost entirely overlapping» ⇒ رنج (Brooks Fig 13.7)."""
    if t < lb:
        return False
    hi = h[t-lb+1:t+1]; lo = l[t-lb+1:t+1]
    span = hi.max() - lo.min()
    if span <= 0:
        return True
    # مجموعِ رنجِ تکی نسبت به span؛ اگر هم‌پوشانی زیاد باشد نسبت بزرگ است.
    indiv = float((hi - lo).sum())
    return (indiv / span) >= 2.3        # هم‌پوشانیِ سنگین


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
    for kk in range(4):
        a = int(n * kk / 4); b = int(n * (kk + 1) / 4)
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
    print("S215 — Al Brooks «Trend Lines» (فصلِ ۱۳): failed-breakout continuation روی خطِ روندِ هندسی")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    # قانونِ مولتی‌تایم‌فریم: از XAUUSD شروع (M1 طلا موجود نیست ⇒ M5..W1)، سپس EURUSD.
    TFS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1', 'XAUUSD_H4', 'XAUUSD_D1',
           'EURUSD_M1', 'EURUSD_M5', 'EURUSD_M15', 'EURUSD_M30']

    # TP روندی (بگذار برد بدود) — گریدِ SL/TP مخصوص هر مقیاس در MH.
    SL_TP = [(150, 300), (200, 400), (250, 500), (300, 450), (200, 300)]
    MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24, 'H4': 16, 'D1': 10}
    EMA = [(10, 30), (20, 50)]
    K = [3, 5]                 # نیم-پنجرهٔ swing-pivot
    PEN = [0.3, 0.6, 1.0]      # عمقِ نفوذِ مجاز (ضریبِ ATR)
    MAX_GAP = [40, 80]         # حداکثر فاصلهٔ دو pivotِ سازندهٔ خط
    SIDES = ['long', 'short']

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
                for k in K:
                    for pen in PEN:
                        for mg in MAX_GAP:
                            sig = trend_line_signals(df, side, ef, es, k, pen, mg)
                            ns = int(sig.sum())
                            if ns < 30:
                                continue
                            for sl, tp in SL_TP:
                                r = evaluate(df, asset, sig, side, sl, tp, mh)
                                if r is None:
                                    continue
                                row = dict(tf=tf, side=side, ema=f"{ef}/{es}", k=k,
                                           pen=pen, max_gap=mg, sl=sl, tp=tp,
                                           net=r['net'], wr=r['wr'], n=r['n'], pf=r['pf'],
                                           wf=r['wf'], wf_ok=r['wf_ok'],
                                           both_ok=r['both_ok'], accepted=r['accepted'])
                                all_rows.append(row)
                                if r['accepted']:
                                    accepted.append(row)
                                    print(f"  ✓ {side} ema{ef}/{es} k{k} pen{pen} gap{mg} "
                                          f"SL{sl}/TP{tp}: net=${r['net']:+,.0f} WR{r['wr']} "
                                          f"n{r['n']} PF{r['pf']} WF{[w[0] for w in r['wf']]}", flush=True)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s215_trend_line.json'), 'w') as f:
        json.dump(all_rows, f, indent=1)
    print(f"\n{'='*100}\nمجموع ردیف: {len(all_rows)} | گیت-پاس: {len(accepted)}")
    accepted.sort(key=lambda r: -r['net'])
    for r in accepted[:25]:
        print(f"  {r['tf']} {r['side']} ema{r['ema']} k{r['k']} pen{r['pen']} gap{r['max_gap']} "
              f"SL{r['sl']}/TP{r['tp']}: net=${r['net']:+,.0f} WR{r['wr']} n{r['n']}")
    print("saved: results/_s215_trend_line.json")


if __name__ == '__main__':
    main()
