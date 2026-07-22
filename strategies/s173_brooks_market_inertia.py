# -*- coding: utf-8 -*-
"""
S173 — Al Brooks «Market Inertia» (فصلِ ۱: The Spectrum of Price Action)

قانونِ #۱ پروژه: هدف = بیشینه‌سازیِ سودِ خالص (XAUUSD + EURUSD)؛ WR فقط کفِ ۴۰٪.

مفهومِ محوریِ فصل ۱ (نقلِ مکانیکیِ Brooks):
«بازار پیوسته اینرسی نشان می‌دهد و تمایل دارد همان کاری را که تازه کرده ادامه دهد.
 اگر در روند است، بیشترِ تلاش‌های برگشتی شکست می‌خورند؛ اگر در رنج است، بیشترِ
 شکست‌ها (breakouts) شکست می‌خورند.»

ترجمهٔ بک‌تست‌پذیر (قاعدهٔ برندهٔ آزمونِ اکتشافی = «trend fade reversal-attempt»):
  1) رژیم را با ADX طبقه‌بندی کن: trend = ADX>adx_hi.
  2) جهتِ روند با EMA(fast)>EMA(slow).
  3) «تلاشِ برگشتی» = close به زیرِ کفِ lb-کندلِ اخیر می‌شکند (در روندِ صعودی).
  4) اینرسیِ روند ⇒ این شکست عمدتاً تله است ⇒ ورودِ LONG.
  (نسخهٔ آینه‌ای برای روندِ نزولی ⇒ SHORT هم آزموده می‌شود.)

گیتِ سخت (هم‌سو با S168/S171/S172):
  net>0  AND  WR≥40  AND  هر دو نیمه مثبت  AND  walk-forward هر ۴ پنجره (net>0 & WR≥40)
  AND  n≥30.

خروجی: results/_s173_market_inertia.json
"""
import os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import s172_brooks_two_legs as S      # load, lastn, sim, stats, halves (زیرساختِ مشترک)
from engine import indicators as ind

ADX_HI = None  # از grid خوانده می‌شود
WR_FLOOR = 40.0


# ============================================================================
#  سیگنالِ اینرسیِ روند (causal — همه با shift(1) وارد می‌شوند)
# ============================================================================
def inertia_signals(df, ef, es, adx_hi, lb, side):
    """
    side='long'  : روندِ صعودی (emaF>emaS) + ADX>adx_hi + شکستِ کفِ lb اخیر ⇒ LONG
    side='short' : روندِ نزولی (emaF<emaS) + ADX>adx_hi + شکستِ سقفِ lb اخیر ⇒ SHORT
    """
    c = df['close']
    cl = c.to_numpy(); h = df['high'].to_numpy(); l = df['low'].to_numpy()
    emaF = ind.ema(c, ef).to_numpy()
    emaS = ind.ema(c, es).to_numpy()
    adx = ind.adx(df, 14)
    adx = adx[0] if isinstance(adx, tuple) else adx
    adx = pd.Series(np.asarray(adx)).fillna(0).to_numpy()

    trend = adx > adx_hi
    prev_ll = pd.Series(l).rolling(lb).min().shift(1).to_numpy()
    prev_hh = pd.Series(h).rolling(lb).max().shift(1).to_numpy()

    if side == 'long':
        rev_attempt = cl < prev_ll            # تلاشِ برگشتی در روندِ صعودی
        raw = trend & (emaF > emaS) & rev_attempt
    else:
        rev_attempt = cl > prev_hh            # تلاشِ برگشتی در روندِ نزولی
        raw = trend & (emaF < emaS) & rev_attempt

    return pd.Series(raw).shift(1).fillna(False).to_numpy()


# ============================================================================
#  ارزیابیِ یک کاندید با گیتِ کامل
# ============================================================================
def walk_forward(df, sig, side, sl, tp, mh, asset, nwin=4):
    n = len(df); b = [int(n * i / nwin) for i in range(nwin + 1)]
    out = []
    z = np.zeros(n, bool)
    for w in range(nwin):
        lo, hi = b[w], b[w + 1]
        sub = df.iloc[lo:hi].reset_index(drop=True)
        s = sig[lo:hi]
        zz = np.zeros(hi - lo, bool)
        if side == 'long':
            r = S.stats(S.sim(sub, s, zz, sl, tp, mh, asset), asset)
        else:
            r = S.stats(S.sim(sub, zz, s, sl, tp, mh, asset), asset)
        out.append((r['net'], r['wr'], r['n']))
    return out


