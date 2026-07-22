# -*- coding: utf-8 -*-
"""
S174 — Al Brooks «Sell-Climax Exhaustion Reversal» (فصلِ ۲: Trend Bars, Doji Bars, Climaxes)
================================================================================
> # 🎯 قانونِ شمارهٔ ۱ پروژه (بالاترین اولویت)
> هدف = بیشینه‌سازیِ **سودِ خالص** (XAUUSD + EURUSD)؛ WR تابعِ هدف نیست اما هر لایهٔ
> فعال باید WR≥۴۰٪ داشته باشد. تعریفِ رسمیِ سودِ خالص = XAUUSD + EURUSD.

--------------------------------------------------------------------------------
منشأ (کتاب، فصلِ ۲: «Trend Bars, Doji Bars, and Climaxes»):
  نقلِ مکرّرِ Brooks (Fig 2.4 bar 19، Fig 2.5 bar 7→9، متنِ ص. ۶۳/۷۲/۷۳):
  «وقتی یک روندِ نزولی ۳۰+ کندل بدونِ اصلاحِ مهم ادامه یافته و به یک بدنهٔ نزولیِ
   استثنایی‌بزرگ (large bear trend bar / sell-climax، اغلب با بدنه‌های *فزاینده* در
   چند کندلِ آخر) می‌رسد، این نشانهٔ خالی‌شدنِ فروش (sell vacuum) و خستگیِ روند است ⇒
   قوی‌ها تهاجمی می‌خرند ⇒ LONG.»

  «Because the strong bulls and bears are waiting for an unusually strong bear
   trend bar before buying, the absence of buying as the market approaches support
   leads to a sell vacuum and the formation of the large bear trend bar. Once it
   forms, the bears quickly buy back their shorts ... and the bulls initiate new
   longs.» (ص. ۷۳)

چرا لبهٔ *نو* است:
  پرتفویِ فعلی هیچ لایهٔ mean-reversion/exhaustion ندارد. S173 در روندِ نزولی SHORT
  می‌زند (اینرسیِ ادامهٔ روند)؛ این ایده برعکس است — در *انتهای* روندِ نزولیِ خسته
  LONG (برگشت). از bias صعودیِ ساختاریِ طلا هم بهره می‌برد.

ترجمهٔ بک‌تست‌پذیر (همه causal، همه با shift(1)):
  1) رژیمِ نزولی: ema(fast) < ema(slow) در لحظهٔ کندلِ کلایمکس.
  2) طولِ روندِ نزولیِ اخیر ≥ dur (شمارشِ کندل‌هایی که close زیرِ ema_slow بوده).
  3) کلایمکسِ فروش: بدنهٔ نزولیِ کندلِ اخیر ≥ k × میانگینِ |body| اخیر (بدنهٔ استثنایی)
     AND بدنه‌های نزولیِ فزاینده در پنجرهٔ کوتاه (سرعت‌گرفتنِ فروش = خستگی).
  4) ورودِ LONG روی کندلِ بعد (shift(1) روی سیگنال).
  SL زیرِ کفِ کلایمکس (پارامتری)، TP نسبتِ R چندگانه؛ گیتِ سختِ ۴-گانه + n≥۳۰.

گیتِ پذیرش (سیب‌به‌سیب با S168/S171/S172/S173):
  net>0 کل + net>0 هر دو نیمه + WR≥۴۰٪ + walk-forward هر ۴ پنجره (net>0 & WR≥40) + n≥۳۰.

خروجی: results/_s174_sell_climax_reversal.json
================================================================================
"""
import os, sys, json
import numpy as np, pandas as pd
import warnings; warnings.filterwarnings('ignore')

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import s172_brooks_two_legs as S           # load, lastn, sim, stats, halves (زیرساختِ مشترک)
from engine import indicators as ind

WR_FLOOR = 40.0


