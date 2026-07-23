# -*- coding: utf-8 -*-
"""
S214 — Al Brooks «Late and Missed Entries» (فصلِ ۱۱ کتابِ Trading Price Action: TRENDS)
========================================================================================
> قانونِ شمارهٔ ۱ پروژه: هدف فقط سودِ خالصِ بیشتر (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

مفهومِ محوریِ فصلِ ۱۱ (قرینهٔ فصلِ ۱۰ — به‌جای fade، ادامهٔ روند/continuation):
  تز «always-in / participate»: «If you look at any chart and think that if you had taken
  the original entry you would still be holding the swing portion of your trade, then you
  need to enter at the market … because the probability of making a profit is high.»

  قاعدهٔ کاملاً کدنویسی‌پذیر (Figure 11.1):
  «Once the market starts forming FOUR OR MORE CONSECUTIVE bull trend bars that are NOT
   too large and therefore possibly climactic, traders should BUY at least a small
   position AT THE MARKET INSTEAD OF WAITING FOR A PULLBACK.»

  ⇒ به‌محضِ تشکیلِ ≥n_run کندلِ trend-bar متوالیِ هم‌جهت (غیرِ climactic) ⇒ ورودِ at-market
    در جهتِ روند، بدونِ انتظار برای اصلاح. قرینه برای SHORT در روندِ نزولی.

  مدیریتِ ریسکِ ورودِ دیرهنگام: استاپِ بزرگ‌تر (swing-size) + TP روندی («بگذار برد بدود»).

ترجمهٔ بک‌تست‌پذیر (همه causal، shift(1) ⇒ ورودِ next-open):
  1) روندِ متوالی: دنبالهٔ ≥`n_run` کندلِ trend-bar هم‌جهتِ پیاپی
     (LONG: close>open و body≥br×range؛ SHORT قرینه).
  2) قیدِ ضدِ climax: میانگینِ range کندل‌های run ≤ `clx`×ATR ⇒ رد اسپایکِ اقلیمی.
  3) تأییدِ رژیم: ema_fast>ema_slow (LONG) / < (SHORT).
  4) ماشه روی کندلِ بلافاصله پس از تکمیلِ run ⇒ at-market (next-open پس از shift).

گیتِ سختِ ۴-گانه: net>0 + هر دو نیمه + walk-forward(۴/۴) + WR≥40 + n≥30.
چارچوبِ load/sim/stats/halves هم‌ترازِ S213/S186 از ماژولِ پایهٔ s172.
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
#  سیگنالِ late-entry (momentum-continuation) — همه causal، خروجی shift(1)
# ============================================================================
def late_entry_signals(df, side, ema_fast, ema_slow, n_run, br, clx, atr_len=14):
    """ورودِ دیرهنگام به روند پس از ≥n_run کندلِ trend-bar متوالیِ هم‌جهتِ غیرِ climactic.

    side='long'  ⇒ ورودِ LONG پس از رشتهٔ bull-trend-bar در روندِ صعودی.
    side='short' ⇒ ورودِ SHORT پس از رشتهٔ bear-trend-bar در روندِ نزولی.

    n_run = حداقل تعدادِ trend-bar هم‌جهتِ متوالی (تز Brooks: «four or more»).
    br    = آستانهٔ نسبتِ بدنه (body≥br×range) برای «trend bar».
    clx   = ضریبِ ضدِ climax: میانگینِ range کندل‌های run نباید از clx×ATR بزرگ‌تر باشد.
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    rng = np.maximum(h - l, 1e-9)
    body = c - o
    atr = ind.atr(df, atr_len).to_numpy()

    ef = ind.ema(pd.Series(c), ema_fast).to_numpy()
    es = ind.ema(pd.Series(c), ema_slow).to_numpy()

    if side == 'long':
        trend_bar = (body > 0) & (np.abs(body) >= br * rng)
        regime = ef > es
    else:
        trend_bar = (body < 0) & (np.abs(body) >= br * rng)
        regime = ef < es

    sig = np.zeros(n, bool)
    # run-length هم‌جهتِ متوالی تا کندلِ i (بسته‌شده)
    run = 0
    for i in range(n):
        if trend_bar[i]:
            run += 1
        else:
            run = 0
        # ماشه: به‌محضِ رسیدن run به n_run (فقط لبهٔ اول، نه هر کندلِ بعدیِ run) + رژیم
        if run == n_run and regime[i] and not np.isnan(atr[i]) and atr[i] > 0:
            # قیدِ ضدِ climax: میانگینِ range کندل‌های run ≤ clx×ATR
            avg_run_rng = rng[i - n_run + 1:i + 1].mean()
            if avg_run_rng <= clx * atr[i]:
                sig[i] = True
    # shift(1) ⇒ ورود در open کندلِ بعد از کندلِ ماشه
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
    print("S214 — Al Brooks «Late and Missed Entries» (فصلِ ۱۱): ادامهٔ روند پس از ≥n_run trend-bar متوالی")
    print("گیت: net>0 + هر دو نیمه + walk-forward ۴/۴ + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    # قانونِ مولتی‌تایم‌فریم: از XAUUSD شروع (M1 طلا موجود نیست ⇒ M5..H1)، سپس EURUSD.
    TFS = ['XAUUSD_M5', 'XAUUSD_M15', 'XAUUSD_M30', 'XAUUSD_H1',
           'EURUSD_M1', 'EURUSD_M5', 'EURUSD_M15', 'EURUSD_M30']

    SL_TP = [(150, 300), (200, 400), (250, 500), (300, 600), (300, 450)]   # TP روندی (بگذار برد بدود)
    MH = {'M1': 96, 'M5': 96, 'M15': 48, 'M30': 32, 'H1': 24}
    EMA = [(10, 30), (20, 50)]
    N_RUN = [4, 5, 6]          # تز Brooks «four or more»
    BR = [0.5, 0.6]            # آستانهٔ بدنهٔ trend-bar
    CLX = [1.5, 2.5]           # ضریبِ ضدِ climax (میانگینِ range run ≤ clx×ATR)
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
                for nr in N_RUN:
                    for br in BR:
                        for clx in CLX:
                            sig = late_entry_signals(df, side, ef, es, nr, br, clx)
                            ns = int(sig.sum())
                            if ns < 30:
                                continue
                            for sl, tp in SL_TP:
                                r = evaluate(df, asset, sig, side, sl, tp, mh)
                                if r is None:
                                    continue
                                row = dict(tf=tf, side=side, ema=f"{ef}/{es}", n_run=nr,
                                           br=br, clx=clx, sl=sl, tp=tp,
                                           net=r['net'], wr=r['wr'], n=r['n'], pf=r['pf'],
                                           wf=r['wf'], wf_ok=r['wf_ok'],
                                           both_ok=r['both_ok'], accepted=r['accepted'])
                                all_rows.append(row)
                                if r['accepted']:
                                    accepted.append(row)
                                    print(f"  ✓ {side} ema{ef}/{es} run{nr} br{br} clx{clx} "
                                          f"SL{sl}/TP{tp}: net=${r['net']:+,.0f} WR{r['wr']} "
                                          f"n{r['n']} PF{r['pf']} WF{r['wf']}", flush=True)

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, '_s214_late_entry.json'), 'w') as f:
        json.dump(all_rows, f, indent=1)
    print(f"\n{'='*100}\nمجموع ردیف: {len(all_rows)} | گیت-پاس: {len(accepted)}")
    accepted.sort(key=lambda r: -r['net'])
    for r in accepted[:25]:
        print(f"  {r['tf']} {r['side']} ema{r['ema']} run{r['n_run']} br{r['br']} clx{r['clx']} "
              f"SL{r['sl']}/TP{r['tp']}: net=${r['net']:+,.0f} WR{r['wr']} n{r['n']}")
    print("saved: results/_s214_late_entry.json")


if __name__ == '__main__':
    main()
