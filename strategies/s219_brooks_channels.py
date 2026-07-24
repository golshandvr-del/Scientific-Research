# -*- coding: utf-8 -*-
"""
S219 — Al Brooks «Channels» (فصلِ ۱۵ کتابِ Trading Price Action: TRENDS، Part II)
=================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

تزِ محوریِ فصلِ ۱۵ (نقلِ مکانیکیِ Brooks):
  «When a channel is in a bull trend, higher prices are more certain, and traders
   should look to BUY NEAR THE BOTTOM of the channel.»
  «At the start of a bull channel, it is better to BUY BELOW THE LOWS OF BARS, but as
   the channel reaches resistance areas … it is better to consider shorting above bars
   instead of buying below bars.»
  «The most reliable buy signal will be a high 2 with a bull signal bar at the moving
   average WHERE THE ENTRY IS NOT TOO CLOSE TO THE TOP OF THE CHANNEL.»

تفاوتِ بنیادی با S215 (فصلِ ۱۳ Trend Lines):
  - S215: فقط یک خطِ روند (trend line) + failed-breakout ⇒ ورودِ ادامهٔ روند روی penetration.
  - S219: یک **channelِ کامل** = خطِ روند (trend line، از دو swing-low) + **خطِ کانالِ موازی**
    (parallel که به سقفِ legِ اول کشیده می‌شود). بُعدِ نوِ کلیدی = **موقعیتِ نسبیِ قیمت داخلِ
    channel** (`pos_in_channel` ∈ [0,1]، 0=کفِ کانال، 1=سقفِ کانال). قاعدهٔ Brooks:
    «فقط در نیمهٔ پایینِ کانال بخر، نه نزدیکِ سقف». این معیارِ موقعیتِ نسبی در پرتفوی
    وجود ندارد (نه S215، نه MA-محورها، نه زمان-محورها).

ترجمهٔ بک‌تست‌پذیر (همه causal، shift(1) ⇒ ورودِ next-open):
  1) دو swing-lowِ تأییدشده (i1<i2، low[i2]>low[i1]) ⇒ خطِ روندِ صعودی؛ شیب m>0؛ رژیم ema_f>ema_s.
  2) خطِ کانالِ موازی = خطِ روند + آفستِ عمودی که آن را به بالاترین high بینِ i1..i2 می‌رساند.
     ⇒ عرضِ کانال = width(t) = channel_line(t) - trend_line(t).
  3) pos_in_channel(t) = (close[t] - trend_line(t)) / width(t).
  4) ماشهٔ LONG (Brooks buy-low): pos ≤ pos_max (نیمهٔ پایین) ∧ pullback (low[t] < low[t-1])
     ∧ close[t] ≥ open[t] (bull bar تأیید) ∧ رژیمِ صعودی ∧ ضدِ رنج.
  قرینهٔ کامل برای SHORT (دو swing-high نزولی، فروش در نیمهٔ بالای کانالِ نزولی: pos ≥ 1-pos_max).

گیتِ سختِ ۴-گانه: net>0 + هر دو نیمه + walk-forward(۴/۴) + WR≥40 + n≥30.
چارچوبِ load/sim/stats/halves + swing_pivots هم‌ترازِ S215/S172/S214.
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
#  سیگنالِ channel «buy-low / sell-high» — causal، shift(1)
# ============================================================================
def channel_signals(df, side, ema_fast, ema_slow, k, pos_max, max_gap,
                    require_pullback=True, anti_range=True, atr_len=14):
    """ورود بر پایهٔ موقعیتِ نسبیِ قیمت داخلِ channel (قاعدهٔ Brooks فصلِ ۱۵).

    side='long':  خطِ روندِ صعودی از دو swing-low؛ خطِ کانالِ موازی به بالاترین high
                  بینِ دو pivot. ورود وقتی close در نیمهٔ پایینِ کانال (pos≤pos_max)
                  و pullback (low[t]<low[t-1]) و bull-bar، در رژیمِ صعودی.
    side='short': قرینه با دو swing-high؛ فروش در نیمهٔ بالای کانالِ نزولی (pos≥1-pos_max).

    k        = نیم-پنجرهٔ swing-pivot (تأخیرِ تأییدِ k کندل).
    pos_max  = سقفِ موقعیتِ نسبیِ مجاز برای خرید (0.5 = فقط نیمهٔ پایین).
    max_gap  = حداکثر فاصلهٔ دو pivotِ سازندهٔ خط.
    require_pullback = ماشه فقط روی pullback (low[t]<low[t-1] برای long).
    anti_range = رد سیگنال وقتی ۳ کندلِ اخیر بیش‌ازحد هم‌پوش‌اند (Fig 13.7/رنج).
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    atr = ind.atr(df, atr_len).to_numpy()
    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()
    sh, sl_ = S.swing_pivots(h, l, k)

    sig = np.zeros(n, bool)

    if side == 'long':
        piv = [i for i in range(n) if sl_[i]]
        yv = l; regime = ef > es
    else:
        piv = [i for i in range(n) if sh[i]]
        yv = h; regime = ef < es

    conf_idx = [p + k for p in piv]
    ptr = 0
    last2 = []
    for t in range(n):
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
        trend_t = yv[i2] + m * (t - i2)          # خطِ روند در t

        if side == 'long':
            # خطِ روندِ صعودی معتبر
            if not (yv[i2] > yv[i1] and m > 0 and regime[t]):
                continue
            # خطِ کانالِ موازی: بالاترین highِ بینِ i1..i2 را با شیبِ m امتداد بده
            seg_hi = h[i1:i2 + 1]
            # آفست: بیشینهٔ فاصلهٔ عمودیِ high نسبت به خطِ روند در همان اندیس
            offs = np.array([h[j] - (yv[i2] + m * (j - i2)) for j in range(i1, i2 + 1)])
            off = float(np.nanmax(offs))
            if off <= 0:
                continue
            channel_t = trend_t + off
            width = channel_t - trend_t
            if width <= 0:
                continue
            pos = (c[t] - trend_t) / width       # 0=کفِ کانال، 1=سقفِ کانال
            if pos > pos_max:                    # نزدیکِ سقف ⇒ نخر
                continue
            if require_pullback and not (l[t] < l[t - 1] if t > 0 else False):
                continue
            if not (c[t] >= o[t]):               # bull-bar تأیید
                continue
            if anti_range and _is_range(h, l, o, c, t):
                continue
            sig[t] = True
        else:
            if not (yv[i2] < yv[i1] and m < 0 and regime[t]):
                continue
            offs = np.array([(yv[i2] + m * (j - i2)) - l[j] for j in range(i1, i2 + 1)])
            off = float(np.nanmax(offs))
            if off <= 0:
                continue
            channel_t = trend_t - off            # خطِ کانالِ زیرِ کف‌ها (نزولی)
            width = trend_t - channel_t
            if width <= 0:
                continue
            pos = (c[t] - channel_t) / width     # 0=کفِ کانال، 1=سقفِ کانال (خطِ روندِ بالا)
            if pos < (1.0 - pos_max):            # نزدیکِ کفِ کانالِ نزولی ⇒ نفروش
                continue
            if require_pullback and not (h[t] > h[t - 1] if t > 0 else False):
                continue
            if not (c[t] <= o[t]):
                continue
            if anti_range and _is_range(h, l, o, c, t):
                continue
            sig[t] = True

    return pd.Series(sig).shift(1).fillna(False).to_numpy()