# ============================================================================
#  سیگنالِ کلایمکسِ فروش (خستگیِ روندِ نزولی) — causal، shift-safe
# ============================================================================
def sell_climax_signals(df, ema_fast, ema_slow, dur, k_body, accel, body_win):
    """
    LONG وقتی:
      - رژیمِ نزولی: ema_fast < ema_slow،
      - روندِ نزولیِ برقرار: طیِ `dur` کندلِ اخیر، close عمدتاً زیرِ ema_slow بوده،
      - کلایمکسِ فروش: بدنهٔ نزولیِ کندلِ اخیر ≥ k_body × میانگینِ |body| اخیر،
      - در صورت accel=True: بدنهٔ نزولیِ کندلِ اخیر بزرگ‌تر از میانگینِ بدنهٔ نزولیِ
        `body_win` کندلِ قبل (سرعت‌گرفتنِ فروش = نشانهٔ خستگی).
    خروجی: بولیِ shift(1)-شده (ورود روی کندلِ بعد از کلایمکس).
    """
    o = df['open'].to_numpy(); c = df['close'].to_numpy()
    h = df['high'].to_numpy(); l = df['low'].to_numpy()
    n = len(df)
    close_s = pd.Series(c)
    ef = ind.ema(close_s, ema_fast).to_numpy()
    es = ind.ema(close_s, ema_slow).to_numpy()

    body = c - o                              # مثبت=صعودی، منفی=نزولی
    abody = np.abs(body)
    mean_body = pd.Series(abody).rolling(20).mean().to_numpy()

    # طولِ روندِ نزولی: شمارشِ کندل‌های اخیر که close<ema_slow
    below = (c < es).astype(float)
    dur_below = pd.Series(below).rolling(dur).sum().to_numpy()   # چند کندل از dur اخیر زیرِ ema

    # بدنهٔ نزولیِ استثنایی
    is_bear = body < 0
    big_bear = is_bear & (abody >= k_body * np.nan_to_num(mean_body, nan=1e18))

    # شتابِ فروش: بدنهٔ نزولیِ فعلی > میانگینِ بدنهٔ نزولیِ پنجرهٔ قبلی
    bear_body = np.where(is_bear, abody, np.nan)
    prev_bear_mean = pd.Series(bear_body).shift(1).rolling(body_win).mean().to_numpy()
    accel_ok = abody > np.nan_to_num(prev_bear_mean, nan=0.0)

    regime_down = (ef < es) & (dur_below >= max(1, int(dur * 0.6)))

    raw = regime_down & big_bear
    if accel:
        raw = raw & accel_ok

    return pd.Series(raw).shift(1).fillna(False).to_numpy()


# ============================================================================
#  ارزیابیِ یک کاندید (گیتِ کامل + walk-forward)
# ============================================================================
def walk_forward(df, sig, sl, tp, mh, asset, nwin=4):
    n = len(df); b = [int(n * i / nwin) for i in range(nwin + 1)]
    out = []
    for w in range(nwin):
        lo, hi = b[w], b[w + 1]
        sub = df.iloc[lo:hi].reset_index(drop=True)
        s = sig[lo:hi]
        z = np.zeros(hi - lo, bool)
        r = S.stats(S.sim(sub, s, z, sl, tp, mh, asset), asset)
        out.append((r['net'], r['wr'], r['n']))
    return out


def evaluate(df, asset, sig, sl, tp, mh, params):
    z = np.zeros(len(df), bool)
    tr = S.sim(df, sig, z, sl, tp, mh, asset)
    r = S.stats(tr, asset)
    if not r or r['n'] < 30:
        return None
    # lazy: walk-forward (گران) فقط وقتی net/WR پایه امیدوارکننده باشد محاسبه می‌شود
    prelim_ok = (r['net'] > 0 and r['wr'] >= WR_FLOOR)
    if prelim_ok:
        hv = S.halves(df, sig, z, sl, tp, mh, asset)
        both_ok = bool(hv and hv['h1'] > 0 and hv['h2'] > 0)
        if both_ok:
            wf = walk_forward(df, sig, sl, tp, mh, asset)
            wf_ok = all(x[0] > 0 and x[1] >= WR_FLOOR for x in wf)
        else:
            wf, wf_ok = [], False
    else:
        hv, both_ok, wf, wf_ok = None, False, [], False
    accept = bool(r['net'] > 0 and r['wr'] >= WR_FLOOR and both_ok and wf_ok)
    d = dict(asset=asset, side='long', sl=sl, tp=tp, mh=mh,
             net=round(r['net'], 1), wr=round(r['wr'], 2), n=r['n'],
             pf=round(r['pf'], 3) if r['pf'] != float('inf') else 999.0,
             h1=round(hv['h1'], 1) if hv else None,
             h2=round(hv['h2'], 1) if hv else None,
             wf=[(round(x[0], 1), round(x[1], 1), x[2]) for x in wf],
             wf_ok=wf_ok, both_ok=both_ok, accepted=accept)
    d.update(params)
    return d