def evaluate(df, asset, sig, side, sl, tp, mh):
    z = np.zeros(len(df), bool)
    if side == 'long':
        tr = S.sim(df, sig, z, sl, tp, mh, asset)
    else:
        tr = S.sim(df, z, sig, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return None
    hv = S.halves(df, sig if side == 'long' else z,
                  z if side == 'long' else sig, sl, tp, mh, asset)
    wf = walk_forward(df, sig, side, sl, tp, mh, asset)
    wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
    both_ok = hv and hv['h1'] > 0 and hv['h2'] > 0
    accept = (r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    return dict(asset=asset, side=side, ef=ef_, es=es_, adx=adx_hi_, lb=lb_,
                sl=sl, tp=tp, mh=mh, net=round(r['net'], 1), wr=round(r['wr'], 2),
                n=r['n'], pf=round(r['pf'], 3),
                h1=round(hv['h1'], 1) if hv else None,
                h2=round(hv['h2'], 1) if hv else None,
                wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
                wf_ok=bool(wf_ok), both_ok=bool(both_ok), accepted=bool(accept))


# متغیرهای سراسری برای ثبتِ پارامتر در evaluate
ef_ = es_ = adx_hi_ = lb_ = None


def main():
    print("=" * 100)
    print("S173 — Al Brooks «Market Inertia» (فصلِ ۱): trend-fade-reversal (اینرسیِ روند)")
    print("گیت: net>0 + هر دو نیمه + walk-forward هر ۴ پنجره + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100)

    grids = {
        'XAUUSD': [(200, 300), (300, 450), (250, 375), (400, 600)],
        'EURUSD': [(20, 30), (30, 45), (40, 60)],
    }
    mhs = [32, 48, 96]
    ema_pairs = [(20, 50), (10, 30)]
    adx_his = [22, 28, 34]
    lbs = [10, 20, 30]

    global ef_, es_, adx_hi_, lb_
    results = []
    accepted = []

    for asset in ('XAUUSD', 'EURUSD'):
        df = S.lastn(S.load(asset + '_M15'))
        print(f"\n### {asset}  (rows={len(df)}) ###")
        for side in ('long', 'short'):
            for (ef, es) in ema_pairs:
                for adx_hi in adx_his:
                    for lb in lbs:
                        ef_, es_, adx_hi_, lb_ = ef, es, adx_hi, lb
                        sig = inertia_signals(df, ef, es, adx_hi, lb, side)
                        if sig.sum() < 30:
                            continue
                        for (sl, tp) in grids[asset]:
                            for mh in mhs:
                                r = evaluate(df, asset, sig, side, sl, tp, mh)
                                if r is None:
                                    continue
                                results.append(r)
                                if r['accepted']:
                                    accepted.append(r)

        # بهترین‌های همین دارایی
        best = sorted([x for x in results if x['asset'] == asset and x['accepted']],
                      key=lambda x: -x['net'])[:6]
        if best:
            print(f"  پذیرفته‌شده‌های {asset} (top by net):")
            for x in best:
                print(f"    ✅ {x['side']:5} ema{x['ef']}/{x['es']} adx>{x['adx']} lb{x['lb']} "
                      f"SL{x['sl']}/TP{x['tp']}/mh{x['mh']}  net=${x['net']:+,.0f} "
                      f"WR={x['wr']:.1f}% n={x['n']} PF={x['pf']:.2f}")
        else:
            print(f"  {asset}: هیچ کاندیدی گیتِ کامل را پاس نکرد.")

    os.makedirs('results', exist_ok=True)
    out = dict(strategy='S173_MarketInertia_ch1',
               n_total=len(results), n_accepted=len(accepted),
               results=results, accepted=accepted)
    with open('results/_s173_market_inertia.json', 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\n✅ ذخیره شد: results/_s173_market_inertia.json  "
          f"(کل={len(results)}، پذیرفته={len(accepted)})")


if __name__ == '__main__':
    main()