def _is_range(h, l, o, c, t, lb=3):
    """۳ کندلِ اخیر «large and almost entirely overlapping» ⇒ رنج (Brooks)."""
    if t < lb:
        return False
    hi = h[t - lb + 1:t + 1]; lo = l[t - lb + 1:t + 1]
    span = hi.max() - lo.min()
    if span <= 0:
        return True
    indiv = float((hi - lo).sum())
    return (indiv / span) >= 2.3


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
    print("S219 — Al Brooks «Channels» (فصلِ ۱۵): buy-low/sell-high بر پایهٔ موقعیتِ نسبی داخلِ channel")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    # قانونِ مولتی‌تایم‌فریم: از XAUUSD شروع (M1 طلا موجود نیست ⇒ M5..D1)، سپس EURUSD.
    TFS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1', 'XAUUSD_H4', 'XAUUSD_D1',
           'EURUSD_M1', 'EURUSD_M5', 'EURUSD_M15', 'EURUSD_M30']

    SL_TP = [(150, 300), (200, 400), (250, 500), (300, 450), (200, 300)]
    MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24, 'H4': 16, 'D1': 10}
    EMA = [(10, 30), (20, 50)]
    K = [3, 5]
    POS_MAX = [0.4, 0.5, 0.6]        # سقفِ موقعیتِ نسبی برای خرید (نیمهٔ پایینِ کانال)
    MAX_GAP = [40, 80]
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
                    for pmax in POS_MAX:
                        for mg in MAX_GAP:
                            sig = channel_signals(df, side, ef, es, k, pmax, mg)
                            ns = int(sig.sum())
                            if ns < 30:
                                continue
                            for sl, tp in SL_TP:
                                r = evaluate(df, asset, sig, side, sl, tp, mh)
                                if r is None:
                                    continue
                                row = dict(tf=tf, side=side, ema=f"{ef}/{es}", k=k,
                                           pos_max=pmax, max_gap=mg, sl=sl, tp=tp,
                                           net=r['net'], wr=r['wr'], n=r['n'], pf=r['pf'],
                                           wf=r['wf'], wf_ok=r['wf_ok'],
                                           both_ok=r['both_ok'], accepted=r['accepted'])
                                all_rows.append(row)
                                if r['accepted']:
                                    accepted.append(row)
                                    print(f"  ✓ {side} ema{ef}/{es} k{k} pos{pmax} gap{mg} "
                                          f"SL{sl}/TP{tp}: net=${r['net']:+,.0f} WR{r['wr']} "
                                          f"n{r['n']} PF{r['pf']} WF{[w[0] for w in r['wf']]}", flush=True)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s219_channels.json'), 'w') as f:
        json.dump(all_rows, f, indent=1)
    print(f"\n{'='*100}\nمجموع ردیف: {len(all_rows)} | گیت-پاس: {len(accepted)}")
    accepted.sort(key=lambda r: -r['net'])
    for r in accepted[:25]:
        print(f"  {r['tf']} {r['side']} ema{r['ema']} k{r['k']} pos{r['pos_max']} gap{r['max_gap']} "
              f"SL{r['sl']}/TP{r['tp']}: net=${r['net']:+,.0f} WR{r['wr']} n{r['n']}")
    print("saved: results/_s219_channels.json")


if __name__ == '__main__':
    main()