def main():
    print("=" * 100)
    print("S174 — Al Brooks «Sell-Climax Exhaustion Reversal» (فصلِ ۲): LONG در خستگیِ روندِ نزولی")
    print("گیت: net>0 + هر دو نیمه + walk-forward هر ۴ پنجره + WR≥40 + n≥30. هدف = سودِ خالصِ بیشتر.")
    print("=" * 100, flush=True)

    grids = {
        'XAUUSD': [(200, 300), (250, 375), (300, 450), (400, 600)],
        'EURUSD': [(20, 30), (30, 45), (40, 60)],
    }
    mhs = [24, 48, 96]
    ema_pairs = [(20, 50), (10, 30)]
    durs = [20, 30]
    k_bodies = [1.6, 2.0, 2.5]
    body_wins = [5, 10]

    results = []
    accepted = []

    for asset in ('XAUUSD', 'EURUSD'):
        df = S.lastn(S.load(asset + '_M15'))
        print(f"\n### {asset}  (rows={len(df)}) ###", flush=True)
        for (ef, es) in ema_pairs:
            for dur in durs:
                for kb in k_bodies:
                    for accel in (True, False):
                        for bw in body_wins:
                            params = dict(ema_fast=ef, ema_slow=es, dur=dur,
                                          k_body=kb, accel=accel, body_win=bw)
                            sig = sell_climax_signals(df, ef, es, dur, kb, accel, bw)
                            if sig.sum() < 30:
                                continue
                            for (sl, tp) in grids[asset]:
                                for mh in mhs:
                                    r = evaluate(df, asset, sig, sl, tp, mh, params)
                                    if r is None:
                                        continue
                                    results.append(r)
                                    if r['accepted']:
                                        accepted.append(r)

        best = sorted([x for x in results if x['asset'] == asset], key=lambda x: -x['net'])[:8]
        print(f"  بهترین‌های {asset} (top by net):")
        for x in best:
            tag = '✅ACCEPT' if x['accepted'] else 'reject '
            print(f"    {tag} ema{x['ema_fast']}/{x['ema_slow']} dur{x['dur']} k{x['k_body']} "
                  f"accel{int(x['accel'])} bw{x['body_win']} SL{x['sl']}/TP{x['tp']}/mh{x['mh']}  "
                  f"net=${x['net']:+,.0f} WR={x['wr']:.1f}% n={x['n']} PF={x['pf']:.2f} "
                  f"wf_ok={x['wf_ok']} both={x['both_ok']}")

    os.makedirs(S.RESULTS, exist_ok=True)
    out = dict(strategy='S174_SellClimaxReversal_ch2',
               n_total=len(results), n_accepted=len(accepted),
               results=results, accepted=sorted(accepted, key=lambda x: -x['net']))
    with open(os.path.join(S.RESULTS, '_s174_sell_climax_reversal.json'), 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=float)
    print(f"\n✅ ذخیره شد: results/_s174_sell_climax_reversal.json "
          f"(کل={len(results)}، پذیرفته={len(accepted)})")
    if accepted:
        top = sorted(accepted, key=lambda x: -x['net'])[0]
        print(f"\n🏆 بهترینِ پذیرفته: {top['asset']} net=${top['net']:+,.0f} "
              f"WR={top['wr']:.1f}% n={top['n']} PF={top['pf']:.2f}")


if __name__ == '__main__':
    main()
